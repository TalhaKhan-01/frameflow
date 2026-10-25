"""Frameflow's Telegram bot (PM2 app frameflow-bot): long polling, Talha's chat only, plus the daily tick.

Buttons: pick:<day>:<n>, skip:<day>, approve:<day>, revise:<day>, reject:<day>.
Commands: /status, /pause, /resume, /retry, /help. A pasted link while a topic card is open picks that link;
text after Revise becomes the revision notes; text after Reject is kept as the reason (a lesson for next time).
"""
import json
import re
import sys
import time
import traceback

from frameflow import daily, telegram

TICK_EVERY = 30
URL = re.compile(r"https?://\S+")
HELP = ("I'm Habit, Frameflow's bot.\n"
        "Every day at 14:00 I send tomorrow's story options. Pick one (or paste a link) by 15:00, or I'll take story 1.\n"
        "The video comes back here before 17:00: Approve, Revise (tell me what to change) or Reject. You can tap any time,\n"
        "even at night: I act on it when the laptop starts at 10:00.\n"
        "Approved before 11:30: posted at 11:30. Approved later: posted right away.\n\n"
        "/status  where things are\n/ab  blind script test\n/pause  stop the daily runs\n/resume  start them again\n/retry  re-run a failed step")


def set_paused(flag):
    p = telegram.CONFIG
    d = json.loads(p.read_text())
    d["paused"] = flag
    p.write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n")


def latest(states):
    rows = [dict(r) for r in daily.db().execute("SELECT * FROM runs ORDER BY day DESC")]
    return next((r for r in rows if r["state"] in states), None)


def retry():
    run = latest(("failed",))
    if not run:
        return telegram.send("Nothing has failed. /status shows where things are.")
    day = run["day"]
    if run["approved_at"] and run["video_id"]:
        daily.update(day, state="queued", note="retry: post")
    elif run["video_id"]:   # the video exists: send its card again
        daily.update(day, note="retry: video card")
        try:
            daily.video_card(day)
        except Exception as e:
            telegram.send(f"Couldn't resend the video card: {str(e)[:200]}")
    elif daily.chosen(run):
        daily.update(day, state="picked", note="retry: make")
        daily.spawn("make", day)
    else:
        daily.db().execute("DELETE FROM runs WHERE day=?", (day,)).connection.commit()
        daily.spawn_scout(day)
    telegram.send(f"Retrying {day}.")


AB_FILE = daily.ROOT / "data" / "ab-tests.jsonl"


