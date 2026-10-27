"""P17.2.2 voice audition: the same Hinglish line per character, from a designed VoiceStudio voice and from Kokoro.

    uv run python spikes/voice_audition.py [--api http://127.0.0.1:7311] [--seed 7]

Needs the VoiceStudio backend running (vault Docs/Cast Bible.md, start command). Writes out/voice-audition/
<id>-voicestudio.wav, <id>-kokoro.wav and audition.json (voice settings, seconds to make, real-time factor).
"""
import argparse
import json
import time
import urllib.request
import uuid
from pathlib import Path

import soundfile as sf

from frameflow import voice

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "out" / "voice-audition"
LINES = {   # cast id: (name, VoiceStudio instruct, Kokoro voice, line)
    "factcheck": ("Sach-in", "male, middle-aged, low pitch, indian accent", "am_michael",
                  "Source dikhao. Bina source ke yeh number aage nahi jaayega."),
    "writer": ("Kavi Kalam", "male, young adult, moderate pitch, indian accent", "am_puck",
               "Yeh line dil se likhi hai, Kat. Isko kaatoge toh kahani ka dil toot jaayega."),
    "editor": ("Kat", "female, young adult, low pitch, indian accent", "af_nicole",
               "Kat. Dil ki baat saath second mein nahi aati."),
}


def generate(api, text, instruct, seed, out):
    fields = {"text": text, "instruct": instruct, "seed": str(seed), "language": "en"}
    boundary = uuid.uuid4().hex
    body = b"".join(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
                    for k, v in fields.items()) + f"--{boundary}--\r\n".encode()
    req = urllib.request.Request(api + "/generate", data=body, method="POST",
                                 headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(req, timeout=900) as r:
        data, kind = r.read(), r.headers.get("Content-Type", "")
    if "json" in kind:   # some builds answer with the saved take's metadata instead of the audio
        meta = json.loads(data)
        url = meta.get("audio_url") or meta.get("url")
        if not url:
            raise SystemExit(f"no audio in the /generate answer: {str(meta)[:400]}")
        with urllib.request.urlopen(api + url if url.startswith("/") else url, timeout=120) as r:
            data = r.read()
    out.write_bytes(data)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://127.0.0.1:7311")
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    report = []
    for pid, (name, instruct, kokoro_voice, line) in LINES.items():
        row = {"id": pid, "name": name, "line": line, "instruct": instruct, "seed": a.seed, "kokoro_voice": kokoro_voice}
        for engine in ("voicestudio", "kokoro"):
            out = OUT / f"{pid}-{engine}.wav"
            t = time.time()
            if engine == "voicestudio":
                generate(a.api, line, instruct, a.seed, out)
            else:
                voice.say(line, out, voice=kokoro_voice)
            made = time.time() - t
            dur = sf.info(str(out)).duration
            row[engine] = {"file": out.name, "seconds_to_make": round(made, 2), "audio_seconds": round(dur, 2),
                           "realtime_factor": round(made / dur, 2) if dur else None}
            print(f"{name:12} {engine:12} {made:6.1f} s for {dur:4.1f} s of audio")
        report.append(row)
    (OUT / "audition.json").write_text(json.dumps(report, ensure_ascii=False, indent=1))
    print("wrote", OUT / "audition.json")


if __name__ == "__main__":
    main()
