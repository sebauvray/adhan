"""Music Assistant audio provider.

Music Assistant exposes a REST API at http://<host>:<port>/api where every
request is a POST with body {message_id, command, args}, authenticated by
a Bearer token. We use:

  - players/all                       → list speakers
  - players/cmd/play_announcement     → fire-and-resume announcement
  - players/cmd/stop                  → stop a player

`play_announcement` takes a `url` field — MA fetches that URL and streams
it to the player. The URL points back to our own /api/audio/{kind}
endpoint, so we don't manage MA's local-files provider or pre-index anything.

Configuration lives in the SQLite `music_assistant` table (HOST, PORT, TOKEN),
written by the Setup wizard and Settings page through the provider manifest.
AUDIO_BASE_URL stays in env because it describes how MA reaches *us*, which
is an infrastructure concern, not user config.
"""
import logging
import os
import secrets

import requests

from db.config import get_value

from .base import (
    AudioFileNotFound,
    AudioProvider,
    AudioProviderUnreachable,
    MusicAssistantAlreadyConfigured,
    Speaker,
    SpeakerNotFound,
)
from .manifest import ConfigField, ProviderManifest, SetupMode

logger = logging.getLogger("audio.music_assistant")

DEFAULT_TIMEOUT = 10


MANIFEST = ProviderManifest(
    id="music-assistant",
    label="Music Assistant",
    icon="🎶",
    description="Découverte automatique AirPlay/Sonos/Cast. Plus moderne, plus de protocoles.",
    setup_modes=(
        SetupMode(
            id="bundled",
            label="Installation simple",
            description="On installe Music Assistant pour toi (recommandé)",
            icon="🚀",
        ),
        SetupMode(
            id="external",
            label="J'ai déjà Music Assistant",
            description="Connexion à un serveur existant",
            icon="⚙️",
        ),
    ),
    fields=(
        ConfigField(
            key="host",
            label="Adresse Music Assistant",
            type="text",
            default="host.docker.internal",
            placeholder="host.docker.internal",
            mode_visibility=("external",),
            required=True,
            storage_table="music_assistant",
            storage_key="HOST",
        ),
        ConfigField(
            key="port",
            label="Port",
            type="number",
            default="8095",
            placeholder="8095",
            mode_visibility=("external",),
            required=True,
            storage_table="music_assistant",
            storage_key="PORT",
        ),
        ConfigField(
            key="token",
            label="Token API",
            type="password",
            placeholder="eyJhbGc...",
            help="À créer dans la WebUI de Music Assistant (Settings → Security → API tokens).",
            required=True,
            mode_visibility=("external",),
            storage_table="music_assistant",
            storage_key="TOKEN",
        ),
    ),
)


class MusicAssistantClient:
    """Stateless wrapper around the MA REST API. One method per concern,
    so the provider stays declarative."""

    def __init__(self, host: str, port: str, token: str, timeout: int = DEFAULT_TIMEOUT):
        self.endpoint = f"http://{host}:{port}/api"
        self.token = token
        self.timeout = timeout

    def call(self, command: str, args: dict | None = None):
        """POST a command to MA. Returns the `result` field, or raises requests.RequestException."""
        body = {
            "message_id": secrets.token_hex(8),
            "command": command,
            "args": args or {},
        }
        resp = requests.post(
            self.endpoint,
            json=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.token}",
            },
            timeout=self.timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, dict) and "error" in data:
            raise requests.RequestException(f"MA error: {data['error']}")
        return data.get("result", data) if isinstance(data, dict) else data


def _normalize_type(provider: str) -> str:
    """Map MA provider instance ids ('airplay', 'sonos', 'chromecast', …) to
    our normalized speaker types."""
    p = (provider or "").lower()
    if "airplay" in p:
        return "airplay"
    if "sonos" in p:
        return "sonos"
    if "cast" in p:
        return "chromecast"
    if "snapcast" in p:
        return "snapcast"
    return "other"


