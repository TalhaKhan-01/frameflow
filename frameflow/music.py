"""Music and sound effects, generated locally (original works: no licence questions).

    python -m frameflow.music library [--out data/library]     write 10 music beds + 20 sound effects + ledger rows
    python -m frameflow.music bed <mood> <seconds> <out.wav>    one bed of any length

Beds are quiet instrumental loops made for sitting under a voice (soft pads, plucks, light drums), 48 kHz stereo.
Everything is deterministic: the same mood and length always give the same file.
"""
import argparse
import json
import wave
from pathlib import Path

import numpy as np

SR = 48000
ROOT = Path(__file__).resolve().parent.parent
LIBRARY = ROOT / "data" / "library"

NOTE = {n: i for i, n in enumerate("C C# D D# E F F# G G# A A# B".split())}


def hz(name, octave):
    return 440.0 * 2 ** ((NOTE[name] + 12 * (octave + 1) - 69) / 12)


def chord(root, quality, octave=3):
    steps = {"maj": (0, 4, 7, 11), "min": (0, 3, 7, 10), "sus": (0, 5, 7, 10), "add9": (0, 4, 7, 14)}[quality]
    base = NOTE[root] + 12 * (octave + 1)
    return [440.0 * 2 ** ((base + s - 69) / 12) for s in steps]


# mood: (bpm, progression, pad brightness 0-1, drums, pluck)
MOODS = {
    "calm-tech":  (90,  [("A", "min"), ("F", "maj"), ("C", "maj"), ("G", "sus")], 0.35, "soft", True),
    "curious":    (100, [("D", "min"), ("A#", "maj"), ("F", "maj"), ("C", "maj")], 0.45, "soft", True),
    "upbeat":     (118, [("C", "maj"), ("G", "maj"), ("A", "min"), ("F", "maj")], 0.6, "full", True),
    "tense":      (96,  [("E", "min"), ("C", "maj"), ("E", "min"), ("D#", "sus")], 0.3, "pulse", False),
    "news":       (110, [("F", "min"), ("C#", "maj"), ("G#", "maj"), ("D#", "maj")], 0.5, "full", False),
    "warm":       (84,  [("D", "maj"), ("B", "min"), ("G", "add9"), ("A", "sus")], 0.4, "soft", True),
    "deep":       (76,  [("C", "min"), ("G#", "maj"), ("D#", "maj"), ("A#", "maj")], 0.25, "pulse", False),
    "bright":     (124, [("G", "maj"), ("D", "maj"), ("E", "min"), ("C", "add9")], 0.7, "full", True),
    "minimal":    (92,  [("A", "min"), ("A", "sus"), ("F", "maj"), ("F", "add9")], 0.3, "none", True),
    "driving":    (128, [("B", "min"), ("G", "maj"), ("D", "maj"), ("A", "maj")], 0.55, "full", False),
}


def env(n, a, r):
    """Attack/release envelope over n samples (a, r in samples)."""
    e = np.ones(n)
    a, r = max(1, min(a, n)), max(1, min(r, n))
    e[:a] = np.linspace(0, 1, a)
    e[-r:] *= np.linspace(1, 0, r)
    return e


def lowpass(x, cutoff):
    """One-pole low-pass, applied along the time axis."""
    a = np.exp(-2 * np.pi * cutoff / SR)
    y = np.empty_like(x)
    acc = 0.0
    for i in range(len(x)):  # small loops are fine: beds are rendered once into the library
        acc = (1 - a) * x[i] + a * acc
        y[i] = acc
    return y


def reverb(x, mix=0.3):
    """Cheap stereo reverb: decaying echoes on a few delay lines per side."""
    out = np.zeros((len(x), 2))
    for side, delays in enumerate(((1557, 1617, 1491, 1422), (1277, 1356, 1188, 1116))):
        acc = np.zeros(len(x))
        for d in delays:
            buf = np.zeros(len(x))  # three decaying echoes per delay line
            buf[d:] = x[:-d] * 0.6
            buf[2 * d:] += x[:-2 * d] * 0.36
            buf[3 * d:] += x[:-3 * d] * 0.22
            acc += buf
        out[:, side] = x * (1 - mix) + acc / len(delays) * mix * 2
    return out


