"""The Studio board (P15): a make goes desk by desk, every desk's gate before the next, one delivery render.

    packaging (the promise)  ->  writer + director (their own lints)  ->  narrator: voice + timing checks  ->  script editor: table read  ->  scenes  ->  standards  ->
    animatic: a 12 fps draft  ->  art director  ->  screening on the animatic  ->  delivery render (once)  ->  QA  ->  final check

Fix loops happen before the delivery render, while a fix is still a text edit, bounded by the profile:
  timing_fix_rounds    narrator checks (re-hooks, caption accuracy, length, voice start) or the table read failed -> one
                       writer/director fix for both, re-voice (local, free), re-check
  animatic_fix_rounds  screening below the bar, drawn events too sparse on the draft, or a standards breach -> fix -> back
                       through the narrator
After the delivery render nothing loops: the result goes to Talha with its honest numbers, and his Revise is the fix path.
Before 26 Oct, make2 rendered, reviewed, rewrote and rendered again; the second render cost as much as the first and
scored worse (Kimi: 14/22 -> 13/22).
"""
import json
import shutil
from pathlib import Path

from frameflow import animatic, artdirect, direct, pipeline, precheck, profiles, progress, qa, review, standards


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


LOCAL = " Change only that scene; keep every other scene exactly as it is."


def script_claims(rout, brief_path):
    """The fact-checker's script check (pure code in the skill): every number said is in the verified facts."""
    from frameflow import brief as brief_mod
    script = rout / "script.json"
    with progress.step("fact-check the script's numbers", desk="factcheck") as info:
        r = json.loads(direct.skill([brief_mod.FACTCHECK, "--project", brief_mod.ROOT, "script", script, brief_path], timeout=120, strict=True))
        info.update({"pass": r["pass"], "detail": r["detail"]})
    return r


def gap_fix(rout, anim):
    """A local, concrete fix for the draft's longest dead stretch: the scene, the time and the words spoken in it, so the
    director can hang a beat on one of them (a whole-storyboard rewrite didn't converge in the 26 Oct board test)."""
    from frameflow import build
    plan = json.loads((rout / "plan.json").read_text())
    words = json.loads((rout / "voice" / "words.json").read_text())
    a, gap = anim["gap_at"], anim["longest_gap"]
    said = " ".join(w["w"] for w in words if a <= w["s"] < a + gap)
    slots = build.timings(plan, rout / "voice")
    scene = next((i for i, (st, d) in enumerate(slots) if st <= a + gap / 2 < st + d), None)
    return (f"measured on the draft: nothing new is drawn for {gap:.1f} s from {a:.1f} s, in scene {scene} "
            f"({plan['scenes'][scene]['type'] if scene is not None else '?'}), while the voice says: \"{said}\". Add one beat in "
            f"scene {scene} cued on a word from that line (its cues name the phrase), so something moves at least every "
            f"2.5 s." + LOCAL)


CAPTION = Path.home() / "Talha_Khan" / "Claude" / "skills" / "social-caption" / "scripts" / "caption.py"


def package(brief_path, out_dir):
    """Packaging desk, before the writer: title, cover line and hook promise naming one stake (social-caption concept).
    The brief carries it as `package`, so the writer delivers it; cover.make starts from its cover line."""
    b = json.loads(Path(brief_path).read_text())
    if b.get("package"):
        return b["package"]
    out_dir.mkdir(parents=True, exist_ok=True)
    with progress.step("packaging: the promise before writing", desk="packaging") as info:
        direct.skill([CAPTION, "--project", direct.ROOT, "concept", brief_path, "--out", out_dir / "package.json"], timeout=600, strict=True)
        pkg = json.loads((out_dir / "package.json").read_text())
        info.update({"title": pkg["title"], "cover_line": pkg["cover_line"], "hook_promise": pkg["hook_promise"][:160],
                     "pass": not pkg.get("problems")})
    b["package"] = {k: pkg[k] for k in ("title", "cover_line", "hook_promise")}
    Path(brief_path).write_text(json.dumps(b, ensure_ascii=False, indent=1))
    return b["package"]


