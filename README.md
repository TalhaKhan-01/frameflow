# Frameflow

Automated short vertical videos (9:16, under 60 s) for YouTube Shorts and Instagram Reels: idea → script → voice → visuals → captions → render → review. Free tools only.

**Status:** research. Planning and decisions live in the Obsidian vault `~/Talha_Khan/Projects/Frameflow/`.

## Layout
| Path | Holds |
|---|---|
| `research/niche-study.json` | Lanes and queries for the `niche-study` skill |
| `data/` | Local SQLite data (gitignored) |
| `frameflow/` | Pipeline code (to come) |

Tools are separate Claude skills in `~/Talha_Khan/Claude/skills/`. This repo holds their config and the pipeline code.

## Run the niche study
```
python3 -I ~/Talha_Khan/Claude/skills/niche-study/scripts/niche_study.py --project . collect --dry-run
python3 -I ~/Talha_Khan/Claude/skills/niche-study/scripts/niche_study.py --project . all
```

## Secrets
Keys live in `~/.config/frameflow/secrets.env` (mode 600) or the environment. See `.env.example`. Never commit them.
