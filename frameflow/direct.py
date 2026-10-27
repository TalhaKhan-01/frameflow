"""Quality v2 front half: brief -> script (shorts-writer skill) -> storyboard (shorts-director skill) -> render plan.

    frameflow direct <brief.json> [--out out/<slug>] [--lane how-tech-works] [--skip-writer] [--skip-director]

Writes <out>/writer/ (hooks, script, table read, report), <out>/director/ (storyboard, notes, report) and
<out>/plan.json (a version-2 plan: drawn scenes with lines, delivery, cues, transitions, energy, sound cues, music).
If the plan fails the scene validator, the errors go back to the director's doctor once.
"""
import datetime as dt
import json
import os
import re
import subprocess
from pathlib import Path

from frameflow import cover, progress, scene_plan

ROOT = Path(__file__).resolve().parent.parent
SKILLS = Path.home() / "Talha_Khan" / "Claude" / "skills"
WRITER = SKILLS / "shorts-writer" / "scripts" / "writer.py"
DIRECTOR = SKILLS / "shorts-director" / "scripts" / "director.py"
CATALOG = ROOT / "research" / "scene-catalog.json"
CONFIG_DIR = os.environ.get("FRAMEFLOW_CLAUDE_CONFIG", str(Path.home() / ".claude-personal"))


def skill(args, timeout=3600, strict=False):
    """Run a skill script. The writer and director exit 1 when their checks still fail (not an error); strict skills
    (screening, producer, editor) exit 1 only on a real failure, which must not pass silently (26 Oct board test)."""
    r = subprocess.run(["python3", "-I", *map(str, args)], cwd=ROOT, capture_output=True, text=True, timeout=timeout,
                       env=dict(os.environ, CLAUDE_CONFIG_DIR=CONFIG_DIR))
    if r.returncode not in ((0,) if strict else (0, 1)):
        raise RuntimeError(f"{Path(str(args[0])).name} failed:\n{(r.stderr or r.stdout)[-1500:]}")
    return r.stdout


def compile_plan(brief, script, storyboard, lane, plan_id, cover_data=None):
    facts = {f["id"]: f for f in brief["facts"]}
    scenes = []
    for sc in storyboard["scenes"]:
        beats = [script["beats"][i] for i in sc["beats"]]
        lines = [{"say": b["say"], "delivery": b["delivery"], "beat": b["beat"], "devices": b["devices"]} for b in beats]
        fact_ids = [f for b in beats for f in b["facts"] if f in facts]
        sources = list(dict.fromkeys(u for f in fact_ids for u in [facts[f]["source"], *facts[f].get("also", [])]))
        data = {**sc["data"], "cues": {k: v for k, v in (sc.get("cues") or {}).items() if isinstance(v, str)}}
        scene = {"type": sc["template"], "say": " ".join(l["say"] for l in lines), "lines": lines, "data": data,
                 "enter": sc["enter"], "energy": round(float(sc["energy"]), 2), "sfx": sc.get("sfx", []),
                 "world": sc["world"], "metaphor": sc["metaphor"], "events": sc.get("events", [])}
        if sources:
            scene["claim"], scene["sources"] = True, sources
        if any(b["beat"] == "payoff" for b in beats):
            scene["payoff"] = True
        scenes.append(scene)
    if cover_data:   # the house outro: cover frame, spoken follow line, Follow button (frameflow.cover)
        scenes.append(cover.endcard(cover_data, plan_id))
    music = {"cues": [{"scene": m["from_scene"], "track": m["track"], "offset": m.get("offset", 0)} for m in storyboard["music"]]}
    return {"id": plan_id, "version": 2, "lane": lane, "title": script["title"], "theme": "paper-press",
            "voice": {"engine": "chatterbox", "model": "standard", "tempo": 1.0, "seed": 7, "pad": 0.12},
            "music": music, "hook_family": script["hook_family"], "ending_strategy": script["ending_strategy"],
            "open_loop": script["open_loop"], "concept": storyboard.get("concept", ""), "scenes": scenes}


WRITER_ROWS = {"hook", "story", "flow", "persona_humour", "honesty", "ending", "sources"}
DIRECTOR_ROWS = {"visual_storytelling", "flow", "pacing", "sound_plan", "captions", "sources", "honesty"}


