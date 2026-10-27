"""The building's replay timeline (P16): a real make (28 Oct, GPS spoofing) read back from its progress log."""
from pathlib import Path

from frameflow import boardview

LOG = Path(__file__).resolve().parent / "fixtures" / "progress-board-make.jsonl"


def test_timeline_follows_the_make():
    t = boardview.make_timeline(LOG)
    s = boardview.make_summary(LOG)
    ev = t["events"]
    assert [e["t"] for e in ev] == sorted(e["t"] for e in ev)
    assert ev[0]["desk"] == "researcher" and ev[0]["t"] == 0
    # every desk the summary counts shows up in the timeline, and nothing else
    assert {e["desk"] for e in ev} == {d["desk"] for d in s["desks"]}
    # both fix rounds (one text, one animatic) are flagged, and writer and director run in each
    fixed = [e for e in ev if e.get("fix")]
    assert s["fix_rounds"] == 2
    assert [e["desk"] for e in fixed if e["desk"] != "packaging"] == ["writer", "director", "writer", "director"]
    # one delivery render, after the last screening of the animatic
    renders = [e for e in ev if e["label"] == "render frames"]
    assert len(renders) == s["renders"] == 1
    assert renders[0]["t"] > max(e["t"] for e in ev if e["label"] == "screening on the animatic")
    # gates and scores carry through, with a one-line snippet for the bubbles
    editor = [e for e in ev if e["desk"] == "editor"]
    assert [e["score"] for e in editor] == ["10/16", "8/16", "12/16"] and editor[-1]["gate"] is True
    assert all(len(e.get("say", "")) <= 120 for e in ev)
    assert t["seconds"] >= ev[-1]["t"]


def test_no_make_no_timeline(tmp_path):
    assert boardview.make_timeline(tmp_path / "missing.jsonl") is None
    f = tmp_path / "p.jsonl"
    f.write_text('{"t": "2026-10-27T10:00:00", "ev": "start", "id": "1", "parent": null, "step": "post"}\n')
    assert boardview.make_timeline(f) is None
