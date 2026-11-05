"""The coach (P11): rules under test are credited against each review row's baseline, promoted, retired, and re-weighted
by audience stats; no model calls here (record(..., propose=False))."""
import json
import random

import pytest

from frameflow import coach


@pytest.fixture
def state(tmp_path, monkeypatch):
    monkeypatch.setattr(coach, "STATE", tmp_path / "coach.json")
    monkeypatch.setattr(coach, "TICKETS", tmp_path / "tickets.jsonl")
    return tmp_path


def episode(root, name, rows, fixes=(), used=None):
    d = root / name
    d.mkdir()
    (d / "review.json").write_text(json.dumps({"rows": rows, "fixes": list(fixes)}))
    if used is not None:
        (d / "coach-used.json").write_text(json.dumps(used))
    return d


def test_playbook_gives_champions_and_at_most_two_trials(state):
    s = coach.load()
    champ = coach.add_rule(s, "writer", "script hook", "Open on the biggest number.", "t")
    champ["status"] = "champion"
    for i in range(4):
        coach.add_rule(s, "writer", "script flow", f"Trial rule {i}.", "t")
    coach.add_rule(s, "visuals", "screen readability", "Crop to the headline.", "t")
    coach.save(s)
    text = coach.playbook("writer", state, rng=random.Random(1))
    used = json.loads((state / "coach-used.json").read_text())["writer"]
    assert used["champions"] == [champ["id"]] and len(used["trials"]) == 2
    assert "Open on the biggest number." in text and "Crop to the headline." not in text


def test_record_credits_rules_against_the_row_baseline(state):
    s = coach.load()
    good = coach.add_rule(s, "writer", "script flow", "Hand off with a link word.", "t")
    bad = coach.add_rule(s, "writer", "script hook", "Open with a question.", "t")
    coach.save(s)
    episode(state, "ep1", {"script flow": 1, "script hook": 2})
    coach.record(state / "ep1", propose=False)                       # sets the baselines, no rules used yet
    used = {"writer": {"champions": [], "trials": [good["id"], bad["id"]]}}
    episode(state, "ep2", {"script flow": 2, "script hook": 1}, used=used)
    res = coach.record(state / "ep2", propose=False)
    rules = {r["id"]: r for r in coach.load()["rules"]}
    assert rules[good["id"]]["alpha"] == 2 and rules[good["id"]]["beta"] == 1
    assert rules[bad["id"]]["alpha"] == 1 and rules[bad["id"]]["beta"] == 2
    assert sorted(res["scored"]) == sorted([good["id"], bad["id"]])
    assert coach.load()["baselines"]["script flow"] == pytest.approx(0.6 * 1 + 0.4 * 2)
    assert coach.record(state / "ep2", propose=False).get("skipped")  # an episode is recorded once


def test_promotion_retirement_and_template_tickets(state):
    s = coach.load()
    up = coach.add_rule(s, "writer", "script flow", "Up.", "t")
    up.update(alpha=6, beta=1, trials=5)
    down = coach.add_rule(s, "writer", "script hook", "Down.", "t")
    down.update(alpha=1, beta=6, trials=5)
    changes = coach.decide(s)
    assert up["status"] == "champion" and down["status"] == "retired" and len(changes) == 2
    coach.save(s)
    episode(state, "ep3", {"screen look": 1}, fixes=[{"row": "look", "fix": "Props are cut off at the frame edge."},
                                                    {"row": "story", "fix": "Name the speaker."}])
    assert coach.record(state / "ep3", propose=False)["tickets"] == 1
    assert "cut off" in coach.TICKETS.read_text()


def test_audience_stats_give_half_a_point(state):
    s = coach.load()
    r = coach.add_rule(s, "writer", "script hook", "Open on a number.", "t")
    coach.save(s)
    d = state / "ep4"
    d.mkdir()
    (d / "coach-used.json").write_text(json.dumps({"writer": {"champions": [], "trials": [r["id"]]}}))
    assert "not scored" in coach.stats("ep4", d, "avg % viewed", 60, [50, 55])
    coach.stats("ep4", d, "avg % viewed", 60, [50, 55, 52])
    got = coach.load()["rules"][0]
    assert got["alpha"] == 1.5 and got["beta"] == 1.0 and got["trials"] == 0
