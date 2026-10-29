"""The Daily Habit's topic desk (P24.6.1): the day's candidate stories, ranked by virality, on one Telegram card where
Talha ticks the ones the episode covers.

    python -m frameflow.showdesk candidates [--n 15]     print the ranked candidates (no Telegram, no run)

The daily scout calls scout(day) when research/show.json has "enabled": true. Ticks are toggles on the card (stog),
"Top N for me" ticks the best N (stop), "Make episode" confirms (smake). No answer by auto_pick_at = the top `topics`.
"""
import argparse
import datetime as dt
import json
import sys
import tempfile
from pathlib import Path

from frameflow import daily, direct, ideas, llm, telegram

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "research" / "show.json"
TOPICS = Path.home() / "Talha_Khan" / "Claude" / "skills" / "shorts-producer" / "scripts" / "topics.py"


def cfg():
    return json.loads(CONFIG.read_text())


def enabled():
    return CONFIG.exists() and cfg().get("enabled", False)


def is_show(run):
    o = json.loads((run or {}).get("options") or "{}")
    return isinstance(o, dict) and o.get("show") is True


VIRAL_SYSTEM = """You are the topic editor of The Daily Habit, a fast daily news show for YouTube Shorts / Instagram Reels:
the narrator Habit covers 8 stories in about 85 seconds, 8-10 seconds each, with a witty line or a pun per story.
Audience: Indians aged 18-30, curious about tech, AI, money, science and the internet; most don't code.
From the candidate stories, pick the best ones for today's episode and rank them by VIRALITY: how likely a story is to
stop a scroll and get shared. Weigh: surprise or shock, a concrete number or stake, relatability for young Indians
(jobs, phones, money, apps they use, India's place in the world), timeliness (last 24-36 h), a fun angle for a pun,
and whether it can be shown with simple graphics (a number, a comparison, a headline, a logo-free icon).
Rules: one entry per real-world story (merge duplicates from different outlets, keep the most original source);
mix lanes (no more than 4 from one lane); drop gossip, deals, coupons, stock tips, tragedies, politics-only fights,
anything that can't be sourced. A candidate marked UPDATE continues a story the show already aired: rank it only on
its new development, and its headline must lead with that development. headline: at most 8 words, punchy, true. why: one short line on why it will travel.
pun: a first idea for the witty line (can be improved later). Return JSON only."""

VIRAL_SCHEMA = {"type": "object", "required": ["stories"], "properties": {"stories": {"type": "array", "items": {
    "type": "object", "required": ["id", "virality", "headline", "why", "lane", "pun"],
    "properties": {"id": {"type": "integer"}, "virality": {"type": "integer", "minimum": 0, "maximum": 100},
                   "headline": {"type": "string"}, "why": {"type": "string"}, "pun": {"type": "string"},
                   "lane": {"type": "string", "enum": ["Tech", "AI", "Money", "India", "Science", "Internet"]}}}}}}


def used_urls():
    out = set()
    for r in daily.db().execute("SELECT story, options FROM runs"):
        if r["story"]:
            out.add(r["story"])
        o = json.loads(r["options"] or "{}")
        if isinstance(o, dict) and o.get("show"):
            out |= {c["url"] for c in o.get("chosen", [])}
    return out


def memory(rows, day):
    """The showrunner's topic memory (shorts-producer topics.py): each row -> new / repeat / update vs the last 14 days."""
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump([{"id": r["id"], "title": r["title"], "summary": (r["summary"] or "")[:300], "url": r["url"]} for r in rows], f)
    return json.loads(direct.skill([TOPICS, "--project", ROOT, "filter", f.name, "--day", day], timeout=600, strict=True))


def record(day, episode, stories):
    """Aired (picked) stories go into the covered-topics ledger, so later cards don't offer them again."""
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump([{"day": day, "episode": episode, "headline": s.get("headline", ""), "title": s.get("title", ""),
                    "summary": (s.get("summary") or "")[:300], "url": s["url"]} for s in stories], f, ensure_ascii=False)
    return json.loads(direct.skill([TOPICS, "--project", ROOT, "record", f.name], timeout=60, strict=True))


