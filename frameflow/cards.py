"""Habit cards: news-first carousel posts (vault Wiki/Sources/Reputeforge Card Posts.md), approved on Telegram like the videos.

    python -m frameflow.cards topics                 send today's card topic options (recent stories + a fresh one)
    python -m frameflow.cards make <run>             brief -> slides -> PNGs -> caption -> preview album with Approve/Revise/Reject
    python -m frameflow.cards revise <run>           Talha's notes -> new slides -> new preview
    python -m frameflow.cards post <run>             Facebook and Instagram carousels (API; The Pilot via Business Suite if it fails) -> links

A run id is cards-<date>-<n>. Facts come only from a sourced brief (a past video's, which costs no research, or a new one);
every fact slide carries its source; slide 1 is a bold but true claim; the last slide is the follow slide.
"""
import datetime as dt
import html
import json
import sqlite3
import sys
from pathlib import Path

from frameflow import llm, telegram

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "frameflow.db"
OUT = ROOT / "out" / "cards"
TABLES = """CREATE TABLE IF NOT EXISTS card_runs (id TEXT PRIMARY KEY, state TEXT, options TEXT, chosen TEXT, brief TEXT, slides TEXT,
  caption TEXT, notes TEXT, revisions INTEGER DEFAULT 0, preview_msg INTEGER, links TEXT, log TEXT DEFAULT '', created_at TEXT, updated_at TEXT);"""


def db():
    DB.parent.mkdir(exist_ok=True)
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    con.executescript(TABLES)
    cols = {r[1] for r in con.execute("PRAGMA table_info(card_runs)")}
    for c in ("day", "post_at"):   # daily card posts ride along with the day's Short
        if c not in cols:
            con.execute(f"ALTER TABLE card_runs ADD COLUMN {c} TEXT")
    return con


def now():
    return dt.datetime.now().replace(microsecond=0).isoformat()


def get(run):
    r = db().execute("SELECT * FROM card_runs WHERE id=?", (run,)).fetchone()
    return dict(r) if r else None


def update(run, **kw):
    note = kw.pop("note", None)
    if note:
        kw["log"] = (get(run) or {}).get("log", "") + f"{now()} {note}\n"
    kw["updated_at"] = now()
    con = db()
    con.execute(f"UPDATE card_runs SET {', '.join(k + '=?' for k in kw)} WHERE id=?", (*kw.values(), run))
    con.commit()


def latest(states):
    rows = [dict(r) for r in db().execute("SELECT * FROM card_runs ORDER BY created_at DESC")]
    return next((r for r in rows if r["state"] in states), None)


# ---------- topics ----------

def topics():
    """Options: the two most recent video briefs (sourced already: no research) and one fresh story from today's ranked ideas."""
    briefs = sorted((ROOT / "briefs").glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:2]
    opts = []
    for b in briefs:
        d = json.loads(b.read_text())
        opts.append({"kind": "brief", "brief": str(b), "title": d["topic"][:140], "facts": len(d.get("facts", []))})
    try:
        from frameflow import daily
        fresh = daily.options_for(daily.lane_for(dt.date.today().isoformat()), 3)
        used = {o.get("title", "")[:40] for o in opts}
        f = next((x for x in fresh if x["title"][:40] not in used), None)
        if f:
            opts.append({"kind": "story", "title": f["title"], "url": f["url"], "summary": f.get("summary", ""), "lane": f.get("lane")})
    except Exception as e:
        print(f"fresh story: {e}", file=sys.stderr)
    day = dt.date.today().isoformat()
    n = 1 + db().execute("SELECT COUNT(*) FROM card_runs WHERE id LIKE ?", (f"cards-{day}-%",)).fetchone()[0]
    run = f"cards-{day}-{n}"
    con = db()
    con.execute("INSERT INTO card_runs (id, state, options, created_at, updated_at) VALUES (?,?,?,?,?)",
                (run, "topic-sent", json.dumps(opts, ensure_ascii=False), now(), now()))
    con.commit()
    lines = ["Habit card post (carousel) for today: pick a story, or paste a link.", ""]
    for i, o in enumerate(opts, 1):
        lines.append(f"{i}. {o['title']}")
        lines.append(f"   {'Ready: ' + str(o['facts']) + ' sourced facts from our video research' if o['kind'] == 'brief' else 'Fresh story: needs a few minutes of research'}")
        lines.append("")
    buttons = [[(str(i), f"cardpick:{run}:{i}") for i in range(1, len(opts) + 1)], [("Not today", f"cardskip:{run}")]]
    msg = telegram.send("\n".join(lines), buttons)
    update(run, preview_msg=msg, note=f"topics sent ({len(opts)})")
    return run


