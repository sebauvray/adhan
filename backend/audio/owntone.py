"""OwnTone audio provider.

Wraps the OwnTone REST API behind the AudioProvider interface so the rest of
the codebase doesn't know which speaker stack is in use. Reads its host/port
and the adhan/alert file paths from the SQLite `owntone` table.
"""
import logging
from typing import Optional

import requests

from db.config import get_value

from .base import (
    AudioFileNotFound,
    AudioProvider,
    AudioProviderUnreachable,
    Speaker,
    SpeakerNotFound,
)
from .manifest import ConfigField, ProviderManifest, SetupMode

logger = logging.getLogger("audio.owntone")


MANIFEST = ProviderManifest(
    id="owntone",
    label="OwnTone",
    icon="🎵",
    description="Lecteur AirPlay open source. Idéal pour HomePods et Apple TV.",
    setup_modes=(
        SetupMode(
            id="bundled",
            label="Installation simple",
            description="On installe OwnTone pour toi (recommandé)",
            icon="🚀",
        ),
        SetupMode(
            id="external",
            label="J'ai déjà OwnTone",
            description="Connexion à un serveur existant",
            icon="⚙️",
        ),
    ),
    fields=(
        ConfigField(
            key="host",
            label="Adresse OwnTone",
            type="text",
            default="host.docker.internal",
            placeholder="host.docker.internal",
            mode_visibility=("external",),
            required=True,
            storage_table="owntone",
            storage_key="HOST",
        ),
        ConfigField(
            key="port",
            label="Port",
            type="number",
            default="3689",
            placeholder="3689",
            mode_visibility=("external",),
            required=True,
            storage_table="owntone",
            storage_key="PORT",
        ),
    ),
)


class OwnToneClient:
    """Thin HTTP wrapper around OwnTone's REST API. One method per OwnTone
    endpoint we use, so OwnToneProvider stays declarative."""

    def __init__(self, host: str, port: str, timeout: int = 5):
        self.base = f"http://{host}:{port}"
        self.timeout = timeout

    def list_outputs(self) -> list[dict]:
        resp = requests.get(f"{self.base}/api/outputs", timeout=self.timeout)
        resp.raise_for_status()
        return resp.json().get("outputs", [])

    def resolve_output_ids(self, names: list[str]) -> list[str]:
        outputs = self.list_outputs()
        by_name = {o["name"]: str(o["id"]) for o in outputs}
        ids: list[str] = []
        for name in names:
            oid = by_name.get(name)
            if oid:
                logger.debug(f"Output found: {name} -> {oid}")
                ids.append(oid)
            else:
                logger.warning(f"Output not found: {name}")
        return ids

    def set_volume(self, output_ids: list[str], volume: int) -> None:
        for oid in output_ids:
            requests.put(
                f"{self.base}/api/outputs/{oid}",
                json={"volume": volume},
                timeout=self.timeout,
            )

    def select_outputs(self, output_ids: list[str]) -> None:
        requests.put(
            f"{self.base}/api/outputs/set",
            json={"outputs": output_ids},
            timeout=self.timeout,
        )

    def resolve_track_uri(self, file_path: str) -> Optional[str]:
        resp = requests.get(
            f"{self.base}/api/search",
            params={"type": "tracks", "expression": f'path is "{file_path}"'},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        items = resp.json().get("tracks", {}).get("items", [])
        if not items:
            return None
        return f"library:track:{items[0]['id']}"

    def play(self, track_uri: str) -> None:
        requests.post(
            f"{self.base}/api/queue/items/add",
            params={"uris": track_uri, "clear": "true", "playback": "start"},
            timeout=self.timeout,
        )

    def stop(self) -> None:
        requests.put(f"{self.base}/api/player/stop", timeout=self.timeout)


class OwnToneProvider(AudioProvider):
    name = "owntone"
    manifest = MANIFEST

    def _client(self) -> OwnToneClient:
        # Re-read config every call so a Settings change takes effect immediately.
        host = get_value("owntone", "HOST", "host.docker.internal")
        port = get_value("owntone", "PORT", "3689")
        return OwnToneClient(host, port)

    def list_speakers(self) -> list[Speaker]:
        try:
            outputs = self._client().list_outputs()
        except requests.RequestException as e:
            raise AudioProviderUnreachable(str(e)) from e
        return [
            Speaker(id=str(o["id"]), name=o["name"], type=o.get("type", "airplay"))
            for o in outputs
        ]

    def play_announcement(self, kind: str, speaker_names: list[str], volume: int) -> None:
        if kind not in ("adhan", "alert"):
            raise ValueError(f"Unknown announcement kind: {kind}")

        key = "ADHAN_FILE" if kind == "adhan" else "ALERT_FILE"
        default = "/srv/media/adhan.mp3" if kind == "adhan" else "/srv/media/alert.mp3"
        file_path = get_value("owntone", key, default)
        if not file_path:
            raise AudioFileNotFound(f"No file path configured for {kind}")

        client = self._client()
        try:
            speaker_ids = client.resolve_output_ids(speaker_names)
            if not speaker_ids:
                raise SpeakerNotFound(f"None of {speaker_names} matched OwnTone outputs")

            track_uri = client.resolve_track_uri(file_path)
            if not track_uri:
                raise AudioFileNotFound(f"Track not found in OwnTone: {file_path}")

            client.set_volume(speaker_ids, volume)
            client.select_outputs(speaker_ids)
            client.play(track_uri)
        except requests.RequestException as e:
            raise AudioProviderUnreachable(f"OwnTone HTTP error: {e}") from e

        logger.info(f"OwnTone playback started: {kind} on {speaker_names} (volume={volume})")

    def stop(self) -> None:
        try:
            self._client().stop()
        except requests.RequestException as e:
            raise AudioProviderUnreachable(str(e)) from e

    def health_check(self) -> bool:
        try:
            self._client().list_outputs()
            return True
        except requests.RequestException:
            return False