def pad(freqs, n, brightness, rng):
    t = np.arange(n) / SR
    sig = np.zeros(n)
    for f in freqs:
        for det in (-0.12, 0.0, 0.11):  # slight detune = chorus
            ph = rng.uniform(0, 2 * np.pi)
            sig += np.sin(2 * np.pi * f * (1 + det / 100) * t + ph)
            sig += brightness * 0.35 * np.sin(2 * np.pi * 2 * f * t + ph)
    return sig / (len(freqs) * 3) * env(n, int(0.6 * SR), int(0.8 * SR))


def pluck(f, n):
    t = np.arange(n) / SR
    return (np.sin(2 * np.pi * f * t) + 0.3 * np.sin(4 * np.pi * f * t)) * np.exp(-t * 6)


def kick(n):
    t = np.arange(n) / SR
    return np.sin(2 * np.pi * (50 + 90 * np.exp(-t * 30)) * t) * np.exp(-t * 9)


def hat(n, rng):
    t = np.arange(n) / SR
    return rng.standard_normal(n) * np.exp(-t * 60) * 0.25


def mix_in(dst, start, x):
    """Add x into dst at start, clipped to dst's length."""
    end = min(start + len(x), len(dst))
    if end > start:
        dst[start:end] += x[: end - start]


def bed(mood, seconds, seed=7):
    bpm, prog, bright, drums, plucks = MOODS[mood]
    rng = np.random.default_rng(seed)
    n = int(seconds * SR)
    beat = 60 / bpm
    bar = int(4 * beat * SR)
    mono = np.zeros(n + bar)
    for b, start in enumerate(range(0, n, bar)):
        root, q = prog[b % len(prog)]
        freqs = chord(root, q)
        mix_in(mono, start, pad(freqs, bar, bright, rng) * 0.55)
        if plucks:
            for k in range(8):
                f = freqs[(k * 3 + b) % len(freqs)] * 2
                s = start + int(k * beat / 2 * SR)
                mix_in(mono, s, pluck(f, int(0.5 * SR)) * 0.12)
        if drums != "none":
            for k in range(4):
                s = start + int(k * beat * SR)
                if drums in ("full", "pulse") or k % 2 == 0:
                    mix_in(mono, s, kick(int(0.4 * SR)) * (0.35 if drums == "full" else 0.22))
                if drums == "full":
                    h = s + int(beat / 2 * SR)
                    mix_in(mono, h, hat(int(0.1 * SR), rng))
    mono = lowpass(mono[:n], 2500 + 5000 * bright)
    st = reverb(mono, 0.35)
    fade = env(n, int(1.0 * SR), int(1.5 * SR))
    st *= fade[:, None]
    return st / (np.max(np.abs(st)) + 1e-9) * 0.7


SFX = {
    "whoosh-up": ("sweep", 0.6, 400, 6000), "whoosh-down": ("sweep", 0.6, 6000, 400),
    "whoosh-short": ("sweep", 0.3, 800, 5000), "whoosh-long": ("sweep", 1.2, 300, 7000),
    "riser-1": ("riser", 2.0, 200, 2000), "riser-2": ("riser", 3.0, 150, 3000),
    "impact-low": ("impact", 1.2, 45, 0), "impact-soft": ("impact", 0.8, 70, 0),
    "pop-1": ("pop", 0.15, 900, 0), "pop-2": ("pop", 0.15, 1300, 0), "pop-3": ("pop", 0.12, 600, 0),
    "tick-1": ("tick", 0.05, 3000, 0), "tick-2": ("tick", 0.05, 4500, 0),
    "ding-1": ("ding", 1.2, 880, 0), "ding-2": ("ding", 1.2, 1320, 0), "ding-low": ("ding", 1.5, 523, 0),
    "click-1": ("tick", 0.03, 1800, 0), "glitch-1": ("glitch", 0.4, 0, 0), "glitch-2": ("glitch", 0.25, 0, 0),
    "count-tick": ("tick", 0.04, 2400, 0),
}


