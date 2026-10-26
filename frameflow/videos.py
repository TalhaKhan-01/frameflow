"""Video register: every rendered video, its checks, and Talha's approval. Nothing is published without approval.

    frameflow make <idea-id>             script -> render -> qa -> review (+ one rewrite on FIX) -> awaiting approval
    frameflow status                     list videos and their state
    frameflow approve <video-id>         Talha approves (only after watching final.mp4)
    frameflow reject <video-id> <why>    send back with a reason
"""
import datetime as dt
import json
import sqlite3
from pathlib import Path

from frameflow import ideas, pipeline, progress, qa, review, script

ROOT = Path(__file__).resolve().parent.parent

SCHEMA = """
CREATE TABLE IF NOT EXISTS videos (
  id TEXT PRIMARY KEY, idea_id INTEGER, plan TEXT, out_dir TEXT, lane TEXT, title TEXT,
  qa_pass INTEGER, review_total INTEGER, review_pass INTEGER, status TEXT, note TEXT,
  youtube_url TEXT, instagram_url TEXT, created_at TEXT, updated_at TEXT);
"""


def db():
    con = ideas.db()
    con.executescript(SCHEMA)
    return con


def now():
    return dt.datetime.now().replace(microsecond=0).isoformat()


def check(out):
    with progress.step("automatic checks (QA gates)") as info:
        q = qa.run(out)
        g = q.get("gates", {})
        info.update({"pass": q.get("pass"), "passed": sum(1 for x in g.values() if x.get("pass")), "of": len(g),
                     "failed": [f"{k}: {x.get('detail', '')}"[:160] for k, x in g.items() if not x.get("pass")]})
    with progress.step("review (Opus watches the video)") as info:
        r = review.run(out)
        info.update({"total": r.get("total"), "max": r.get("max"), "pass": r.get("pass"),
                     "fixes": [f"{x.get('row')}: {x.get('fix', '')}"[:160] for x in r.get("fixes", [])[:4]]})
    return q, r


def make(idea_id):
    s = script.write(idea_id)
    if s["fails"]:
        return {"status": "script-failed", **s}
    plan_path = Path(s["plan"])
    report = pipeline.render(plan_path)
    out = Path(report["final"]).parent
    q, r = check(out)
    rewrites = 0
    if not (q["pass"] and r["pass"]):
        feedback = [f"{f['row']}: {f['fix']}" for f in r["fixes"]] + [f"automatic check {k}: {g['detail']}" for k, g in q["gates"].items() if not g["pass"]]
        script.rewrite(plan_path, feedback)
        rewrites = 1
        report = pipeline.render(plan_path)
        q, r = check(out)
    plan = json.loads(plan_path.read_text())
    status = "awaiting-approval" if q["pass"] and r["pass"] else "needs-work"
    try:   # what this video teaches the next ones (frameflow.lessons)
        from frameflow import lessons
        lessons.distill(rout)
    except (Exception, SystemExit) as e:
        print(f"lessons: {e}")
    con = db()   # the row first: library.mark_used looks the video up
    con.execute("INSERT OR REPLACE INTO videos (id, idea_id, plan, out_dir, lane, title, qa_pass, review_total, review_pass, status, note, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (plan["id"], idea_id, str(plan_path), str(out), plan["lane"], plan["title"], int(q["pass"]), r["total"], int(r["pass"]),
                 status, f"{rewrites} rewrite(s)", now(), now()))
    con.execute("UPDATE ideas SET status='made' WHERE id=?", (idea_id,))
    con.commit()
    try:   # the asset library: record what was reused
        from frameflow import library
        library.mark_used(plan["id"])
    except (Exception, SystemExit) as e:
        print(f"library: {e}")
    return {"video": plan["id"], "status": status, "qa": q["pass"], "review": f"{r['total']}/12", "rewrites": rewrites,
            "seconds": report["seconds"], "final": report["final"]}


