"""Voice step: local text-to-speech, free. House voice: Chatterbox "lively" (MIT, GPU); Kokoro (Apache-2.0) is the fallback.

    python -m frameflow.voice sample "<text>" [--voice af_heart] [--speed 1.0] [--out f.wav]
    python -m frameflow.voice voices
    python -m frameflow.voice tts <script.json> <out-dir>

script.json: {"engine": "chatterbox" | "kokoro", "voice": "af_heart", "speed": 1.0, "tempo": 1.12, "seed": 7, "pad": 0.25,
              "lines": [{"id": "hook", "say": "...", "energy": 0.7, "pause_before": 0.4}, ...]}
Chatterbox: each line's energy (0-1) sets exaggeration (about 0.4-0.8; the house setting is energy 0.6);
`tempo` speeds the finished line up without changing pitch (ffmpeg atempo), to reach 175-190 words a minute.
pause_before adds silence before a line (a held beat before a reveal); otherwise lines are `pad` seconds apart.
tts writes NN-<id>.wav per line (48 kHz mono, about -15 LUFS), voice.wav and durations.json (seconds and start
per line, words per minute, loudness, engine). If Chatterbox can't run (no GPU memory, worker error), Kokoro
voices the script instead and durations.json says so.
Model files: Kokoro in ~/.cache/frameflow/kokoro/ (or FRAMEFLOW_KOKORO); Chatterbox in ~/.cache/frameflow/hf.
"""
import argparse
import json
import os
import subprocess
import tempfile
import wave
from pathlib import Path

from frameflow import media

MODEL_DIR = Path(os.environ.get("FRAMEFLOW_KOKORO", "~/.cache/frameflow/kokoro")).expanduser()
DEFAULT_VOICE = "af_heart"
WORKER = Path(__file__).resolve().parent / "chatterbox_worker.py"
CHATTERBOX = ["uv", "run", "--quiet", "--no-project", "--python", "3.12", "--with", "chatterbox-tts==0.1.7", "--with", "setuptools==80.9.0", "python", "-I", str(WORKER)]   # -I: frameflow/secrets.py must not shadow the stdlib
HOUSE = {"exaggeration": 0.65, "cfg_weight": 0.5}   # "lively", chosen in the vault's House Voice decision
_engine = None


def engine():
    global _engine
    if _engine is None:
        from kokoro_onnx import Kokoro
        model, voices = MODEL_DIR / "kokoro-v1.0.onnx", MODEL_DIR / "voices-v1.0.bin"
        if not (model.exists() and voices.exists()):
            raise SystemExit(f"Kokoro model files missing in {MODEL_DIR} (model-files-v1.0 release of thewh1teagle/kokoro-onnx)")
        _engine = Kokoro(str(model), str(voices))
    return _engine


def say(text, out, voice=DEFAULT_VOICE, speed=1.0, lang=None):
    """Synthesize one line to a cleaned 48 kHz mono WAV at `out`."""
    import soundfile as sf
    lang = lang or ("en-gb" if voice.startswith("b") else "en-us")
    samples, rate = engine().create(text, voice=voice, speed=float(speed), lang=lang)
    with tempfile.TemporaryDirectory() as tmp:
        raw = Path(tmp) / "raw.wav"
        sf.write(str(raw), samples, rate)
        media.clean_voice(raw, out)
    return Path(out)


def expression(energy):
    """Line energy 0-1 -> Chatterbox settings around the house 'lively' style (energy 0.6 = house setting)."""
    e = min(max(float(energy), 0.0), 1.0)
    # cfg weight stays at the house value: per Resemble, lowering it slows delivery, and pace comes from `tempo` instead
    return {"exaggeration": round(0.4 + 0.4 * e + (HOUSE["exaggeration"] - 0.64), 3), "cfg_weight": HOUSE["cfg_weight"]}


def chatterbox_lines(lines, out, seed=7, model="standard", ref=None, timeout=1800):
    """Raw Chatterbox WAVs for lines [(text, energy, path)] in one worker run (the model loads once)."""
    job = {"model": model, "ref": str(ref) if ref else None,
           "lines": [{"text": text, "out": str(path), "seed": seed + i, **expression(energy)} for i, (text, energy, path) in enumerate(lines)]}
    job_file = Path(out) / "chatterbox-job.json"
    job_file.write_text(json.dumps(job, ensure_ascii=False, indent=1))
    r = subprocess.run(CHATTERBOX + [str(job_file)], capture_output=True, text=True, timeout=timeout,
                       env=dict(os.environ, HF_HOME=str(Path("~/.cache/frameflow/hf").expanduser())))
    if r.returncode or not all(Path(p).exists() for _, _, p in lines):
        raise RuntimeError(f"chatterbox worker failed: {(r.stderr or r.stdout)[-1200:]}")
    return [p for _, _, p in lines]


