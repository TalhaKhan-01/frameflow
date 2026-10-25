"""Scene plan: the JSON contract between the script writer and the renderer.

A plan is one video: a list of scenes, each naming a template from the scene library, the line the voice says
over it, the data the template shows, and the sources behind any factual claim.

    python -m frameflow.scene_plan validate <plan.json>     exit 0 if valid, 1 with one error per line if not

{
  "id": "2026-10-24-iphone-prices",          lowercase letters, digits, hyphens
  "lane": "global-tech",                     one of LANES
  "title": "Same iPhone, ₹20,000 more",
  "voice": {"voice": "af_heart", "speed": 0.95},           optional
  "scenes": [
    {"type": "headline-reveal", "say": "...", "data": {"kicker": "INDIA vs DUBAI", "lines": ["Same iPhone,", "₹20,000 more."]},
     "claim": true, "sources": ["https://..."]},
    ...
  ]
}
"""
import json
import re
import sys
from pathlib import Path

LANES = {"global-tech", "india-tech", "ai-news", "dev-tools", "ai-money", "how-tech-works"}
MAX_SECONDS = 95.0       # v1 plans only; v2 plans use the active profile's max_seconds (frameflow.profiles)
WORDS_PER_SECOND = 3.3   # about 198 words a minute: measured on the Black October render (Chatterbox house voice, tempo 1.0)
PAD = 0.25               # silence between scenes, as in the voice step
URL = re.compile(r"^https?://[^\s/$.?#].[^\s]*$", re.I)


def _str(v, max_len=None):
    return isinstance(v, str) and v.strip() != "" and (max_len is None or len(v) <= max_len)


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


# Per scene type: minimum on-screen seconds, and a data check returning a list of problems.
def _headline(d):
    errs = []
    if not (isinstance(d.get("lines"), list) and 1 <= len(d["lines"]) <= 3 and all(_str(l, 28) for l in d["lines"])):
        errs.append("data.lines must be 1-3 non-empty strings of at most 28 characters")
    if "kicker" in d and not _str(d["kicker"], 32):
        errs.append("data.kicker must be a non-empty string of at most 32 characters")
    return errs


def _stat(d):
    errs = []
    if not _num(d.get("value")):
        errs.append("data.value must be a number")
    if not _str(d.get("label"), 60):
        errs.append("data.label must be a non-empty string of at most 60 characters")
    for k in ("prefix", "suffix"):
        if k in d and not isinstance(d[k], str):
            errs.append(f"data.{k} must be a string")
    return errs


def _comparison(d):
    cols = d.get("columns")
    if not (isinstance(cols, list) and 2 <= len(cols) <= 4):
        return ["data.columns must list 2-4 columns"]
    return [f"data.columns[{i}] needs a label and a value" for i, c in enumerate(cols)
            if not (isinstance(c, dict) and _str(c.get("label"), 24) and (_str(c.get("value")) or _num(c.get("value"))))]


def _chart(d):
    errs = []
    if d.get("kind") not in ("bar", "line"):
        errs.append("data.kind must be bar or line")
    pts = d.get("series")
    if not (isinstance(pts, list) and 2 <= len(pts) <= 12 and
            all(isinstance(p, dict) and _str(p.get("label"), 16) and _num(p.get("value")) for p in pts)):
        errs.append("data.series must list 2-12 points, each with a label (at most 16 characters) and a numeric value")
    return errs


def _code(d):
    errs = []
    if not _str(d.get("code")) or len(d["code"].splitlines()) > 14:
        errs.append("data.code must be non-empty and at most 14 lines")
    elif max(len(l) for l in d["code"].splitlines()) > 46:
        errs.append("data.code lines must be at most 46 characters (longer lines shrink the code below phone-readable size)")
    if not _str(d.get("language"), 20):
        errs.append("data.language is required")
    return errs


def _news(d):
    errs = []
    if not (_str(d.get("url")) and (URL.match(d["url"]) or d["url"].startswith("file://"))):
        errs.append("data.url must be an http(s) URL")
    for k in ("headline", "source", "highlight"):
        if not _str(d.get(k)):
            errs.append(f"data.{k} is required")
    return errs


SUBJECTS_3D = ("chip", "phone", "server", "globe", "rocket", "satellite")
ACTIONS_3D = ("spin", "explode", "orbit")


def _explainer(d):
    errs = []
    if d.get("subject") not in SUBJECTS_3D:
        errs.append(f"data.subject must be one of {', '.join(SUBJECTS_3D)}")
    if d.get("action") not in ACTIONS_3D:
        errs.append(f"data.action must be one of {', '.join(ACTIONS_3D)}")
    if "title" in d and not _str(d["title"], 60):
        errs.append("data.title must be at most 60 characters")
    return errs


# Drawn scenes (Quality v2): a world that changes on beats. A beat is {"do": <verb>, "at": seconds or cue name, ...}.
def _beats(d, verbs):
    errs = []
    beats = d.get("beats", [])
    if not isinstance(beats, list):
        return ["data.beats must be a list"]
    for i, b in enumerate(beats):
        if not (isinstance(b, dict) and b.get("do") in verbs):
            errs.append(f"data.beats[{i}].do must be one of {', '.join(verbs)}")
        elif "at" in b and not (_num(b["at"]) or _str(b["at"], 40)):
            errs.append(f"data.beats[{i}].at must be seconds or a cue name")
    return errs


