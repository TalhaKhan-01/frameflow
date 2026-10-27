"""Narrator desk (P15 Studio board): timing checks on the real voice, before any picture is made.

    python -m frameflow.precheck <render-dir>     writes <render-dir>/precheck.json; exit 0 when every check passes

Runs inside pipeline.render after the voice and its word timing, before the scenes are built or rendered. Every check
needs only the plan and the voice track, so a fix is still a text edit:
  rehooks     longest stretch between re-hook beats on the real voice (qa.rehook_gaps, the same code QA uses later)
  captions    word error rate of the spoken words against the script (what the caption gate measures later)
  length      the voice's length against the bar
  voice-start first word time
  events      ADVISORY estimate of drawn events: a scene's entrance plus each storyboard beat, timed by its cue word in the
              real voice (or its offset in seconds). Templates also move between beats, so the estimate flags stretches
              that turn out fine; it never fails the check. The animatic (a 12 fps draft render) measures the real thing.
Thresholds: research/quality-bar.json (frameflow.bar).
"""
import json
import re
import sys
from pathlib import Path

from frameflow import bar, build, captions, qa


def _norm(w):
    return re.sub(r"[^a-z0-9]", "", w.lower())


def cue_time(phrase, words, start, end):
    """When `phrase` is spoken inside [start, end): the start of its first word, or None."""
    want = [_norm(x) for x in phrase.split() if _norm(x)]
    if not want:
        return None
    toks = [(i, _norm(w["w"])) for i, w in enumerate(words) if start - 0.05 <= w["s"] < end + 0.05]
    for k in range(len(toks) - len(want) + 1):
        if all(toks[k + j][1] == want[j] for j in range(len(want))):
            return words[toks[k][0]]["s"]
    first = next((words[i]["s"] for i, t in toks if t == want[0]), None)   # loose: the first word alone
    return first


def event_times(plan, words, slots):
    """Estimated drawn events: each scene's entrance and every beat (and a beat's 'until' moment)."""
    times = []
    for s, (st, dur) in zip(plan["scenes"], slots):
        end = st + dur
        times.append(round(st, 2))
        cues = s.get("data", {}).get("cues") or {}
        for b in s.get("data", {}).get("beats", []) or []:
            for key in ("at", "until"):
                at = b.get(key)
                if at is None:
                    continue
                if isinstance(at, (int, float)):
                    t = st + float(at)
                elif at == "start":
                    t = st
                else:
                    t = cue_time(cues.get(at, at), words, st, end)
                if t is not None and st <= t < end:
                    times.append(round(t, 2))
    return sorted(set(times))


def run(render_dir):
    out = Path(render_dir)
    b = bar.load()
    plan = json.loads((out / "plan.json").read_text())
    script = json.loads((out / "script.json").read_text())
    words = json.loads((out / "voice" / "words.json").read_text())
    total = json.loads((out / "voice" / "durations.json").read_text())["total"]
    checks = {}

    def check(name, ok, detail, fix_row=None, fix=None):
        checks[name] = {"pass": bool(ok), "detail": detail, **({"row": fix_row, "fix": fix} if not ok else {})}

    rg, lim = qa.rehook_gaps(out), b["pacing"]["max_rehook_gap"]
    over = qa.rehook_stretches(out, lim)
    where = "; ".join(f"{g:.1f} s from {a[0]:.1f} s ({a[1]}) to {z[0]:.1f} s ({z[1]}), covering {', '.join(ins) or 'one line'}, "
                      f"so add one around {(a[0] + z[0]) / 2:.0f} s" for g, a, z, ins in over)
    check("rehooks", rg <= lim, f"longest stretch without a re-hook {rg:.1f} s (max {lim}); {len(over)} stretch(es) over",
          "story", f"on the real voice {len(over)} stretch(es) run longer than {lim} s without a re-hook: {where}. A re-hook is a 'but', "
                   f"a twist, a question to the viewer or a reveal, marked as a beat or the rehook device; cutting words elsewhere doesn't "
                   f"help. Change only the lines in those stretches; keep every other line exactly as it is.")
    err = captions.wer(re.sub(r"\[(chuckle|laugh)\]", " ", " ".join(l["say"] for l in script["lines"])), " ".join(w["w"] for w in words))
    check("captions", err < b["captions"]["max_word_error"], f"word error rate {err:.1%} (max {b['captions']['max_word_error']:.0%})",
          "story", f"the voice is misheard on {err:.1%} of words: spell out numbers and names as they are said, avoid tongue-twisters and rare acronyms")
    lo, hi = b["length"]["target_seconds"]
    check("length", total <= b["length"]["max_seconds"], f"{total:.1f} s of voice (max {b['length']['max_seconds']:.0f}, target {lo:.0f}-{hi:.0f})",
          "pacing", f"the voice runs {total:.0f} s, over {b['length']['max_seconds']:.0f} s: cut words")
    start = words[0]["s"] if words else None
    check("voice-start", start is not None and start <= b["voice"]["first_word_by"], f"first word at {start} s",
          "pacing", "the first word must come within the first moment: no silence before the hook")
    slots = build.timings(plan, out / "voice")
    ev = event_times(plan, words, slots)
    gaps = [(b2 - a, a) for a, b2 in zip(ev, ev[1:] + [total])]
    worst, at = max(gaps) if gaps else (total, 0.0)
    rate = len(ev) / total * 10 if total else 0
    scene_at = next((i for i, (st, d) in enumerate(slots) if st <= at < st + d), None)
    check("events", worst <= b["pacing"]["max_event_gap"] and rate >= b["pacing"]["events_per_10s"],
          f"estimated {rate:.1f} drawn events per 10 s, longest gap {worst:.1f} s at {at:.1f} s (scene {scene_at})",
          "pacing", f"scene {scene_at}: nothing new is drawn for {worst:.1f} s from {at:.1f} s; add a beat on a word in that stretch "
                    f"(one at least every {b['pacing']['max_event_gap']} s)")
    checks["events"]["advisory"] = True
    r = {"pass": all(c["pass"] for k, c in checks.items() if not c.get("advisory")), "checks": checks, "events": ev, "voice_seconds": round(total, 2),
         "words_per_second": round(sum(len(l["say"].split()) for l in script["lines"]) / total, 3) if total else None}
    (out / "precheck.json").write_text(json.dumps(r, ensure_ascii=False, indent=1))
    return r


def fixes(r):
    """The failed checks as review-style fixes for direct.revise (row routing as the review's)."""
    return [{"row": c["row"], "fix": f"pre-render check '{k}': {c['fix']} ({c['detail']})"} for k, c in r["checks"].items()
            if not c["pass"] and not c.get("advisory")]


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: python -m frameflow.precheck <render-dir>")
    r = run(sys.argv[1])
    for k, c in r["checks"].items():
        print(f"{'PASS' if c['pass'] else ('NOTE' if c.get('advisory') else 'FAIL')}  {k}: {c['detail']}")
    sys.exit(0 if r["pass"] else 1)


if __name__ == "__main__":
    main()