# ---------- slides ----------

SYSTEM = """You design one Instagram/Facebook carousel for Thirdspace, a daily news-explainer page for AI, tech and money
(narrator and mascot: Habit; audience: Indians aged 18-30, curious, most don't code). Craft: one idea per slide, read in about
3 seconds; very little text; the same rhythm on every slide; plain words with an Indian everyday analogy where it helps.
Slide 1 is the hook: a BOLD but TRUE claim, ideally with a number or a challenge ("This bug sat inside 7 of 10 websites for
14 years"). Then 3-5 slides that tell the story in order so a first-time reader can follow (each leads into the next), then
one closing slide with the takeaway or an honest question. Do not write a follow slide (it is added after you).
Slide types:
- hook: heading (max 70 chars), optional body (max 120)
- stat: heading (max 60), stat (the number as it should appear big, e.g. "69.3%", "14 years", "₹2,000"), body (max 120)
- fact: heading (max 60), body (max 170)
- compare: heading (max 60), left {label, value}, right {label, value} (labels max 24, values max 40)
- list: heading (max 60), items (2-5, each max 80; put the key term first, then a colon and the explanation)
- close: heading (max 70), body (max 140)
For every slide give highlight: 1-2 words or a short phrase copied exactly from its heading, to mark with a highlighter.
For every slide that states a fact, give fact_ids from the brief and source (the outlet name of the first fact's source).
Use ONLY the brief's facts; keep every number exactly; keep hedges ("so far", "as of"). Choose the format that fits:
story (what happened -> why it matters -> the number -> what's next), glossary of the story's terms, then-vs-now, myth-vs-fact."""

SLIDE = {"type": "object", "required": ["type", "heading", "highlight"], "properties": {
    "type": {"type": "string", "enum": ["hook", "stat", "fact", "compare", "list", "close"]},
    "heading": {"type": "string"}, "highlight": {"type": "array", "items": {"type": "string"}}, "body": {"type": "string"},
    "stat": {"type": "string"}, "items": {"type": "array", "items": {"type": "string"}},
    "left": {"type": "object", "properties": {"label": {"type": "string"}, "value": {"type": "string"}}},
    "right": {"type": "object", "properties": {"label": {"type": "string"}, "value": {"type": "string"}}},
    "fact_ids": {"type": "array", "items": {"type": "string"}}, "source": {"type": "string"}}}
SCHEMA = {"type": "object", "required": ["format", "title", "slides"], "properties": {
    "format": {"type": "string"}, "title": {"type": "string"}, "slides": {"type": "array", "minItems": 4, "maxItems": 7, "items": SLIDE}}}


def brief_for(run):
    r = get(run)
    chosen = json.loads(r["chosen"])
    if chosen["kind"] == "brief":
        return Path(chosen["brief"])
    from frameflow import brief
    return brief.build(chosen["url"], chosen.get("title", ""), chosen.get("lane", ""), chosen.get("summary", ""))


def write_slides(brief, notes=""):
    facts = "\n".join(f"[{f['id']}] {f['text']} (source: {f['source']})" for f in brief["facts"])
    from frameflow import lessons
    prompt = (f"TOPIC: {brief['topic']}\nANGLE: {brief.get('angle_hint', '')}\nFACTS:\n{facts}\nCAUTIONS:\n"
              + "\n".join(f"- {c}" for c in brief.get("cautions", []))
              + (f"\n\nTHE OWNER ASKS FOR THESE CHANGES:\n{notes}" if notes else "") + "\n\nDesign the carousel.")
    return llm.call(prompt, SYSTEM, SCHEMA, model="sonnet", purpose="cards:slides", effort="medium", timeout=900)