def scenes_named(notes):
    """Scene numbers the director's notes name ('scene 16', 'scene(s) 3, 4', 'Scene 12 -> 13', 'Scenes 2-7'), or None when a
    note names none: then it may concern the whole storyboard and the full doctor runs. Keep-lines don't count."""
    found = set()
    for note in notes:
        if "KEEP unchanged" in note:
            continue
        refs = re.findall(r"\bscenes?(?:\(s\))?\s*((?:\d+\s*(?:[-–→>]+|,|and|to)?\s*)+)", note, re.I)
        if not refs:
            return None
        for a, b in re.findall(r"\bscenes?\s*(\d+)\s*(?:to|[-–→>]+)\s*scenes?\s*(\d+)", note, re.I):   # "Scene 4 to Scene 6"
            found |= set(range(int(a), int(b) + 1))
        for ref in refs:
            for a, b in re.findall(r"(\d+)\s*[-–]\s*(\d+)", ref):
                found |= set(range(int(a), int(b) + 1))
            found |= {int(x) for x in re.findall(r"\d+", ref)}
    return sorted(found) or None


RANGE = re.compile(r"(\d+(?:\.\d+)?)\s*s?\s*(?:to|-|–)\s*(\d+(?:\.\d+)?)\s*s\b", re.I)
POINT = re.compile(r"(?:at|around|about|from|near|~)\s*(\d+(?:\.\d+)?)\s*s\b", re.I)
HOOK = re.compile(r"\b(?:the hook|hook's|first line|opening line)\b", re.I)
COVER = re.compile(r"\b(?:end ?card|cover|thumbnail)\b", re.I)


def note_scope(note, slots=None, story=None):
    """The story scenes one note is about: the scenes it names; else the seconds it gives, through the voice timing
    (slots: (start, length) per plan scene); else the hook, scene 0. "cover" for a note about the end card or cover only
    (the cover desk redoes those), "keep" for a keep-line, None when it concerns the whole video."""
    if "KEEP unchanged" in note:
        return "keep"
    named = scenes_named([note])
    if named:
        return set(named) | ({0} if HOOK.search(note) else set())
    if slots:
        spans = [(float(a), float(b)) for a, b in RANGE.findall(note)] + [(float(x), float(x)) for x in POINT.findall(note)]
        hit = {i for a, b in spans for i, (st, d) in enumerate(slots) if st <= b and a < st + d}
        if hit:
            story_hit = {i for i in hit if story is None or i < story}
            return story_hit or "cover"
    if HOOK.search(note):
        return {0}
    if COVER.search(note):
        return "cover"
    return None


def scope(notes, slots=None, story=None):
    """Scenes a set of notes is about (a set, possibly empty), or None as soon as one note concerns the whole video."""
    found = set()
    for n in notes:
        s = note_scope(n, slots, story)
        if s is None:
            return None
        if isinstance(s, set):
            found |= s
    return found


def _slots(out, plan):
    """(start, length) per plan scene from the last voice take, or None before there is a voice."""
    voice = out / "render" / "voice"
    if not plan or not (voice / "durations.json").exists():
        return None
    from frameflow import build   # build pulls in the render stack; only needed here
    try:
        return build.timings(plan, voice)
    except (KeyError, ValueError, IndexError):
        return None


def revise(brief_path, out, review, lane="how-tech-works"):
    """Send a review's fixes back: words to the writer's doctor, picture/pacing/sound to the director's doctor
    (which also re-maps the storyboard to the revised beats), then recompile the plan.

    Both desks stay inside the scenes the notes are about when they can (P15.6.7): the writer rewrites only those
    scenes' beats (doctor --beats, merged in code, so the beat count holds) and the director redraws only those scenes
    plus the ones whose words changed. A note about the whole video sends that desk back to a full fix."""
    out = Path(out)
    wdir, ddir = out / "writer", out / "director"
    w_notes = [f"{f['row']}: {f['fix']}" for f in review["fixes"] if f["row"] in WRITER_ROWS]
    d_notes = [f"{f['row']}: {f['fix']}" for f in review["fixes"] if f["row"] in DIRECTOR_ROWS]
    n = len(list(out.glob("review*-writer-notes.txt"))) + 1
    beats_before = len(json.loads((wdir / "script.json").read_text())["beats"]) if (wdir / "script.json").exists() else None
    board = json.loads((ddir / "storyboard.json").read_text()) if (ddir / "storyboard.json").exists() else None
    plan = json.loads((out / "plan.json").read_text()) if (out / "plan.json").exists() else None
    story = len(board["scenes"]) if board else None
    slots = _slots(out, plan)
    w_scope, w_scoped = None, False
    if w_notes:
        (out / f"review{n}-writer-notes.txt").write_text("\n".join(w_notes))
        w_scope = scope(w_notes, slots, story) if board else None
        beats = sorted({b for sc in (w_scope or ()) if sc < len(board["scenes"]) for b in board["scenes"][sc]["beats"]}) if board else []
        w_scoped = bool(beats)
        label = f"writer fixes scenes {', '.join(map(str, sorted(w_scope)))} only" if w_scoped else "writer fixes the script"
        with progress.step(label, desk="writer", notes=len(w_notes)):
            skill([WRITER, "--project", ROOT, "doctor", brief_path, "--out", wdir, "--notes", out / f"review{n}-writer-notes.txt"]
                  + (["--beats", ",".join(map(str, beats))] if w_scoped else []))
    beats_after = len(json.loads((wdir / "script.json").read_text())["beats"])
    d_scope = scope(d_notes, slots, story)
    # scene-only when every director note has its scenes, the beats didn't move, and the writer (if it ran) stayed in scope
    local = d_scope is not None and beats_before == beats_after and (not w_notes or w_scoped)
    scenes = sorted(d_scope | (w_scope if w_scoped else set())) if local else None
    if local and not scenes:
        local = False   # nothing to point at: let the director check the whole storyboard
    extra = [f"The words changed in scenes {', '.join(map(str, sorted(w_scope)))}: re-time their cues and events to the new lines."] if local and w_scoped else []
    (out / f"review{n}-director-notes.txt").write_text("\n".join(d_notes + extra + ([] if local else ["The script may have changed: map every beat once, in order."])))
    with progress.step("director fixes " + (f"scenes {', '.join(map(str, scenes))} only" if local else "the storyboard"), desk="director",
                       notes=len(d_notes)):
        skill([DIRECTOR, "--project", ROOT, "doctor", ddir / "storyboard.json", "--script", wdir / "script.json", "--catalog", CATALOG,
               "--out", ddir, "--problems", out / f"review{n}-director-notes.txt"] + (["--scenes", ",".join(map(str, scenes))] if local else []))
    return direct(brief_path, out, lane, skip_writer=True, skip_director=True)


