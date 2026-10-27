# Studio-show spike (P24.1)

Samples of **The Daily Habit** show: Habit at a news desk in four framings (studio wide, split close-up, square PiP, full graphic), three sets (Riso Newsroom, Paper Desk, Night Desk), two Habit looks (pixel, 2D puppet), four intro types and the show package. Design: vault `Docs/Show Bible.md`.

| File | What |
|---|---|
| `show.js` | One HyperFrames composition for every variant: sets, Habit rigs, framing layer (camera + clip + seam mask), graphics, package, captions. Pure function of time; seek-safe |
| `make.py` | Builds, checks and renders the variants; `sheets`, `safe` (framings vs platform UI), `mouth` (lip sync only while the voice speaks) |
| `episode.json` | The sample script (the 27 Oct GPS story told as one story) with a shot and a graphic per beat |

```
uv run python -m frameflow.voice tts out/studio-show/voice-script.json out/studio-show/voice   # house voice, one WAV per line
uv run python spikes/studio-show/make.py --list
uv run python spikes/studio-show/make.py render episode
```

Assets: everything is drawn in code (SVG); fonts and libraries are the repo's vendored ones (OFL fonts, GSAP). No new third-party asset, so no new licence rows. Outputs go to `out/studio-show/` (gitignored).