def ab_test():
    """Blind A/B: the first script the writer drafted vs the final one, for the latest video that has both."""
    import random
    cands = sorted(daily.ROOT.glob("out/*/writer/script-v1.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not cands:
        return telegram.send("No video has two script versions to compare yet.")
    wdir = cands[0].parent
    v1, v2 = (json.loads((wdir / n).read_text()) for n in ("script-v1.json", "script.json"))
    pair = [("v1", v1), ("v2", v2)]
    random.shuffle(pair)
    test = f"{wdir.parent.name}:{pair[0][0]}"
    for label, (_, s) in zip("AB", pair):
        telegram.send(f"Script {label}\n\n" + "\n".join(b["say"] for b in s["beats"]))
    telegram.send("Which one would you rather watch?", [[("A", f"ab:{test}:A"), ("B", f"ab:{test}:B")]])


def on_callback(cb):
    data = cb.get("data", "")
    telegram.answer(cb["id"])
    kind, _, rest = data.partition(":")
    if kind == "ab":   # ab:<video>:<version shown as A>:<tap>
        video, first, tap = rest.split(":")
        chosen_v = first if tap == "A" else ("v2" if first == "v1" else "v1")
        with AB_FILE.open("a") as f:
            f.write(json.dumps({"video": video, "chose": chosen_v, "at": daily.now().isoformat()}) + "\n")
        telegram.clear_buttons(cb["message"]["message_id"])
        return telegram.send(f"You picked the {'final (v2)' if chosen_v == 'v2' else 'first draft (v1)'} script. Noted.")
    if kind in ("promote", "keep"):   # weekly lesson promotion
        from frameflow import lessons
        if kind == "promote":
            r = lessons.promote(rest)
            return telegram.send(f"Lesson {r['id']} is now a permanent {r['area']} house rule.")
        return telegram.send(f"Keeping {rest} under test.")
    day = rest.split(":")[0]
    run = daily.get(day)
    if not run:
        return telegram.send(f"I have no run for {day} any more.")
    if kind == "pick" and run["state"] == "topic-sent":
        daily.pick(day, int(rest.split(":")[1]))
    elif kind == "skip" and run["state"] == "topic-sent":
        daily.update(day, state="skipped", note="Talha skipped the day")
        telegram.clear_buttons(run["topic_msg"], f"Skipping {day}. No video that day.")
    elif kind == "approve" and run["state"] == "video-sent":
        daily.approve(day)
    elif kind == "revise" and run["state"] == "video-sent":
        if run["revisions"] >= daily.cfg()["max_revisions"]:
            return telegram.send(f"That's {run['revisions']} revisions already (the limit). Approve or Reject this one.")
        daily.update(day, state="awaiting-notes", note="waiting for revision notes")
        telegram.clear_buttons(run["video_msg"])
        telegram.send("What should change? Write it in one message (words, pace, a scene, the ending...).")
    elif kind == "reject" and run["state"] == "video-sent":
        from frameflow import videos
        videos.set_status(run["video_id"], "rejected", "rejected on Telegram")
        daily.update(day, state="rejected", note="Talha rejected the video")
        telegram.clear_buttons(run["video_msg"], "Rejected, nothing will be posted. If you tell me why in one message, "
                                                  "I'll keep it as a lesson for the next videos.")
    else:
        telegram.send(f"That button is from an older step ({run['day']} is now '{run['state']}').")


def on_text(text):
    t = text.strip()
    cmd = t.split()[0].lower() if t.startswith("/") else ""
    if cmd in ("/start", "/help"):
        return telegram.send(HELP)
    if cmd == "/status":
        return telegram.send(daily.status_text())
    if cmd == "/pause":
        set_paused(True)
        return telegram.send("Paused: no new topic cards until /resume. Anything already approved still posts.")
    if cmd == "/resume":
        set_paused(False)
        return telegram.send("Resumed. Next topic card at " + daily.cfg()["topic_card_at"] + ".")
    if cmd == "/retry":
        return retry()
    if cmd == "/ab":
        return ab_test()
    waiting = latest(("awaiting-notes",))
    if waiting:
        daily.update(waiting["day"], notes=t, revisions=waiting["revisions"] + 1, state="making", note="notes received")
        telegram.send("Got it. Revising now; the new version comes back here.")
        return daily.spawn("revise", waiting["day"])
    open_topic = latest(("topic-sent",))
    m = URL.search(t)
    if open_topic and m:
        return daily.pick(open_topic["day"], url=m.group(0))
    rejected = latest(("rejected",))
    if rejected and not (rejected["notes"] or "").startswith("REJECT:"):
        daily.update(rejected["day"], notes="REJECT: " + t, note="reject reason kept")
        try:
            from frameflow import lessons, videos
            row = videos.db().execute("SELECT out_dir FROM videos WHERE id=?", (rejected["video_id"],)).fetchone()
            lessons.distill(row["out_dir"], notes=t, source=f"{rejected['video_id']} (rejected)")
        except Exception as e:
            print(f"lessons: {e}", file=sys.stderr)
        return telegram.send("Thanks, noted for the next videos.")
    telegram.send("I didn't catch that. /help shows what I can do.")


def loop():
    me = telegram.config()["chat_id"]
    offset, last_tick = None, 0.0
    print("frameflow-bot polling", flush=True)
    while True:
        try:
            for u in telegram.updates(offset, wait=20):
                offset = u["update_id"] + 1
                msg, cb = u.get("message"), u.get("callback_query")
                chat = (msg or (cb or {}).get("message") or {}).get("chat", {}).get("id")
                if chat != me:   # only Talha's chat; everyone else is ignored silently
                    continue
                try:
                    if cb:
                        on_callback(cb)
                    elif msg and msg.get("text"):
                        on_text(msg["text"])
                except Exception as e:
                    traceback.print_exc()
                    telegram.send(f"Something went wrong handling that: {str(e)[:200]}")
        except telegram.TelegramError as e:
            print(f"poll: {e}", file=sys.stderr, flush=True)
            time.sleep(5)
        if time.time() - last_tick >= TICK_EVERY:
            last_tick = time.time()
            try:
                daily.tick()
            except Exception:
                traceback.print_exc()


if __name__ == "__main__":
    loop()
