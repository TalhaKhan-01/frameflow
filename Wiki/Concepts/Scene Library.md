---
type: concept
status: seed
created: 2026-10-23
tags: [concept, architecture]
---
# Scene Library

**In one line:** polished, reusable motion-graphics templates built once; each video only fills in a short JSON plan.

## Explanation
Example scenes: headline reveal, stat counter, chart race, code snippet, comparison split, 3D product spin, news snapshot with highlight. A plan step looks like `{scene: "stat-counter", value: "40%", label: "...", duration: 4}`. Expensive creative work is paid once, each video stays cheap in tokens, and quality stays consistent.

## How it connects
- Builds on: [[High Quality Short]] (consistent look)
- Leads to: [[Pipeline With Few Model Calls]]

## Sources
- [[Strategy Q&A 2026-10-23]]