def make(brief_path, lane, out=None, skip_writer=False, skip_director=False, quality="looks"):
    pc = profiles.pipeline()
    if not skip_writer:
        import re
        slug = re.sub(r"[^a-z0-9]+", "-", Path(brief_path).stem.lower()).strip("-")
        from frameflow import analyst
        with progress.step("showrunner: run sheet (evidence so far)", desk="showrunner") as info:
            sheet = analyst.run_sheet(brief_path, Path(out) if out else direct.ROOT / "out" / slug)
            info.update({"videos_with_results": sheet["videos_with_results"], "evidence": sheet["evidence"][1:4]})
        package(brief_path, Path(out) if out else direct.ROOT / "out" / slug)
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
    table_done, tr = False, None
    while True:
        pipeline.voice_stage(plan_path, rout)
        with progress.step("narrator checks (timing on the real voice)", desk="narrator") as info:
            pre = precheck.run(rout)
            info.update({"pass": pre["pass"], "failed": [f"{k}: {c['detail']}" for k, c in pre["checks"].items() if not c["pass"] and not c.get("advisory")]})
        claims = script_claims(rout, brief_path)
        if not claims["pass"]:
            pre["pass"] = False
            pre["checks"]["claims"] = {"pass": False, "detail": claims["detail"], "row": "sources",
                                       "fix": f"the script says numbers the verified facts don't carry ({', '.join(claims['unverified_numbers'])}): "
                                              "use the fact sheet's numbers exactly, or drop the claim"}
        if not table_done:   # the table read once per plan text: a re-voice alone doesn't change the words
            with progress.step("table read (script editor)", desk="editor") as info:
                tr = review.table_read(rout, json.loads((rout / "plan.json").read_text()), brief_path)
                info.update({"total": tr["total"], "max": tr["max"], "pass": tr["pass"], "fixes": [f"{f['row']}: {f['fix']}"[:160] for f in tr["fixes"]][:5]})
            table_done = True
        if (not pre["pass"] or not tr["pass"]) and timing_left:   # one text round fixes the timing and the table read together
            timing_left -= 1
            rounds["timing"] += 1
            fixes = precheck.fixes(pre) + ([{"row": f["row"], "fix": f"table read: {f['fix']}"} for f in tr["fixes"]] if not tr["pass"] else [])
            _revise(brief_path, plan_path, fixes, lane, f"text fix {rounds['timing']}: narrator checks + table read", "writer")
            table_done = False
            continue
        pipeline.build_stage(rout)
        with progress.step("standards (labels, licences, numbers)", desk="standards") as info:
            std = standards.run(rout, brief_path)
            info.update({"pass": std["pass"], "problems": [p for c in std["checks"].values() for p in c["problems"]][:6]})
        with progress.step("animatic (12 fps draft render)", desk="animatic") as info:
            anim = animatic.make(rout)
            info.update({"events": anim["detail"], "pass": anim["pass"], "render_seconds": anim["render_seconds"]})
        with progress.step("art director (stills of the draft)", desk="artdirector") as info:
            art = artdirect.run(rout)
            info.update({"pass": art["pass"], "problems": [p for c in art["checks"].values() for p in c["problems"]][:6]})
        plan = json.loads((rout / "plan.json").read_text())
        with progress.step("screening on the animatic", desk="screening") as info:
            scr = review.screen_animatic(rout, plan, anim)
            info.update({"total": scr["total"], "max": scr["max"], "pass": scr["pass"],
                         "swipe_risks": [f"{x['t']:.0f}s {x['why']}"[:160] for x in scr.get("swipe_risks", [])]})
        if (scr["pass"] and anim["pass"] and std["pass"] and art["pass"]) or not animatic_left:
            break
        animatic_left -= 1
        rounds["animatic"] += 1
        fixes = [{"row": f["row"], "fix": f["fix"]} for f in scr.get("fixes", [])]
        fixes += [{"row": "pacing", "fix": f"from the swipe read: around {x['t']:.0f} s a viewer would leave: {x['why']}"} for x in scr.get("swipe_risks", [])[:2]]
        if not anim["pass"]:
            fixes.append({"row": "pacing", "fix": gap_fix(rout, anim)})
        fixes += standards.fixes(std) + artdirect.fixes(art)
        _revise(brief_path, plan_path, fixes, lane, f"animatic fix {rounds['animatic']}: rewrite from the screening", "director")
        table_done = False
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
