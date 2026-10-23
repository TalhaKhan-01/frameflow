---
type: doc
status: draft
created: 2026-10-23
tags: [doc]
---
# V1 Scope

Working plan for the first version of [[Frameflow]]. Open questions first: the answers decide the design.

## Open questions
1. **Niche and format:** what are the videos about, and in what style? Faceless (stock/AI visuals, screen recordings, animated text) or with a face on camera?
2. **Input:** where do ideas come from? Typed by hand, a list or spreadsheet, or found automatically (trends, RSS, Reddit)?
3. **Voice:** AI voiceover (local or paid), your own recorded voice, or music only? Which language(s)?
4. **Visuals:** stock footage, AI-generated images or clips, code-generated motion graphics, or your own footage?
5. **Publishing:** upload automatically through the YouTube Data API and the Instagram Graph API (which requires an Instagram Business or Creator account linked to a Facebook Page), or export files and upload by hand at first?
6. **Volume:** how many videos a week?
7. **Budget:** zero (local and free tools only), or a small monthly budget for APIs?

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
