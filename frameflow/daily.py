"""Daily automation: one run per posting day, moved along by the Telegram bot (vault Decisions/Daily Automation.md).

    python -m frameflow.daily scout [--day YYYY-MM-DD]     topic card for a posting day (default: tomorrow)
    python -m frameflow.daily make <day>                   brief -> make2 -> video card       (spawned by the bot)
    python -m frameflow.daily revise <day>                 Talha's notes -> re-render -> card  (spawned by the bot)
    python -m frameflow.daily post <day>                   pack -> YouTube, Instagram, Facebook -> links card
    python -m frameflow.daily tick                         what the bot runs every 30 s: 20:00 scout, 22:30 auto-pick, 11:30 posts
    python -m frameflow.daily status

States: topic-sent -> picked -> making -> video-sent -> (revising -> making) -> queued -> posting -> posted,
or skipped / rejected / failed. Long steps run as their own processes (logs/daily-<day>-<step>.log), so the bot keeps
answering while a video renders. Nothing is ever posted without Talha's Approve.
"""
import argparse
import datetime as dt
import json
import re
import os
import sqlite3
import subprocess
import sys
import traceback
from pathlib import Path

from frameflow import telegram

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "frameflow.db"
LOGS = ROOT / "logs"

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
  day TEXT PRIMARY KEY, lane TEXT, state TEXT, options TEXT, pick INTEGER, story TEXT, brief TEXT, video_id TEXT,
  revisions INTEGER DEFAULT 0, notes TEXT, topic_msg INTEGER, video_msg INTEGER, approved_at TEXT, post_at TEXT,
  links TEXT, job_pid INTEGER, log TEXT DEFAULT '', created_at TEXT, updated_at TEXT, posted_at TEXT, stats_at TEXT);
