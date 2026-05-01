"""Tracker engine — turns each prayer log into a stream of events
(increment / reset) for downstream UI animations.

Each tracker is a tiny rule that reads the user's full prayer history
and decides what should happen for the new log. The orchestrator
(`evaluate_for_log`) runs every tracker, compares against the persisted
state, persists the new state, and produces the JSON events the frontend
will consume to play combo animations."""

from .base import Tracker, TrackerResult, TrackerEvent, ALL_PRAYERS, prayer_order
from .registry import TRACKERS, evaluate_for_log

__all__ = [
    "Tracker",
    "TrackerResult",
    "TrackerEvent",
    "ALL_PRAYERS",
    "prayer_order",
    "TRACKERS",
    "evaluate_for_log",
]
