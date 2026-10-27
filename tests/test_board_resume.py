"""A make stopped after the plan (usage limit) resumes at the narrator: no second writer/director call (26 Oct board test)."""
import json

import pytest

from frameflow import analyst, board, direct


@pytest.fixture()
def world(tmp_path, monkeypatch):
    out = tmp_path / "out"
    brief = tmp_path / "brief.json"
    brief.write_text("{}")
    calls = []

    def fake_direct(b, o, lane, sw, sd):
        calls.append("direct")
        (out / "plan.json").write_text("{}")
        return {"errors": [], "plan": str(out / "plan.json")}
    monkeypatch.setattr(analyst, "run_sheet", lambda b, o: {"videos_with_results": 0, "evidence": []})
    monkeypatch.setattr(board, "package", lambda b, o: out.mkdir(exist_ok=True))
    monkeypatch.setattr(direct, "direct", fake_direct)
    return out, brief, calls, monkeypatch


def test_resume_skips_writer_after_a_stop(world):
    out, brief, calls, mp = world
    def stopped(*a, **k):
        calls.append("run")
        raise RuntimeError("model call failed: You've hit your session limit · resets 2:10am (Asia/Kolkata)")
    mp.setattr(board, "run", stopped)
    with pytest.raises(RuntimeError):
        board.make(brief, "ai", out)
    assert json.loads((out / board.CHECKPOINT).read_text())["plan"] == str(out / "plan.json")
    mp.setattr(board, "run", lambda *a, **k: calls.append("run") or {"status": "rendered"})
    assert board.make(brief, "ai", out)["status"] == "rendered"
    assert calls == ["direct", "run", "run"]          # the writer and director ran once
    assert not (out / board.CHECKPOINT).exists()      # a finished make leaves no checkpoint


def test_other_brief_does_not_resume(world):
    out, brief, calls, mp = world
    out.mkdir()
    (out / "plan.json").write_text("{}")
    (out / board.CHECKPOINT).write_text(json.dumps({"brief": "another.json", "plan": str(out / "plan.json")}))
    mp.setattr(board, "run", lambda *a, **k: calls.append("run") or {"status": "rendered"})
    board.make(brief, "ai", out)
    assert calls == ["direct", "run"]


def test_limit_error_is_not_retried(monkeypatch, tmp_path):
    from frameflow import review
    n = []
    def fail(*a, **k):
        n.append(1)
        raise RuntimeError("screening.py failed: You've hit your session limit · resets 2:10am (Asia/Kolkata)")
    monkeypatch.setattr(direct, "skill", fail)
    with pytest.raises(RuntimeError):
        review._screening("screen", [], tmp_path / "x.json")
    assert len(n) == 1
