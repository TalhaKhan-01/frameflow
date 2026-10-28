"""A daily card post goes out with its day's Short: when the Short's post time moves, the carousel moves with it (28 Oct:
the Short was moved to 10:32 for a test and the carousel stayed at 11:30)."""
import json

import pytest

from frameflow import cards, daily, telegram


@pytest.fixture()
def sandbox(tmp_path, monkeypatch):
    db = tmp_path / "frameflow.db"
    monkeypatch.setattr(daily, "DB", db)
    monkeypatch.setattr(cards, "DB", db)
    spawned = []
    monkeypatch.setattr(telegram, "send", lambda *a, **k: 1)
    monkeypatch.setattr(cards, "spawn", lambda step, run: spawned.append((step, run)))
    monkeypatch.setattr(daily, "spawn", lambda step, day: spawned.append((step, day)) or 4242)
    monkeypatch.setattr(daily, "stats_due", lambda: [])
    daily.db()
    return spawned


def add_short(day, state, post_at):
    con = daily.db()
    con.execute("INSERT INTO runs (day, lane, state, options, post_at, log, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?)",
                (day, "ai-news", state, json.dumps([]), post_at, "", "2026-10-28T09:00:00", "2026-10-28T09:00:00"))
    con.commit()


def add_card(day, post_at, state="queued"):
    con = cards.db()
    con.execute("INSERT INTO card_runs (id, state, day, post_at, log, created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
                (f"cards-{day}", state, day, post_at, "", "2026-10-28T09:00:00", "2026-10-28T09:00:00"))
    con.commit()


def test_follow_time_leads_with_the_short_only_while_it_is_going_out(sandbox):
    add_card("2026-10-28", "2026-10-28T11:30:00")
    assert cards.follow_time(cards.get("cards-2026-10-28")) == "2026-10-28T11:30:00"   # no Short: own time
    add_short("2026-10-28", "queued", "2026-10-28T10:32:00")
    assert cards.follow_time(cards.get("cards-2026-10-28")) == "2026-10-28T10:32:00"
    daily.update("2026-10-28", state="rejected")
    assert cards.follow_time(cards.get("cards-2026-10-28")) == "2026-10-28T11:30:00"


def test_tick_moves_and_posts_the_carousel_with_the_short(sandbox, monkeypatch):
    import datetime as dt
    add_short("2026-10-28", "queued", "2026-10-28T10:32:00")
    add_card("2026-10-28", "2026-10-28T11:30:00")
    monkeypatch.setattr(daily, "now", lambda: dt.datetime(2026, 10, 28, 10, 20))
    daily.tick()
    cr = cards.get("cards-2026-10-28")
    assert cr["state"] == "queued" and cr["post_at"] == "2026-10-28T10:32:00" and "follows the Short" in cr["log"]
    monkeypatch.setattr(daily, "now", lambda: dt.datetime(2026, 10, 28, 10, 32, 30))
    daily.tick()
    assert cards.get("cards-2026-10-28")["state"] == "posting"
    assert ("post", "cards-2026-10-28") in sandbox and ("post", "2026-10-28") in sandbox
