"""The Daily Habit show maker (P24.4-P24.7): the ticked stories -> one episode, end to end, unattended.

    python -m frameflow.show make <day>          what the daily make runs for a show run (research -> card on Telegram)
    python -m frameflow.show render <day>        re-run from the voice on (keeps research and script)
    python -m frameflow.show theme <out.wav>     the original Daily Habit theme (ident + sting cut), for listening

Desks, each with a check: researcher (one per story, web search, sources re-loaded) -> fact-checker (skill
shorts-factcheck, per story) -> writer (rundown: an open, one 20-30 word segment per story with a witty line, an outro)
-> lints in code (words, digits, numbers vs verified facts, graphics) + an independent table read, fix rounds up to
research/show.json doctor_rounds -> narrator (Chatterbox house voice, Whisper word timing) -> director in code (a framing
pattern per topic, countdown, graphics, emotions) -> sound (stamp, original theme, ducked bed, SFX on visual events)
-> one render (scenes/_shared/show/show.js) -> QA (length, loudness, peak, black, captions) + a screening of the render
-> the videos row, the publish inputs, and the Telegram video card. Output: out/show/<slug>/ (gitignored).
"""
import argparse
import concurrent.futures as cf
import datetime as dt
import importlib.util
import json
import re
import shutil
import subprocess
import sys
from array import array
from pathlib import Path

import numpy as np

from frameflow import brief, build, captions, daily, llm, media, music, progress, qa, showdesk, sound, voice

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "out" / "show"
FPS = 30
SR = 48000
STING = 1.5
GAP = 0.3           # breath after each line
END_HOLD = 2.6
EMOTIONS = ["neutral", "excited", "surprised", "doubtful", "smug", "worried", "laughing", "serious"]
GRAPHICS = ["headline", "stat", "versus", "bars", "quote", "list"]
PATTERNS = [[(0, "split"), (0.55, "pip")], [(0, "pip"), (0.6, "split")], [(0, "split"), (0.45, "pip")], [(0, "pip"), (0.5, "split")]]   # Habit always on screen (an empty bottom half read as a dead frame, Ep 1 screening)

_spec = importlib.util.spec_from_file_location("factcheck", brief.FACTCHECK)
factcheck = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(factcheck)


def cfg():
    return showdesk.cfg()


def wps():
    return json.loads((ROOT / "research" / "quality-bar.json").read_text())["speech"]["words_per_second"]


# ---------- researcher + fact-checker, one story at a time ----------
RESEARCH_SYSTEM = """You are the researcher for The Daily Habit, a fast daily news show (8 stories, 8-10 seconds each) for
Indians aged 18-30. Research ONE story with web search and fetch: find the original reporting (the outlet's own page,
not a news aggregator link) and one more independent source when you can. Return 3-6 short facts, each a single checkable
claim with the exact URL of the page that states it. Numbers exactly as the source gives them, with what they refer to.
Prefer the facts that make the story land in 8 seconds: the number, the who, the so-what for a young Indian.
source_name: only the outlet's short name, nothing else (e.g. Reuters, Mint, The Verge). cautions: what must not be overstated.
Never invent a fact or a URL. If you cannot read any source, return an empty facts list."""

RESEARCH_SCHEMA = {"type": "object", "required": ["facts", "source_name", "cautions"], "properties": {
    "facts": {"type": "array", "maxItems": 6, "items": {"type": "object", "required": ["text", "source"],
                                                         "properties": {"text": {"type": "string"}, "source": {"type": "string"}}}},
    "source_name": {"type": "string"}, "cautions": {"type": "array", "items": {"type": "string"}}}}


def research_one(i, story):
    """One story's researched, fact-checked facts; cached per idea (a test run and the real episode share the work)."""
    cache = OUT / "_research" / f"{story.get('idea') or brief.slugify(story['title'])}.json"
    if cache.exists():
        r = json.loads(cache.read_text())
        for f in r["facts"]:
            f["id"] = re.sub(r"^s\d+", f"s{i}", f["id"])
        return {**r, "story": i, "source_name": outlet(r.get("source_name", ""))}
    r = _research_one(i, story)
    if len(r["facts"]) >= 2:   # a story the fact-checker dropped gets a fresh try next time
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(r, ensure_ascii=False, indent=1))
    return r


def _research_one(i, story):
    c = cfg()
    b = llm.call(f"Today is {dt.date.today().isoformat()}.\nStory: {story['title']}\nLink (may be an aggregator): {story['url']}\n"
                 f"Outlet: {story.get('outlet', '')}\nWhat we know: {story.get('summary', '')[:300]}\nResearch it.",
                 RESEARCH_SYSTEM, RESEARCH_SCHEMA, model=c.get("research_model", "sonnet"), tools="WebSearch,WebFetch",
                 purpose=f"show.research:{i}", effort="low", timeout=1200)
    facts = [{"id": f"s{i}f{k + 1}", "text": f["text"], "source": f["source"]} for k, f in enumerate(b["facts"])]
    loaded = [f for f in facts if brief.loads(f["source"])]
    facts = loaded or facts   # no page answers a plain request (bot walls): the fact-checker reads them with WebFetch
    if not facts:
        return {"story": i, "facts": [], "verdict": "no sources loaded", "source_name": b.get("source_name", "")}
    r = factcheck.check_brief(ROOT, {"topic": story["title"], "facts": facts})
    standing = [{"id": f["id"], "text": f["text"], "source": f["source"]} for f in r["facts"] if f.get("verdict") != "unreachable"]
    return {"story": i, "facts": standing, "verdict": r["summary"], "source_name": outlet(b.get("source_name") or story.get("outlet", "")),
            "cautions": b.get("cautions", [])}


def outlet(name):
    """'Reuters (via MarketScreener; ET carried it)' -> 'Reuters': the chip is on air, notes are not."""
    return re.split(r"\s*[(;,/]|\s+via\s+|\s+citing\s+", name.strip())[0][:26].strip()


def research(stories, out):
    path = out / "research.json"
    if path.exists():
        return json.loads(path.read_text())
    res = [None] * len(stories)
    with cf.ThreadPoolExecutor(max_workers=cfg().get("research_parallel", 4)) as ex:
        futs = {ex.submit(research_one, i + 1, s): i for i, s in enumerate(stories)}
        for f in cf.as_completed(futs):
            i = futs[f]
            try:
                res[i] = f.result()
            except Exception as e:   # one story's research failing drops that story, not the episode
                res[i] = {"story": i + 1, "facts": [], "verdict": f"failed: {str(e)[:200]}"}
            progress.note(f"story {i + 1}: {res[i]['verdict']}", facts=len(res[i]["facts"]))
    kept = [dict(stories[i], **r) for i, r in enumerate(res) if len(r["facts"]) >= 2]
    dropped = [stories[i]["headline"] for i, r in enumerate(res) if len(r["facts"]) < 2]
    if len(kept) < cfg()["min_pick"]:
        raise RuntimeError(f"only {len(kept)} stories survived research and fact-check (need {cfg()['min_pick']}); dropped: {dropped}")
    data = {"stories": kept, "dropped": dropped}
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1))
    return data


