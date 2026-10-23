---
type: doc
status: first-run
created: 2026-10-23
tags: [doc, research]
---
# Niche Study

Purpose: set the mix and priorities across the six lanes in [[Wide Lanes India First]], and calibrate the [[Quality Bar]] against what actually performs.

## Method
1. For each lane, collect about 100–200 recent top Shorts (YouTube Data API with an API key, or `yt-dlp` metadata), with India-focused queries as well as global ones.
2. Measure:
   - **demand** (views);
   - **outliers** (views relative to channel size, showing room for small channels);
   - **saturation** (how many channels, how often they post);
   - **format** (length, hook type, cut pace, caption style, visuals).
3. Score each lane on demand, gaps, daily automation fit, fit with our visual strengths, ad value and credibility.
4. One-page result, then decide the weekly mix together.

## Status
First run 2026-10-23: [[Niche Study Results 2026-10-23]] (48 queries, ~1,900 Shorts, ~4,900 quota units).
Tool: the `niche-study` skill (`~/Talha_Khan/Claude/skills/niche-study/`); Frameflow's config is `~/Talha_Khan/Code/frameflow/research/niche-study.json`.

## First-run reading
- Ranking: global tech changes (0.88) > India's tech scene (0.64) > AI news (0.55) > dev tools (0.25) > AI × money (0.09) > how tech works (0.08).
- **Samples are noisy:** some queries pulled off-topic videos (game cheat codes under dev tools, Aadhaar how-tos under AI news, Hindi titles despite English relevance). The low-scoring lanes may be under-measured. Fix: sharper queries and a topic filter, then re-run.
- **Small channels break out in every lane:** channels with under 1k subscribers reached 100k–1M+ views. A new channel can win on single videos.
- **Winning patterns seen:** India angle on global tech (prices India vs USA vs UAE, "becoming an Indian brand?"), head-to-head comparisons ("ChatGPT vs Claude vs Gemini"), personal-stakes framing ("Is your job next?"), very short punchy clips (5–25 s) among the breakouts, while median length is about 60 s.
