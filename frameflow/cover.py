"""Cover and outro: the thumbnail title for a script, and the house end card scene the pipeline appends.

    python -m frameflow.cover <out-dir>      write <out-dir>/cover.json from writer/script.json (once; delete it to redo)

The end card (scenes/endcard) opens as the cover (Habit mark, a 1-3 line title, the key drawing, one stat) for
brand.json's lead_seconds of silence, so the thumbnail frame has no captions; then Habit says the outro line and
the Follow button appears. pipeline.render saves that frame as cover.png and records its time for Instagram.
"""
import json
import re
import sys
import zlib
from pathlib import Path

from frameflow import llm, scene_plan

ROOT = Path(__file__).resolve().parent.parent
BRAND = ROOT / "research" / "brand.json"

SYSTEM = """You design the cover (thumbnail) for a short vertical explainer drawn in a hand-drawn editorial style.
Give a cover title of 2-5 words split over 1-3 lines (at most 14 characters per line, all caps), that makes a
scroller curious without lying or repeating the video title word for word; mark the one line that carries the
punch. Pick 0-2 drawn icons that show the story at a glance, from this list only: {icons}. Give one short stat or
stake from the script (at most 26 characters, digits allowed), true to the script, no hype words.
The cover becomes the thumbnail, so it must be exactly as careful as the narration: keep every hedge the script makes
("so far", "as of", "attempts", "unconfirmed") and never turn an open question or an early count into a flat fact."""

SCHEMA = {"type": "object", "required": ["title", "mark", "art", "stat"], "properties": {
    "title": {"type": "array", "minItems": 1, "maxItems": 3, "items": {"type": "string", "maxLength": 14}},
    "mark": {"type": "integer", "minimum": 0, "maximum": 2},
    "art": {"type": "array", "maxItems": 2, "items": {"type": "string", "enum": list(scene_plan.ICONS)}},
    "stat": {"type": "string", "maxLength": 26}}}


def brand():
    return json.loads(BRAND.read_text())


def make(out_dir, model=None, notes=""):
    """notes: the owner's change request for the cover (a change order); it skips the cached cover."""
    from frameflow import profiles
    model = model or profiles.pipeline()["cover_model"]
    out = Path(out_dir)
    path = out / "cover.json"
    script = json.loads((out / "writer" / "script.json").read_text())
    text = "\n".join(b["say"] for b in script["beats"])
    if path.exists() and not notes:
        c = json.loads(path.read_text())
        if not bad_numbers(c, text):   # a cached cover is reused only while it still matches the (maybe revised) script
            return c
    ask = f"\n\nThe channel owner asks for this cover: {notes}" if notes else ""
    if not notes and (out / "package.json").exists():   # the packaging desk decided the promise before the script was written
        pkg = json.loads((out / "package.json").read_text())
        ask = f"\n\nThe package decided before writing: title \"{pkg['title']}\", cover line \"{pkg['cover_line']}\". Keep the cover on that stake."
    c = llm.call(f"Video title: {script['title']}\nScript:\n{text}{ask}", SYSTEM.format(icons=", ".join(scene_plan.ICONS)), SCHEMA,
                 model=model, purpose=f"cover:{out.name}", effort="low")
    if bad_numbers(c, text):   # the cover becomes the thumbnail: its numbers must be the script's (it once said 80% vs 20% for 83.2% vs 36.1%)
        c = llm.call(f"Video title: {script['title']}\nScript:\n{text}\n\nYour last cover used numbers the script doesn't say "
                     f"({', '.join(bad_numbers(c, text))}). Use only numbers exactly as the script says them, or none.",
                     SYSTEM.format(icons=", ".join(scene_plan.ICONS)), SCHEMA, model=model, purpose=f"cover-fix:{out.name}", effort="low")
        if bad_numbers(c, text):
            c["stat"] = ""
            c["title"] = [l for l in c["title"] if not re.search(r"\d", l)] or ["TODAY'S STORY"]
    c["title"] = [l.upper() for l in c["title"]][:3]
    c["mark"] = min(c["mark"], len(c["title"]) - 1)
    path.write_text(json.dumps(c, ensure_ascii=False, indent=1))
    return c


