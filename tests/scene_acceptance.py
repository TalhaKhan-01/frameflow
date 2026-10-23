#!/usr/bin/env python3
"""Acceptance test for scene templates (phasedoc P3.4.x): build each template's sample.json, run HyperFrames
check, render twice, and verify 1080x1920, the planned length, and identical frames at t=1 s.

Usage: uv run python tests/scene_acceptance.py <type> [<type> ...]
Writes a 4-frame contact sheet per template to out/samples/<type>/sheet.jpg for a visual check.
"""
import hashlib
import subprocess
import sys

from frameflow import build, media


def frame_hash(video, t=1.0):
    raw = subprocess.run([media.FFMPEG, "-hide_banner", "-loglevel", "error", "-ss", str(t), "-i", str(video),
                          "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
    return hashlib.sha256(raw).hexdigest()[:16]


def run(scene_type):
    out, total = build.scene_sample(scene_type)
    code, log = build.check(out)
    a = build.render(out, out / "a.mp4")
    b = build.render(out, out / "b.mp4")
    v = [s for s in media.probe(a)["streams"] if s["codec_type"] == "video"][0]
    dur = media.duration(a)
    times = [0.2, 0.5, 1.0, total * 0.4, total * 0.7, total - 0.1]
    ha, hb = frame_hash(a), frame_hash(b)
    stable = all(frame_hash(a, x) == frame_hash(b, x) for x in times)
    frames = [out / f"f{i}.jpg" for i in range(4)]
    for f, t in zip(frames, (0.4, 1.0, total / 2, total * 0.9)):
        media.ffmpeg("-ss", f"{t:.2f}", "-i", a, "-frames:v", "1", "-vf", "scale=270:-2", f)
    media.ffmpeg(*sum((["-i", f] for f in frames), []), "-filter_complex", "hstack=inputs=4", out / "sheet.jpg")
    ok = code == 0 and (v["width"], v["height"]) == (1080, 1920) and abs(dur - total) < 0.1 and ha == hb and stable
    print(f"{'PASS' if ok else 'FAIL'}  {scene_type}: check exit {code}, {v['width']}x{v['height']}, "
          f"{dur:.2f}s (planned {total:.2f}), frame@1s {ha} / {hb}, 6-time match {stable}, sheet {out / 'sheet.jpg'}")
    if code:
        print("\n".join(l for l in log.splitlines() if "✗" in l or "error" in l.lower())[:1500])
    return ok


if __name__ == "__main__":
    results = [run(t) for t in sys.argv[1:]]
    sys.exit(0 if all(results) else 1)
