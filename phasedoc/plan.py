#!/usr/bin/env python3
"""Frameflow phasedoc: the task tree for the Frameflow build arc (phasedoc skill).

    plan.py init                       create/seed the database (re-running adds new tasks, keeps status)
    plan.py tick <id>                  mark done: ONLY after the leaf's acceptance test has passed
    plan.py part <id>                  mark partially complete
    plan.py cancel <id> <reason>       drop a leaf (or every leaf under a stage); reason becomes a note
    plan.py note <id> <text>           attach context
    plan.py add <id> <parent> <title> <acceptance> <component>   register a leaf found mid-arc
    plan.py tree                       print the tree
    plan.py components                 per-component rollup (what the cockpit reads)
    plan.py mirror                     regenerate BUILDPLAN.md

Every state change regenerates BUILDPLAN.md: commit it together with plan.db.
"""
import datetime as dt
import json
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DB = HERE / "plan.db"
MIRROR = HERE / "BUILDPLAN.md"

SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
  id TEXT PRIMARY KEY, parent TEXT NOT NULL DEFAULT '', title TEXT NOT NULL,
  acceptance TEXT NOT NULL DEFAULT '', component TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','partial','done','cancelled')),
  created_at TEXT, updated_at TEXT, done_at TEXT);
CREATE TABLE IF NOT EXISTS notes (task_id TEXT NOT NULL, ts TEXT NOT NULL, text TEXT NOT NULL);
"""

# (id, parent, title, acceptance, component). Parents have no acceptance test; every leaf has one.
TASKS = [
    ("P0", "", "Setup and foundations", "", ""),
    ("P0.1", "P0", "Accounts and keys", "", ""),
    ("P0.1.1", "P0.1", "Password manager and two-factor sign-in on every Frameflow account",
     "Talha confirms in chat: Bitwarden holds the Frameflow logins, and 2FA (authenticator app) is on for both Google accounts and Instagram", "setup"),
    ("P0.1.2", "P0.1", "YouTube Data API key works",
     "a channels.list call for UCrcF7Q5J4kEENdJuA8BPQxQ with YOUTUBE_API_KEY from ~/.config/frameflow/secrets.env returns the channel title (1 quota unit); key value never printed", "setup"),
    ("P0.1.3", "P0.1", "Stock media API keys (Pexels, Pixabay)",
     "secrets check shows PEXELS_API_KEY and PIXABAY_API_KEY set, and one search call to each returns at least 1 result", "setup"),
    ("P0.1.4", "P0.1", "YouTube channel and Instagram Creator account exist",
     "curl -s -o /dev/null -w '%{http_code}' returns 200 for https://www.youtube.com/channel/UCrcF7Q5J4kEENdJuA8BPQxQ and https://www.instagram.com/madebythirdspace/", "setup"),
    ("P0.2", "P0", "Repository and vault", "", ""),
    ("P0.2.1", "P0.2", "One private repo holds code, config and vault",
     "GH_TOKEN=$(gh auth token --user TalhaKhan-01) gh repo view TalhaKhan-01/frameflow shows PRIVATE; vault/ is tracked; git log origin/main..HEAD is empty", "setup"),
    ("P0.2.2", "P0.2", "Obsidian opens the in-repo vault with its plugins",
     "~/Talha_Khan/Projects/Frameflow is a symlink to ~/Talha_Khan/Code/frameflow/vault, and Obsidian shows the hub's Dataview dashboard with Templater, Git and Terminal enabled (Talha confirms)", "setup"),
    ("P0.2.3", "P0.2", "Secrets stay out of git",
     "stat -c %a ~/.config/frameflow/secrets.env prints 600, and a git grep over all history for key patterns (AIza…, ghp_…, sk-ant-…) finds nothing", "setup"),

    ("P1", "", "Research: niche, deep study, quality bar", "", ""),
    ("P1.1", "P1", "Niche study", "", ""),
    ("P1.1.1", "P1.1", "niche-study skill runs end to end on Frameflow's lanes",
     "python3 -I ~/Talha_Khan/Claude/skills/niche-study/scripts/niche_study.py --project . score prints a scored row for all 6 lanes, and report writes vault/Docs/Niche Study Results <date>.md", "research"),
    ("P1.1.2", "P1.1", "Every lane's sample is at least 70% on-topic",
     "niche-study score: kept/found >= 0.70 for every lane (spot-check of 6 dropped titles per lane shows real off-topic videos)", "research"),
    ("P1.1.3", "P1.1", "Weekly lane mix decided from the evidence",
     "vault/Decisions/Lane Mix.md exists with status accepted, naming per-lane frequency and citing the niche and deep study numbers", "research"),
    ("P1.2", "P1", "Deep study of breakout Shorts", "", ""),
    ("P1.2.1", "P1.2", "deep-study skill measures clips: speech start, words/min, cuts, loudness, contact sheets",
     "vault/Docs/Deep Study <date>.md lists at least 25 measured clips with cuts/10s, LUFS and caption status; local Whisper fills blocked captions", "research"),
    ("P1.2.2", "P1.2", "Controlled vocabulary and footage field for annotations",
     "deep_study.py annotate rejects a JSON row whose hook_type is not in the vocabulary (non-zero exit), and accepts footage=original|reused|ai-generated|mixed", "research"),
    ("P1.2.3", "P1.2", "English-only sample: 10 breakouts per lane, all annotated visually",
     "deep-study report shows at least 50 measured English-title clips across the 6 lanes, every one annotated (no Devanagari or Hinglish titles in the clip table)", "research"),
    ("P1.3", "P1", "Quality bar v1", "", ""),
    ("P1.3.1", "P1.3", "Quality Bar note with numeric targets from the evidence",
     "vault/Wiki/Concepts/Quality Bar.md (status growing) has a table of at least 8 targets (length, speech start, words/min, cuts/10s, loudness, hook rules, captions, ending), each with a derived_from citing the deep study or a benchmark", "quality"),
    ("P1.3.2", "P1.3", "Hook and script rules written as a checklist the review step can apply",
     "vault/Docs/Script Rules.md lists at least 10 pass/fail rules, each linked to Quality Bar or a deep-study clip", "quality"),

    ("P2", "", "Voice", "", ""),
    ("P2.1", "P2", "Local text-to-speech installed in the project",
     "uv run python -m frameflow.voice sample \"Hello from Frameflow\" writes a WAV longer than 1 s using Kokoro, with no global installs", "voice"),
    ("P2.2", "P2", "House voice chosen by ear",
     "vault/Decisions/House Voice.md accepted, after Talha listened to at least 4 samples (Kokoro and one alternative such as Chatterbox), naming voice, speed and licence", "voice"),
    ("P2.3", "P2", "Voice step: script lines to per-scene audio plus durations",
     "frameflow voice tts on a 5-line sample script writes 5 WAVs and durations.json; each clip is 48 kHz mono and the joined voice measures -16 to -14 LUFS", "voice"),

    ("P3", "", "Scene library (motion-graphics templates)", "", ""),
    ("P3.1", "P3", "Renderer decided after a spike",
     "the same 5 s 1080x1920 title card is rendered in HyperFrames and in Remotion; vault/Decisions/Renderer.md accepted with render time, determinism (two renders give identical frame hashes) and licence", "scenes"),
    ("P3.2", "P3", "Scene-plan contract with a validator",
     "tests/test_scene_plan.py passes: a valid sample plan validates, and plans with an unknown scene type, a missing field or a total over 60 s are rejected", "scenes"),
    ("P3.3", "P3", "Visual identity locked",
     "vault/Docs/Visual Identity.md accepted by Talha: palette tokens, a licensed font pairing, motion language, safe zones for both platforms, and one signature move", "scenes"),
    ("P3.4", "P3", "Scene templates", "", ""),
    ("P3.4.1", "P3.4", "Headline reveal",
     "rendering scenes/headline-reveal/sample.json gives a 1080x1920 clip of the planned length; two renders give identical frame hashes at t=1 s", "scenes"),
    ("P3.4.2", "P3.4", "Stat counter",
     "rendering scenes/stat-counter/sample.json gives a 1080x1920 clip; the final frame shows the target number (frame check); two renders identical at t=1 s", "scenes"),
    ("P3.4.3", "P3.4", "Comparison split (e.g. India vs USA vs UAE prices)",
     "rendering scenes/comparison/sample.json gives a 1080x1920 clip with 3 columns from the JSON; two renders identical at t=1 s", "scenes"),
    ("P3.4.4", "P3.4", "Animated chart (bar or line)",
     "rendering scenes/chart/sample.json from a CSV gives a 1080x1920 clip; values in the last frame match the CSV; two renders identical at t=1 s", "scenes"),
    ("P3.4.5", "P3.4", "Code or repo card",
     "rendering scenes/code-card/sample.json shows syntax-coloured code (Shiki) and repo stats; two renders identical at t=1 s", "scenes"),
    ("P3.4.6", "P3.4", "News snapshot with highlight",
     "a deterministic Playwright capture of a sample article page plus highlight animation renders at 1080x1920 with the source credit visible", "scenes"),
    ("P3.4.7", "P3.4", "Low-poly 3D explainer shot",
     "a 5 s low-poly 3D scene (Blender or Three.js) renders headless at 1080x1920 from a JSON parameter file in under 5 minutes", "scenes"),
    ("P3.4.8", "P3.4", "Word-pop caption layer",
     "given word timings, the caption layer highlights each word within 1 frame of its time (checked at 5 sample words)", "captions"),

    ("P4", "", "Ideas and scripts", "", ""),
    ("P4.1", "P4", "Idea collector (RSS, Hacker News, GitHub Trending, YouTube trends)",
     "frameflow ideas collect inserts at least 30 new ideas from at least 4 sources into data/frameflow.db, with source URL and lane", "ideas"),
    ("P4.2", "P4", "Idea ranking in one batched model call",
     "frameflow ideas rank sends one claude -p call (Haiku) for all fresh ideas and stores a ranked list with angle and lane; output validates against the schema", "ideas"),
    ("P4.3", "P4", "frameflow-script skill: script plus scene plan",
     "for a ranked idea, the skill outputs a script and a scene plan that pass the P3.2 validator and every rule in Script Rules.md checked automatically", "script"),
    ("P4.4", "P4", "Every claim carries a source",
     "the validator fails a plan where any factual line has no source URL, and passes the sample plan where all do", "script"),

    ("P5", "", "Assets and licences", "", ""),
    ("P5.1", "P5", "Keyless stock fetchers (Openverse, Wikimedia Commons, NASA)",
     "frameflow assets search \"data center\" returns results from all 3 sources and downloads one file of each with source, licence and author recorded", "assets"),
    ("P5.2", "P5", "Licence ledger for every render",
     "the QA step fails a render that uses an asset without a ledger row (source, licence, URL, author) and passes when all rows exist", "assets"),
    ("P5.3", "P5", "Music and sound-effect library",
     "data/library/ holds at least 10 music beds and 20 sound effects, each with a ledger row whose licence allows commercial use", "assets"),

    ("P6", "", "Assembly and quality checks", "", ""),
    ("P6.1", "P6", "Captions from real word timings",
     "frameflow captions on a rendered voice track produces word timings whose text matches the script with word error rate under 10% (local Whisper)", "captions"),
    ("P6.2", "P6", "One command renders a full Short",
     "frameflow render out/sample/plan.json produces a 1080x1920 MP4 under 60 s with voice, scenes, captions and music in one run", "render"),
    ("P6.3", "P6", "Automatic quality checks",
     "frameflow qa fails a test video that breaks each rule in turn (length, size, loudness outside -15 to -13 LUFS, black frames over 0.5 s, caption mismatch, missing licence row) and passes the clean one", "qa"),
    ("P6.4", "P6", "Model review against the quality bar",
     "frameflow review sends one call with key frames and the script and returns pass/fix JSON with a score per Quality Bar row", "qa"),
    ("P6.5", "P6", "Human approval gate",
     "a video cannot reach the publish step until Talha marks it approved (status column), checked by trying to publish an unapproved video", "qa"),

    ("P7", "", "Publishing and feedback", "", ""),
    ("P7.1", "P7", "Publish pack per platform",
     "for an approved video, out/<id>/publish.md holds a YouTube title, description, tags, and an Instagram caption with hashtags, within platform length limits", "publish"),
    ("P7.2", "P7", "Manual upload checklist and post log",
     "after uploading, frameflow posted <id> <youtube-url> <instagram-url> records both links; both URLs return 200", "publish"),
    ("P7.3", "P7", "48-hour stats entry",
     "frameflow stats <id> stores views, average % viewed, likes, shares, saves (and viewed-vs-swiped when available) for both platforms", "feedback"),
    ("P7.4", "P7", "Weekly learning report",
     "frameflow learn writes vault/Docs/Week <n> Learnings.md comparing top and bottom videos and proposing at least 3 quality-bar or prompt changes", "feedback"),

    ("P8", "", "Launch", "", ""),
    ("P8.1", "P8", "Pilot: 3 videos in 3 different lanes published",
     "3 posted rows in the post log, each passed QA and approval, in 3 different lanes, live on both platforms", "launch"),
    ("P8.2", "P8", "Cadence week: at least 1 video every day for 7 days",
     "the post log shows at least one published video on each of 7 consecutive days", "launch"),
    ("P8.3", "P8", "First-week retrospective and mix adjustment",
     "vault/Decisions/Lane Mix.md updated (or superseded) with week-one numbers, and the log has a closing entry for the week", "launch"),
]


def now():
    return dt.datetime.now().replace(microsecond=0).isoformat()


def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


def get(con, task_id):
    row = con.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    if not row:
        sys.exit(f"no task {task_id}")
    return row


def is_leaf(con, task_id):
    return not con.execute("SELECT 1 FROM tasks WHERE parent=?", (task_id,)).fetchone()


def leaves_under(con, task_id):
    if is_leaf(con, task_id):
        return [task_id]
    out = []
    for (kid,) in con.execute("SELECT id FROM tasks WHERE parent=? ORDER BY id", (task_id,)).fetchall():
        out += leaves_under(con, kid)
    return out


def set_status(con, task_id, status):
    get(con, task_id)
    if not is_leaf(con, task_id) and status != "cancelled":
        sys.exit(f"{task_id} is not a leaf: tick, part and note work on leaves (cancel can take a stage)")
    t = now()
    con.execute("UPDATE tasks SET status=?, updated_at=?, done_at=? WHERE id=?",
                (status, t, t if status == "done" else None, task_id))


def note(con, task_id, text):
    get(con, task_id)
    con.execute("INSERT INTO notes VALUES (?,?,?)", (task_id, now(), text))


def rollup(con):
    comps = {}
    for r in con.execute("SELECT * FROM tasks ORDER BY id"):
        if r["component"] and is_leaf(con, r["id"]):
            comps.setdefault(r["component"], []).append(r["status"])
    out = {}
    for k, sts in sorted(comps.items()):
        counted = [s for s in sts if s != "cancelled"]
        done, partial = counted.count("done"), counted.count("partial")
        state = "green" if counted and done == len(counted) else "amber" if done or partial else "grey"
        out[k] = {"total": len(counted), "done": done, "partial": partial, "state": state}
    return out


MARK = {"done": "[x]", "partial": "[~]", "open": "[ ]", "cancelled": "[-]"}


def lines(con, parent="", depth=0):
    out = []
    for r in con.execute("SELECT * FROM tasks WHERE parent=? ORDER BY id", (parent,)).fetchall():
        leaf = is_leaf(con, r["id"])
        if leaf:
            out.append(("  " * depth) + f"- {MARK[r['status']]} **{r['id']}** {r['title']}  \n"
                       + ("  " * depth) + f"  _Acceptance:_ {r['acceptance']}")
            for n in con.execute("SELECT * FROM notes WHERE task_id=? ORDER BY ts", (r["id"],)):
                out.append(("  " * depth) + f"  _Note {n['ts'][:10]}:_ {n['text']}")
        else:
            leaves = leaves_under(con, r["id"])
            sts = [get(con, l)["status"] for l in leaves if get(con, l)["status"] != "cancelled"]
            out.append(("  " * depth) + f"- **{r['id']} {r['title']}** ({sts.count('done')}/{len(sts)})")
            out += lines(con, r["id"], depth + 1)
    return out


def mirror(con):
    leaves = [r for r in con.execute("SELECT * FROM tasks").fetchall() if is_leaf(con, r["id"])]
    counted = [r for r in leaves if r["status"] != "cancelled"]
    done = sum(r["status"] == "done" for r in counted)
    text = [
        "# Frameflow buildplan (generated)", "",
        "> Generated by `phasedoc/plan.py` on every change. Do not edit by hand; commit it with `plan.db`.",
        "> **Retrospective seeding (2026-10-23):** the arc was set up after setup and research work had started. "
        "Leaves ticked at seeding have tick timestamps of the seeding date; each was ticked only after its "
        "acceptance test was run that day. Partial leaves carry a note saying what is still missing.", "",
        f"**{done}/{len(counted)} leaves done** · [x] done · [~] partial · [ ] open · [-] cancelled", "",
        *lines(con), "",
    ]
    MIRROR.write_text("\n".join(text))


def main():
    a = sys.argv[1:]
    if not a or a[0] in ("-h", "--help"):
        print(__doc__)
        return
    con, cmd = db(), a[0]
    if cmd == "init":
        ids = {row[0] for row in TASKS}
        for tid, parent, _, acceptance, comp in TASKS:
            if comp and not (comp.isalpha() and comp == comp.lower()):
                sys.exit(f"{tid}: component '{comp}' must be lowercase letters only")
            if parent and parent not in ids:
                sys.exit(f"{tid}: parent {parent} is not in the task list")
            leaf = not any(p == tid for _, p, _, _, _ in TASKS)
            if leaf and not acceptance.strip():
                sys.exit(f"{tid}: every leaf needs an acceptance test")
        t = now()
        before = con.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        con.executemany("INSERT OR IGNORE INTO tasks (id, parent, title, acceptance, component, created_at, updated_at)"
                        " VALUES (?,?,?,?,?,?,?)", [(*row, t, t) for row in TASKS])
        print(f"tasks: {before} -> {con.execute('SELECT COUNT(*) FROM tasks').fetchone()[0]}")
    elif cmd in ("tick", "part") and len(a) == 2:
        set_status(con, a[1], "done" if cmd == "tick" else "partial")
    elif cmd == "cancel" and len(a) >= 3:
        for leaf in leaves_under(con, a[1]):
            set_status(con, leaf, "cancelled")
            note(con, leaf, "Cancelled: " + " ".join(a[2:]))
    elif cmd == "note" and len(a) >= 3:
        note(con, a[1], " ".join(a[2:]))
    elif cmd == "add" and len(a) == 6:
        _, tid, parent, title, acceptance, comp = a
        get(con, parent)
        if not acceptance.strip():
            sys.exit("a leaf needs a runnable acceptance test")
        if comp and not (comp.isalpha() and comp == comp.lower()):
            sys.exit("component must be lowercase letters only")
        t = now()
        con.execute("INSERT INTO tasks (id, parent, title, acceptance, component, created_at, updated_at)"
                    " VALUES (?,?,?,?,?,?,?)", (tid, parent, title, acceptance, comp, t, t))
    elif cmd == "tree":
        print("\n".join(lines(con)))
        return
    elif cmd == "components":
        print(json.dumps(rollup(con), indent=1))
        return
    elif cmd == "mirror":
        pass
    else:
        sys.exit("bad arguments; see plan.py --help")
    con.commit()
    mirror(con)


if __name__ == "__main__":
    main()
