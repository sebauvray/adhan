ARG DEBIAN_VERSION=bookworm
FROM debian:${DEBIAN_VERSION}

ARG TZ \
    AUTONOMOUS=false \
    GECKODRIVER_VERSION=v0.34.0

WORKDIR /app

# Packages de base (toujours installés)
RUN apt-get update && apt-get install -y \
    tzdata \
    wget \
    python3 \
    python3-pip \
    cron \
    procps \
    jq \
    curl \
    && if [ "$AUTONOMOUS" = "true" ]; then apt-get install -y firefox-esr; fi \
    && rm -rf /var/lib/apt/lists/*

# Timezone
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Geckodriver — uniquement si AUTONOMOUS=true
RUN if [ "$AUTONOMOUS" = "true" ]; then \
      ARCH=$(uname -m) && case "$ARCH" in \
        x86_64)  ARCH="linux64" ;; \
        aarch64) ARCH="linux-aarch64" ;; \
        arm*)    ARCH="linux-armhf" ;; \
        *) echo "Architecture non supportée"; exit 1 ;; \
      esac && \
      wget -O geckodriver.tar.gz \
        "https://github.com/mozilla/geckodriver/releases/download/$GECKODRIVER_VERSION/geckodriver-$GECKODRIVER_VERSION-$ARCH.tar.gz" \
      && tar -xzf geckodriver.tar.gz \
      && mv geckodriver /usr/local/bin/ \
      && chmod +x /usr/local/bin/geckodriver \
      && rm geckodriver.tar.gz; \
    fi

# Dépendances Python
COPY scheduler/requirements.txt .
RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt \
    && if [ "$AUTONOMOUS" = "true" ]; then \
         pip3 install --no-cache-dir --break-system-packages selenium; \
       fi \
    && rm requirements.txt

# Backend module shared with the API container (DB + providers)
COPY backend/db        /app/db
COPY backend/providers /app/providers

# Scheduler scripts
COPY scheduler/get_time_salat.py /app/get_time_salat.py
COPY scheduler/load_config.py    /app/load_config.py
COPY scheduler/get_homepods.py   /app/get_homepods.py
COPY scheduler/adhan.sh          /app/adhan.sh
RUN chmod +x /app/adhan.sh

# Cron
COPY scheduler/salat.crontab /etc/cron.d/salat
RUN touch /var/log/cron.log

# Entrypoint
COPY scheduler/startup.sh /opt/startup.sh
RUN chmod +x /opt/startup.sh
CMD ["/opt/startup.sh"]
