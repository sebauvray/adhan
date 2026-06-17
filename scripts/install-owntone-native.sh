#!/usr/bin/env bash
#
# install-owntone-native.sh — Install OwnTone natively on macOS for Adhan Home.
#
# Why native (not the bundled Docker container): on macOS, Docker/OrbStack runs
# containers inside a Linux VM with its own private IP (e.g. 192.168.139.x).
# AirPlay 2 to HomePods needs a bidirectional RTP/timing channel, so the HomePod
# must be able to reach the sender back — impossible from the VM IP. OwnTone must
# therefore run on the Mac host directly to stream from the real LAN IP.
#
# There is no Homebrew formula for OwnTone, so we build it from source (same steps
# as the project's official macOS CI), install it user-local (no sudo), and register
# a LaunchAgent so it starts at login and restarts on crash.
#
# Idempotent: re-running skips already-built artifacts. Pass --service-only to just
# (re)load the LaunchAgent without touching the build (used by `make up`).
set -euo pipefail

MODE="install"
case "${1:-}" in
  --service-only) MODE="service" ;;
  --uninstall)    MODE="uninstall" ;;
esac

# --- Paths (user-local install, no sudo) ---
PREFIX="$HOME/owntone_data/usr"
CONF_DIR="$HOME/owntone_data/etc"
CONF="$CONF_DIR/owntone.conf"
BIN="$PREFIX/sbin/owntone"
SRC_OWNTONE="$HOME/owntone-server"
SRC_INOTIFY="$HOME/libinotify-kqueue"
MEDIA_DIR="${OWNTONE_MEDIA_DIR:-$HOME/Music/OwnTone}"
LABEL="com.adhanhome.owntone"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

log() { printf '\033[36m→ %s\033[0m\n' "$1"; }
die() { printf '\033[31m✗ %s\033[0m\n' "$1" >&2; exit 1; }

[ "$(uname -s)" = "Darwin" ] || die "L'install native d'OwnTone est réservée à macOS."

# ---------------------------------------------------------------------------
# Service-only fast path: (re)load the LaunchAgent and exit.
# ---------------------------------------------------------------------------
install_service() {
  [ -x "$BIN" ] || die "Binaire OwnTone introuvable ($BIN). Lance d'abord l'install complète."
  mkdir -p "$(dirname "$PLIST")"
  cat > "$PLIST" <<PLISTEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$LABEL</string>
    <key>ProgramArguments</key>
    <array>
        <string>$BIN</string>
        <string>-f</string>
        <string>-c</string>
        <string>$CONF</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$HOME/owntone_data/var/log/owntone.console.log</string>
    <key>StandardErrorPath</key>
    <string>$HOME/owntone_data/var/log/owntone.console.log</string>
</dict>
</plist>
PLISTEOF

  local domain="gui/$(id -u)"
  # Reload cleanly (bootout may fail if not loaded — that's fine).
  launchctl bootout "$domain/$LABEL" 2>/dev/null || true
  launchctl bootstrap "$domain" "$PLIST" 2>/dev/null \
    || launchctl load "$PLIST" 2>/dev/null \
    || die "Échec du chargement du service launchd."
  launchctl kickstart -k "$domain/$LABEL" 2>/dev/null || true
  log "Service launchd '$LABEL' chargé (démarrage auto au login, relance sur crash)."
}

# ---------------------------------------------------------------------------
# Uninstall: stop the service and remove build/config/db. Keeps the media
# library (it's the user's personal music) and the Homebrew deps (shared).
# ---------------------------------------------------------------------------
uninstall_owntone() {
  launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
  rm -f "$PLIST"
  pkill -f "owntone_data/usr/sbin/owntone" 2>/dev/null || true
  rm -rf "$HOME/owntone_data" "$SRC_OWNTONE" "$SRC_INOTIFY"
  log "OwnTone natif désinstallé (service, build, config, base)."
  log "Conservé : bibliothèque média $MEDIA_DIR (ta musique perso) et les paquets Homebrew."
}

if [ "$MODE" = "service" ]; then
  install_service
  exit 0
fi

if [ "$MODE" = "uninstall" ]; then
  uninstall_owntone
  exit 0
fi

