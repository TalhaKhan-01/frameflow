# Frameflow

An automated daily newsroom for one narrator, **Habit**: every day it picks a story, writes it, storyboards it, renders a 60–110 s vertical Short, checks it, and posts it to YouTube Shorts, Instagram Reels and a Facebook Page at 11:30, plus a carousel card post from the same brief. The owner approves on Telegram; nothing posts without that tap.

**Status:** running daily since 25 Oct 2026 (first fully automatic post 26 Oct). Build tracked in the phasedoc (`phasedoc/BUILDPLAN.md`, cockpit http://127.0.0.1:7300).

**Live:**
- Betadoc (story + docs): https://frameflow-betadoc.vercel.app
- Studio (read-only; open for now, PIN lock switchable): https://frameflow-studio-tau.vercel.app

## Layout
| Path | Holds |
|---|---|
| `frameflow/` | Pipeline (Python): `daily.py` + `bot.py` (schedule, Telegram), `brief.py` → `direct.py` → `pipeline.py` → `qa.py` + `review.py`, `cards.py`, `publish.py`, `lessons.py`, `library.py`, `stats48.py`, `cleanup.py`, `webexport.py` |
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
uv run frameflow make2 briefs/<brief>.json # one video end to end
uv run pytest -q                           # tests
PM2_HOME=~/.pm2-personal pm2 start ecosystem.config.js && pm2 save
```
The daily run needs no command: `frameflow-bot` ticks every 30 s and follows the schedule in `research/automation.json`.

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
Keys live in `~/.config/frameflow/secrets.env` (mode 600) or the environment; names in `.env.example`. Never commit them. The Studio PIN is `FRAMEFLOW_WEB_PIN` there.
