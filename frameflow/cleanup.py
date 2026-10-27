"""Disk cleanup for finished videos, after the asset library has taken what it reuses.

    python -m frameflow.cleanup <video_id> [--dry-run]     clean one video
    python -m frameflow.cleanup --all [--dry-run]           every video that is ready
    python -m frameflow.cleanup --report                    what each video folder holds and what cleanup would free

Two levels:
  rounds   as soon as a video exists (run after every make): earlier render rounds (render-r1, render-r2...), test renders,
           cover projects, renderer scratch folders and the animatic's draft video. The current round is untouched.
  posted   once the video is posted AND its 48 h stats are in (or it was rejected and is 3+ days old): the raw render,
           audio stems, scene project and voice takes. Kept for good: final.mp4, cover.png, the Telegram preview, every
           JSON (plan, script, storyboard, review, QA, report, publish pack), the brief, and the vault page.
Guard: nothing is deleted from a video the library hasn't processed (library.extract records every video it saw).
"""
import json
import shutil
import sys
from pathlib import Path

from frameflow import library, videos

ROOT = Path(__file__).resolve().parent.parent
KEEP = {"final.mp4", "cover.png", "preview-720.mp4", "keyframes.jpg"}
BULKY = ("raw.mp4", "premix.wav", "music-stem.wav", "sfx-stem.wav")


def size(p):
    p = Path(p)
    if p.is_file():
        return p.stat().st_size
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) if p.exists() else 0


def ready_for_posted(row):
    """Posted with the 48 h stats done, or rejected / left unapproved for 3+ days."""
    from frameflow import daily
    run = next((dict(r) for r in daily.db().execute("SELECT * FROM runs WHERE video_id=?", (row["id"],))), None)
    if row["status"] == "posted":
        if run is None:   # posted by hand before the daily runs existed: wait 3 days after posting
            return (videos.now()[:10] > (row["updated_at"] or "")[:10]) and _days_since(row["updated_at"]) >= 3
        return bool(run.get("stats_at"))
    return row["status"] in ("rejected", "retired", "needs-work", "awaiting-approval") and _days_since(row["updated_at"]) >= 3


def _days_since(iso):
    import datetime as dt
    try:
        return (dt.datetime.now() - dt.datetime.fromisoformat(iso)).days
    except Exception:
        return 0


def targets(row):
    base = Path(row["plan"]).parent
    render = Path(row["out_dir"])
    rounds = [p for p in base.glob("render-r*") if p.is_dir()] + [p for p in (base / "blank-test", base / "cover-project") if p.exists()]
    rounds += [p for p in render.glob("work-*") if p.is_dir()]
    rounds += [p for p in (render / "animatic.mp4", render / "animatic") if p.exists()]   # the animatic's draft (its sheet and numbers stay)
    posted = []
    if ready_for_posted(row):
        posted = [render / n for n in BULKY if (render / n).exists()] + ([render / "project"] if (render / "project").exists() else [])
        posted += [w for w in (render / "voice").glob("*.wav")] if (render / "voice").exists() else []
    return rounds, posted


def clean(video_id, dry=False):
    row = videos.db().execute("SELECT * FROM videos WHERE id=?", (video_id,)).fetchone()
    if not row:
        raise SystemExit(f"no video {video_id}")
    if video_id not in library.extracted():
        return {"video": video_id, "skipped": "the asset library hasn't processed this video yet"}
    rounds, posted = targets(row)
    freed = 0
    for p in rounds + posted:
        if p.name in KEEP:
            continue
        freed += size(p)
        if not dry:
            shutil.rmtree(p) if p.is_dir() else p.unlink()
    return {"video": video_id, "freed_mb": round(freed / 1e6, 1), "rounds": len(rounds), "posted_level": bool(posted), "dry_run": dry}


def clean_all(dry=False):
    out = []
    for r in videos.db().execute("SELECT id FROM videos"):
        try:
            out.append(clean(r["id"], dry))
        except SystemExit as e:
            out.append({"video": r["id"], "skipped": str(e)})
    return out


def main():
    a = sys.argv[1:]
    dry = "--dry-run" in a
    a = [x for x in a if x != "--dry-run"]
    if not a:
        sys.exit(__doc__)
    if a[0] == "--report":
        for r in videos.db().execute("SELECT * FROM videos"):
            rounds, posted = targets(r)
            print(f"{r['id'][:50]:50} {r['status']:18} folder {size(Path(r['plan']).parent) / 1e6:7.0f} MB  "
                  f"would free {sum(size(p) for p in rounds + posted) / 1e6:6.0f} MB  library: {'yes' if r['id'] in library.extracted() else 'no'}")
    elif a[0] == "--all":
        print(json.dumps(clean_all(dry), indent=1))
    else:
        print(json.dumps(clean(a[0], dry), indent=1))


if __name__ == "__main__":
    main()
