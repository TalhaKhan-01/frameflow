# Frameflow: architecture

The top row is the groundwork. The two rows below are the daily pipeline, from an idea to a posted video and back into learning. Each box is coloured live from the task tree: grey = not started, amber = in progress, green = done and verified.

<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 980 790" width="980" height="790" font-family="system-ui, sans-serif" font-size="14">
  <defs>
    <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
      <path d="M0,0 L10,5 L0,10 z" fill="currentColor" opacity="0.6"/>
    </marker>
  </defs>
  <text x="20" y="22" fill="currentColor" opacity="0.7" font-size="12">GROUNDWORK</text>
  <g id="comp-setup"><rect x="20" y="32" width="170" height="64" rx="10" stroke="currentColor" stroke-opacity="0.35"/>
    <text x="105" y="60" text-anchor="middle" fill="currentColor" font-weight="600">Setup</text>
    <text x="105" y="80" text-anchor="middle" fill="currentColor" font-size="11" opacity="0.75">accounts, keys, repo, vault</text></g>
  <g id="comp-research"><rect x="210" y="32" width="170" height="64" rx="10" stroke="currentColor" stroke-opacity="0.35"/>
    <text x="295" y="60" text-anchor="middle" fill="currentColor" font-weight="600">Research</text>
    <text x="295" y="80" text-anchor="middle" fill="currentColor" font-size="11" opacity="0.75">niche + deep study</text></g>
  <g id="comp-quality"><rect x="400" y="32" width="170" height="64" rx="10" stroke="currentColor" stroke-opacity="0.35"/>
    <text x="485" y="60" text-anchor="middle" fill="currentColor" font-weight="600">Quality bar</text>
    <text x="485" y="80" text-anchor="middle" fill="currentColor" font-size="11" opacity="0.75">targets + script rules</text></g>
  <g id="comp-scenes"><rect x="590" y="32" width="170" height="64" rx="10" stroke="currentColor" stroke-opacity="0.35"/>
    <text x="675" y="60" text-anchor="middle" fill="currentColor" font-weight="600">Scene library</text>
    <text x="675" y="80" text-anchor="middle" fill="currentColor" font-size="11" opacity="0.75">templates + identity</text></g>
  <g id="comp-assets"><rect x="780" y="32" width="180" height="64" rx="10" stroke="currentColor" stroke-opacity="0.35"/>
    <text x="870" y="60" text-anchor="middle" fill="currentColor" font-weight="600">Assets</text>
    <text x="870" y="80" text-anchor="middle" fill="currentColor" font-size="11" opacity="0.75">stock, music, licences</text></g>

  <text x="20" y="148" fill="currentColor" opacity="0.7" font-size="12">DAILY PIPELINE</text>
  <g id="comp-ideas"><rect x="20" y="158" width="170" height="64" rx="10" stroke="currentColor" stroke-opacity="0.35"/>
    <text x="105" y="186" text-anchor="middle" fill="currentColor" font-weight="600">Ideas</text>
    <text x="105" y="206" text-anchor="middle" fill="currentColor" font-size="11" opacity="0.75">collect + rank</text></g>
  <g id="comp-script"><rect x="210" y="158" width="170" height="64" rx="10" stroke="currentColor" stroke-opacity="0.35"/>
    <text x="295" y="186" text-anchor="middle" fill="currentColor" font-weight="600">Script</text>
    <text x="295" y="206" text-anchor="middle" fill="currentColor" font-size="11" opacity="0.75">script + scene plan</text></g>
  <g id="comp-voice"><rect x="400" y="158" width="170" height="64" rx="10" stroke="currentColor" stroke-opacity="0.35"/>
    <text x="485" y="186" text-anchor="middle" fill="currentColor" font-weight="600">Voice</text>
    <text x="485" y="206" text-anchor="middle" fill="currentColor" font-size="11" opacity="0.75">local text-to-speech</text></g>
  <g id="comp-captions"><rect x="590" y="158" width="170" height="64" rx="10" stroke="currentColor" stroke-opacity="0.35"/>
    <text x="675" y="186" text-anchor="middle" fill="currentColor" font-weight="600">Captions</text>
    <text x="675" y="206" text-anchor="middle" fill="currentColor" font-size="11" opacity="0.75">word timings, word-pop</text></g>
  <g id="comp-render"><rect x="780" y="158" width="180" height="64" rx="10" stroke="currentColor" stroke-opacity="0.35"/>
    <text x="870" y="186" text-anchor="middle" fill="currentColor" font-weight="600">Render</text>
    <text x="870" y="206" text-anchor="middle" fill="currentColor" font-size="11" opacity="0.75">one command → MP4</text></g>

  <g id="comp-qa"><rect x="780" y="284" width="180" height="64" rx="10" stroke="currentColor" stroke-opacity="0.35"/>
    <text x="870" y="312" text-anchor="middle" fill="currentColor" font-weight="600">Checks + approval</text>
    <text x="870" y="332" text-anchor="middle" fill="currentColor" font-size="11" opacity="0.75">auto QA, AI review, Talha</text></g>
  <g id="comp-publish"><rect x="590" y="284" width="170" height="64" rx="10" stroke="currentColor" stroke-opacity="0.35"/>
    <text x="675" y="312" text-anchor="middle" fill="currentColor" font-weight="600">Publish</text>
    <text x="675" y="332" text-anchor="middle" fill="currentColor" font-size="11" opacity="0.75">pack, Pilot + API upload</text></g>
  <g id="comp-feedback"><rect x="400" y="284" width="170" height="64" rx="10" stroke="currentColor" stroke-opacity="0.35"/>
    <text x="485" y="312" text-anchor="middle" fill="currentColor" font-weight="600">Feedback</text>
    <text x="485" y="332" text-anchor="middle" fill="currentColor" font-size="11" opacity="0.75">48 h stats, weekly lessons</text></g>
  <g id="comp-launch"><rect x="20" y="284" width="360" height="64" rx="10" stroke="currentColor" stroke-opacity="0.35"/>
    <text x="200" y="312" text-anchor="middle" fill="currentColor" font-weight="600">Launch</text>
    <text x="200" y="332" text-anchor="middle" fill="currentColor" font-size="11" opacity="0.75">3 pilots → 7-day cadence → retrospective</text></g>

  <text x="20" y="462" fill="currentColor" opacity="0.7" font-size="12">QUALITY V2 AND THE STUDIO BOARD (P9, P15)</text>
  <g id="comp-writer"><rect x="20" y="472" width="170" height="64" rx="10" stroke="currentColor" stroke-opacity="0.35"/>
    <text x="105" y="500" text-anchor="middle" fill="currentColor" font-weight="600">Writer</text>
    <text x="105" y="520" text-anchor="middle" fill="currentColor" font-size="11" opacity="0.75">Habit's voice, hooks, beats</text></g>
  <g id="comp-director"><rect x="210" y="472" width="170" height="64" rx="10" stroke="currentColor" stroke-opacity="0.35"/>
    <text x="295" y="500" text-anchor="middle" fill="currentColor" font-weight="600">Director</text>
    <text x="295" y="520" text-anchor="middle" fill="currentColor" font-size="11" opacity="0.75">storyboard, metaphors, cues</text></g>
  <g id="comp-sound"><rect x="400" y="472" width="170" height="64" rx="10" stroke="currentColor" stroke-opacity="0.35"/>
    <text x="485" y="500" text-anchor="middle" fill="currentColor" font-weight="600">Sound</text>
    <text x="485" y="520" text-anchor="middle" fill="currentColor" font-size="11" opacity="0.75">SFX cues, music beds</text></g>
  <g id="comp-studio"><rect x="590" y="472" width="170" height="64" rx="10" stroke="currentColor" stroke-opacity="0.35"/>
    <text x="675" y="500" text-anchor="middle" fill="currentColor" font-weight="600">Studio board</text>
    <text x="675" y="520" text-anchor="middle" fill="currentColor" font-size="11" opacity="0.75">desks, animatic, 1 render</text></g>
  <g id="comp-pilot"><rect x="780" y="472" width="180" height="64" rx="10" stroke="currentColor" stroke-opacity="0.35"/>
    <text x="870" y="500" text-anchor="middle" fill="currentColor" font-weight="600">Pilot video</text>
    <text x="870" y="520" text-anchor="middle" fill="currentColor" font-size="11" opacity="0.75">Black October</text></g>

  <text x="20" y="582" fill="currentColor" opacity="0.7" font-size="12">RUNS BY ITSELF, WATCHED BY TALHA (P10-P14)</text>
  <g id="comp-automation"><rect x="20" y="592" width="170" height="64" rx="10" stroke="currentColor" stroke-opacity="0.35"/>
    <text x="105" y="620" text-anchor="middle" fill="currentColor" font-weight="600">Daily automation</text>
    <text x="105" y="640" text-anchor="middle" fill="currentColor" font-size="11" opacity="0.75">Telegram, 14:00 → 11:30</text></g>
  <g id="comp-learning"><rect x="210" y="592" width="170" height="64" rx="10" stroke="currentColor" stroke-opacity="0.35"/>
    <text x="295" y="620" text-anchor="middle" fill="currentColor" font-weight="600">Learning</text>
    <text x="295" y="640" text-anchor="middle" fill="currentColor" font-size="11" opacity="0.75">lessons ledger, house rules</text></g>
  <g id="comp-control"><rect x="400" y="592" width="170" height="64" rx="10" stroke="currentColor" stroke-opacity="0.35"/>
    <text x="485" y="620" text-anchor="middle" fill="currentColor" font-weight="600">Control panel</text>
    <text x="485" y="640" text-anchor="middle" fill="currentColor" font-size="11" opacity="0.75">127.0.0.1:7310, Making view</text></g>
  <g id="comp-web"><rect x="590" y="592" width="170" height="64" rx="10" stroke="currentColor" stroke-opacity="0.35"/>
    <text x="675" y="620" text-anchor="middle" fill="currentColor" font-weight="600">Studio web app</text>
    <text x="675" y="640" text-anchor="middle" fill="currentColor" font-size="11" opacity="0.75">Vercel snapshot</text></g>
  <g id="comp-betadoc"><rect x="780" y="592" width="180" height="64" rx="10" stroke="currentColor" stroke-opacity="0.35"/>
    <text x="870" y="620" text-anchor="middle" fill="currentColor" font-weight="600">Betadoc</text>
    <text x="870" y="640" text-anchor="middle" fill="currentColor" font-size="11" opacity="0.75">story, docs, tour</text></g>
  <g id="comp-house"><rect x="590" y="700" width="370" height="64" rx="10" stroke="currentColor" stroke-opacity="0.35"/>
    <text x="775" y="728" text-anchor="middle" fill="currentColor" font-weight="600">Thirdspace House</text>
    <text x="775" y="748" text-anchor="middle" fill="currentColor" font-size="11" opacity="0.75">pixel building: replay on Studio + betadoc, live on the panel</text></g>

  <g stroke="currentColor" stroke-opacity="0.55" stroke-width="1.6" fill="none" marker-end="url(#arrow)">
    <path d="M190,190 H208"/><path d="M380,190 H398"/><path d="M570,190 H588"/><path d="M760,190 H778"/>
    <path d="M870,222 V282"/><path d="M780,316 H762"/><path d="M590,316 H572"/><path d="M400,316 H382"/>
    <path d="M485,348 V400 H8 V190 H16" stroke-dasharray="5 4"/>
    <path d="M485,96 V156" stroke-dasharray="3 3"/><path d="M675,96 V156" stroke-dasharray="3 3"/><path d="M870,96 V156" stroke-dasharray="3 3"/>
  </g>
  <text x="300" y="424" fill="currentColor" opacity="0.7" font-size="12">learning loop: results feed the next ideas and the quality bar</text>
