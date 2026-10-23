---
type: decision
status: proposed
date: 2026-10-23
tags: [decision, architecture]
---
# Pipeline With Few Model Calls

## Context
[[Frameflow]] must make high-quality videos daily, using as few tokens as possible, under [[Free Tools Only]] (scripts run through Claude Code inside the Pro plan).

## Options
1. Fully agentic: an agent plans, searches, writes code, renders and retries on its own.
2. A fixed code pipeline with 3–4 model calls per video at the steps that need judgment, plus a reusable [[Scene Library]].

## Decision
Option 2 (proposed in [[Strategy Q&A 2026-10-23]]).

## Consequences
- About 10–30k tokens per video once the library exists; to be measured.
- Model calls: rank ideas (Haiku, batched), script plus JSON scene plan (Sonnet), quality review (Haiku or Sonnet). Opus for building templates.
- Consistent quality comes from perfected templates; the one-time expensive work is building the library.
- Agent loops only for self-repair after a failed check, capped at 1–2 retries.
