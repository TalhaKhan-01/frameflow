# Betadoc concept: Night Edition (locked 2026-10-25)

Format: **LONG** (`index.html` + `documentation.html`). Mix chosen by Talha: **12 cinematic video + 03 WebGL immersive + 07 live product hero**.

The idea: Frameflow is a newsroom that works the night shift for one narrator, Habit. The betadoc is that newsroom after dark. The Studio app (`web/`) wears the daytime Paper Press look, so the betadoc doesn't repeat it.

## Palette (OKLCH)
| Token | Value | Use |
|---|---|---|
| `--night` | `oklch(0.165 0.02 275)` | background (dominant) |
| `--night-2` | `oklch(0.215 0.024 275)` | surfaces |
| `--paper` | `oklch(0.95 0.018 85)` | text |
| `--muted` | `oklch(0.74 0.02 80)` | secondary text |
| `--red` | `oklch(0.64 0.2 29)` | press red: the one sharp accent |
| `--lamp` | `oklch(0.85 0.13 80)` | lamp amber: live data, highlights |

## Type (all OFL-1.1, self-hosted from the repo's bundled fonts)
- Display: **Fraunces** (variable, opsz), italic for emphasis.
- Text: **Space Grotesk**.
- Numbers and labels: **JetBrains Mono**.

## Motion language
- Ease `power3.out` for entrances, `expo.inOut` for section morphs; durations 0.6 s (UI), 1.2 s (headlines).
- **Staged load:** shader fades in → headline lines rise → phone slides up and the Short plays muted → live wire counts up.
- On scroll: the shader turns chaotic in *Problem* (`uChaos` up) and calms in *Product*; nothing else moves on its own.
- `prefers-reduced-motion`: the shader draws one still frame, the scrub becomes a static strip of frames, and all content shows at once.

## Background
A full-screen WebGL2 fragment shader: domain-warped fbm "ink in water" over newsprint grain and a vignette, with a slow cursor ripple. Raw WebGL, no 3D library.

## The one wow moment
**The Short builds itself.** A pinned section scrubs 72 real frames of the latest posted Short inside a phone while six stage captions (Topic → Brief → Script → Storyboard → Render → Checks) pass, and the real QA gates tick on the right.

## Live product hero
The hero reads `live.json` (written by `frameflow web export` after every post): today's run and its state, ideas collected, Shorts posted, lessons and tasks passed.