def candidates(n=None, hours=36, day=None):
    """Fresh ranked ideas -> topic memory drops repeats -> one model call that merges duplicates and ranks by virality
    -> the best n. Returns (stories, repeats removed)."""
    c = cfg()
    n = n or c["candidates"]
    try:
        ideas.collect()
        ideas.rank(hours=hours, keep=40)
    except Exception as e:   # a dead feed or a model hiccup shouldn't stop the card: use what is already ranked
        print(f"collect/rank: {e}", file=sys.stderr)
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=hours)
    used = used_urls()
    rows = [dict(r) for r in ideas.db().execute(
        "SELECT id, source, title, url, summary, angle, hook, score, lane, published FROM ideas WHERE status='new' AND score > 0 "
        "AND fetched_at >= ? ORDER BY score DESC LIMIT 80", ((daily.now() - dt.timedelta(days=2)).isoformat(),))]
    rows = [r for r in rows if r["url"] not in used and (ideas.published_at(r["published"]) or cutoff) >= cutoff][:60]
    try:
        verdicts = memory(rows, day or (daily.now().date() + dt.timedelta(days=1)).isoformat())
    except Exception as e:   # a failed memory call shouldn't cost the day's card: the card says it wasn't checked
        print(f"topic memory: {e}", file=sys.stderr)
        verdicts = None
    removed = [r for r in rows if (verdicts or {}).get(str(r["id"]), {}).get("verdict") == "repeat"]
    rows = [r for r in rows if r not in removed][:45]
    if len(rows) < n:
        raise RuntimeError(f"only {len(rows)} fresh ranked stories after {len(removed)} repeats (need {n})")
    upd = {str(r["id"]): verdicts[str(r["id"])] for r in rows if (verdicts or {}).get(str(r["id"]), {}).get("verdict") == "update"}
    listing = "\n".join(f"{r['id']} | {r['lane']} | {r['source']} | {r['title']} | {(r['summary'] or '')[:160]} | angle: {r['angle'] or '-'}"
                        + (f" | UPDATE of '{upd[str(r['id'])]['covered']['headline']}' (aired {upd[str(r['id'])]['covered']['day']}): new = {upd[str(r['id'])]['new_info']}"
                           if str(r["id"]) in upd else "") for r in rows)
    out = llm.call(f"Today is {dt.date.today().isoformat()}. {len(rows)} candidate stories (id | lane | source | title | summary | angle).\n"
                   f"Return the best {n}, most viral first.\n{listing}",
                   VIRAL_SYSTEM, VIRAL_SCHEMA, model=c.get("virality_model", "sonnet"), purpose="show.virality", effort="medium")
    by_id = {r["id"]: r for r in rows}
    picked, seen = [], set()
    for s in sorted(out["stories"], key=lambda s: -s["virality"]):
        r = by_id.get(s["id"])
        if not r or r["url"] in seen:
            continue
        seen.add(r["url"])
        title, _, outlet = r["title"].rpartition(" - ") if " - " in r["title"] else (r["title"], "", "")
        picked.append({"idea": r["id"], "title": title or r["title"], "url": r["url"], "summary": r["summary"] or "",
                       "outlet": outlet or daily.source_of(r["url"]), "virality": s["virality"], "headline": s["headline"],
                       "why": s["why"], "pun": s["pun"], "lane": s["lane"], "angle": r["angle"] or ""})
        if str(r["id"]) in upd:
            picked[-1]["update"] = upd[str(r["id"])]
            if not picked[-1]["headline"].lower().startswith("update"):
                picked[-1]["headline"] = "Update: " + picked[-1]["headline"]
    return picked[:n], (len(removed) if verdicts is not None else None)


def episode_number(day):
    eps = [json.loads(r["options"] or "{}") for r in daily.db().execute("SELECT options FROM runs WHERE day < ?", (day,))]
    return 1 + sum(1 for o in eps if isinstance(o, dict) and o.get("show") and o.get("chosen"))


def buttons(day, n, ticked):
    c = cfg()
    rows, row = [], []
    for i in range(1, n + 1):
        row.append((f"{'✅' if i in ticked else '☐'} {i}", f"stog:{day}:{i}"))
        if len(row) == 5:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([(f"⭐ Top {c['topics']} for me", f"stop:{day}"), (f"▶ Make episode ({len(ticked)}/{c['max_pick']})", f"smake:{day}")])
    rows.append([("Skip this day", f"skip:{day}")])
    return rows


