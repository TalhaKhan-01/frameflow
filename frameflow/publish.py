"""Publishing (manual uploads, by decision) and the feedback loop.

    frameflow publish <video-id>                 approved videos only: out/<id>/publish.md (titles, descriptions, tags, captions)
    frameflow posted <video-id> <yt-url> <ig-url> record where it went live (both URLs must answer)
    frameflow stats <video-id> [--avg-viewed 72 --swiped 35 --ig-plays 1200 --ig-shares 14 --ig-saves 9 ...]
                                                 48 h stats: YouTube public counts fetched; private numbers typed from Studio/Insights
    frameflow learn                              weekly report: top vs bottom videos -> vault/Docs/Week <n> Learnings.md
"""
import datetime as dt
import json
import re
import urllib.request
from pathlib import Path

from frameflow import ideas, llm, videos

ROOT = Path(__file__).resolve().parent.parent
LIMITS = {"yt_title": 100, "yt_description": 5000, "yt_tags_total": 500, "ig_caption": 2200, "ig_hashtags": 5}

STATS_SCHEMA = """
CREATE TABLE IF NOT EXISTS stats (
  video_id TEXT, platform TEXT, taken_at TEXT, views INTEGER, likes INTEGER, comments INTEGER, shares INTEGER,
  saves INTEGER, avg_viewed REAL, swiped REAL, follows INTEGER, raw TEXT);
"""

PACK_SYSTEM = """You write upload metadata for Frameflow Shorts (English, India-first, tech/AI/money).
YouTube title: <= 60 characters, the hook's stake, no clickbait the video doesn't pay off, no emojis.
YouTube description: 2-3 short lines on what the video shows, then 'Sources:' with every source URL, then 3 hashtags including #Shorts.
Tags: 8-15 short search phrases. Instagram caption: hook line, one line of context, a question to the viewer, then 4-5 hashtags.
Pinned comment: one question that invites replies. Never add facts that are not in the script."""

PACK_SCHEMA = {"type": "object", "required": ["yt_title", "yt_description", "yt_tags", "ig_caption", "pinned_comment"], "properties": {
    "yt_title": {"type": "string"}, "yt_description": {"type": "string"}, "yt_tags": {"type": "array", "items": {"type": "string"}},
    "ig_caption": {"type": "string"}, "pinned_comment": {"type": "string"}}}


def pack_problems(p):
    problems = []
    if len(p["yt_title"]) > 60:
        problems.append(f"YouTube title is {len(p['yt_title'])} characters (aim for at most 60, hard limit 100)")
    if len(p["yt_description"]) > LIMITS["yt_description"]:
        problems.append("YouTube description over 5,000 characters")
    if len(",".join(p["yt_tags"])) > LIMITS["yt_tags_total"]:
        problems.append("YouTube tags over 500 characters in total")
    if "#shorts" not in p["yt_description"].lower():
        problems.append("YouTube description lacks #Shorts")
    if len(p["ig_caption"]) > LIMITS["ig_caption"]:
        problems.append("Instagram caption over 2,200 characters")
    if len(re.findall(r"#\w+", p["ig_caption"])) > LIMITS["ig_hashtags"]:
        problems.append("Instagram caption has more than 5 hashtags")
    return problems


