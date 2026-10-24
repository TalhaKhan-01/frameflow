"""Sound design (Quality v2): a named sound-effect library, a scene-aware music score and the cue-sheet mix.

    python -m frameflow.sound library            fetch Kenney's CC0 packs + Incompetech tracks, build data/library/sfx2 and the ledger
    python -m frameflow.sound list               the effect names the director can use

Effect names are a fixed vocabulary (SFX below): the director writes {"at": cue, "name": "slam"} and never a file name.
Kenney (CC0) gives recorded impacts, clicks, glitches and footsteps; whooshes, risers, the record scratch and sub drops
are synthesised here (original work). Music: Kevin MacLeod tracks (incompetech.com, CC BY 4.0, credited in the video
description) cut, faded and gain-automated by the plan's music cues and each scene's energy.
"""
import argparse
import json
import subprocess
import urllib.request
import zipfile
from pathlib import Path

import numpy as np

from frameflow import media, music

ROOT = Path(__file__).resolve().parent.parent
LIB = ROOT / "data" / "library"
KENNEY = LIB / "kenney"
SFX_DIR = LIB / "sfx2"
MUSIC_DIR = LIB / "music-cc"
SR = 48000

KENNEY_PACKS = {
    "impact-sounds": "https://kenney.nl/media/pages/assets/impact-sounds/87b4ddecda-1677589768/kenney_impact-sounds.zip",
    "interface-sounds": "https://kenney.nl/media/pages/assets/interface-sounds/fa43c1dd4d-1677589452/kenney_interface-sounds.zip",
    "sci-fi-sounds": "https://kenney.nl/media/pages/assets/sci-fi-sounds/6b296f9ecf-1677589334/kenney_sci-fi-sounds.zip",
    "digital-audio": "https://kenney.nl/media/pages/assets/digital-audio/216eac4753-1677590265/kenney_digital-audio.zip",
}

TRACKS = {   # name: (file, mood, bpm measured)
    "sneaky-snitch": ("Sneaky-Snitch.mp3", "quirky, sneaky, comic", 171),
    "investigations": ("Investigations.mp3", "curious, quirky", 185),
    "hitman": ("Hitman.mp3", "driving, tense", 150),
    "volatile-reaction": ("Volatile-Reaction.mp3", "intense, urgent", 160),
    "movement-proposition": ("Movement-Proposition.mp3", "thriller, pulsing", 126),
    "crypto": ("Crypto.mp3", "dark electronic, calm", 80),
    "spy-glass": ("Spy-Glass.mp3", "spy, suspense", 77),
    "unanswered-questions": ("Unanswered-Questions.mp3", "mysterious, steady", 120),
    "darkest-child": ("Darkest-Child.mp3", "dark, brooding", 86),
}

