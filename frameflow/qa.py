"""Automatic quality checks: the measurable rows of the Quality Bar, as pass/fail gates.

    frameflow qa <out-dir>     (a render folder: final.mp4, voice/words.json, script.json, assets.json)

Exit 0 when every gate passes. Writes <out-dir>/qa.json. Gates:
  length      final.mp4 is at most 60 s (30-50 s is the target; outside it is a warning)
  size        1080x1920
  loudness    integrated -15 to -13 LUFS, true peak at most -1.0 dBTP
  black       no black stretch longer than 0.5 s
  captions    word error rate of the spoken words against the script under 10%
  voice-start first word within 0.3 s
  licences    every asset ledger row has source, licence, url and author; music and voice rows present
"""
import json
import re
import subprocess
import sys
from pathlib import Path

from frameflow import captions, media

LIMITS = {"max_seconds": 60.0, "target_seconds": (30.0, 50.0), "lufs": (-15.0, -13.0), "true_peak": -1.0,
          "black_seconds": 0.5, "wer": 0.10, "voice_start": 0.3}


def loudness_and_peak(path):
    r = subprocess.run([media.FFMPEG, "-hide_banner", "-i", str(path), "-vn", "-af", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True)
    i = re.findall(r"I:\s+(-?[\d.]+) LUFS", r.stderr)
    p = re.findall(r"Peak:\s+(-?[\d.]+|-inf) dBFS", r.stderr)
    return (float(i[-1]) if i else None), (float(p[-1]) if p and p[-1] != "-inf" else None)


def black_stretches(path, min_len):
    r = subprocess.run([media.FFMPEG, "-hide_banner", "-i", str(path), "-vf", f"blackdetect=d={min_len}:pic_th=0.98",
                        "-an", "-f", "null", "-"], capture_output=True, text=True)
    return [(float(a), float(b)) for a, b in re.findall(r"black_start:([\d.]+) black_end:([\d.]+)", r.stderr)]


def run(out_dir):
    out = Path(out_dir)
    final = out / "final.mp4"
    gates, warnings = {}, []

    def gate(name, ok, detail):
        gates[name] = {"pass": bool(ok), "detail": detail}

    secs = media.duration(final)
    gate("length", secs <= LIMITS["max_seconds"], f"{secs:.2f} s (max {LIMITS['max_seconds']:.0f})")
    lo, hi = LIMITS["target_seconds"]
    if not lo <= secs <= hi:
        warnings.append(f"length {secs:.1f} s is outside the 30-50 s target")
    v = [s for s in media.probe(final)["streams"] if s["codec_type"] == "video"][0]
    gate("size", (v["width"], v["height"]) == (1080, 1920), f"{v['width']}x{v['height']}")
    lufs, peak = loudness_and_peak(final)
    lo, hi = LIMITS["lufs"]
    gate("loudness", lufs is not None and lo <= lufs <= hi and (peak is None or peak <= LIMITS["true_peak"]),
         f"{lufs} LUFS, true peak {peak} dBTP (want {lo} to {hi} LUFS, peak <= {LIMITS['true_peak']})")
    black = black_stretches(final, LIMITS["black_seconds"])
    gate("black", not black, f"{len(black)} black stretch(es) over {LIMITS['black_seconds']} s: {black[:3]}")
    script = json.loads((out / "script.json").read_text())
    words = json.loads((out / "voice" / "words.json").read_text())
    err = captions.wer(" ".join(l["say"] for l in script["lines"]), " ".join(w["w"] for w in words))
    gate("captions", err < LIMITS["wer"], f"word error rate {err:.1%} (max {LIMITS['wer']:.0%})")
    start = words[0]["s"] if words else None
    gate("voice-start", start is not None and start <= LIMITS["voice_start"], f"first word at {start} s")
    rows = json.loads((out / "assets.json").read_text()) if (out / "assets.json").exists() else []
    missing = [r.get("asset", "?") for r in rows if not all(str(r.get(k, "")).strip() for k in ("source", "licence", "url", "author"))]
    kinds = {r.get("asset") for r in rows}
    # every image the build step put in the project needs its own ledger row
    images = sorted(str(f.relative_to(out / "project")) for f in (out / "project" / "assets").glob("*")
                    if f.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")) if (out / "project" / "assets").exists() else []
    covered = {r.get("file") for r in rows}
    unlisted = [f for f in images if f not in covered]
    gate("licences", rows and not missing and not unlisted and {"voice", "music"} <= kinds,
         f"{len(rows)} rows; incomplete: {missing or 'none'}; images without a row: {unlisted or 'none'}; "
         f"voice and music rows: {'yes' if {'voice', 'music'} <= kinds else 'no'}")
    report = {"pass": all(g["pass"] for g in gates.values()), "gates": gates, "warnings": warnings}
    (out / "qa.json").write_text(json.dumps(report, indent=1))
    return report


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: frameflow qa <out-dir>")
    r = run(sys.argv[1])
    for name, g in r["gates"].items():
        print(f"{'PASS' if g['pass'] else 'FAIL'}  {name:12} {g['detail']}")
    for w in r["warnings"]:
        print(f"WARN  {w}")
    sys.exit(0 if r["pass"] else 1)


if __name__ == "__main__":
    main()
