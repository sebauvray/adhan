"""Tracker base contract.

A `Tracker` reads the user's full prayer history and decides what the new
log triggers for *its* dimension (salat count, group count, fire streak,
perfect day streak). It only knows about its own rule — the orchestrator
in `registry.evaluate_for_log` handles persistence and "streak broken"
detection.
"""
from dataclasses import dataclass
from typing import Optional


ALL_PRAYERS = ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]


def prayer_order(prayer: str) -> int:
    """Position of a prayer in the daily sequence (0..4). Returns -1 if unknown."""
    try:
        return ALL_PRAYERS.index(prayer)
    except ValueError:
        return -1


@dataclass(frozen=True)
class TrackerResult:
    """What a tracker computed for a brand new log.

    `total` and `combo` are the absolute new values (not deltas) — derived
    from the user's full history so backlog logs naturally re-build the
    streak instead of just "+1 from last value".
    """
    total: int
    combo: int


@dataclass(frozen=True)
class TrackerEvent:
    """Frontend-facing event emitted for one tracker reacting to one log.

    `action` is what the UI should play:
      - "increment" → COMBO x{combo} {label}!
      - "broken"    → sad reset label (e.g. FEU ÉTEINT), combo dropped to 1
    """
    tracker_id: str
    action: str  # "increment" | "broken"
    total: int
    combo: int


class Tracker:
    """Abstract tracker. Each subclass overrides `evaluate()` and sets `id`."""

    id: str = ""

    def evaluate(self, log: dict, history: list[dict]) -> Optional[TrackerResult]:
        """Compute new total + combo for this tracker after `log` was inserted.

        `log`     — the brand new prayer_logs row (dict with keys: user_id,
                    prayer, date, on_time, in_group)
        `history` — full prayer_logs for this user, *including* the new log,
                    sorted by (date asc, prayer order asc)

        Return None if this tracker does NOT trigger for this log
        (e.g. group tracker on a non-group log, fire tracker on an
        incomplete day, etc.)."""
        raise NotImplementedError
