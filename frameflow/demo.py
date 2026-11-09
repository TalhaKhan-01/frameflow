"""The live demo: one plain-words brief -> one finished, fact-checked explainer episode in under 15 minutes.

    uv run python -m frameflow.demo prep "<brief>"   before the meeting: find the story, research + fact-check it, split it
                                                     into 3-4 beats, source its pictures (all cached)
    uv run python -m frameflow.demo run  "<brief>"   on stage: write -> visuals -> voice -> direct -> sound -> render ->
                                                     QA + critic -> video sent to Telegram

One topic told as 3-4 beats (what it is, what happened, why it matters, what's next), each its own segment with real
photos and a graphic, in The Daily Habit's look. The run writes its progress to logs/progress-2099-12-31.jsonl, so
Frameflow Control's Making view shows it live. Nothing is posted: the video goes to Telegram only.
"""
import datetime as dt
import json
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEMO = ROOT / "out" / "demo"
DAY = "2099-12-31"
os.environ.setdefault("FF_PROGRESS", str(ROOT / "logs" / f"progress-{DAY}.jsonl"))

from frameflow import build, llm, progress, show, telegram  # noqa: E402

BEATS_SYSTEM = """You plan a one-topic news explainer for The Daily Habit (a vertical Short read by the narrator Habit for
Indians aged 18-30). Split the verified facts into 3 or 4 beats that tell the story in order: what it is, what happened
(the news), why it matters to the viewer, what's next. Each beat gets a headline (at most 38 characters, punchy, true)
and the ids of the facts it uses (each fact in one beat only; every beat needs at least 1 fact). Return JSON only."""
BEATS_SCHEMA = {"type": "object", "required": ["beats"], "properties": {"beats": {"type": "array", "minItems": 3, "maxItems": 4, "items": {
    "type": "object", "required": ["headline", "facts"], "properties": {"headline": {"type": "string"}, "facts": {"type": "array", "items": {"type": "string"}}}}}}}


def slug(brief):
    return re.sub(r"[^a-z0-9]+", "-", brief.lower()).strip("-")[:40]


def story_for(brief):
    """A prepared story whose words match the brief best (out/demo/<slug>/story.json), else the base story.json."""
    words = set(re.findall(r"[a-z0-9]{3,}", brief.lower()))
    best, score = None, 0
    for f in DEMO.glob("*/story.json"):
        s = json.loads(f.read_text())
        n = len(words & set(re.findall(r"[a-z0-9]{3,}", (s["title"] + " " + s["headline"] + " " + s.get("summary", "")).lower())))
        if n > score:
            best, score = f.parent, n
    if not best:
        sys.exit(f"no prepared story matches '{brief}': run prep first")
    return best


def beats(folder):
    """research-one.json (one researched, fact-checked story) -> data with one 'story' per beat (cached in data.json)."""
    path = folder / "data.json"
    if path.exists():
        return json.loads(path.read_text())
    s = json.loads((folder / "story.json").read_text())
    r = json.loads((folder / "research-one.json").read_text())
    facts = {f["id"]: f for f in r["facts"]}
    plan = llm.call("FACTS\n" + "\n".join(f"[{f['id']}] {f['text']}" for f in r["facts"]), BEATS_SYSTEM, BEATS_SCHEMA,
                    model="sonnet", purpose="demo.beats", timeout=600)["beats"]
    stories = []
    for k, b in enumerate(plan, 1):
        fs = [dict(facts[i], id=f"s{k}f{n}") for n, i in enumerate(b["facts"], 1) if i in facts]
        if fs:
            stories.append({**{x: s.get(x) for x in ("title", "url", "outlet", "source_name", "lane", "idea")},
                            "headline": b["headline"][:38], "story": len(stories) + 1,
                            "facts": [dict(f, id=f"s{len(stories) + 1}f{n}") for n, f in enumerate(fs, 1)],
                            "cautions": r.get("cautions", []), "verdict": r.get("verdict", "")})
    data = {"stories": stories, "dropped": [], "topic": s["headline"]}
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1))
    return data


def prep(brief):
    folder = story_for(brief)
    with progress.step("demo prep", desk="showrunner"):
        if not (folder / "research-one.json").exists():
            s = json.loads((folder / "story.json").read_text())
            (folder / "research-one.json").write_text(json.dumps(show.research_one(1, s), ensure_ascii=False, indent=1))
        data = beats(folder)
    print(json.dumps({"folder": str(folder), "beats": [s["headline"] for s in data["stories"]],
                      "facts": sum(len(s["facts"]) for s in data["stories"])}, indent=1))


