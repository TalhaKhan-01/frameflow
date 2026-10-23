"""Small ffmpeg/ffprobe helpers shared by the pipeline steps."""
import json
import re
import shutil
import subprocess
from pathlib import Path

FFMPEG = shutil.which("ffmpeg") or "ffmpeg"
FFPROBE = shutil.which("ffprobe") or "ffprobe"


def ffmpeg(*args, timeout=600):
    r = subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-y", *map(str, args)],
                       capture_output=True, text=True, timeout=timeout)
    if r.returncode:
        raise RuntimeError(f"ffmpeg failed: {r.stderr[-800:]}")
    return r


def probe(path):
    r = subprocess.run([FFPROBE, "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)],
                       capture_output=True, text=True, check=True)
    return json.loads(r.stdout)


def duration(path):
    return float(probe(path)["format"]["duration"])


def loudness(path):
    """Integrated loudness (LUFS, EBU R128) of a file's audio."""
    r = subprocess.run([FFMPEG, "-hide_banner", "-i", str(path), "-vn", "-af", "ebur128", "-f", "null", "-"],
                       capture_output=True, text=True)
    found = re.findall(r"I:\s+(-?[\d.]+) LUFS", r.stderr)
    return float(found[-1]) if found else None


def clean_voice(raw, out, target_lufs=-15.0):
    """Trim edge silence, normalise loudness, write 48 kHz mono 16-bit WAV. Two passes: one graph can hang on ffmpeg 6.1."""
    out = Path(out)
    trimmed = out.with_suffix(".trim.wav")
    trim = "silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.05"
    ffmpeg("-i", raw, "-af", f"{trim},areverse,{trim},areverse", trimmed)
    ffmpeg("-i", trimmed, "-af", f"loudnorm=I={target_lufs}:TP=-1.5:LRA=11", "-ar", "48000", "-ac", "1",
           "-c:a", "pcm_s16le", out)
    trimmed.unlink(missing_ok=True)
    return out
