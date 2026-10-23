---
type: doc
status: draft
created: 2026-10-23
tags: [doc, tools]
---
# Tool Candidates

Free tools for each stage of [[Frameflow]], under the [[Free Tools Only]] rule. ★ = shortlisted, ⚠ = licence or policy catch. Check every licence again before the tool goes into the build.

Hardware: RTX 3050 Laptop (4 GB VRAM), 16 threads, 15 GB RAM. FFmpeg, Blender, Node 24 and Python 3.12 are already installed.

## 1. Ideas and research
| Tool | Gives | Notes |
|---|---|---|
| ★ RSS feeds (The Verge, TechCrunch, Ars Technica, Reuters Tech, company blogs) | Fresh news | Free and stable; `feedparser` |
| ★ Hacker News API | What developers are discussing | Free, no key |
| ★ GitHub Trending | New tools and repos | Scrape the page; no official API |
| arXiv API | New AI papers | Free |
| Reddit (r/technology, r/MachineLearning, r/LocalLLaMA) | Discussion and sentiment | Free API tier is rate-limited |
| Google Trends via `pytrends` | Search interest | Unofficial; breaks often |
| ★ YouTube Data API search | What's already trending in Shorts | Free quota; also feeds the niche study |
| Finance data: `yfinance`, CoinGecko, FRED | Prices and macro charts | `yfinance` is unofficial; FRED needs a free key |

## 2. Script
| Tool | Notes |
|---|---|
| ★ Claude via Claude Code (`claude -p`) | Best quality; runs inside the Pro plan's limits, no API bill |
| Ollama + a small model (Qwen, Llama, Gemma at 3–8B) | Fully local fallback; quality lower, 4 GB VRAM is tight |

## 3. Voice
| Tool | Licence | Notes |
|---|---|---|
| ★ Kokoro-82M | Apache-2.0 | Fast even on CPU, very natural English, some Hindi voices |
| ★ Chatterbox (Resemble AI) | MIT | Emotion control, voice cloning; heavier, test on 4 GB |
| Indic Parler-TTS (AI4Bharat) | Apache-2.0 | For Hindi or other Indian languages |
| Piper | check (moved to GPL) | Very fast, more robotic |
| ⚠ F5-TTS | code MIT, weights non-commercial | Not for a monetised channel |
| ⚠ XTTS-v2 | Coqui licence, non-commercial | Avoid |

## 4. Captions and timing
| Tool | Licence | Notes |
|---|---|---|
| ★ faster-whisper / WhisperX | MIT / BSD | Word timestamps for animated captions; also a QA check (does the audio say what the script says?) |
| `pysubs2` | MIT | Writes styled `.ass` captions for FFmpeg |

## 5. Visuals
**Motion graphics (rendered from code, Claude's strength)**
| Tool | Licence | Good for |
|---|---|---|
| ★ HyperFrames | Apache-2.0 | HTML/CSS/JS scenes rendered to video |
| ★ Remotion | free for individuals and small companies | React video; large ecosystem |
| Motion Canvas / Revideo | MIT | Code-driven animation, smooth timelines |
| ★ Manim (Community) | MIT | Explaining AI and maths concepts: graphs, equations, network diagrams |
| GSAP | free (now including bonus plugins) | Web animation inside HTML scenes |
| Lottie (`lottie-web`) + LottieFiles free animations | MIT / per file | Icons and small animated elements |
| ECharts / D3 | Apache-2.0 / ISC | Finance and data charts that animate |
| Shiki | MIT | Code snippets with real syntax colouring |
| Mermaid, Excalidraw | MIT | Diagrams in a hand-drawn or clean style |

**3D (low-poly when needed)**
| Tool | Licence | Notes |
|---|---|---|
| ★ Blender (installed) | GPL | Low-poly scenes, rendered headless from Python |
| Three.js | MIT | 3D in the browser, captured frame by frame |
| ★ Kenney assets, Poly Pizza | CC0 / mixed (check per model) | Free low-poly models |

**Captures and stock**
| Tool | Licence | Notes |
|---|---|---|
| ★ Playwright | Apache-2.0 | Deterministic screenshots and page captures (never a jittery screencast); news snapshots, product pages |
| ★ Pexels, Pixabay | free commercial licences | Stock video and photos through their APIs |
| Mixkit, Coverr | free licences | More stock video |
| NASA media, Wikimedia Commons | public domain / per file | Space and science shots |
| Lucide / Iconify icons, Google Fonts | ISC / OFL | Icons and fonts |
| ⚠ News snapshots | publishers' copyright | Short, credited, with commentary, never paywalled; blur ads and personal data |
| Local image generation (SD 1.5 / SDXL-Turbo) | varies | 4 GB VRAM: slow; only if a scene really needs it; realistic output needs YouTube's synthetic-content label |

## 6. Music and sound
| Source | Notes |
|---|---|
| ★ Pixabay Music and sound effects | Free commercial licence |
| Freesound | Per-file CC0 / CC-BY (credit required) |
| Incompetech | CC-BY, credit required |
| YouTube Audio Library | Manual download; check per track whether it may also go on Instagram |

## 7. Assembly and QA
| Tool | Notes |
|---|---|
| ★ FFmpeg (installed) | Final mix, captions burned in, 1080×1920, loudness normalised to −14 LUFS |
| MoviePy | Python wrapper for simple edits |
| `ffprobe` checks | Duration, resolution, audio levels, black-frame detection before publishing |
| Playwright + HTML templates | Thumbnails and covers |

## 8. Publishing and scheduling
| Tool | Notes |
|---|---|
| ★ YouTube Data API v3 | Free 10,000 units/day; an upload costs about 1,600, so 1–2 a day fits. ⚠ Uploads stay private until the API project passes Google's audit |
| ★ Instagram Graph API (content publishing, Reels) | Needs an Instagram Business or Creator account linked to a Facebook Page and a Meta app |
| SQLite job table | Each video's status: idea → scripted → rendered → approved → posted |
| systemd timer or cron | Daily runs |
| n8n (self-hosted) | Optional visual workflow tool; free for your own use |
