#!/usr/bin/env python3
"""Acceptance test for fast transitions (phasedoc P9.5.4): a 4-scene plan joined by whip-left, velocity and glitch,
built twice and compared frame by frame inside every transition window (the exit tail, the cut, the entry).

Usage: uv run python tests/transition_acceptance.py
Writes out/samples/transitions/sheet.jpg: for each cut, frames at -0.15 s, -0.05 s, +0.05 s and +0.2 s.
"""
import json
import sys

from frameflow import build, media
from scene_acceptance import frame_hash

ENTERS = ["cut", "whip-left", "velocity", "glitch"]
SAMPLES = ["stamps", "cast", "flap", "quote"]


def main():
    scenes = []
    for kind, enter in zip(SAMPLES, ENTERS):
        s = json.loads((build.SCENES / kind / "sample.json").read_text())
        scenes.append({**s, "duration": 3.0, "enter": enter})
    plan = {"id": "sample-transitions", "lane": "global-tech", "title": "Sample: transitions", "scenes": scenes}
    out, total = build.project(plan, build.ROOT / "out" / "samples" / "transitions")
    a, b = build.render(out, out / "a.mp4"), build.render(out, out / "b.mp4")
    starts = [st for st, _ in build.timings(plan)][1:]
    offsets = (-0.15, -0.05, 0.05, 0.2)
    ok = True
    frames = []
    for name, st in zip(ENTERS[1:], starts):
        same = all(frame_hash(a, st + o) == frame_hash(b, st + o) for o in offsets)
        moved = len({frame_hash(a, st + o) for o in offsets}) == len(offsets)   # every sampled frame differs: it animates
        ok &= same and moved
        print(f"{'PASS' if same and moved else 'FAIL'}  {name} at {st:.2f}s: renders match {same}, frames all differ {moved}")
        for i, o in enumerate(offsets):
            f = out / f"{name}-{i}.jpg"
            media.ffmpeg("-ss", f"{st + o:.3f}", "-i", a, "-frames:v", "1", "-vf", "scale=200:-2", f)
            frames.append(f)
    rows = [out / f"row-{n}.jpg" for n in ENTERS[1:]]
    for n, row in zip(ENTERS[1:], rows):
        media.ffmpeg(*sum((["-i", out / f"{n}-{i}.jpg"] for i in range(len(offsets))), []), "-filter_complex", f"hstack=inputs={len(offsets)}", row)
    media.ffmpeg(*sum((["-i", r] for r in rows), []), "-filter_complex", f"vstack=inputs={len(rows)}", out / "sheet.jpg")
    dur = media.duration(a)
    ok &= abs(dur - total) < 0.1
    print(f"{'PASS' if ok else 'FAIL'}  transitions: {dur:.2f}s (planned {total:.2f}), sheet {out / 'sheet.jpg'}")
    return ok


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