# ---------- writer, lints, table read, fix rounds ----------
WRITER_SYSTEM = """You write The Daily Habit, a daily news show for YouTube Shorts / Instagram Reels, read aloud by the narrator
Habit (warm, quick, a little cheeky; Indian, speaks clear English; audience Indians aged 18-30, most don't code).
Format: a cold open, then one segment per story in the given order, then the outro. Every segment is 22-28 spoken words
(about 8-10 seconds; never over 30): a hook that names the story, ONE fact (the strongest), why it matters to the viewer
in plain words, and a quick handoff into the next story (the last segment hands off to the outro).
Humour: at most MAX_JOKES witty lines in the whole episode, only where one comes naturally from the story (a light desi
comparison, a deadpan aside). Never force a pun; a clear, sharp line beats a weak joke. The owner found forced jokes
cringe, so when in doubt, leave it out.
Hard rules:
- Use only the verified facts given. Never add a number, name or claim that is not in them; never overstate (see cautions).
- No digits anywhere in `say`: write numbers as words the way a person says them ("ninety percent", "sixteen point three
  billion dollars", "sixty thousand"). Round only if the fact itself rounds.
- Plain spoken English, short sentences, no jargon without a two-word explanation, no "folks", no "buckle up",
  no "in today's episode", no greeting.
- open: 10-20 words, starts with "Breaking:" and teases the top two stories with a stake.
- outro: 10-20 words, a one-line wrap that calls back to one story, and ends exactly with "Make learning a Habit."
- witty: copy the exact witty sentence from `say` (verbatim), or "" when the segment has no joke (most segments).
- emotion: Habit's face for that line, one of neutral, excited, surprised, doubtful, smug, worried, laughing, serious.
  Match it to the line, and vary it across the episode.
- headline: the on-screen topic strip, at most 38 characters. wall: one big word or number for the studio wall, at most
  8 characters. breaking: the open's on-screen bar, at most 55 characters. title: the episode's post title, at most 60
  characters, naming the top story.
- graphic: what fills the screen while Habit speaks. Pick the type that shows the fact best and vary types:
  stat {value, label, sub} (value like "90%", "₹225 Cr", "$16.3B", "60,000"; digits allowed in graphics),
  versus {left:{label,value}, right:{label,value}, caption}, bars {items:[{label,value}] 2-4, caption},
  headline {top, bottom, kicker}, quote {text (max 20 words, verbatim from a fact), who}, list {title, items: 3 short}.
  Every number in a graphic must be in the verified facts. Labels short (max 28 characters).
Return JSON only."""

ANALOGIES = ROOT / "research" / "analogies.json"


def analogies():
    return json.loads(ANALOGIES.read_text())


