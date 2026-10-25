"""Brief: turn a picked story (an idea row or a pasted link) into a sourced brief for the v2 writer.

    python -m frameflow.brief <url> [--title T] [--lane L] [--out briefs/<slug>.json]

The model researches with web search and fetch, then returns facts that each carry the URL that supports them.
Every source is fetched again here: a fact whose source doesn't load is dropped, and a brief with fewer than
8 sourced facts is refused, so nothing unsourced reaches the script.
"""
import argparse
import datetime as dt
import json
import re
import urllib.request
from pathlib import Path

from frameflow import llm

ROOT = Path(__file__).resolve().parent.parent
BRIEFS = ROOT / "briefs"
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Frameflow/0.1 (+personal research)"}
MIN_FACTS = 8

SYSTEM = """You are the researcher for a daily 50-90 second explainer channel (narrator: Habit; audience: Indians aged
18-30 who are curious about tech, AI and money, most don't code). Research the story with web search and fetch,
reading the original reporting and at least two independent outlets. Return a brief:
- topic: one sentence, what happened and why it matters now.
- audience: who is watching and what they already know.
- angle_hint: the most surprising true angle, a twist if the facts support one, and an Indian angle when real.
- facts: 12-20 short facts, each a single checkable claim with the exact URL of the page that states it (source),
  optional extra supporting URLs (also). Numbers exactly as the source gives them, with the date they refer to.
  Prefer the original source (company post, filing, paper, official statement) over aggregators.
- cautions: what must not be overstated (attempts vs confirmed harm, estimates, disputed claims, things not yet known).
- notes: tone ideas, an everyday analogy, a fair practical takeaway, an ending question.
Never invent a fact or a URL. If something is unclear or disputed, put it in cautions, not in facts.
If you could not read the sources (tools failed, pages blocked), return an empty facts list: never pad it with
facts about the brief itself."""

SCHEMA = {"type": "object", "required": ["topic", "audience", "angle_hint", "facts", "cautions", "notes"], "properties": {
    "topic": {"type": "string"}, "audience": {"type": "string"}, "angle_hint": {"type": "string"},
    "facts": {"type": "array", "maxItems": 24, "items": {"type": "object", "required": ["text", "source"], "properties": {
        "text": {"type": "string"}, "source": {"type": "string"}, "also": {"type": "array", "items": {"type": "string"}}}}},
    "cautions": {"type": "array", "items": {"type": "string"}}, "notes": {"type": "string"}}}


def slugify(text, n=6):
    words = re.findall(r"[a-z0-9]+", text.lower())
    return "-".join(words[:n]) or "story"


def loads(url, timeout=20):
    """True if the URL answers with a page (some sites refuse HEAD, so this is a small GET)."""
    try:
        req = urllib.request.Request(url, headers={**UA, "Range": "bytes=0-2048"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return 200 <= r.status < 400
    except Exception as e:   # 403 from bot walls still means the page exists
        return getattr(e, "code", None) in (401, 403, 429)


def build(url, title="", lane="", summary="", out=None, model="sonnet"):
    prompt = (f"Story to research ({dt.date.today().isoformat()}):\nTitle: {title or '(from the link)'}\nLink: {url}\n"
              f"Lane: {lane}\nWhat we know so far: {summary or '-'}\nWrite the brief.")
    b = llm.call(prompt, SYSTEM, SCHEMA, model=model, tools="WebSearch,WebFetch", purpose=f"brief:{slugify(title or url)}",
                 effort="medium", timeout=1500)
    if b["topic"].upper().startswith("UNVERIFIED") or any("NOT read" in f["text"] for f in b["facts"]):
        raise SystemExit("the researcher couldn't read the sources; no brief written")
    kept, dropped = [], []
    for f in b["facts"]:
        if loads(f["source"]):
            kept.append({"id": f"f{len(kept) + 1}", "text": f["text"], "source": f["source"],
                         **({"also": [u for u in f.get("also", []) if loads(u)]} if f.get("also") else {})})
        else:
            dropped.append(f["source"])
    if len(kept) < MIN_FACTS:
        raise SystemExit(f"only {len(kept)} facts have a source that loads (need {MIN_FACTS}); dropped: {dropped[:5]}")
    brief = {**b, "facts": kept, "lane": lane, "story_url": url,
             "notes": b["notes"] + (f"\n(Dropped {len(dropped)} fact(s) whose source didn't load.)" if dropped else "")}
    path = Path(out or BRIEFS / f"{dt.date.today().isoformat()}-{slugify(title or b['topic'])}.json")
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(brief, ensure_ascii=False, indent=1))
    return path


def main():
    ap = argparse.ArgumentParser(description="story link -> sourced brief")
    ap.add_argument("url")
    ap.add_argument("--title", default="")
    ap.add_argument("--lane", default="")
    ap.add_argument("--out")
    a = ap.parse_args()
    print(build(a.url, a.title, a.lane, out=a.out))


if __name__ == "__main__":
    main()
