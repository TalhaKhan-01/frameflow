"""48-hour stats, collected automatically and sent as a Telegram card; they also score the video's lessons.

    python -m frameflow.stats48 <video_id> [--no-send]

What each platform gives with the current permissions:
- YouTube: views, likes, comments (Data API, public counts). Watch-time and % viewed need the Analytics scope.
- Instagram: likes, comments (instagram_basic); plays, reach, saves, shares when instagram_manage_insights is granted.
- Facebook: the Reel's views/likes when the token can read them.
Anything a permission blocks is left out and named on the card, never guessed.
"""
import argparse
import json
import re
import statistics
import sys
from pathlib import Path

from frameflow import publish, telegram, videos

ROOT = Path(__file__).resolve().parent.parent
SKILL = Path.home() / "Talha_Khan" / "Claude" / "skills" / "social-upload" / "scripts"


def _ig():
    sys.path.insert(0, str(SKILL))
    import instagram
    return instagram


def youtube_stats(url, since):
    """Analytics API first (% viewed, average view seconds, watch time, shares, subs); public counts if it isn't on."""
    import subprocess
    m = re.search(r"(?:shorts/|v=|youtu\.be/)([A-Za-z0-9_-]{11})", url or "")
    if m:
        r = subprocess.run(["python3", "-I", str(SKILL / "youtube.py"), "--project", str(ROOT), "analytics", m.group(1),
                            "--since", since or "2026-01-01"], capture_output=True, text=True, timeout=120)
        if r.returncode == 0:
            d = json.loads(r.stdout)
            return {"views": d.get("views"), "avg_viewed_pct": d.get("averageViewPercentage"), "avg_view_s": d.get("averageViewDuration"),
                    "minutes_watched": d.get("estimatedMinutesWatched"), "likes": d.get("likes"), "shares": d.get("shares"),
                    "comments": d.get("comments"), "subs_gained": d.get("subscribersGained")}
    return publish.youtube_public(url)


def instagram_stats(url):
    ig = _ig()
    cfg = ig.config(str(ROOT))
    code = re.search(r"/(?:reel|p)/([A-Za-z0-9_-]+)", url or "")
    if not code:
        return {}, ["no Instagram link"]
    acc = ig.account(cfg)
    media = ig.req(cfg, "GET", ig.graph(cfg, f"{acc['ig_user_id']}/media"),
                   {"fields": "id,permalink,like_count,comments_count", "limit": 50}).get("data", [])
    m = next((x for x in media if code.group(1) in (x.get("permalink") or "")), None)
    if not m:
        return {}, ["Reel not found in the account's media"]
    out, missing = {"likes": m.get("like_count"), "comments": m.get("comments_count")}, []
    try:   # needs instagram_manage_insights
        ins = ig.req(cfg, "GET", ig.graph(cfg, f"{m['id']}/insights"), {"metric": "views,reach,saved,shares"}).get("data", [])
        for i in ins:
            out[{"saved": "saves"}.get(i["name"], i["name"])] = (i.get("values") or [{}])[0].get("value")
    except SystemExit:
        missing.append("Instagram views/reach/saves/shares (needs instagram_manage_insights)")
    return out, missing


def facebook_stats(video_dir):
    up = json.loads((video_dir / "upload.json").read_text()) if (video_dir / "upload.json").exists() else {}
    vid = (up.get("facebook") or {}).get("id")
    if not vid:
        return {}, ["no Facebook Reel id"]
    ig = _ig()
    cfg = ig.config(str(ROOT))
    try:
        d = ig.req(cfg, "GET", ig.graph(cfg, vid), {"fields": "views,likes.summary(true),comments.summary(true)"})
        return {"views": d.get("views"), "likes": (d.get("likes") or {}).get("summary", {}).get("total_count"),
                "comments": (d.get("comments") or {}).get("summary", {}).get("total_count")}, []
    except SystemExit:
        return {}, ["Facebook Reel stats (needs read_insights / pages_read_engagement on the Reel)"]


def collect(video_id, send=True):
    con = videos.db()
    con.executescript(publish.STATS_SCHEMA)
    row = con.execute("SELECT * FROM videos WHERE id=?", (video_id,)).fetchone()
    out = Path(row["out_dir"])
    t = videos.now()
    yt = youtube_stats(row["youtube_url"], row["updated_at"][:10] if row["updated_at"] else None)
    ins, missing = instagram_stats(row["instagram_url"]) if row["instagram_url"] else ({}, ["no Instagram link"])
    keys = row.keys()
    fb, fb_missing = facebook_stats(out) if "facebook_url" in keys and row["facebook_url"] else ({}, [])
    missing += fb_missing + ([] if "avg_viewed_pct" in yt else ["YouTube % viewed (the YouTube Analytics API isn't enabled)"])
    for platform, s in (("youtube", yt), ("instagram", ins), ("facebook", fb)):
        if s:
            con.execute("INSERT INTO stats VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                        (video_id, platform, t, s.get("views"), s.get("likes"), s.get("comments"), s.get("shares"), s.get("saves"),
                         s.get("avg_viewed_pct"), None, s.get("subs_gained"), json.dumps(s)))
    con.commit()
    verdict = score_lessons(video_id, out, yt.get("views"))
    lines = [f"48 h stats: {row['title']}"]
    for name, s in (("YouTube", yt), ("Instagram", ins), ("Facebook", fb)):
        if s:
            lines.append(f"{name}: " + ", ".join(f"{k} {v}" for k, v in s.items() if v is not None))
    if verdict:
        lines.append(verdict)
    if missing:
        lines.append("Not available yet: " + "; ".join(missing))
    if send:
        telegram.send("\n".join(lines))
    return {"youtube": yt, "instagram": ins, "facebook": fb, "missing": missing, "verdict": verdict}


def score_lessons(video_id, out, views):
    """Lessons that were in this video's prompts get credit if it beat the channel's median YouTube views so far."""
    used_file = out.parent / "lessons-used.json"
    if views is None or not used_file.exists():
        return ""
    con = videos.db()
    past = [r[0] for r in con.execute("SELECT MAX(views) FROM stats WHERE platform='youtube' AND video_id != ? GROUP BY video_id", (video_id,))
            if r[0] is not None]
    if len(past) < 3:
        return "Lessons not scored yet (need 3 earlier videos to compare)."
    from frameflow import lessons
    ids = [i for area in json.loads(used_file.read_text()).values() for i in area]
    med = statistics.median(past)
    lessons.score(ids, views >= med)
    return f"{'Above' if views >= med else 'Below'} the channel median ({med:.0f} views): {len(ids)} lesson(s) marked {'helped' if views >= med else 'hurt'}."


def main():
    ap = argparse.ArgumentParser(description="48-hour stats")
    ap.add_argument("video_id")
    ap.add_argument("--no-send", action="store_true")
    a = ap.parse_args()
    print(json.dumps(collect(a.video_id, not a.no_send), indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