# ---------------------------------------------------------------------------
# Full install.
# ---------------------------------------------------------------------------
command -v brew >/dev/null 2>&1 || die "Homebrew requis. Installe-le : https://brew.sh"
BP="$(brew --prefix)"
export HOMEBREW_NO_AUTO_UPDATE=1 HOMEBREW_NO_ENV_HINTS=1
export MACOSX_DEPLOYMENT_TARGET="$(sw_vers -productVersion)"

# 1) Build dependencies (idempotent — brew install is a no-op if already present).
log "Installation des dépendances Homebrew (peut être long la 1re fois)…"
brew install automake autoconf libtool pkg-config gettext gperf bison flex \
  libunistring confuse libplist libwebsockets libevent libgcrypt json-c \
  protobuf-c libsodium gnutls openssl ffmpeg sqlite

# Keg-only tools must be on PATH (macOS ships ancient bison/flex).
export PATH="$BP/opt/bison/bin:$BP/opt/flex/bin:$BP/opt/gettext/bin:$PATH"

# 2) libinotify-kqueue (macOS shim for Linux inotify — OwnTone hard-requires it).
#    Its -Werror trips on a macOS-26 availability warning, so we disable it.
if [ ! -f "$PREFIX/lib/libinotify.dylib" ]; then
  log "Compilation de libinotify-kqueue…"
  rm -rf "$SRC_INOTIFY"
  git clone --depth 1 https://github.com/libinotify-kqueue/libinotify-kqueue "$SRC_INOTIFY"
  cd "$SRC_INOTIFY"
  autoreconf -fvi
  ./configure --prefix="$PREFIX" CFLAGS="-g -O2 -Wno-error -Wno-unguarded-availability-new"
  make -j"$(sysctl -n hw.ncpu)"
  make install
else
  log "libinotify-kqueue déjà compilé — on saute."
fi

# 3) OwnTone server itself.
if [ ! -x "$BIN" ]; then
  log "Compilation d'OwnTone (quelques minutes)…"
  rm -rf "$SRC_OWNTONE"
  git clone --depth 1 https://github.com/owntone/owntone-server.git "$SRC_OWNTONE"
  cd "$SRC_OWNTONE"
  export ACLOCAL_PATH="$BP/share/gettext/m4:${ACLOCAL_PATH:-}"
  export CFLAGS="-I$PREFIX/include -I$BP/include -I$(brew --prefix sqlite)/include -I$BP/opt/flex/include -Wno-error"
  export LDFLAGS="-L$PREFIX/lib -L$BP/lib -L$(brew --prefix sqlite)/lib -L$BP/opt/flex/lib"
  export PKG_CONFIG_PATH="$(brew --prefix sqlite)/lib/pkgconfig:$(brew --prefix openssl)/lib/pkgconfig:$BP/lib/pkgconfig"
  export INOTIFY_CFLAGS="-I$PREFIX/include"
  export INOTIFY_LIBS="-L$PREFIX/lib -linotify"
  autoreconf -fi
  ./configure --prefix="$PREFIX" --sysconfdir="$CONF_DIR" --localstatedir="$HOME/owntone_data/var"
  make -j"$(sysctl -n hw.ncpu)"
  make install
else
  log "OwnTone déjà compilé — on saute."
fi

# 4) Media library directory (user's personal music + adhan/alert files).
mkdir -p "$MEDIA_DIR"
log "Bibliothèque média : $MEDIA_DIR"

# 5) Patch the config — only when still at install defaults, to preserve user edits.
[ -f "$CONF" ] || die "Config OwnTone introuvable ($CONF) après build."
if grep -q 'uid = "owntone"' "$CONF"; then
  sed -i '' -E "s|^([[:space:]]*uid[[:space:]]*=).*|\1 \"$(id -un)\"|" "$CONF"
  log "Config: uid → $(id -un)"
fi
if grep -q '/srv/music' "$CONF"; then
  sed -i '' -E "s|^([[:space:]]*directories[[:space:]]*=).*|\1 { \"$MEDIA_DIR\" }|" "$CONF"
  log "Config: directories → $MEDIA_DIR"
fi

# 6) Register and start the LaunchAgent.
install_service

log "OwnTone natif installé. Interface : http://localhost:3689"