def publish(video_id):
    row = videos.require_approved(video_id)
    out = Path(row["out_dir"])
    plan = json.loads(Path(row["plan"]).read_text())
    sources = sorted({u for s in plan["scenes"] for u in s.get("sources", [])})
    script = "\n".join(s.get("say", "") for s in plan["scenes"])
    # CC BY music must be credited where viewers can see it: the skill appends these verbatim on every platform
    assets = json.loads((out / "assets.json").read_text()) if (out / "assets.json").exists() else []
    credits = [r["credit"] for r in assets if r.get("credit")]
    brief_file = ROOT / "briefs" / f"{Path(row['plan']).parent.name}.json"   # make2 names the output folder after the brief
    brief = json.loads(brief_file.read_text()) if brief_file.exists() else {}
    inp = {"title": plan["title"], "script": script, "lane": plan["lane"], "sources": sources, "credits": credits,
           "facts": [f["text"] for f in brief.get("facts", [])], "cautions": brief.get("cautions", [])}
    (out / "caption-input.json").write_text(json.dumps(inp, ensure_ascii=False, indent=1))
    import os
    import subprocess
    r = subprocess.run(["python3", "-I", str(CAPTION), "--project", str(ROOT), "write", str(out / "caption-input.json"), "--out", str(out / "caption-pack.json")],
                       capture_output=True, text=True, timeout=1800, env=dict(os.environ, CLAUDE_CONFIG_DIR=llm.CONFIG_DIR))
    if r.returncode:
        raise SystemExit(f"social-caption failed: {(r.stderr or r.stdout)[-600:]}")
    p = json.loads((out / "caption-pack.json").read_text())
    problems = p.get("problems", []) + pack_problems(p)
    report = json.loads((out / "report.json").read_text()) if (out / "report.json").exists() else {}
    p["cover"], p["cover_at"] = report.get("cover"), report.get("cover_at")
    md = [f"# Publish pack: {plan['title']}", "", f"Video file: `{out / 'final.mp4'}` ({row['lane']})", "",
          *([f"Cover: `{p['cover']}` (frame at {p['cover_at']:.2f} s)", ""] if p.get("cover") else []),
          "## YouTube Shorts", f"**Title** ({len(p['yt_title'])} chars): {p['yt_title']}", "", "**Description:**", "", p["yt_description"], "",
          f"**Tags:** {', '.join(p['yt_tags'])}", "", f"**Pinned comment:** {p['pinned_comment']}", "",
          "## Instagram Reels", "**Caption:**", "", p["ig_caption"], "",
          "## Facebook Reels", "**Caption:**", "", p.get("fb_caption", p["ig_caption"]), "",
          "## Upload checklist",
          "- [ ] YouTube Studio → Create → Upload → final.mp4; paste title, description, tags; audience: not made for kids",
          "- [ ] 'Altered or synthetic content': the narration voice is AI-generated; tick it if YouTube's question applies to this video",
          "- [ ] YouTube thumbnail: cover.png (or pick the cover frame in Studio)",
          "- [ ] Instagram → New Reel → final.mp4; paste caption; turn on 'Also share to feed'; cover: the end card's cover frame",
          "- [ ] Pin the comment on both platforms",
          f"- [ ] Then record the links: `uv run frameflow posted {video_id} <youtube-url> <instagram-url>`"]
    if problems:
        md += ["", "## Fix before posting", *[f"- {x}" for x in problems]]
    (out / "publish.md").write_text("\n".join(md) + "\n")
    (out / "publish.json").write_text(json.dumps(p, ensure_ascii=False, indent=1))
    return {"pack": str(out / "publish.md"), "problems": problems}


UPLOADER = Path.home() / "Talha_Khan" / "Claude" / "skills" / "social-upload" / "scripts"
CAPTION = Path.home() / "Talha_Khan" / "Claude" / "skills" / "social-caption" / "scripts" / "caption.py"


