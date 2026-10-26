# Frameflow

An automated daily newsroom for one narrator, **Habit**: every day it picks a story, writes it, storyboards it, renders a 60–110 s vertical Short, checks it, and posts it to YouTube Shorts, Instagram Reels and a Facebook Page at 11:30, plus a carousel card post from the same brief. The owner approves on Telegram; nothing posts without that tap.

**Status:** running daily since 25 Oct 2026 (first fully automatic post 26 Oct). Build tracked in the phasedoc (`phasedoc/BUILDPLAN.md`, cockpit http://127.0.0.1:7300).

**Live:**
- Betadoc (story + docs): https://frameflow-betadoc.vercel.app
- Studio (read-only; open for now, PIN lock switchable): https://frameflow-studio-tau.vercel.app
- Source (public, view only): https://github.com/TalhaKhan-01/frameflow

## Layout
| Path | Holds |
|---|---|
| `frameflow/` | Pipeline (Python): `daily.py` + `bot.py` (schedule, Telegram), `brief.py` → `board.py` (the studio board: `direct.py`, `precheck.py`, `standards.py`, `animatic.py`, `artdirect.py`, `review.py`, `pipeline.py`, `qa.py`), `producer.py` (Revise change orders), `analyst.py`, `bar.py` (the one quality bar), `progress.py`, `cards.py`, `publish.py`, `lessons.py`, `library.py`, `stats48.py`, `cleanup.py`, `webexport.py` |
| `scenes/` | HyperFrames scene templates and the shared theme (fonts bundled, OFL) |
| `research/` | Niche config, lessons ledger, asset library, house rules |
| `briefs/`, `plans/` | Sourced briefs and scene plans |
| `web/` | Studio web app (Vite + TS), Vercel project `frameflow-studio` |
| `betadoc/` | Betadoc site (Vite + TS, GSAP, WebGL), Vercel project `frameflow-betadoc`; concept in `betadoc/CONCEPT.md` |
| `phasedoc/` | Build plan (`plan.py`, `plan.db`, generated `BUILDPLAN.md`) |
| `scripts/deploy-check.sh` | Waits for the Vercel build of HEAD and probes the live site |
| `ecosystem.config.js` | Personal PM2 apps: `frameflow-bot`, `frameflow-chrome`, `phasedoc-frameflow` |
| `data/`, `out/`, `logs/`, `vault/` | Local only (gitignored): SQLite, renders, logs, the Obsidian vault |

## Run
```
uv sync                                    # Python env (one per project)
uv run frameflow --help                    # every command
uv run frameflow make2 briefs/<brief>.json # one video end to end, through the studio board
uv run pytest -q                           # tests
PM2_HOME=~/.pm2-personal pm2 start ecosystem.config.js && pm2 save
```
The daily run needs no command: `frameflow-bot` ticks every 30 s and follows the schedule in `research/automation.json`.

## How a video is made (studio board, since 26 Oct 2026)
Desk by desk, each with a gate, then one delivery render: showrunner (run sheet) → researcher → fact-checker → packaging
(title, cover, hook promise) → writer → director → narrator (voice, timing checks) → script editor (table read) → standards →
animatic (12 fps draft) → art director → screening on the animatic → **one delivery render** → QC → final check → Talha →
publisher → analyst (48 h results). Fix loops run only before the delivery render, bounded by the profile. Thresholds:
`research/quality-bar.json`. Revise on Telegram: known issues as toggles or your own words → a change order with Go / Change
it / Cancel → only the stages it needs. Craft desks are skills in `~/Talha_Khan/Claude/skills` (`shorts-producer`,
`shorts-factcheck`, `shorts-editor`, `shorts-screening`, `shorts-writer`, `shorts-director`, `social-caption`). Details:
vault `Docs/Frameflow Studio Board.md`; live progress in the control panel (`Code/frameflow-control`, Making panel).

## Studio and betadoc
```
uv run frameflow web export     # snapshot -> web/public/data/studio.json (open) or studio.enc (AES-GCM, PIN) + betadoc/public/live.json
uv run frameflow web open|lock  # switch the Studio between open and PIN-locked (web/access.json), then export
uv run frameflow web refresh    # export, then commit + push only web/public and betadoc/public (runs after each post)
cd web && npm ci && npm run build && npm run walk   # FRAMEFLOW_WEB_PIN=... when locked
cd betadoc && npm ci && npm run build && npm run walk
scripts/deploy-check.sh studio|betadoc
```
Both deploy from git pushes (personal Vercel `talha-785b`). Only already-public media is copied into `web/public` and `betadoc/public`.

## Secrets
Keys live in `~/.config/frameflow/secrets.env` (mode 600) or the environment; names in `.env.example`. Never commit them. The Studio PIN is `FRAMEFLOW_WEB_PIN` there, and the one Telegram chat the bot talks to is `TELEGRAM_CHAT_ID`.

## Licence
Copyright © 2026 Talha Khan. All rights reserved. The code is public to read and learn from; no licence is granted to copy, modify or redistribute it. Bundled third-party pieces keep their own licences (fonts OFL-1.1, rough.js MIT, three.js MIT, GSAP standard licence, Open Peeps CC0 in `scenes/_cast/`, Kokoro voice model Apache-2.0); each video's asset ledger lists what it used.
