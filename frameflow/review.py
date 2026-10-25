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


ROWS_V2 = ["hook", "story", "flow", "persona_humour", "visual_storytelling", "pacing", "sound_plan", "captions", "sources", "honesty", "ending"]
PASS_V2 = 16   # of 22, and no row at 0 (was 15 of 20 before the flow row, 2026-10-25)

SYSTEM_V2 = """You review Frameflow Shorts (Quality Bar v2) before a human approves them. Be strict, specific and fair.
Score each row 0 (fails), 1 (weak) or 2 (strong):
- hook: the first line stops a scrolling thumb within 2 s with a concrete, honest stake or image, and the video pays it off.
- story: And-But-Therefore shape; an open loop early; a re-hook (twist, question, reveal) at least every ~10 s; the payoff answers the loop.
- flow: a first-time viewer can follow without effort. Each part leads into the next (because, but, so, a callback, a bridge);
  when the video moves to a new part of the story, the viewer knows what is being answered now and why it matters, however that
  is done (a spoken question, a bridge, a visual that sets it up). What is on screen at a moment (headings, labels) agrees with what
  is being said then. No jumps, no orphan facts, no heading that the voice never addresses. Judge it by playing the script in your
  head as someone who knows nothing about the topic. For a score below 2, name the exact seam (between which lines or scenes) and
  what the viewer is missing there; describe the problem, don't prescribe one fixed technique.
- persona_humour: sounds like the named narrator (a sharp, friendly, slightly goofy friend), mostly informative with 3-5 light comic beats
  that each carry a fact; no AI-sounding phrasing; one line played straight.
- visual_storytelling: drawn worlds and metaphors that SHOW the idea (not slides of numbers); the metaphor maps onto the real mechanism;
  something visibly happens every couple of seconds (see the event stats).
- pacing: no dead stretches, no rush that loses the viewer; scene lengths vary with the beat.
- sound_plan: judge the cue sheet and energy plan you are given (you can't hear it): risers into reveals, hits on reveals, silence before
  the twist, music that rises with the stakes; restraint (the voice stays on top).
- captions: the burned-in captions in the frames are large, high-contrast and readable on a phone; text stays out of the caption band.
- sources: factual scenes carry a source credit; every number on screen matches the script's facts.
- honesty: no implied harm the facts don't support; re-enactments labelled; contested points stated as such.
- ending: a named ending strategy (loop, twist, practical payoff, cliffhanger, callback), not a goodbye.
For every row below 2, give one concrete fix. Read the key-frame sheet before scoring visual rows."""

SCHEMA_V2 = {"type": "object", "required": ["scores", "fixes", "summary"], "properties": {
    "scores": {"type": "object", "required": ROWS_V2, "properties": {r: {"type": "integer", "minimum": 0, "maximum": 2} for r in ROWS_V2}},
    "fixes": {"type": "array", "items": {"type": "object", "required": ["row", "fix"], "properties": {"row": {"type": "string"}, "fix": {"type": "string"}}}},
    "summary": {"type": "string"}}}


def keyframes_v2(out, every=3.0, cols=6):   # 3 s / 200 px since 2026-10-25: half the image tokens; QA gates watch every frame
    """One frame every `every` seconds, in a grid (6 per row), each labelled with its time."""
    final = out / "final.mp4"
    total = media.duration(final)
    times = [round(t, 2) for t in [i * every + 0.8 for i in range(int(total // every))] if t < total - 0.2]
    rows, frames = [], []
    for i, t in enumerate(times):
        f = out / f"kf{i}.jpg"
        media.ffmpeg("-ss", f"{t:.2f}", "-i", final, "-frames:v", "1", "-vf",
                     f"scale=200:-2,drawtext=text='{t:.0f}s':x=8:y=8:fontsize=24:fontcolor=white:box=1:boxcolor=black@0.6", f)
        frames.append(f)
    for r in range(0, len(frames), cols):
        group = frames[r:r + cols]
        while len(group) < cols:
            group.append(group[-1])
        row = out / f"kfrow{r}.jpg"
        media.ffmpeg(*sum((["-i", g] for g in group), []), "-filter_complex", f"hstack=inputs={cols}", row)
        rows.append(row)
    sheet = out / "keyframes.jpg"
    if len(rows) == 1:
        rows[0].replace(sheet)
    else:
        media.ffmpeg(*sum((["-i", r] for r in rows), []), "-filter_complex", f"vstack=inputs={len(rows)}", sheet)
    for f in frames + rows:
        f.unlink(missing_ok=True)
    return sheet


def run_v2(out, plan, model="opus"):
    from frameflow import qa
    sheet = keyframes_v2(out)
    ev, total = qa.visual_events(out / "final.mp4")
    gaps = [b - a for a, b in zip([0.0] + ev, ev + [total])]
    sfx = json.loads((out / "project" / "sfx.json").read_text()) if (out / "project" / "sfx.json").exists() else []
    lines = []
    for i, s in enumerate(plan["scenes"]):
        lines.append(f"Scene {i} [{s['type']}; world: {s.get('world', '')}; metaphor: {s.get('metaphor', '')}; enter: {s.get('enter')}; "
                     f"energy {s.get('energy')}]" + (f" sources: {', '.join(s.get('sources', []))}" if s.get("sources") else ""))
        for l in s.get("lines", [{"say": s.get("say", ""), "beat": "", "devices": []}]):
            lines.append(f"    ({l.get('beat', '')}; {', '.join(l.get('devices', []))}) {l['say']}")
        lines.append(f"    on screen: {json.dumps({k: v for k, v in s['data'].items() if not k.startswith('_')}, ensure_ascii=False)[:300]}")
    music = json.dumps(plan.get("music", {}))
    cue_sheet = ", ".join(f"{c['t']:.1f}s {c['name']}" for c in sfx)
    prompt = (f"Title: {plan['title']}\nHook family: {plan.get('hook_family')}; ending strategy: {plan.get('ending_strategy')}; open loop: "
              f"{plan.get('open_loop')}\nScript and storyboard:\n" + "\n".join(lines) +
              ("\nThe last scene is the channel's fixed house end card (cover title, a spoken follow line, Follow button), added "
                 "after the story on purpose: judge the ending and the story on the last scene before it, and don't mark the "
                 "end card down as a goodbye." if plan["scenes"][-1]["type"] == "endcard" else "") +
              f"\n\nMusic plan: {music}\nSound cue sheet: {cue_sheet}\nMeasured: {len(ev) / total * 10:.1f} visual events per 10 s, "
              f"longest gap {max(gaps):.1f} s, length {total:.1f} s.\n\nKey frames, one every 3 s with the time in the corner, left to right "
              f"then top to bottom: {sheet}\nScore every row.")
    r = llm.call(prompt, SYSTEM_V2, SCHEMA_V2, model=model, tools="Read", add_dirs=[out], purpose=f"review2:{plan['id']}", effort="high")
    total_score = sum(r["scores"].values())
    r["total"], r["max"] = total_score, 2 * len(ROWS_V2)
    r["pass"] = total_score >= PASS_V2 and min(r["scores"].values()) > 0
    (out / "review.json").write_text(json.dumps(r, ensure_ascii=False, indent=1))
    return r


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