def direct(brief_path, out=None, lane="how-tech-works", skip_writer=False, skip_director=False):
    brief = json.loads(Path(brief_path).read_text())
    slug = re.sub(r"[^a-z0-9]+", "-", Path(brief_path).stem.lower()).strip("-")
    out = Path(out or ROOT / "out" / slug)
    wdir, ddir = out / "writer", out / "director"
    out.mkdir(parents=True, exist_ok=True)
    try:   # the learning loop: the current top lessons go into the writer's and director's house rules
        from frameflow import lessons
        (out / "lessons-used.json").write_text(json.dumps(lessons.write_files()))
        from frameflow import profiles
        profiles.snapshot(out)   # which profile (models, rounds) this video is made with
        from frameflow import library   # proven material from past videos, offered (not imposed) to the writer and director
        brief_data = json.loads(Path(brief_path).read_text())
        story = " ".join([brief_data.get("topic", ""), brief_data.get("angle_hint", "")] + [x["text"] for x in brief_data.get("facts", [])])
        if profiles.pipeline().get("assets", True):
            (out / "material-offered.json").write_text(json.dumps(library.material(story)))
        else:
            for m in ("material-writer.txt", "material-director.txt"):
                (ROOT / "research" / m).write_text("")
    except Exception as e:
        print(f"lessons: {e}")
    if not skip_writer:
        with progress.step("writer: hooks, story and script (shorts-writer)") as pi:
            skill([WRITER, "--project", ROOT, "run", brief_path, "--out", wdir])
            pi["title"] = json.loads((wdir / "script.json").read_text()).get("title")
    script = json.loads((wdir / "script.json").read_text())
    if not skip_director:
        with progress.step("director: storyboard and sound plan (shorts-director)"):
            skill([DIRECTOR, "--project", ROOT, "run", wdir / "script.json", "--catalog", CATALOG, "--out", ddir])
    plan_id = f"{dt.date.today().isoformat()}-{slug}"
    with progress.step("cover text"):
        cover_data = cover.make(out)
    plan = compile_plan(brief, script, json.loads((ddir / "storyboard.json").read_text()), lane, plan_id, cover_data)
    errs = scene_plan.validate(plan)
    if errs:   # one round back to the director with the validator's exact errors
        (ddir / "validator-problems.txt").write_text("\n".join(errs))
        progress.note("render plan invalid: back to the director", errors=len(errs))
        with progress.step("director fixes the plan's errors", errors=len(errs)):
            skill([DIRECTOR, "--project", ROOT, "doctor", ddir / "storyboard.json", "--script", wdir / "script.json",
                   "--catalog", CATALOG, "--out", ddir, "--problems", ddir / "validator-problems.txt"])
        plan = compile_plan(brief, script, json.loads((ddir / "storyboard.json").read_text()), lane, plan_id, cover_data)
        errs = scene_plan.validate(plan)
    (out / "plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=1))
    return {"plan": str(out / "plan.json"), "scenes": len(plan["scenes"]), "errors": errs,
            "seconds_estimate": round(scene_plan.total_seconds(plan), 1)}
