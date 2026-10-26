"""Showrunner desk glue (P15 Studio board): Talha's Revise words -> a change order he confirms -> exactly its stages.

    python -m frameflow.producer issues <day>     the known issues the Revise message offers as buttons
    python -m frameflow.producer order <day>      build the change order from the run's notes and ticked issues (spawned job)
    python -m frameflow.producer apply <day>      run the confirmed order (called by daily.revise)

The skill (~/Talha_Khan/Claude/skills/shorts-producer) reads the words and decides WHAT changes; which stages that re-runs
comes from research/shorts-producer.json in code. Orders are saved as out/<slug>/change-order-<n>.json.
"""
import json
import sys
from pathlib import Path

from frameflow import board, build, direct, pipeline, progress, qa, review, videos

ROOT = Path(__file__).resolve().parent.parent
PRODUCER = Path.home() / "Talha_Khan" / "Claude" / "skills" / "shorts-producer" / "scripts" / "producer.py"
TARGET_ROWS = {   # where each kind of change goes in direct.revise (WRITER_ROWS / DIRECTOR_ROWS route them)
    "words": ["story", "visual_storytelling"],     # the writer rewrites, the director re-maps the new lines
    "visuals": ["visual_storytelling"],
    "voice": ["persona_humour"],                    # the writer's delivery marks (pace, pauses, stress), same words
    "sound": ["sound_plan"],
}


def _video(day):
    from frameflow import daily
    run = daily.get(day)
    row = videos.db().execute("SELECT * FROM videos WHERE id=?", (run["video_id"],)).fetchone()
    return run, row, Path(row["out_dir"]), Path(row["plan"])


def issues(day):
    """Short numbered issues: the screening's fixes, then failed automatic checks."""
    _, _, out, _ = _video(day)
    rev = json.loads((out / "review.json").read_text()) if (out / "review.json").exists() else {}
    q = json.loads((out / "qa.json").read_text()) if (out / "qa.json").exists() else {}
    found = [f"{f['row'].replace('_', ' ')}: {f['fix']}" for f in rev.get("fixes", []) if f.get("fix")]
    found += [f"check '{k}' failed: {g.get('detail', '')}" for k, g in (q.get("gates") or {}).items() if not g.get("pass")]
    return found


def context(day):
    run, row, out, plan_path = _video(day)
    plan = json.loads((out / "plan.json").read_text())
    slots = build.timings(plan, out / "voice") if (out / "voice" / "durations.json").exists() else [(0, 0)] * len(plan["scenes"])
    scenes = []
    for i, (s, (st, d)) in enumerate(zip(plan["scenes"], slots)):
        shown = {k: v for k, v in s.get("data", {}).items() if k not in ("beats", "cues") and not k.startswith("_")}
        scenes.append({"i": i, "start": st, "end": st + d, "type": s["type"],
                       "say": " ".join(l.get("say", "") for l in s.get("lines", [{"say": s.get("say", "")}])),
                       "on_screen": json.dumps(shown, ensure_ascii=False)[:200]})
    rev = json.loads((out / "review.json").read_text()) if (out / "review.json").exists() else {}
    q = json.loads((out / "qa.json").read_text()) if (out / "qa.json").exists() else {}
    pub = json.loads((out / "publish.json").read_text()) if (out / "publish.json").exists() else {}
    all_issues = issues(day)
    picks = json.loads(run.get("revise_picks") or "[]")
    return {"words": (run.get("notes") or "").strip(), "picked": [all_issues[i] for i in picks if i < len(all_issues)],
            "title": plan["title"], "scenes": scenes, "screening": {"scores": rev.get("scores", {}), "fixes": rev.get("fixes", [])},
            "failed_checks": [f"{k}: {g.get('detail', '')}" for k, g in (q.get("gates") or {}).items() if not g.get("pass")],
            "post_text": pub.get("ig_caption", ""), "purpose": row["id"]}


def order(day):
    """The change order for the run's words and ticked issues (one Sonnet call through the skill)."""
    from frameflow import daily
    run, row, out, _ = _video(day)
    ctx = context(day)
    n = len(list(out.glob("change-order-*.json"))) + 1
    (out / f"change-order-{n}.context.json").write_text(json.dumps(ctx, ensure_ascii=False, indent=1))
    path = out / f"change-order-{n}.json"
    with progress.step("showrunner: change order", desk="showrunner") as info:
        direct.skill([PRODUCER, "--project", ROOT, "order", out / f"change-order-{n}.context.json", "--out", path], timeout=900, strict=True)
        o = json.loads(path.read_text())
        info.update({"gist": o["gist"][:200], "targets": o["targets"], "stages": o["stages"], "minutes": o["minutes"]})
    daily.update(day, order_file=str(path), note=f"change order {n}: {', '.join(o['targets'])} ({o['minutes']} min)")
    return o