class MusicAssistantProvider(AudioProvider):
    name = "music-assistant"
    manifest = MANIFEST

    def _client(self) -> MusicAssistantClient:
        host = get_value("music_assistant", "HOST", "host.docker.internal")
        port = get_value("music_assistant", "PORT", "8095")
        token = get_value("music_assistant", "TOKEN", "")
        if not token:
            raise AudioProviderUnreachable(
                "Token Music Assistant absent. Renseigne-le dans les paramètres."
            )
        return MusicAssistantClient(host, port, token)

    def _audio_url_for(self, kind: str) -> str:
        """Build the URL MA will GET to fetch the announcement audio."""
        base = os.environ.get("AUDIO_BASE_URL", "http://host.docker.internal:8001").rstrip("/")
        return f"{base}/api/audio/{kind}"

    def list_speakers(self) -> list[Speaker]:
        try:
            players = self._client().call("players/all")
        except requests.RequestException as e:
            raise AudioProviderUnreachable(str(e)) from e
        if not isinstance(players, list):
            return []
        return [
            Speaker(
                id=p["player_id"],
                name=p.get("display_name") or p.get("name", p["player_id"]),
                type=_normalize_type(p.get("provider", "")),
            )
            for p in players
            if p.get("available", True)
        ]

    def play_announcement(self, kind: str, speaker_names: list[str], volume: int) -> None:
        if kind not in ("adhan", "alert"):
            raise ValueError(f"Unknown announcement kind: {kind}")

        url = self._audio_url_for(kind)
        speakers = self.list_speakers()
        by_name = {s.name: s.id for s in speakers}
        player_ids = [by_name[n] for n in speaker_names if n in by_name]
        if not player_ids:
            raise SpeakerNotFound(f"None of {speaker_names} matched MA players")

        client = self._client()
        try:
            for pid in player_ids:
                client.call(
                    "players/cmd/play_announcement",
                    {"player_id": pid, "url": url, "volume_level": volume},
                )
        except requests.RequestException as e:
            msg = str(e).lower()
            if "404" in msg or "not found" in msg:
                raise AudioFileNotFound(f"MA could not fetch {url}") from e
            raise AudioProviderUnreachable(f"MA HTTP error: {e}") from e

        logger.info(f"MA announcement: {kind} on {speaker_names} (volume={volume})")

    def stop(self) -> None:
        try:
            speakers = self.list_speakers()
            client = self._client()
            for s in speakers:
                try:
                    client.call("players/cmd/stop", {"player_id": s.id})
                except requests.RequestException:
                    logger.warning(f"Failed to stop MA player {s.name}")
        except AudioProviderUnreachable:
            raise
        except requests.RequestException as e:
            raise AudioProviderUnreachable(str(e)) from e

    def health_check(self) -> bool:
        try:
            self._client().call("players/all")
            return True
        except (requests.RequestException, AudioProviderUnreachable):
            return False


def _looks_already_onboarded(resp: "requests.Response", data: dict) -> bool:
    """True when MA's /setup refuses because an admin account already exists.

    MA replies 4xx with a message like "Setup already completed" — we match on
    that intent rather than the precise wording so a future rephrase doesn't
    silently turn the reuse path back into a hard failure."""
    msg = (data.get("error") or resp.text or "").lower()
    return "already" in msg or "exists" in msg or resp.status_code == 409


def bootstrap_music_assistant(
    username: str,
    password: str,
    host: str | None = None,
    port: str | None = None,
    device_name: str = "Adhan Home",
) -> str:
    """Make sure a usable MA admin token exists, onboarding or reusing as needed.

    Two paths, decided by how MA's `POST /setup` answers:
      - *fresh instance* → /setup creates the admin and returns a token.
      - *already onboarded* (e.g. a previous install left its `ma-data` volume)
        → we log in with the same credentials and mint a long-lived token.

    We deliberately don't pre-check `/info` for an onboarding flag: MA exposes
    `onboard_done` (provider/player setup finished) which is *not* the same as
    "an admin exists", so reading it picked the wrong branch. Letting /setup
    itself tell us is unambiguous.

    Raises `MusicAssistantAlreadyConfigured` when MA already has an admin but
    the supplied credentials don't unlock it — the caller surfaces a "start
    fresh" choice. The returned token must be persisted by the caller (into the
    SQLite `music_assistant.TOKEN` row) so the user is never asked for it.
    """
    base = f"http://{host or get_value('music_assistant', 'HOST', 'host.docker.internal')}:" \
           f"{port or get_value('music_assistant', 'PORT', '8095')}"

    try:
        resp = requests.post(
            f"{base}/setup",
            json={"username": username, "password": password, "device_name": device_name},
            timeout=15,
        )
    except requests.RequestException as e:
        raise AudioProviderUnreachable(f"MA injoignable : {e}") from e

    data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}

    if resp.ok and data.get("success"):
        token = data.get("token") or ""
        if not token:
            raise AudioProviderUnreachable("MA /setup n'a pas renvoyé de token")
        return token

    if not _looks_already_onboarded(resp, data):
        raise AudioProviderUnreachable(data.get("error") or f"MA /setup HTTP {resp.status_code}")

    # Already onboarded — reuse it by logging in with the same credentials.
    return _login_long_lived_token(base, username, password, device_name)


def _login_long_lived_token(base: str, username: str, password: str, device_name: str) -> str:
    """Log into an already-onboarded MA and return a long-lived token.

    Uses the official `music_assistant_client` helper, which logs in over HTTP
    then opens MA's WebSocket to create a persistent token (a plain login only
    yields a short-lived session token, useless for a daemon that fires for
    years). Raises `MusicAssistantAlreadyConfigured` when the credentials don't
    match the existing admin."""
    import asyncio

    try:
        from music_assistant_client import login_with_token
    except ImportError as e:  # pragma: no cover - dependency must be installed in the image
        raise AudioProviderUnreachable(
            "music-assistant-client manquant : impossible de réutiliser l'installation existante."
        ) from e

    try:
        _user, token = asyncio.run(
            login_with_token(base, username, password, token_name=device_name)
        )
    except Exception as e:
        # We already reached /setup, so MA is up — a failure here is the
        # credentials not matching the existing admin, not a network issue.
        raise MusicAssistantAlreadyConfigured(
            "Music Assistant a déjà un compte admin, mais ces identifiants ne correspondent pas. "
            "Repars de zéro pour le réinstaller."
        ) from e

    if not token:
        raise AudioProviderUnreachable("MA login n'a pas renvoyé de token")
    return token