# ---------- render (Paper Press, 1080x1350) ----------

FONTS = ROOT / "scenes" / "_shared" / "vendor" / "fonts"
MARKS = ["rgba(245,200,75,.65)", "rgba(150,215,140,.65)", "rgba(240,150,190,.55)", "rgba(120,210,230,.6)", "rgba(190,160,240,.6)"]
CSS = f"""
@font-face {{ font-family: Serif; src: url('file://{FONTS}/fraunces-latin-wght-normal.woff2'); font-weight: 100 900; }}
@font-face {{ font-family: Sans; src: url('file://{FONTS}/inter-latin-wght-normal.woff2'); font-weight: 100 900; }}
@font-face {{ font-family: Hand; src: url('file://{FONTS}/kalam-latin-700-normal.woff2'); font-weight: 700; }}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ width: 1080px; height: 1350px; background: #f3eee4; color: #16141c; font-family: Sans; position: relative; overflow: hidden;
  background-image: radial-gradient(rgba(0,0,0,.035) 1px, transparent 1.2px), radial-gradient(rgba(0,0,0,.025) 1px, transparent 1.2px);
  background-size: 7px 7px, 11px 11px; background-position: 0 0, 3px 5px; }}
.top {{ position: absolute; top: 56px; left: 70px; right: 70px; display: flex; align-items: center; justify-content: space-between; }}
.mark {{ display: flex; align-items: center; gap: 16px; font: 700 34px Serif; }}
.mark .ring {{ width: 64px; height: 64px; border: 4px solid #16141c; border-radius: 50%; display: flex; align-items: center; justify-content: center;
  font: 800 40px Serif; position: relative; background: #fbf8f1; }}
.mark .ring i {{ position: absolute; width: 11px; height: 11px; background: #c8372a; border-radius: 50%; right: 13px; bottom: 15px; }}
.num {{ font: 600 28px Sans; color: #5d564b; }}
.page {{ position: absolute; top: 170px; bottom: 150px; left: 80px; right: 80px; display: flex; flex-direction: column; justify-content: center; gap: 44px; }}
h1 {{ font: 800 76px/1.12 Serif; letter-spacing: -0.5px; }}
h1.big {{ font-size: 92px; text-align: center; }}
mark {{ background: linear-gradient(transparent 52%, var(--m) 52%, var(--m) 92%, transparent 92%); color: inherit; padding: 0 4px; }}
.body {{ font: 500 40px/1.45 Sans; color: #2b2830; }}
.body.center {{ text-align: center; }}
.stat {{ font: 800 210px/1 Serif; color: #c8372a; text-align: center; letter-spacing: -4px; }}
.cmp {{ display: grid; grid-template-columns: 1fr auto 1fr; gap: 30px; align-items: stretch; }}
.cmp .c {{ border: 4px solid #16141c; border-radius: 26px; padding: 40px 30px; background: #fbf8f1; text-align: center;
  box-shadow: 8px 8px 0 #16141c; display: flex; flex-direction: column; justify-content: center; gap: 22px; }}
.cmp .l {{ font: 700 34px Sans; color: #5d564b; text-transform: uppercase; letter-spacing: 2px; }}
.cmp .v {{ font: 800 52px/1.15 Serif; }}
.cmp .vs {{ font: 700 54px Hand; color: #c8372a; align-self: center; }}
ol {{ list-style: none; display: flex; flex-direction: column; gap: 30px; }}
ol li {{ font: 500 38px/1.38 Sans; padding-left: 78px; position: relative; }}
ol li b {{ font-weight: 800; }}
ol li::before {{ content: attr(data-n); position: absolute; left: 0; top: -2px; width: 56px; height: 56px; border: 3px solid #16141c;
  border-radius: 50%; font: 800 30px/50px Serif; text-align: center; background: #fbf8f1; }}
.foot {{ position: absolute; bottom: 60px; left: 80px; right: 80px; display: flex; justify-content: space-between; font: 500 26px Sans; color: #5d564b; }}
.foot b {{ color: #16141c; font-weight: 700; }}
.swipe {{ font: 700 34px Hand; color: #c8372a; text-align: right; }}
.follow {{ align-items: center; text-align: center; }}
.follow .ring {{ width: 230px; height: 230px; border-width: 9px; font-size: 140px; }}
.follow .ring i {{ width: 34px; height: 34px; right: 46px; bottom: 52px; }}
"""


