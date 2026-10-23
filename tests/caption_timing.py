#!/usr/bin/env python3
"""Caption timing test (phasedoc P3.4.8): the amber highlight moves to a word within one frame of its spoken start.

Usage: uv run python tests/caption_timing.py <video.mp4> <words.json> [n=5]
For n words that are not first in their caption chunk, the amber pixels' centre in the caption band must shift
right between (start - 1 frame) and (start + 1 frame).
"""
import json
import subprocess
import sys

from frameflow import captions, media

FRAME = 1 / 30
Y0, Y1, W = 1280, 1540, 1080


def amber_centre(video, t):
    raw = subprocess.run([media.FFMPEG, "-hide_banner", "-loglevel", "error", "-ss", f"{t:.3f}", "-i", video, "-frames:v", "1",
                          "-vf", f"crop={W}:{Y1 - Y0}:0:{Y0}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
    xs = [(i // 3) % W for i in range(0, len(raw), 3)
          if raw[i] > 200 and 150 < raw[i + 1] < 215 and raw[i + 2] < 150]
    return sum(xs) / len(xs) if len(xs) > 200 else None


video, words_path = sys.argv[1], sys.argv[2]
n = int(sys.argv[3]) if len(sys.argv) > 3 else 5
words = json.loads(open(words_path).read())
picks = [g[i] for g in captions.chunks(words) for i in range(1, len(g))]
step = max(len(picks) // n, 1)
ok = 0
for w in picks[::step][:n]:
    # Sample safely inside the neighbouring frames: ffmpeg picks the first frame at or after the requested time,
    # so "one frame before" is s - 1.5 frames and "within one frame after" is s + 0.5 frame.
    before, after = amber_centre(video, w["s"] - 1.5 * FRAME), amber_centre(video, w["s"] + 0.5 * FRAME)
    good = before is not None and after is not None and after > before + 20
    ok += good
    print(f"{'PASS' if good else 'FAIL'}  '{w['w']}' at {w['s']:.2f}s: amber centre {before} -> {after}")
print(f"{ok}/{min(n, len(picks))} words switch within one frame")
sys.exit(0 if ok == min(n, len(picks)) else 1)