CREATE TABLE IF NOT EXISTS weekly (week TEXT PRIMARY KEY, sent_at TEXT);
"""


def cfg():
    return telegram.config()


def db():
    DB.parent.mkdir(exist_ok=True)
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    cols = {r[1] for r in con.execute("PRAGMA table_info(runs)")}
    for c in ("posted_at", "stats_at"):   # added after the first runs table
        if c not in cols:
            con.execute(f"ALTER TABLE runs ADD COLUMN {c} TEXT")
    return con


def now():
    return dt.datetime.now().replace(microsecond=0)


def at(day, hhmm):
    h, m = map(int, hhmm.split(":"))
    return dt.datetime.combine(dt.date.fromisoformat(day), dt.time(h, m))


def get(day):
    r = db().execute("SELECT * FROM runs WHERE day=?", (day,)).fetchone()
    return dict(r) if r else None


def update(day, **kw):
    con = db()
    note = kw.pop("note", None)
    if note:
        kw["log"] = (get(day) or {}).get("log", "") + f"{now().isoformat()} {note}\n"
    kw["updated_at"] = now().isoformat()
    con.execute(f"UPDATE runs SET {', '.join(k + '=?' for k in kw)} WHERE day=?", (*kw.values(), day))
    con.commit()


def lane_for(day):
    c = cfg()
    lanes, start = c["lanes"], c["rotation_start"]
    offset = (dt.date.fromisoformat(day) - dt.date.fromisoformat(start["date"])).days
    return lanes[(lanes.index(start["lane"]) + offset) % len(lanes)]


def lane_name(lane):
    return cfg()["lane_names"].get(lane, lane)


def spawn(step, day):
    """Run a long step in its own process; the bot only watches its state."""
    LOGS.mkdir(exist_ok=True)
    log = open(LOGS / f"daily-{day}-{step}.log", "a")
    p = subprocess.Popen(["uv", "run", "python", "-m", "frameflow.daily", step, day], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                         start_new_session=True)
    update(day, job_pid=p.pid, note=f"spawned {step} (pid {p.pid})")
    return p.pid


def job_alive(run):
    pid = run.get("job_pid")
    if not pid:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


# ---- scout: tomorrow's lane, 3 stories, topic card ----

def options_for(lane, n):
    from frameflow import ideas
    try:
        ideas.collect()
        ideas.rank()
    except Exception as e:   # a dead feed or a model hiccup shouldn't stop the card: use what is already ranked
        print(f"collect/rank: {e}", file=sys.stderr)
    con = ideas.db()
    used = {r["story"] for r in db().execute("SELECT story FROM runs WHERE story IS NOT NULL")}
    rows = con.execute("SELECT id, title, url, summary, angle, hook, score, lane FROM ideas WHERE status='new' AND score IS NOT NULL "
                       "AND fetched_at >= ? ORDER BY (lane=?) DESC, score DESC LIMIT 40",
                       ((now() - dt.timedelta(days=3)).isoformat(), lane)).fetchall()
    out = []
    for r in rows:
        if r["url"] in used or any(o["url"] == r["url"] for o in out):
            continue
        out.append({"idea": r["id"], "title": r["title"], "url": r["url"], "summary": r["summary"] or "", "angle": r["angle"] or "",
                    "hook": r["hook"] or "", "score": r["score"], "lane": r["lane"]})
        if len(out) == n:
            break
    return out


def source_of(url):
    from frameflow import build
    return build.source_name(url)


def scout(day=None):
    day = day or (now().date() + dt.timedelta(days=1)).isoformat()
    if get(day) and get(day)["state"] not in ("failed",):
        return get(day)
    lane = lane_for(day)
    opts = options_for(lane, cfg()["options"])
    con = db()
    con.execute("INSERT OR REPLACE INTO runs (day, lane, state, options, created_at, updated_at, log) VALUES (?,?,?,?,?,?,?)",
                (day, lane, "topic-sent", json.dumps(opts, ensure_ascii=False), now().isoformat(), now().isoformat(), ""))
    con.commit()
    when = dt.date.fromisoformat(day).strftime("%A %d %b")
    lines = [f"Tomorrow's video ({when}) · lane: {lane_name(lane)}", "Pick a story, or paste a link of your own.", ""]
    for i, o in enumerate(opts, 1):
        title, _, outlet = o["title"].rpartition(" - ") if " - " in o["title"] else (o["title"], "", "")
        lines += [f"{i}. {title or o['title']}", f"   Source: {outlet or source_of(o['url'])}",
                  f"   Angle: {o['angle']}" if o["angle"] else "", f"   Hook: {o['hook']}" if o["hook"] else "", ""]
    lines.append(f"No answer by {cfg()['auto_pick_at']} and I'll make story 1.")
    buttons = [[(str(i), f"pick:{day}:{i}") for i in range(1, len(opts) + 1)], [("Skip this day", f"skip:{day}")]]
    msg = telegram.send("\n".join(l for l in lines if l is not None), buttons)
    update(day, topic_msg=msg, note=f"topic card sent ({len(opts)} options, lane {lane})")
    return get(day)


def pick(day, n=None, url=None, auto=False):
    run = get(day)
    if not run or run["state"] != "topic-sent":
        return run
    opts = json.loads(run["options"] or "[]")
    if url:
        story = {"title": "", "url": url, "summary": "", "lane": run["lane"]}
        label = f"your link {url}"
    else:
        story = opts[(n or 1) - 1]
        label = f"story {n or 1}: {story['title']}"
    update(day, state="picked", pick=n or 0, story=story["url"], options=json.dumps({"list": opts, "chosen": story}, ensure_ascii=False),
           note=f"picked {label}{' (auto)' if auto else ''}")
    if run.get("topic_msg"):
        telegram.clear_buttons(run["topic_msg"])
    telegram.send(f"{'No pick by ' + cfg()['auto_pick_at'] + ', so I took' if auto else 'Got it:'} {label}.\n"
                  "Researching and making the video now. I'll send it here for your approval.")
    spawn("make", day)


def chosen(run):
    o = json.loads(run["options"] or "{}")
    return o.get("chosen") if isinstance(o, dict) else None


# ---- make / revise: the video, then the approval card ----

def make(day):
    from frameflow import brief, videos
    run = get(day)
    story = chosen(run)
    if run.get("brief") and Path(run["brief"]).exists():   # a retry reuses the research it already did
        path = Path(run["brief"])
        update(day, state="making", note=f"reusing brief {path.name}; make2 started")
    else:
        update(day, state="making", note="making: research brief")
        path = brief.build(story["url"], story.get("title", ""), run["lane"], story.get("summary", ""))
        update(day, brief=str(path), note=f"brief {path.name}; make2 started")
    r = videos.make2(str(path), run["lane"])
    if r.get("status") == "plan-invalid":
        raise RuntimeError(f"plan invalid after the director's fix: {r.get('errors')}")
    update(day, video_id=r["video"], note=f"made {r['video']}: {r['status']}, review {r['review']}")
    video_card(day)


def preview(final, out):
    """A Telegram-sized copy (bots can send up to 50 MB): 720 px wide, same length and sound."""
    from frameflow import media
    media.ffmpeg("-i", str(final), "-vf", "scale=720:-2", "-c:v", "libx264", "-preset", "veryfast", "-crf", "28",
                 "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(out))
    return out


def video_card(day):
    from frameflow import videos
    run = get(day)
    row = videos.db().execute("SELECT * FROM videos WHERE id=?", (run["video_id"],)).fetchone()
    out = Path(row["out_dir"])
    rep = json.loads((out / "report.json").read_text())
    rev = json.loads((out / "review.json").read_text()) if (out / "review.json").exists() else {}
    qa = json.loads((out / "qa.json").read_text()) if (out / "qa.json").exists() else {}
    gates = qa.get("gates", {})
    failed = [k for k, g in gates.items() if not g.get("pass")]
    prev = preview(out / "final.mp4", out / "preview-720.mp4")
    if (out / "cover.png").exists():
        telegram.send_file("photo", out / "cover.png", caption="Cover / thumbnail")
    fixes = "\n".join(f"- {f['row']}: {f['fix'][:180]}" for f in rev.get("fixes", [])[:3])
    text = (f"{row['title']}\n{rep['seconds']:.0f} s · review {rev.get('total', '?')}/{rev.get('max', 20)} "
            f"{'PASS' if rev.get('pass') else 'below the bar'} · QA {'all pass' if not failed else 'failed: ' + ', '.join(failed)}\n"
            + (f"\nReviewer's remaining notes:\n{fixes}\n" if fixes else "")
            + f"\nApprove before {cfg()['post_at']} and it posts at {cfg()['post_at']}; later approval posts right away.")
    approvable = bool(row["qa_pass"] and row["review_pass"])
    buttons = [[("✅ Approve", f"approve:{day}")] if approvable else [],
               [("✏️ Revise", f"revise:{day}"), ("❌ Reject", f"reject:{day}")]]
    msg = telegram.send_file("video", prev, caption=text[:1024], buttons=[b for b in buttons if b],
                             extra={"supports_streaming": "true", "width": 720, "height": 1280})
    if len(text) > 1024:
        telegram.send(text)
    update(day, state="video-sent", video_msg=msg, note=f"video card sent (approvable: {approvable})")


def revise(day):
    from frameflow import direct, videos, pipeline
    run = get(day)
    row = videos.db().execute("SELECT * FROM videos WHERE id=?", (run["video_id"],)).fetchone()
    notes = (run["notes"] or "").strip()
    rev_file = Path(row["out_dir"]) / "review.json"
    if re.search(r"review", notes, re.I) and len(notes) < 80 and rev_file.exists():   # "use the reviewer's notes"
        fixes = json.loads(rev_file.read_text()).get("fixes", [])
        notes = "\n".join(f"{x['row']}: {x['fix']}" for x in fixes) or notes
        update(day, note="using the reviewer's notes as the revision notes")
    update(day, state="making", note=f"revising with Talha's notes: {notes[:200]}")
    try:
        from frameflow import lessons
        lessons.distill(Path(row["out_dir"]), notes=notes, source=f"{run['video_id']} (Talha's revise notes)")
    except Exception as e:
        print(f"lessons: {e}")
    fixes = [{"row": "story", "fix": f"Talha (the channel owner) asks: {notes}"},
             {"row": "visual_storytelling", "fix": f"Talha (the channel owner) asks: {notes}"}]
    d = direct.revise(run["brief"], Path(row["plan"]).parent, {"fixes": fixes}, run["lane"])
    if d["errors"]:
        raise RuntimeError(f"revised plan invalid: {d['errors']}")
    report = pipeline.render(Path(d["plan"]), Path(d["plan"]).parent / "render", "looks")
    q, r = videos.check(Path(report["final"]).parent)
    con = videos.db()
    con.execute("UPDATE videos SET qa_pass=?, review_total=?, review_pass=?, status=?, note=?, updated_at=? WHERE id=?",
                (int(q["pass"]), r["total"], int(r["pass"]), "awaiting-approval" if q["pass"] and r["pass"] else "needs-work",
                 f"v2 revised from Talha's notes (round {run['revisions']})", videos.now(), run["video_id"]))
    con.commit()
    video_card(day)


def reflow(day):
    """Re-review a made video with the current review (flow row included); weak flow -> a flow-only revision -> new card."""
    from frameflow import direct, pipeline, review, videos
    run = get(day)
    row = videos.db().execute("SELECT * FROM videos WHERE id=?", (run["video_id"],)).fetchone()
    if run.get("video_msg"):
        telegram.clear_buttons(run["video_msg"])
    telegram.send("Re-checking this video's flow with the new review before you approve it. A fresh card follows.")
    update(day, state="making", note="reflow: re-review with the flow row")
    r = review.run(Path(row["out_dir"]))
    flow = r["scores"].get("flow", 2)
    update(day, note=f"reflow review {r['total']}/{r['max']}, flow {flow}")
    if flow < 2:
        fixes = [x for x in r.get("fixes", []) if x["row"] == "flow"] or [{"row": "flow", "fix": "Smooth the seams between parts."}]
        d = direct.revise(run["brief"], Path(row["plan"]).parent, {"fixes": fixes}, run["lane"])
        if d["errors"]:
            raise RuntimeError(f"revised plan invalid: {d['errors']}")
        report = pipeline.render(Path(d["plan"]), Path(d["plan"]).parent / "render", "looks")
        q, r = videos.check(Path(report["final"]).parent)
        con = videos.db()
        con.execute("UPDATE videos SET qa_pass=?, review_total=?, review_pass=?, status=?, note=?, updated_at=? WHERE id=?",
                    (int(q["pass"]), r["total"], int(r["pass"]), "awaiting-approval" if q["pass"] and r["pass"] else "needs-work",
                     f"v2 flow revision (review {r['total']}/{r['max']}, flow {r['scores'].get('flow')})", videos.now(), run["video_id"]))
        con.commit()
        update(day, note=f"after flow revision: review {r['total']}/{r['max']}, flow {r['scores'].get('flow')}")
    else:
        con = videos.db()
        con.execute("UPDATE videos SET review_total=?, review_pass=?, updated_at=? WHERE id=?", (r["total"], int(r["pass"]), videos.now(), run["video_id"]))
        con.commit()
    video_card(day)


def approve(day):
    from frameflow import videos
    run = get(day)
    videos.set_status(run["video_id"], "approved", "approved on Telegram")
    slot = at(day, cfg()["post_at"])
    t = now()
    post_at = slot if t < slot else t
    update(day, state="queued", approved_at=t.isoformat(), post_at=post_at.isoformat(), note=f"approved; post at {post_at}")
    if run.get("video_msg"):
        telegram.clear_buttons(run["video_msg"])
    telegram.send(f"Approved. Posting {'at ' + slot.strftime('%H:%M on %a %d %b') if post_at == slot else 'now'} "
                  "on YouTube Shorts, Instagram and Facebook.")


# ---- post ----

def post(day):
    from frameflow import publish
    run = get(day)
    update(day, state="posting", note="posting")
    if not (Path(publish.videos.db().execute("SELECT out_dir FROM videos WHERE id=?", (run["video_id"],)).fetchone()["out_dir"]) / "publish.json").exists():
        publish.publish(run["video_id"])
    results = publish.upload(run["video_id"], tuple(cfg()["platforms"]))
    links = {k: v.get("url") for k, v in results.items() if isinstance(v, dict) and v.get("url")}
    missing = [p for p in cfg()["platforms"] if p not in links]
    update(day, links=json.dumps(links), state="posted" if not missing else "failed", posted_at=now().isoformat(),
           note=f"posted: {links}" + (f"; missing {missing}" if missing else ""))
    lines = ["Live:"] + [f"{k.capitalize()}: {v}" for k, v in links.items()]
    if missing:
        lines.append(f"Not posted: {', '.join(missing)} (I'll look into it; the details are in the log).")
    telegram.send("\n".join(lines))


# ---- tick: called by the bot every 30 s ----

def tick():
    c = cfg()
    t = now()
    tomorrow = (t.date() + dt.timedelta(days=1)).isoformat()
    if not c.get("paused") and t >= at(t.date().isoformat(), c["topic_card_at"]) and not get(tomorrow):
        spawn_scout(tomorrow)
    for run in stats_due():
        update(run["day"], stats_at=t.isoformat())
        try:
            from frameflow import stats48
            stats48.collect(run["video_id"])
        except Exception as e:
            print(f"stats {run['day']}: {e}", file=sys.stderr)
    if t.weekday() == 6 and t.hour >= 21:
        weekly()
    for run in [dict(r) for r in db().execute("SELECT * FROM runs WHERE state NOT IN ('posted','skipped','rejected')")]:
        day = run["day"]
        if run["state"] == "waiting-limit":
            m = re.search(r"retry at (\S+) \(step (\w+)\)", (run.get("log") or "").strip().splitlines()[-1])
            if m and t >= dt.datetime.fromisoformat(m.group(1)):
                update(day, state="making" if m.group(2) != "post" else "posting", note=f"usage limit reset: re-running {m.group(2)}")
                spawn(m.group(2), day)
            continue
        if run["state"] == "topic-sent":
            deadline = at((dt.date.fromisoformat(day) - dt.timedelta(days=1)).isoformat(), c["auto_pick_at"])
            if t >= deadline and json.loads(run["options"] or "[]"):
                pick(day, 1, auto=True)
        elif run["state"] == "queued" and run["post_at"] and t >= dt.datetime.fromisoformat(run["post_at"]):
            spawn("post", day)
            update(day, state="posting")
        elif run["state"] in ("making", "posting", "picked") and not job_alive(run) and run.get("job_pid") \
                and (now() - dt.datetime.fromisoformat(run["updated_at"])).total_seconds() > 60:
            # usually the laptop shut down mid-job (it runs 10:00-17:00): start the step again once, then ask
            restarts = (run.get("log") or "").count("restarted after stop")
            step = "post" if run["state"] == "posting" else ("revise" if run.get("notes") and run.get("video_id") else "make")
            if restarts < 2:
                update(day, note=f"restarted after stop ({run['state']})")
                spawn(step, day)
                telegram.send(f"The {day} video's {step} step had stopped (laptop off?). Starting it again now.")
            else:
                update(day, state="failed", job_pid=None, note=f"job stopped while {run['state']} (twice)")
                telegram.send(f"The {step} step for {day} stopped twice. Log: logs/daily-{day}-*.log. Reply /retry to try again.")


def stats_due():
    """Posted runs whose 48 hours are up and whose stats card hasn't gone out."""
    cutoff = (now() - dt.timedelta(hours=48)).isoformat()
    return [dict(r) for r in db().execute("SELECT * FROM runs WHERE posted_at IS NOT NULL AND posted_at <= ? AND stats_at IS NULL", (cutoff,))]


