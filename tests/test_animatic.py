"""P15.1.2 / P15.2.1: the animatic and the narrator checks see what QA sees after the delivery render, before it.

Uses the Kimi video (26 Oct), whose render folder holds the delivery render (final.mp4), its qa.json, and the animatic
(python -m frameflow.animatic); skipped where that folder isn't present.
"""
import json
import subprocess
from pathlib import Path

import numpy as np
import pytest

from frameflow import media, precheck, qa

KIMI = Path(__file__).resolve().parent.parent / "out" / "2026-10-26-china-s-moonshot-ai-launches-kimi" / "render"
need_animatic = pytest.mark.skipif(not (KIMI / "animatic.mp4").exists() or not (KIMI / "final.mp4").exists(), reason="Kimi animatic not here")
need_voice = pytest.mark.skipif(not (KIMI / "voice" / "words.json").exists() or not (KIMI / "qa.json").exists(), reason="Kimi render not here")


def _px(args):
    raw = subprocess.run([media.FFMPEG, "-loglevel", "error", *args, "-vf", "scale=270:480", "-frames:v", "1", "-f", "rawvideo",
                          "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(480, 270, 3).astype(np.int16)


@need_animatic
def test_animatic_stills_are_the_delivery_frames():
    diffs = []
    for t in [0.8 + 3 * i for i in range(38)]:
        still, real = _px(["-ss", f"{t}", "-i", str(KIMI / "animatic.mp4")]), _px(["-ss", f"{t}", "-i", str(KIMI / "final.mp4")])
        assert still.mean() > 150, f"draft frame at {t}s is dark"
        diffs.append(np.abs(still - real).mean())
    assert np.median(diffs) < 4 and sum(d < 10 for d in diffs) >= 0.9 * len(diffs)


@need_animatic
def test_animatic_measures_events_like_qa_on_the_delivery_render():
    a = json.loads((KIMI / "animatic.json").read_text())
    ev, total = qa.visual_events(KIMI / "final.mp4")
    real_gap = max(b - x for x, b in zip([0.0] + ev, ev + [total]))
    assert abs(a["longest_gap"] - real_gap) <= 0.3 and abs(a["per_10s"] - len(ev) / total * 10) <= 1.0
    q = json.loads((KIMI / "qa.json").read_text())["gates"]["events"]["pass"]
    assert a["pass"] == q


@need_voice
def test_narrator_checks_give_qa_verdicts_before_any_picture():
    r = precheck.run(KIMI)
    q = json.loads((KIMI / "qa.json").read_text())["gates"]
    for k in ("rehooks", "captions", "voice-start"):
        assert r["checks"][k]["pass"] == q[k]["pass"], k
    assert "11.9" in r["checks"]["rehooks"]["detail"] and "11.9" in q["rehooks"]["detail"]
    assert r["checks"]["events"].get("advisory") and "events" not in [f["fix"].split("'")[1] for f in precheck.fixes(r)]


def test_cue_time_finds_the_spoken_phrase():
    words = [{"w": w, "s": i * 0.5} for i, w in enumerate("A Chinese AI now costs exactly half".split())]
    assert precheck.cue_time("exactly half", words, 0, 10) == 2.5
    assert precheck.cue_time("Chinese AI", words, 1.0, 10) is None and precheck.cue_time("nothing here", words, 0, 10) is None
