"""Script writer: one ranked idea -> a scene plan that passes the validator and the automatic Script Rules.

    frameflow script <idea-id> [--model sonnet]      writes plans/<plan-id>.json

Sonnet writes the script and scene plan from the idea and its source text, using only facts in that text.
If any check fails, one repair call gets the exact failures (at most one retry, then it gives up honestly).
"""
import datetime as dt
import html
import json
import re
import urllib.request
from pathlib import Path

from frameflow import ideas, llm, rules, scene_plan

ROOT = Path(__file__).resolve().parent.parent
PLANS = ROOT / "plans"

SYSTEM = """You write scripts for Frameflow: English YouTube Shorts / Instagram Reels about tech, AI and money for an India-first audience.
Output one scene plan as JSON. Every video is built from these scene templates (data fields in brackets):
- headline-reveal: kicker (<=32 chars, optional), lines (1-3 strings, each <=28 chars), highlight (optional exact substring of a line)
- stat-counter: value (number), prefix (optional, e.g. "₹"), suffix (optional, e.g. "%", " cr"), label (<=60 chars), kicker (optional), decimals (optional)
- comparison: kicker/title (optional), columns (2-4 objects: label <=24 chars, value string or number, note optional), highlight (optional index)
- chart: kind ("bar" or "line"), series (2-12 objects: label <=16 chars, value number), unit (optional), kicker/title (optional), highlight (optional index)
Rules (all must hold):
R1 scene 1's say line is the hook: lead with the biggest concrete number or comparison in the source (who is affected, how many, how much),
stated plainly, not hedged with 'may' unless the source is hedged. No greeting.
R2 every video starts speaking at once (scene 1 has a say line).
R3 one idea per video. R4 each say line <= 18 words, spoken English, contractions, talk to "you" where natural.
R5 total spoken length 30-50 seconds (about 2.8 words per second; aim for 90-130 words in total, 6-9 scenes).
R6 a new visual every few seconds: no scene longer than about 6 seconds of speech.
R7 every number in a say line also appears in that scene's data (shown, not only said).
R8 every scene stating a fact sets claim: true and lists source URLs (use the provided source URL).
R9 include an honest India angle when one exists. R10 mark the scene that answers the hook with payoff: true; it must start before 85% of the runtime.
R11 the second-to-last scene answers the hook in practical terms (what changes for you, what to do); the last say line is a question
to the viewer or a share prompt ("Send this to someone who...").
R12 no hype words unless the next line proves them. R13 in say lines, spell numbers and acronyms for the voice
("twenty thousand rupees", "G.S.T."); digits go only in data. R14 title <= 60 characters and contains the hook's stake.
Use ONLY facts present in the provided source text, title and summary. Never invent numbers. If the source lacks a figure,
build the scene around what it does say. Write in Indian English with ₹, lakh and crore where natural."""

PLAN_SCHEMA = {"type": "object", "required": ["id", "lane", "title", "scenes"], "properties": {
    "id": {"type": "string"}, "lane": {"type": "string", "enum": sorted(scene_plan.LANES)},
    "title": {"type": "string"}, "description": {"type": "string"},
    "scenes": {"type": "array", "minItems": 5, "maxItems": 11, "items": {"type": "object", "required": ["type", "say", "data"],
        "properties": {"type": {"type": "string", "enum": ["headline-reveal", "stat-counter", "comparison", "chart"]},
                       "say": {"type": "string"}, "data": {"type": "object"}, "claim": {"type": "boolean"},
                       "payoff": {"type": "boolean"}, "sources": {"type": "array", "items": {"type": "string"}}}}}}}


