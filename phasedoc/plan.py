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
import re
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

    # P9 plan of record: vault/Docs/Quality v2 Plan.md
    ("P9", "", "Quality v2: human script, direction, expressive voice, sound, drawn scenes", "", ""),
    ("P9.1", "P9", "shorts-writer skill (human scriptwriter)", "", ""),
    ("P9.1.1", "P9.1", "Narrator persona (Habit) and humour rules",
     "vault/Wiki/Concepts/Narrator Habit.md accepted by Talha; the skill reads the persona from a project config file", "writer"),
    ("P9.1.2", "P9.1", "Angle mining, 20-hook room and virality scan",
     "on the fixture brief the skill returns 20 hooks across at least 8 of 10 hook families, each scored on the rubric, top 3 kept with reasons", "writer"),
    ("P9.1.3", "P9.1", "Beat sheet: And-But-Therefore, open loop, re-hooks, imagine beat, ending strategy",
     "validator passes: no re-hook gap over 10 s, at least 1 imagine beat, at least 2 everyday analogies, payoff before 85% of runtime, ending strategy named", "writer"),
    ("P9.1.4", "P9.1", "Anti-slop linter",
     "flags at least 90% of a seeded slop fixture and makes 0 hits on 3 human-written reference scripts", "writer"),
    ("P9.1.5", "P9.1", "Performance markup per line",
     "every line carries emotion, energy (0-1), pause-before and stressed words, and the voice step reads them", "writer"),
    ("P9.1.6", "P9.1", "Table read: v2 script beats v1",
     "blind A/B on the same story: Talha prefers the v2 script", "writer"),
    ("P9.2", "P9", "shorts-director skill (storyboard and visual direction)", "", ""),
    ("P9.2.1", "P9.2", "Storyboard schema and validator",
     "each beat has a visual world, motion verbs, transition and SFX cue; validator fails any stretch over 2.5 s without a visual event", "director"),
    ("P9.2.2", "P9.2", "Metaphor bank and trend references",
     "bank of at least 40 visual metaphors mapped to scene blocks; the director cites which one it used and why", "director"),
    ("P9.2.3", "P9.2", "Storyboard to scene-plan compiler",
     "a storyboard compiles into a valid plan.json that renders without manual edits", "director"),
    ("P9.2.4", "P9.2", "Director review row",
     "model review of the keyframe sheet scores visual storytelling 2/2 on the pilot", "director"),
    ("P9.3", "P9", "Expressive Chatterbox voice", "", ""),
    ("P9.3.1", "P9.3", "Per-line expression and pace",
     "line energy maps to exaggeration 0.4-0.8 and cfg weight; measured pace 175-190 wpm after atempo", "voice"),
    ("P9.3.2", "P9.3", "Chatterbox Turbo tag audition",
     "[chuckle]/[laugh] tested on Chatterbox Turbo (MIT); audition note with samples in the vault; Talha keeps or drops them", "voice"),
    ("P9.3.3", "P9.3", "Deterministic voice and Kokoro fallback",
     "same script + seed gives the same audio hash; Kokoro is used when the GPU is busy", "voice"),
    ("P9.4", "P9", "Sound design layer", "", ""),
    ("P9.4.1", "P9.4", "SFX library v2",
     "whooshes, impacts, risers, glitches, ticks, record-scratch from CC0/royalty-free packs plus procedural; every file has a licence row", "sound"),
    ("P9.4.2", "P9.4", "Cue sheet to mix",
     "storyboard cues land within 1 frame of their scene events; music 18 dB under voice; SFX peaks below the voice peak", "sound"),
    ("P9.4.3", "P9.4", "Energy-curve beds",
     "bed intensity rises across the video, near-silence before the payoff, then a hit; final loudness -14 LUFS", "sound"),
    ("P9.5", "P9", "Scene library v2 (Paper Press)", "", ""),
    ("P9.5.1", "P9.5", "Maps and routes",
     "map scene with drawing routes and a vehicle on a path passes the 6-time frame-hash determinism test", "scenes"),
    ("P9.5.2", "P9.5", "Drawn props",
     "hand-drawn arrows, circles, labels and CC0 characters scene passes the determinism test", "scenes"),
    ("P9.5.3", "P9.5", "Kinetic type",
     "slam, per-letter reveal and scramble-decode scenes pass the determinism test", "scenes"),
    ("P9.5.4", "P9.5", "Fast transitions",
     "whip pan, velocity cut and glitch cut between two scenes pass the determinism test", "scenes"),
    ("P9.5.5", "P9.5", "2.5D and isometric",
     "parallax layers and exploded-stack scenes pass the determinism test", "scenes"),
    ("P9.5.6", "P9.5", "Cyber pack for the pilot",
     "terminal typing, climbing counter, street of padlocked websites and lights-out scenes pass the determinism test", "scenes"),
    ("P9.6", "P9", "Stricter Quality Bar and review", "", ""),
    ("P9.6.1", "P9.6", "Quality Bar v2",
     "new targets (50-90 s, 175-190 wpm, 4+ changes per 10 s, re-hook gap, analogies, humour, sound, drawn share) accepted by Talha", "quality"),
    ("P9.6.2", "P9.6", "Script Rules v2 and validator",
     "R5 becomes 50-90 s and new rules are checked by the validator; existing tests still pass", "quality"),
    ("P9.6.3", "P9.6", "Review v2",
     "review rows for story, humour, visual events and sound added; the v1 iPhone video fails and the pilot passes", "quality"),
    ("P9.6.4", "P9.6", "Tokens per video measured",
     "writer + director token use for the pilot recorded in data/llm-usage.jsonl and summarised in the vault", "quality"),
    ("P9.7", "P9", "Pilot video: Black October (PHP2Shell)", "", ""),
    ("P9.7.1", "P9.7", "Fact sheet re-checked on render day",
     "vault/Wiki/Sources/Black October PHP2Shell.md re-checked; every on-screen number has a source; contested points labelled", "pilot"),
    ("P9.7.2", "P9.7", "Made with the v2 pipeline",
     "rendered through writer, director, voice, sound and scenes v2; passes automatic gates and review v2", "pilot"),
    ("P9.7.3", "P9.7", "Talha approves the pilot",
     "frameflow approve <id> run by Talha's decision", "pilot"),
    ("P9.7.4", "P9.7", "Side-by-side with v1",
     "vault note compares the pilot with the v1 iPhone video: events per 10 s, re-hook gaps, review scores", "pilot"),
    ("P9.3.4", "P9.3", "Voice pace table per beat and emotion",
     "research/voice-pace.json drives per-line tempo; on the next render the mean pace is 175-190 wpm and no plain line is outside its target by more than the tolerance unless clamped", "voice"),
    ("P9.3.5", "P9.3", "Turbo laugh lines in the pipeline",
     "a line tagged [chuckle] or [laugh] renders on Turbo cloned from the house voice at Talha's chosen temperature; tags never reach captions; at most one per video", "voice"),

    ("P10", "", "Daily automation: Telegram approvals and 11:30 posting", "", ""),
    ("P10.1", "P10", "Telegram bot", "", ""),
    ("P10.1.1", "P10.1", "Bot online and locked to Talha",
     "PM2 app frameflow-bot runs with long polling; TELEGRAM_BOT_TOKEN read from secrets.env; messages from any chat but Talha's are ignored; /status answers", "automation"),
    ("P10.1.2", "P10.1", "Approval state machine",
     "a run moves topic-sent -> picked -> making -> video-sent -> approved/revise/rejected -> queued -> posted, persisted in SQLite so a restart resumes it", "automation"),
    ("P10.1.3", "P10.1", "Pause, resume and blind A/B",
     "/pause stops the next daily run, /resume restarts it; /ab sends two scripts for one story and records the tap (closes P9.1.6)", "automation"),
    ("P10.2", "P10", "Evening topic run", "", ""),
    ("P10.2.1", "P10.2", "Lane rotation tech -> AI -> money",
     "the scheduler picks tomorrow's lane by rotation from the post log (tech 2026-10-25, then AI, then money)", "automation"),
    ("P10.2.2", "P10.2", "20:00 topic card with 3 sourced stories",
     "at 20:00 the bot sends 3 ranked stories for tomorrow's lane (headline, why now, sources, hook idea) with buttons 1/2/3/Skip and accepts a pasted link", "automation"),
    ("P10.2.3", "P10.2", "Auto-pick at 22:30",
     "with no reply by 22:30, story 1 is picked and the bot says so", "automation"),
    ("P10.3", "P10", "Make and approve", "", ""),
    ("P10.3.1", "P10.3", "Pick starts make2",
     "a pick builds the brief (facts re-checked) and runs make2 end to end without a human", "automation"),
    ("P10.3.2", "P10.3", "Video card on Telegram",
     "the bot sends a 720p preview under 50 MB, the cover, titles and caption, the review score and QA summary, with Approve/Revise/Reject", "automation"),
    ("P10.3.3", "P10.3", "Revise loop from Telegram notes",
     "Talha's typed notes go to the writer/director doctors as human notes, the video is re-rendered and re-sent; at most 2 rounds", "automation"),
    ("P10.4", "P10", "Post at 11:30 on three platforms", "", ""),
    ("P10.4.1", "P10.4", "Post queue",
     "approved before 11:30 -> posted at 11:30 that day; approved after 11:30 -> posted at once (until the day ends)", "automation"),
    ("P10.4.2", "P10.4", "Dedicated Chrome for The Pilot",
     "a PM2-run Chrome with its own profile folder (Thirdspace Google + Instagram only) and a 127.0.0.1 DevTools port; Talha signed in once; YouTube upload works unattended", "publish"),
    ("P10.4.3", "P10.4", "Facebook Page Reels",
     "the Meta token has pages_manage_posts; the approved video is posted as a Thirdspace Page Reel through the API and its link recorded", "publish"),
    ("P10.4.4", "P10.4", "Post checks and links",
     "after posting, every link returns 200 and its caption is present; the bot sends the links and the pinned comment is posted", "publish"),
    ("P10.5", "P10", "Unattended week", "", ""),
    ("P10.5.1", "P10.5", "Seven days without a hand on the keyboard",
     "7 consecutive days posted at 11:30 (or on late approval) with Talha's only input being Telegram taps", "launch"),

    ("P11", "", "Learning pipeline", "", ""),
    ("P11.1", "P11", "Lessons ledger",
     "research/lessons.jsonl rows (source, area, general lesson, evidence, status) written after each video from review fixes, failed gates, Talha's notes and rejections; duplicates merged", "learning"),
    ("P11.2", "P11", "Lessons feed the writer and director",
     "the top active lessons per area (at most 8) reach the writer and director prompts for each new video; the run log lists which", "learning"),
    ("P11.3", "P11", "48-hour stats per platform",
     "frameflow stats pulls views, % watched, swipe-away, likes, shares and follows for YouTube, Instagram and Facebook 48 h after posting and sends a stats card (closes P7.3)", "feedback"),
    ("P11.4", "P11", "Lessons scored by results",
     "each lesson used in a video is marked helped/hurt from that video's % watched and swipe-away against the channel average", "learning"),
    ("P11.5", "P11", "Weekly promotion",
     "every Sunday lessons that helped in 3+ videos are proposed on Telegram for the Quality Bar or house rules; approved ones are applied, stale ones retired; the weekly report lands in the vault (closes P7.4)", "learning"),

    ("P12", "", "Reuse: asset library, cleanup, Habit cards", "", ""),
    ("P12.1", "P12", "Asset library",
     "passing videos feed research/assets (knowledge cards, unused hooks, analogies, scene recipes) with origin and scores; the researcher, writer and director are offered matching items with variety windows and freshness flags; a profile switch turns it off; tests pass", "learning"),
    ("P12.2", "P12", "Disk cleanup after the library has taken what it reuses",
     "48 h after posting, a video keeps final.mp4, cover, brief, review, stats and its vault page; intermediate renders and scene projects are deleted only after library.extract ran; a video shrinks to about 80 MB", "automation"),
    ("P12.3", "P12", "Habit cards (news-first carousel posts)",
     "from a video's knowledge cards, a Paper Press carousel (bold-claim hook slide, 3-5 fact slides with source lines, follow slide) is rendered at 1080x1350, approved on Telegram and posted to Instagram and Facebook", "publish"),
    ("P12.4", "P12", "Repeating voice lines cached",
     "a line marked cache (the house outro) is recorded once and reused when the words and delivery match", "voice"),

    ("P13", "", "Studio web app and betadoc (Vercel)", "", ""),
    ("P13.1", "P13", "Studio app", "", ""),
    ("P13.1.1", "P13.1", "PIN-locked Studio snapshot",
     "uv run frameflow web export writes web/public/data/studio.enc (AES-GCM, key from FRAMEFLOW_WEB_PIN via PBKDF2) plus media for posted items only; tests/test_webexport.py decrypts it round-trip, and a grep of web/public finds no token, chat id or secrets.env value", "web"),
    ("P13.1.2", "P13.1", "Studio pages: runs, videos, card posts, lessons, library",
     "headless walk of the built web/dist at 1440 and 390 px: a wrong PIN shows an error, the right PIN shows today's run, the Black October page (player, QA gates, review scores, links), card posts, lessons and library; 0 console errors, no horizontal overflow", "web"),
    ("P13.1.3", "P13.1", "Studio live on Vercel (talha-785b), deployed by git push",
     "Vercel project frameflow-studio (root web/) is git-connected to TalhaKhan-01/frameflow; scripts/deploy-check.sh studio passes (production SHA = HEAD, / and data/studio.enc return 200)", "web"),
    ("P13.1.4", "P13.1", "Snapshot refreshes itself after each post",
     "after a daily post (and after the 48 h stats), the daily tick runs web export, commits only web/public and pushes; the live Studio shows the new post within 10 minutes", "web"),
    ("P13.2", "P13", "Betadoc", "", ""),
    ("P13.2.1", "P13.2", "Concept locked (cinematic video + WebGL immersive + live product hero)",
     "betadoc/CONCEPT.md lists OKLCH tokens, a licensed type pairing, the motion language and the one wow moment; a row is in the sitecraft used.md", "betadoc"),
    ("P13.2.2", "P13.2", "Story site: index.html and documentation.html (LONG)",
     "betadoc build has hero (real Short + WebGL + live numbers) -> problem -> product -> architecture SVG -> honest feature matrix (built/partial/roadmap) -> roadmap -> deployment -> demo call-to-action, and documentation.html with its own contents; walk at 1440, 390 and --reduced: 0 console errors, no overflow", "betadoc"),
    ("P13.2.3", "P13.2", "Betadoc live on Vercel (talha-785b), deployed by git push",
     "Vercel project frameflow-betadoc (root betadoc/) is git-connected; scripts/deploy-check.sh betadoc passes; the Studio link on it opens the PIN screen", "betadoc"),
    ("P13.2.4", "P13.2", "Narrated demo video in the hero",
     "betadoc/video renders a deterministic 60 fps narrated tour (betadoc narrate.py, voice Talha picked) with captions; it streams from the live site", "betadoc"),
    ("P14", "", "Control panel (local experiment: Code/frameflow-control, 127.0.0.1:7310)", "", ""),
    ("P14.1", "P14", "Watch: now, today's schedule, runs, jobs, services, connections, activity, machine",
     "the panel renders every section from live data; headless walk at 1440 and 390 px: 0 console errors, no horizontal overflow", "control"),
    ("P14.2", "P14", "Control: pick, approve, revise, reject, post time, post now, retry, one-platform retry, stop, card posts",
     "sandboxed tests: each action follows the run's state like the Telegram bot, refuses stale clicks and never re-posts a partly posted video; the real runs and config are unchanged by the tests", "control"),
    ("P14.3", "P14", "Settings and services: schedule, platforms, profile, Studio, restarts, lessons, feedback",
     "sandboxed tests: schedule and platform validation, the pause/resume flag, the restart whitelist; settings land in automation.json", "control"),
    ("P14.4", "P14", "Security: this machine only, a token per start, Origin and Host checks",
     "tests: a foreign Host gets 403, a POST without the token or from a foreign Origin gets 403, path tricks on media and logs are refused; the LAN address is refused", "control"),
    ("P14.5", "P14", "Health alerts on Telegram from the same checks",
     "an expired account token, Chrome down or disk over 90% sends one Telegram alert (not one per tick); tested with a forced failure", "control"),
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


def id_key(task_id):
    """Natural order for task ids: P2 before P10 (SQL text order puts P10 between P1 and P2)."""
    return [(0, int(x), "") if x.isdigit() else (1, 0, x) for x in re.split(r"(\d+)", task_id) if x]


def leaves_under(con, task_id):
    if is_leaf(con, task_id):
        return [task_id]
    out = []
    for (kid,) in sorted(con.execute("SELECT id FROM tasks WHERE parent=?", (task_id,)).fetchall(), key=lambda r: id_key(r[0])):
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
    for r in sorted(con.execute("SELECT * FROM tasks WHERE parent=?", (parent,)).fetchall(), key=lambda r: id_key(r["id"])):
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
