"""The director fixes only the named scenes when every note names them and the script's beats didn't move."""
import json

import pytest

from frameflow import direct


def test_scenes_named():
    assert direct.scenes_named(["pacing: scene 16 (chat): add a beat", "flow: KEEP unchanged: the ending"]) == [16]
    assert direct.scenes_named(["pacing: Scenes 2-4 are slow", "sound_plan: scene(s) 7, 9: quieter"]) == [2, 3, 4, 7, 9]
    assert direct.scenes_named(["pacing: scene 3 is slow", "pacing: the whole thing drags"]) is None


@pytest.fixture()
def world(tmp_path, monkeypatch):
    (tmp_path / "writer").mkdir()
    (tmp_path / "director").mkdir()
    (tmp_path / "writer" / "script.json").write_text(json.dumps({"beats": [{}, {}, {}]}))
    calls = []

    def fake_skill(args, timeout=3600, strict=False):
        calls.append([str(a) for a in args])
        if "writer.py" in str(args[0]) and "drop-a-beat" in (tmp_path / "flag").read_text():
            (tmp_path / "writer" / "script.json").write_text(json.dumps({"beats": [{}, {}]}))
        return ""
    monkeypatch.setattr(direct, "skill", fake_skill)
    monkeypatch.setattr(direct, "direct", lambda *a, **k: {"plan": "p", "errors": []})
    return tmp_path, calls


def director_args(calls):
    return next(c for c in calls if "director.py" in c[0])


def test_scene_notes_fix_only_those_scenes(world):
    out, calls = world
    (out / "flag").write_text("")
    direct.revise("brief.json", out, {"fixes": [{"row": "pacing", "fix": "scene 16 (chat): add a beat"}]})
    args = director_args(calls)
    assert args[args.index("--scenes") + 1] == "16" and not any("writer.py" in c[0] for c in calls)


def test_beats_moved_or_global_note_means_full_fix(world):
    out, calls = world
    (out / "flag").write_text("drop-a-beat")
    direct.revise("brief.json", out, {"fixes": [{"row": "story", "fix": "scene 2: sharper"}, {"row": "pacing", "fix": "scene 16: a beat"}]})
    assert "--scenes" not in director_args(calls), "the writer changed the beats: the whole storyboard is re-mapped"
    calls.clear()
    (out / "flag").write_text("")
    direct.revise("brief.json", out, {"fixes": [{"row": "pacing", "fix": "the whole thing drags"}]})
    assert "--scenes" not in director_args(calls)


# ---------- P15.6.7: notes scoped to scenes, the writer and the director stay inside them ----------
from pathlib import Path

FX = json.loads((Path(__file__).parent / "fixtures" / "notes-2026-10-28-round2.json").read_text())


def test_note_scope_reads_scenes_times_hook_and_cover():
    slots = [(0.0, 5.0), (5.0, 10.0), (15.0, 10.0), (25.0, 5.0)]
    assert direct.note_scope("flow: Scene 4 to Scene 6 drags", slots, 3) == {4, 5, 6}
    assert direct.note_scope("pacing: around 17 s a viewer would leave", slots, 3) == {2}
    assert direct.note_scope("captions: overlaps at 4 to 6s", slots, 3) == {0, 1}
    assert direct.note_scope("captions: overlaps at 27s", slots, 3) == "cover"   # only the end card is there
    assert direct.note_scope("honesty: the hook's claim overreaches; see Scene 2", slots, 3) == {0, 2}
    assert direct.note_scope("sources: the end card stat is unsourced", slots, 3) == "cover"
    assert direct.note_scope("flow: KEEP unchanged: the ending", slots, 3) == "keep"
    assert direct.note_scope("pacing: the whole thing drags", slots, 3) is None
    assert direct.scope(["flow: scene 1 is slow", "sources: the end card stat"], slots, 3) == {1}
    assert direct.scope(["flow: scene 1 is slow", "pacing: the whole thing drags"], slots, 3) is None


def test_real_28_oct_notes_all_scoped():
    """Every note of the 28 Oct round 2 maps to scenes, so neither desk falls back to a full rewrite."""
    w = direct.scope(FX["writer"], FX["slots"], FX["story_scenes"])
    d = direct.scope(FX["director"], FX["slots"], FX["story_scenes"])
    assert w is not None and d is not None
    assert len(w) < FX["story_scenes"] and len(d) < FX["story_scenes"]


def test_scoped_round_passes_beats_and_scenes(world):
    out, calls = world
    (out / "flag").write_text("")
    board = {"scenes": [{"beats": [0]}, {"beats": [1]}, {"beats": [2]}]}
    (out / "director" / "storyboard.json").write_text(json.dumps(board))
    direct.revise("brief.json", out, {"fixes": [{"row": "flow", "fix": "Scene 1: the line is written, not spoken"},
                                                  {"row": "pacing", "fix": "scene 2: add a beat on 'trust'"}]})
    w = next(c for c in calls if "writer.py" in c[0])
    assert w[w.index("--beats") + 1] == "1"
    d = director_args(calls)
    assert d[d.index("--scenes") + 1] == "1,2", "the director redraws the named scene and the one whose words changed"
    assert "re-time their cues" in (out / "review1-director-notes.txt").read_text()


def test_unscoped_writer_note_means_full_fixes(world):
    out, calls = world
    (out / "flag").write_text("")
    (out / "director" / "storyboard.json").write_text(json.dumps({"scenes": [{"beats": [0]}, {"beats": [1]}, {"beats": [2]}]}))
    direct.revise("brief.json", out, {"fixes": [{"row": "story", "fix": "the story never builds"}, {"row": "pacing", "fix": "scene 2: a beat"}]})
    assert "--beats" not in next(c for c in calls if "writer.py" in c[0])
    assert "--scenes" not in director_args(calls), "a whole-script rewrite moves words everywhere: full director"