def make2(brief_path, lane="how-tech-works", out=None, skip_writer=False, skip_director=False, quality="looks"):
    """Quality v2: brief -> writer + director skills -> plan -> render -> qa -> review v2 -> awaiting approval."""
    from frameflow import direct
    with progress.step("script and storyboard (writer + director)"):
        d = direct.direct(brief_path, out, lane, skip_writer, skip_director)
    if d["errors"]:
        return {"status": "plan-invalid", **d}
    plan_path = Path(d["plan"])
    rounds = 0
    while True:
        with progress.step(f"round {rounds + 1}: render and check"):
            report = pipeline.render(plan_path, plan_path.parent / "render", quality)
            rout = Path(report["final"]).parent
            q, r = check(rout)
        weak_flow = r.get("scores", {}).get("flow", 2) < 2
        from frameflow import profiles   # automatic revisions allowed by the active profile (diet: 1; revisions can flatten the voice, L4)
        if (q["pass"] and r["pass"] and not weak_flow) or rounds >= profiles.pipeline()["max_auto_revisions"]:
            break
        if q["pass"] and r["pass"] and weak_flow:   # good enough overall but hard to follow: fix only the flow, keep the rest (lesson L4)
            r = {**r, "fixes": [x for x in r.get("fixes", []) if x["row"] == "flow"] or
                 [{"row": "flow", "fix": "The reviewer found the flow weak; smooth the seams between parts without changing the voice or jokes."}]}
        rounds += 1   # the review's fixes go back to the writer and the director, then a fresh render
        for name, g in q["gates"].items():   # failed automatic gates are the director's to fix too
            if not g["pass"] and name in ("events", "blank-frames", "rehooks", "length"):
                r.setdefault("fixes", []).append({"row": "pacing" if name != "rehooks" else "story", "fix": f"automatic check '{name}' failed: {g['detail']}"})
        (rout / f"review-round{rounds}.json").write_text(json.dumps(r, ensure_ascii=False, indent=1))
        with progress.step(f"automatic revision {rounds}: rewrite from the review", fixes=len(r.get("fixes", []))):
            d = direct.revise(brief_path, plan_path.parent, r, lane)
        if d["errors"]:
            break
    plan = json.loads(plan_path.read_text())
    status = "awaiting-approval" if q["pass"] and r["pass"] else "needs-work"
    progress.note(f"result: {status}", qa=q["pass"], review=f"{r['total']}/{r.get('max', 12)}", rounds=rounds + 1)
    try:   # what this video teaches the next ones (frameflow.lessons)
        from frameflow import lessons
        with progress.step("lessons for the next videos"):
            lessons.distill(rout)
    except (Exception, SystemExit) as e:
        print(f"lessons: {e}")
    con = db()   # the row first: the library looks the video up (before it, mark_used's SystemExit killed every fresh make)
    con.execute("INSERT OR REPLACE INTO videos (id, idea_id, plan, out_dir, lane, title, qa_pass, review_total, review_pass, status, note, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (plan["id"], None, str(plan_path), str(rout), plan["lane"], plan["title"], int(q["pass"]), r["total"], int(r["pass"]),
                 status, f"v2 from {brief_path}; {rounds} review round(s)", now(), now()))
    con.commit()
    try:   # the asset library: record what was reused, then take this video's reusable assets (only if it passed)
        from frameflow import library
        with progress.step("asset library"):
            library.mark_used(plan["id"])
            library.extract(plan["id"])
    except (Exception, SystemExit) as e:   # optional steps never cost the video
        print(f"library: {e}")
    from frameflow import vaultnote
    with progress.step("vault note"):
        vaultnote.safe_write(plan["id"])   # the video's page in the vault (facts, sources, review)
    return {"video": plan["id"], "status": status, "qa": {k: g["pass"] for k, g in q["gates"].items()},
            "review": f"{r['total']}/{r.get('max', 12)}", "seconds": report["seconds"], "final": report["final"]}


def set_status(video_id, status, note="", force=False):
    """force: Talha approves a video below the bar on purpose (its failures become lessons, see daily.approve)."""
    con = db()
    row = con.execute("SELECT * FROM videos WHERE id=?", (video_id,)).fetchone()
    if not row:
        raise SystemExit(f"no video {video_id}")
    if status == "approved" and not force and not (row["qa_pass"] and row["review_pass"]):
        raise SystemExit(f"{video_id} has not passed qa and review; fix it before approving")
    con.execute("UPDATE videos SET status=?, note=?, updated_at=? WHERE id=?", (status, note or row["note"], now(), video_id))
    con.commit()


def require_approved(video_id):
    row = db().execute("SELECT * FROM videos WHERE id=?", (video_id,)).fetchone()
    if not row:
        raise SystemExit(f"no video {video_id}")
    if row["status"] not in ("approved", "posted"):
        raise SystemExit(f"{video_id} is '{row['status']}': only videos Talha approved can be published (frameflow approve {video_id})")
    return row


def listing():
    return [dict(r) for r in db().execute("SELECT id, status, lane, review_total, qa_pass, title, note FROM videos ORDER BY created_at DESC")]
