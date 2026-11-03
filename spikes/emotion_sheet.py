"""Habit's eight faces from the show template itself (P24.4.2): each emotion for 1.2 s in the split shot, mouth closed for
the first half and talking for the second, rendered once and cut into a contact sheet.

    uv run python spikes/emotion_sheet.py [out/show/emotions]

Uses the latest made episode's show-plan only for the set and look; nothing else from it.
"""
import json
import sys
from pathlib import Path

import numpy as np

from frameflow import build, music, show

EMOTIONS = ["neutral", "excited", "surprised", "doubtful", "smug", "worried", "laughing", "serious"]
STEP, FPS = 1.2, 30


def main():
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else show.OUT / "emotions"
    out.mkdir(parents=True, exist_ok=True)
    segs, env = [], []
    for i, e in enumerate(EMOTIONS):
        segs.append({"start": round(i * STEP, 3), "dur": STEP, "shot": "split", "shots": [[0, "split"]], "emotion": e,
                     "wall": e.upper(), "wallSub": "HABIT'S FACES", "id": e})
        n = int(STEP * FPS)
        env += [0.0] * (n // 2) + [0.55 + 0.25 * np.sin(k * 1.9) for k in range(n - n // 2)]   # closed, then talking
    dur = round(len(EMOTIONS) * STEP, 3)
    c = {"set": show.cfg()["set"], "look": "puppet", "episode": 0, "topics": 0, "date": "", "breakingText": "",
         "ticker": [], "segments": segs, "dur": dur, "env": [round(float(v), 3) for v in env], "envFps": FPS, "words": []}
    silent = out / "silence.wav"
    music.write_wav(silent, np.zeros((int(dur * show.SR), 2), np.float32))
    pd = show.project(c, silent, out)
    final = build.render(pd, out / "emotions.mp4", quality="looks")
    times = [t for i in range(len(EMOTIONS)) for t in (i * STEP + 0.35, i * STEP + 0.95)]
    sheet = show.stills(final, times, out, "emotion-sheet")
    print(json.dumps({"sheet": str(sheet), "video": str(final), "order": [f"{e} ({m})" for e in EMOTIONS for m in ("closed", "talking")]}, indent=1))


if __name__ == "__main__":
    main()