def weekly():
    """Sunday evening: lessons that held for 3+ videos are offered for promotion; stale ones retire; a short report."""
    from frameflow import lessons
    week = now().strftime("%G-W%V")
    con = db()
    if con.execute("SELECT 1 FROM weekly WHERE week=?", (week,)).fetchone():
        return
    con.execute("INSERT INTO weekly VALUES (?,?)", (week, now().isoformat()))
    con.commit()
    gone = lessons.retire_stale()
    posted = con.execute("SELECT COUNT(*) FROM runs WHERE state='posted' AND posted_at >= ?", ((now() - dt.timedelta(days=7)).isoformat(),)).fetchone()[0]
    rows = lessons.load()
    telegram.send(f"Week {week}: {posted} video(s) posted. Lessons: {sum(r['status'] == 'active' for r in rows)} active, "
                  f"{sum(r['status'] == 'promoted' for r in rows)} made permanent" + (f", {len(gone)} retired ({', '.join(gone)})." if gone else "."))
    for r in lessons.promotable():
        telegram.send(f"Lesson {r['id']} ({r['area']}) helped in {r['helped']} videos:\n\"{r['text']}\"\nMake it a permanent house rule?",
                      [[("✅ Make permanent", f"promote:{r['id']}"), ("Keep testing", f"keep:{r['id']}")]])


