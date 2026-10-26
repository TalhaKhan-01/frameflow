"""Analyst desk (P15 Studio board): 48 h results tied to the decisions each desk made, read back at the next make.

    python -m frameflow.analyst summary         results per decision (hook family, ending, lane, length, package) so far
    python -m frameflow.analyst record <video>  add one video's decisions and results (stats48 does this after 48 h)

data/analyst.jsonl holds one row per video: its decisions (lane, hook family, ending strategy, length, words per second,
package title and cover line, animatic and final screening scores, fix rounds before the render) and its results (views,
average % viewed, likes, comments, shares, saves per platform). summary() groups the results by each decision. The
showrunner's run sheet (run_sheet) puts the evidence in front of the packaging desk and the writer at the next make, and
the weekly learning report cites it. No model call: counting, with the sample size shown so a 2-video pattern isn't
mistaken for a rule.
"""
import json
import re
import statistics
import sys
from pathlib import Path

from frameflow import videos

ROOT = Path(__file__).resolve().parent.parent
FILE = ROOT / "data" / "analyst.jsonl"
MIN_VIDEOS = 3


def decisions(video_id):
    row = videos.db().execute("SELECT * FROM videos WHERE id=?", (video_id,)).fetchone()
    out = Path(row["out_dir"])
    plan = json.loads((out / "plan.json").read_text()) if (out / "plan.json").exists() else {}
    rep = json.loads((out / "report.json").read_text()) if (out / "report.json").exists() else {}
    a = json.loads((out / "animatic-review.json").read_text()) if (out / "animatic-review.json").exists() else {}
    f = json.loads((out / "review.json").read_text()) if (out / "review.json").exists() else {}
    pkg = json.loads((out.parent / "package.json").read_text()) if (out.parent / "package.json").exists() else {}
    m = re.search(r"timing (\d+), animatic (\d+)", row["note"] or "")
    secs = rep.get("seconds")
    return {"lane": row["lane"], "hook_family": plan.get("hook_family"), "ending": plan.get("ending_strategy"),
            "seconds": secs, "length": None if secs is None else ("under 75 s" if secs < 75 else "75-100 s" if secs <= 100 else "over 100 s"),
            "words_per_second": round(rep["words"] / secs, 2) if rep.get("words") and secs else None,
            "package_title": pkg.get("title"), "cover_line": pkg.get("cover_line"),
            "animatic_score": a.get("total"), "final_score": f.get("total"),
            "fix_rounds": {"timing": int(m.group(1)), "animatic": int(m.group(2))} if m else None}


def results(video_id):
    con = videos.db()
    rows = con.execute("SELECT platform, views, likes, comments, shares, saves, avg_viewed FROM stats WHERE video_id=? "
                       "ORDER BY taken_at DESC", (video_id,)).fetchall()
    seen, out = set(), {}
    for r in rows:   # the latest row per platform
        if r[0] in seen:
            continue
        seen.add(r[0])
        out[r[0]] = {k: v for k, v in zip(("views", "likes", "comments", "shares", "saves", "avg_viewed"), r[1:]) if v is not None}
    return out


def record(video_id):
    row = {"video": video_id, "decisions": decisions(video_id), "results": results(video_id)}
    FILE.parent.mkdir(exist_ok=True)
    rows = [json.loads(l) for l in FILE.read_text().splitlines()] if FILE.exists() else []
    rows = [r for r in rows if r["video"] != video_id] + [row]
    FILE.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    return row


def summary():
    rows = [json.loads(l) for l in FILE.read_text().splitlines()] if FILE.exists() else []
    rows = [r for r in rows if (r["results"].get("youtube") or {}).get("views") is not None]
    out = {"videos": len(rows), "by": {}}
    for key in ("hook_family", "ending", "lane", "length"):
        groups = {}
        for r in rows:
            v = r["decisions"].get(key)
            if v:
                groups.setdefault(v, []).append(r["results"]["youtube"])
        out["by"][key] = {v: {"n": len(g), "median_views": statistics.median(x["views"] for x in g),
                              **({"median_viewed_pct": statistics.median(x["avg_viewed"] for x in g if x.get("avg_viewed") is not None)}
                                 if any(x.get("avg_viewed") is not None for x in g) else {})}
                          for v, g in sorted(groups.items(), key=lambda kv: -statistics.median(x["views"] for x in kv[1]))}
    hits = [r for r in rows if r["decisions"].get("animatic_score") is not None and r["decisions"].get("final_score") is not None]
    out["animatic_vs_final"] = [(r["decisions"]["animatic_score"], r["decisions"]["final_score"]) for r in hits]
    return out


def evidence_lines(s=None):
    """Plain lines for a prompt: what has worked so far, with sample sizes; empty below MIN_VIDEOS videos."""
    s = s or summary()
    if s["videos"] < MIN_VIDEOS:
        return []
    lines = [f"Evidence from our last {s['videos']} videos (YouTube, 48 h; small samples, treat as hints):"]
    for key, label in (("hook_family", "hook family"), ("length", "length"), ("ending", "ending")):
        g = s["by"].get(key) or {}
        if len(g) >= 2:
            best, worst = next(iter(g.items())), list(g.items())[-1]
            lines.append(f"- {label}: '{best[0]}' did best (median {best[1]['median_views']:.0f} views, n={best[1]['n']}); "
                         f"'{worst[0]}' did worst (median {worst[1]['median_views']:.0f}, n={worst[1]['n']})")
    return lines if len(lines) > 1 else []


def run_sheet(brief_path, out_dir):
    """The showrunner's run sheet for a make: the evidence so far, written beside the video and into the brief's notes."""
    lines = evidence_lines()
    sheet = {"evidence": lines, "videos_with_results": summary()["videos"]}
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "run-sheet.json").write_text(json.dumps(sheet, ensure_ascii=False, indent=1))
    if lines:
        b = json.loads(Path(brief_path).read_text())
        if "Evidence from our last" not in b.get("notes", ""):
            b["notes"] = (b.get("notes", "") + "\n" + "\n".join(lines)).strip()
            Path(brief_path).write_text(json.dumps(b, ensure_ascii=False, indent=1))
    return sheet


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "summary"
    if cmd == "record" and len(sys.argv) == 3:
        print(json.dumps(record(sys.argv[2]), ensure_ascii=False, indent=1))
    else:
        print(json.dumps(summary(), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