UNITS = {w: i for i, w in enumerate("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen "
                                      "sixteen seventeen eighteen nineteen".split())}
TENS = {w: 10 * i for i, w in enumerate("_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()) if w != "_"}
SCALES = {"hundred": 100, "thousand": 1000, "lakh": 100000, "million": 1000000, "crore": 10000000, "billion": 1000000000}


def spoken_numbers(text):
    """Every number the script says, as digits: 'eighty-three point two' -> 83.2, 'three hundred and four' -> 304,
    'twenty twelve' -> 2012, plus any digits written as digits."""
    found = set(re.findall(r"\d+(?:\.\d+)?", text))
    raw = text.lower().replace("-", " ").split()
    toks = [w.strip(".,!?;:'\"()") for w in raw]
    stops = {i for i, w in enumerate(raw) if w.rstrip("'\")").endswith((".", ",", "!", "?", ";", ":"))}   # punctuation ends a number
    i = 0
    while i < len(toks):
        if toks[i] not in UNITS and toks[i] not in TENS:
            i += 1
            continue
        total, cur, decimals, parts = 0, 0, "", []
        while i < len(toks):
            w = toks[i]
            if w in UNITS:
                if UNITS[w] >= 10 and cur in TENS.values():   # 'twenty twelve' is a year, not 32
                    parts.append(cur)
                    cur = 0
                cur += UNITS[w]
            elif w in TENS:
                if cur and cur % 100 not in (0,) and cur < 100:   # 'twenty twelve': two numbers spoken as one year
                    parts.append(cur)
                    cur = 0
                cur += TENS[w]
            elif w in SCALES:
                cur = max(cur, 1) * SCALES[w]
                if SCALES[w] >= 1000:
                    total, cur = total + cur, 0
            elif w == "and" and (cur or total) and i + 1 < len(toks) and (toks[i + 1] in UNITS or toks[i + 1] in TENS):
                pass
            elif w == "point" and i + 1 < len(toks) and toks[i + 1] in UNITS:
                while i + 1 < len(toks) and toks[i + 1] in UNITS and UNITS[toks[i + 1]] < 10:
                    i += 1
                    decimals += str(UNITS[toks[i]])
                    if i in stops:
                        break
            else:
                break
            i += 1
            if i - 1 in stops:
                break
        value = total + cur
        if parts:   # a year like 'twenty twelve' -> 2012, 'twenty twenty six' -> 2026
            found.add(str(parts[0] * 100 + value))
        found.add(f"{value}.{decimals}" if decimals else str(value))
    return found


def bad_numbers(cover, script_text):
    """Numbers on the cover (title or stat) that the script never says."""
    said = spoken_numbers(script_text)
    shown = re.findall(r"\d+(?:\.\d+)?", " ".join(cover.get("title", [])) + " " + cover.get("stat", ""))
    return [n for n in shown if n not in said and n.lstrip("0") not in said]


def endcard(cover, plan_id):
    """The house end card scene for a plan: cover first, then the spoken outro and the Follow button."""
    b = brand()
    say = b["outro_lines"][zlib.crc32(plan_id.encode()) % len(b["outro_lines"])]
    data = {"title": cover["title"], "mark": cover.get("mark", 0), "art": cover.get("art", []), "narrator": b["narrator"],
            "tagline": b["tagline"], "handle": b["handle"], "credit": b.get("credit", ""), "button": b["button"], "coverAt": b["cover_at"],
            "cues": {"follow": say.split()[0].strip(",.!?").lower()}}
    if cover.get("stat"):
        data["stat"] = cover["stat"]
    return {"type": "endcard", "say": say, "outro": True, "lead": b["lead_seconds"],
            "lines": [{"say": say, "delivery": {"energy": b["outro_energy"], "pause_before": b["lead_seconds"] + b.get("hold_before", 0.15)},
                       "beat": "outro", "devices": []}],
            "data": data, "enter": "whip-up", "energy": b["outro_energy"], "world": "house end card", "metaphor": "",
            "sfx": [{"at": "follow", "name": "pop", "gain": -12}]}


if __name__ == "__main__":
    print(json.dumps(make(sys.argv[1]), ensure_ascii=False, indent=1))
