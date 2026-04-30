"""Provider manifests — the declarative contract each adapter must publish.

Hexagonal-architecture twin of the runtime port (`AudioProvider`):
the runtime port says *what the app calls*; the manifest says *what
the UI needs to render to configure that adapter*. The frontend reads
manifests from `GET /api/audio/providers` and renders the wizard +
Settings dynamically — adding Chromecast/Alexa later means shipping
a new adapter + manifest, no UI change.
"""
from dataclasses import asdict, dataclass, field
from typing import Literal


FieldType = Literal["text", "password", "number", "url"]


@dataclass(frozen=True)
class ConfigField:
    """A single piece of configuration the provider needs from the user.

    `storage_table` / `storage_key` describe where the value is persisted
    in SQLite, so the manifest is the only place that knows the mapping
    between the UI field and its row in the DB.

    `mode_visibility` lets a field appear only for some setup modes
    (e.g. host/port make sense in "external" mode but not in "bundled").
    Empty tuple = always visible.
    """

    key: str
    label: str
    type: FieldType = "text"
    default: str = ""
    placeholder: str = ""
    help: str = ""
    required: bool = False
    mode_visibility: tuple[str, ...] = ()
    storage_table: str = "config"
    storage_key: str = ""

    def resolved_storage_key(self) -> str:
        return self.storage_key or self.key.upper()


@dataclass(frozen=True)
class SetupMode:
    """How the provider can be deployed: bundled inside our compose stack,
    or as an external service the user already runs."""

    id: str
    label: str
    description: str
    icon: str = ""


@dataclass(frozen=True)
class ProviderManifest:
    """Everything the UI needs to know about a provider, without ever
    referencing it by name."""

    id: str
    label: str
    icon: str
    description: str
    setup_modes: tuple[SetupMode, ...] = field(default_factory=tuple)
    fields: tuple[ConfigField, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict:
        """JSON-serializable form for the API."""
        return asdict(self)
