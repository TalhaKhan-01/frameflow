"""Voice cues for the HQ's chat bubbles (P17.2.4): one short signature sound per cast member, synthesised here from
sine waves and noise, so every file is our own (no third-party sounds, no licence to track).

    uv run python scripts/make_cues.py      # writes web/public/cues/<cue>.ogg (mono, 24 kHz, Opus) and cues.json

The cue names are the `cue` field of web/src/office/cast.ts.
"""
import json
import re
import subprocess
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "web" / "public" / "cues"
SR = 24000
rng = np.random.default_rng(7)


def t(sec):
    return np.arange(int(SR * sec)) / SR


def env(n, attack=0.005, decay=8.0):
    x = np.arange(n) / SR
    return np.minimum(1, x / attack) * np.exp(-decay * x)


def tone(f, sec, decay=8.0, attack=0.005):
    x = t(sec)
    return np.sin(2 * np.pi * f * x) * env(len(x), attack, decay)


def noise(sec, decay=20.0):
    n = int(SR * sec)
    return rng.uniform(-1, 1, n) * env(n, 0.001, decay)


def bandpass(x, lo, hi):
    spec = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    spec[(f < lo) | (f > hi)] = 0
    return np.fft.irfft(spec, len(x))


def mix(*xs):
    n = max(len(x) for x in xs)
    return sum(np.pad(x, (0, n - len(x))) for x in xs)


def cat(*parts, gap=0.0):
    out = []
    for p in parts:
        out += [p, np.zeros(int(SR * gap))]
    return np.concatenate(out)


def sweep(f0, f1, sec, decay=4.0):
    x = t(sec)
    f = np.linspace(f0, f1, len(x))
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * env(len(x), 0.01, decay)


CUES = {
    "chime": lambda: cat(tone(880, 0.35, 6), tone(1320, 0.5, 5), gap=0.02),
    "phone": lambda: cat(*[(tone(440, 0.05, 0) + tone(480, 0.05, 0)) * 0.6] * 6, gap=0.03),
    "stopwatch": lambda: cat(bandpass(noise(0.03, 120), 2000, 6000), bandpass(noise(0.03, 120), 2500, 7000), gap=0.12),
    "tab-pop": lambda: sweep(300, 1200, 0.08, 30),
    "stamp": lambda: mix(tone(70, 0.25, 18) * 1.2, bandpass(noise(0.08, 40), 100, 800)),
    "double-click": lambda: cat(bandpass(noise(0.015, 200), 3000, 8000), bandpass(noise(0.015, 200), 3000, 8000), gap=0.09),
    "typewriter": lambda: cat(*[bandpass(noise(0.02, 150), 1500, 5000)] * 4, tone(2093, 0.4, 7), gap=0.06),
    "snip": lambda: cat(bandpass(noise(0.04, 60), 4000, 10000), bandpass(noise(0.05, 50), 3000, 9000), gap=0.05),
    "clapper": lambda: bandpass(noise(0.12, 35), 400, 4000) * 1.3,
    "pen-click": lambda: cat(bandpass(noise(0.01, 300), 2500, 9000), bandpass(noise(0.01, 300), 1800, 7000), gap=0.07),
    "scratch": lambda: bandpass(noise(0.3, 6), 300, 3000) * np.sin(2 * np.pi * 9 * t(0.3)) ** 2,
    "flipbook": lambda: cat(*[bandpass(noise(0.012, 250), 1500, 6000) * 0.8] * 8, gap=0.025),
    "brush": lambda: bandpass(noise(0.35, 7), 2000, 8000) * np.sin(np.pi * t(0.35) / 0.35),
    "whistle": lambda: cat(sweep(1800, 2600, 0.18, 2), sweep(2600, 1500, 0.3, 4), gap=0.02),
    "fan-whir": lambda: (bandpass(rng.uniform(-1, 1, len(t(0.6))), 80, 600) * np.linspace(0.2, 1, len(t(0.6)))
                         * (0.6 + 0.4 * np.sin(2 * np.pi * 30 * t(0.6)))),
    "loupe-ping": lambda: tone(2637, 0.4, 9),
    "bicycle-bell": lambda: cat(tone(2350, 0.25, 9) + tone(3100, 0.25, 12) * 0.4, tone(2350, 0.4, 7) + tone(3100, 0.4, 10) * 0.4, gap=0.04),
    "chalk": lambda: cat(bandpass(noise(0.05, 50), 1000, 5000), bandpass(noise(0.04, 60), 1200, 5000), gap=0.08),
    "sack": lambda: bandpass(noise(0.35, 6), 500, 4000) * 0.7,
    "bat-tock": lambda: mix(tone(950, 0.12, 40), bandpass(noise(0.03, 120), 800, 3000)),
    "kettle": lambda: sweep(1600, 2300, 0.7, 1.5) * 0.7 + bandpass(noise(0.7, 2), 3000, 7000) * 0.15,
    "meow": lambda: cat(sweep(500, 900, 0.15, 1), sweep(900, 450, 0.3, 3)),
}


def cast_cues():
    ts = (ROOT / "web" / "src" / "office" / "cast.ts").read_text()
    return dict(re.findall(r'id: "([a-z]+)",[^}]*?cue: "([a-z-]+)"', ts))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    need = cast_cues()
    missing = sorted(set(need.values()) - set(CUES))
    if missing:
        raise SystemExit(f"no synth for cue(s): {missing}")
    sizes = {}
    for name in sorted(set(need.values())):
        x = CUES[name]()
        x = x / (np.max(np.abs(x)) or 1) * 0.6
        fade = min(len(x), int(SR * 0.01))
        x[-fade:] *= np.linspace(1, 0, fade)
        with tempfile.NamedTemporaryFile(suffix=".wav") as tmp:
            sf.write(tmp.name, x.astype(np.float32), SR)
            out = OUT / f"{name}.ogg"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", tmp.name, "-c:a", "libopus", "-b:a", "32k", str(out)], check=True)
        sizes[name] = out.stat().st_size
    (OUT / "cues.json").write_text(json.dumps({"by_person": need, "licence": "own synthesis (scripts/make_cues.py), no third-party audio",
                                               "bytes": sizes}, indent=1))
    print(f"{len(sizes)} cues, largest {max(sizes.values())} bytes -> {OUT}")


if __name__ == "__main__":
    main()
