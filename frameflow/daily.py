"""Daily automation: one run per posting day, moved along by the Telegram bot (vault Decisions/Daily Automation.md).

    python -m frameflow.daily scout [--day YYYY-MM-DD]     topic card for a posting day (default: tomorrow)
    python -m frameflow.daily make <day>                   brief -> the board -> video card     (spawned by the bot)
    python -m frameflow.daily order <day>                  Talha's Revise words -> showrunner change order (Go / Change it / Cancel)
    python -m frameflow.daily revise <day>                 the confirmed change order -> only its stages -> card
    python -m frameflow.daily post <day>                   pack -> YouTube, Instagram, Facebook -> links card
    python -m frameflow.daily tick                         what the bot runs every 30 s: 14:00 scout, 15:00 auto-pick, 11:30 posts
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

from frameflow import progress, telegram

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
    for c in ("posted_at", "stats_at", "revise_picks", "order_file", "order_msg"):   # added after the first runs table
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
    try:   # an exited job its parent hasn't reaped is a zombie: os.kill still succeeds (26 Oct: a dead make sat at 'making')
        return Path(f"/proc/{pid}/stat").read_text().split(") ")[1][0] != "Z"
    except (OSError, IndexError):
        return False


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
    if get(day) and get(day)["state"] not in ("failed", "scouting"):
        return get(day)
    from frameflow import showdesk
    if showdesk.enabled():   # The Daily Habit show: candidates ranked by virality, Talha ticks the episode's stories
        return showdesk.scout(day)
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
    if isinstance(o, dict) and o.get("show"):   # the show: several stories; the run reads as its episode
        c = o.get("chosen") or []
        return {"title": f"The Daily Habit Ep {o.get('episode')}: " + " · ".join(x["headline"] for x in c), "url": c[0]["url"]} if c else None
    return o.get("chosen") if isinstance(o, dict) else None


# ---- make / revise: the video, then the approval card ----

def make(day):
    from frameflow import brief, showdesk, videos
    run = get(day)
    if showdesk.is_show(run):   # the episode: research every story, rundown script, voice, sound, render, QA, card
        from frameflow import show
        return show.make_day(day)
    story = chosen(run)
    if run.get("brief") and Path(run["brief"]).exists():   # a retry reuses the research it already did
        path = Path(run["brief"])
        update(day, state="making", note=f"reusing brief {path.name}; make2 started")
    else:
        update(day, state="making", note="making: research brief")
        with progress.step("research brief", story=story.get("title") or story["url"]) as info:
            path = brief.build(story["url"], story.get("title", ""), run["lane"], story.get("summary", ""))
            info["brief"] = path.name
        with progress.step("fact-check the brief", desk="factcheck") as info:
            fc = brief.factcheck(path)
            info.update({"pass": fc["pass"], "summary": fc["summary"]})
        update(day, brief=str(path), note=f"brief {path.name}; make2 started")
    with progress.step("make video") as info:
        r = videos.make2(str(path), run["lane"])
        info.update({k: r.get(k) for k in ("video", "status", "review", "seconds")})
    if r.get("status") == "plan-invalid":
        raise RuntimeError(f"plan invalid after the director's fix: {r.get('errors')}")
    update(day, video_id=r["video"], note=f"made {r['video']}: {r['status']}, review {r['review']}")
    with progress.step("send video card to Telegram"):
        video_card(day)
    try:   # the day's card post, from the same brief (no second topic choice, little extra cost)
        from frameflow import cards
        with progress.step("make card post (carousel)"):
            cards.make_for_day(day, path)
        update(day, note="card post made")
    except Exception as e:
        update(day, note=f"card post failed: {str(e)[:200]}")
    try:   # one render folder per video: scratch, earlier rounds and the animatic's draft go now, not after 48 h
        from frameflow import cleanup
        with progress.step("storage cleanup (rounds level)", desk="analyst") as info:
            info.update(cleanup.clean(r["video"]))
    except (Exception, SystemExit) as e:
        update(day, note=f"cleanup skipped: {str(e)[:120]}")


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
    # Talha decides: Approve is always offered; below the bar it says so and the failures are listed above.
    approvable = bool(row["qa_pass"] and row["review_pass"])
    if not approvable:
        why = [f"- {k}: {gates[k].get('detail', '')[:150]}" for k in failed] + ([] if rev.get("pass") else ["- review below the bar"])
        text = text.replace("\nApprove before", "\nBelow the bar:\n" + "\n".join(why) + "\n\nApprove before", 1)
    buttons = [[("✅ Approve" if approvable else "⚠️ Approve anyway", f"approve:{day}")],
               [("✏️ Revise", f"revise:{day}"), ("❌ Reject", f"reject:{day}")]]
    msg = telegram.send_file("video", prev, caption=text[:1024], buttons=[b for b in buttons if b],
                             extra={"supports_streaming": "true", "width": 720, "height": 1280})
    if len(text) > 1024:
        telegram.send(text)
    post_text_card(day, row)
    update(day, state="video-sent", video_msg=msg, note=f"video card sent (approvable: {approvable})")


def post_text_card(day, row):
    """The post text goes for approval with the video (P25, Talha 29 Oct): the social-caption pack is written now, not
    at posting time, and Approve covers it. A failure here only means the pack is written at posting time as before."""
    from frameflow import publish
    out = Path(row["out_dir"])
    try:
        if not (out / "publish.json").exists():
            publish.publish(row["id"], require=False)
        p = json.loads((out / "publish.json").read_text())
        telegram.send("📝 Post text (approved together with the video; Revise in your words to change it):\n\n"
                      f"YouTube title: {p['yt_title']}\n\nYouTube description:\n{p['yt_description'][:900]}\n\n"
                      f"Instagram / Facebook caption:\n{p['ig_caption'][:1500]}\n\nPinned comment: {p['pinned_comment']}")
        update(day, note="post text sent with the video card")
    except (Exception, SystemExit) as e:
        update(day, note=f"post text not sent ({str(e)[:150]}): it is written at posting time")


def order(day):
    """The showrunner's change order for Talha's Revise words and ticked issues, sent for Go / Change it / Cancel."""
    from frameflow import producer, showdesk
    run = get(day)
    if showdesk.is_show(run):   # a show episode: the notes go straight to the writer (no board change order)
        picks = json.loads(run.get("revise_picks") or "[]")
        found = producer.issues(day)
        notes = "\n".join([f"- {(run.get('notes') or '').strip()}"] if (run.get("notes") or "").strip() else []) + \
                "".join(f"\n- {found[i]}" for i in picks if i < len(found))
        path = ROOT / "out" / "show" / f"order-{day}.txt"
        path.write_text(notes.strip())
        msg = telegram.send(f"I'll rewrite the episode with these notes, then re-voice and re-render it (about 15 min):\n{notes.strip()[:3000]}",
                            [[("Go", f"ordgo:{day}"), ("Change it", f"ordchg:{day}"), ("Cancel", f"ordno:{day}")]])
        return update(day, state="order-sent", order_file=str(path), order_msg=str(msg), note="show revise notes sent for Go")
    update(day, state="ordering", note="showrunner: reading the revise request")
    o = producer.order(day)
    msg = telegram.send(producer.message(o), [[("Go", f"ordgo:{day}"), ("Change it", f"ordchg:{day}"), ("Cancel", f"ordno:{day}")]])
    update(day, state="order-sent", order_msg=str(msg), note="change order sent")


def revise(day):
    """Every revise is a confirmed change order (frameflow.producer): Talha's words become an order he says Go to, and only
    its stages re-run. The older notes-straight-to-a-re-render path went with the studio board (27 Oct cleanup)."""
    run = get(day)
    if not (run.get("order_file") and Path(run["order_file"]).exists()):
        raise RuntimeError("no confirmed change order: Revise starts with the showrunner (Telegram Revise, or the control panel)")
    return revise_order(day)


def revise_order(day):
    from frameflow import producer, showdesk, videos
    run = get(day)
    if showdesk.is_show(run):
        from frameflow import show
        show.revise(day, Path(run["order_file"]).read_text())
        update(day, order_file=None, revise_picks=None, note="show revise done")
        with progress.step("send video card to Telegram"):
            video_card(day)
        return
    q, r = producer.apply(day)
    con = videos.db()
    con.execute("UPDATE videos SET qa_pass=?, review_total=?, review_pass=?, status=?, note=?, updated_at=? WHERE id=?",
                (int(q["pass"]), r["total"], int(r["pass"]), "awaiting-approval" if q["pass"] and r["pass"] else "needs-work",
                 f"revised by change order {Path(run['order_file']).stem} (round {run['revisions']})", videos.now(), run["video_id"]))
    con.commit()
    update(day, order_file=None, revise_picks=None, note=f"change order done: review {r['total']}/{r.get('max')}, QA {'pass' if q['pass'] else 'fail'}")
    with progress.step("send video card to Telegram"):
        video_card(day)


def approve(day):
    from frameflow import videos
    run = get(day)
    row = videos.db().execute("SELECT * FROM videos WHERE id=?", (run["video_id"],)).fetchone()
    below = not (row["qa_pass"] and row["review_pass"])
    videos.set_status(run["video_id"], "approved", "approved anyway on Telegram (below the bar)" if below else "approved on Telegram",
                      force=below)
    slot = at(day, cfg()["post_at"])
    t = now()
    post_at = slot if t < slot else t
    update(day, state="queued", approved_at=t.isoformat(), post_at=post_at.isoformat(), note=f"approved; post at {post_at}")
    if run.get("video_msg"):
        telegram.clear_buttons(run["video_msg"])
    telegram.send(f"Approved. Posting {'at ' + slot.strftime('%H:%M on %a %d %b') if post_at == slot else 'now'} "
                  "on YouTube Shorts, Instagram and Facebook.")
    if below:
        keep_for_next(day, Path(row["out_dir"]))


def keep_for_next(day, render_dir):
    """Approved anyway: the failed checks and the reviewer's notes become lessons for the next videos."""
    try:
        from frameflow import lessons
        r = lessons.distill(render_dir, source=f"{get(day)['video_id']} (approved anyway)",
                            notes="Talha approved this video anyway although it is below the bar. "
                                  "Make its failed checks and the reviewer's notes into lessons so the next videos avoid them.")
        rows = {x["id"]: x for x in lessons.load()}
        kept = [f"- {rows[i]['text']}" for i in r.get("reinforce", []) if i in rows]
        kept += [f"- {x['text']}" for x in r.get("new", [])]
        update(day, note=f"approved anyway: {len(r.get('new', []))} new lessons, {len(r.get('reinforce', []))} reinforced")
        telegram.send("Kept for the next video:\n" + ("\n".join(kept)[:3500] or "- nothing new (already covered by existing lessons)"))
    except Exception as e:
        update(day, note=f"approved anyway, but saving lessons failed: {e}")
        telegram.send(f"Approved, but I couldn't save its notes as lessons ({str(e)[:200]}). /retry won't redo this; tell me in chat.")


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
    unconfirmed = [k for k, v in results.items() if isinstance(v, dict) and v.get("unconfirmed")]
    lines = ["Live:"] + [f"{k.capitalize()}: {v}" for k, v in links.items() if k not in unconfirmed]
    if unconfirmed:   # accepted by the site, link not found: counted as posted (a retry would post twice); Talha checks
        lines.append("Posted, but I couldn't confirm the link (check it here): "
                     + "; ".join(f"{k.capitalize()}: {links[k]}" for k in unconfirmed))
        update(day, note=f"posted, link unconfirmed: {unconfirmed}")
    if missing:
        lines.append(f"Not posted: {', '.join(missing)} (I'll look into it; the details are in the log).")
    telegram.send("\n".join(lines))
    from frameflow import webexport
    update(day, note=f"studio: {webexport.refresh(f'posted {day}')}")


