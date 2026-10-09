"""Telegram bot for the YouTube downloader backend.

Runs inside the same container as server.py (started as a background thread
when the TELEGRAM_BOT_TOKEN env var is set). Talks to the backend over
localhost, so no extra hosting is needed.

User flow: send a YouTube link -> choose Video or MP3 -> bot replies with
the file (Telegram caps bot files at 50 MB).
"""
import asyncio
import logging
import os
import re
import time

import httpx
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

log = logging.getLogger("ytdl-bot")

PORT = int(os.environ.get("PORT", 5000))
API = "http://127.0.0.1:%d" % PORT
MAX_TG_BYTES = 50 * 1024 * 1024  # Telegram Bot API file limit

YOUTUBE_RE = re.compile(r"(https?://)?(www\.)?(youtube\.com|youtu\.be)/\S+")

pending = {}  # telegram user id -> youtube url


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Send me a YouTube link and I'll fetch it for you as video or MP3."
    )


async def on_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    m = YOUTUBE_RE.search(text)
    if not m:
        await update.message.reply_text(
            "That doesn't look like a YouTube link. Send me a YouTube URL."
        )
        return
    pending[update.effective_user.id] = m.group(0)
    kb = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Video", callback_data="dl:video"),
                InlineKeyboardButton("MP3 audio", callback_data="dl:audio"),
            ]
        ]
    )
    await update.message.reply_text("What do you want?", reply_markup=kb)


async def on_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    kind = q.data.split(":", 1)[1]
    url = pending.pop(update.effective_user.id, None)
    if not url:
        await q.edit_message_text("Send me a YouTube link first.")
        return
    await q.edit_message_text("Downloading... this can take a minute.")
    try:
        path, title = await asyncio.to_thread(_fetch_and_wait, url, kind)
    except Exception as e:  # noqa: BLE001 - surfaced to the user
        await q.message.reply_text("Failed: %s" % str(e)[:200])
        return
    try:
        size = os.path.getsize(path)
        if size > MAX_TG_BYTES:
            await q.message.reply_text(
                "That file is about %d MB, too big for Telegram "
                "(50 MB max). Try a shorter video, or use the website."
                % (size // 1024 // 1024)
            )
            return
        with open(path, "rb") as f:
            if kind == "audio":
                await q.message.reply_audio(audio=f, title=title[:64])
            else:
                await q.message.reply_video(video=f, caption=title[:200])
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def _fetch_and_wait(url, kind):
    """Blocking worker: ask the backend to download, poll, save the file.

    Returns (path, title). Runs in a thread via asyncio.to_thread.
    """
    c = httpx.Client(base_url=API, timeout=30)
    r = c.post("/api/fetch", json={"url": url, "kind": kind})
    r.raise_for_status()
    job_id = r.json()["job_id"]

    deadline = time.time() + 600
    title = "video"
    while time.time() < deadline:
        time.sleep(4)
        s = c.get("/api/status/%s" % job_id).json()
        status = s.get("status")
        if status == "ready":
            title = s.get("title", "video")
            break
        if status == "error":
            raise RuntimeError(s.get("error", "download failed"))
    else:
        raise RuntimeError("timed out waiting for the download")

    dl = c.get("/api/download/%s" % job_id)
    dl.raise_for_status()
    path = "/tmp/tg_%s.%s" % (job_id, "mp3" if kind == "audio" else "mp4")
    with open(path, "wb") as f:
        for chunk in dl.iter_bytes(1024 * 256):
            f.write(chunk)
    return path, title


def run_bot(token: str):
    logging.basicConfig(level=logging.WARNING)
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(on_choice))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_link))
    log.warning("Telegram bot started")
    app.run_polling()


if __name__ == "__main__":
    run_bot(os.environ["TELEGRAM_BOT_TOKEN"])
