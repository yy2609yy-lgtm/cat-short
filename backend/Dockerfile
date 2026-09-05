FROM python:3.12-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app
RUN python /app/scripts/generate_bed.py \
    && chmod +x /app/entrypoint.sh

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    MUSIC_BED_PATH=/app/assets/music/cozy_afternoon.wav

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
