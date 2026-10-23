---
type: hub
project: Frameflow
code: ~/Talha_Khan/Code/frameflow
status: active
created: 2026-10-23
tags: [hub]
---
# Frameflow

**What it is:** _one line about the project_
**Code:** `~/Talha_Khan/Code/frameflow`
**Status:** active · [[log]] · [[index]]

## Goals
-

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
