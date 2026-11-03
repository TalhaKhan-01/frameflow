"""Re-render a made show episode into a test folder with the current template and code, then QA + screening.

    uv run python spikes/show_test_render.py 2026-11-03-daily-habit-ep5 test-ep5 [--no-screening] [--set riso|paper|night] [--look puppet|pixel] [--twice]

Copies the episode's research, script and voice (no new voice, no GPU) into out/show/<test>/, re-runs visuals
(library cached), direct, sound, render, QA, the contact sheet and (unless --no-screening) the screening.
Writes nothing to the run database, the videos table or briefs/, so the real episode and its post are untouched.
"""
import json
import shutil
import sys
from pathlib import Path

from frameflow import build, show


def main():
    src, name = sys.argv[1], sys.argv[2]
    a, out = show.OUT / src, show.OUT / name
    out.mkdir(parents=True, exist_ok=True)
    for f in ("research.json", "script.json", "voice-script.json"):
        if (a / f).exists():
            shutil.copy(a / f, out / f)
    shutil.copytree(a / "voice", out / "voice", dirs_exist_ok=True)
    data, script = json.loads((out / "research.json").read_text()), json.loads((out / "script.json").read_text())
    if script.get("hook_pick"):   # the banner follows the picked hook (hookpick.apply since 3 Nov)
        from frameflow import hookpick
        g = hookpick.story_of(script["open"]["say"], script)
        if g:
            script["breaking"] = g["headline"][:55]
    ep = int(src.rsplit("ep", 1)[1])
    day = src[:10]
    media_by, _ = show.visuals(script, data, out)
    vd = show.narrate(script, out)
    c, voice_at = show.direct(script, data, vd, ep, day, media_by)
    for flag in ("--set", "--look"):   # render the same episode in another set or Habit look (P24.4.1, P24.4.3)
        if flag in sys.argv:
            c[flag[2:]] = sys.argv[sys.argv.index(flag) + 1]
    audio, sheet = show.mix(c, voice_at, out)
    pd = show.project(c, audio, out)
    code, log = build.check(pd)
    errs = [l for l in log.splitlines() if "✗ error" in l]
    final = build.render(pd, out / "final.mp4", quality="looks")
    q = show.check_render(final, c, script, vd, out)
    if "--twice" in sys.argv:   # P24.4.4: the package is deterministic (same frames on a second render)
        import hashlib, subprocess
        from frameflow import media
        def fh(v, t):
            raw = subprocess.run([media.FFMPEG, "-hide_banner", "-loglevel", "error", "-ss", f"{t:.2f}", "-i", str(v), "-frames:v", "1",
                                  "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
            return hashlib.sha256(raw).hexdigest()[:16]
        again = build.render(pd, out / "again.mp4", quality="looks")
        probe = [1.0] + [s["start"] + s["dur"] * 0.5 for s in c["segments"]] + [c["dur"] - 0.2]
        same = [round(t, 2) for t in probe if fh(final, t) != fh(again, t)]
        q["gates"]["deterministic"] = {"pass": not same, "detail": f"{len(probe)} frames compared; differ at {same}" if same else f"{len(probe)} frames identical"}
        (out / "again.mp4").unlink()
    times = [c["breakingAt"] + 1.0, c["stingAt"] + 0.7] + [s["start"] + s["dur"] * f for s in c["segments"] if s.get("topic") for f in (0.3, 0.8)] + [c["endAt"] + 1.0]
    png = show.stills(final, times, out, "contact")
    res = {"check_errors": len(errs), "qa": q["pass"], "gates": {k: v["pass"] for k, v in q["gates"].items()}, "contact": str(png)}
    if "--no-screening" not in sys.argv:
        scr = show.screening(png, times, script)
        res["screening"] = {"total": scr["total"], "max": scr["max"], "rows": scr["rows"]}
        (out / "screening.json").write_text(json.dumps(scr, ensure_ascii=False, indent=1))
    (out / "test.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
