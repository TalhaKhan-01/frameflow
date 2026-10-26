# Frameflow: plan of record

Frameflow turns a topic into a finished vertical Short (1080×1920 pixels, under 60 seconds) for YouTube Shorts and Instagram Reels, using free tools only. Talha reviews every video before it goes out. The aim is high-quality, trend-aware videos across six topic lanes, India-first and in English. This plan tracks the whole build, from research to a first week of daily posting.

**How to read the progress:** every task at the bottom of the tree has a test written next to it. A task is ticked only after that test has actually been run. The arc was set up after setup and research had started, so some tasks were ticked on 2026-10-23 after their tests were run that day (retrospective seeding).

## P0 Setup and foundations
Before any video can be made, the accounts, keys and project folders have to exist and be safe. This phase covers the password manager and two-factor sign-in, the YouTube Data API key (the key that lets a script read public YouTube statistics), the stock-media keys, the YouTube channel and Instagram Creator account, one private GitHub repository holding code and notes together, and a private secrets file that never enters git.

The stock-media keys (Pexels, Pixabay) are paused by those services, so free sources that need no key are planned in phase P5 instead.

## P1 Research: niche, deep study, quality bar
We don't guess what works: we measure it. The niche study compares six topic lanes (global tech, India's tech scene, AI news, developer tools, AI and money, how tech works) using about 1,900 recent Shorts. The deep study then looks closely at the Shorts that broke out from small channels: how fast the voice starts, how many words per minute, how often the picture cuts, how loud the audio is, what the first three seconds say and show.

Those numbers become the **quality bar**: a scored checklist with numeric targets that every Frameflow video has to pass. This phase also produces the written script rules (how to build a hook, how to pace, how to end).

## P2 Voice
Every video needs a clear, natural voice. This phase installs a free text-to-speech engine (Kokoro runs locally on this laptop) inside the project, lets Talha pick the house voice by ear from several samples, and builds the step that turns each script line into an audio clip with known length, at the standard loudness for these platforms.

## P3 Scene library (motion-graphics templates)
Instead of writing new animation code for every video, Frameflow uses a library of polished, reusable scene templates: a headline reveal, a number counter, an India-vs-world price comparison, an animated chart, a code or repository card, a news snapshot with highlights, a low-poly 3D explainer shot and a word-by-word caption layer. Each video only fills these with data, which keeps quality consistent and costs few AI tokens.

First a short trial decides the renderer (HyperFrames or Remotion). A "scene plan" format with an automatic checker defines what a video is made of. The visual identity (colours, fonts, motion style, safe zones for each platform) is locked before the templates are built. Every template must render the same frames every time (deterministic), so videos never judder.

## P4 Ideas and scripts
A collector gathers fresh ideas from tech news feeds, Hacker News, GitHub Trending and YouTube trends. One batched AI call (a small, cheap model) ranks them and picks an angle for each. A Frameflow script skill then writes the script and its scene plan, following the script rules from P1. Every factual line must carry a source link, or the checker rejects the plan.

## P5 Assets and licences
Videos need footage, images, music and sound effects that may legally be used on a channel that could earn money. This phase builds downloaders for free sources that need no key (Openverse, Wikimedia Commons, NASA), a licence record for every asset used in a video, and a small music and sound-effect library with commercial-use licences.

## P6 Assembly and quality checks
One command turns a scene plan into a finished video: voice, scenes, captions timed to the real spoken words, and music. Automatic checks then test it against the measurable parts of the quality bar (length, size, loudness, blank frames, captions matching the audio, licence records). One AI review call scores the judgement parts (hook, angle, pacing, accuracy). Nothing can be published until Talha approves it.

## P7 Publishing and feedback
Uploading is manual for now (a decision recorded in the vault), so Frameflow prepares a publish pack for each platform: title, description, tags, caption and hashtags. After posting, the links are logged. Statistics are recorded after 48 hours, and a weekly learning report compares the best and worst videos and proposes changes to the quality bar and prompts. This loop is how the channel learns what its audience wants.

## P8 Launch
The finish line: three pilot videos in three different lanes, then a full week with at least one video every day, then a retrospective that adjusts the lane mix using real numbers from the channel.

## P9 Quality v2
Talha's review of the first video: it read out facts over number screens. P9 makes videos feel written and directed by people. A scriptwriter skill writes in the voice of the named narrator **Habit** (mostly informative, a few funny everyday analogies), generates 20 hooks and keeps the best, builds an And-But-Therefore story with a re-hook at least every 10 seconds, and bans AI-sounding wording. A director skill storyboards each beat as a drawn, moving world with a sound cue. The voice gets per-line emotion; a sound layer adds whooshes, risers and impacts; the scene library gains maps, drawn props, kinetic type, fast transitions and 2.5D. A stricter quality bar (50-90 s) and review judge it, and a pilot video on Black October (PHP2Shell) proves it. Full plan: vault/Docs/Quality v2 Plan.md.

## P15 Studio board
Talha's call after the 26 Oct Kimi video (two renders, and the second one scored worse): Frameflow should work like a real studio. Every role is a desk with its own quality gate, and no desk grades its own work. A **showrunner** owns the run and turns Talha's loose revise words into a change order he confirms (Go / Change it / Cancel). A **fact-checker** verifies the brief and the script's claims. **Packaging** sets the title, cover and hook promise before any writing. A **script editor** does an independent table read. The **narrator** desk checks timing on the real voice. An **art director** and an **animatic** (HyperFrames stills every 3 s, screened in full) catch what the render would show, and **standards** checks labels, licences and claims. All of this happens before the one render, which is production, not a draft. Then a technical check, a final screening that must match the animatic, and Talha. Craft desks are generic skills (shorts-producer, shorts-factcheck, shorts-editor, shorts-screening, shorts-packaging); channel policy and glue are Frameflow modules; no Claude Code agents, because the pipeline runs unattended. Every desk reads one bar (research/quality-bar.json); the control panel shows the board and the first-render hit rate. After the live proof, the Studio web app and the betadoc tell the new story. Full plan: ~/.claude-personal/plans/so-few-things-we-radiant-knuth.md.
