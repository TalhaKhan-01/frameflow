"""Video notes in the vault: one readable page per video, generated from the pipeline's own files.

    python -m frameflow.vaultnote <video_id>      write or refresh vault/Wiki/Sources/Videos/<date> <title>.md
    python -m frameflow.vaultnote --all           every video in the database

The brief JSON (briefs/<slug>.json) stays the source of truth; the note is a view of it plus what happened to the video
(review score, links, 48 h stats, lessons it taught). It is rewritten whenever the pipeline calls write(), after
make2, after posting and after the 48 h stats, so it never drifts. Nothing here calls a model.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

from frameflow import videos

ROOT = Path(__file__).resolve().parent.parent
VAULT = ROOT / "vault"
FOLDER = VAULT / "Wiki" / "Sources" / "Videos"
LANE_NOTES = {"how-tech-works": "Lane Tech", "ai-news": "Lane AI", "ai-money": "Lane Money"}


def safe(text, n=70):
    return re.sub(r"\s+", " ", re.sub(r'[\\/:*?"<>|#^\[\]]', "", text)).strip()[:n].rstrip()


def yaml_str(s):
    return json.dumps(str(s), ensure_ascii=False)


def note_path(video_id, title):
    date = video_id[:10] if re.match(r"\d{4}-\d{2}-\d{2}", video_id) else "undated"
    existing = list(FOLDER.glob(f"{date} *.md"))
    for p in existing:   # keep the same file if the title was reworded
        if f"video_id: {yaml_str(video_id)}" in p.read_text():
            return p
    return FOLDER / f"{date} {safe(title)}.md"


def lane_note(lane):
    name = LANE_NOTES.get(lane, f"Lane {lane}")
    p = VAULT / "Wiki" / "Concepts" / f"{name}.md"
    if not p.exists():
        p.write_text(f"""---
type: concept
status: growing
created: {videos.now()[:10]}
tags: [concept, lane]
---
# {name}

One of the daily lanes in the [[Daily Automation]] rotation (tech → AI → money). Pipeline lane id: `{lane}`.

