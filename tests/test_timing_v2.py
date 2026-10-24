"""Quality v2 timing: scenes follow the voice exactly (multi-line scenes included), cue phrases resolve to the moment
the word is spoken, and the sound cue sheet lands transitions and declared cues at absolute times."""
import json

from frameflow import build


def voice_dir(tmp_path, lines, words):
    (tmp_path / "durations.json").write_text(json.dumps({"lines": lines, "total": 10}))
    (tmp_path / "words.json").write_text(json.dumps(words))
    return tmp_path


def plan():
    return {"id": "t", "lane": "global-tech", "title": "t", "version": 2, "scenes": [
        {"type": "kinetic", "say": "Parts of the internet went dark.", "data": {"lines": [{"t": "DARK"}], "cues": {"dark": "went dark"}}},
        {"type": "street", "say": "On purpose. Really.", "lines": [{"say": "On purpose."}, {"say": "Really."}], "enter": "whip-left",
         "data": {"buildings": [{"label": "A"}, {"label": "B"}]}, "sfx": [{"at": "start", "name": "slam"}]},
        {"type": "kinetic", "say": "Why?", "enter": "punch", "data": {"lines": [{"t": "WHY"}]}}]}


def test_scenes_follow_voice_lines(tmp_path):
    vd = voice_dir(tmp_path, [{"id": "s0", "start": 0.0, "seconds": 2.0}, {"id": "s1.0", "start": 2.3, "seconds": 0.9},
                              {"id": "s1.1", "start": 3.6, "seconds": 0.5}, {"id": "s2", "start": 4.6, "seconds": 0.4}], [])
    slots = build.timings(plan(), vd)
    assert slots[0] == (0.0, 2.3)
    assert slots[1] == (2.3, 2.3)          # both lines of scene 1, up to scene 2's line
    assert slots[2][0] == 4.6


def test_cue_resolves_to_spoken_word():
    words = [{"w": "Parts", "s": 0.0, "e": 0.3}, {"w": "of", "s": 0.3, "e": 0.4}, {"w": "the", "s": 0.4, "e": 0.5},
             {"w": "internet", "s": 0.5, "e": 0.9}, {"w": "went", "s": 1.1, "e": 1.3}, {"w": "dark.", "s": 1.3, "e": 1.7}]
    cues = build.cue_times(plan()["scenes"][0], 0.0, 2.3, words)
    assert cues["dark"] == round(1.1 - 0.06, 3)
    assert cues["end"] == round(2.3 - 0.35, 3)


def test_sfx_sheet_absolute_times():
    slots = [(0.0, 2.3), (2.3, 2.3), (4.6, 1.0)]
    cues = [{"start": 0.0}, {"start": 0.0}, {"start": 0.0}]
    sheet = build.sfx_sheet(plan(), slots, cues)
    names = [(c["name"], c["t"]) for c in sheet]
    assert ("whoosh", round(2.3 - 0.12, 3)) in names    # transition into scene 1
    assert ("slam", 2.3) in names                        # declared cue at scene 1's start
    assert ("slam", round(4.6 - 0.12, 3)) in names       # punch transition into scene 2
