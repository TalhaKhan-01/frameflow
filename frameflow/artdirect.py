"""Art director desk (P15 Studio board): the picture checks on the animatic draft, before the delivery render.

    python -m frameflow.artdirect <render-dir>     reads animatic.mp4, writes artdirect.json; exit 0 when all pass

  empty      blank paper above the caption band for a second or more (qa.blank_spans, the same measurement as QA)
  black      black stretches over the bar (qa.black_stretches)
  brand      every still sits on the Paper Press background: a still whose page is dark or off-palette means a scene
             (or the theme) didn't render as designed
Overlapping or garbled text and text in the caption band need eyes: the screening's captions row judges them on the
same stills. Thresholds: research/quality-bar.json (picture).
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

from frameflow import bar, build, media, qa

PAPER = np.array(qa.PAPER, dtype=np.float32)


def page_colour(video, t):
    """Median colour of the page margins at time t (left and right strips above the caption band), 0-255 RGB."""
    w, h = 108, 192
    raw = subprocess.run([media.FFMPEG, "-loglevel", "error", "-ss", f"{t:.2f}", "-i", str(video), "-frames:v", "1", "-vf",
                          f"scale={w}:{h}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
    if len(raw) < w * h * 3:
        return None
    fr = np.frombuffer(raw, np.uint8).reshape(h, w, 3).astype(np.float32)
    margins = np.concatenate([fr[20:120, :6].reshape(-1, 3), fr[20:120, -6:].reshape(-1, 3)])
    return np.median(margins, axis=0)


def run(render_dir):
    out = Path(render_dir)
    video = out / "animatic.mp4"
    pic = bar.load()["picture"]
    plan = json.loads((out / "plan.json").read_text())
    slots = build.timings(plan, out / "voice")
    scene_at = lambda t: next((i for i, (st, d) in enumerate(slots) if st <= t < st + d), None)
    checks = {}

    def check(name, problems, row):
        checks[name] = {"pass": not problems, "problems": problems, "row": row}

    blanks = [s for s in qa.blank_spans(video, ink=pic["blank_ink"]) if s[1] - s[0] >= pic["blank_fail_seconds"]]
    check("empty", [f"scene {scene_at(a)}: nothing drawn above the captions from {a:.1f} s to {b:.1f} s" for a, b in blanks], "visual_storytelling")
    black = qa.black_stretches(video, pic["black_seconds"])
    check("black", [f"black picture {x}" for x in black[:5]], "visual_storytelling")
    off = []
    total = media.duration(video)
    for i, (st, d) in enumerate(slots):
        t = min(st + d * 0.6, total - 0.1)
        c = page_colour(video, t)
        if c is not None and float(np.abs(c - PAPER).mean()) > 40:
            off.append(f"scene {i} ({plan['scenes'][i]['type']}) at {t:.1f} s: the page is rgb{tuple(int(x) for x in c)}, not the Paper Press paper")
    check("brand", off, "visual_storytelling")
    r = {"pass": all(c["pass"] for c in checks.values()), "checks": checks}
    (out / "artdirect.json").write_text(json.dumps(r, ensure_ascii=False, indent=1))
    return r


def fixes(r):
    return [{"row": c["row"], "fix": f"art director '{k}': {p}. Change only that scene; keep every other scene exactly as it is."}
            for k, c in r["checks"].items() for p in c["problems"]]


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: python -m frameflow.artdirect <render-dir>")
    r = run(sys.argv[1])
    for k, c in r["checks"].items():
        print(f"{'PASS' if c['pass'] else 'FAIL'}  {k}" + "".join(f"\n      - {p}" for p in c["problems"]))
    sys.exit(0 if r["pass"] else 1)


if __name__ == "__main__":
    main()
