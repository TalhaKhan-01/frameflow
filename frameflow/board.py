"""The Studio board (P15): a make goes desk by desk, every desk's gate before the next, one delivery render.

    writer + director (their own lints)  ->  narrator: voice + timing checks  ->  animator: scenes  ->  standards  ->
    animatic: a 12 fps draft  ->  screening on the animatic  ->  delivery render (once)  ->  QA  ->  final check

Fix loops happen before the delivery render, while a fix is still a text edit, bounded by the profile:
  timing_fix_rounds    narrator checks failed (re-hooks, caption accuracy, length, voice start) -> writer/director fix,
                       re-voice (local, free), re-check
  animatic_fix_rounds  screening below the bar, drawn events too sparse on the draft, or a standards breach -> fix -> back
                       through the narrator
After the delivery render nothing loops: the result goes to Talha with its honest numbers, and his Revise is the fix path.
Before 26 Oct, make2 rendered, reviewed, rewrote and rendered again; the second render cost as much as the first and
scored worse (Kimi: 14/22 -> 13/22).
"""
import json
import shutil
from pathlib import Path

from frameflow import animatic, direct, pipeline, precheck, profiles, progress, qa, review, standards


def _revise(brief_path, plan_path, fixes, lane, label, desk):
    """One fix round through the writer and director; a plan that comes back invalid is dropped (the last valid one stays)."""
    keep = plan_path.read_text()
    with progress.step(label, desk=desk, fixes=len(fixes)) as info:
        d = direct.revise(brief_path, plan_path.parent, {"fixes": fixes}, lane)
        info["plan_valid"] = not d["errors"]
        if d["errors"]:
            plan_path.write_text(keep)
            progress.note("the fix came back invalid; keeping the last valid plan", errors=d["errors"][:3])
    return not d["errors"]


def make(brief_path, lane, out=None, skip_writer=False, skip_director=False, quality="looks"):
    pc = profiles.pipeline()
    with progress.step("script and storyboard (writer + director)", desk="writer"):
        d = direct.direct(brief_path, out, lane, skip_writer, skip_director)
    if d["errors"]:
        return {"status": "plan-invalid", **d}
    return run(brief_path, Path(d["plan"]), lane, quality)


def run(brief_path, plan_path, lane, quality="looks"):
    """The desks from the narrator on, with the fix loops, to one delivery render, QA and the final check. A make enters
    here after the writer and director; a revise enters here after its change order's writer/director fixes."""
    pc = profiles.pipeline()
    plan_path = Path(plan_path)
    rout = plan_path.parent / "render"
    timing_left, animatic_left = pc["timing_fix_rounds"], pc["animatic_fix_rounds"]
    rounds = {"timing": 0, "animatic": 0}
    while True:
        pipeline.voice_stage(plan_path, rout)
        with progress.step("narrator checks (timing on the real voice)", desk="narrator") as info:
            pre = precheck.run(rout)
            info.update({"pass": pre["pass"], "failed": [f"{k}: {c['detail']}" for k, c in pre["checks"].items() if not c["pass"] and not c.get("advisory")]})
        if not pre["pass"] and timing_left:
            timing_left -= 1
            rounds["timing"] += 1
            _revise(brief_path, plan_path, precheck.fixes(pre), lane, f"timing fix {rounds['timing']}: rewrite from the narrator checks", "writer")
            continue
        pipeline.build_stage(rout)
        with progress.step("standards (labels, licences, numbers)", desk="standards") as info:
            std = standards.run(rout, brief_path)
            info.update({"pass": std["pass"], "problems": [p for c in std["checks"].values() for p in c["problems"]][:6]})
        with progress.step("animatic (12 fps draft render)", desk="animatic") as info:
            anim = animatic.make(rout)
            info.update({"events": anim["detail"], "pass": anim["pass"], "render_seconds": anim["render_seconds"]})
        plan = json.loads((rout / "plan.json").read_text())
        with progress.step("screening on the animatic", desk="screening") as info:
            scr = review.screen_animatic(rout, plan, anim)
            info.update({"total": scr["total"], "max": scr["max"], "pass": scr["pass"],
                         "swipe_risks": [f"{x['t']:.0f}s {x['why']}"[:160] for x in scr.get("swipe_risks", [])]})
        if (scr["pass"] and anim["pass"] and std["pass"]) or not animatic_left:
            break
        animatic_left -= 1
        rounds["animatic"] += 1
        fixes = [{"row": f["row"], "fix": f["fix"]} for f in scr.get("fixes", [])]
        fixes += [{"row": "pacing", "fix": f"from the swipe read: around {x['t']:.0f} s a viewer would leave: {x['why']}"} for x in scr.get("swipe_risks", [])[:2]]
        if not anim["pass"]:
            fixes.append({"row": "pacing", "fix": f"measured on the draft: {anim['detail']}: add a drawn beat on a spoken word in that stretch"})
        fixes += standards.fixes(std)
        _revise(brief_path, plan_path, fixes, lane, f"animatic fix {rounds['animatic']}: rewrite from the screening", "director")
    report = pipeline.deliver_stage(rout, quality)
    with progress.step("technical QC (QA gates)", desk="qc") as info:
        q = qa.run(rout)
        info.update({"pass": q["pass"], "failed": [f"{k}: {g['detail']}"[:160] for k, g in q["gates"].items() if not g["pass"]]})
    plan = json.loads((rout / "plan.json").read_text())
    with progress.step("final screening (render vs animatic)", desk="screening") as info:
        r = review.check_final(rout, plan)
        info.update({"total": r["total"], "max": r["max"], "pass": r["pass"], "animatic_total": scr["total"],
                     "changed": [f"{c['row']}: {c['why']}"[:160] for c in r.get("changed_after_render", [])]})
    (rout / "animatic.mp4").unlink(missing_ok=True)   # the draft has done its job; the sheet and numbers stay
    shutil.rmtree(rout / "animatic", ignore_errors=True)
    return {"status": "rendered", "plan": str(plan_path), "render": str(rout), "report": report, "qa": q, "review": r,
            "animatic_total": scr["total"], "rounds": rounds}
