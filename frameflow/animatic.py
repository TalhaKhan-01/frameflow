"""The animatic (P15 Studio board): a 12 fps draft render of the project, screened before the real render.

    python -m frameflow.animatic <render-dir>      writes <render-dir>/animatic.mp4, animatic.jpg and animatic.json

The screening reads a contact sheet of stills plus the script, and QA measures drawn events at 12 frames a second on a
small grey copy; neither needs the delivery render. A draft at 12 fps gives both, exactly: on the Kimi video (26 Oct) it
took 58 s (the delivery render plus mix took about 148 s), found 138 events against the final's 140 and the same longest
gaps (3.1 s at 103.2 s vs 3.0 s). So the full screening, art direction and their fixes happen here, while a fix is still
a text edit, and the delivery render runs once. (Stills by `hyperframes snapshot` were tried first: they match too, but
can't measure motion, and the project's linked stylesheet doesn't apply in snapshot mode.)
"""
import json
import sys
import time
from pathlib import Path

from frameflow import bar, build, profiles, qa, review

FPS = 12


def measured(video):
    """Drawn events on the draft, with the bar's verdict (same code and thresholds as the QA 'events' gate)."""
    p = bar.load()["pacing"]
    ev, total = qa.visual_events(video)
    gaps = [(b - a, a) for a, b in zip([0.0] + ev, ev + [total])]
    worst, at = max(gaps) if gaps else (total, 0.0)
    rate = len(ev) / total * 10 if total else 0.0
    return {"events": ev, "seconds": round(total, 2), "per_10s": round(rate, 1), "longest_gap": round(worst, 2), "gap_at": round(at, 2),
            "pass": worst <= p["max_event_gap"] and rate >= p["events_per_10s"],
            "detail": f"{rate:.1f} visual events per 10 s (min {p['events_per_10s']}), longest gap {worst:.1f} s (max {p['max_event_gap']}) at {at:.1f} s"}


def make(render_dir):
    """Draft render -> contact sheet -> measured events, for a render folder whose project exists (after build.project)."""
    out = Path(render_dir).resolve()
    pc = profiles.pipeline()
    t0 = time.time()
    video = build.render(out / "project", out / "animatic.mp4", "draft", fps=FPS)
    sheet = review.keyframes_v2(out, pc["keyframe_every"], width=pc["keyframe_width"], video=video, name="animatic.jpg")
    m = measured(video)
    r = {"video": str(video), "sheet": str(sheet), "every": pc["keyframe_every"], "render_seconds": round(time.time() - t0, 1), **m}
    (out / "animatic.json").write_text(json.dumps({k: v for k, v in r.items() if k != "events"} | {"events": len(m["events"])}, indent=1))
    return r


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: python -m frameflow.animatic <render-dir>")
    r = make(sys.argv[1])
    print(json.dumps({k: r[k] for k in ("sheet", "render_seconds", "detail", "pass")}, indent=1))


if __name__ == "__main__":
    main()
