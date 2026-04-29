"""Factory: pick the AudioProvider implementation based on `AUDIO_PROVIDER` env.

Defaulting to 'owntone' for now keeps the current behavior while we add more
providers; the default flips to 'music-assistant' once that adapter ships.
"""
import os

from .base import AudioProvider


def get_provider() -> AudioProvider:
    name = os.environ.get("AUDIO_PROVIDER", "owntone").lower()
    if name == "owntone":
        from .owntone import OwnToneProvider

        return OwnToneProvider()
    if name == "music-assistant":
        # Imported lazily so OwnTone-only deployments don't pay the dep cost.
        from .music_assistant import MusicAssistantProvider

        return MusicAssistantProvider()
    raise ValueError(
        f"Unknown AUDIO_PROVIDER={name!r}. Use 'owntone' or 'music-assistant'."
    )
