"""Automatic quality checks: the measurable rows of the Quality Bar, as pass/fail gates.

    frameflow qa <out-dir>     (a render folder: final.mp4, voice/words.json, script.json, assets.json)

Exit 0 when every gate passes. Writes <out-dir>/qa.json. Every limit comes from research/quality-bar.json (frameflow.bar). Gates:
  length      final.mp4 is at most 60 s (30-50 s is the target; outside it is a warning)
  size        1080x1920
  loudness    integrated -15 to -13 LUFS, true peak at most -1.0 dBTP
  black       no black stretch longer than 0.5 s
  captions    word error rate of the spoken words against the script under 10%
  voice-start first word within 0.3 s
  licences    every asset ledger row has source, licence, url and author; music and voice rows present
Version-2 plans (Quality Bar v2) add:
  length      the bar's target and hard limit
  events      visual events (frame changes) at least pacing.events_per_10s, no stretch over pacing.max_event_gap without one
  rehooks     no stretch over pacing.max_rehook_gap between re-hook beats (but/twist/loop/payoff or a 'rehook' device) on the
              real voice timing, up to the house end card
"""
import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np

from frameflow import bar, captions, media

V1_LENGTH = {"max_seconds": 60.0, "target_seconds": (30.0, 50.0)}   # version-1 plans only


def limits():
    """(LIMITS, V2) from the shared Quality Bar (research/quality-bar.json), read fresh so an edit applies at once."""
    b = bar.load()
    lim = {**V1_LENGTH, "lufs": tuple(b["sound"]["lufs"]), "true_peak": b["sound"]["true_peak"],
           "black_seconds": b["picture"]["black_seconds"], "wer": b["captions"]["max_word_error"], "voice_start": b["voice"]["first_word_by"]}
    v2 = {"max_seconds": float(b["length"]["max_seconds"]), "target_seconds": tuple(b["length"]["target_seconds"]), **b["pacing"]}
    return lim, v2


LIMITS, V2 = limits()


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




def visual_events(path, fps=12, changed=0.7, min_sep=0.5):
    """Times where something visibly happens: at least `changed` % of the pixels above the caption band change by more
    than 18 grey levels from one frame to the next (96x170 grey, 12 fps). Ongoing motion counts at most every `min_sep`
    seconds; the slow camera drift stays under the threshold. Calibrated on the drawn-scene samples (2026-10-24)."""
    w, h = 96, 170
    raw = subprocess.run([media.FFMPEG, "-loglevel", "error", "-i", str(path), "-vf", f"fps={fps},scale={w}:{h},format=gray",
                          "-f", "rawvideo", "-"], capture_output=True).stdout
    frames = np.frombuffer(raw, np.uint8).reshape(-1, h, w).astype(np.float32)[:, : int(h * 0.64)]
    if len(frames) < 2:
        return [], 0.0
    share = (np.abs(np.diff(frames, axis=0)) > 18).mean(axis=(1, 2)) * 100
    events, last = [], -9.0
    for i, v in enumerate(share):
        t = (i + 1) / fps
        if v >= changed and t - last >= min_sep:
            events.append(round(t, 2))
            last = t
    return events, len(frames) / fps


PAPER = (0xF3, 0xEE, 0xE4)   # Paper Press background (--ff-bg)