def limit_reset(message):
    """'You've hit your session limit · resets 8:20pm (...)' -> the ISO time to retry (2 minutes after the reset)."""
    m = re.search(r"limit.*?resets\s+(\d{1,2})(?::(\d{2}))?\s*([ap]m)", message, re.I)
    if not m:
        return None
    h, mi, ap = int(m.group(1)), int(m.group(2) or 0), m.group(3).lower()
    h = h % 12 + (12 if ap == "pm" else 0)
    when = dt.datetime.combine(dt.date.today(), dt.time(h, mi)) + dt.timedelta(minutes=2)
    if when < now() - dt.timedelta(hours=1):
        when += dt.timedelta(days=1)
    return when.replace(microsecond=0).isoformat()


def last_step(run):
    """The step that was running when a run stopped (from its log)."""
    for line in reversed((run.get("log") or "").splitlines()):
        m = re.search(r"\(step (\w+)\)|(\w+) failed:|spawned (\w+)", line)
        if m:
            return next(g for g in m.groups() if g)
    return "make"


def spawn_scout(day):
    con = db()
    con.execute("INSERT OR IGNORE INTO runs (day, lane, state, created_at, updated_at, log) VALUES (?,?,?,?,?,?)",
                (day, lane_for(day), "scouting", now().isoformat(), now().isoformat(), ""))
    con.commit()
    spawn("scout", day)


