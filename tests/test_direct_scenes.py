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