def source_text(url, limit=4000):
    """Readable paragraph text of an article (best effort; aggregator redirect pages give little)."""
    try:
        raw = ideas.fetch(url, timeout=20).decode("utf-8", "replace")
    except Exception:
        return ""
    paras = re.findall(r"<p[^>]*>(.*?)</p>", raw, re.S | re.I)
    text = " ".join(re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", p))).strip() for p in paras)
    return text[:limit]


def write(idea_id, model="sonnet"):
    con = ideas.db()
    idea = con.execute("SELECT * FROM ideas WHERE id=?", (idea_id,)).fetchone()
    if not idea:
        raise SystemExit(f"no idea {idea_id}")
    body = source_text(idea["url"])
    slug = re.sub(r"[^a-z0-9]+", "-", idea["title"].lower()).strip("-")[:48]
    plan_id = f"{dt.date.today().isoformat()}-{slug}"
    brief = (f"Idea #{idea['id']} (lane {idea['lane']}, score {idea['score']})\nTitle: {idea['title']}\nSource: {idea['source']} {idea['url']}\n"
             f"Summary: {idea['summary']}\nSuggested angle: {idea['angle']}\nSuggested hook: {idea['hook']}\nIndia angle: {idea['india_angle']}\n"
             f"Source text:\n{body or '(not available: use only the title and summary)'}\n\nUse id \"{plan_id}\".")
    plan = llm.call(brief, SYSTEM, PLAN_SCHEMA, model=model, purpose=f"script:{plan_id}", effort="medium")
    fails = rules.check(plan)
    attempts = 1
    if fails:
        attempts = 2
        fix = (f"{brief}\n\nYour previous plan:\n{json.dumps(plan, ensure_ascii=False)}\n\nIt fails these checks; fix every one and "
               f"return the full corrected plan:\n- " + "\n- ".join(fails))
        plan = llm.call(fix, SYSTEM, PLAN_SCHEMA, model=model, purpose=f"script-fix:{plan_id}", effort="medium")
        fails = rules.check(plan)
    plan["id"] = plan_id
    plan.setdefault("idea_id", idea_id)
    PLANS.mkdir(exist_ok=True)
    out = PLANS / f"{plan_id}.json"
    out.write_text(json.dumps(plan, ensure_ascii=False, indent=1) + "\n")
    con.execute("UPDATE ideas SET status=? WHERE id=?", ("scripted" if not fails else "script-failed", idea_id))
    con.commit()
    return {"plan": str(out), "attempts": attempts, "fails": fails, "seconds": round(scene_plan.total_seconds(plan), 1),
            "source_chars": len(body)}


def rewrite(plan_path, feedback, model="sonnet"):
    """One rewrite of an existing plan from review feedback (at most one per video, by policy)."""
    plan = json.loads(Path(plan_path).read_text())
    con = ideas.db()
    idea = con.execute("SELECT * FROM ideas WHERE id=?", (plan.get("idea_id"),)).fetchone()
    body = source_text(idea["url"]) if idea else ""
    prompt = (f"Source: {idea['url'] if idea else ''}\nSource text:\n{body or '(not available)'}\n\nCurrent plan:\n"
              f"{json.dumps(plan, ensure_ascii=False)}\n\nA reviewer asked for these fixes; apply all that the source supports, keep "
              f"every rule, keep the id \"{plan['id']}\", return the full plan:\n- " + "\n- ".join(feedback))
    new = llm.call(prompt, SYSTEM, PLAN_SCHEMA, model=model, purpose=f"script-rewrite:{plan['id']}", effort="medium")
    new["id"], new["idea_id"] = plan["id"], plan.get("idea_id")
    fails = rules.check(new)
    if fails:   # one repair for rule failures introduced by the rewrite
        new = llm.call(f"{prompt}\n\nYour rewrite fails these checks; fix them:\n- " + "\n- ".join(fails), SYSTEM, PLAN_SCHEMA,
                       model=model, purpose=f"script-rewrite-fix:{plan['id']}", effort="medium")
        new["id"], new["idea_id"] = plan["id"], plan.get("idea_id")
        fails = rules.check(new)
    Path(plan_path).write_text(json.dumps(new, ensure_ascii=False, indent=1) + "\n")
    return {"plan": str(plan_path), "fails": fails}
