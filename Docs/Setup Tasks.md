---
type: doc
status: in-progress
created: 2026-10-23
tags: [doc, setup, tasks]
---
# Setup Tasks

Tasks for Talha to set up accounts and keys for [[Frameflow]]. All free ([[Free Tools Only]]). Tick each box when it's done.

## Golden rules for secrets
- Keys go **only** into `~/.config/frameflow/secrets.env` (mode 600, outside git and outside this vault). Edit it with `nano ~/.config/frameflow/secrets.env`.
- **Never paste a key into the chat**, a screenshot, a note or a commit. Chats are stored.
- Claude's file tools are blocked from reading that folder (deny rule in `~/.claude-personal/settings.json`). Pipeline scripts load the keys at runtime; Claude only checks which names are filled in, never the values.
- If a key ever leaks: revoke it on the provider's site, make a new one, update the file.

## Accounts (no secrets here)
| Platform | Account | Signed in with |
|---|---|---|
| YouTube | https://www.youtube.com/channel/UCrcF7Q5J4kEENdJuA8BPQxQ (channel ID `UCrcF7Q5J4kEENdJuA8BPQxQ`) | talhakhanhere16@gmail.com |
| Instagram | https://www.instagram.com/madebythirdspace/ (Creator) | talhahere16@gmail.com |
| Google Cloud | project `Frameflow` | |

## A. Security basics (now)
- [x] Install a password manager: Bitwarden, installed and logged in (2026-10-23).
- [ ] Turn on two-factor authentication with an authenticator app for every account below. Save the recovery codes in the password manager.

## B. Stock media keys (now, about 10 min)
- [ ] ⏸ (2026-10-23: new key issuance paused) **Pexels:** sign up → https://www.pexels.com/api/ → request API key → `PEXELS_API_KEY`.
- [ ] ⏸ (2026-10-23: key requests also blocked) **Pixabay:** sign up → https://pixabay.com/api/docs/ (the key appears on the page when logged in) → `PIXABAY_API_KEY`.

## C. Google / YouTube
**Now:**
- [x] Decided 2026-10-23: start on Talha's own account, move to a separate one later. Original question: a **separate Google account for the channel** (recommended: keeps your personal Gmail apart and is easier to hand over or recover) or your main one.
- [x] Google Cloud project `Frameflow` created (2026-10-23); APIs still to enable. Google Cloud Console (https://console.cloud.google.com) → new project `frameflow` → enable **YouTube Data API v3** and **YouTube Analytics API**.
- [ ] OAuth consent screen → user type **External** → app name `Frameflow` → add the channel's Google account as a test user.
- [ ] Set the consent screen's publishing status to **In production**. In Testing mode, sign-in tokens expire every 7 days and the daily automation would break. It stays unverified: you're the only user and will click past one warning screen.
- [ ] Credentials → Create OAuth client ID → type **Desktop app** → download the JSON → save it as `~/.config/frameflow/youtube_client_secret.json` → `chmod 600` it.

**After the niche study:**
- [x] Channel created early, on Talha's own account (2026-10-23). Create the YouTube channel (name, handle, picture, banner, description). Claude drafts these once the niche is chosen.
- [ ] Put the channel ID into `YOUTUBE_CHANNEL_ID`.
- [ ] One-time browser sign-in: Claude runs the authorisation script, you approve in the browser, and the refresh token saves itself into the secrets folder.

**When the first videos are ready:**
- [ ] Submit the **YouTube API Services audit form**, so videos uploaded through the API can be public. Until it's approved, API uploads stay private: post by hand, or upload as private and publish in Studio.

## D. Instagram (after the niche study)
- [x] Instagram Creator account `@madebythirdspace` created (2026-10-23).
- [ ] Meta for Developers (https://developers.facebook.com) → developer account → create an app for the Instagram API.
- [ ] Add the product **Instagram API with Instagram Login** (no Facebook Page needed) → add your account as a tester → generate a token with the content-publishing and insights permissions. Meta's screens change often, so do this step together with Claude in a live session.
- [ ] Put the app ID, app secret, Instagram user ID and access token into `secrets.env`. The token lasts 60 days; the pipeline will refresh it automatically.

## E. Optional
- [ ] **FRED** key (US economic data, for finance videos): https://fred.stlouisfed.org/docs/api/api_key.html → `FRED_API_KEY`.

## F. Hand-off
- [ ] Fill in `secrets.env` and save.
- [ ] Tell Claude "keys done". Claude runs a check that prints only which variables are set or missing, never the values.