def _cues(d):
    c = d.get("cues", {})
    if not isinstance(c, dict) or not all(_str(k, 40) and _str(v, 80) for k, v in c.items()):
        return ["data.cues must map cue names to words or phrases from the scene's say line"]
    return []


STREET_VERBS = ("draw", "note", "lights-off", "locks", "foundation", "crack", "robot", "shutters", "race", "zoom")


def _street(d):
    errs = _beats(d, STREET_VERBS) + _cues(d)
    b = d.get("buildings")
    if not (isinstance(b, list) and 2 <= len(b) <= 6 and all(isinstance(x, dict) and _str(x.get("label"), 14) for x in b)):
        errs.append("data.buildings must list 2-6 buildings, each with a label of at most 14 characters")
    return errs


FLOW_VERBS = ("draw", "send", "work", "return", "hijack", "note")
ICONS = ("phone", "kitchen", "server", "page", "database", "robot", "stranger", "door", "box")


def _flow(d):
    errs = _beats(d, FLOW_VERBS) + _cues(d)
    n = d.get("nodes")
    if not (isinstance(n, list) and 2 <= len(n) <= 3 and all(isinstance(x, dict) and _str(x.get("label"), 14) and x.get("icon", "box") in ICONS for x in n)):
        errs.append(f"data.nodes must list 2-3 nodes, each with a label (at most 14 characters) and an icon from {', '.join(ICONS)}")
    return errs


def _labels(d, key, lo, hi, field, n):
    v = d.get(key)
    if not (isinstance(v, list) and lo <= len(v) <= hi and all(isinstance(x, dict) and _str(x.get(field), n) for x in v)):
        return [f"data.{key} must list {lo}-{hi} items, each with {field} (at most {n} characters)"]
    return []


def _stack(d):
    errs = _beats(d, ("build", "explode", "highlight", "stamp", "note")) + _cues(d) + _labels(d, "layers", 2, 6, "label", 22)
    st = d.get("stamp")
    if st is not None and not (isinstance(st, dict) and _str(st.get("text"), 16)):
        errs.append("data.stamp must be {text (at most 16 characters), sub (optional)}")
    return errs


def _meter(d):
    errs = _beats(d, ("step", "boil")) + _cues(d)
    st = d.get("steps")
    if not (isinstance(st, list) and 2 <= len(st) <= 5 and all(isinstance(x, dict) and _str(x.get("when"), 30) and _str(x.get("what"), 22) for x in st)):
        errs.append("data.steps must list 2-5 steps, each with when (at most 30 characters) and what (at most 22)")
    return errs


def _flap(d):
    errs = _beats(d, ("count", "caption", "cake")) + _cues(d)
    if not (_num(d.get("from")) and _num(d.get("to"))):
        errs.append("data.from and data.to must be numbers")
    if "caption" in d and not _str(d["caption"], 22):
        errs.append("data.caption must be at most 22 characters")
    return errs


KINETIC_STYLES = ("slam", "drop", "scramble", "type", "stamp", "marker", "strike")


def _kinetic(d):
    errs = _beats(d, ("line", "circle", "fade")) + _cues(d)
    ls = d.get("lines")
    if not (isinstance(ls, list) and 1 <= len(ls) <= 5 and all(isinstance(x, dict) and _str(x.get("t"), 24) and x.get("style", "slam") in KINETIC_STYLES for x in ls)):
        errs.append(f"data.lines must list 1-5 lines, each with t (at most 24 characters) and a style from {', '.join(KINETIC_STYLES)}")
    return errs


def _stamps(d):
    errs = _beats(d, ("deal", "stamp")) + _cues(d) + _labels(d, "items", 2, 6, "name", 22)
    if "stamp" in d and not _str(d["stamp"], 12):
        errs.append("data.stamp must be at most 12 characters")
    return errs


def _quote(d):
    errs = _beats(d, ("words", "mark", "who", "doodle")) + _cues(d)
    if not _str(d.get("quote"), 160):
        errs.append("data.quote must be a real quote of at most 160 characters")
    if not _str(d.get("who"), 40):
        errs.append("data.who (who said it) is required")
    if d.get("mark") and d["mark"].lower() not in d.get("quote", "").lower():
        errs.append("data.mark must be a phrase from the quote")
    if d.get("doodle", "fire") not in ("fire", "bulb", "lock", "bug"):
        errs.append("data.doodle must be fire, bulb, lock or bug")
    return errs


def _chat(d):
    errs = _beats(d, ("ask", "think", "reply", "stamp")) + _cues(d)
    if not _str(d.get("prompt"), 80):
        errs.append("data.prompt must be at most 80 characters")
    if not _str(d.get("reply"), 120):
        errs.append("data.reply must be at most 120 characters")
    if d.get("reply") and not _str(d.get("note"), 30):
        errs.append("data.note is required (e.g. \"re-enactment\"): an invented reply must be labelled on screen")
    return errs