def upload(video_id, platforms=("youtube", "instagram", "facebook"), privacy="public"):
    """Approved videos only: post with the social-upload skill (API) or The Pilot (frameflow.pilot), record the links.
    Each platform is tried on its own, so one failure doesn't block the others; results say what happened."""
    import subprocess
    row = videos.require_approved(video_id)
    out = Path(row["out_dir"])
    if not (out / "publish.json").exists():
        publish(video_id)
    p = json.loads((out / "publish.json").read_text())
    (out / "instagram-caption.txt").write_text(p["ig_caption"])
    (out / "facebook-caption.txt").write_text(p.get("fb_caption", p["ig_caption"]))
    report = json.loads((out / "report.json").read_text()) if (out / "report.json").exists() else {}
    mode = json.loads((ROOT / "research" / "social-upload.json").read_text()).get("youtube_mode", "api")
    results = {}

    def run(cmd, timeout=3600):
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=ROOT)
        if r.returncode:
            raise RuntimeError((r.stderr or r.stdout).strip()[-600:])
        return json.loads(r.stdout[r.stdout.rindex("{"):])

    pilot = ["uv", "run", "python", "-m", "frameflow.pilot"]
    # Facebook first: its Reel gives Instagram a public video URL, so Instagram posts by API with the caption as data
    platforms = sorted(platforms, key=lambda x: {"facebook": 0, "youtube": 1, "instagram": 2}.get(x, 3))
    for platform in platforms:
        try:
            if platform == "youtube" and mode == "studio":
                results["youtube"] = run(pilot + ["youtube", video_id])
            elif platform == "youtube":
                meta = {"title": p["yt_title"], "description": p["yt_description"], "tags": p["yt_tags"], "category": "28",
                        "privacy": privacy, "made_for_kids": False, "synthetic": True}
                (out / "youtube-meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1))
                results["youtube"] = run(["python3", "-I", str(UPLOADER / "youtube.py"), "--project", str(ROOT), "upload",
                                          str(out / "final.mp4"), str(out / "youtube-meta.json")])
            elif platform == "instagram":
                offset = ["--thumb-offset", str(int(report["cover_at"] * 1000))] if report.get("cover_at") else []
                src = (results.get("facebook") or {}).get("source")
                attempts = []
                if src:   # 1) the Facebook Reel's public video URL (no upload from here, caption as data)
                    attempts.append(["python3", "-I", str(UPLOADER / "instagram.py"), "--project", str(ROOT), "reel-url", src,
                                     str(out / "instagram-caption.txt"), *offset])
                attempts.append(["python3", "-I", str(UPLOADER / "instagram.py"), "--project", str(ROOT), "publish",   # 2) direct upload
                                 str(out / "final.mp4"), str(out / "instagram-caption.txt"), *offset])
                for cmd in attempts:
                    try:
                        results["instagram"] = run(cmd)
                        break
                    except RuntimeError as e:
                        results.setdefault("instagram_api_errors", []).append(str(e)[-300:])
                else:   # 3) last resort: the web (its caption can get lost, so the result says so)
                    results["instagram"] = run(pilot + ["instagram", video_id])
            elif platform == "facebook":
                try:
                    results["facebook"] = run(["python3", "-I", str(UPLOADER / "facebook.py"), "--project", str(ROOT), "publish",
                                               str(out / "final.mp4"), str(out / "facebook-caption.txt")])
                except RuntimeError as e:   # dead Meta token: post the Reel on the web as the Page
                    results["facebook_api_error"] = str(e)[-300:]
                    results["facebook"] = run(pilot + ["facebook", video_id])
        except Exception as e:
            results[platform] = {"error": str(e)[-600:]}
    yt = results.get("youtube") or {}
    if yt.get("url") and p.get("pinned_comment"):   # the pack's comment goes up under the Short (pinning stays a Studio click)
        try:
            vid = re.search(r"shorts/([A-Za-z0-9_-]{11})", yt["url"]).group(1)
            results["youtube_comment"] = run(["python3", "-I", str(UPLOADER / "youtube.py"), "--project", str(ROOT), "comment", vid,
                                              p["pinned_comment"]])
        except Exception as e:
            results["youtube_comment"] = {"error": str(e)[-300:]}
    (out / "upload.json").write_text(json.dumps(results, ensure_ascii=False, indent=1))
    links = {k: v["url"] for k, v in results.items() if isinstance(v, dict) and v.get("url")}
    con = videos.db()
    cols = {r[1] for r in con.execute("PRAGMA table_info(videos)")}
    if "facebook_url" not in cols:
        con.execute("ALTER TABLE videos ADD COLUMN facebook_url TEXT")
    con.execute("UPDATE videos SET youtube_url=COALESCE(?, youtube_url), instagram_url=COALESCE(?, instagram_url), "
                "facebook_url=COALESCE(?, facebook_url), updated_at=? WHERE id=?",
                (links.get("youtube"), links.get("instagram"), links.get("facebook"), videos.now(), video_id))
    if all(pl in links for pl in platforms):
        con.execute("UPDATE videos SET status='posted' WHERE id=?", (video_id,))
    con.commit()
    from frameflow import vaultnote
    vaultnote.safe_write(video_id)   # add the links to the video's vault page
    return results


def url_ok(url):
    try:
        req = urllib.request.Request(url, headers=ideas.UA, method="GET")
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status == 200
    except Exception:
        return False


def posted(video_id, yt_url, ig_url):
    videos.require_approved(video_id)
    bad = [u for u in (yt_url, ig_url) if not url_ok(u)]
    if bad:
        raise SystemExit(f"these links don't answer with 200 yet: {bad}")
    con = videos.db()
    con.execute("UPDATE videos SET status='posted', youtube_url=?, instagram_url=?, updated_at=? WHERE id=?",
                (yt_url, ig_url, videos.now(), video_id))
    con.commit()
    from frameflow import vaultnote
    vaultnote.safe_write(video_id)
    return {"video": video_id, "status": "posted"}


def youtube_public(url):
    m = re.search(r"(?:shorts/|v=|youtu\.be/)([A-Za-z0-9_-]{11})", url or "")
    if not m:
        return {}
    import importlib.util
    spec = importlib.util.spec_from_file_location("ns", Path.home() / "Talha_Khan/Claude/skills/niche-study/scripts/niche_study.py")
    ns = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ns)
    ns.PROJECT = ROOT
    items = ns.api("videos", part="statistics", id=m.group(1)).get("items", [])
    st = items[0]["statistics"] if items else {}
    return {"views": int(st.get("viewCount", 0)), "likes": int(st.get("likeCount", 0)), "comments": int(st.get("commentCount", 0))}


