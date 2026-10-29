"""The hook card (P25.1.2): a tap, an Improve in Talha's words and a timeout each end with the chosen open in
script.json. Model calls and Telegram are stubbed; the make's wait loop runs for real on hooks.json."""
import datetime as dt
import json

import pytest

from frameflow import daily, hookpick, llm, telegram

SCRIPT = {"open": {"say": "Breaking: the writer's open about a big lab and a payments app today.", "emotion": "excited"},
          "table_read": {"rows": {"hook": 1}}}
HOOKS = [{"say": f"Breaking: hook number {w} teases the top stories with a stake for you.", "family": "stake", "score": 90 - i, "why": "w"}
         for i, w in enumerate(["one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven"])]


@pytest.fixture
def env(monkeypatch, tmp_path):
    sent = []
    monkeypatch.setattr(telegram, "send", lambda text, buttons=None: sent.append((text, buttons)) or len(sent))
    monkeypatch.setattr(telegram, "clear_buttons", lambda *a: sent.append(("clear", a)))
    monkeypatch.setattr(daily, "update", lambda *a, **k: None)
    monkeypatch.setattr(hookpick, "path_for", lambda day: tmp_path / "hooks.json")
    monkeypatch.setattr(hookpick, "valid", lambda say, script, data: [] if say.startswith("Breaking") else ["open must start"])
    monkeypatch.setattr(hookpick, "cfg", lambda: {"enabled": True, "count": 10, "wait_minutes": 20, "model": "sonnet"})
    calls = []

    def fake(prompt, system, schema, **k):
        calls.append(k["purpose"])
        if k["purpose"] == "show.hooks":
            return {"hooks": HOOKS + [{"say": "No prefix so it is dropped from the card.", "family": "x", "score": 99, "why": ""}]}
        return {"say": "the jobs angle: IT stocks wobble as a giant lab files to go public"}
    monkeypatch.setattr(llm, "call", fake)
    return tmp_path, sent, calls


def test_card_lists_ten_valid_hooks_and_a_tap_chooses(env, monkeypatch):
    out, sent, _ = env
    hooks = hookpick.options(SCRIPT, {"stories": []})
    assert len(hooks) == 10 and all(h["say"].startswith("Breaking") for h in hooks)
    assert hooks[-1]["family"] == "writer's open", "the writer's open always stays on the card"
    assert not any("No prefix" in h["say"] for h in hooks)
    deadline = daily.now() + dt.timedelta(minutes=20)
    hookpick.save(out / "hooks.json", {"status": "waiting", "hooks": hooks, "deadline": deadline.isoformat(), "msg": 1, "history": []})
    hookpick.on_tap("hk", "d", "3")
    s = hookpick.pick(SCRIPT, {"stories": []}, out, "d", poll=0)
    assert s["open"]["say"] == hooks[2]["say"] and s["hook_pick"]["by"] == "tap"
    assert json.loads((out / "script.json").read_text())["open"]["say"] == hooks[2]["say"]


def test_improve_rewrites_resends_and_timeout_takes_hook_one(env, monkeypatch):
    out, sent, calls = env
    past = (daily.now() - dt.timedelta(minutes=1)).isoformat()
    hookpick.save(out / "hooks.json", {"status": "waiting", "hooks": HOOKS[:10], "deadline": past, "msg": 1, "history": []})
    hookpick.on_tap("hkimp", "d")
    hookpick.on_text("d", "4 make it about jobs")
    h = json.loads((out / "hooks.json").read_text())
    assert h["status"] == "improve-ready" and h["improve"] == {"n": 4, "words": "make it about jobs"}
    monkeypatch.setattr(hookpick, "cfg", lambda: {"enabled": True, "count": 10, "wait_minutes": 0, "model": "sonnet"})
    s = hookpick.pick(SCRIPT, {"stories": []}, out, "d", poll=0)
    assert "show.hook-improve" in calls
    assert s["open"]["say"].startswith("Breaking: the jobs angle") and s["hook_pick"]["by"] == "timeout"
    h = json.loads((out / "hooks.json").read_text())
    assert h["hooks"][0]["family"] == "your edit of 4" and len(h["hooks"]) == 10 and h["history"][0]["words"] == "make it about jobs"
    assert any("your edit of 4 is now 1" in t for t, *_ in sent if isinstance(t, str))


def test_write_my_own(env):
    out, sent, _ = env
    future = (daily.now() + dt.timedelta(minutes=20)).isoformat()
    hookpick.save(out / "hooks.json", {"status": "waiting", "hooks": HOOKS[:10], "deadline": future, "msg": 1, "history": []})
    hookpick.on_tap("hkown", "d")
    hookpick.on_text("d", "Anthropic just made Indian IT nervous, and Free Fire is back")
    s = hookpick.pick(SCRIPT, {"stories": []}, out, "d", poll=0)
    assert s["open"]["say"] == "Breaking: Anthropic just made Indian IT nervous, and Free Fire is back" and s["hook_pick"]["by"] == "own"


def test_closed_card_says_so(env):
    out, sent, _ = env
    hookpick.save(out / "hooks.json", {"status": "chosen", "hooks": HOOKS[:10], "deadline": "", "msg": 1, "history": [],
                                       "choice": {"n": 1, "say": HOOKS[0]["say"], "by": "tap"}})
    hookpick.on_tap("hk", "d", "2")
    assert "closed" in sent[-1][0]
