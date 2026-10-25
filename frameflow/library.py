"""Asset library: what past videos made that future videos can reuse (vault Decisions/Daily Automation.md, "assets").

    python -m frameflow.library extract <video_id>     pull a finished video's reusable assets into the library
    python -m frameflow.library suggest "<text>"       what the library would offer for a story (no model call)
    python -m frameflow.library stats

Stored in research/assets/ (small JSON lines, in git):
  knowledge.jsonl   sourced facts (knowledge cards): the researcher starts from them and re-checks each one
  hooks.jsonl       hooks a video wrote but didn't use, with their scores
  analogies.jsonl   everyday comparisons the narrator used
  scenes.jsonl      storyboard scene recipes (world, metaphor, template, data shape) with the visual score they earned
Quality guards: only videos that passed review (or were posted) feed the library; each asset keeps where it came from,
that video's scores, and when it was last used; suggestions skip anything used in the last VARIETY_DAYS days and are
offered as optional material, never as rules. Matching is keyword overlap, so serving costs no tokens.
"""
import datetime as dt
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIB = ROOT / "research" / "assets"
KINDS = ("knowledge", "hooks", "analogies", "scenes")
VARIETY_DAYS = {"hooks": 30, "analogies": 21, "scenes": 10, "knowledge": 0}
FRESH_DAYS = 30          # a knowledge card older than this is offered as "re-check the number"
STOP = set("""a an the and or but so to of in on at for with from by as is are was were be been it its this that these those
you your we our they their he she his her them i me my not no yes do does did can could will would should may might just than
then there here what which who whom why how when where all any each more most some such only own same very also into over
about after before because while during until up down out off again once said says one two new now get got make made like""".split())


def now():
    return dt.date.today().isoformat()


def path(kind):
    return LIB / f"{kind}.jsonl"


def load(kind):
    p = path(kind)
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()] if p.exists() else []


def save(kind, rows):
    LIB.mkdir(parents=True, exist_ok=True)
    path(kind).write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))


def keys(text):
    """Topic keywords: names and acronyms first (PHP, Microsoft), then other content words."""
    names = {w.lower() for w in re.findall(r"\b(?:[A-Z][a-zA-Z0-9]+|[A-Z]{2,}[0-9]*)\b", text)}
    words = {w for w in re.findall(r"[a-z][a-z0-9-]{2,}", text.lower()) if w not in STOP}
    return sorted(names | words)


def aid(kind, text):
    return kind[0] + hashlib.sha1(re.sub(r"\W+", " ", text.lower()).strip().encode()).hexdigest()[:10]


def _video(video_id):
    from frameflow import videos
    row = videos.db().execute("SELECT * FROM videos WHERE id=?", (video_id,)).fetchone()
    if not row:
        raise SystemExit(f"no video {video_id}")
    return row


EXTRACTED = LIB / "extracted.json"


def extracted():
    """Every video the library has processed (cleanup only touches these)."""
    return set(json.loads(EXTRACTED.read_text())) if EXTRACTED.exists() else set()


def _mark_extracted(video_id):
    LIB.mkdir(parents=True, exist_ok=True)
    EXTRACTED.write_text(json.dumps(sorted(extracted() | {video_id}), indent=1))


def extract(video_id):
    """Add a finished video's assets. Only videos that passed review or were posted feed the library."""
    row = _video(video_id)
    if not (row["review_pass"] or row["status"] in ("approved", "posted")):
        _mark_extracted(video_id)   # looked at: nothing worth keeping
        return {"skipped": f"{video_id} didn't pass review; nothing taken"}
    base = Path(row["plan"]).parent
    out = Path(row["out_dir"])
    rev = json.loads((out / "review.json").read_text()) if (out / "review.json").exists() else {}
    scores, total = rev.get("scores", {}), rev.get("total")
    origin = {"from": video_id, "review": total, "lane": row["lane"], "added": now()}
    added = {k: 0 for k in KINDS}

    def add(kind, item):
        rows = load(kind)
        if any(r["id"] == item["id"] for r in rows):
            return
        rows.append({**item, **origin, "used": []})
        save(kind, rows)
        added[kind] += 1

    brief_file = ROOT / "briefs" / f"{base.name}.json"
    brief = json.loads(brief_file.read_text()) if brief_file.exists() else {}
    for f in brief.get("facts", []):
        add("knowledge", {"id": aid("knowledge", f["text"] + f["source"]), "text": f["text"], "source": f["source"],
                          "also": f.get("also", []), "keys": keys(f["text"]), "verified": now(), "topic": brief.get("topic", "")[:160]})
    script_file = base / "writer" / "script.json"
    script = json.loads(script_file.read_text()) if script_file.exists() else {}
    opening = (script.get("beats") or [{}])[0].get("say", "")
    hooks_file = base / "writer" / "hooks.json"
    if hooks_file.exists():
        hk = json.loads(hooks_file.read_text())
        for h in hk.get("hooks", []):
            if h["line"][:30] in opening or h.get("total", 0) < 9:   # the used hook, or a weak one
                continue
            add("hooks", {"id": aid("hooks", h["line"]), "text": h["line"], "family": h.get("family"), "score": h.get("total"),
                          "keys": keys(h["line"] + " " + brief.get("topic", ""))})
    for b in script.get("beats", []):
        if "analogy" in b.get("devices", []):
            add("analogies", {"id": aid("analogies", b["say"]), "text": b["say"], "keys": keys(b["say"] + " " + brief.get("topic", ""))})
    sb_file = base / "director" / "storyboard.json"
    if sb_file.exists() and scores.get("visual_storytelling", 0) >= 1:
        sb = json.loads(sb_file.read_text())
        for sc in sb.get("scenes", []):
            said = " ".join(script["beats"][i]["say"] for i in sc.get("beats", []) if i < len(script.get("beats", [])))
            shape = {k: v for k, v in sc.get("data", {}).items() if k not in ("cues", "beats")}
            add("scenes", {"id": aid("scenes", sc["world"]), "template": sc["template"], "world": sc["world"], "metaphor": sc.get("metaphor"),
                           "why": sc.get("why", ""), "data": shape, "visual_score": scores.get("visual_storytelling"),
                           "keys": keys(said + " " + sc["world"] + " " + sc.get("why", ""))})
    _mark_extracted(video_id)
    return {"video": video_id, "added": added}


