"""Pipeline profiles: named, reversible presets for the models, rounds and review settings, for experiments.

    frameflow profile list               the profiles and which one is active
    frameflow profile show               the settings in force right now
    frameflow profile use <name>         switch (writes the values into the config files below; the next video uses them)
    frameflow profile save <name>        keep the current settings as a new profile (try something, then save it)

A profile (research/profiles/<name>.json) holds overrides per config file:
  "pipeline"        -> research/pipeline.json        review model and keyframes, automatic revisions, small-job models
  "shorts-writer"   -> research/shorts-writer.json   writer_model, hooks_model, judge_model, doctor_model, doctor_rounds
  "shorts-director" -> research/shorts-director.json model, doctor_model, doctor_rounds
  "social-caption"  -> research/social-caption.json  model
  "voice-pace"      -> research/voice-pace.json      default_wpm, beats (target words per minute by beat)
Only the keys a profile names are changed; everything else in those files stays. Every video stores the settings it
was made with (out/<slug>/profile.json), so results and token use can be compared per profile. Switching is just
writing JSON, and git keeps the history, so any change can be undone.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESEARCH = ROOT / "research"
PROFILES = RESEARCH / "profiles"
FILES = {"pipeline": "pipeline.json", "shorts-writer": "shorts-writer.json", "shorts-director": "shorts-director.json",
         "social-caption": "social-caption.json", "voice-pace": "voice-pace.json"}
PIPELINE_DEFAULTS = {"profile": "diet", "review_model": "opus", "keyframe_every": 3.0, "keyframe_width": 200,
                     "max_auto_revisions": 1, "brief_model": "sonnet", "cover_model": "haiku", "lessons_model": "haiku",
                     "assets": True, "max_seconds": 120.0, "target_seconds": [60.0, 115.0]}


def _read(name):
    p = RESEARCH / FILES[name]
    return json.loads(p.read_text()) if p.exists() else {}


def pipeline():
    """The pipeline's own settings (with defaults), read fresh each time so a switch applies to the next step."""
    return {**PIPELINE_DEFAULTS, **_read("pipeline")}


def names():
    return sorted(p.stem for p in PROFILES.glob("*.json"))


def current():
    """The settings in force, per config file, limited to the keys any profile controls."""
    keys = {}
    for n in names():
        for section, vals in json.loads((PROFILES / f"{n}.json").read_text()).items():
            if section in FILES:
                keys.setdefault(section, set()).update(vals)
    out = {}
    for section, ks in keys.items():
        data = pipeline() if section == "pipeline" else _read(section)
        out[section] = {k: data.get(k) for k in sorted(ks)}
    return out


def use(name):
    prof = json.loads((PROFILES / f"{name}.json").read_text())
    for section, vals in prof.items():
        if section not in FILES:
            continue
        p = RESEARCH / FILES[section]
        data = json.loads(p.read_text()) if p.exists() else {}
        data.update(vals)
        if section == "pipeline":
            data["profile"] = name
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    if "pipeline" not in prof:
        p = RESEARCH / FILES["pipeline"]
        data = json.loads(p.read_text()) if p.exists() else {}
        data["profile"] = name
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    return current()


def save(name, about=""):
    snap = current()
    snap["pipeline"] = {k: v for k, v in snap.get("pipeline", {}).items() if k != "profile"}
    (PROFILES / f"{name}.json").write_text(json.dumps({"_about": about or f"saved from the settings in force", **snap}, ensure_ascii=False, indent=2) + "\n")
    p = RESEARCH / FILES["pipeline"]
    data = json.loads(p.read_text()) if p.exists() else {}
    data["profile"] = name
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    return name


def snapshot(out_dir):
    """Record what a video was made with (called by direct before the writer runs)."""
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    (Path(out_dir) / "profile.json").write_text(json.dumps({"profile": pipeline().get("profile"), **current()}, ensure_ascii=False, indent=1))


def main(argv=None):
    a = argv if argv is not None else sys.argv[1:]
    cmd = a[0] if a else "list"
    if cmd == "list":
        active = pipeline().get("profile")
        for n in names():
            about = json.loads((PROFILES / f"{n}.json").read_text()).get("_about", "")
            print(f"{'*' if n == active else ' '} {n:10} {about}")
    elif cmd == "show":
        print(json.dumps({"profile": pipeline().get("profile"), **current()}, indent=1))
    elif cmd == "use" and len(a) > 1:
        use(a[1])
        print(f"now using profile {a[1]}; the next video is made with it")
    elif cmd == "save" and len(a) > 1:
        print(f"saved and using profile {save(a[1], ' '.join(a[2:]))}")
    else:
        sys.exit("usage: frameflow profile list | show | use <name> | save <name> [about]")


if __name__ == "__main__":
    main()
