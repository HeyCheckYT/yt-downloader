"""YouTube downloader backend (Flask + yt-dlp).

Endpoints:
  POST /api/fetch            {"url": "<youtube url>", "kind": "video"|"audio"} -> {"job_id": ...}
  GET  /api/status/<job_id>  -> {"status": "queued"|"downloading"|"ready"|"error", ...}
  GET  /api/download/<job_id> -> the file as an attachment

Designed for free cloud hosting (Render free tier + Docker).
Video is capped at 720p mp4 to keep downloads fast and files small.
"""
import os
import threading
import time
import uuid

from flask import Flask, jsonify, request, send_file
from flask_cors import CORS

import yt_dlp

app = Flask(__name__)
CORS(app)  # the Blogger page lives on a different origin

DOWNLOAD_DIR = "/tmp/ydl"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

jobs = {}  # job_id -> dict(status, title, filename, error, created)


def _pick_file(job_id):
    for f in os.listdir(DOWNLOAD_DIR):
        if f.startswith(job_id):
            return f
    return None


def download_job(job_id, url, kind):
    try:
        jobs[job_id]["status"] = "downloading"
        outtmpl = os.path.join(DOWNLOAD_DIR, "%s.%%(ext)s" % job_id)

        if kind == "audio":
            fmt = "bestaudio/best"
            postprocessors = [
                {"key": "FFmpegExtractAudio", "preferredcodec": "mp3",
                 "preferredquality": "192"}
            ]
            merge = None
        else:
            # 720p-or-lower mp4 keeps free-tier downloads quick
            fmt = ("bv*[height<=720][ext=mp4]+ba[ext=m4a]/"
                   "b[height<=720][ext=mp4]/b[height<=720]/b")
            postprocessors = []
            merge = "mp4"

        opts = {
            "format": fmt,
            "outtmpl": outtmpl,
            "postprocessors": postprocessors,
            "merge_output_format": merge,
            "quiet": True,
            "no_warnings": True,
            "retries": 3,
            # mobile player clients are far less likely to be
            # bot-blocked from datacenter IPs
            "extractor_args": {"youtube": {"player_client": ["android", "web"]}},
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get("title", "video")

        fname = _pick_file(job_id)
        if not fname:
            raise RuntimeError("download produced no file")
        jobs[job_id].update(status="ready", title=title, filename=fname)
    except Exception as e:  # noqa: BLE001 - surfaced to the widget
        jobs[job_id].update(status="error", error=str(e)[:300])


@app.post("/api/fetch")
def fetch():
    data = request.get_json(force=True, silent=True) or {}
    url = (data.get("url") or "").strip()
    kind = data.get("kind", "video")
    if kind not in ("video", "audio"):
        kind = "video"
    if not url or ("youtube.com" not in url and "youtu.be" not in url):
        return jsonify({"error": "that is not a YouTube URL"}), 400
    job_id = uuid.uuid4().hex[:12]
    jobs[job_id] = {"status": "queued", "created": time.time()}
    threading.Thread(target=download_job, args=(job_id, url, kind),
                     daemon=True).start()
    return jsonify({"job_id": job_id})


@app.get("/api/status/<job_id>")
def status(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "unknown job"}), 404
    out = {"status": job["status"]}
    if job["status"] == "ready":
        out["title"] = job.get("title")
        out["download_url"] = "/api/download/%s" % job_id
    elif job["status"] == "error":
        out["error"] = job.get("error")
    return jsonify(out)


@app.get("/api/download/<job_id>")
def download(job_id):
    job = jobs.get(job_id)
    if not job or job["status"] != "ready":
        return jsonify({"error": "not ready"}), 404
    path = os.path.join(DOWNLOAD_DIR, job["filename"])
    if not os.path.exists(path):
        return jsonify({"error": "file expired, fetch again"}), 404
    return send_file(path, as_attachment=True,
                     download_name=job["filename"])


@app.get("/")
def index():
    return "YouTube downloader backend is running."


@app.before_request
def cleanup():
    # free tiers have tiny disks: drop files older than an hour
    now = time.time()
    try:
        for f in os.listdir(DOWNLOAD_DIR):
            p = os.path.join(DOWNLOAD_DIR, f)
            if now - os.path.getmtime(p) > 3600:
                try:
                    os.remove(p)
                except OSError:
                    pass
    except OSError:
        pass


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
