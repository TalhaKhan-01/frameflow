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
MAX_SECONDS = 60.0
WORDS_PER_SECOND = 2.7   # about 160 words a minute: Kokoro at speed 1.1 (breakout median is 171-175)
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


SCENES = {
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
        if s.get("claim"):
            srcs = s.get("sources")
            if not (isinstance(srcs, list) and srcs and all(isinstance(u, str) and URL.match(u) for u in srcs)):
                errs.append(f"{where} makes a factual claim but has no source URL (sources: [\"https://...\"])")
    if not errs and total_seconds(plan) > MAX_SECONDS:
        errs.append(f"planned length {total_seconds(plan):.1f} s is over {MAX_SECONDS:.0f} s")
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
