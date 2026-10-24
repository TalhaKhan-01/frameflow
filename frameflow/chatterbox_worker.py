"""Chatterbox worker: runs in its own throwaway environment (PyTorch is too heavy for the project env).

    uv run --no-project --python 3.12 --with chatterbox-tts==0.1.7 --with setuptools==80.9.0 python -I frameflow/chatterbox_worker.py <job.json>

job.json: {"model": "standard" | "turbo", "ref": optional reference wav (turbo: required unless built-in voice),
           "lines": [{"text": "...", "out": "/abs/raw.wav", "exaggeration": 0.65, "cfg_weight": 0.5,
                      "temperature": 0.8, "seed": 7}, ...]}
Writes each line's raw WAV at the model's sample rate (24 kHz). The same text, settings and seed give the same audio.
Standalone on purpose: imports nothing from frameflow.
"""
import json
import os
import sys

os.environ.setdefault("HF_HOME", os.path.expanduser("~/.cache/frameflow/hf"))

import torch  # noqa: E402
import torchaudio  # noqa: E402


def seed_all(seed):
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def main():
    job = json.load(open(sys.argv[1]))
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False
    device = "cuda" if torch.cuda.is_available() else "cpu"
    if job.get("model") == "turbo":
        from chatterbox.tts_turbo import ChatterboxTurboTTS
        model = ChatterboxTurboTTS.from_pretrained(device=device)
        if job.get("ref"):
            model.prepare_conditionals(job["ref"])
    else:
        from chatterbox.tts import ChatterboxTTS
        model = ChatterboxTTS.from_pretrained(device=device)
        if job.get("ref"):
            model.prepare_conditionals(job["ref"], exaggeration=job["lines"][0].get("exaggeration", 0.5))
    done = []
    for line in job["lines"]:
        seed_all(int(line.get("seed", 7)))
        kw = {"temperature": float(line.get("temperature", 0.8))}
        if job.get("model") != "turbo":
            kw.update(exaggeration=float(line.get("exaggeration", 0.5)), cfg_weight=float(line.get("cfg_weight", 0.5)))
        with torch.inference_mode():
            wav = model.generate(line["text"], **kw)
        torchaudio.save(line["out"], wav.cpu(), model.sr)
        done.append(line["out"])
        print(json.dumps({"done": line["out"]}), flush=True)
    print(json.dumps({"ok": True, "sr": model.sr, "files": len(done), "device": device}))


if __name__ == "__main__":
    main()
