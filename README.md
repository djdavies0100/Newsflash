# The Daily Briefing

A personal daily news briefing app styled like a newspaper on your phone.
Pick topics (from suggestions or your own), get today's headlines pulled
automatically from Google News RSS, and each story gets a short AI-generated
summary so you can decide what's worth clicking into.

## How it works

- **`news_fetcher.py`** — pulls headlines per topic via Google News RSS search
- **`summarizer.py`** — fetches the actual article text and asks Claude for a
  one-sentence summary; falls back to summarizing from the headline alone if
  the article can't be fetched (paywalls, etc.)
- **`storage.py`** — SQLite storage for your topics, cached daily headlines,
  and cached AI summaries (so you're not re-summarizing the same story twice)
- **`app.py`** — FastAPI backend: topic management, suggested topics, the
  briefing endpoint, an on-demand summary endpoint, and a background
  scheduler that refreshes automatically at 7:00 AM every day
- **`static/index.html`** — the newspaper-style dashboard, built mobile-first
- **`static/manifest.json` + `static/icons/`** — home screen icon and PWA config

## Add it to your home screen

Once the app is running (locally or deployed), you can add it like a real app:

- **iOS (Safari)**: open the page → tap the Share icon → **Add to Home Screen**
- **Android (Chrome)**: open the page → tap the ⋮ menu → **Add to Home screen** /
  **Install app**

It'll launch full-screen with its own icon, no browser bar.

## Teaching it your taste (like / dislike)

Every story has 👍 / 👎 buttons. Tapping them does two things:

1. **Blocks bad sources automatically** — if a source's dislikes outweigh its
   likes by 2 or more (tracked across all your feedback, all time), future
   fetches skip that source entirely.
2. **Boosts topics you engage with** — topics with a strong positive like
   history get a few extra stories pulled each day.

This is deterministic (no AI needed) so it works with or without an API key,
and it compounds over time — the more you use it, the more it filters out
noise. Tap a button again to undo it.

## Setup

```bash
pip install -r requirements.txt
```

**For AI summaries**, set your Anthropic API key as an environment variable
before starting the server:

```bash
export ANTHROPIC_API_KEY="your-key-here"
```

Get a key at https://console.claude.com/settings/keys if you don't have one.
The app works fine without a key too — it'll just skip the summary line
under each headline.

## Run it

```bash
uvicorn app:app --reload --port 8000
```

Then open **http://localhost:8000** in your browser (or on your phone once deployed — see below).

1. Tap **Customize your edition**, pick some suggested topics or add your own
2. Hit **Refresh Edition** to pull today's headlines
3. Summaries fill in a few seconds after headlines load (they're generated
   in the background, a few at a time)
4. Come back tomorrow — it refreshes itself at 7 AM, or hit refresh manually anytime

Your topics, headlines, and cached summaries live in `briefing.db` (created
automatically — delete it anytime to start fresh).

## A note on summary cost

Summaries use `claude-haiku-4-5`, the cheapest current model, and are cached
permanently once generated — so you're only ever paying to summarize each
story once, not every time you load the page.

## Notes on the news source

This uses Google News' public RSS search endpoint
(`news.google.com/rss/search?q=...`), which requires no API key and works
for any free-text topic. It's more robust than scraping individual news
sites directly, since RSS structure rarely changes and this isn't tied to
any one publisher's website layout.

If you later want to add specific publications only (say, just NYT and
Reuters for a topic), that's a small change to `news_fetcher.py` — happy to
add that if you want it.

## Deploying so you can check it from your phone

Since this is single-user with no login, the simplest path is:

1. **Render.com** (free tier) — connect this folder as a repo, set the start
   command to `uvicorn app:app --host 0.0.0.0 --port $PORT`, add
   `ANTHROPIC_API_KEY` as an environment variable in Render's dashboard, deploy.
2. **Fly.io** — similar, works well for small always-on apps like this.

Both give you a public URL you can bookmark on your phone home screen so it
opens like a native app. Let me know if you want a `Dockerfile` or
step-by-step deploy walkthrough for either.

## Ideas for later (not built yet)

- Push notification / email when the briefing is ready
- Add-to-home-screen manifest so it launches full-screen like a real app
- Filter out specific sources you don't care about
- "Read" / "dismiss" state per story
