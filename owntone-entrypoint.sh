#!/bin/sh
# Fix volume permissions before starting OwnTone
OWNTONE_UID="${UID:-1000}"
OWNTONE_GID="${GID:-1000}"

echo "[entrypoint] Fixing permissions for UID=$OWNTONE_UID GID=$OWNTONE_GID"
chown -R "$OWNTONE_UID:$OWNTONE_GID" /etc/owntone /srv/media /var/cache/owntone

# Start OwnTone via the default init system
exec /sbin/init
