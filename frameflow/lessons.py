"""Lessons: every video teaches the next one (vault Decisions/Daily Automation.md, learning pipeline).

    python -m frameflow.lessons distill <render-dir> [--notes "Talha's words"]   new lessons from a finished video
    python -m frameflow.lessons files                                            rewrite the writer/director lesson files
    python -m frameflow.lessons list

Ledger: research/lessons.jsonl, one lesson per line:
  {"id", "area": writer|director, "text" (general, applies to any video), "evidence", "source", "status":
   active|promoted|retired, "seen" (videos that raised it), "helped", "hurt", "created", "updated"}
The top active lessons per area (at most 8) go to research/lessons-<area>.txt, which the shorts-writer and
shorts-director skills read through their `lessons_file` config and add to their house rules.
"""
import argparse
import datetime as dt
import json
from pathlib import Path

from frameflow import llm, profiles

ROOT = Path(__file__).resolve().parent.parent
LEDGER = ROOT / "research" / "lessons.jsonl"
FILES = {"writer": ROOT / "research" / "lessons-writer.txt", "director": ROOT / "research" / "lessons-director.txt"}
TOP = 8

SYSTEM = """You keep the lessons ledger of a daily short-video channel. From one video's review notes, failed checks and
the owner's words, write at most 3 lessons that will make FUTURE videos better. A lesson is general (it would apply to a
different story), concrete and checkable ("Hold every stat on screen until the narrator finishes saying it", not "fix
scene 5" or "be better"). area = writer (words, hook, story, jokes, ending, facts) or director (pictures, pacing, scenes,
transitions, sound). If a note repeats an existing lesson, list that lesson's id under reinforce instead of writing it
again. The owner's own words weigh most. Write nothing for one-off fixes that wouldn't recur.
The pipeline itself already adds the cover/thumbnail and the follow end card after the story, so write no lesson asking
the writer or director to add either; lessons about the story's own ending are fine."""

SCHEMA = {"type": "object", "required": ["new", "reinforce"], "properties": {
    "new": {"type": "array", "maxItems": 3, "items": {"type": "object", "required": ["area", "text", "evidence"], "properties": {
        "area": {"type": "string", "enum": ["writer", "director"]}, "text": {"type": "string"}, "evidence": {"type": "string"}}}},
    "reinforce": {"type": "array", "items": {"type": "string"}}}}


def load():
    return [json.loads(l) for l in LEDGER.read_text().splitlines() if l.strip()] if LEDGER.exists() else []


def save(rows):
    LEDGER.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))


def today():
    return dt.date.today().isoformat()


def distill(render_dir, notes="", source=None):
    out = Path(render_dir)
    rev = json.loads((out / "review.json").read_text()) if (out / "review.json").exists() else {}
    qa = json.loads((out / "qa.json").read_text()) if (out / "qa.json").exists() else {}
    failed = [f"{k}: {g.get('detail', '')}" for k, g in qa.get("gates", {}).items() if not g.get("pass")]
    rows = load()
    active = [r for r in rows if r["status"] == "active"]
    prompt = ("Existing active lessons:\n" + ("\n".join(f"{r['id']} [{r['area']}] {r['text']}" for r in active) or "none") +
              "\n\nThis video's review notes:\n" + ("\n".join(f"- {f['row']}: {f['fix']}" for f in rev.get("fixes", [])) or "none") +
              f"\nReview scores: {json.dumps(rev.get('scores', {}))}\nFailed checks: {failed or 'none'}\nOwner's words: {notes or 'none'}")
    if not (rev.get("fixes") or failed or notes):
        return {"new": [], "reinforce": []}
    r = llm.call(prompt, SYSTEM, SCHEMA, model=profiles.pipeline()["lessons_model"], purpose=f"lessons:{out.parent.name}", effort="low")
    src = source or out.parent.name
    for rid in r["reinforce"]:
        for row in rows:
            if row["id"] == rid:
                row["seen"] += 1
                row["updated"] = today()
                row["evidence"] = (row["evidence"] + f"; again in {src}")[-600:]
    n = max([int(x["id"][1:]) for x in rows] or [0])
    for les in r["new"]:
        n += 1
        rows.append({"id": f"L{n}", "area": les["area"], "text": les["text"], "evidence": f"{src}: {les['evidence']}"[:600],
                     "source": "talha" if notes else "review", "status": "active", "seen": 1, "helped": 0, "hurt": 0,
                     "created": today(), "updated": today()})
    save(rows)
    write_files()
    return r


def rank(row):
    """Owner's lessons first, then the ones raised by the most videos, then the ones results backed, then the newest."""
    return (row["source"] == "talha", row["seen"], row["helped"] - row["hurt"], row["updated"])


def write_files():
    rows = load()
    used = {}
    for area, path in FILES.items():
        top = sorted([r for r in rows if r["status"] == "active" and r["area"] == area], key=rank, reverse=True)[:TOP]
        path.write_text("".join(r["text"].replace("\n", " ") + "\n" for r in top))
        used[area] = [r["id"] for r in top]
    return used


def score(lesson_ids, helped):
    """After 48 h: lessons that were in a video's prompts get credit (or blame) from how that video did."""
    rows = load()
    for row in rows:
        if row["id"] in lesson_ids:
            row["helped" if helped else "hurt"] += 1
            row["updated"] = today()
    save(rows)


def promotable(min_helped=3):
    return [r for r in load() if r["status"] == "active" and r["helped"] >= min_helped and r["helped"] > r["hurt"]]


def promote(lesson_id):
    """Move a proven lesson into the skill's permanent house rules (research/shorts-<area>.json)."""
    rows = load()
    row = next(r for r in rows if r["id"] == lesson_id)
    cfg_path = ROOT / "research" / ("shorts-writer.json" if row["area"] == "writer" else "shorts-director.json")
    cfg = json.loads(cfg_path.read_text())
    if row["text"] not in cfg.setdefault("house_rules", []):
        cfg["house_rules"].append(row["text"])
        cfg_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n")
    row["status"], row["updated"] = "promoted", today()
    save(rows)
    write_files()
    return row


def retire_stale(days=21):
    """Lessons results argue against, or that nothing has raised or backed for weeks, stop taking prompt space."""
    rows, cutoff, gone = load(), (dt.date.today() - dt.timedelta(days=days)).isoformat(), []
    for r in rows:
        if r["status"] == "active" and (r["hurt"] > r["helped"] + 1 or (r["updated"] < cutoff and r["helped"] == 0 and r["source"] != "talha")):
            r["status"], r["updated"] = "retired", today()
            gone.append(r["id"])
    save(rows)
    write_files()
    return gone


def main():
    ap = argparse.ArgumentParser(description="Frameflow lessons ledger")
    ap.add_argument("cmd", choices=["distill", "files", "list"])
    ap.add_argument("dir", nargs="?")
    ap.add_argument("--notes", default="")
    a = ap.parse_args()
    if a.cmd == "distill":
        print(json.dumps(distill(a.dir, a.notes), ensure_ascii=False, indent=1))
    elif a.cmd == "files":
        print(json.dumps(write_files(), indent=1))
    else:
        for r in load():
            print(f"{r['id']:4} {r['status']:8} {r['area']:8} seen {r['seen']} +{r['helped']}/-{r['hurt']}  {r['text']}")


if __name__ == "__main__":
    main()