</svg>

## Components
| Key | What it is | Phase |
|---|---|---|
| `setup` | Accounts, keys, repository, vault, secrets | P0 |
| `research` | Niche study and deep study | P1 |
| `quality` | Quality bar targets and script rules | P1 |
| `voice` | Local text-to-speech and the voice step | P2 |
| `scenes` | Renderer, scene-plan contract, visual identity, templates | P3 |
| `captions` | Word-pop caption layer and word timings | P3, P6 |
| `ideas` | Idea collector and ranking | P4 |
| `script` | Script and scene-plan writer, source checks | P4 |
| `assets` | Keyless stock, licence ledger, music and sound effects | P5 |
| `render` | One-command render | P6 |
| `qa` | Automatic checks, AI review, approval gate | P6 |
| `publish` | Publish pack (cover, credits), YouTube by The Pilot in Studio until the API audit, Instagram by API (The Pilot for long Reels), post log | P7 |
| `feedback` | 48-hour stats and weekly learning | P7 |
| `launch` | Pilot, cadence week, retrospective | P8 |
| `writer` | shorts-writer skill: persona, hooks, beat sheet, slop linter, voice markup | P9 |
| `director` | shorts-director skill: storyboard, metaphor bank, compiler | P9 |
| `sound` | SFX library v2, cue-sheet mix, energy-curve beds | P9 |
| `pilot` | Black October pilot video | P9 |
| `automation` | Telegram bot (approvals, /status, /pause, /ab), evening topic run with lane rotation, make-and-approve loop, 11:30 post queue | P10 |
| `learning` | Lessons ledger fed by reviews, Talha's notes and 48 h stats; lessons injected into writer/director; weekly promotion | P11 |
| `web` | Studio web app (read-only snapshot, open or PIN mode, auto-refresh after posts) | P13 |
| `betadoc` | Story page, documentation and narrated tour | P13 |
| `control` | Frameflow Control panel (127.0.0.1:7310): controls, connection lights, Making view | P14 |
| `studio` | The studio board: desks with gates, animatic, one delivery render, showrunner Revise, analyst | P15 |
| `showrunner` | shorts-producer skill: Revise change orders and topic memory (no story twice in 14 days) | P25 |
| `visuals` | visual-sourcing skill (logos, judged photos, headline screenshots, licence tiers, library) + the show's media layer and analogy gags | P25 |
| `narrator` | voice-narrate skill (planned) | P25 |
| `editor` | video-editor skill: assembly and the one render (planned) | P25 |
| `critic` | video-critic skill: table read + screening (planned) | P25 |
| `integrity` | video-integrity skill: facts + standards + QC (planned) | P25 |
| `publisher` | social-publisher skill: posting + 48 h analyst (planned) | P25 |
| `docs` | README, vault, betadoc and Studio pages kept in step with the system | P25 |

