"""The hook card (P25.1.2): after the writer, Talha picks the show's open from 10 ranked hooks on Telegram.

    python -m frameflow.hookpick options <out-dir>      print the 10 hooks for a written episode (no Telegram)

The make writes <out>/hooks.json and waits on it; the bot only writes Talha's tap or words into it, and the make does the
model work. States: waiting -> improve (his words for hook n) -> waiting (the rewritten list, timer reset) ...;
own (his own open) or chosen ends it. No answer by the deadline = hook 1. research/show.json "hook_pick" sets
enabled / count / wait_minutes.
"""
import argparse
import datetime as dt
import json
import re
import time
from pathlib import Path

from frameflow import daily, llm, progress, telegram

FAMILIES = ["stake", "number shock", "question", "contrast", "you-relevance", "curiosity gap", "myth-bust",
            "countdown tease", "India angle", "deadpan"]

SYSTEM = """You write cold opens for The Daily Habit, a fast daily news Short read by the narrator Habit (warm, quick, a
little cheeky; audience Indians aged 18-30). The open is the hook: the first 3 seconds decide whether a viewer stays.
Write COUNT different opens for this episode, one per hook family where possible: FAMILIES.
Rules for every open: 10-20 spoken words; starts with "Breaking:"; teases the top stories with a concrete stake;
uses only the verified facts given (no new number, name or claim); no digits (say numbers as words); plain spoken
English, no greeting, no "buckle up", no "in today's episode". Then rank them: score 0-100 = how likely the open stops
a scroll and makes the viewer stay for the second story. why: one short line. Return JSON only."""

IMPROVE = """You rewrite one cold open for The Daily Habit, following the owner's words exactly. Keep every rule: 10-20
spoken words, starts with "Breaking:", only the verified facts, no digits, plain spoken English. Return JSON only."""

LIST_SCHEMA = {"type": "object", "required": ["hooks"], "properties": {"hooks": {"type": "array", "items": {
    "type": "object", "required": ["say", "family", "score", "why"], "properties": {
        "say": {"type": "string"}, "family": {"type": "string"}, "score": {"type": "integer"}, "why": {"type": "string"}}}}}}
ONE_SCHEMA = {"type": "object", "required": ["say"], "properties": {"say": {"type": "string"}}}


def cfg():
    from frameflow import show
    return {"enabled": True, "count": 10, "wait_minutes": 20, "model": "sonnet", **show.cfg().get("hook_pick", {})}


def valid(say, script, data):
    """The problems this open adds to the script's own lint (show.lint on a copy), so a hook on the card can always air."""
    from frameflow import show
    probe = dict(script, open=dict(script["open"], say=say))
    base = set(show.lint(script, data))
    return [e for e in show.lint(probe, data) if e not in base and not e.startswith("estimated length")]


def options(script, data):
    from frameflow import show
    c = cfg()
    ask = (f"The episode's stories and verified facts:\n{show.stories_block(data)}\n\nThe writer's own open: {script['open']['say']}\n\n"
           f"Write {c['count'] + 4} opens and rank them.")
    system = SYSTEM.replace("COUNT", str(c["count"] + 4)).replace("FAMILIES", ", ".join(FAMILIES))
    r = llm.call(ask, system, LIST_SCHEMA, model=c["model"], purpose="show.hooks", effort="medium", timeout=900)
    hooks = [{"say": script["open"]["say"], "family": "writer's open", "score": script.get("table_read", {}).get("rows", {}).get("hook", 1) * 40 + 10,
              "why": "the open the writer and the table read settled on"}]
    for h in sorted(r["hooks"], key=lambda h: -h["score"]):
        h["say"] = h["say"].strip()
        if not valid(h["say"], script, data) and h["say"].lower() not in {x["say"].lower() for x in hooks}:
            hooks.append(h)
    mine = hooks[0]   # the writer's open passed the table read: it always stays on the card
    hooks = sorted(hooks, key=lambda h: -h["score"])[:c["count"]]
    if mine not in hooks:
        hooks[-1] = mine
    return hooks


