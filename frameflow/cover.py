"""Cover and outro: the thumbnail title for a script, and the house end card scene the pipeline appends.

    python -m frameflow.cover <out-dir>      write <out-dir>/cover.json from writer/script.json (once; delete it to redo)

The end card (scenes/endcard) opens as the cover (Habit mark, a 1-3 line title, the key drawing, one stat) for
brand.json's lead_seconds of silence, so the thumbnail frame has no captions; then Habit says the outro line and
the Follow button appears. pipeline.render saves that frame as cover.png and records its time for Instagram.
"""
import json
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


def make(out_dir, model="haiku"):
    out = Path(out_dir)
    path = out / "cover.json"
    if path.exists():
        return json.loads(path.read_text())
    script = json.loads((out / "writer" / "script.json").read_text())
    text = "\n".join(b["say"] for b in script["beats"])
    c = llm.call(f"Video title: {script['title']}\nScript:\n{text}", SYSTEM.format(icons=", ".join(scene_plan.ICONS)), SCHEMA,
                 model=model, purpose=f"cover:{out.name}", effort="low")
    c["title"] = [l.upper() for l in c["title"]][:3]
    c["mark"] = min(c["mark"], len(c["title"]) - 1)
    path.write_text(json.dumps(c, ensure_ascii=False, indent=1))
    return c


def endcard(cover, plan_id):
    """The house end card scene for a plan: cover first, then the spoken outro and the Follow button."""
    b = brand()
    say = b["outro_lines"][zlib.crc32(plan_id.encode()) % len(b["outro_lines"])]
    data = {"title": cover["title"], "mark": cover.get("mark", 0), "art": cover.get("art", []), "narrator": b["narrator"],
            "tagline": b["tagline"], "handle": b["handle"], "button": b["button"], "coverAt": b["cover_at"],
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
