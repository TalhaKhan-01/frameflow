"""P15.6.1: the analyst groups results by desk decision, shows sample sizes, and feeds the run sheet from 3 videos on."""
import json

from frameflow import analyst


def _rows(tmp_path, monkeypatch, n):
    f = tmp_path / "analyst.jsonl"
    data = [("bold-claim", 900, "75-100 s"), ("question", 300, "over 100 s"), ("bold-claim", 700, "75-100 s"), ("question", 200, "over 100 s")][:n]
    f.write_text("".join(json.dumps({"video": f"v{i}", "decisions": {"hook_family": h, "length": L, "ending": "twist", "lane": "ai-news"},
                                     "results": {"youtube": {"views": v}}}) + "\n" for i, (h, v, L) in enumerate(data)))
    monkeypatch.setattr(analyst, "FILE", f)


def test_summary_groups_by_decision(tmp_path, monkeypatch):
    _rows(tmp_path, monkeypatch, 4)
    s = analyst.summary()
    assert s["videos"] == 4 and list(s["by"]["hook_family"]) == ["bold-claim", "question"]
    assert s["by"]["hook_family"]["bold-claim"] == {"n": 2, "median_views": 800.0}
    lines = analyst.evidence_lines(s)
    assert "'bold-claim' did best (median 800 views, n=2)" in lines[1] and "small samples" in lines[0]


def test_run_sheet_waits_for_three_videos_then_adds_evidence(tmp_path, monkeypatch):
    brief = tmp_path / "brief.json"
    brief.write_text(json.dumps({"topic": "t", "notes": "n"}))
    _rows(tmp_path, monkeypatch, 2)
    assert analyst.run_sheet(brief, tmp_path / "out")["evidence"] == [] and json.loads(brief.read_text())["notes"] == "n"
    _rows(tmp_path, monkeypatch, 4)
    analyst.run_sheet(brief, tmp_path / "out")
    analyst.run_sheet(brief, tmp_path / "out")   # twice: the evidence goes in once
    notes = json.loads(brief.read_text())["notes"]
    assert notes.count("Evidence from our last") == 1 and "bold-claim" in notes and (tmp_path / "out" / "run-sheet.json").exists()