## The pipeline as it runs today (2026-10-27): the studio board
The day (P10, `frameflow.daily` driven by the bot's tick): **14:00** topic card (3 stories, lane rotation tech → AI → money) → pick, or auto-pick at **15:00** → make → video card on Telegram (Approve / Approve anyway / Revise / Reject) → **11:30** next day: YouTube (The Pilot in Studio), Facebook and Instagram (API; The Pilot while the Meta token is blocked) and the card post → links → +48 h stats card → lessons → asset library → cleanup.

A make (`videos.make2` → `board.make`, P15), every desk's gate before the next:
1. **Research brief** (`brief.py`) → **fact-checker** (skill shorts-factcheck): unsupported facts dropped, partial ones corrected.
2. **Showrunner run sheet** (`analyst.py`: evidence from videos with 48 h results) → **packaging** (social-caption concept mode: title, cover line, hook promise).
3. **Writer** (shorts-writer) and **director** (shorts-director), each linting the measurable targets first. A valid plan writes a checkpoint: a make stopped later (usage limit) resumes at step 4.
4. **Narrator**: Chatterbox voice → Whisper word timings → `precheck.py` (re-hooks, caption accuracy, length, voice start) + script numbers vs the verified facts → **script editor** table read (shorts-editor). Fails → one text fix round (`timing_fix_rounds`).
5. **Scenes** (HyperFrames, Paper Press) → **standards** (`standards.py`: labels, licences, on-screen numbers) → **animatic** (`animatic.py`, 12 fps draft) → **art director** (`artdirect.py`: empty, black, off-brand) → **screening** (shorts-screening on the draft's stills). Fails → one fix round (`animatic_fix_rounds`), back to step 4.
6. **One delivery render** → technical QC (`qa.py` gates) → **final screening** (render vs animatic). No loop after the render: the honest numbers go to Talha, and his Revise is the fix path (showrunner change order → only its stages re-run).

Models: the **lean** profile (Opus/high only for the draft, storyboard and animatic screening; Sonnet/medium for hooks and fixes; Haiku for small jobs), ~405k tokens a video with both fix rounds (vault Docs/Token Budget.md).

One bar for every desk: `research/quality-bar.json`; one re-hook definition (`qa.is_rehook`) for QA, the narrator checks and the writer's lint. Progress per step: `logs/progress-<day>.jsonl` (control panel Making view, Studio Board tab).

## P25 (2026-10-29): the show's flow with the first new skills
14:00 `showdesk.scout` → `shorts-producer topics.py filter` (repeats of the last 14 days removed, follow-ups labelled) → the topic card → pick → `show.make_day`: research + fact-check per story → rundown writer (analogy ids only from `research/analogies.json` and the visual library) → `hookpick.pick` (10 opens on Telegram, waits on `hooks.json`, 20 min → hook 1) → `show.produce`: `show.visuals` (Haiku names each story's subject and logo → `visual-sourcing find`: Simple Icons / Commons / Openverse / site icon, Playwright headline capture, vision judge, library) → voice → `show.direct` (media first, then the data graphic, gag at the witty line) → sound (bed: Sneaky Snitch from Ep 3) → render (`show.js` media + gag layers) → QA + screening → `daily.video_card` + `post_text_card` (social-caption pack) → carousel. `showdesk.pick` records the aired stories in the topic ledger.
