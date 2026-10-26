"""P15.4.3: the Revise conversation on Telegram, with Telegram, the job spawner and the issue list stubbed.

Revise -> the known issues as toggles -> Done (or own words) -> the showrunner job -> the order with Go / Change it /
Cancel -> Go spawns the revise; Change it waits for new words; Cancel brings the video card back.
"""
import json

import pytest

from frameflow import bot, daily, producer, telegram

DAY = "2099-02-01"


@pytest.fixture()
def sb(tmp_path, monkeypatch):
    monkeypatch.setattr(daily, "DB", tmp_path / "frameflow.db")
    log = {"sent": [], "edited": [], "cleared": [], "spawned": [], "cards": 0}
    monkeypatch.setattr(telegram, "send", lambda text, buttons=None, chat=None: log["sent"].append((text, buttons)) or len(log["sent"]) + 100)
    monkeypatch.setattr(telegram, "edit_buttons", lambda mid, b: log["edited"].append((mid, b)))
    monkeypatch.setattr(telegram, "clear_buttons", lambda mid, note=None: log["cleared"].append(mid))
    monkeypatch.setattr(telegram, "answer", lambda *a, **k: None)
    monkeypatch.setattr(daily, "spawn", lambda step, day: log["spawned"].append(step) or 4242)
    monkeypatch.setattr(daily, "video_card", lambda day: log.__setitem__("cards", log["cards"] + 1))
    monkeypatch.setattr(producer, "issues", lambda day: ["hook: the stake comes late", "pacing: a 3 s gap at 103 s", "check 'rehooks' failed: 11.9 s"])
    con = daily.db()
    con.execute("INSERT INTO runs (day, lane, state, video_id, revisions, video_msg, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?)",
                (DAY, "ai-money", "video-sent", "v1", 0, 77, daily.now().isoformat(), daily.now().isoformat()))
    con.commit()
    return log


def tap(data):
    bot.on_callback({"id": "cb", "data": data, "message": {"message_id": 1}})


def test_issues_toggle_done_go(sb):
    tap(f"revise:{DAY}")
    run = daily.get(DAY)
    assert run["state"] == "awaiting-notes" and run["revisions"] == 1 and 77 in sb["cleared"]
    text, buttons = sb["sent"][-1]
    assert "1. hook: the stake comes late" in text and [b[0] for b in buttons[0]] == ["1", "2", "3"]
    tap(f"iss:{DAY}:1")
    assert json.loads(daily.get(DAY)["revise_picks"]) == [1] and sb["edited"][-1][1][0][1][0] == "✓2"
    tap(f"iss:{DAY}:1")
    assert json.loads(daily.get(DAY)["revise_picks"]) == []
    tap(f"issdone:{DAY}")
    assert "Tick at least one" in sb["sent"][-1][0] and not sb["spawned"]
    tap(f"issall:{DAY}")
    tap(f"issdone:{DAY}")
    assert daily.get(DAY)["state"] == "ordering" and sb["spawned"] == ["order"]
    daily.update(DAY, state="order-sent", order_msg="150", order_file="/tmp/x.json")   # what daily.order leaves behind
    tap(f"ordgo:{DAY}")
    assert daily.get(DAY)["state"] == "making" and sb["spawned"] == ["order", "revise"]


def test_own_words_then_change_it_then_cancel(sb):
    tap(f"revise:{DAY}")
    bot.on_text("bhai hook boring hai, aur music thoda kam karo")
    run = daily.get(DAY)
    assert run["state"] == "ordering" and run["notes"].startswith("bhai hook") and sb["spawned"] == ["order"]
    daily.update(DAY, state="order-sent", order_msg="150", order_file="/tmp/x.json")
    tap(f"ordchg:{DAY}")
    assert daily.get(DAY)["state"] == "awaiting-notes" and daily.get(DAY)["order_file"] is None
    bot.on_text("music theek hai, sirf hook")
    assert "Then: music theek hai" in daily.get(DAY)["notes"] and sb["spawned"] == ["order", "order"]
    daily.update(DAY, state="order-sent", order_msg="151", order_file="/tmp/y.json")
    tap(f"ordno:{DAY}")
    run = daily.get(DAY)
    assert run["state"] == "video-sent" and run["revisions"] == 0 and sb["cards"] == 1


def test_stale_buttons_do_nothing(sb):
    tap(f"ordgo:{DAY}")   # no order was sent
    assert daily.get(DAY)["state"] == "video-sent" and not sb["spawned"]
