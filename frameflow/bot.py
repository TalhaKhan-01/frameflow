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
        "/status  where things are\n/cards  a Habit card post (carousel) for today\n/profile [name]  model presets for experiments\n/feedback <notes>  your notes on the last video\n/log  what the current run is doing\n/ab  blind script test\n/pause  stop the daily runs\n/resume  start them again\n/retry  re-run a failed step")


def set_paused(flag):
    p = telegram.CONFIG
    d = json.loads(p.read_text())
    d["paused"] = flag
    p.write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n")


def latest(states):
    rows = [dict(r) for r in daily.db().execute("SELECT * FROM runs ORDER BY day DESC")]
    return next((r for r in rows if r["state"] in states), None)


def retry():
    run = latest(("failed", "waiting-limit"))
    if not run:
        return telegram.send("Nothing has failed. /status shows where things are.")
    day = run["day"]
    step = daily.last_step(run)
    if run["approved_at"] and run["video_id"]:
        daily.update(day, state="queued", note="retry: post")
    elif run["video_id"] and step in ("revise", "reflow"):   # re-run the step that stopped, not just the card
        daily.update(day, state="making", note=f"retry: {step}")
        daily.spawn(step, day)
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


def revise_buttons(day, found, picks):
    """Issue toggles (✓ when picked), five to a row, then All / Done / Cancel."""
    nums = [(f"{'✓' if i in picks else ''}{i + 1}", f"iss:{day}:{i}") for i in range(len(found))]
    rows = [nums[k:k + 5] for k in range(0, len(nums), 5)]
    return rows + [[("All of them", f"issall:{day}"), ("Done picking", f"issdone:{day}"), ("Cancel", f"isscancel:{day}")]]


