FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    supervisor \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt && rm /tmp/requirements.txt

COPY backend/app.py            /app/app.py
COPY backend/scheduler.py      /app/scheduler.py
COPY backend/adhan_player.py   /app/adhan_player.py
COPY backend/db/               /app/db/
COPY backend/providers/        /app/providers/
COPY backend/cli/              /app/cli/

COPY frontend/static/    /app/static/
COPY frontend/templates/ /app/templates/

COPY backend/supervisord.conf /app/supervisord.conf

EXPOSE 8080

CMD ["supervisord", "-c", "/app/supervisord.conf"]
