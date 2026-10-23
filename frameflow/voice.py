"""Voice step: local text-to-speech with Kokoro (Apache-2.0 model, runs on this machine, free).

    python -m frameflow.voice sample "<text>" [--voice af_heart] [--speed 1.0] [--out f.wav]
    python -m frameflow.voice voices
    python -m frameflow.voice tts <script.json> <out-dir>

script.json: {"voice": "af_heart", "speed": 1.0, "pad": 0.25, "lines": [{"id": "hook", "say": "..."}, ...]}
tts writes NN-<id>.wav per line (48 kHz mono, about -15 LUFS), voice.wav (all lines joined with `pad` seconds
between them) and durations.json (seconds per line, start times, words per minute, loudness of voice.wav).
Model files: ~/.cache/frameflow/kokoro/ (kokoro-v1.0.onnx, voices-v1.0.bin), or FRAMEFLOW_KOKORO.
"""
import argparse
import json
import os
import tempfile
import wave
from pathlib import Path

from frameflow import media

MODEL_DIR = Path(os.environ.get("FRAMEFLOW_KOKORO", "~/.cache/frameflow/kokoro")).expanduser()
DEFAULT_VOICE = "af_heart"
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


def seconds(path):
    with wave.open(str(path)) as w:
        return w.getnframes() / w.getframerate()


def join(clips, pad, out):
    """Concatenate WAVs with `pad` seconds of silence between them (all 48 kHz mono 16-bit)."""
    with wave.open(str(out), "wb") as dst:
        dst.setnchannels(1)
        dst.setsampwidth(2)
        dst.setframerate(48000)
        silence = b"\x00\x00" * int(48000 * pad)
        for i, c in enumerate(clips):
            with wave.open(str(c)) as src:
                dst.writeframes(src.readframes(src.getnframes()))
            if i < len(clips) - 1:
                dst.writeframes(silence)


def tts(script_path, out_dir):
    script = json.loads(Path(script_path).read_text())
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    voice, speed, pad = script.get("voice", DEFAULT_VOICE), script.get("speed", 1.0), script.get("pad", 0.25)
    clips, lines, t = [], [], 0.0
    for i, line in enumerate(script["lines"]):
        clip = say(line["say"], out / f"{i:02d}-{line['id']}.wav", voice, speed, script.get("lang"))
        d = seconds(clip)
        words = len(line["say"].split())
        lines.append({"id": line["id"], "file": clip.name, "start": round(t, 3), "seconds": round(d, 3),
                      "wpm": round(words / d * 60) if d else None})
        clips.append(clip)
        t += d + pad
    join(clips, pad, out / "voice.wav")
    info = {"voice": voice, "speed": speed, "pad": pad, "total": round(seconds(out / "voice.wav"), 3),
            "lufs": media.loudness(out / "voice.wav"), "lines": lines}
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