def sfx(kind, seconds, a, b, seed=3):
    rng = np.random.default_rng(seed)
    n = int(seconds * SR)
    t = np.arange(n) / SR
    if kind in ("sweep", "riser"):
        noise = rng.standard_normal(n)
        cut = np.geomspace(a, b, n)
        y = np.zeros(n)
        acc = 0.0
        for i in range(n):
            al = np.exp(-2 * np.pi * cut[i] / SR)
            acc = (1 - al) * noise[i] + al * acc
            y[i] = acc
        shape = np.sin(np.pi * np.linspace(0, 1, n)) if kind == "sweep" else np.linspace(0, 1, n) ** 2
        if kind == "riser":
            y += 0.3 * np.sin(2 * np.pi * np.geomspace(a, b, n) * t)
        y *= shape
    elif kind == "impact":
        y = np.sin(2 * np.pi * (a + 60 * np.exp(-t * 20)) * t) * np.exp(-t * 4) + rng.standard_normal(n) * np.exp(-t * 30) * 0.3
    elif kind == "pop":
        y = np.sin(2 * np.pi * a * (1 + 0.5 * np.exp(-t * 60)) * t) * np.exp(-t * 40)
    elif kind == "tick":
        y = np.sin(2 * np.pi * a * t) * np.exp(-t * 200)
    elif kind == "ding":
        y = sum(np.sin(2 * np.pi * a * h * t) * np.exp(-t * (3 + h)) / h for h in (1, 2.76, 5.4))
    else:  # glitch
        y = np.sign(np.sin(2 * np.pi * rng.uniform(80, 400) * t)) * (rng.uniform(0, 1, n) > 0.4) * np.exp(-t * 6)
    y = y / (np.max(np.abs(y)) + 1e-9) * 0.8
    return np.stack([y, y], axis=1)


def write_wav(path, stereo):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pcm = (np.clip(stereo, -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    return path


def library(out=LIBRARY):
    out = Path(out)
    rows = []
    for mood in MOODS:
        f = write_wav(out / "music" / f"bed-{mood}.wav", bed(mood, 60))
        rows.append({"file": str(f.relative_to(out)), "kind": "music", "mood": mood, "seconds": 60})
    for name, (kind, secs, a, b) in SFX.items():
        f = write_wav(out / "sfx" / f"{name}.wav", sfx(kind, secs, a, b))
        rows.append({"file": str(f.relative_to(out)), "kind": "sfx", "name": name, "seconds": secs})
    for r in rows:
        r.update({"source": "generated by frameflow.music (procedural synthesis)", "licence": "original work by Talha Khan; free for any use",
                  "url": "local", "author": "Frameflow"})
    (out / "ledger.json").write_text(json.dumps(rows, indent=1))
    return rows


def main():
    ap = argparse.ArgumentParser(description="Frameflow music and sound effects (generated).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    l = sub.add_parser("library")
    l.add_argument("--out", default=str(LIBRARY))
    b = sub.add_parser("bed")
    b.add_argument("mood", choices=list(MOODS))
    b.add_argument("seconds", type=float)
    b.add_argument("out")
    a = ap.parse_args()
    if a.cmd == "library":
        rows = library(a.out)
        print(f"{sum(r['kind'] == 'music' for r in rows)} beds, {sum(r['kind'] == 'sfx' for r in rows)} sound effects -> {a.out}")
    else:
        print(write_wav(a.out, bed(a.mood, a.seconds)))


if __name__ == "__main__":
    main()
