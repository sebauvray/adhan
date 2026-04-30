"""Provider registry — single point of knowledge about which adapters exist.

Each entry pairs a runtime class (the AudioProvider implementation) with its
declarative manifest. The active provider id is read from the SQLite `config`
table so the wizard/Settings can switch providers at runtime — env vars are
no longer authoritative for this choice.

Adding a new adapter (Chromecast, Alexa, …) is one line in `_PROVIDERS`.
"""
from __future__ import annotations

from typing import Type

from db.config import get_value

from .base import AudioProvider
from .manifest import ProviderManifest
from .music_assistant import MusicAssistantProvider
from .owntone import OwnToneProvider


_PROVIDERS: dict[str, Type[AudioProvider]] = {
    OwnToneProvider.name: OwnToneProvider,
    MusicAssistantProvider.name: MusicAssistantProvider,
}


def list_manifests() -> list[ProviderManifest]:
    """All available providers — for the wizard/Settings UI."""
    return [cls.manifest for cls in _PROVIDERS.values()]


def get_manifest(provider_id: str) -> ProviderManifest | None:
    cls = _PROVIDERS.get(provider_id)
    return cls.manifest if cls else None


def active_provider_id() -> str:
    """Read the currently selected provider from the DB. Defaults to the
    first registered provider if nothing is set yet (fresh install)."""
    pid = get_value("config", "AUDIO_PROVIDER", "") or next(iter(_PROVIDERS), "owntone")
    return pid if pid in _PROVIDERS else next(iter(_PROVIDERS), "owntone")


def active_mode() -> str:
    """Bundled (we run the provider container) vs external (user-managed)."""
    return get_value("config", "AUDIO_PROVIDER_MODE", "bundled") or "bundled"


def get_provider() -> AudioProvider:
    """Instantiate the currently active provider."""
    pid = active_provider_id()
    cls = _PROVIDERS.get(pid)
    if not cls:
        raise ValueError(f"Unknown audio provider: {pid!r}")
    return cls()