def esc(s):
    return html.escape(s or "")


def marked(text, phrases, k=0):
    out = esc(text)
    for j, p in enumerate(phrases[:2]):
        p = esc(p.strip())
        if p and p in out:
            out = out.replace(p, f'<mark style="--m:{MARKS[(k + j) % len(MARKS)]}">{p}</mark>', 1)
    return out


def slide_html(s, i, n, handle, tag):
    top = (f'<div class="top"><div class="mark"><div class="ring">h<i></i></div>Habit</div>'
           f'<div class="num">{i}/{n}</div></div>')
    foot_src = f'Source: <b>{esc(s.get("source"))}</b>' if s.get("source") else ""
    foot = f'<div class="foot"><span>{foot_src}</span><span>{esc(handle)}</span></div>'
    h = marked(s["heading"], s.get("highlight", []), i)
    t = s["type"]
    if t == "hook":
        inner = f'<h1 class="big">{h}</h1>' + (f'<div class="body center">{esc(s.get("body"))}</div>' if s.get("body") else "") + \
                '<div class="swipe">swipe →</div>'
    elif t == "stat":
        inner = f'<h1>{h}</h1><div class="stat">{esc(s.get("stat"))}</div>' + (f'<div class="body">{esc(s.get("body"))}</div>' if s.get("body") else "")
    elif t == "compare":
        L, R = s.get("left") or {}, s.get("right") or {}
        inner = (f'<h1>{h}</h1><div class="cmp"><div class="c"><div class="l">{esc(L.get("label"))}</div><div class="v">{esc(L.get("value"))}</div></div>'
                 f'<div class="vs">vs</div><div class="c"><div class="l">{esc(R.get("label"))}</div><div class="v">{esc(R.get("value"))}</div></div></div>')
    elif t == "list":
        items = []
        for k, it in enumerate(s.get("items", [])[:5], 1):
            term, sep, rest = it.partition(":")
            items.append(f'<li data-n="{k}"><b>{esc(term)}</b>{":" + esc(rest) if sep else ""}</li>')
        inner = f'<h1>{h}</h1><ol>{"".join(items)}</ol>'
    elif t == "follow":
        inner = (f'<div class="mark" style="flex-direction:column;gap:30px"><div class="ring">h<i></i></div></div>'
                 f'<h1 class="big">{h}</h1><div class="body center">{esc(s.get("body"))}</div>')
        return f'<html><head><style>{CSS}</style></head><body><div class="page follow">{inner}</div>{foot}</body></html>'
    else:   # fact, close
        inner = f'<h1>{h}</h1>' + (f'<div class="body">{esc(s.get("body"))}</div>' if s.get("body") else "")
    return f'<html><head><style>{CSS}</style></head><body>{top}<div class="page">{inner}</div>{foot}</body></html>'


def render(slides, out_dir):
    from playwright.sync_api import sync_playwright
    cap = json.loads((ROOT / "research" / "social-caption.json").read_text())
    handle, tag = cap.get("handle", ""), cap.get("channel_tag", "")
    full = slides + [{"type": "follow", "heading": "New habit every day", "highlight": ["habit"],
                      "body": f"Follow {handle} for tech, AI and money, explained simply. {tag}"}]
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome", headless=True)
        page = b.new_page(viewport={"width": 1080, "height": 1350}, device_scale_factor=1)
        for i, s in enumerate(full, 1):
            page.set_content(slide_html(s, i, len(full), handle, tag), wait_until="load")
            page.evaluate("document.fonts.ready")
            page.wait_for_timeout(150)
            path = out_dir / f"slide-{i:02d}.png"
            page.screenshot(path=str(path))
            paths.append(path)
        b.close()
    return paths


