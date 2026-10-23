"""Model review: one call scores the judgement rows of the Quality Bar from the script and key frames.

    frameflow review <out-dir>      writes <out-dir>/review.json and keyframes.jpg; exit 0 on pass

The key frames (the middle of every scene) are stacked into one contact sheet, so the model reads one image.
Rows scored 0-2: hook (QB 6), captions readable (QB 7), originality (QB 8), India angle (QB 9),
sources on screen (QB 10), ending (QB 11). Pass = total >= 9 of 12 and no row at 0.
"""
import json
import sys
from pathlib import Path

from frameflow import build, llm, media

ROWS = ["hook", "captions", "originality", "india_angle", "sources", "ending"]
PASS_TOTAL = 9

SYSTEM = """You review Frameflow Shorts against its Quality Bar before a human approves them. Be strict and specific.
Score each row 0 (fails), 1 (weak) or 2 (strong):
- hook: the first spoken line carries a concrete stake (number, comparison, bold claim) that the video then proves.
- captions: the burned-in captions in the frames are large, high-contrast and readable on a phone.
- originality: visuals are original motion graphics, not someone else's footage; the angle adds something beyond the headline.
- india_angle: an honest India angle (₹ price, Indian users or companies, availability) where one exists; 2 if not applicable but the video says why.
- sources: the core factual claim is backed by a source, ideally named on screen; no invented numbers.
- ending: the payoff answers the hook and the last line is a question or share prompt, not a goodbye.
For every row below 2, give one concrete fix. Read the key-frame image before scoring visual rows."""

SCHEMA = {"type": "object", "required": ["scores", "fixes", "summary"], "properties": {
    "scores": {"type": "object", "required": ROWS, "properties": {r: {"type": "integer", "minimum": 0, "maximum": 2} for r in ROWS}},
    "fixes": {"type": "array", "items": {"type": "object", "required": ["row", "fix"], "properties": {"row": {"type": "string"}, "fix": {"type": "string"}}}},
    "summary": {"type": "string"}}}


def keyframes(out):
    plan = json.loads((out / "plan.json").read_text())
    slots = build.timings(plan, out / "voice")
    frames = []
    for i, (start, dur) in enumerate(slots):
        f = out / f"kf{i}.jpg"
        media.ffmpeg("-ss", f"{start + dur * 0.7:.2f}", "-i", out / "final.mp4", "-frames:v", "1", "-vf", "scale=360:-2", f)
        frames.append(f)
    per_row = 5
    rows = []
    for r in range(0, len(frames), per_row):
        group = frames[r:r + per_row]
        while len(group) < per_row:
            group.append(group[-1])
        row = out / f"kfrow{r}.jpg"
        media.ffmpeg(*sum((["-i", g] for g in group), []), "-filter_complex", f"hstack=inputs={per_row}", row)
        rows.append(row)
    sheet = out / "keyframes.jpg"
    if len(rows) == 1:
        rows[0].replace(sheet)
    else:
        media.ffmpeg(*sum((["-i", r] for r in rows), []), "-filter_complex", f"vstack=inputs={len(rows)}", sheet)
    for f in frames + rows:
        f.unlink(missing_ok=True)
    return sheet, plan


def run(out_dir, model="sonnet"):
    out = Path(out_dir).resolve()
    sheet, plan = keyframes(out)
    script = "\n".join(f"{i + 1}. [{s['type']}] {s.get('say', '')}  | on screen: {json.dumps(s.get('data', {}), ensure_ascii=False)[:200]}"
                       f"{'  | sources: ' + ', '.join(s.get('sources', [])) if s.get('sources') else ''}" for i, s in enumerate(plan["scenes"]))
    prompt = (f"Title: {plan['title']}\nLane: {plan['lane']}\nScript (scene, spoken line, on-screen data, sources):\n{script}\n\n"
              f"Key frames, one per scene, left to right then top to bottom: {sheet}\nScore every row.")
    r = llm.call(prompt, SYSTEM, SCHEMA, model=model, tools="Read", add_dirs=[out], purpose=f"review:{plan['id']}", effort="low")
    total = sum(r["scores"].values())
    r["total"] = total
    r["pass"] = total >= PASS_TOTAL and min(r["scores"].values()) > 0
    (out / "review.json").write_text(json.dumps(r, ensure_ascii=False, indent=1))
    return r


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: frameflow review <out-dir>")
    r = run(sys.argv[1])
    for k in ROWS:
        print(f"{r['scores'][k]}/2  {k}")
    print(f"total {r['total']}/12 -> {'PASS' if r['pass'] else 'FIX'}\n{r['summary']}")
    for f in r["fixes"]:
        print(f"- {f['row']}: {f['fix']}")
    sys.exit(0 if r["pass"] else 1)


if __name__ == "__main__":
    main()