def _recent(item, days):
    if not days or not item.get("used"):
        return False
    return (dt.date.today() - dt.date.fromisoformat(item["used"][-1])).days < days


def suggest(text, kind, n=5, min_overlap=2):
    """Best-matching assets for a story text: by keyword overlap, recently used ones last and flagged."""
    want = set(keys(text))
    scored = []
    for item in load(kind):
        overlap = len(want & set(item.get("keys", [])))
        if overlap < min_overlap:
            continue
        recent = _recent(item, VARIETY_DAYS[kind])
        quality = item.get("review") or 0
        scored.append(((not recent, overlap, quality), item, recent))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [(item, recent) for _, item, recent in scored[:n]]


def material(text):
    """The optional material files the writer and director skills read (config material_file), for one story."""
    w, d = [], []
    for item, recent in suggest(text, "hooks", 4):
        w.append(f"- hook ({item['family']}, scored {item['score']}/14){' [recently used]' if recent else ''}: {item['text']}")
    for item, recent in suggest(text, "analogies", 4):
        w.append(f"- analogy{' [recently used]' if recent else ''}: {item['text']}")
    for item, recent in suggest(text, "scenes", 4):
        d.append(f"- scene recipe ({item['template']}, metaphor {item['metaphor']}, visual score {item['visual_score']}/2)"
                 f"{' [recently used]' if recent else ''}: {item['world']} Why it worked: {item['why']}")
    (ROOT / "research" / "material-writer.txt").write_text("\n".join(w) + ("\n" if w else ""))
    (ROOT / "research" / "material-director.txt").write_text("\n".join(d) + ("\n" if d else ""))
    return {"writer": len(w), "director": len(d)}


def known_facts(text, n=8):
    """Knowledge cards for the researcher: a head start, each to be re-checked (older ones flagged)."""
    out = []
    for item, _ in suggest(text, "knowledge", n, min_overlap=2):
        age = (dt.date.today() - dt.date.fromisoformat(item["verified"])).days
        out.append(f"- {item['text']} (source: {item['source']}; checked {item['verified']}"
                   + ("; numbers may be out of date, re-check" if age > FRESH_DAYS else "") + ")")
    return out


def mark_used(video_id):
    """After a script and storyboard exist: record which offered assets the video actually used (fuzzy match)."""
    import difflib
    row = _video(video_id)
    base = Path(row["plan"]).parent
    script = json.loads((base / "writer" / "script.json").read_text()) if (base / "writer" / "script.json").exists() else {"beats": []}
    said = " ".join(b["say"] for b in script["beats"]).lower()
    sb = json.loads((base / "director" / "storyboard.json").read_text()) if (base / "director" / "storyboard.json").exists() else {"scenes": []}
    used = []
    for kind in ("hooks", "analogies"):
        rows = load(kind)
        for r in rows:
            t = r["text"].lower()
            if r["from"] != video_id and (t[:40] in said or difflib.SequenceMatcher(None, t, said[:len(t) * 3]).ratio() > 0.8):
                r["used"].append(now())
                used.append(r["id"])
        save(kind, rows)
    rows = load("scenes")
    metaphors = {s.get("metaphor") for s in sb["scenes"]}
    for r in rows:
        if r["from"] != video_id and r.get("metaphor") in metaphors:
            r["used"].append(now())
            used.append(r["id"])
    save("scenes", rows)
    return used


def stats():
    return {k: len(load(k)) for k in KINDS}


def main():
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    if a[0] == "extract":
        print(json.dumps(extract(a[1]), indent=1))
    elif a[0] == "suggest":
        text = " ".join(a[1:])
        for kind in KINDS:
            for item, recent in suggest(text, kind, 3):
                print(f"[{kind}{', recent' if recent else ''}] {item.get('text') or item.get('world')}"[:200])
    elif a[0] == "stats":
        print(json.dumps(stats(), indent=1))
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