def message(o):
    lines = ["Here's what I understood:", o["gist"], "", "I'll change:"]
    for c in o["changes"]:
        where = f" (scene {', '.join(map(str, c['scenes']))})" if c.get("scenes") else ""
        lines.append(f"• {c['target'].replace('_', ' ')}{where}: {c['instruction']}")
    if o.get("keep"):
        lines += ["", "I'll keep: " + "; ".join(o["keep"])]
    stages = " → ".join(o["stages"])
    lines += ["", f"Re-runs: {stages} (usually ~{o['minutes']} min)."]
    if o.get("question"):
        lines += ["", f"One question: {o['question']} (answer with Change it, or tap Go if my guess is fine)"]
    return "\n".join(lines)


def fixes_for(o):
    """The order as review-style fixes for direct.revise, plus keep-lines so the untouched parts stay."""
    out = []
    for c in o["changes"]:
        where = f"scene(s) {', '.join(map(str, c['scenes']))}: " if c.get("scenes") else ""
        for row in TARGET_ROWS.get(c["target"], []):
            note = " Change delivery marks only (pace, pauses, stress); keep the words." if c["target"] == "voice" else ""
            out.append({"row": row, "fix": f"Talha (the channel owner) asks: {where}{c['instruction']}.{note}"})
    for k in o.get("keep", []):
        out.append({"row": "flow", "fix": f"KEEP unchanged (Talha didn't ask to change it): {k}"})   # flow goes to both desks
    return out


def apply(day):
    """Run a confirmed order: writer/director fixes if it needs them, then only the stages it lists."""
    from frameflow import cover, publish
    run, row, out, plan_path = _video(day)
    o = json.loads(Path(run["order_file"]).read_text())
    st = set(o["stages"])
    lane, brief = run["lane"], run["brief"]
    if st & {"writer", "director"}:
        board._revise(brief, plan_path, fixes_for(o), lane, "change order: writer and director", "writer" if "writer" in st else "director")
    if "narrator" in st:   # words, visuals or voice: through every desk to one delivery render
        b = board.run(brief, plan_path, lane)
        q, r = b["qa"], b["review"]
    elif "remix" in st:   # sound only: new cue sheet into the project, new mix on the kept frames
        shutil_plan(plan_path, out)
        pipeline.build_stage(out)
        pipeline.remix_stage(out)
        with progress.step("technical QC (QA gates)", desk="qc"):
            q = qa.run(out)
        r = json.loads((out / "review.json").read_text())   # pictures and words unchanged: the screening stands
    elif "cover" in st:   # new cover text: it is the end card's title, so the end card is redrawn and the video re-rendered
        notes = "; ".join(c["instruction"] for c in o["changes"] if c["target"] == "cover")
        cover.make(plan_path.parent, notes=notes)
        d = direct.direct(brief, plan_path.parent, lane, skip_writer=True, skip_director=True)
        if d["errors"]:
            raise RuntimeError(f"the plan with the new cover is invalid: {d['errors']}")
        pipeline.build_stage(out) if (out / "voice" / "durations.json").exists() else None
        pipeline.deliver_stage(out)
        with progress.step("technical QC (QA gates)", desk="qc"):
            q = qa.run(out)
        r = review.check_final(out, json.loads((out / "plan.json").read_text()))
    else:
        q = json.loads((out / "qa.json").read_text())
        r = json.loads((out / "review.json").read_text())
    if "packaging" in st:
        notes = "; ".join(c["instruction"] for c in o["changes"] if c["target"] == "post_text")
        with progress.step("packaging: post text", desk="packaging"):
            publish.publish(row["id"], owner_notes=notes, require=False)
    return q, r


def shutil_plan(plan_path, out):
    """The render folder's plan.json follows the revised plan (voice_stage copies it on a full run)."""
    if Path(plan_path).resolve() != (Path(out) / "plan.json").resolve():
        (Path(out) / "plan.json").write_text(Path(plan_path).read_text())


def main():
    cmd, day = (sys.argv[1:] + [None, None])[:2]
    if cmd == "issues":
        print("\n".join(f"{i + 1}. {x}" for i, x in enumerate(issues(day))))
    elif cmd == "order":
        print(json.dumps(order(day), ensure_ascii=False, indent=1))
    elif cmd == "apply":
        q, r = apply(day)
        print(json.dumps({"qa": q["pass"], "review": f"{r['total']}/{r.get('max')}"}))
    else:
        sys.exit("usage: python -m frameflow.producer issues|order|apply <day>")


if __name__ == "__main__":
    main()
