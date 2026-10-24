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

from frameflow import scene_plan

ROOT = Path(__file__).resolve().parent.parent
SKILLS = Path.home() / "Talha_Khan" / "Claude" / "skills"
WRITER = SKILLS / "shorts-writer" / "scripts" / "writer.py"
DIRECTOR = SKILLS / "shorts-director" / "scripts" / "director.py"
CATALOG = ROOT / "research" / "scene-catalog.json"
CONFIG_DIR = os.environ.get("FRAMEFLOW_CLAUDE_CONFIG", str(Path.home() / ".claude-personal"))


def skill(args, timeout=3600):
    r = subprocess.run(["python3", "-I", *map(str, args)], cwd=ROOT, capture_output=True, text=True, timeout=timeout,
                       env=dict(os.environ, CLAUDE_CONFIG_DIR=CONFIG_DIR))
    if r.returncode not in (0, 1):
        raise SystemExit(f"{args[0]} failed:\n{(r.stderr or r.stdout)[-1500:]}")
    return r.stdout


def compile_plan(brief, script, storyboard, lane, plan_id):
    facts = {f["id"]: f for f in brief["facts"]}
    scenes = []
    for sc in storyboard["scenes"]:
        beats = [script["beats"][i] for i in sc["beats"]]
        lines = [{"say": b["say"], "delivery": b["delivery"], "beat": b["beat"], "devices": b["devices"]} for b in beats]
        fact_ids = [f for b in beats for f in b["facts"] if f in facts]
        sources = list(dict.fromkeys(facts[f]["source"] for f in fact_ids))
        data = {**sc["data"], "cues": {k: v for k, v in (sc.get("cues") or {}).items() if isinstance(v, str)}}
        scene = {"type": sc["template"], "say": " ".join(l["say"] for l in lines), "lines": lines, "data": data,
                 "enter": sc["enter"], "energy": round(float(sc["energy"]), 2), "sfx": sc.get("sfx", []),
                 "world": sc["world"], "metaphor": sc["metaphor"], "events": sc.get("events", [])}
        if sources:
            scene["claim"], scene["sources"] = True, sources
        if any(b["beat"] == "payoff" for b in beats):
            scene["payoff"] = True
        scenes.append(scene)
    music = {"cues": [{"scene": m["from_scene"], "track": m["track"], "offset": m.get("offset", 0)} for m in storyboard["music"]]}
    return {"id": plan_id, "version": 2, "lane": lane, "title": script["title"], "theme": "paper-press",
            "voice": {"engine": "chatterbox", "model": "standard", "tempo": 1.0, "seed": 7, "pad": 0.12},
            "music": music, "hook_family": script["hook_family"], "ending_strategy": script["ending_strategy"],
            "open_loop": script["open_loop"], "concept": storyboard.get("concept", ""), "scenes": scenes}


def direct(brief_path, out=None, lane="how-tech-works", skip_writer=False, skip_director=False):
    brief = json.loads(Path(brief_path).read_text())
    slug = re.sub(r"[^a-z0-9]+", "-", Path(brief_path).stem.lower()).strip("-")
    out = Path(out or ROOT / "out" / slug)
    wdir, ddir = out / "writer", out / "director"
    if not skip_writer:
        skill([WRITER, "--project", ROOT, "run", brief_path, "--out", wdir])
    script = json.loads((wdir / "script.json").read_text())
    if not skip_director:
        skill([DIRECTOR, "--project", ROOT, "run", wdir / "script.json", "--catalog", CATALOG, "--out", ddir])
    plan_id = f"{dt.date.today().isoformat()}-{slug}"
    plan = compile_plan(brief, script, json.loads((ddir / "storyboard.json").read_text()), lane, plan_id)
    errs = scene_plan.validate(plan)
    if errs:   # one round back to the director with the validator's exact errors
        (ddir / "validator-problems.txt").write_text("\n".join(errs))
        skill([DIRECTOR, "--project", ROOT, "doctor", ddir / "storyboard.json", "--script", wdir / "script.json",
               "--catalog", CATALOG, "--out", ddir, "--problems", ddir / "validator-problems.txt"])
        plan = compile_plan(brief, script, json.loads((ddir / "storyboard.json").read_text()), lane, plan_id)
        errs = scene_plan.validate(plan)
    (out / "plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=1))
    return {"plan": str(out / "plan.json"), "scenes": len(plan["scenes"]), "errors": errs,
            "seconds_estimate": round(scene_plan.total_seconds(plan), 1)}
