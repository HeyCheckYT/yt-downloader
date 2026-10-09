FROM python:3.11-slim

# ffmpeg: needed for mp3 extraction and mp4 merging.
# git/curl/unzip: needed to install deno and fetch the bgutil repo.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg git curl unzip \
    && rm -rf /var/lib/apt/lists/*

# deno (>= 2.4.3): JS runtime used by yt-dlp's PO-token plugin to pass
# YouTube's "confirm you're not a bot" check on datacenter IPs.
RUN curl -fsSL https://deno.land/install.sh | DENO_INSTALL=/root/.deno sh
ENV PATH="/root/.deno/bin:${PATH}"
RUN deno --version

# bgutil PO-token server files (required by the bgutil-ytdlp-pot-provider
# pip plugin; deno resolves its npm dependencies itself).
RUN git clone --depth 1 https://github.com/Brainicism/bgutil-ytdlp-pot-provider.git /opt/bgutil

# Pre-warm deno's npm cache so the first real token request doesn't time out.
RUN cd /opt/bgutil/server && deno install && deno run --allow-all src/generate_once.ts --version

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY server.py bot.py ./

# Render sets $PORT; one worker so the Telegram bot polls only once
CMD ["sh", "-c", "gunicorn server:app --bind 0.0.0.0:$PORT --workers 1 --threads 8 --timeout 600"]