# ---- tick: called by the bot every 30 s ----

def tick():
    c = cfg()
    t = now()
    tomorrow = (t.date() + dt.timedelta(days=1)).isoformat()
    if not c.get("paused") and t >= at(t.date().isoformat(), c["topic_card_at"]) and not get(tomorrow):
        spawn_scout(tomorrow)
    try:   # card posts approved for today's slot; a daily card follows its Short's post time when that moves
        from frameflow import cards
        for cr in [dict(x) for x in cards.db().execute("SELECT * FROM card_runs WHERE state='queued' AND post_at IS NOT NULL")]:
            follow = cards.follow_time(cr)
            if follow != cr["post_at"]:
                cards.update(cr["id"], post_at=follow, note=f"post time follows the Short: {follow}")
            if t >= dt.datetime.fromisoformat(follow):
                cards.update(cr["id"], state="posting", note="post time")
                cards.spawn("post", cr["id"])
    except Exception as e:
        print(f"card queue: {e}", file=sys.stderr)
    for run in stats_due():
        update(run["day"], stats_at=t.isoformat())
        try:
            from frameflow import stats48
            stats48.collect(run["video_id"])
        except Exception as e:
            print(f"stats {run['day']}: {e}", file=sys.stderr)
        try:   # stats are in: the library has its assets, so the bulky files can go
            from frameflow import cleanup, library
            library.extract(run["video_id"])
            freed = cleanup.clean(run["video_id"])
            update(run["day"], note=f"cleanup: {freed}")
        except Exception as e:
            print(f"cleanup {run['day']}: {e}", file=sys.stderr)
        from frameflow import webexport
        update(run["day"], note="studio: " + webexport.refresh("48 h stats " + run["day"]))
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
        from frameflow import showdesk
        if run["state"] == "topic-sent":
            deadline = at((dt.date.fromisoformat(day) - dt.timedelta(days=1)).isoformat(), c["auto_pick_at"])
            if showdesk.is_show(run):   # the card's own pick-by time (a late card gets a fair window)
                deadline = dt.datetime.fromisoformat(json.loads(run["options"]).get("pick_by") or deadline.isoformat())
            if t >= deadline and showdesk.is_show(run):
                showdesk.pick(day, auto=True)
            elif t >= deadline and json.loads(run["options"] or "[]"):
                pick(day, 1, auto=True)
        elif run["state"] == "picked" and not run.get("job_pid") and showdesk.is_show(run) and showdesk.cfg().get("make_ready"):
            spawn("make", day)   # ticked while the show maker was still being finished
        elif run["state"] == "queued" and run["post_at"] and t >= dt.datetime.fromisoformat(run["post_at"]):
            spawn("post", day)
            update(day, state="posting")
        elif run["state"] in ("making", "posting", "picked", "ordering") and not job_alive(run) and run.get("job_pid") \
                and (now() - dt.datetime.fromisoformat(run["updated_at"])).total_seconds() > 60:
            # usually the laptop shut down mid-job (it runs 10:00-17:00): start the step again once, then ask
            restarts = (run.get("log") or "").count("restarted after stop")
            step = ("post" if run["state"] == "posting" else "order" if run["state"] == "ordering"
                    else ("revise" if run.get("notes") and run.get("video_id") else "make"))
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


