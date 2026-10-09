# YouTube Downloader — Deploy Guide

You get two parts: a **backend** (does the downloading, runs free on Render)
and a **Blogger widget** (the buttons your visitors see).

## Part 1 — Put the backend on Render (free, ~10 min)

1. Create a free account at **github.com** (if you don't have one).
2. Create a new repository (any name, e.g. `yt-downloader`), and upload
   these 4 files into it: `server.py`, `requirements.txt`, `Dockerfile`,
   `render.yaml`. (On GitHub: *Add file → Upload files*.)
3. Create a free account at **render.com**, then **New → Web Service**.
4. Connect your GitHub repo. Render will detect the `render.yaml` and pick
   the Docker runtime automatically — leave everything as-is, choose the
   **Free** plan, and click **Create Web Service**.
5. Wait ~5 minutes for the first build. When it says **Live**, copy your
   service URL — it looks like `https://yt-downloader-xxxx.onrender.com`.

That's it — the backend is running.

## Part 2 — Add it to Blogger (~5 min)

1. Open `blogger-widget.html` in any text editor.
2. Find the line `const YTDL_API = "https://YOUR-APP-NAME.onrender.com";`
   and replace it with your real Render URL from step 5 above.
3. In Blogger: **Layout → Add a Gadget → HTML/JavaScript**.
4. Paste the whole widget code, give it a title like "YouTube Downloader",
   and **Save**.
5. Open your blog and test it with any short YouTube video.

## Good to know

- **Free tier sleeps.** If nobody uses it for 15 minutes, Render puts it to
  sleep. The first click after that takes ~30–60 seconds to wake up — the
  widget already tells visitors to wait and retry.
- **Keep videos modest.** Video is capped at 720p mp4 to stay quick. Very
  long videos (1 hr+) may fail on the free tier's time limits.
- **Files auto-delete** from the server after 1 hour to save disk space.
- **If a download fails** with a "bot" error, YouTube is blocking the
  server's IP — wait a bit and retry. This happens occasionally with all
  free cloud hosts.

## Part 3 — Telegram bot (optional, ~5 min)

The bot runs inside the same backend, so no extra hosting or cost.

1. Open Telegram and search for **@BotFather**. Send `/newbot`, pick a
   display name and a username (must end in `bot`). BotFather replies with
   a token — copy it.
2. In Render: open your **yt-downloader** service → **Environment** → add
   variable `TELEGRAM_BOT_TOKEN` with the token as the value → **Save**.
   Render redeploys automatically (~3 min).
3. Open your bot in Telegram, send `/start`, then send any YouTube link.
   Choose **Video** or **MP3 audio** — the bot replies with the file.

Notes:
- Telegram caps bot files at 50 MB. Bigger files get a "too big" message;
  use the website for those.
- Keep-alive: the free plan sleeps after 15 idle minutes, which also pauses
  the bot. Add a free monitor at uptimerobot.com pinging your Render URL
  every 5 minutes to keep it awake (~720 hrs/month, inside the 750 hr free
  quota).

## Files

| File | What it is |
|---|---|
| `server.py` | The backend (Flask + yt-dlp) |
| `requirements.txt` | Python packages |
| `Dockerfile` | Tells Render how to build it (includes ffmpeg) |
| `render.yaml` | Tells Render to use the free plan |
| `blogger-widget.html` | Paste into Blogger |