def caption(brief, deck, out_dir):
    """Post text through the social-caption skill (same rules as the videos: 5 Instagram tags, 10+ on Facebook)."""
    import os
    import subprocess
    text = "\n".join(s["heading"] + (". " + s.get("body", "") if s.get("body") else "") + (" " + s.get("stat", "") if s.get("stat") else "")
                     + (" " + "; ".join(s.get("items", [])) if s.get("items") else "") for s in deck["slides"])
    inp = {"title": deck["title"], "script": text, "lane": brief.get("lane", ""), "facts": [f["text"] for f in brief["facts"]],
           "cautions": brief.get("cautions", []), "sources": sorted({f["source"] for f in brief["facts"]})}
    (out_dir / "caption-input.json").write_text(json.dumps(inp, ensure_ascii=False, indent=1))
    skill = Path.home() / "Talha_Khan" / "Claude" / "skills" / "social-caption" / "scripts" / "caption.py"
    r = subprocess.run(["python3", "-I", str(skill), "--project", str(ROOT), "write", str(out_dir / "caption-input.json"), "--out",
                        str(out_dir / "caption-pack.json")], capture_output=True, text=True, timeout=1200,
                       env=dict(os.environ, CLAUDE_CONFIG_DIR=llm.CONFIG_DIR))
    if r.returncode:
        raise RuntimeError(f"social-caption: {(r.stderr or r.stdout)[-400:]}")
    return json.loads((out_dir / "caption-pack.json").read_text())


def make(run, notes=""):
    r = get(run)
    update(run, state="making", note="making slides" + (" (revision)" if notes else ""))
    bpath = Path(r["brief"]) if r.get("brief") else brief_for(run)
    update(run, brief=str(bpath))
    brief = json.loads(bpath.read_text())
    deck = write_slides(brief, notes)
    out = OUT / run
    for old in out.glob("slide-*.png"):
        old.unlink()
    paths = render(deck["slides"], out)
    pack = caption(brief, deck, out)
    (out / "deck.json").write_text(json.dumps(deck, ensure_ascii=False, indent=1))
    update(run, slides=json.dumps(deck, ensure_ascii=False), caption=json.dumps(pack, ensure_ascii=False), note=f"{len(paths)} slides rendered")
    preview(run)


def make_for_day(day, brief_path):
    """The daily card post: made from the same researched brief as the day's Short, posted with it at the post time."""
    run = f"cards-{day}"
    con = db()
    con.execute("DELETE FROM card_runs WHERE id=?", (run,))
    con.execute("INSERT INTO card_runs (id, state, options, chosen, brief, day, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?)",
                (run, "picked", "[]", json.dumps({"kind": "brief", "brief": str(brief_path)}), str(brief_path), day, now(), now()))
    con.commit()
    make(run)
    return run


def queue_or_post(run):
    """Approve: a daily card post waits for the day's post time (like the Short); a one-off card posts at once."""
    from frameflow import daily
    r = get(run)
    if r.get("day"):
        slot = daily.at(r["day"], daily.cfg()["post_at"])
        if dt.datetime.now() < slot:
            update(run, state="queued", post_at=slot.isoformat(), note=f"approved; post at {slot}")
            return f"Approved. The card post goes out with the Short at {slot.strftime('%H:%M on %a %d %b')}."
    update(run, state="posting", note="approved; posting now")
    spawn("post", run)
    return "Approved. Posting the carousel on Instagram and Facebook now."


def preview(run):
    r = get(run)
    out = OUT / run
    paths = sorted(out.glob("slide-*.png"))
    pack = json.loads(r["caption"])
    telegram.send_album(paths, caption=f"Habit card post: {json.loads(r['slides'])['title']}")
    when = "with the Short at the post time" if r.get("day") else "now"
    msg = telegram.send("Caption (Instagram):\n\n" + pack["ig_caption"][:3500] + f"\n\nApprove to post it {when} on Instagram and Facebook.",
                        [[("✅ Approve", f"cardok:{run}")], [("✏️ Revise", f"cardrev:{run}"), ("❌ Reject", f"cardno:{run}")]])
    update(run, state="preview-sent", preview_msg=msg, note="preview sent")