# name -> list of (offset seconds, source, gain dB). Source: "k:<pack>/<file stem>" (Kenney) or "p:<procedural name>".
SFX = {
    "whoosh": [(0, "p:whoosh", 0)],
    "whoosh-big": [(0, "p:whoosh-big", 0)],
    "riser": [(0, "p:riser", 0)],               # 1.6 s; place it to end on the reveal
    "riser-long": [(0, "p:riser-long", 0)],     # 3.2 s
    "impact": [(0, "k:impact-sounds/impactPunch_heavy_000", 0), (0, "p:sub-hit", -4)],
    "impact-big": [(0, "k:impact-sounds/impactPunch_heavy_002", 0), (0, "p:sub-drop", 0)],
    "sub-drop": [(0, "p:sub-drop", 0)],
    "slam": [(0, "k:impact-sounds/impactPunch_medium_000", 0)],
    "stamp": [(0, "k:impact-sounds/impactSoft_heavy_001", 0), (0.01, "k:impact-sounds/impactPunch_medium_002", -6)],
    "shutter": [(0, "k:impact-sounds/impactMetal_heavy_000", 0), (0.03, "k:impact-sounds/impactPlate_heavy_001", -5)],
    "lock": [(0, "k:impact-sounds/impactMetal_light_000", 0)],
    "rattle": [(0, "k:impact-sounds/impactMetal_light_001", 0), (0.08, "k:impact-sounds/impactMetal_light_002", -2),
               (0.16, "k:impact-sounds/impactMetal_light_003", -3), (0.24, "k:impact-sounds/impactMetal_light_004", -5)],
    "crack": [(0, "k:impact-sounds/impactWood_heavy_000", 0), (0.02, "k:sci-fi-sounds/explosionCrunch_000", -4)],
    "click": [(0, "k:interface-sounds/click_001", 0)],
    "switch": [(0, "k:interface-sounds/switch_002", 0)],
    "pop": [(0, "k:interface-sounds/toggle_001", 0)],
    "tick": [(0, "k:interface-sounds/tick_002", 0)],
    "type": [(0, "k:interface-sounds/click_003", -6)],
    "glitch": [(0, "k:interface-sounds/glitch_001", 0)],
    "error": [(0, "k:interface-sounds/error_004", 0)],
    "ding": [(0, "k:interface-sounds/confirmation_002", 0)],
    "alarm": [(0, "k:digital-audio/threeTone2", 0)],
    "beep": [(0, "k:digital-audio/pepSound1", 0)],
    "boom": [(0, "k:sci-fi-sounds/lowFrequency_explosion_000", 0)],
    "footsteps": [(i * 0.17, f"k:impact-sounds/footstep_concrete_00{i % 5}", -3) for i in range(6)],
    "scratch": [(0, "p:scratch", 0)],
}


def fetch(url, dest):
    req = urllib.request.Request(url, headers={"User-Agent": "frameflow/0.1"})
    with urllib.request.urlopen(req, timeout=120) as r:
        dest.write_bytes(r.read())
    return dest


def download():
    KENNEY.mkdir(parents=True, exist_ok=True)
    for name, url in KENNEY_PACKS.items():
        d = KENNEY / f"kenney_{name}"
        if d.exists():
            continue
        z = fetch(url, KENNEY / f"{name}.zip")
        with zipfile.ZipFile(z) as f:
            f.extractall(d)
        z.unlink()
    MUSIC_DIR.mkdir(parents=True, exist_ok=True)
    for file, *_ in TRACKS.values():
        dest = MUSIC_DIR / file
        if not dest.exists():
            fetch("https://incompetech.com/music/royalty-free/mp3-royaltyfree/" + file.removesuffix(".mp3").replace("-", "%20") + ".mp3", dest)


