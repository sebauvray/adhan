"""Audio provider abstraction.

The Adhan Home API only knows about *what* it needs (list speakers, play an
announcement on some of them at a given volume, stop). Each provider
(OwnTone, Music Assistant, …) implements the AudioProvider interface, so
swapping providers is one env var (`AUDIO_PROVIDER`) — no business code change.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class Speaker:
    """A speaker exposed by the provider (HomePod, Sonos, Chromecast, …)."""

    id: str
    name: str
    type: str  # 'airplay' | 'sonos' | 'chromecast' | 'other'


class AudioProviderError(Exception):
    """Base class for provider failures."""


class AudioProviderUnreachable(AudioProviderError):
    """The provider's HTTP API is not responding."""


class AudioFileNotFound(AudioProviderError):
    """The configured audio file isn't accessible to the provider."""


class SpeakerNotFound(AudioProviderError):
    """None of the requested speakers were found in the provider."""


class AudioProvider(ABC):
    """Interface every audio provider must implement.

    Concrete providers: OwnToneProvider, MusicAssistantProvider, ...
    """

    name: str = "unknown"

    @abstractmethod
    def list_speakers(self) -> list[Speaker]:
        """Return the speakers currently exposed by the provider."""

    @abstractmethod
    def play_announcement(self, kind: str, speaker_names: list[str], volume: int) -> None:
        """Play the audio file for `kind` ('adhan' | 'alert') on the named speakers
        at the given volume (0-100). Raises AudioProviderError on failure."""

    @abstractmethod
    def stop(self) -> None:
        """Stop any current playback."""

    @abstractmethod
    def health_check(self) -> bool:
        """Return True if the provider is reachable, False otherwise."""
