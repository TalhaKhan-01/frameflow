"""Ideas: collect fresh topics from news and trend sources, then rank them in one batched model call.

    frameflow ideas collect            fetch sources (research/sources.json) into data/frameflow.db
    frameflow ideas rank [--hours 48]  one Haiku call ranks all fresh, unranked ideas (score, lane, angle, hook)
    frameflow ideas list [--top 15]    best ranked ideas not yet used
"""
import datetime as dt
import html
import json
import re
import sqlite3
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

from frameflow import llm, scene_plan

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "frameflow.db"
SOURCES = ROOT / "research" / "sources.json"
NICHE = ROOT / "research" / "niche-study.json"
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Frameflow/0.1 (+personal research)"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS ideas (
  id INTEGER PRIMARY KEY, source TEXT, title TEXT, url TEXT UNIQUE, summary TEXT, published TEXT,
  lane TEXT, fetched_at TEXT, status TEXT DEFAULT 'new',
  score INTEGER, angle TEXT, hook TEXT, india_angle TEXT, ranked_at TEXT);
"""


def db():
    DB.parent.mkdir(exist_ok=True)
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


def fetch(url, timeout=20):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def clean(text, limit=400):
    text = re.sub(r"<[^>]+>", " ", html.unescape(text or ""))
    return re.sub(r"\s+", " ", text).strip()[:limit]


def parse_feed(raw, name):
    root = ET.fromstring(raw)
    ns = {"a": "http://www.w3.org/2005/Atom"}
    items = []
    for it in root.iter("item"):
        items.append({"source": name, "title": clean(it.findtext("title"), 200), "url": (it.findtext("link") or "").strip(),
                      "summary": clean(it.findtext("description")), "published": it.findtext("pubDate") or ""})
    for it in root.findall("a:entry", ns):
        link = it.find("a:link", ns)
        items.append({"source": name, "title": clean(it.findtext("a:title", namespaces=ns), 200),
                      "url": link.get("href") if link is not None else "", "summary": clean(it.findtext("a:summary", namespaces=ns) or it.findtext("a:content", namespaces=ns)),
                      "published": it.findtext("a:updated", namespaces=ns) or ""})
    return [i for i in items if i["title"] and i["url"].startswith("http")]


def lane_of(title, summary, lanes):
    """First lane whose include words appear (whole word) in the title or summary; None if none match."""
    text = f"{title} {summary}".lower()
    best, hits = None, 0
    for lane, cfg in lanes.items():
        n = sum(1 for w in cfg.get("include", []) if re.search(r"(?<!\w)" + re.escape(w.lower()) + r"(?!\w)", text))
        if n > hits:
            best, hits = lane, n
    return best


def collect():
    src = json.loads(SOURCES.read_text())
    lanes = json.loads(NICHE.read_text())["lanes"]
    found, errors = [], []
    for f in src.get("rss", []):
        try:
            found += parse_feed(fetch(f["url"]), f["name"])
        except Exception as e:  # one broken feed must not stop the rest
            errors.append(f"{f['name']}: {e}")
    for q in src.get("google_news", []):
        url = "https://news.google.com/rss/search?" + urllib.parse.urlencode({"q": q + " when:2d", "hl": "en-IN", "gl": "IN", "ceid": "IN:en"})
        try:
            found += parse_feed(fetch(url), f"Google News: {q}")[:15]
        except Exception as e:
            errors.append(f"Google News {q}: {e}")
    if src.get("hacker_news_top"):
        try:
            ids = json.loads(fetch("https://hacker-news.firebaseio.com/v0/topstories.json"))[:src["hacker_news_top"]]
            for i in ids:
                it = json.loads(fetch(f"https://hacker-news.firebaseio.com/v0/item/{i}.json"))
                if it and it.get("url"):
                    found.append({"source": "Hacker News", "title": clean(it.get("title"), 200), "url": it["url"],
                                  "summary": f"{it.get('score', 0)} points, {it.get('descendants', 0)} comments", "published": str(it.get("time", ""))})
        except Exception as e:
            errors.append(f"Hacker News: {e}")
    if src.get("github_trending"):
        try:
            page = fetch("https://github.com/trending?since=daily").decode("utf-8", "replace")
            rows = page.split('class="Box-row"')[1:21]
            if not rows:
                raise ValueError("no Box-row entries: page layout changed")
            for row in rows:
                h = re.search(r'<h2[^>]*>.*?href="/([^"]+)"', row, re.S)
                d = re.search(r'<p class="[^"]*">(.*?)</p>', row, re.S)
                if h:
                    repo = h.group(1).strip()
                    found.append({"source": "GitHub Trending", "title": f"{repo} is trending on GitHub", "url": f"https://github.com/{repo}",
                                  "summary": clean(d.group(1) if d else ""), "published": dt.date.today().isoformat()})
        except Exception as e:
            errors.append(f"GitHub Trending: {e}")
    yt = src.get("youtube_most_popular")
    if yt:
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location("ns", Path.home() / "Talha_Khan/Claude/skills/niche-study/scripts/niche_study.py")
            ns = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(ns)
            ns.PROJECT = ROOT
            res = ns.api("videos", part="snippet", chart="mostPopular", **yt)  # 1 quota unit
            for it in res.get("items", []):
                found.append({"source": "YouTube trending (IN, Science & Tech)", "title": clean(it["snippet"]["title"], 200),
                              "url": f"https://www.youtube.com/watch?v={it['id']}", "summary": clean(it["snippet"].get("description"), 300),
                              "published": it["snippet"].get("publishedAt", "")})
        except Exception as e:
            errors.append(f"YouTube: {e}")
    con, now, added = db(), dt.datetime.now().replace(microsecond=0).isoformat(), 0
    seen_titles = {re.sub(r"\W+", " ", r[0].lower()).strip() for r in con.execute("SELECT title FROM ideas")}
    for i in found:
        key = re.sub(r"\W+", " ", i["title"].lower()).strip()
        if key in seen_titles:
            continue
        cur = con.execute("INSERT OR IGNORE INTO ideas (source, title, url, summary, published, lane, fetched_at) VALUES (?,?,?,?,?,?,?)",
                          (i["source"], i["title"], i["url"], i["summary"], i["published"], lane_of(i["title"], i["summary"], lanes), now))
        if cur.rowcount:
            added += 1
            seen_titles.add(key)
    con.commit()
    sources = sorted({i["source"].split(":")[0] for i in found})
    return {"found": len(found), "added": added, "sources": sources, "errors": errors}


RANK_SYSTEM = """You pick topics for Frameflow, an English YouTube Shorts / Instagram Reels channel about tech, AI and money, India-first audience.
Score each idea 0-100 for: timeliness, a concrete stake for the viewer (a number, comparison, or claim that can be proven),
an honest India angle, and whether it can be shown with motion graphics (charts, comparisons, numbers, headlines) instead of
someone else's footage. Drop gossip, pure opinion, deals/coupons, sensitive tragedies and anything that cannot be sourced.
Lanes: global-tech, india-tech, ai-news, dev-tools, ai-money, how-tech-works. Write the hook as the first spoken line:
at most 18 words, a concrete stake, no greeting. Return JSON only."""

RANK_SCHEMA = {"type": "object", "required": ["ideas"], "properties": {"ideas": {"type": "array", "items": {
    "type": "object", "required": ["id", "keep", "score", "lane", "angle", "hook", "india_angle"],
    "properties": {"id": {"type": "integer"}, "keep": {"type": "boolean"}, "score": {"type": "integer", "minimum": 0, "maximum": 100},
                   "lane": {"type": "string", "enum": sorted(scene_plan.LANES)}, "angle": {"type": "string"},
                   "hook": {"type": "string"}, "india_angle": {"type": "string"}}}}}}


def published_at(text):
    """Parse RSS (RFC 822), ISO 8601 or Unix-time strings; None when unknown."""
    from email.utils import parsedate_to_datetime
    text = (text or "").strip()
    try:
        if text.isdigit():
            return dt.datetime.fromtimestamp(int(text), dt.timezone.utc)
        if re.match(r"\d{4}-\d{2}-\d{2}", text):
            d = dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
            return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)
        return parsedate_to_datetime(text)
    except (ValueError, TypeError):
        return None


def rank(hours=48, keep=30, limit=200):
    """One Haiku call over every fresh, unranked idea; the model returns only the best `keep` (fewer output tokens)."""
    con = db()
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=hours)
    rows = [r for r in con.execute("SELECT id, source, title, summary, lane, published FROM ideas WHERE score IS NULL ORDER BY id DESC")
            if (published_at(r["published"]) or cutoff) >= cutoff][:limit]
    if not rows:
        return {"ranked": 0}
    listing = "\n".join(f"{r['id']} | {r['lane'] or '?'} | {r['source']} | {r['title']} | {r['summary'][:140]}" for r in rows)
    out = llm.call(f"Here are {len(rows)} fresh ideas (id | lane guess | source | title | summary). Return only the best {keep}, "
                   f"best first, with keep=true. Skip the rest.\n{listing}",
                   RANK_SYSTEM, RANK_SCHEMA, model="haiku", purpose="ideas.rank", effort="low")
    now = dt.datetime.now().replace(microsecond=0).isoformat()
    ids = {r["id"] for r in rows}
    n = 0
    for it in out["ideas"]:
        if it["id"] not in ids:
            continue
        con.execute("UPDATE ideas SET score=?, lane=?, angle=?, hook=?, india_angle=?, ranked_at=?, status=? WHERE id=?",
                    (it["score"] if it["keep"] else 0, it["lane"], it["angle"], it["hook"], it["india_angle"], now,
                     "new" if it["keep"] else "dropped", it["id"]))
        n += 1
    returned = {it["id"] for it in out["ideas"]}
    con.executemany("UPDATE ideas SET score=0, status='skipped', ranked_at=? WHERE id=?", [(now, r["id"]) for r in rows if r["id"] not in returned])
    con.commit()
    return {"ranked": n, "sent": len(rows), "skipped": len(rows) - len(returned & ids)}


def top(n=15):
    return [dict(r) for r in db().execute("SELECT * FROM ideas WHERE status='new' AND score > 0 ORDER BY score DESC LIMIT ?", (n,))]