def run_step(a, day):
    if a.step == "scout":
        # the bot's placeholder row ('scouting') stays until scout() replaces it: deleting it first let the 30 s tick
        # see no run and start a second scout, and two topic cards went out (2026-10-26)
        print(json.dumps(scout(day), indent=1, default=str)[:2000])
    elif a.step == "make":
        make(day)
    elif a.step == "order":
        order(day)
    elif a.step == "revise":
        revise(day)
    elif a.step == "post":
        post(day)
    elif a.step == "tick":
        tick()
    else:
        print(status_text())


def main():
    ap = argparse.ArgumentParser(description="Frameflow daily automation")
    ap.add_argument("step", choices=["scout", "make", "order", "revise", "post", "tick", "status"])
    ap.add_argument("day", nargs="?")
    ap.add_argument("--day", dest="day_opt")
    a = ap.parse_args()
    day = a.day or a.day_opt
    if day and a.step in ("make", "order", "revise", "post"):   # step-by-step progress for the control panel's Making view
        os.environ["FF_PROGRESS"] = str(ROOT / "logs" / f"progress-{day}.jsonl")
    try:
        with progress.step(a.step, day=day):
            run_step(a, day)
    except (Exception, SystemExit) as e:   # SystemExit("no video ...") from a helper once ended a make silently, stuck at 'making'
        if isinstance(e, SystemExit) and e.code in (None, 0):
            raise
        reset = limit_reset(str(e))
        if day and reset and get(day):   # Claude usage limit: not a failure, a wait; tick re-runs the step at the reset time
            update(day, state="waiting-limit", job_pid=None, post_at=get(day).get("post_at"), note=f"{a.step} paused by the usage limit; retry at {reset} (step {a.step})")
            try:
                telegram.send(f"Paused by the Claude usage limit. I'll carry on by myself at {reset[11:16]}.")
            except Exception:
                pass
            sys.exit(0)
        if day and a.step in ("make", "order", "revise", "post", "scout") and get(day):
            update(day, state="failed", job_pid=None, note=f"{a.step} failed: {e}")
            try:
                telegram.send(f"The {a.step} step for {day} failed: {str(e)[:300]}\nReply /retry to try again.")
            except Exception:
                pass
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