_cfg = show.cfg
show.cfg = lambda: {**_cfg(), "length": [40, 75], "min_pick": 1}   # one topic in 3-4 beats runs ~45-65 s, not the show's 75-100


def run(brief):
    folder = story_for(brief)
    data = beats(folder)
    out = show.OUT / f"demo-{folder.name}-{time.strftime('%H%M')}"
    out.mkdir(parents=True, exist_ok=True)
    (out / "research.json").write_text(json.dumps(data, ensure_ascii=False, indent=1))
    t0 = time.time()
    with progress.step("make", day=DAY, brief=brief):
        with progress.step("research + fact-check (prepared)", desk="factcheck") as info:
            info.update(beats=len(data["stories"]), facts=sum(len(s["facts"]) for s in data["stories"]))
        with progress.step("write the episode (writer, lints, table read)", desk="writer") as info:
            script = show.write(data, out, 0, dt.date.today().strftime("%d %b %Y"))
            info.update(table_read=f"{script['table_read']['total']}/{script['table_read']['max']}")
        with progress.step("visuals: photos, logos, headline pages", desk="visuals") as info:
            media_by, ledger = show.visuals(script, data, out)
            info.update(assets=sum(1 for r in ledger if not r.get("missing")))
        with progress.step("voice (narrator)", desk="narrator"):
            vd = show.narrate(script, out)
        with progress.step("direct (framings, graphics, faces)", desk="director"):
            c, voice_at = show.direct(script, data, vd, 0, dt.date.today().isoformat(), media_by)
        with progress.step("sound (stamp, theme, bed, SFX)", desk="sound"):
            audio, sheet = show.mix(c, voice_at, out)
        with progress.step("render", desk="render") as info:
            pd = show.project(c, audio, out)
            build.check(pd)
            final = build.render(pd, out / "final.mp4", quality="looks")
            info.update(seconds=c["dur"])
        with progress.step("QA + critic", desk="qc") as info:
            q = show.check_render(final, c, script, vd, out)
            times = show.still_times(c)[:1] + show.still_times(c)[2:-1]
            png = show.stills(final, times, out, "contact")
            scr = show.screening(png, times, script, c)
            info.update(qa=q["pass"], screening=f"{scr['total']}/{scr['max']}")
        with progress.step("send the video to Telegram", desk="owner"):
            mins = (time.time() - t0) / 60
            telegram.send_file("video", final, caption=f"Frameflow live demo: {data['topic']}\nMade in {mins:.1f} min · "
                               f"table read {script['table_read']['total']}/{script['table_read']['max']} · screening {scr['total']}/{scr['max']} · "
                               f"QA {'pass' if q['pass'] else 'see report'} · not posted")
    res = {"video": str(final), "minutes": round((time.time() - t0) / 60, 1), "seconds": c["dur"], "qa": q["gates"],
           "table_read": script["table_read"]["total"], "screening": scr["total"]}
    (out / "demo.json").write_text(json.dumps(res, indent=1, default=str))
    print(json.dumps(res, indent=1, default=str))


def start(brief):
    """Launch `run` in the background and return at once: the pipeline runs on its own, Frameflow Control's Making
    panel shows it live, the video arrives on Telegram."""
    import subprocess
    folder = story_for(brief)   # fail now, in the chat, if no prepared story matches
    (ROOT / "logs" / f"progress-{DAY}.jsonl").unlink(missing_ok=True)   # a fresh timeline for this run
    log = open(ROOT / "logs" / "demo-run.log", "a")
    p = subprocess.Popen(["uv", "run", "python", "-m", "frameflow.demo", "run", brief], cwd=ROOT, stdout=log,
                         stderr=subprocess.STDOUT, start_new_session=True)
    print(f"Frameflow started (pid {p.pid}) on: {json.loads((folder / 'story.json').read_text())['headline']}\n"
          f"Watch it live: http://127.0.0.1:7310 (Making panel). The video arrives on Telegram; nothing is posted.")


if __name__ == "__main__":
    cmd, brief = sys.argv[1], " ".join(sys.argv[2:])
    {"prep": prep, "run": run, "start": start}[cmd](brief)
