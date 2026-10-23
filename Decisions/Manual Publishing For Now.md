---
type: decision
status: accepted
date: 2026-10-23
tags: [decision, publishing]
---
# Manual Publishing For Now

## Context
Automatic YouTube uploads and private analytics need an OAuth consent screen (Google Auth Platform) and a sign-in client. Frameflow is a personal project that will be open-sourced on GitHub and Vercel.

## Decision (Talha, 2026-10-23)
Skip the Google Auth Platform setup for now.

## Consequences
- Frameflow renders the finished video plus a ready-to-paste title, description and tags. Talha uploads to YouTube and Instagram by hand.
- No automatic private stats (watch %, viewed vs swiped away). The feedback loop in [[Algorithm Signals]] starts with numbers copied from YouTube Studio and Instagram Insights, or public counts only.
- Public data (search, views, likes, for the [[Niche Study]]) only needs a plain **API key** (Google Cloud → Credentials), which isn't part of the Auth Platform.
- Open-sourcing fits: the repo will ship "bring your own keys" config; no secrets in git.
- Revisit when daily volume makes manual uploads a chore.
