---
type: doc
status: final
created: 2026-10-23
tags: [doc, qa, strategy]
---
# Strategy Q&A 2026-10-23

Quick Q&A between Talha and Claude about [[Frameflow]]'s two main aims:
1. Make high-quality, trendy videos, with a real understanding of what "high quality" means.
2. Work smartly, using as few tokens as possible without lowering quality.

## Q1. Is it feasible and cost-effective to make this an agentic workflow?
**Yes, as a code pipeline with a few model calls, not a fully agentic one.** Decision: [[Pipeline With Few Model Calls]].
- A fully agentic workflow re-reads its growing context on every turn. It would cost hundreds of thousands of tokens per video, vary from run to run, and use up the Pro plan's limits at 1–2 videos a day.
- Code does collection, voice, captions, stock search, rendering, mixing, checks and publishing (0 tokens). The model is used only for: ranking ideas (one batched call), the script plus a JSON scene plan (one call), and a quality review (one call).
- Biggest saver: the [[Scene Library]]. Polished, reusable scene templates are built once; each video only fills in a short JSON plan.
- Other savers: the right model for each step (Haiku for ranking and checks, Sonnet for scripts, Opus for templates and hard creative calls), batching, fixed prompts with strict JSON output, and self-repair retries capped at 1–2.
- Estimate: about 10–30k tokens per video once the library exists (to be measured). `claude -p` runs share the Pro plan's usage limits with interactive sessions.

## Q2. What does Claude understand by a high-quality video?
**A video people watch to the end, and feel was worth it.** Polish serves that goal. Full breakdown: [[High Quality Short]].
- Formula: right idea × strong hook × no wasted seconds × a consistent look and sound × trust. It's multiplicative, so one weak factor drags the whole video down.
- Becomes measurable as a scored [[Quality Bar]], applied by automatic checks and the review call. The niche study tests it against real data.
- Talha: "yes fantastic".

## Q3. In the backend, the aim is to get into the algorithm and catch an audience. How?
**Score well on the signals the algorithms measure, and learn faster than other channels.** Details: [[Algorithm Signals]].
- Both platforms test each video on a small audience and widen its reach when the reaction is strong.
- The backend:
  1. a feedback loop (Analytics and Insights APIs, stored next to each video's script, hook, scenes, length and topic);
  2. a weekly learning call that updates the quality bar and prompts;
  3. hook experiments (Instagram Trial Reels);
  4. speed on trends;
  5. a focused niche;
  6. a clean native upload for each platform;
  7. posting-time data.
- Never: fake engagement, bots, engagement groups, bought followers, mass re-uploads.
