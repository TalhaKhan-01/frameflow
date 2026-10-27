"""Model review: one call scores the judgement rows of the Quality Bar from the script and key frames.

    frameflow review <out-dir>      writes <out-dir>/review.json and keyframes.jpg; exit 0 on pass

The key frames (the middle of every scene) are stacked into one contact sheet, so the model reads one image.
Rows scored 0-2: hook (QB 6), captions readable (QB 7), originality (QB 8), India angle (QB 9),
sources on screen (QB 10), ending (QB 11). Pass = total >= 9 of 12 and no row at 0.
"""
import json
import sys
from pathlib import Path

from frameflow import bar, build, llm, media

ROOT = Path(__file__).resolve().parent.parent

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
    sheet = out / name
    if len(rows) == 1:
        rows[0].replace(sheet)
    else:
        media.ffmpeg(*sum((["-i", r] for r in rows), []), "-filter_complex", f"vstack=inputs={len(rows)}", sheet)
    for f in frames + rows:
        f.unlink(missing_ok=True)
    return sheet, plan


ROWS_V2 = bar.get("screening", "rows")        # research/quality-bar.json: the one bar every desk reads
PASS_V2 = bar.get("screening", "pass_total")  # of 2 x rows, and no row at 0
# The v2 rubric, prompt and scoring live in the shorts-screening skill; this module builds its input (P15 Studio board).

