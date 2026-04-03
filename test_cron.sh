#!/bin/bash
# Test cron: reprogramme Asr dans 2 minutes et surveille le log

CONTAINER="adhan-home"
CRON_FILE="/etc/cron.d/salat"

# Heure cible = maintenant + 2 min
TARGET=$(docker exec "$CONTAINER" date -d "+2 minutes" "+%M %H")
MIN=$(echo "$TARGET" | awk '{print $1}')
HOUR=$(echo "$TARGET" | awk '{print $2}')

echo "==> Reprogrammation de Asr à ${HOUR}:${MIN} (dans ~2 min)"

# Remplacer la ligne Asr dans le crontab
docker exec "$CONTAINER" sed -i "s|^[0-9]* [0-9]* \* \* \* root bash /app/adhan.sh Asr|${MIN} ${HOUR} * * * root bash /app/adhan.sh Asr|" "$CRON_FILE"

# Vérifier
echo "==> Crontab actuel :"
docker exec "$CONTAINER" cat "$CRON_FILE"

# Vider le log
docker exec "$CONTAINER" truncate -s 0 /var/log/cron.log

echo ""
echo "==> Surveillance du log (Ctrl+C pour arrêter)..."
docker exec "$CONTAINER" tail -f /var/log/cron.log
