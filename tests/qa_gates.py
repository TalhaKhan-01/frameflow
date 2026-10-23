#!/usr/bin/env python3
"""Acceptance test for frameflow qa (phasedoc P6.3): break each rule in turn on copies of a clean render,
and check that exactly that gate fails, and that the clean render passes.

Usage: uv run python tests/qa_gates.py out/<clean-render>
"""
import json
import shutil
import sys
import tempfile
from pathlib import Path

from frameflow import media, qa

clean = Path(sys.argv[1])


def variant(name, tmp, break_it):
    d = Path(tmp) / name
    shutil.copytree(clean, d, ignore=shutil.ignore_patterns("project", "raw.mp4", "*.wav"))
    (d / "voice").mkdir(exist_ok=True)
    shutil.copy(clean / "voice" / "words.json", d / "voice" / "words.json")
    break_it(d)
    return d


def reencode(d, *args):
    src = d / "final.mp4"
    tmp = d / "broken.mp4"
    media.ffmpeg("-i", src, *args, tmp)
    tmp.replace(src)


breakers = {
    "clean": (None, lambda d: None),
    "length": ("length", lambda d: reencode(d, "-vf", "tpad=stop_mode=clone:stop_duration=50", "-af", "apad=pad_dur=50")),
    "size": ("size", lambda d: reencode(d, "-vf", "scale=720:1280", "-c:a", "copy")),
    "loudness": ("loudness", lambda d: reencode(d, "-c:v", "copy", "-af", "volume=6dB")),
    "black": ("black", lambda d: reencode(d, "-vf", "drawbox=enable='between(t,5,6.5)':x=0:y=0:w=iw:h=ih:color=black:t=fill", "-c:a", "copy")),
    "captions": ("captions", lambda d: (d / "voice" / "words.json").write_text(json.dumps(
        [dict(w, w="banana") if i % 3 == 0 else w for i, w in enumerate(json.loads((d / "voice" / "words.json").read_text()))]))),
    "licences": ("licences", lambda d: (d / "assets.json").write_text(json.dumps(
        [dict(r, licence="") if r["asset"] == "music" else r for r in json.loads((d / "assets.json").read_text())]))),
}

ok = True
with tempfile.TemporaryDirectory() as tmp:
    for name, (expect, fn) in breakers.items():
        r = qa.run(variant(name, tmp, fn))
        failed = sorted(g for g, v in r["gates"].items() if not v["pass"])
        good = failed == ([expect] if expect else [])
        ok &= good
        print(f"{'PASS' if good else 'FAIL'}  {name:9} -> failed gates: {failed or 'none'}")
sys.exit(0 if ok else 1)