def post(run):
    import os
    import subprocess
    r = get(run)
    out = OUT / run
    paths = [str(p) for p in sorted(out.glob("slide-*.png"))]
    pack = json.loads(r["caption"])
    (out / "ig.txt").write_text(pack["ig_caption"])
    (out / "fb.txt").write_text(pack.get("fb_caption", pack["ig_caption"]))
    update(run, state="posting", note="posting")
    links, errors = {}, {}
    up = Path.home() / "Talha_Khan" / "Claude" / "skills" / "social-upload" / "scripts"
    try:
        p = subprocess.run(["python3", "-I", str(up / "facebook.py"), "--project", str(ROOT), "photos", str(out / "fb.txt"), *paths],
                           capture_output=True, text=True, timeout=900)
        if p.returncode:
            raise RuntimeError((p.stderr or p.stdout)[-400:])
        links["facebook"] = json.loads(p.stdout[p.stdout.rindex("{"):])["url"]
    except Exception as e:
        errors["facebook"] = str(e)[-300:]
    try:   # Instagram API, images hosted on the Facebook Page; the caption travels as data (the web composer dropped it)
        p = subprocess.run(["python3", "-I", str(up / "instagram.py"), "--project", str(ROOT), "carousel", str(out / "ig.txt"), *paths],
                           capture_output=True, text=True, timeout=1800)
        if p.returncode:
            raise RuntimeError((p.stderr or p.stdout)[-400:])
        links["instagram"] = json.loads(p.stdout[p.stdout.rindex("{"):])["url"]
    except Exception as e:
        errors["instagram"] = str(e)[-300:]
    if errors:   # dead Meta token: The Pilot posts what's missing through Business Suite (captions checked, links matched)
        caps = [a for k, f in (("facebook", "fb.txt"), ("instagram", "ig.txt")) if k in errors for a in (f"--{k[:2]}-caption", str(out / f))]
        try:
            p = subprocess.run(["uv", "run", "python", "-m", "frameflow.pilot", "photos", *paths, *caps],
                               capture_output=True, text=True, timeout=2400, cwd=ROOT)
            if p.returncode:
                raise RuntimeError((p.stderr or p.stdout)[-400:])
            got = json.loads(p.stdout[p.stdout.rindex("{"):])
            for k, v in got.items():
                links[k] = v
                errors.pop(k, None)
        except Exception as e2:
            errors = {k: f"API: {v[-150:]}; Pilot: {str(e2)[-150:]}" for k, v in errors.items()}
    update(run, state="posted" if not errors else "failed", links=json.dumps(links), note=f"posted {links} errors {list(errors)}")
    telegram.send("Card post live:\n" + "\n".join(f"{k.capitalize()}: {v}" for k, v in links.items())
                  + ("\nNot posted: " + "; ".join(f"{k}: {v[:150]}" for k, v in errors.items()) if errors else ""))
    from frameflow import webexport
    update(run, note="studio: " + webexport.refresh("card post " + run))


def spawn(step, run):
    import subprocess
    (ROOT / "logs").mkdir(exist_ok=True)
    log = open(ROOT / "logs" / f"{run}-{step}.log", "a")
    subprocess.Popen(["uv", "run", "python", "-m", "frameflow.cards", step, run], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                     start_new_session=True)


def main():
    a = sys.argv[1:]
    step, run = (a + [None, None])[:2]
    try:
        if step == "topics":
            print(topics())
        elif step == "make":
            make(run)
        elif step == "revise":
            make(run, get(run)["notes"] or "")
        elif step == "post":
            post(run)
        else:
            sys.exit(__doc__)
    except Exception as e:
        if run and get(run):
            update(run, state="failed", note=f"{step} failed: {e}")
            telegram.send(f"The card post's {step} step failed: {str(e)[:300]}")
        raise


if __name__ == "__main__":
    main()
