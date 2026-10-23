---
type: doc
status: in-discussion
created: 2026-10-23
tags: [doc]
---
# V1 Scope

Working plan for the first version of [[Frameflow]]. Open questions first: the answers decide the design.

## Answers so far (2026-10-23)
| Question | Answer | Still open |
|---|---|---|
| Niche | To be discovered together | Run a niche study before committing (see [[#Things to discuss]]) |
| Ideas | Trending tech news, tech topics, global tech changes, AI and finance, more to come | Which sources, how ideas are ranked |
| Voice | Kokoro, or the best free alternative, for fast, high-quality output | Voice, language(s), pace; compare a few models |
| Visuals | Stock footage (Pexels, Pixabay, …), low-poly 3D when needed, code-made motion graphics, HyperFrames, Playwright captures, snapshots of news from trusted sites | Visual identity, which tool per beat |
| Publishing | Talha provides the accounts and access for automated posting | YouTube API audit, Instagram account type |
| Volume | 1–2 videos per day | How much review time per video |
| Budget | Free tools only, see [[Free Tools Only]] | Where scripts are written (see below) |

Candidate tools for each stage: [[Tool Candidates]].

## Things to discuss
1. **Niche study:** measure what works in tech, AI and finance Shorts before choosing one lane.
2. **Who writes the scripts on a zero budget:** Claude through Claude Code (`claude -p`, inside Talha's Pro plan limits, no API bill) or a local LLM (Ollama; 4 GB VRAM limits it to small models). The Claude API itself is paid.
3. **Voice:** pick one model and voice after listening to samples; English only, or Hindi/Urdu too.
4. **YouTube upload limit:** videos uploaded through an unaudited Google API project are locked to private until the project passes Google's audit. Plan the audit, or upload by hand until then.
5. **Platform policies:**
   - YouTube can demonetise mass-produced, templated content under its "inauthentic content" policy, so each video needs a real angle.
   - Realistic AI-made visuals must be labelled as synthetic.
   - News screenshots: credit the source, keep them short and add commentary, never show paywalled content.
6. **Licences:** stock and music must allow commercial use; keep a licence record for every asset in each video.
7. **Hardware:** RTX 3050 with 4 GB VRAM. Local voice and Whisper are fine; local image and video generation is slow or too heavy.
8. **Scheduling:** what runs automatically each day, and where the review step sits.

## Pipeline sketch
| Stage | Does | Output |
|---|---|---|
| 1. Idea | Pick a topic | topic + angle |
| 2. Script | Hook, body, call to action, sized to under 60 s | script text |
| 3. Voice | Text to speech, or a recording | audio + word timings |
| 4. Visuals | Footage, images or motion graphics per beat | clips |
| 5. Captions | Word-timed captions burned in | caption track |
| 6. Render | Assemble 1080×1920 video | `.mp4` |
| 7. Review | Watch, approve or send back | approved video |
| 8. Publish | Upload to YouTube Shorts and Instagram Reels, with title, description and hashtags | live links |

## Not in V1
- Analytics and feedback loops (views, retention).
- Multiple channels or clients.
