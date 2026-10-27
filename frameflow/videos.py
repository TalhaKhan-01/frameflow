"""Video register: every rendered video, its checks, and Talha's approval. Nothing is published without approval.

    frameflow make2 <brief.json>         the studio board (frameflow.board) -> awaiting approval or needs-work
    frameflow status                     list videos and their state
    frameflow approve <video-id>         Talha approves (only after watching final.mp4)
    frameflow reject <video-id> <why>    send back with a reason
"""
import datetime as dt
import json
from pathlib import Path

from frameflow import ideas, progress

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


def make2(brief_path, lane="how-tech-works", out=None, skip_writer=False, skip_director=False, quality="looks"):
    """The Studio board (frameflow.board): desks and gates before one delivery render -> QA -> final check -> awaiting approval."""
    from frameflow import board
    b = board.make(brief_path, lane, out, skip_writer, skip_director, quality)
    if b["status"] == "plan-invalid":
        return b
    plan_path, rout, report, q, r = Path(b["plan"]), Path(b["render"]), b["report"], b["qa"], b["review"]
    plan = json.loads(plan_path.read_text())
    status = "awaiting-approval" if q["pass"] and r["pass"] else "needs-work"
    progress.note(f"result: {status}", qa=q["pass"], review=f"{r['total']}/{r.get('max', 12)}", animatic=b["animatic_total"],
                  fix_rounds_before_render=b["rounds"], delivery_renders=1)
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
                 status, f"studio board from {brief_path}; fix rounds before the render: timing {b['rounds']['timing']}, animatic "
                 f"{b['rounds']['animatic']}; one delivery render", now(), now()))
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
    try:   # the voice's real speaking rate -> the bar -> the writer's and director's next estimates
        from frameflow import bar
        bar.calibrate()
    except (Exception, SystemExit) as e:
        print(f"calibrate: {e}")
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
