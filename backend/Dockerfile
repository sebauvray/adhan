FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    supervisor \
    tzdata \
    ca-certificates \
    curl \
    gnupg \
    && install -m 0755 -d /etc/apt/keyrings \
    && curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc \
    && chmod a+r /etc/apt/keyrings/docker.asc \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian $(. /etc/os-release && echo $VERSION_CODENAME) stable" \
       > /etc/apt/sources.list.d/docker.list \
    && apt-get update && apt-get install -y --no-install-recommends \
    docker-ce-cli \
    docker-compose-plugin \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt && rm /tmp/requirements.txt

COPY backend/app.py            /app/app.py
COPY backend/scheduler.py      /app/scheduler.py
COPY backend/adhan_player.py   /app/adhan_player.py
COPY backend/audio/            /app/audio/
COPY backend/db/               /app/db/
COPY backend/providers/        /app/providers/
COPY backend/cli/              /app/cli/

COPY backend/supervisord.conf /app/supervisord.conf

EXPOSE 8080

CMD ["supervisord", "-c", "/app/supervisord.conf"]