def start_order(day):
    """The showrunner reads the words and ticked issues in its own process (a Claude call); the order comes back here."""
    daily.update(day, state="ordering", note="showrunner: reading the request")
    telegram.send("Got it. Working out exactly what to change; I'll show you before anything is redone.")
    daily.spawn("order", day)


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
    if kind.startswith("card"):   # Habit card posts (frameflow.cards)
        from frameflow import cards
        run_id = rest.split(":")[0]
        cr = cards.get(run_id)
        if not cr:
            return telegram.send("That card post is gone.")
        if kind == "cardpick" and cr["state"] == "topic-sent":
            opts = json.loads(cr["options"])
            choice = opts[int(rest.split(":")[1]) - 1]
            cards.update(run_id, state="picked", chosen=json.dumps(choice, ensure_ascii=False), note=f"picked {choice['title'][:80]}")
            telegram.clear_buttons(cr["preview_msg"])
            telegram.send(f"Making the card post: {choice['title'][:120]}\nThe slides come back here in a few minutes.")
            return cards.spawn("make", run_id)
        if kind == "cardskip":
            cards.update(run_id, state="skipped", note="skipped")
            return telegram.clear_buttons(cr["preview_msg"], "No card post today.")
        if kind == "cardok" and cr["state"] == "preview-sent":
            return telegram.clear_buttons(cr["preview_msg"], cards.queue_or_post(run_id))
        if kind == "cardrev" and cr["state"] == "preview-sent":
            if cr["revisions"] >= 2:
                return telegram.send("That's 2 revisions already. Approve or Reject this one.")
            cards.update(run_id, state="card-notes", note="waiting for notes")
            return telegram.clear_buttons(cr["preview_msg"], "What should change on the slides? One message, please.")
        if kind == "cardno" and cr["state"] == "preview-sent":
            cards.update(run_id, state="rejected", note="rejected")
            return telegram.clear_buttons(cr["preview_msg"], "Rejected, nothing posted.")
        return telegram.send(f"That button is from an older step (the card post is now '{cr['state']}').")
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
        from frameflow import producer
        found = producer.issues(day)
        daily.update(day, state="awaiting-notes", revisions=run["revisions"] + 1, notes="", revise_picks="[]", order_file=None,
                     note="revise: asking what to change")
        telegram.clear_buttons(run["video_msg"])
        text = ("What should change? Tap any known issue, or just tell me in your own words (one message, as loose as you like)."
                + ("\n\nKnown issues:\n" + "\n".join(f"{i + 1}. {x[:220]}" for i, x in enumerate(found)) if found else ""))
        msg = telegram.send(text, revise_buttons(day, found, []))
        daily.update(day, order_msg=str(msg))
    elif kind in ("iss", "issall", "issdone") and run["state"] == "awaiting-notes":
        from frameflow import producer
        found = producer.issues(day)
        picks = json.loads(run.get("revise_picks") or "[]")
        if kind == "iss":
            n = int(rest.split(":")[1])
            picks = [x for x in picks if x != n] if n in picks else sorted(picks + [n])
        elif kind == "issall":
            picks = list(range(len(found)))
        daily.update(day, revise_picks=json.dumps(picks))
        if kind != "issdone":
            return telegram.edit_buttons(int(run["order_msg"]), revise_buttons(day, found, picks))
        if not picks and not (run.get("notes") or "").strip():
            return telegram.send("Tick at least one issue, or write what should change.")
        telegram.clear_buttons(int(run["order_msg"]))
        start_order(day)
    elif kind == "ordgo" and run["state"] == "order-sent":
        telegram.clear_buttons(int(run["order_msg"]))
        daily.update(day, state="making", note="change order confirmed (Go)")
        telegram.send("Go. Revising now; the new version comes back here.")
        daily.spawn("revise", day)
    elif kind == "ordchg" and run["state"] == "order-sent":
        telegram.clear_buttons(int(run["order_msg"]))
        daily.update(day, state="awaiting-notes", order_file=None, note="change order: Talha wants it different")
        telegram.send("Tell me what to change instead, or what I got wrong (your ticked issues stay ticked).")
    elif kind in ("ordno", "isscancel") and run["state"] in ("order-sent", "awaiting-notes"):
        if run.get("order_msg"):
            telegram.clear_buttons(int(run["order_msg"]))
        daily.update(day, state="video-sent", order_file=None, revise_picks=None, revisions=max(run["revisions"] - 1, 0),
                     note="revise cancelled")
        telegram.send("Cancelled; nothing changes. Here is the video again.")
        daily.video_card(day)
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
    if cmd == "/cards":
        from frameflow import cards
        return cards.spawn("topics", "new")
    if cmd == "/profile":   # pipeline presets (models, rounds): /profile lists, /profile <name> switches for the next video
        from frameflow import profiles
        arg = t.split()[1] if len(t.split()) > 1 else ""
        if arg:
            if arg not in profiles.names():
                return telegram.send(f"No profile '{arg}'. Profiles: {', '.join(profiles.names())}")
            profiles.use(arg)
            return telegram.send(f"Switched to '{arg}'. The next video is made with it (a video already in progress keeps its settings).")
        active = profiles.pipeline().get("profile")
        lines = [f"{'▶ ' if n == active else '  '}{n}: {json.loads((profiles.PROFILES / (n + '.json')).read_text()).get('_about', '')}" for n in profiles.names()]
        return telegram.send("Profiles (/profile <name> to switch):\n" + "\n".join(lines))
    if cmd == "/feedback":   # Talha's notes on the latest posted (or made) video -> lessons for every next video
        words = t[len("/feedback"):].strip()
        if not words:
            return telegram.send("Write it after the command, e.g. /feedback the hook was slow and the music too loud.")
        from frameflow import lessons, videos
        row = videos.db().execute("SELECT id, out_dir FROM videos WHERE status IN ('posted','approved','awaiting-approval') "
                                  "ORDER BY updated_at DESC LIMIT 1").fetchone()
        if not row:
            return telegram.send("No video to attach that to yet.")
        r = lessons.distill(row["out_dir"], notes=words, source=f"{row['id']} (Talha's feedback)", owner_only=True)
        new = "\n".join(f"- {x['text']}" for x in r.get("new", [])) or "(it matched lessons already in the ledger; they got stronger)"
        return telegram.send(f"Thanks. From your feedback on {row['id']}:\n{new}\nThese go into every next script and storyboard.")
    if cmd == "/log":   # the latest run's step-by-step log and the last lines of its current job
        run = (latest(("topic-sent", "picked", "making", "video-sent", "awaiting-notes", "queued", "posting", "failed", "posted")) or {})
        if not run:
            return telegram.send("No runs yet.")
        steps = "\n".join(l[11:16] + l[19:] for l in (run.get("log") or "").strip().splitlines()[-12:])
        logs = sorted(daily.LOGS.glob(f"daily-{run['day']}-*.log"), key=lambda p: p.stat().st_mtime)
        tail = ""
        if logs:
            lines = [l for l in logs[-1].read_text(errors="replace").splitlines() if l.strip() and "token" not in l.lower()][-6:]
            tail = f"\n\nLast lines of {logs[-1].name}:\n" + "\n".join(l[:160] for l in lines)
        return telegram.send(f"{run['day']} · {run['state']}\n{steps}{tail}")
    from frameflow import cards
    card_wait = cards.latest(("card-notes",))
    if card_wait:
        cards.update(card_wait["id"], notes=t, revisions=card_wait["revisions"] + 1, state="making", note="notes received")
        telegram.send("Got it. Redoing the slides now.")
        return cards.spawn("revise", card_wait["id"])
    card_topic = cards.latest(("topic-sent",))
    if card_topic and URL.search(t) and not latest(("topic-sent",)):
        url = URL.search(t).group(0)
        cards.update(card_topic["id"], state="picked", chosen=json.dumps({"kind": "story", "title": "", "url": url}), note=f"picked link {url}")
        telegram.send("Making the card post from your link. The slides come back here in a few minutes.")
        return cards.spawn("make", card_topic["id"])
    waiting = latest(("awaiting-notes",))
    if waiting:
        before = (waiting.get("notes") or "").strip()
        daily.update(waiting["day"], notes=(f"{before}\nThen: {t}" if before else t), note="revise words received")
        if waiting.get("order_msg"):
            telegram.clear_buttons(int(waiting["order_msg"]))
        return start_order(waiting["day"])
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
    me = telegram.chat_id()
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
                except (Exception, SystemExit) as e:   # SystemExit too: a refused step must answer, not restart the bot
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