def blank_spans(path, fps=4, ink=0.025, min_len=0.75):
    """Stretches where the picture above the caption band is blank paper: under `ink` of its pixels differ clearly from
    the background for at least `min_len` seconds. Calibrated on Black October (2026-10-25): a kicker alone measures
    0.4-2%, one line of headline text 3-4%, a drawn scene 10-30%. So this catches empty frames (a template showing
    nothing, a beat that never fires), not sparse text cards; those are the reviewer's call. Transitions don't count."""
    w, h = 270, 480
    raw = subprocess.run([media.FFMPEG, "-loglevel", "error", "-i", str(path), "-vf", f"fps={fps},scale={w}:{h}", "-f", "rawvideo",
                          "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
    frames = np.frombuffer(raw, np.uint8).reshape(-1, h, w, 3).astype(np.int16)
    y0, y1 = int(230 / 1920 * h), int(1280 / 1920 * h)
    share = [(np.abs(fr[y0:y1] - np.array(PAPER)).sum(2) > 60).mean() for fr in frames]
    spans, start = [], None
    for i, s in enumerate(share + [1.0]):
        if s < ink and start is None:
            start = i
        elif s >= ink and start is not None:
            if (i - start) / fps >= min_len:
                spans.append((round(start / fps, 2), round(i / fps, 2)))
            start = None
    return spans


REHOOK_BEATS = ("but", "twist", "loop", "payoff")   # the payoff is the reveal that answers the loop: a re-hook moment too


def rehook_stretch(out):
    """The longest stretch between re-hook moments on the real voice: (seconds, (t, where it starts), (t, where it ends),
    scenes inside). It ends where the house end card starts: the follow line is fixed and owes the viewer no re-hook
    (before 26 Oct the measurement ran to the last second, so a long ending plus the end card failed on its own)."""
    plan = json.loads((out / "plan.json").read_text())
    dur = json.loads((out / "voice" / "durations.json").read_text())
    starts = {l["id"]: l["start"] for l in dur["lines"]}
    lid = lambda i, s, j: f"s{i}" if len(s["lines"]) == 1 else f"s{i}.{j}"
    end = next((starts.get(lid(i, s, 0)) for i, s in enumerate(plan["scenes"]) if s["type"] == "endcard" and s.get("lines")), None)
    end = end if end is not None else dur["total"]
    marks = [(0.0, "the start")]
    for i, s in enumerate(plan["scenes"]):
        for j, line in enumerate(s.get("lines", [])):
            t = starts.get(lid(i, s, j))
            if t is not None and t < end and (line.get("beat") in REHOOK_BEATS or "rehook" in line.get("devices", [])):
                marks.append((t, f"scene {i}: \"{line.get('say', '')[:60]}\""))
    marks.append((end, "the end card" if end < dur["total"] else "the end"))
    gap, a, b = max(((y[0] - x[0], x, y) for x, y in zip(marks, marks[1:])), key=lambda g: g[0])
    inside = sorted({i for i, s in enumerate(plan["scenes"]) for j, _ in enumerate(s.get("lines", []))
                     if a[0] < starts.get(lid(i, s, j), -1) < b[0]})
    return gap, a, b, [f"scene {i}" for i in inside]


def rehook_gaps(out):
    """Longest stretch between re-hook moments, on the real voice timing (v2 plans with lines)."""
    return rehook_stretch(out)[0]


def run(out_dir):
    LIMITS, V2 = limits()
    out = Path(out_dir)
    final = out / "final.mp4"
    gates, warnings = {}, []

    def gate(name, ok, detail):
        gates[name] = {"pass": bool(ok), "detail": detail}

    plan = json.loads((out / "plan.json").read_text()) if (out / "plan.json").exists() else {}
    v2 = plan.get("version", 1) >= 2
    L = {**LIMITS, **(V2 if v2 else {})}   # v2 length and pacing come from the shared bar
    secs = media.duration(final)
    gate("length", secs <= L["max_seconds"], f"{secs:.2f} s (max {L['max_seconds']:.0f})")
    lo, hi = L["target_seconds"]
    if not lo <= secs <= hi:
        warnings.append(f"length {secs:.1f} s is outside the {lo:.0f}-{hi:.0f} s target")
    if v2:
        ev, total = visual_events(final)
        gaps = [b - a for a, b in zip([0.0] + ev, ev + [total])]
        rate = len(ev) / total * 10 if total else 0
        gate("events", rate >= V2["events_per_10s"] and max(gaps) <= V2["max_event_gap"],
             f"{rate:.1f} visual events per 10 s (min {V2['events_per_10s']}), longest gap {max(gaps):.1f} s (max {V2['max_event_gap']}) "
             f"at {ev[gaps.index(max(gaps)) - 1] if gaps.index(max(gaps)) else 0:.1f} s")
        pic = bar.load()["picture"]
        blanks = blank_spans(final, ink=pic["blank_ink"])
        gate("blank-frames", not [s for s in blanks if s[1] - s[0] >= pic["blank_fail_seconds"]],
             f"blank picture (under {pic['blank_ink']:.1%} drawn, 0.75 s or more): {blanks or 'none'}; fails at {pic['blank_fail_seconds']:g} s or more")
        rg = rehook_gaps(out)
        gate("rehooks", rg <= V2["max_rehook_gap"], f"longest stretch without a re-hook {rg:.1f} s (max {V2['max_rehook_gap']})")
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
    err = captions.wer(re.sub(r"\[(chuckle|laugh)\]", " ", " ".join(l["say"] for l in script["lines"])), " ".join(w["w"] for w in words))
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