def stats(video_id, manual):
    con = videos.db()
    con.executescript(STATS_SCHEMA)
    row = con.execute("SELECT * FROM videos WHERE id=?", (video_id,)).fetchone()
    if not row or row["status"] != "posted":
        raise SystemExit(f"{video_id} is not posted yet")
    yt = youtube_public(row["youtube_url"])
    t = videos.now()
    con.execute("INSERT INTO stats VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (video_id, "youtube", t, yt.get("views"), yt.get("likes"), yt.get("comments"), manual.get("yt_shares"), None,
                 manual.get("avg_viewed"), manual.get("swiped"), manual.get("yt_subs"), json.dumps(yt)))
    con.execute("INSERT INTO stats VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (video_id, "instagram", t, manual.get("ig_plays"), manual.get("ig_likes"), manual.get("ig_comments"),
                 manual.get("ig_shares"), manual.get("ig_saves"), manual.get("ig_avg_watch"), None, manual.get("ig_follows"), "{}"))
    con.commit()
    return {"video": video_id, "youtube": yt, "manual": manual}


LEARN_SYSTEM = """You analyse a week of Frameflow Shorts results to improve the next week. Compare the best and worst videos on
retention (average % viewed, viewed-vs-swiped), shares/sends and follows, against how each was made (lane, hook, length, scenes, review scores).
Be concrete and evidence-based; with few videos, say what is noise. Propose at least 3 specific changes to the Quality Bar targets,
Script Rules or the writer prompt, each tied to the numbers."""

LEARN_SCHEMA = {"type": "object", "required": ["summary", "findings", "proposals"], "properties": {
    "summary": {"type": "string"}, "findings": {"type": "array", "items": {"type": "string"}},
    "proposals": {"type": "array", "minItems": 3, "items": {"type": "object", "required": ["change", "why"],
                  "properties": {"change": {"type": "string"}, "why": {"type": "string"}}}}}}


def learn(week=None):
    con = videos.db()
    con.executescript(STATS_SCHEMA)
    rows = con.execute("""SELECT v.id, v.lane, v.title, v.review_total, s.platform, s.views, s.likes, s.comments, s.shares, s.saves,
                          s.avg_viewed, s.swiped, s.follows FROM videos v JOIN stats s ON s.video_id = v.id WHERE v.status='posted'""").fetchall()
    if not rows:
        raise SystemExit("no posted videos with stats yet")
    data = []
    for r in rows:
        plan = json.loads(Path(con.execute("SELECT plan FROM videos WHERE id=?", (r["id"],)).fetchone()[0]).read_text())
        data.append({**dict(r), "hook": plan["scenes"][0].get("say"), "scenes": [s["type"] for s in plan["scenes"]]})
    out = llm.call("Results:\n" + json.dumps(data, ensure_ascii=False), LEARN_SYSTEM, LEARN_SCHEMA, model="sonnet",
                   purpose="learn", effort="medium")
    week = week or dt.date.today().isocalendar().week
    md = ["---", "type: doc", "status: draft", f"created: {dt.date.today().isoformat()}", "tags: [doc, learning]", "---",
          f"# Week {week} Learnings", "", out["summary"], "", "## Findings", *[f"- {f}" for f in out["findings"]], "",
          "## Proposed changes", *[f"- **{p['change']}**: {p['why']}" for p in out["proposals"]], "",
          "Inputs: [[Quality Bar]], [[Script Rules]], [[Lane Mix]]."]
    path = ROOT / "vault" / "Docs" / f"Week {week} Learnings.md"
    path.write_text("\n".join(md) + "\n")
    return {"report": str(path), "proposals": len(out["proposals"])}
