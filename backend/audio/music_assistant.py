"""Music Assistant audio provider.

Music Assistant exposes a REST API at http://<host>:8095/api where every
request is a POST with body {message_id, command, args}, authenticated by
a Bearer token. We use:

  - players/all                       → list speakers
  - players/cmd/play_announcement     → fire-and-resume announcement
  - players/cmd/stop                  → stop a player

`play_announcement` takes a `url` field — MA fetches that URL and streams
it to the player. The URL points back to our own /api/audio/{kind}
endpoint (added in step 3.3), so we don't have to manage MA's local-files
provider or pre-index anything.

Configuration is read from env so no DB schema change is required to
plug MA in. Settings UI persistence lands in step 3.5.

  MA_HOST            host of the Music Assistant server (default localhost)
  MA_PORT            port (default 8095)
  MA_TOKEN           Bearer token (required — created in the MA WebUI)
  AUDIO_BASE_URL     URL where MA can reach our /api (default
                     http://host.docker.internal:8001 for Docker Desktop)
"""
import logging
import os
import secrets

import requests

from .base import (
    AudioFileNotFound,
    AudioProvider,
    AudioProviderUnreachable,
    Speaker,
    SpeakerNotFound,
)

logger = logging.getLogger("audio.music_assistant")

DEFAULT_TIMEOUT = 10


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
        # Some commands return data directly (list of players), others wrap in {result}
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

    def _client(self) -> MusicAssistantClient:
        host = os.environ.get("MA_HOST", "localhost")
        port = os.environ.get("MA_PORT", "8095")
        token = os.environ.get("MA_TOKEN", "")
        if not token:
            raise AudioProviderUnreachable(
                "MA_TOKEN env var not set. Generate a token in the Music Assistant WebUI "
                "and pass it via docker-compose."
            )
        return MusicAssistantClient(host, port, token)

    def _audio_url_for(self, kind: str) -> str:
        """Build the URL MA will GET to fetch the announcement audio.
        Default targets the api container as seen from MA's network (host mode):
        http://host.docker.internal:8001/api/audio/{kind}."""
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

        # Resolve human names → MA player_ids (the configured prayer outputs are
        # stored by name so they survive provider restarts that re-issue ids).
        speakers = self.list_speakers()
        by_name = {s.name: s.id for s in speakers}
        player_ids = [by_name[n] for n in speaker_names if n in by_name]
        if not player_ids:
            raise SpeakerNotFound(f"None of {speaker_names} matched MA players")

        client = self._client()
        try:
            # play_announcement is per-player in MA — fire one call each.
            # MA itself takes care of saving/restoring whatever was playing.
            for pid in player_ids:
                client.call(
                    "players/cmd/play_announcement",
                    {"player_id": pid, "url": url, "volume_level": volume},
                )
        except requests.RequestException as e:
            # Catch the typical "audio file unreachable" symptom early.
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
                # Best-effort: if one player fails, keep stopping the others.
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