def _endcard(d):
    errs = _cues(d)
    if not (isinstance(d.get("title"), list) and 1 <= len(d["title"]) <= 3 and all(_str(l, 16) for l in d["title"])):
        errs.append("data.title must be 1-3 lines of at most 16 characters (the cover title)")
    if "mark" in d and not (isinstance(d["mark"], int) and 0 <= d["mark"] < len(d.get("title") or [])):
        errs.append("data.mark must be the index of a title line")
    if not (isinstance(d.get("art", []), list) and len(d.get("art", [])) <= 2 and all(a in ICONS for a in d.get("art", []))):
        errs.append(f"data.art must list at most 2 icons from {', '.join(ICONS)}")
    for key, n in (("stat", 28), ("tagline", 28), ("handle", 30), ("narrator", 16)):
        if key in d and not _str(d[key], n):
            errs.append(f"data.{key} must be at most {n} characters")
    return errs


SCENES = {
    "endcard": (2.5, _endcard),
    "street": (2.0, _street),
    "flow": (2.0, _flow),
    "stack": (2.0, _stack),
    "meter": (2.0, _meter),
    "flap": (2.0, _flap),
    "kinetic": (1.2, _kinetic),
    "stamps": (2.0, _stamps),
    "quote": (2.5, _quote),
    "chat": (2.5, _chat),
    "headline-reveal": (2.0, _headline),
    "stat-counter": (2.5, _stat),
    "comparison": (3.0, _comparison),
    "chart": (3.5, _chart),
    "code-card": (3.5, _code),
    "news-snapshot": (3.0, _news),
    "explainer-3d": (4.0, _explainer),
}


def scene_seconds(scene):
    """Planned length: explicit duration, else voice time at the breakout pace, never under the template minimum."""
    minimum = SCENES.get(scene.get("type"), (2.0, None))[0]
    if _num(scene.get("duration")):
        return max(float(scene["duration"]), minimum)
    words = len(str(scene.get("say", "")).split())
    return max(words / WORDS_PER_SECOND, minimum)


def total_seconds(plan):
    scenes = plan.get("scenes") or []
    return sum(scene_seconds(s) for s in scenes) + PAD * max(len(scenes) - 1, 0)


def validate(plan):
    """Return a list of human-readable problems; empty means the plan is valid."""
    if not isinstance(plan, dict):
        return ["plan must be a JSON object"]
    errs = []
    if not (_str(plan.get("id")) and re.fullmatch(r"[a-z0-9][a-z0-9-]{2,80}", plan["id"])):
        errs.append("id must be lowercase letters, digits and hyphens")
    if plan.get("lane") not in LANES:
        errs.append(f"lane must be one of {sorted(LANES)}")
    if not _str(plan.get("title"), 100):
        errs.append("title is required (at most 100 characters)")
    scenes = plan.get("scenes")
    if not (isinstance(scenes, list) and scenes):
        return errs + ["scenes must be a non-empty list"]
    for i, s in enumerate(scenes):
        where = f"scenes[{i}]"
        if not isinstance(s, dict):
            errs.append(f"{where} must be an object")
            continue
        if s.get("type") not in SCENES:
            errs.append(f"{where}.type '{s.get('type')}' is not a scene in the library ({', '.join(SCENES)})")
            continue
        if not isinstance(s.get("data"), dict):
            errs.append(f"{where}.data must be an object")
        else:
            errs += [f"{where}: {e}" for e in SCENES[s["type"]][1](s["data"])]
        if "say" in s and not isinstance(s["say"], str):
            errs.append(f"{where}.say must be a string")
        if "lines" in s and not (isinstance(s["lines"], list) and s["lines"] and all(isinstance(x, dict) and _str(x.get("say")) for x in s["lines"])):
            errs.append(f"{where}.lines must list objects with a say line")
        if s.get("claim"):
            srcs = s.get("sources")
            if not (isinstance(srcs, list) and srcs and all(isinstance(u, str) and URL.match(u) for u in srcs)):
                errs.append(f"{where} makes a factual claim but has no source URL (sources: [\"https://...\"])")
    limit = MAX_SECONDS
    if plan.get("version", 1) >= 2:   # v2 plans follow the active profile's hard limit
        from frameflow import profiles
        limit = float(profiles.pipeline()["max_seconds"])
    if not errs and total_seconds(plan) > limit:
        errs.append(f"planned length {total_seconds(plan):.1f} s is over {limit:.0f} s")
    return errs


def main():
    if len(sys.argv) != 3 or sys.argv[1] != "validate":
        sys.exit("usage: python -m frameflow.scene_plan validate <plan.json>")
    try:
        plan = json.loads(Path(sys.argv[2]).read_text())
    except (OSError, ValueError) as e:
        sys.exit(f"cannot read plan: {e}")
    errs = validate(plan)
    if errs:
        print("\n".join(errs))
        sys.exit(1)
    print(f"valid: {len(plan['scenes'])} scenes, about {total_seconds(plan):.1f} s")


if __name__ == "__main__":
    main()
