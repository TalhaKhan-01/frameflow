"""One re-hook definition (QA, narrator checks, writer lint) and every long stretch reported at once (27 Oct test)."""
import json

from frameflow import qa


def test_is_rehook():
    assert qa.is_rehook({"beat": "payoff", "devices": [], "say": "So the weak spot was trust."})
    assert qa.is_rehook({"beat": "ending", "devices": ["straight"], "say": "What else do we trust?"})
    assert qa.is_rehook({"beat": "and", "devices": ["rehook"], "say": "Here's the catch."})
    # since 5 Nov (Review Queue item 3, option a) a question counts wherever it's spoken in the line
    assert qa.is_rehook({"beat": "and", "devices": ["straight"], "say": "And the pickup? A real driver."})
    assert not qa.is_rehook({"beat": "and", "devices": ["straight"], "say": "One rack costs a lot."})


def test_mid_line_question_counts_where_it_is_spoken():
    assert qa.rehook_share({"beat": "and", "devices": [], "say": "Why AI cargo, though? One rack costs a lot."}) == 0.0
    assert qa.rehook_share({"beat": "and", "devices": [], "say": "One rack costs a lot. Why though?"}) == 5 / 7
    assert qa.rehook_share({"beat": "but", "devices": [], "say": "One rack costs a lot."}) == 0.0


def test_every_stretch_over_the_limit(tmp_path):
    lines = [("hook", "x", 0.0), ("and", "a", 3.0), ("and", "b", 9.0), ("but", "c", 16.0), ("and", "d", 20.0), ("and", "e", 28.0),
             ("ending", "f", 31.0)]
    scenes = [{"type": "t", "lines": [{"beat": b, "devices": [], "say": s}]} for b, s, _ in lines] + [{"type": "endcard", "lines": [{"beat": "outro", "devices": [], "say": "Follow."}]}]
    (tmp_path / "plan.json").write_text(json.dumps({"scenes": scenes}))
    (tmp_path / "voice").mkdir()
    dl = [{"id": f"s{i}", "start": t} for i, (_, _, t) in enumerate(lines)] + [{"id": f"s{len(lines)}", "start": 33.0}]
    (tmp_path / "voice" / "durations.json").write_text(json.dumps({"lines": dl, "total": 36.0}))
    over = qa.rehook_stretches(tmp_path, 10.5)
    assert [round(g, 1) for g, *_ in over] == [17.0, 16.0]   # 16 -> 33 (end card) and 0 -> 16; both, longest first
    assert qa.rehook_gaps(tmp_path) == 17.0
