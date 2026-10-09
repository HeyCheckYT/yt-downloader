FROM python:3.11-slim

# ffmpeg is needed for mp3 extraction and mp4 merging
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY server.py .

# Render sets $PORT; one worker so the Telegram bot polls only once
CMD ["sh", "-c", "gunicorn server:app --bind 0.0.0.0:$PORT --workers 1 --threads 8 --timeout 600"]