def keyframes_v2(out, every=3.0, cols=6, width=200, video=None, name="keyframes.jpg"):   # spacing and size from the active profile
    """One frame every `every` seconds, in a grid (6 per row), each labelled with its time. `video`: another file than
    final.mp4 (the animatic's draft render), written to `name`."""
    final = Path(video) if video else out / "final.mp4"
    total = media.duration(final)
    times = [round(t, 2) for t in [i * every + 0.8 for i in range(int(total // every))] if t < total - 0.2]
    rows, frames = [], []
    for i, t in enumerate(times):
        f = out / f"kf{i}.jpg"
        media.ffmpeg("-ss", f"{t:.2f}", "-i", final, "-frames:v", "1", "-vf",
                     f"scale={width}:-2,drawtext=text='{t:.0f}s':x=8:y=8:fontsize=24:fontcolor=white:box=1:boxcolor=black@0.6", f)
        frames.append(f)
    for r in range(0, len(frames), cols):
        group = frames[r:r + cols]
        while len(group) < cols:
            group.append(group[-1])
        row = out / f"kfrow{r}.jpg"
        media.ffmpeg(*sum((["-i", g] for g in group), []), "-filter_complex", f"hstack=inputs={cols}", row)
        rows.append(row)
    sheet = out / name
    if len(rows) == 1:
        rows[0].replace(sheet)
    else:
        media.ffmpeg(*sum((["-i", r] for r in rows), []), "-filter_complex", f"vstack=inputs={len(rows)}", sheet)
    for f in frames + rows:
        f.unlink(missing_ok=True)
    return sheet


SCREENING = Path.home() / "Talha_Khan" / "Claude" / "skills" / "shorts-screening" / "scripts" / "screening.py"


def screening_input(out, plan, sheet, measured, every, purpose):
    """What the screening desk reads: script + storyboard per scene, sound plan, measured pacing, the contact sheet."""
    sfx = json.loads((out / "project" / "sfx.json").read_text()) if (out / "project" / "sfx.json").exists() else []
    lines = []
    for i, s in enumerate(plan["scenes"]):
        lines.append(f"Scene {i} [{s['type']}; world: {s.get('world', '')}; metaphor: {s.get('metaphor', '')}; enter: {s.get('enter')}; "
                     f"energy {s.get('energy')}]" + (f" sources: {', '.join(s.get('sources', []))}" if s.get("sources") else ""))
        for l in s.get("lines", [{"say": s.get("say", ""), "beat": "", "devices": []}]):
            lines.append(f"    ({l.get('beat', '')}; {', '.join(l.get('devices', []))}) {l['say']}")
        lines.append(f"    on screen: {json.dumps({k: v for k, v in s['data'].items() if not k.startswith('_')}, ensure_ascii=False)[:300]}")
    return {"title": plan["title"], "meta": {"hook family": plan.get("hook_family"), "ending strategy": plan.get("ending_strategy"),
                                             "open loop": plan.get("open_loop")},
            "script": "\n".join(lines), "music": json.dumps(plan.get("music", {})),
            "cue_sheet": ", ".join(f"{c['t']:.1f}s {c['name']}" for c in sfx), "measured": measured,
            "sheet": str(Path(sheet).resolve()), "every": every, "purpose": purpose}


def _screening(cmd, files, out_file):
    """One retry: a model call that fails now and then (it happened in the 26 Oct board test) mustn't cost the make."""
    from frameflow import direct, progress
    for attempt in (1, 2):
        Path(out_file).unlink(missing_ok=True)   # never read back an earlier result (26 Oct: a failed call returned the last one)
        try:
            direct.skill([SCREENING, "--project", ROOT, cmd, *files, "--out", out_file], timeout=2400, strict=True)
            return json.loads(Path(out_file).read_text())
        except RuntimeError as e:
            if attempt == 2 or "limit" in str(e) and "resets" in str(e):   # a usage limit won't pass on a retry: daily waits for the reset
                raise
            progress.note("screening call failed; trying once more", error=str(e)[-300:])


EDITOR = Path.home() / "Talha_Khan" / "Claude" / "skills" / "shorts-editor" / "scripts" / "editor.py"


def table_read(out, plan, brief_path):
    """The script editor's table read (skill shorts-editor): script + storyboard + real line times + fact sheet, no pictures."""
    from frameflow import direct, progress
    out = Path(out)
    dur = json.loads((out / "voice" / "durations.json").read_text())
    starts = {l["id"]: l["start"] for l in dur["lines"]}
    lines = []
    for i, s in enumerate(plan["scenes"]):
        lines.append(f"Scene {i} [{s['type']}; world: {s.get('world', '')}; metaphor: {s.get('metaphor', '')}]")
        for j, l in enumerate(s.get("lines", [])):
            t = starts.get(f"s{i}" if len(s["lines"]) == 1 else f"s{i}.{j}")
            lines.append(f"    ({l.get('beat', '')}; {', '.join(l.get('devices', []))}; {t:.1f}s) {l['say']}" if t is not None else f"    {l['say']}")
        lines.append(f"    on screen: {json.dumps({k: v for k, v in s['data'].items() if not k.startswith('_') and k not in ('beats', 'cues')}, ensure_ascii=False)[:240]}")
    brief = json.loads(Path(brief_path).read_text()) if brief_path and Path(brief_path).exists() else {}
    sfx = json.loads((out / "project" / "sfx.json").read_text()) if (out / "project" / "sfx.json").exists() else []
    inp = {"title": plan["title"], "meta": {"hook family": plan.get("hook_family"), "ending strategy": plan.get("ending_strategy"),
                                             "open loop": plan.get("open_loop")},
           "script": "\n".join(lines), "facts": [f.get("text", "") for f in brief.get("facts", [])],
           "music": json.dumps(plan.get("music", {})), "cue_sheet": ", ".join(f"{c['t']:.1f}s {c['name']}" for c in sfx),
           "purpose": plan["id"]}
    (out / "table-read-input.json").write_text(json.dumps(inp, ensure_ascii=False, indent=1))
    path = out / "table-read.json"
    for attempt in (1, 2):
        path.unlink(missing_ok=True)
        try:
            direct.skill([EDITOR, "--project", ROOT, "read", out / "table-read-input.json", "--out", path], timeout=900, strict=True)
            return json.loads(path.read_text())
        except RuntimeError as e:
            if attempt == 2 or "limit" in str(e) and "resets" in str(e):   # a usage limit won't pass on a retry: daily waits for the reset
                raise
            progress.note("table read failed; trying once more", error=str(e)[-300:])


def screen_animatic(out, plan, anim):
    """The full screening on the animatic (frameflow.animatic: a 12 fps draft), before the delivery render."""
    out = Path(out)
    inp = screening_input(out, plan, anim["sheet"], f"{anim['detail']}; length {anim['seconds']:.1f} s (measured on the animatic draft)",
                          anim["every"], f"animatic:{plan['id']}")
    (out / "animatic-input.json").write_text(json.dumps(inp, ensure_ascii=False, indent=1))
    return _screening("screen", [out / "animatic-input.json"], out / "animatic-review.json")


def _final_input(out, plan, purpose):
    from frameflow import qa, profiles
    pc = profiles.pipeline()
    sheet = keyframes_v2(out, pc["keyframe_every"], width=pc["keyframe_width"])
    ev, total = qa.visual_events(out / "final.mp4")
    gaps = [b - a for a, b in zip([0.0] + ev, ev + [total])]
    inp = screening_input(out, plan, sheet, f"{len(ev) / total * 10:.1f} visual events per 10 s, longest gap {max(gaps):.1f} s, length {total:.1f} s",
                          pc["keyframe_every"], purpose)
    (out / "final-input.json").write_text(json.dumps(inp, ensure_ascii=False, indent=1))
    return out / "final-input.json"


def check_final(out, plan):
    """The delivery render against the screened animatic: one small call re-scores only what the render changed."""
    out = Path(out)
    if not (out / "animatic-review.json").exists():
        return run_v2(out, plan)
    r = _screening("compare", [out / "animatic-review.json", _final_input(out, plan, f"final:{plan['id']}")], out / "review.json")
    return r


def run_v2(out, plan, model=None):
    """A full screening of a finished video (reflow, or a video made before the animatic existed)."""
    out = Path(out)
    return _screening("screen", [_final_input(out, plan, f"review2:{plan['id']}")], out / "review.json")


def run(out_dir, model="sonnet"):
    out = Path(out_dir).resolve()
    plan = json.loads((out / "plan.json").read_text())
    if plan.get("version", 1) >= 2:
        return run_v2(out, plan)
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
    for k in r["scores"]:
        print(f"{r['scores'][k]}/2  {k}")
    print(f"total {r['total']}/{r.get('max', 12)} -> {'PASS' if r['pass'] else 'FIX'}\n{r['summary']}")
    for f in r["fixes"]:
        print(f"- {f['row']}: {f['fix']}")
    sys.exit(0 if r["pass"] else 1)


if __name__ == "__main__":
    main()