## Videos in this lane
```dataview
TABLE date AS "Date", review AS "Review", status AS "Status"
FROM "Wiki/Sources/Videos"
WHERE lane = "{lane}"
SORT date DESC
```
""")
    return name


def write(video_id):
    row = videos.db().execute("SELECT * FROM videos WHERE id=?", (video_id,)).fetchone()
    if not row:
        raise SystemExit(f"no video {video_id}")
    keys = row.keys()
    out = Path(row["out_dir"])
    slug = Path(row["plan"]).parent.name
    brief_file = ROOT / "briefs" / f"{slug}.json"
    brief = json.loads(brief_file.read_text()) if brief_file.exists() else {}
    rev = json.loads((out / "review.json").read_text()) if (out / "review.json").exists() else {}
    rep = json.loads((out / "report.json").read_text()) if (out / "report.json").exists() else {}
    pack = json.loads((out / "caption-pack.json").read_text()) if (out / "caption-pack.json").exists() else {}
    from frameflow import build
    tags = ["source", "video"] + [t.lstrip("#") for t in pack.get("hashtags", {}).get("instagram", [])[1:]]
    links = {k: row[f"{k}_url"] for k in ("youtube", "instagram", "facebook") if f"{k}_url" in keys and row[f"{k}_url"]}
    lane = lane_note(row["lane"])
    con = videos.db()
    stats = []
    try:
        stats = [dict(r) for r in con.execute("SELECT platform, MAX(taken_at) AS at, views, likes, comments, shares, saves, avg_viewed "
                                                "FROM stats WHERE video_id=? GROUP BY platform", (video_id,))]
    except Exception:
        pass
    from frameflow import lessons
    taught = [l for l in lessons.load() if l["evidence"].startswith(slug) or slug in l["evidence"][:80]]

    fm = [f"type: source", f"kind: video", f"video_id: {yaml_str(video_id)}", f"date: {video_id[:10]}", f"lane: {row['lane']}",
          f"status: {row['status']}", "review: " + yaml_str(f"{rev.get('total', '?')}/{rev.get('max', 20)}"),
          f"seconds: {rep.get('seconds', '')}"] + [f"{k}: {v}" for k, v in links.items()] + \
         [f"created: {video_id[:10]}", f"tags: [{', '.join(dict.fromkeys(tags))}]"]
    md = ["---", *fm, "---", f"# {row['title']}", "",
          f"[[{lane}]] video by [[Narrator Habit]], made by the [[Daily Automation]] pipeline. "
          f"Status **{row['status']}**, review **{rev.get('total', '?')}/{rev.get('max', 20)}**"
          + (f", {rep['seconds']:.0f} s" if rep.get("seconds") else "") + ".", ""]
    if links:
        md += ["## Posted", *[f"- {k.capitalize()}: {v}" for k, v in links.items()], ""]
    if brief:
        md += ["## Story", brief.get("topic", ""), ""]
        if brief.get("angle_hint"):
            md += [f"**Angle:** {brief['angle_hint']}", ""]
        md += ["## Facts and sources", "| # | Fact | Source |", "|---|---|---|"]
        for f in brief.get("facts", []):
            src = f"[{build.source_name(f['source'])}]({f['source']})" + "".join(f", [{build.source_name(u)}]({u})" for u in f.get("also", []))
            md.append(f"| {f.get('id', '')} | {f['text'].replace('|', '/')} | {src} |")
        md.append("")
        if brief.get("cautions"):
            md += ["## Cautions (what the video must not overstate)", *[f"- {c}" for c in brief["cautions"]], ""]
    if rev:
        md += ["## Review", f"Scores: " + ", ".join(f"{k} {v}" for k, v in rev.get("scores", {}).items()), ""]
        if rev.get("fixes"):
            md += ["Reviewer's notes:", *[f"- **{x['row']}**: {x['fix']}" for x in rev["fixes"]], ""]
    if stats:
        md += ["## Results (48 h)", "| Platform | Views | Likes | Comments | Shares | Saves | % viewed |", "|---|---|---|---|---|---|---|"]
        for s in stats:
            md.append(f"| {s['platform']} | {s['views'] or '-'} | {s['likes'] or '-'} | {s['comments'] or '-'} | {s['shares'] or '-'} | "
                      f"{s['saves'] or '-'} | {s['avg_viewed'] or '-'} |")
        md.append("")
    if taught:
        md += ["## Lessons it taught", *[f"- {l['id']} ({l['area']}, {l['status']}): {l['text']}" for l in taught], ""]
    if pack.get("ig_caption"):
        md += ["## Caption (Instagram)", "", *[f"> {l}" if l else ">" for l in pack["ig_caption"].splitlines()], ""]
    md += ["## Files", f"- Brief: `briefs/{slug}.json`", f"- Video and review: `{out.relative_to(ROOT)}/`", ""]
    FOLDER.mkdir(parents=True, exist_ok=True)
    path = note_path(video_id, row["title"])
    path.write_text("\n".join(md))
    commit(f"video note: {path.stem}")
    return path


def commit(message):
    """The vault keeps its own local git (never pushed); a failed commit never stops the pipeline."""
    try:
        subprocess.run(["git", "-C", str(VAULT), "add", "-A"], capture_output=True, timeout=30)
        subprocess.run(["git", "-C", str(VAULT), "commit", "-q", "-m", message], capture_output=True, timeout=30)
    except Exception:
        pass


def safe_write(video_id):
    try:
        return write(video_id)
    except Exception as e:
        print(f"vault note {video_id}: {e}", file=sys.stderr)


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: python -m frameflow.vaultnote <video_id> | --all")
    ids = [r["id"] for r in videos.db().execute("SELECT id FROM videos")] if sys.argv[1] == "--all" else [sys.argv[1]]
    for v in ids:
        print(safe_write(v))


if __name__ == "__main__":
    main()