def load(path, seconds=None):
    """Any audio file -> float32 stereo array at 48 kHz."""
    args = [media.FFMPEG, "-loglevel", "error", "-i", str(path)]
    if seconds:
        args += ["-t", f"{seconds:.3f}"]
    raw = subprocess.run(args + ["-ac", "2", "-ar", str(SR), "-f", "f32le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).reshape(-1, 2).copy()


# ---- procedural effects (original work) ----
def _noise(n, seed):
    return np.random.default_rng(seed).standard_normal(n)


def _onepole(x, cut):
    """One-pole low-pass with a per-sample cutoff (array) or a fixed one."""
    cut = np.broadcast_to(np.asarray(cut, dtype=float), x.shape)
    a = np.exp(-2 * np.pi * cut / SR)
    y = np.empty_like(x)
    acc = 0.0
    for i in range(len(x)):
        acc = (1 - a[i]) * x[i] + a[i] * acc
        y[i] = acc
    return y


def procedural(name):
    if name in ("whoosh", "whoosh-big"):
        dur = 0.45 if name == "whoosh" else 0.9
        n = int(dur * SR)
        t = np.linspace(0, 1, n)
        cut = 300 + 7000 * np.sin(np.pi * t) ** 2
        y = _onepole(_noise(n, 11), cut) * np.sin(np.pi * t) ** 1.5
        hp = y - _onepole(y, 250)
        pan = np.linspace(-0.8, 0.8, n)   # moves left to right with the cut
        st = np.stack([hp * (1 - pan) / 2, hp * (1 + pan) / 2], 1)
    elif name in ("riser", "riser-long"):
        dur = 1.6 if name == "riser" else 3.2
        n = int(dur * SR)
        t = np.linspace(0, 1, n)
        tt = np.arange(n) / SR
        noise = _onepole(_noise(n, 5), 200 + 9000 * t ** 2.2)
        f = 110 * 2 ** (2.5 * t ** 1.7)                 # glide up two and a half octaves
        phase = 2 * np.pi * np.cumsum(f) / SR
        tone = (np.sin(phase) + 0.5 * np.sin(2 * phase + 0.3) + 0.25 * np.sin(3 * phase)) * (1 + 0.35 * np.sin(2 * np.pi * (4 + 18 * t) * tt))
        y = (0.55 * noise / (np.abs(noise).max() + 1e-9) + 0.45 * tone / 1.75) * t ** 2.4
        y[-int(0.012 * SR):] *= np.linspace(1, 0, int(0.012 * SR))   # hard stop: the impact takes over
        st = np.stack([y, np.roll(y, 240)], 1)
    elif name in ("sub-drop", "sub-hit"):
        dur = 1.4 if name == "sub-drop" else 0.5
        n = int(dur * SR)
        tt = np.arange(n) / SR
        f = 35 + (120 if name == "sub-drop" else 80) * np.exp(-tt * (3.5 if name == "sub-drop" else 14))
        y = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt * (2.2 if name == "sub-drop" else 7))
        st = np.stack([y, y], 1)
    elif name == "scratch":
        # vinyl scratch: band-limited noise + a tone whose pitch rubs forward and back twice
        n = int(0.55 * SR)
        tt = np.arange(n) / SR
        rub = np.abs(np.sin(2 * np.pi * 3.6 * tt))
        f = 180 + 1400 * rub
        tone = np.sign(np.sin(2 * np.pi * np.cumsum(f) / SR)) * 0.4
        noise = _onepole(_noise(n, 9), 500 + 5000 * rub)
        y = (tone + 0.8 * noise / (np.abs(noise).max() + 1e-9)) * (0.3 + 0.7 * rub) * np.exp(-tt * 1.5)
        st = np.stack([y, y], 1)
    else:
        raise KeyError(name)
    return (st / (np.abs(st).max() + 1e-9) * 0.85).astype(np.float32)


def source(src):
    kind, name = src.split(":", 1)
    if kind == "p":
        return procedural(name)
    pack, stem = name.split("/", 1)
    return load(KENNEY / f"kenney_{pack}" / "Audio" / f"{stem}.ogg")


def library():
    download()
    SFX_DIR.mkdir(parents=True, exist_ok=True)
    rows = []
    for name, parts in SFX.items():
        layers = [(off, source(src), g) for off, src, g in parts]
        n = max(int(off * SR) + len(a) for off, a, _ in layers)
        out = np.zeros((n, 2), np.float32)
        for off, a, g in layers:
            i = int(off * SR)
            out[i:i + len(a)] += a * 10 ** (g / 20)
        out = out / (np.abs(out).max() + 1e-9) * 0.89
        f = music.write_wav(SFX_DIR / f"{name}.wav", out)
        kenney = any(s.startswith("k:") for _, s, _ in parts)
        rows.append({"file": f"sfx2/{name}.wav", "kind": "sfx", "name": name, "seconds": round(n / SR, 3),
                     "source": "Kenney sound packs (kenney.nl)" + (" + frameflow synthesis" if any(s.startswith("p:") for _, s, _ in parts) else "") if kenney else "generated by frameflow.sound (procedural synthesis)",
                     "licence": "CC0 1.0 (Kenney); synthesised parts original work" if kenney else "original work by Talha Khan; free for any use",
                     "url": "https://kenney.nl/assets" if kenney else "local", "author": "Kenney" if kenney else "Frameflow"})
    for key, (file, mood, bpm) in TRACKS.items():
        title = file.removesuffix(".mp3").replace("-", " ")
        rows.append({"file": f"music-cc/{file}", "kind": "music", "name": key, "mood": mood, "bpm": bpm,
                     "source": f"{title}, Kevin MacLeod (incompetech.com)", "licence": "CC BY 4.0",
                     "url": "https://incompetech.com/music/royalty-free/", "author": "Kevin MacLeod",
                     "credit": f"{title} Kevin MacLeod (incompetech.com)\nLicensed under Creative Commons: By Attribution 4.0\nhttps://creativecommons.org/licenses/by/4.0/"})
    (LIB / "ledger-v2.json").write_text(json.dumps(rows, indent=1))
    return rows


def ledger():
    return {r["file"]: r for r in json.loads((LIB / "ledger-v2.json").read_text())}


# ---- music score ----
def energy_db(e):
    """Scene energy 0-1 -> music gain in dB before ducking (0 = silence)."""
    return None if e <= 0.02 else -18 + 12 * min(max(e, 0.0), 1.0)   # first pilot sat ~21 dB under the voice: too quiet


def score(plan, slots, total):
    """Music track for the video. plan["music"]["cues"]: [{"scene": i, "track": name or null, "offset": seconds into
    the track}] -> each cue starts its track at that scene (crossfade 0.25 s; null = silence). Gain follows each scene's
    "energy" (0-1, default 0.5); energy 0 cuts the music for that scene (a held breath before a twist)."""
    n = int((total + 0.5) * SR)
    out = np.zeros((n, 2), np.float32)
    cues = sorted((plan.get("music") or {}).get("cues") or [{"scene": 0, "track": "sneaky-snitch", "offset": 0}], key=lambda c: c["scene"])
    used = []
    starts = [s for s, _ in slots] + [total]
    for j, c in enumerate(cues):
        if not c.get("track"):
            continue
        a = starts[min(c["scene"], len(slots))]
        b = starts[min(cues[j + 1]["scene"], len(slots))] if j + 1 < len(cues) else total + 0.5
        file, *_ = TRACKS[c["track"]]
        seg = load(MUSIC_DIR / file)[int(c.get("offset", 0) * SR):]
        seg = seg[: max(int((b - a + 0.25) * SR), 0)]
        i0 = int(a * SR)
        fade = min(int(0.25 * SR), len(seg))
        if fade:
            seg[:fade] *= np.linspace(0, 1, fade)[:, None]
            seg[-fade:] *= np.linspace(1, 0, fade)[:, None]
        end = min(i0 + len(seg), n)
        out[i0:end] += seg[: end - i0]
        used.append(c["track"])
    # gain automation per scene, 0.12 s ramps
    gain = np.zeros(n, np.float32)
    for (st, d), scene in zip(slots, plan["scenes"]):
        g = energy_db(scene.get("energy", 0.5))
        gain[int(st * SR): int((st + d) * SR)] = 0 if g is None else 10 ** (g / 20)
    gain[int(starts[-2] * SR + slots[-1][1] * SR):] = gain[int(starts[-2] * SR + slots[-1][1] * SR) - 1] if len(slots) else 0
    k = int(0.12 * SR)
    smooth = np.convolve(gain, np.ones(k) / k, mode="same").astype(np.float32)
    return out * smooth[:, None], sorted(set(used))


def place_sfx(sheet, total):
    """The cue sheet ({t, name, gain}) as one stereo track."""
    n = int((total + 2) * SR)
    out = np.zeros((n, 2), np.float32)
    cache = {}
    for c in sheet:
        name = c["name"]
        if name not in cache:
            cache[name] = load(SFX_DIR / f"{name}.wav")
        a = cache[name] * 10 ** (c.get("gain", -12) / 20)
        i = int(max(c["t"], 0) * SR)
        end = min(i + len(a), n)
        out[i:end] += a[: end - i]
    return out[: int((total + 0.5) * SR)]


def main():
    ap = argparse.ArgumentParser(description="Frameflow sound design.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("library")
    sub.add_parser("list")
    a = ap.parse_args()
    if a.cmd == "library":
        rows = library()
        print(f"{sum(r['kind'] == 'sfx' for r in rows)} effects, {sum(r['kind'] == 'music' for r in rows)} tracks -> {LIB}")
    else:
        print("effects: " + ", ".join(SFX))
        print("tracks:  " + ", ".join(f"{k} ({v[1]})" for k, v in TRACKS.items()))


if __name__ == "__main__":
    main()
