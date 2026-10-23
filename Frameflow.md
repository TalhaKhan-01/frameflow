---
type: hub
project: Frameflow
code: ~/Talha_Khan/Code/frameflow
status: active
created: 2026-10-23
tags: [hub]
---
# Frameflow

**What it is:** a pipeline that turns an idea into a finished vertical short video (9:16, under 60 s) and publishes it to YouTube Shorts and Instagram Reels.
**Status:** shaping the first version, see [[V1 Scope]]
**Code:** `~/Talha_Khan/Code/frameflow`
**Links:** [[log]] · [[index]]

## Goals
_Draft goals, to be confirmed with Talha._
- Idea → script → voiceover → visuals → captions → rendered 9:16 video, in one run.
- A review step before anything is posted.
- Publish (or schedule) to YouTube Shorts and Instagram Reels from the same render.
- Keep running costs low: local or free tools by default, paid APIs only where they clearly pay off.

## Dashboard

### Docs
```dataview
TABLE status, file.mtime AS "Updated"
FROM "Docs"
SORT file.mtime DESC
```

### Concepts
```dataview
TABLE status, length(file.inlinks) AS "Links in"
FROM "Wiki/Concepts"
SORT status ASC, file.name ASC
```

### Sources
```dataview
TABLE kind, author, read
FROM "Wiki/Sources"
SORT read DESC
```

### Decisions
```dataview
TABLE status, date
FROM "Decisions"
SORT date DESC
```

### Raw material not yet processed
```dataview
LIST
FROM "Raw"
SORT file.ctime DESC
```

### Orphans (nothing links here yet)
```dataview
LIST
FROM "Wiki" OR "Docs" OR "Decisions"
WHERE length(file.inlinks) = 0
```