def scout(day):
    """The show's topic card for a posting day: `candidates` stories, most viral first, tick boxes, Make."""
    c = cfg()
    cands, removed = candidates(day=day)
    ep = episode_number(day)
    deadline = daily.at((dt.date.fromisoformat(day) - dt.timedelta(days=1)).isoformat(), daily.cfg()["auto_pick_at"])
    opts = {"show": True, "episode": ep, "list": cands, "ticked": [], "chosen": [], "pick_by": deadline.isoformat()}
    con = daily.db()
    con.execute("INSERT OR REPLACE INTO runs (day, lane, state, options, created_at, updated_at, log) VALUES (?,?,?,?,?,?,?)",
                (day, "show", "topic-sent", json.dumps(opts, ensure_ascii=False), daily.now().isoformat(), daily.now().isoformat(), ""))
    con.commit()
    when = dt.date.fromisoformat(day).strftime("%A %d %b")
    lines = [f"🗞 The Daily Habit · Ep {ep} · {when}",
             f"{len(cands)} stories, most viral first. Tick {c['min_pick']}-{c['max_pick']} for the episode, then tap Make "
             f"(or ⭐ for my top {c['topics']}).",
             "⚠️ Topic memory couldn't run today: check for repeats yourself." if removed is None else
             f"🧠 Topic memory: {removed} repeat{'' if removed == 1 else 's'} of the last 14 days removed." if removed else
             "🧠 Topic memory: no repeats of the last 14 days in today's news.", ""]
    for i, s in enumerate(cands, 1):
        lines += [f"{i}. {s['headline']}  · {s['lane']} · 🔥{s['virality']}",
                  f"   {s['why'][:130]} ({s['outlet'][:30]})"]
        if s.get("update"):
            lines.append(f"   ↪ follows Ep {s['update']['covered']['episode']} ({s['update']['covered']['day']}): {s['update']['new_info'][:110]}")
        lines.append("")
    lines.append(f"No answer by {deadline.strftime('%H:%M %a')} and I'll make my top {c['topics']}.")
    msg = telegram.send("\n".join(lines), buttons(day, len(cands), []))
    daily.update(day, topic_msg=msg, note=f"show topic card sent (Ep {ep}, {len(cands)} candidates, {removed} repeats removed)")
    return daily.get(day)


def toggle(day, i=None, top=False):
    run = daily.get(day)
    o = json.loads(run["options"])
    c = cfg()
    if top:
        o["ticked"] = list(range(1, min(c["topics"], len(o["list"])) + 1))
    elif i in o["ticked"]:
        o["ticked"].remove(i)
    elif len(o["ticked"]) >= c["max_pick"]:
        return telegram.send(f"That's {c['max_pick']} already: untick one first.")
    else:
        o["ticked"] = sorted(o["ticked"] + [i])
    daily.update(day, options=json.dumps(o, ensure_ascii=False))
    telegram.edit_buttons(run["topic_msg"], buttons(day, len(o["list"]), o["ticked"]))


def pick(day, ticked=None, auto=False):
    """Confirm the episode's stories (in virality order) and start the make (or wait for the show maker)."""
    run = daily.get(day)
    if not run or run["state"] != "topic-sent":
        return run
    o = json.loads(run["options"])
    c = cfg()
    ticked = sorted(ticked if ticked is not None else o["ticked"])
    if auto and not ticked:
        ticked = list(range(1, min(c["topics"], len(o["list"])) + 1))
    if len(ticked) < c["min_pick"]:
        return telegram.send(f"Tick at least {c['min_pick']} stories (you have {len(ticked)}), or tap ⭐ for my top {c['topics']}.")
    o["ticked"], o["chosen"] = ticked, [o["list"][i - 1] for i in ticked]
    daily.update(day, state="picked", story=o["chosen"][0]["url"], options=json.dumps(o, ensure_ascii=False),
                 note=f"picked {len(ticked)} stories {ticked}{' (auto)' if auto else ''}")
    try:
        record(day, o["episode"], o["chosen"])
    except Exception as e:   # the ledger is a memory, not a gate: a failed write must not stop the episode
        daily.update(day, note=f"topic memory not recorded: {str(e)[:150]}")
    if run.get("topic_msg"):
        telegram.clear_buttons(run["topic_msg"])
    names = "\n".join(f"{k}. {s['headline']}" for k, s in enumerate(o["chosen"], 1))
    telegram.send(f"{'No pick in time, so I took my top ' + str(len(ticked)) if auto else 'Got it'}: Ep {o['episode']} runs these, in this order:\n"
                  f"{names}\n\n" + ("Researching and fact-checking each story now; the episode comes here for your approval."
                                    if c.get("make_ready") else "The show maker is getting its last checks; it starts by itself as soon as it's ready."))
    if c.get("make_ready"):
        daily.spawn("make", day)


def main():
    ap = argparse.ArgumentParser(description="The Daily Habit topic desk")
    ap.add_argument("cmd", choices=["candidates"])
    ap.add_argument("--n", type=int)
    ap.add_argument("--day", help="the posting day the card is for (default tomorrow)")
    a = ap.parse_args()
    cands, removed = candidates(a.n, day=a.day)
    print(f"{removed} repeats removed by topic memory")
    for i, s in enumerate(cands, 1):
        print(f"{i:2}. [{s['virality']}] {s['lane']:8} {s['headline']} | {s['title'][:90]} ({s['outlet']})"
              + (f"  <- UPDATE of {s['update']['covered']['day']}: {s['update']['new_info']}" if s.get("update") else ""))


if __name__ == "__main__":
    main()