def analogy_images():
    """The catalogue's pictures that the visual library already holds (judged once): the writer is offered only
    these, so a chosen gag always has its picture and always looks the same. No library yet = the whole catalogue."""
    a = analogies()
    idx_path = ROOT / json.loads((ROOT / "research" / "visual-sourcing.json").read_text())["library"] / "index.json"
    if not idx_path.exists():
        return list(a["images"])
    idx = json.loads(idx_path.read_text())
    return [k for k, name in a["images"].items() if "photo-" + re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") in idx]


def analogy_rules():
    a = analogies()
    tr = "\n".join(f"  {k}: {v['when']}. Fields: {v['fields']}." for k, v in a["treatments"].items())
    return (f"""- analogy: a picture gag that makes one segment land, at most {a['max_per_episode']} in the episode and only where it
  truly helps (most segments: treatment "none"). It appears on screen while the witty line (or the end of the segment)
  is said, so pair it with the segment's witty line when there is one. Pick the treatment by what the line needs:
{tr}
  image, left, right: only these image ids: {', '.join(analogy_images())}. A number in big/labels must be in the verified facts.""")


def writer_system():
    return WRITER_SYSTEM.replace("MAX_JOKES", str(cfg().get("max_jokes", 3))).replace("Return JSON only.", analogy_rules() + "\nReturn JSON only.")


G_ITEM = {"type": "object", "properties": {"label": {"type": "string"}, "value": {"type": "string"}}}
LINE = {"type": "object", "required": ["say", "emotion"], "properties": {"say": {"type": "string"}, "emotion": {"type": "string", "enum": EMOTIONS}}}
WRITER_SCHEMA = {"type": "object", "required": ["title", "breaking", "open", "segments", "outro"], "properties": {
    "title": {"type": "string"}, "breaking": {"type": "string"}, "open": LINE, "outro": LINE,
    "segments": {"type": "array", "items": {"type": "object",
                 "required": ["story", "say", "witty", "emotion", "headline", "wall", "facts", "graphic", "analogy"],
                 "properties": {"story": {"type": "integer"}, "say": {"type": "string"}, "witty": {"type": "string"},
                                "emotion": {"type": "string", "enum": EMOTIONS}, "headline": {"type": "string"},
                                "wall": {"type": "string"}, "facts": {"type": "array", "items": {"type": "string"}},
                                "graphic": {"type": "object", "required": ["type"], "properties": {
                                    "type": {"type": "string", "enum": GRAPHICS}, "value": {"type": "string"}, "label": {"type": "string"},
                                    "sub": {"type": "string"}, "top": {"type": "string"}, "bottom": {"type": "string"},
                                    "kicker": {"type": "string"}, "text": {"type": "string"}, "who": {"type": "string"},
                                    "title": {"type": "string"}, "caption": {"type": "string"},
                                    "left": G_ITEM, "right": G_ITEM, "items": {"type": "array", "items": {}}}},
                                "analogy": {"type": "object", "required": ["treatment"], "properties": {
                                    "treatment": {"type": "string", "enum": ["none", "compare", "scale", "photo", "stamp"]},
                                    "image": {"type": "string"}, "left": {"type": "string"}, "right": {"type": "string"},
                                    "left_label": {"type": "string"}, "right_label": {"type": "string"}, "joiner": {"type": "string"},
                                    "big": {"type": "string"}, "label": {"type": "string"}, "caption": {"type": "string"},
                                    "word": {"type": "string"}}}}}}}}


def stories_block(data):
    out = []
    for s in data["stories"]:
        out.append(f"STORY {s['story']} ({s['lane']}) {s['headline']} [source: {s.get('source_name', '')}]\n"
                   f"  a possible light angle (use only if it comes naturally): {s.get('pun', '')}\n"
                   + "\n".join(f"  {f['id']}: {f['text']}" for f in s["facts"])
                   + (f"\n  cautions: {'; '.join(s.get('cautions', [])[:3])}" if s.get("cautions") else ""))
    return "\n".join(out)


def words(text):
    return len(re.findall(r"[A-Za-z₹$%']+|\d+", text))


def lint(script, data):
    c, errs = cfg(), []
    lo, hi = c["segment_words"]
    order = [s["story"] for s in data["stories"]]
    if [g["story"] for g in script["segments"]] != order:
        errs.append(f"segments must cover stories {order} in that order, one each (got {[g['story'] for g in script['segments']]})")
    lines = [("open", script["open"]["say"], 10, 22), ("outro", script["outro"]["say"], 10, 22)] + \
            [(f"segment {g['story']}", g["say"], lo, hi) for g in script["segments"]]
    for name, say, a, b in lines:
        n = words(say)
        if not a <= n <= b:
            errs.append(f"{name}: {n} words (needs {a}-{b})")
        if re.search(r"\d", say):
            errs.append(f"{name}: digits in say ({say[:60]}...): write numbers as words")
    if not script["open"]["say"].lower().startswith("breaking"):
        errs.append("open must start with 'Breaking:'")
    if not script["outro"]["say"].rstrip().endswith("Make learning a Habit."):
        errs.append("outro must end exactly with 'Make learning a Habit.'")
    facts = {f["id"]: f for s in data["stories"] for f in s["facts"]}
    for g in script["segments"]:
        if g["witty"].strip() and g["witty"].strip().strip(".") not in g["say"]:
            errs.append(f"segment {g['story']}: witty line is not in say verbatim")
        if len(g["headline"]) > 40:
            errs.append(f"segment {g['story']}: headline over 38 characters")
        if len(g["wall"]) > 9:
            errs.append(f"segment {g['story']}: wall over 8 characters")
        gr = g["graphic"]
        need = {"stat": ["value", "label"], "versus": ["left", "right"], "bars": ["items"], "headline": ["top", "bottom"],
                "quote": ["text"], "list": ["title", "items"]}[gr["type"]]
        miss = [k for k in need if not gr.get(k)]
        if miss:
            errs.append(f"segment {g['story']}: {gr['type']} graphic lacks {miss}")
        if gr["type"] == "bars" and not 2 <= len(gr.get("items") or []) <= 4:
            errs.append(f"segment {g['story']}: bars need 2-4 items")
    errs += lint_analogies(script)
    said = " ".join(t for _, t, _, _ in lines)
    shown = " ".join(json.dumps(g["graphic"], ensure_ascii=False) for g in script["segments"]) + " " + \
        " ".join(f"{(g.get('analogy') or {}).get('big', '')} {(g.get('analogy') or {}).get('label', '')}" for g in script["segments"])
    for what, text in (("said", said), ("shown", re.sub(r'"type": "\w+"', "", shown))):
        r = factcheck.check_script(text, {"facts": list(facts.values())})
        if not r["pass"]:
            errs.append(f"numbers {what} but not in the verified facts: {r['unverified_numbers']}")
    secs = sum(words(t) for _, t, _, _ in lines) / wps() + STING + GAP * len(lines) + END_HOLD
    if not c["length"][0] - 8 <= secs <= c["length"][1]:
        errs.append(f"estimated length {secs:.0f} s (target {c['length'][0]}-{c['length'][1]} s)")
    jokes = sum(1 for g in script["segments"] if g["witty"].strip())
    if jokes > c.get("max_jokes", 3):
        errs.append(f"{jokes} witty lines (at most {c.get('max_jokes', 3)}: keep only the ones that come naturally)")
    types = [g["graphic"]["type"] for g in script["segments"]]
    if max(types.count(t) for t in set(types)) > 3:
        errs.append(f"graphics too samey: {types} (no type more than 3 times)")
    emos = [g["emotion"] for g in script["segments"]]
    if len(set(emos)) < 4:
        errs.append(f"emotions too samey: {emos} (use at least 4 different ones)")
    return errs


def lint_analogies(script):
    a, errs = analogies(), []
    used = [g for g in script["segments"] if (g.get("analogy") or {}).get("treatment", "none") != "none"]
    if len(used) > a["max_per_episode"]:
        errs.append(f"{len(used)} analogies (at most {a['max_per_episode']}: keep the ones that land best)")
    lim = {"left_label": 18, "right_label": 18, "label": 24, "caption": 30, "word": 14}
    for g in used:
        an, t = g["analogy"], g["analogy"]["treatment"]
        for k in a["treatments"][t]["needs"]:
            if an.get(k) not in analogy_images():
                errs.append(f"segment {g['story']}: analogy {t} needs {k} from the image list (got {an.get(k)!r})")
        if t == "stamp" and not 1 <= len(an.get("word", "")) <= 14:
            errs.append(f"segment {g['story']}: stamp word must be 1-14 characters")
        if t == "scale" and not an.get("big"):
            errs.append(f"segment {g['story']}: scale needs big (the multiplier or count)")
        errs += [f"segment {g['story']}: analogy {k} over {n} characters" for k, n in lim.items() if len(an.get(k) or "") > n]
    return errs


JUDGE_SYSTEM = """You are the independent script editor (table read) for The Daily Habit, a fast daily news show (8 stories
in about 85 seconds) read aloud by Habit for Indians aged 18-30. Read the script aloud in your head, against the verified
facts. Score each row 0-2 (2 = ready to air, 1 = mixed, 0 = broken):
hook (the open stops a scroll), clarity (each story is understood in one listen, no jargon), wit (the few witty lines
land naturally; any forced or cringe joke scores 0 for this row; no joke is better than a forced one), flow (handoffs make it one show, not a list), accuracy (every claim is
in the facts, nothing overstated, cautions respected), variety (emotions and graphics fit and vary), ending (the outro lands).
For every row under 2 give one concrete fix naming the segment. Be strict: 2 means a professional editor would air it.
The format is fixed; never suggest changing it: the open starts with "Breaking:" (10-20 words), every segment is 22-28
spoken words, numbers are spoken as words, the outro ends with "Make learning a Habit." Fixes must keep within it."""

JUDGE_SCHEMA = {"type": "object", "required": ["rows", "fixes"], "properties": {
    "rows": {"type": "object", "required": ["hook", "clarity", "wit", "flow", "accuracy", "variety", "ending"],
             "properties": {k: {"type": "integer", "minimum": 0, "maximum": 2} for k in ["hook", "clarity", "wit", "flow", "accuracy", "variety", "ending"]}},
    "fixes": {"type": "array", "items": {"type": "object", "required": ["row", "fix"], "properties": {"row": {"type": "string"}, "fix": {"type": "string"}}}}}}


def table_read(script, data):
    c = cfg()
    r = llm.call(f"VERIFIED FACTS\n{stories_block(data)}\n\nSCRIPT\n{json.dumps(script, ensure_ascii=False, indent=1)}",
                 JUDGE_SYSTEM, JUDGE_SCHEMA, model=c.get("judge_model", "opus"), purpose="show.tableread", effort="medium")
    total, mx = sum(r["rows"].values()), 2 * len(r["rows"])
    return {**r, "total": total, "max": mx, "pass": total >= c["pass_share"] * mx and min(r["rows"].values()) >= 1}


def write(data, out, ep, date):
    path = out / "script.json"
    if path.exists():
        return json.loads(path.read_text())
    c = cfg()
    lessons = (ROOT / "research" / "lessons-writer.txt")
    ask = (f"Episode {ep} of The Daily Habit, {date}. {len(data['stories'])} stories, in this order:\n{stories_block(data)}\n\n"
           + (f"House lessons from earlier videos (apply what fits a news rundown):\n{lessons.read_text()[:2500]}\n\n" if lessons.exists() else "")
           + "Write the episode.")
    script = llm.call(ask, writer_system(), WRITER_SCHEMA, model=c["writer_model"], purpose="show.write", effort="high", timeout=1500)
    history, best, reads = [], None, 0
    for rnd in range(2 * c["doctor_rounds"] + 2):   # a lint-only repair may follow any fix round that broke the format
        errs = lint(script, data)
        tr = None
        if not errs:
            tr = table_read(script, data)
            reads += 1
            if best is None or tr["total"] > best[1]["total"]:
                best = (script, tr)
        history.append({"round": rnd, "lint": errs, "table_read": tr})
        progress.note(f"script round {rnd}: {len(errs)} lint problems" + (f", table read {tr['total']}/{tr['max']}" if tr else ""))
        if (tr and tr["pass"]) or (tr and reads > c["doctor_rounds"]) or rnd == 2 * c["doctor_rounds"] + 1:
            break
        notes = "\n".join(f"- {e}" for e in errs) or "\n".join(f"- {f['row']}: {f['fix']}" for f in tr["fixes"])
        script = llm.call(f"{ask}\n\nYour draft:\n{json.dumps(script, ensure_ascii=False)}\n\nFix these problems (keep what works, "
                          f"change only what the notes need, every rule still applies; count the words of every segment: 22-28):\n{notes}",
                          writer_system(), WRITER_SCHEMA, model=c["doctor_model"], purpose=f"show.doctor{rnd + 1}", effort="medium", timeout=1500)
    (out / "script-rounds.json").write_text(json.dumps(history, ensure_ascii=False, indent=1))
    if best is None:
        raise RuntimeError(f"no draft passed the script checks: {history[-1]['lint'][:4]}")
    script = best[0]
    script["table_read"] = best[1]
    path.write_text(json.dumps(script, ensure_ascii=False, indent=1))
    return script


# ---------- visuals (P25.2): logos, photos and the source's headline for every story (visual-sourcing skill) ----------
VISUALS = Path.home() / "Talha_Khan" / "Claude" / "skills" / "visual-sourcing" / "scripts" / "visuals.py"
CUE_SYSTEM = """You pick the real visuals for a fast news Short. For each story, name what the viewer should SEE while
it is said: main = the one person, product, place or thing the story is about (kind person | product | place | thing),
or kind none when it is only a company or an abstract idea; wiki = that subject's exact English Wikipedia page title,
or "" if unsure; logo = the company or brand whose logo belongs on screen ("" if none). Prefer the subject a viewer
would recognise (Sam Altman, iPhone, Dalal Street), never a generic word. Return JSON only."""
CUE_SCHEMA = {"type": "object", "required": ["stories"], "properties": {"stories": {"type": "array", "items": {
    "type": "object", "required": ["story", "kind", "name", "wiki", "logo"], "properties": {
        "story": {"type": "integer"}, "kind": {"type": "string", "enum": ["person", "product", "place", "thing", "none"]},
        "name": {"type": "string"}, "wiki": {"type": "string"}, "logo": {"type": "string"}}}}}}


def page_for(s):
    """The article to screenshot: the story's own link unless it is an aggregator redirect, else the first fact's source."""
    for u in [s.get("url", "")] + [f["source"] for f in s["facts"]]:
        if u and "news.google.com" not in u:
            return u
    return ""


def visuals(script, data, out):
    """Cues for every story (subject photo, logo, the source's headline) and every analogy image -> visual-sourcing.
    Cues already in the ledger are kept (a revise only fetches what is new); the skill's library keeps picks stable."""
    vdir = out / "visuals"
    vdir.mkdir(parents=True, exist_ok=True)
    led_path, cue_path = vdir / "ledger.json", vdir / "cues.json"
    ledger = json.loads(led_path.read_text()) if led_path.exists() else []
    cues = json.loads(cue_path.read_text()) if cue_path.exists() else []
    stories = {s["story"]: s for s in data["stories"]}
    if not cues:
        ask = "\n".join(f"STORY {g['story']}: {stories[g['story']]['headline']} | {g['say']}" for g in script["segments"])
        picks = llm.call(ask, CUE_SYSTEM, CUE_SCHEMA, model=cfg().get("visuals", {}).get("model", "haiku"), purpose="show.visual-cues", timeout=600)
        for p in picks["stories"]:
            s = stories.get(p["story"])
            if not s:
                continue
            if p["kind"] != "none" and p["name"]:
                cues.append({"id": f"s{p['story']}-photo", "kind": "photo", "name": p["name"], "wiki": p["wiki"] or None,
                             "context": s["headline"]})
            if p["logo"]:
                cues.append({"id": f"s{p['story']}-logo", "kind": "logo", "name": p["logo"]})
            if page_for(s):
                cues.append({"id": f"s{p['story']}-shot", "kind": "screenshot", "url": page_for(s)})
    imgs = analogies()["images"]
    for g in script["segments"]:   # analogy images: fixed catalogue names, so the library returns the same picture
        an = g.get("analogy") or {}
        for k in ("image", "left", "right"):
            iid = an.get(k)
            if iid in imgs and not any(c["id"] == f"a-{iid}" for c in cues):
                cues.append({"id": f"a-{iid}", "kind": "photo", "name": imgs[iid], "context": "an everyday picture for a visual analogy in an Indian news Short"})
    cue_path.write_text(json.dumps(cues, ensure_ascii=False, indent=1))
    have = {r["id"] for r in ledger}
    todo = [c for c in cues if c["id"] not in have]
    if todo:
        from frameflow import direct as directmod
        batch = vdir / f"batch-{len(list(vdir.glob('batch-*'))) + 1}"
        batch.mkdir()
        (batch / "cues.json").write_text(json.dumps(todo, ensure_ascii=False, indent=1))
        directmod.skill([VISUALS, "--project", ROOT, "find", batch / "cues.json", "--out", batch], timeout=1800, strict=True)
        for r in json.loads((batch / "ledger.json").read_text()):
            if not r.get("missing"):
                shutil.move(str(batch / r["file"]), vdir / r["file"])
            ledger.append(r)
        shutil.rmtree(batch)
        led_path.write_text(json.dumps(ledger, ensure_ascii=False, indent=1))
    by = {}
    for r in ledger:
        if r.get("missing"):
            continue
        src = f"assets/media/{r['file']}"
        if r["id"].startswith("a-"):
            by.setdefault("analogy", {})[r["id"][2:]] = {"src": src, "w": r.get("width"), "h": r.get("height"),
                                                         "credit": f"{r['author'][:30]} · {r['licence']}"}
            continue
        story, kind = int(r["id"].split("-")[0][1:]), r["kind"]
        if kind == "photo":
            by.setdefault(story, {})["photo"] = {"src": src, "w": r["width"], "h": r["height"],
                                                "credit": f"Photo: {r['author'][:40]} · {r['licence']} · {r['source']}"}
        elif kind == "screenshot":
            by.setdefault(story, {})["shot"] = {"src": src, "w": r["width"], "h": r["height"], "head": r.get("headline"),
                                               "credit": f"Source: {r['source'].removeprefix('www.')}"}
        elif kind == "logo":
            by.setdefault(story, {})["logo"] = {"src": src, "name": r["name"]}
    return by, ledger


def gag_for(g, seg, mine_words, media_by):
    """The segment's analogy as a render spec, timed to the witty line (or 55% of the segment), after the real visuals."""
    an = g.get("analogy") or {}
    t = an.get("treatment", "none")
    if t == "none":
        return None
    pics = (media_by or {}).get("analogy", {})
    spec = {"treatment": t, **{k: an.get(k, "") for k in ("left_label", "right_label", "joiner", "big", "label", "caption", "word")}}
    for k in analogies()["treatments"][t]["needs"]:
        if an.get(k) not in pics:
            return None   # its picture wasn't found: no half gag
        spec[k] = pics[an[k]]
    at = seg["dur"] * 0.55
    if g.get("witty") and g["witty"].strip() in g["say"] and mine_words:
        k = words(g["say"][:g["say"].index(g["witty"].strip())])
        if k < len(mine_words):
            at = mine_words[k]["s"] - seg["start"]
    lo = (seg.get("media") or {}).get("dur", 0) + 0.3
    spec["dur"] = 2.4
    spec["at"] = round(min(max(at, lo), seg["dur"] - spec["dur"] - 0.2), 2)
    return spec if spec["at"] >= lo - 0.01 else None


# ---------- narrator ----------
ENERGY = {"neutral": 0.55, "excited": 0.75, "surprised": 0.7, "doubtful": 0.5, "smug": 0.6, "worried": 0.5, "laughing": 0.75, "serious": 0.45}


def lines_of(script):
    out = [{"id": "open", "say": script["open"]["say"], "emotion": script["open"]["emotion"]}]
    out += [{"id": f"t{k}", "say": g["say"], "emotion": g["emotion"]} for k, g in enumerate(script["segments"], 1)]
    out.append({"id": "outro", "say": script["outro"]["say"], "emotion": script["outro"]["emotion"]})
    return out


def narrate(script, out):
    vd = out / "voice"
    if (vd / "words.json").exists():
        return vd
    lines = lines_of(script)
    vs = {"engine": "chatterbox", "model": "standard", "tempo": 1.0, "seed": 7, "pad": GAP,
          "lines": [{"id": l["id"], "say": l["say"], "energy": ENERGY.get(l["emotion"], 0.6), "beat": "hook" if l["id"] == "open" else
                     "outro" if l["id"] == "outro" else "and", "emotion": l["emotion"]} for l in lines]}
    (out / "voice-script.json").write_text(json.dumps(vs, ensure_ascii=False, indent=1))
    info = voice.tts(out / "voice-script.json", vd)
    progress.note(f"voice: {info['engine']}, {info['total']:.1f} s, {info['wpm']} wpm", fallback=info.get("fallback_reason"))
    captions.align(vd)
    return vd


def envelope(wav):
    raw = subprocess.run(["ffmpeg", "-v", "quiet", "-i", str(wav), "-ac", "1", "-ar", "12000", "-f", "s16le", "-"], capture_output=True).stdout
    a = array("h")
    a.frombytes(raw)
    hop = 12000 // FPS
    vals = [(sum(x * x for x in a[i:i + hop]) / max(len(a[i:i + hop]), 1)) ** 0.5 for i in range(0, len(a), hop)]
    ref = sorted(vals)[int(len(vals) * 0.95)] or 1
    return [round(min(v / ref, 1.0), 3) for v in vals]


# ---------- director (code): timeline, framings, package ----------
def direct(script, data, vd, ep, day, media_by=None):
    D = {l["id"]: l for l in json.loads((vd / "durations.json").read_text())["lines"]}
    heard = json.loads((vd / "words.json").read_text())
    lines = lines_of(script)
    shown = captions.respell(heard, " ".join(l["say"] for l in lines))
    stories = {s["story"]: s for s in data["stories"]}
    t, segs, voice_at, words, env = 0.3, [], [], [], []
    c = {"set": cfg()["set"], "look": cfg()["look"], "episode": ep, "topics": len(script["segments"]),
         "date": dt.date.fromisoformat(day).strftime("%d %b").upper(), "breakingText": script["breaking"],
         "ticker": [g["headline"].upper() for g in script["segments"]]}

    def place(lid, seg, min_dur=0.0):
        nonlocal t, env
        info = D[lid]
        dur = max(info["seconds"] + GAP, min_dur)
        seg.update({"start": round(t, 3), "dur": round(dur, 3), "id": lid})
        a, b = info["start"] - 0.05, info["start"] + info["seconds"] + 0.05
        mine = [w for w in shown if a <= w["s"] < b]
        grp, n = 0, 0
        for w in mine:   # caption chunks: up to 3 words, a new chunk after a comma, colon or full stop
            words.append({"w": w["w"], "s": round(t + w["s"] - info["start"], 3), "e": round(t + w["e"] - info["start"], 3), "g": f"{len(segs)}-{grp}"})
            n += 1
            if n == 3 or re.search(r"[,.;:!?]$", w["w"]):
                grp, n = grp + 1, 0
        e = envelope(vd / info["file"])
        f0 = int(round(t * FPS))
        env += [0.0] * max(f0 - len(env), 0)
        env[f0:f0 + len(e)] = e
        voice_at.append((vd / info["file"], t, info["seconds"]))
        segs.append(seg)
        t += dur

    c["breakingAt"] = round(t + 0.05, 3)
    place("open", {"shot": "wide", "emotion": script["open"]["emotion"], "wall": "BREAKING", "wallSub": "THE DAILY HABIT"})
    c["breakingDur"] = D["open"]["seconds"]
    c["stingAt"] = round(t, 3)
    segs.append({"start": round(t, 3), "dur": STING, "shot": "wide", "wall": "EP " + str(ep), "emotion": "excited"})
    t += STING
    for k, g in enumerate(script["segments"], 1):
        pat = PATTERNS[(k - 1) % len(PATTERNS)]
        s = stories[g["story"]]
        lo = cfg()["segment_seconds"][0]
        seg = {"topic": k, "lane": s["lane"], "headline": g["headline"], "source": s.get("source_name", ""), "shot": pat[0][1],
               "emotion": g["emotion"], "wall": g["wall"].upper(), "wallSub": s["lane"].upper(), "g": g["graphic"]}
        place(f"t{k}", seg, lo)
        seg["shots"] = [[round(seg["dur"] * f, 2), shot] for f, shot in pat]
        m = (media_by or {}).get(g["story"])
        if m and (m.get("photo") or m.get("shot")):   # real visuals for the first ~45% of the story, then the graphic
            seg["media"] = {**m, "dur": round(min(max(seg["dur"] * 0.45, 3.0), 5.0), 2)}
        gag = gag_for(g, seg, [w for w in words if w["s"] >= seg["start"] - 0.01 and w["s"] < seg["start"] + seg["dur"]], media_by)
        if gag:
            seg["gag"] = gag
    c["tickerAt"] = round(t + 0.2, 3)
    place("outro", {"shot": "wide", "emotion": script["outro"]["emotion"], "wall": "SEE YOU", "wallSub": "TOMORROW"})
    c["endAt"] = round(segs[-1]["start"] + D["outro"]["seconds"] - 0.2, 3)
    t = c["endAt"] + END_HOLD
    segs[-1]["dur"] = round(t - segs[-1]["start"], 3)
    c["endDur"] = round(t - c["endAt"], 3)
    c.update({"dur": round(t + 0.2, 3), "segments": segs, "words": words, "env": env, "envFps": FPS})
    segs[-1]["dur"] = round(c["dur"] - segs[-1]["start"], 3)
    return c, voice_at


# ---------- sound: stamp, theme, bed, SFX, ducking ----------
def theme(seconds=3.6, seed=11):
    """The Daily Habit theme ident: a news-desk figure (four-chord stabs, a rising pluck motif, kick on the beat, a
    final hit). Original, synthesised here; deterministic."""
    bpm, n = 120, int(seconds * SR)
    beat = int(60 / bpm * SR)
    rng = np.random.default_rng(seed)
    mono = np.zeros(n + SR)
    prog = [("F", "min"), ("C#", "maj"), ("D#", "maj"), ("C", "maj")]
    for b, (root, q) in enumerate(prog):
        start = b * 2 * beat
        if start >= n:
            break
        fr = music.chord(root, q, 4)
        stab = sum(music.pluck(f, int(0.45 * SR)) for f in fr) / len(fr)
        music.mix_in(mono, start, stab * 0.5)
        music.mix_in(mono, start, music.pad(music.chord(root, q, 3), 2 * beat, 0.6, rng) * 0.25)
        for k in range(2):
            music.mix_in(mono, start + k * beat, music.kick(int(0.35 * SR)) * 0.5)
    motif = [0, 3, 7, 12, 10, 12, 15, 19]
    base = music.hz("F", 5)
    for i, st in enumerate(motif):
        music.mix_in(mono, int(i * beat / 2), music.pluck(base * 2 ** (st / 12), int(0.3 * SR)) * 0.22)
    hit = int(seconds * SR) - int(0.9 * SR)
    music.mix_in(mono, hit, sum(music.pluck(f, int(0.9 * SR)) for f in music.chord("F", "min", 3)) * 0.4)
    music.mix_in(mono, hit, music.kick(int(0.5 * SR)) * 0.7)
    mono = music.lowpass(mono[:n], 9000)
    st = music.reverb(mono, 0.25)
    st *= music.env(n, int(0.01 * SR), int(0.4 * SR))[:, None]
    return (st / (np.max(np.abs(st)) + 1e-9) * 0.9).astype(np.float32)


def mix(c, voice_at, out):
    m = cfg().get("music", {})
    total = c["dur"]
    n = int((total + 0.5) * SR)
    vtrack = np.zeros((n, 2), np.float32)
    for f, start, _ in voice_at:
        a = sound.load(f)
        i = int(start * SR)
        end = min(i + len(a), n)
        vtrack[i:end] += a[:end - i]
    # music: the theme under the open's tail and the sting, then the bed from the first topic to the end card
    th = theme()
    th_at = max(c["stingAt"] + STING - len(th) / SR, 0.0)
    mtrack = np.zeros((n, 2), np.float32)
    i = int(th_at * SR)
    mtrack[i:i + len(th)] += th[:n - i] * 10 ** (m.get("theme_gain_db", -8) / 20)
    bed_from = c["stingAt"] + STING - 0.2
    track = m.get("track", "investigations")
    if track.startswith("synth:"):
        bed = music.bed(track[6:], total - bed_from + 1.0, seed=5).astype(np.float32)
    else:   # a real track, looped to the show's length, like the single-story Shorts
        src = sound.load(sound.MUSIC_DIR / sound.TRACKS[track][0])
        need = int((total - bed_from + 1.0) * SR)
        bed = np.concatenate([src] * (need // len(src) + 1))[:need].astype(np.float32)
        bed /= max(np.max(np.abs(bed)), 1e-9) / 0.9
    fade = min(int(0.6 * SR), len(bed))
    bed[:fade] *= np.linspace(0, 1, fade)[:, None]
    i = int(bed_from * SR)
    bed = bed[:n - i]
    gain = np.full(n, 10 ** (m.get("bed_gain_db", -13) / 20), np.float32)
    talk = np.zeros(n, np.float32)
    for _, start, secs in voice_at:
        talk[int(start * SR):int((start + secs) * SR)] = 1
    k = int(0.15 * SR)
    talk = np.convolve(talk, np.ones(k) / k, mode="same").astype(np.float32)
    duck = 10 ** (m.get("duck_db", -7) / 20)
    g = gain * (1 - talk * (1 - duck))
    mtrack[i:i + len(bed)] += bed * g[i:i + len(bed), None]
    # end card: the theme's sting cut again
    j = int((c["endAt"] + 0.1) * SR)
    cut = th[-int(1.6 * SR):]
    mtrack[j:j + len(cut)] += cut[:max(n - j, 0)] * 10 ** ((m.get("theme_gain_db", -8) - 2) / 20)
    # SFX on visual events
    sheet = [{"t": c["breakingAt"], "name": "stamp", "gain": -6}, {"t": c["stingAt"], "name": "whoosh-big", "gain": -12}]
    for s in c["segments"]:
        if not s.get("topic"):
            continue
        sheet.append({"t": s["start"] - 0.05, "name": "whoosh", "gain": -16})
        g0 = s["start"] + (s["media"]["dur"] if s.get("media") else 0)   # the graphic enters after the real visuals
        if s.get("media"):
            sheet.append({"t": s["start"] + 0.5, "name": "pop", "gain": -20})   # the logo badge
            sheet.append({"t": g0 - 0.15, "name": "whoosh", "gain": -20})
        if s.get("g"):
            sheet.append({"t": g0 + 0.2, "name": "pop", "gain": -18})
            if s["g"]["type"] in ("stat", "versus", "bars"):
                sheet.append({"t": g0 + 1.4, "name": "ding", "gain": -22})
            if s["g"]["type"] == "headline":
                sheet.append({"t": g0 + 0.3, "name": "slam", "gain": -16})
        if s.get("gag"):   # analogy visuals (P25.2.4): one fixed sound per treatment
            t = s["start"] + s["gag"]["at"]
            sheet.append({"t": t, "name": {"stamp": "slam", "scale": "pop", "compare": "whoosh", "photo": "whoosh"}[s["gag"]["treatment"]], "gain": -16})
            if s["gag"]["treatment"] == "compare":
                sheet.append({"t": t + 0.7, "name": "ding", "gain": -22})
        for off, _ in s.get("shots", [])[1:]:
            sheet.append({"t": s["start"] + off - 0.1, "name": "whoosh", "gain": -20})
        for sec in (3, 2, 1):   # countdown ticks into the next topic
            sheet.append({"t": s["start"] + s["dur"] - sec, "name": "tick", "gain": -24})
    sfx = sound.place_sfx(sheet, total)[:n]
    stems = vtrack + mtrack + np.pad(sfx, ((0, n - len(sfx)), (0, 0)))
    raw = out / "premix.wav"
    music.write_wav(raw, stems / max(np.max(np.abs(stems)), 1.0))
    final = out / "mix.wav"
    media.ffmpeg("-i", str(raw), "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-ar", "48000", "-ac", "2", str(final))
    (out / "sfx.json").write_text(json.dumps(sheet, indent=1))
    (out / "music.json").write_text(json.dumps({"track": track, "bed_from": bed_from, **m}, indent=1))
    return final, sheet


# ---------- the HyperFrames project and the render ----------
def project(c, audio, out):
    pd = out / "project"
    if pd.exists():
        shutil.rmtree(pd)
    shutil.copytree(build.SHARED, pd / "assets")
    with open(pd / "assets" / "theme.css", "a") as f:
        f.write("\n" + (build.SHARED / "themes" / "paper-press.css").read_text())
    shutil.copy(audio, pd / "assets" / "mix.wav")
    if (out / "visuals").exists():   # the visual-sourcing files the segments point at (assets/media/...)
        (pd / "assets" / "media").mkdir(exist_ok=True)
        for f in (out / "visuals").iterdir():
            if f.suffix.lower() in (".png", ".jpg", ".jpeg", ".svg", ".webp", ".gif"):
                shutil.copy(f, pd / "assets" / "media" / f.name)
    fonts = "\n    ".join(f'<link rel="preload" href="assets/vendor/fonts/{f.name}" as="font" type="font/woff2" crossorigin />'
                          for f in sorted((build.SHARED / "vendor" / "fonts").glob("*.woff2")))
    warm = ('<div aria-hidden="true" style="position:absolute;opacity:0">' + "".join(
        f'<span style="font-family:{ff};font-weight:{w}">Aa₹</span>' for ff, w in
        [('"FF Serif"', 800), ('"FF Display"', 700), ('"FF Body"', 700), ('"FF Mono"', 700), ('"FF Hand"', 700)]) + "</div>")
    (pd / "index.html").write_text(f"""<!doctype html>
<html lang="en" data-resolution="portrait">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=1080, height=1920" />
    <title>The Daily Habit · Ep {c['episode']}</title>
    <link rel="stylesheet" href="assets/theme.css" />
    {fonts}
    <script src="assets/vendor/gsap.min.js"></script>
    <script src="assets/vendor/DrawSVGPlugin.min.js"></script>
    <script src="assets/vendor/MotionPathPlugin.min.js"></script>
    <script src="assets/vendor/rough.min.js"></script>
    <script>gsap.registerPlugin(DrawSVGPlugin, MotionPathPlugin);</script>
    <script src="assets/ff-kit.js"></script>
    <script src="assets/show/show.js"></script>
    <style>#root {{ position: relative; width: 100%; height: 100%; overflow: hidden; }}</style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-start="0" data-duration="{c['dur']}" data-width="1080" data-height="1920">
      {warm}
      <audio id="mix" src="assets/mix.wav" data-start="0" data-duration="{c['dur']}" data-track-index="0"></audio>
      <div id="show"></div>
    </div>
    <script type="application/json" id="cfg">{build.json_for_html(c)}</script>
    <script>
      window.__timelines = window.__timelines || {{}};
      SHOW.build(JSON.parse(document.getElementById("cfg").textContent));
    </script>
  </body>
</html>
""")
    (pd / "package.json").write_text(json.dumps({"name": f"daily-habit-ep{c['episode']}", "private": True, "type": "module"}))
    (out / "show-plan.json").write_text(json.dumps({k: v for k, v in c.items() if k not in ("env", "words")}, ensure_ascii=False, indent=1))
    return pd


def stills(video, times, out, name):
    d = out / name
    d.mkdir(exist_ok=True)
    files = []
    for i, t in enumerate(times):
        f = d / f"{i:02d}.png"
        media.ffmpeg("-ss", f"{t:.2f}", "-i", str(video), "-frames:v", "1", "-vf", "scale=360:640", str(f))
        files.append(f)
    sheet = out / f"{name}.png"
    cols = 6
    rows = (len(files) + cols - 1) // cols
    args = []
    for f in files:
        args += ["-i", str(f)]
    layout = "|".join(f"{(i % cols) * 360}_{(i // cols) * 640}" for i in range(len(files)))
    media.ffmpeg(*args, "-filter_complex", f"{''.join(f'[{i}:v]' for i in range(len(files)))}xstack=inputs={len(files)}:layout={layout}:fill=black",
                 str(sheet))
    return sheet


SCREEN_SYSTEM = """You are the screening editor of The Daily Habit, a vertical news show (1080x1920) for YouTube Shorts and
Instagram Reels. You get a contact sheet of stills (left to right, top to bottom, with their times) and the script.
Open the image with the Read tool and look closely. Score each row 0-2 (2 = ready to air):
look (polished, consistent, on-brand), readability (graphic text and numbers readable at phone size, nothing cut off or
overlapping), framing (Habit and graphics placed well; nothing important in the bottom 420 px or the right 180 px below
y 1000, where the platform buttons sit), captions (readable, never covering a key graphic), package (topic strip,
countdown, bug and source chip clear and not cluttered), story (each still tells its topic), habit (the narrator looks
alive and his face fits the line). For every row under 2 give one concrete fix. Be strict and specific."""
SCREEN_ROWS = ["look", "readability", "framing", "captions", "package", "story", "habit"]
SCREEN_SCHEMA = {"type": "object", "required": ["rows", "fixes"], "properties": {
    "rows": {"type": "object", "required": SCREEN_ROWS, "properties": {k: {"type": "integer", "minimum": 0, "maximum": 2} for k in SCREEN_ROWS}},
    "fixes": {"type": "array", "items": {"type": "object", "required": ["row", "fix"], "properties": {"row": {"type": "string"}, "fix": {"type": "string"}}}}}}


def screening(sheet, times, script):
    c = cfg()
    r = llm.call(f"Contact sheet: {sheet}\nStill times (s): {', '.join(f'{t:.1f}' for t in times)}\n\nScript:\n"
                 + "\n".join(f"- {l['id']}: {l['say']}" for l in lines_of(script)),
                 SCREEN_SYSTEM, SCREEN_SCHEMA, model=c.get("judge_model", "opus"), tools="Read", add_dirs=[sheet.parent],
                 purpose="show.screening", effort="medium")
    total, mx = sum(r["rows"].values()), 2 * len(r["rows"])
    return {**r, "total": total, "max": mx, "pass": total >= c["pass_share"] * mx and min(r["rows"].values()) >= 1}


def check_render(final, c, script, vd, out):
    bar = json.loads((ROOT / "research" / "quality-bar.json").read_text())
    secs = media.duration(final)
    lufs, peak = qa.loudness_and_peak(final)
    black = qa.black_stretches(final, bar["picture"]["black_seconds"])
    blank = qa.blank_spans(final)
    lo, hi = cfg()["length"]
    heard = " ".join(w["w"] for w in json.loads((vd / "words.json").read_text()))
    werr = captions.wer(" ".join(l["say"] for l in lines_of(script)), heard)
    L = bar["sound"]["lufs"]
    gates = {"length": {"pass": lo - 8 <= secs <= hi + 5, "detail": f"{secs:.1f} s (target {lo}-{hi})"},
             "loudness": {"pass": lufs is not None and L[0] - 0.5 <= lufs <= L[1] + 0.5 and (peak is None or peak <= bar["sound"]["true_peak"] + 0.5),
                          "detail": f"{lufs} LUFS, peak {peak} dBFS"},
             "black": {"pass": not black, "detail": f"{len(black)} black stretches"},
             "blank": {"pass": not blank, "detail": f"{len(blank)} blank stretches"},
             "captions": {"pass": werr <= bar["captions"]["max_word_error"], "detail": f"word error {werr:.2f}"}}
    return {"pass": all(g["pass"] for g in gates.values()), "gates": gates, "seconds": secs}


# ---------- the whole episode ----------
def slug_for(day, ep):
    return f"{day}-daily-habit-ep{ep}"


def make_day(day):
    run = daily.get(day)
    o = json.loads(run["options"])
    ep, stories = o["episode"], o["chosen"]
    slug = slug_for(day, ep)
    out = OUT / slug
    out.mkdir(parents=True, exist_ok=True)
    daily.update(day, state="making", note=f"show make started: Ep {ep}, {len(stories)} stories -> {out}")
    with progress.step("research + fact-check every story", desk="factcheck") as info:
        data = research(stories, out)
        info.update({"kept": len(data["stories"]), "dropped": data["dropped"]})
    if data["dropped"]:
        daily.update(day, note=f"dropped after fact-check: {data['dropped']}")
    with progress.step("write the rundown (writer, lints, table read)", desk="writer") as info:
        script = write(data, out, ep, dt.date.fromisoformat(day).strftime("%d %b %Y"))
        info.update({"table_read": f"{script['table_read']['total']}/{script['table_read']['max']}"})
    from frameflow import hookpick
    if hookpick.cfg()["enabled"] and not script.get("hook_pick"):   # Talha picks the open from 10 hooks (P25.1.2)
        script = hookpick.pick(script, data, out, day)
        daily.update(day, note=f"open chosen ({script['hook_pick']['by']}): {script['open']['say'][:80]}")
    result = produce(day, ep, slug, data, script, out)
    daily.update(day, video_id=result["video"], note=f"made {result['video']}: {result['status']}, review {result['review']}")
    with progress.step("send video card to Telegram"):
        daily.video_card(day)
    try:   # the day's card post (carousel) from the episode's verified facts, approved separately, posted with the show
        from frameflow import cards
        with progress.step("make card post (carousel)"):
            cards.make_for_day(day, ROOT / "briefs" / f"{slug}.json")
        daily.update(day, note="card post made")
    except Exception as e:
        daily.update(day, note=f"card post failed: {str(e)[:200]}")
    return result


def produce(day, ep, slug, data, script, out):
    (out / "publish.json").unlink(missing_ok=True)   # a new render gets new post text (written with its video card)
    media_by, vis_ledger = {}, []
    if cfg().get("visuals", {}).get("enabled", True):
        with progress.step("visuals: logos, photos, headline screenshots", desk="visuals") as info:
            try:
                media_by, vis_ledger = visuals(script, data, out)
            except Exception as e:   # no visuals is a weaker video, not a failed one: the graphics still carry it
                info["error"] = str(e)[:200]
                daily.update(day, note=f"visuals failed, graphics only: {str(e)[:150]}")
            info["stories_with_media"] = sum(1 for m in media_by.values() if m.get("photo") or m.get("shot"))
    with progress.step("voice (narrator)", desk="narrator"):
        vd = narrate(script, out)
    with progress.step("direct (framings, package, emotions)", desk="director"):
        c, voice_at = direct(script, data, vd, ep, day, media_by)
    with progress.step("sound (stamp, theme, bed, SFX)", desk="sound") as info:
        audio, sheet = mix(c, voice_at, out)
        info["cues"] = len(sheet)
    with progress.step("render", desk="render") as info:
        pd = project(c, audio, out)
        code, log = build.check(pd)
        check_errors = [l for l in log.splitlines() if "✗ error" in l]   # a QA gate, not a stop: Talha sees it on the card
        info["check_errors"] = len(check_errors)
        final = build.render(pd, out / "final.mp4", quality="looks")
        info["seconds"] = c["dur"]
    with progress.step("QA + screening", desk="qc") as info:
        q = check_render(final, c, script, vd, out)
        q["gates"]["layout"] = {"pass": not check_errors, "detail": "; ".join(e[:140] for e in check_errors[:3]) or "hyperframes check: 0 errors"}
        q["pass"] = all(g["pass"] for g in q["gates"].values())
        times = [c["breakingAt"] + 1.0, c["stingAt"] + 0.7] + [s["start"] + s["dur"] * f for s in c["segments"] if s.get("topic") for f in (0.3, 0.8)] + [c["endAt"] + 1.0]
        sheet_png = stills(final, times, out, "contact")
        scr = screening(sheet_png, times, script)
        info.update({"qa": q["pass"], "screening": f"{scr['total']}/{scr['max']}"})
    tr = script["table_read"]
    review = {"total": scr["total"] + tr["total"], "max": scr["max"] + tr["max"], "pass": scr["pass"] and tr["pass"],
              "rows": {**{f"script {k}": v for k, v in tr["rows"].items()}, **{f"screen {k}": v for k, v in scr["rows"].items()}},
              "fixes": scr["fixes"] + tr["fixes"], "table_read": tr, "screening": scr}
    (out / "review.json").write_text(json.dumps(review, ensure_ascii=False, indent=1))
    (out / "qa.json").write_text(json.dumps(q, ensure_ascii=False, indent=1))
    cover_at = c["stingAt"] + 0.7
    media.ffmpeg("-ss", f"{cover_at:.2f}", "-i", str(final), "-frames:v", "1", str(out / "cover.png"))
    (out / "report.json").write_text(json.dumps({"seconds": q["seconds"], "final": str(final), "cover": str(out / "cover.png"),
                                                 "cover_at": cover_at, "episode": ep, "stories": len(script["segments"])}, indent=1))
    led = sound.ledger()
    assets = [{"file": f"sfx2/{n}.wav", **{k: led.get(f"sfx2/{n}.wav", {}).get(k) for k in ("source", "licence", "url", "author")}}
              for n in sorted({x["name"] for x in sheet})]
    assets += [{"file": "theme", "source": "frameflow.show.theme (synthesised)", "licence": "original work by Talha Khan"}]
    track = cfg().get("music", {}).get("track", "")
    if track and not track.startswith("synth:"):
        assets.append(led.get(f"music-cc/{sound.TRACKS[track][0]}", {"file": track}))
    assets += [{"file": f"visuals/{r['file']}", "source": r["source"], "licence": r["licence"], "tier": r["tier"],
                "url": r.get("page"), "author": r["author"]} for r in vis_ledger if not r.get("missing")]
    (out / "assets.json").write_text(json.dumps(assets, indent=1))
    facts = [dict(f, story=s["story"]) for s in data["stories"] for f in s["facts"]]
    stories = {s["story"]: s for s in data["stories"]}
    plan = {"id": slug, "version": 2, "title": script["title"], "lane": "global-tech", "show": True, "episode": ep,
            "scenes": [{"say": l["say"], "sources": sorted({f["source"] for f in stories[g["story"]]["facts"]}) if g else []}
                       for l, g in zip(lines_of(script), [None] + script["segments"] + [None])]}
    (out / "plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=1))
    heads = "; ".join(f"{g['headline']}" for g in script["segments"])
    (ROOT / "briefs" / f"{slug}.json").write_text(json.dumps({
        "topic": f"The Daily Habit Ep {ep}: today's {len(script['segments'])} stories ({heads})",
        "angle_hint": "An episode digest carousel: slide 1 a bold hook naming the biggest story and that there are "
                      f"{len(script['segments'])} stories today; then one stat, compare or fact slide per story for the first five "
                      "stories in the episode's order (each with its own source); a close slide inviting people to watch the full "
                      "episode for all of them.", "facts": facts, "lane": "global-tech",
                                                              "cautions": [x for s in data["stories"] for x in s.get("cautions", [])][:12]},
                                                             ensure_ascii=False, indent=1))
    from frameflow import videos
    status = "awaiting-approval" if q["pass"] and review["pass"] else "needs-work"
    con = videos.db()
    con.execute("INSERT OR REPLACE INTO videos (id, idea_id, plan, out_dir, lane, title, qa_pass, review_total, review_pass, status, note, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (slug, None, str(out / "plan.json"), str(out), "global-tech", script["title"], int(q["pass"]), review["total"], int(review["pass"]),
                 status, f"The Daily Habit Ep {ep} (frameflow.show)", videos.now(), videos.now()))
    con.commit()
    return {"video": slug, "status": status, "review": f"{review['total']}/{review['max']}", "qa": q["pass"], "final": str(final)}


def rerender(day):
    run = daily.get(day)
    o = json.loads(run["options"])
    slug = slug_for(day, o["episode"])
    out = OUT / slug
    data, script = json.loads((out / "research.json").read_text()), json.loads((out / "script.json").read_text())
    r = produce(day, o["episode"], slug, data, script, out)
    daily.update(day, video_id=r["video"], note=f"re-rendered {r['video']}: {r['status']}, review {r['review']}")
    return r


def revise(day, notes):
    """Talha's Revise on a show episode: his words and ticked issues go to the writer as notes (the script, the graphics,
    the faces), then the voice, the render, QA and screening run again, and a new card goes out."""
    run = daily.get(day)
    o = json.loads(run["options"])
    slug = slug_for(day, o["episode"])
    out = OUT / slug
    data, old = json.loads((out / "research.json").read_text()), json.loads((out / "script.json").read_text())
    n = len(list(out.glob("revision-*.json"))) + 1
    shutil.copy(out / "script.json", out / f"revision-{n}.before.json")
    c = cfg()
    ask = f"Episode {o['episode']} of The Daily Habit. Stories in order:\n{stories_block(data)}"
    old.pop("table_read", None)
    with progress.step("writer: Talha's revise notes", desk="writer"):
        script = llm.call(f"{ask}\n\nThe aired draft:\n{json.dumps(old, ensure_ascii=False)}\n\nThe owner asked for these changes "
                          f"(apply them exactly; keep everything else; every rule still applies):\n{notes}",
                          writer_system(), WRITER_SCHEMA, model=c["doctor_model"], purpose="show.revise", effort="medium", timeout=1500)
        errs = lint(script, data)
        if errs:
            script = llm.call(f"{ask}\n\nYour draft:\n{json.dumps(script, ensure_ascii=False)}\n\nFix these problems, keeping the owner's "
                              f"changes:\n" + "\n".join(f"- {e}" for e in errs), writer_system(), WRITER_SCHEMA, model=c["doctor_model"],
                              purpose="show.revise-fix", effort="medium", timeout=1500)
            errs = lint(script, data)
        if errs:
            raise RuntimeError(f"the revised script fails its checks: {errs[:4]}")
        script["table_read"] = table_read(script, data)
    (out / f"revision-{n}.json").write_text(json.dumps({"notes": notes, "script": script}, ensure_ascii=False, indent=1))
    (out / "script.json").write_text(json.dumps(script, ensure_ascii=False, indent=1))
    shutil.rmtree(out / "voice", ignore_errors=True)
    r = produce(day, o["episode"], slug, data, script, out)
    daily.update(day, video_id=r["video"], note=f"revised (round {run['revisions']}): {r['status']}, review {r['review']}")
    return r


def main():
    ap = argparse.ArgumentParser(description="The Daily Habit show maker")
    ap.add_argument("cmd", choices=["make", "render", "theme", "cards"])
    ap.add_argument("arg")
    a = ap.parse_args()
    if a.cmd == "theme":
        music.write_wav(Path(a.arg), theme())
        return print(a.arg)
    if a.cmd == "cards":   # the day's card post by hand (from the episode's brief)
        from frameflow import cards
        o = json.loads(daily.get(a.arg)["options"])
        return print(cards.make_for_day(a.arg, ROOT / "briefs" / f"{slug_for(a.arg, o['episode'])}.json"))
    print(json.dumps(make_day(a.arg) if a.cmd == "make" else rerender(a.arg), indent=1))


if __name__ == "__main__":
    main()
