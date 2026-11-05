"""The show's newer pictures on one short composition, rendered twice for the frame-hash determinism test (P9.5.1 maps
and routes, P9.5.5 parallax): Ep 6's open and sting, then two topics with a map graphic (a Taiwan -> USA route with
the vehicle riding it; India alone), the camera cutting wide -> split -> pip so the back set's parallax shows.

    uv run python spikes/graphics_sheet.py [out/show/graphics]

Silent (no voice, so no captions). Writes graphics.mp4, again.mp4, graphics-sheet.png and result.json.
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

from frameflow import build, media, music, show

FPS = 30


def frame_hash(v, t):
    raw = subprocess.run([media.FFMPEG, "-hide_banner", "-loglevel", "error", "-ss", f"{t:.2f}", "-i", str(v), "-frames:v", "1",
                          "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
    return hashlib.sha256(raw).hexdigest()[:16]


def main():
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else show.OUT / "graphics"
    out.mkdir(parents=True, exist_ok=True)
    c = json.loads((show.OUT / "2026-11-04-daily-habit-ep6" / "show-plan.json").read_text())
    segs = [s for s in c["segments"] if not s.get("topic")][:2]   # the open and the sting
    t = segs[-1]["start"] + segs[-1]["dur"]
    maps = [({"type": "map", "title": "Chips shipped", "countries": ["TWN", "USA"], "route": True, "caption": "Taiwan to the US"}, "TWN"),
            ({"type": "map", "title": "Where it happened", "countries": ["IND"], "caption": "India"}, "IND")]
    for k, (g, wall) in enumerate(maps, 1):
        segs.append({"topic": k, "lane": "World", "headline": g["title"], "source": "Natural Earth", "shot": "wide", "emotion": "neutral",
                     "wall": wall, "wallSub": "MAP", "start": round(t, 3), "dur": 6.0, "id": f"t{k}",
                     "shots": [[0.0, "wide"], [2.0, "split"], [4.0, "pip"]], "g": show.map_geo(g)})
        t += 6.0
    dur = round(t + 0.5, 3)
    c.update(segments=segs, topics=2, dur=dur, endAt=dur + 5, endDur=0.0, tickerAt=dur + 5, env=[0.0] * int(dur * FPS + 2),
             envFps=FPS, words=[])
    silent = out / "silence.wav"
    music.write_wav(silent, np.zeros((int(dur * show.SR), 2), np.float32))
    pd = show.project(c, silent, out)
    code, log = build.check(pd)
    errs = [l for l in log.splitlines() if "✗ error" in l]
    final = build.render(pd, out / "graphics.mp4", quality="looks")
    again = build.render(pd, out / "again.mp4", quality="looks")
    s1, s2 = segs[2]["start"], segs[3]["start"]
    probe = [s1 + 0.5, s1 + 1.5, s1 + 2.6, s1 + 3.4, s1 + 5.0, s2 + 3.0]   # route drawing, vehicle mid-way, the cuts
    same = [round(p, 2) for p in probe if frame_hash(final, p) == frame_hash(again, p)]
    sheet = show.stills(final, [s1 + 0.6, s1 + 1.6, s1 + 2.6, s1 + 4.5, s2 + 1.0, s2 + 3.0], out, "graphics-sheet")
    res = {"check_errors": len(errs), "errors": errs[:3], "frames_compared": len(probe), "identical": len(same),
           "deterministic": len(same) == len(probe), "sheet": str(sheet), "video": str(final)}
    (out / "result.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