def card(day, hooks, deadline, note=""):
    lines = [f"🎣 Pick the open for {day}'s episode" + (f" ({note})" if note else ""), ""]
    for i, h in enumerate(hooks, 1):
        lines += [f"{i}. {h['say']}", f"   {h['family']} · 🔥{h['score']} · {h['why'][:90]}", ""]
    lines.append(f"Tap a number. ✏️ Improve: tap it, then send e.g. \"3 make it about jobs\". 📝 Write my own: tap it, then "
                 f"send your open. No answer by {deadline.strftime('%H:%M')} = hook 1.")
    nums = [(str(i), f"hk:{day}:{i}") for i in range(1, len(hooks) + 1)]
    rows = [nums[:5], nums[5:10]] if len(nums) > 5 else [nums]
    rows.append([("✏️ Improve one", f"hkimp:{day}"), ("📝 Write my own", f"hkown:{day}")])
    return telegram.send("\n".join(lines), [r for r in rows if r])


def path_for(day):
    """The hooks.json of the day's episode while it is being made (None when there is no show make)."""
    from frameflow import show, showdesk
    run = daily.get(day)
    if not run or not showdesk.is_show(run):
        return None
    ep = json.loads(run["options"])["episode"]
    return show.OUT / show.slug_for(day, ep) / "hooks.json"


def state(day):
    p = path_for(day)
    return (p, json.loads(p.read_text())) if p and p.exists() else (p, None)


def save(p, h):
    p.write_text(json.dumps(h, ensure_ascii=False, indent=1))


def pick(script, data, out, day, poll=5):
    """Send the card, wait for Talha (or the deadline), return the script with the chosen open. Resumes a card already
    sent if the make restarts while it waits."""
    c = cfg()
    p = out / "hooks.json"
    h = json.loads(p.read_text()) if p.exists() else None
    if h and h["status"] == "chosen":
        return apply(script, h, out)
    if not h:
        with progress.step("hooks: 10 opens for the hook card", desk="writer") as info:
            hooks = options(script, data)
            info["hooks"] = len(hooks)
        deadline = daily.now() + dt.timedelta(minutes=c["wait_minutes"])
        h = {"status": "waiting", "hooks": hooks, "deadline": deadline.isoformat(), "msg": None, "history": []}
        h["msg"] = card(day, hooks, deadline)
        save(p, h)
        daily.update(day, note=f"hook card sent ({len(hooks)} hooks, waits until {deadline.strftime('%H:%M')})")
    with progress.step("hooks: waiting for Talha's pick", desk="writer") as info:
        while True:
            h = json.loads(p.read_text())
            if h["status"] == "improve-ready":   # his words for hook n: rewrite it, show the list again, reset the clock
                n, words = h["improve"]["n"], h["improve"]["words"]
                base = h["hooks"][n - 1]
                new = improve(base["say"], words, data)
                fresh = {"say": new, "family": f"your edit of {n}", "score": base["score"], "why": f"from: {words[:60]}"}
                h["hooks"] = [fresh] + [x for i, x in enumerate(h["hooks"]) if i != n - 1]
                h["history"].append({"improve": n, "words": words, "new": new})
                deadline = daily.now() + dt.timedelta(minutes=c["wait_minutes"])
                h.update(status="waiting", deadline=deadline.isoformat(), improve=None)
                if h.get("msg"):
                    telegram.clear_buttons(h["msg"])
                h["msg"] = card(day, h["hooks"], deadline, note=f"your edit of {n} is now 1")
                save(p, h)
                continue
            if h["status"] == "chosen":
                info["choice"] = h["choice"]["by"]
                break
            if h["status"] in ("waiting", "improve", "own") and daily.now() >= dt.datetime.fromisoformat(h["deadline"]):
                h.update(status="chosen", choice={"n": 1, "say": h["hooks"][0]["say"], "by": "timeout"})
                save(p, h)
                if h.get("msg"):
                    telegram.clear_buttons(h["msg"], f"No pick by {h['deadline'][11:16]}, so I went with 1: {h['hooks'][0]['say']}")
                info["choice"] = "timeout"
                break
            time.sleep(poll)
    return apply(script, h, out)