def status_text():
    rows = [dict(r) for r in db().execute("SELECT * FROM runs ORDER BY day DESC LIMIT 4")]
    if not rows:
        return "No runs yet. The first topic card comes at " + cfg()["topic_card_at"] + "."
    out = [f"Paused: {'yes' if cfg().get('paused') else 'no'}"]
    for r in rows:
        story = chosen(r) or {}
        out.append(f"{r['day']} · {lane_name(r['lane'])} · {r['state']}" + (f" · {story.get('title') or story.get('url', '')}"[:120] if story else "")
                   + (f" · post at {r['post_at'][11:16]}" if r["state"] == "queued" and r["post_at"] else ""))
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description="Frameflow daily automation")
    ap.add_argument("step", choices=["scout", "make", "revise", "reflow", "post", "tick", "status"])
    ap.add_argument("day", nargs="?")
    ap.add_argument("--day", dest="day_opt")
    a = ap.parse_args()
    day = a.day or a.day_opt
    try:
        if a.step == "scout":
            if day and get(day) and get(day)["state"] == "scouting":   # spawned by the bot: replace the placeholder row
                db().execute("DELETE FROM runs WHERE day=?", (day,)).connection.commit()
            print(json.dumps(scout(day), indent=1, default=str)[:2000])
        elif a.step == "make":
            make(day)
        elif a.step == "revise":
            revise(day)
        elif a.step == "reflow":
            reflow(day)
        elif a.step == "post":
            post(day)
        elif a.step == "tick":
            tick()
        else:
            print(status_text())
    except Exception as e:
        reset = limit_reset(str(e))
        if day and reset and get(day):   # Claude usage limit: not a failure, a wait; tick re-runs the step at the reset time
            update(day, state="waiting-limit", job_pid=None, post_at=get(day).get("post_at"), note=f"{a.step} paused by the usage limit; retry at {reset} (step {a.step})")
            try:
                telegram.send(f"Paused by the Claude usage limit. I'll carry on by myself at {reset[11:16]}.")
            except Exception:
                pass
            sys.exit(0)
        if day and a.step in ("make", "revise", "reflow", "post", "scout") and get(day):
            update(day, state="failed", job_pid=None, note=f"{a.step} failed: {e}")
            try:
                telegram.send(f"The {a.step} step for {day} failed: {str(e)[:300]}\nReply /retry to try again.")
            except Exception:
                pass
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