def finish(raw, out, tempo=1.0):
    """Clean a raw line (trim, loudness, 48 kHz) and speed it up by `tempo` without changing pitch."""
    if abs(tempo - 1.0) < 1e-3:
        return media.clean_voice(raw, out)
    fast = Path(out).with_suffix(".fast.wav")
    media.ffmpeg("-i", raw, "-af", f"atempo={tempo:.4f}", fast)
    media.clean_voice(fast, out)
    fast.unlink(missing_ok=True)
    return Path(out)


def seconds(path):
    with wave.open(str(path)) as w:
        return w.getnframes() / w.getframerate()


def join(clips, pad, out):
    """Concatenate WAVs (all 48 kHz mono 16-bit) with silence between them: `pad` seconds, or one gap per clip boundary."""
    gaps = pad if isinstance(pad, (list, tuple)) else [pad] * max(len(clips) - 1, 0)
    with wave.open(str(out), "wb") as dst:
        dst.setnchannels(1)
        dst.setsampwidth(2)
        dst.setframerate(48000)
        for i, c in enumerate(clips):
            with wave.open(str(c)) as src:
                dst.writeframes(src.readframes(src.getnframes()))
            if i < len(clips) - 1:
                dst.writeframes(b"\x00\x00" * int(48000 * gaps[i]))


def tts(script_path, out_dir):
    script = json.loads(Path(script_path).read_text())
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    voice, speed, pad = script.get("voice", DEFAULT_VOICE), script.get("speed", 1.0), script.get("pad", 0.25)
    engine_used, fallback = script.get("engine", "kokoro"), None
    paths = [out / f"{i:02d}-{line['id']}.wav" for i, line in enumerate(script["lines"])]
    if engine_used == "chatterbox":
        try:
            raws = chatterbox_lines([(l["say"], l.get("energy", 0.6), p.with_suffix(".raw.wav")) for l, p in zip(script["lines"], paths)],
                                    out, seed=int(script.get("seed", 7)), model=script.get("model", "standard"), ref=script.get("ref"))
            for raw, p in zip(raws, paths):
                finish(raw, p, float(script.get("tempo", 1.0)))
        except Exception as e:   # no GPU memory, worker crash: the video still gets a voice
            engine_used, fallback = "kokoro", str(e)[-400:]
    if engine_used == "kokoro":
        for line, p in zip(script["lines"], paths):
            say(line["say"], p, voice, speed, script.get("lang"))
    gaps = [max(float(l.get("pause_before", 0.0)), pad) for l in script["lines"][1:]]
    clips, lines, t = [], [], 0.0
    for i, (line, clip) in enumerate(zip(script["lines"], paths)):
        d = seconds(clip)
        words = len(line["say"].split())
        lines.append({"id": line["id"], "file": clip.name, "start": round(t, 3), "seconds": round(d, 3),
                      "wpm": round(words / d * 60) if d else None})
        clips.append(clip)
        t += d + (gaps[i] if i < len(gaps) else 0)
    join(clips, gaps, out / "voice.wav")
    spoken = sum(l["seconds"] for l in lines)
    info = {"engine": engine_used, "fallback_reason": fallback, "voice": voice if engine_used == "kokoro" else "chatterbox-" + script.get("model", "standard"),
            "speed": speed, "tempo": script.get("tempo", 1.0) if engine_used == "chatterbox" else None, "pad": pad,
            "total": round(seconds(out / "voice.wav"), 3), "lufs": media.loudness(out / "voice.wav"),
            "wpm": round(sum(len(l["say"].split()) for l in script["lines"]) / spoken * 60) if spoken else None, "lines": lines}
    (out / "durations.json").write_text(json.dumps(info, indent=1))
    return info


def main():
    ap = argparse.ArgumentParser(description="Frameflow voice step (Kokoro, local).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sample")
    s.add_argument("text")
    s.add_argument("--voice", default=DEFAULT_VOICE)
    s.add_argument("--speed", type=float, default=1.0)
    s.add_argument("--out")
    sub.add_parser("voices")
    t = sub.add_parser("tts")
    t.add_argument("script")
    t.add_argument("out_dir")
    a = ap.parse_args()
    if a.cmd == "sample":
        out = Path(a.out or f"sample-{a.voice}.wav")
        say(a.text, out, a.voice, a.speed)
        print(f"{out} ({seconds(out):.2f}s, {media.loudness(out)} LUFS)")
    elif a.cmd == "voices":
        names = engine().get_voices()
        print("  ".join(v for v in names if v[:2] in ("af", "am", "bf", "bm")))
    else:
        info = tts(a.script, a.out_dir)
        for l in info["lines"]:
            print(f"{l['id']:12s} {l['seconds']:5.2f}s  {l['wpm']} wpm")
        print(f"voice.wav {info['total']:.2f}s at {info['lufs']} LUFS")


if __name__ == "__main__":
    main()