def apply(script, h, out):
    script = dict(script, open=dict(script["open"], say=h["choice"]["say"]))
    script["hook_pick"] = h["choice"]
    (out / "script.json").write_text(json.dumps(script, ensure_ascii=False, indent=1))
    return script


def improve(say, words, data):
    from frameflow import show
    r = llm.call(f"Verified facts:\n{show.stories_block(data)}\n\nThe open: {say}\nThe owner's words: {words}\n\nRewrite the open.",
                 IMPROVE, ONE_SCHEMA, model=cfg()["model"], purpose="show.hook-improve", effort="medium", timeout=600)
    return own_text(r["say"])


def own_text(text):
    t = re.sub(r"\s+", " ", text).strip().strip('"')
    return t if t.lower().startswith("breaking") else f"Breaking: {t}"


# ---------- the bot's side: it only writes Talha's choice into hooks.json ----------
def on_tap(kind, day, n=None):
    p, h = state(day)
    if not h or h["status"] == "chosen":
        return telegram.send("That hook card is closed: the episode already has its open.")
    if kind == "hk":
        n = int(n)
        h.update(status="chosen", choice={"n": n, "say": h["hooks"][n - 1]["say"], "by": "tap"})
        save(p, h)
        return telegram.clear_buttons(h["msg"], f"Open {n}: {h['hooks'][n - 1]['say']}\nVoicing the episode now.")
    if kind == "hkimp":
        h["status"] = "improve"
        save(p, h)
        return telegram.send("Which hook and what should change? Send e.g. \"3 make it about jobs\" (no number = hook 1).")
    if kind == "hkown":
        h["status"] = "own"
        save(p, h)
        return telegram.send("Send your open as one message. I'll start it with \"Breaking:\" if you don't.")


def waiting_text():
    """The day whose hook card is waiting for Talha's words (improve or own), or None."""
    for r in daily.db().execute("SELECT day FROM runs WHERE state='making' ORDER BY day DESC"):
        p, h = state(r["day"])
        if h and h["status"] in ("improve", "own"):
            return r["day"]
    return None


def on_text(day, text):
    p, h = state(day)
    if h["status"] == "own":
        say = own_text(text)
        h.update(status="chosen", choice={"n": 0, "say": say, "by": "own"})
        save(p, h)
        if h.get("msg"):
            telegram.clear_buttons(h["msg"])
        return telegram.send(f"Your open: {say}\nVoicing the episode now.")
    m = re.match(r"\s*#?(\d{1,2})\b[\s:.-]*(.*)", text, re.S)
    n, words = (int(m.group(1)), m.group(2).strip()) if m and 1 <= int(m.group(1)) <= len(h["hooks"]) else (1, text.strip())
    h.update(status="improve-ready", improve={"n": n, "words": words or text.strip()})
    save(p, h)
    return telegram.send(f"Rewriting hook {n} with your words. The new list comes in a minute.")


def main():
    from frameflow import show
    ap = argparse.ArgumentParser(description="The hook card")
    ap.add_argument("cmd", choices=["options"])
    ap.add_argument("out")
    a = ap.parse_args()
    out = Path(a.out)
    script = json.loads((out / "script.json").read_text())
    data = json.loads((out / "research.json").read_text())
    for i, h in enumerate(options(script, data), 1):
        print(f"{i:2}. [{h['score']}] {h['family']:15} {h['say']}")


if __name__ == "__main__":
    main()
