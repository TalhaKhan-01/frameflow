# Frameflow vault: schema

Obsidian vault for the **Frameflow** project. Code lives in `~/Talha_Khan/Code/frameflow/`, never here. This vault holds docs, decisions and the project's knowledge graph.

## Layout
| Path | Holds |
|---|---|
| `Frameflow.md` | Hub: what the project is, goals, Dataview dashboard |
| `index.md` | One line per note, grouped by section. Update it whenever a note is added, renamed or removed |
| `log.md` | Dated progress log, newest at the top. Add an entry for every working session |
| `Docs/` | Project documents: plans, specs, write-ups (`type: doc`) |
| `Decisions/` | One note per decision: context, options, choice, consequences (`type: decision`) |
| `Wiki/Concepts/` | Atomic notes, one idea each (`type: concept`, `status: seed / growing / evergreen`) |
| `Wiki/Sources/` | One note per article, paper, video, course or repo that was read (`type: source`) |
| `Raw/` | Untouched input: pasted text, transcripts, exports. Never edit; summarise into `Wiki/Sources/` |
| `Attachments/` | Images and files embedded in notes |
| `Templates/` | Templater templates (applied automatically by folder). Not part of the graph |

## Writing rules
- Every note starts with YAML frontmatter matching its template. When Claude writes a note directly, write real values, never Templater `<% %>` code.
- Note names in Title Case, readable as link text (`Retrieval Augmented Generation.md`).
- Link liberally with `[[wikilinks]]`: the knowledge graph is built from them. A concept links to what it builds on and what it leads to; a source links to the concepts it feeds; a decision links to the concepts and docs behind it.
- One idea per concept note. Split a note when it grows a second idea.
- Flow of knowledge: `Raw/` → `Wiki/Sources/` (summary) → `Wiki/Concepts/` (ideas) → `Docs/` and `Decisions/` (applied).
- No secrets, keys or passwords in the vault: it is a git repo.

## Git
The vault is its own git repo. The Obsidian Git plugin commits every 10 minutes; push is off until a remote is added (ask Talha first). Claude may commit after a batch of edits.
