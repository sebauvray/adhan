"""Orchestrator: runs every tracker against a new log, persists the
new state, and produces frontend events.

Adding a new tracker = appending one entry in `TRACKERS`."""
from typing import Iterable

from db.config import (
    fetch_user_history,
    get_tracker_state,
    update_tracker_state,
)

from .base import Tracker, TrackerEvent
from .fire import FireTracker
from .group import GroupTracker
from .perfect_day import PerfectDayTracker
from .salat import SalatTracker


TRACKERS: tuple[Tracker, ...] = (
    SalatTracker(),
    GroupTracker(),
    FireTracker(),
    PerfectDayTracker(),
)


def evaluate_for_log(user_id: int, log: dict) -> list[TrackerEvent]:
    """Run every tracker for one freshly-inserted log. Persist new state.
    Return the events to play in the UI, in display order
    (group → salat → fire → perfect_day = least-rare to most-rare climax)."""
    history = fetch_user_history(user_id)
    raw: dict[str, tuple] = {}
    for tracker in TRACKERS:
        result = tracker.evaluate(log, history)
        if result is None:
            continue
        prior = get_tracker_state(user_id, tracker.id)
        broken = prior["current_combo"] > 1 and result.combo == 1
        new_best = max(prior["best_combo"], result.combo)
        update_tracker_state(
            user_id,
            tracker.id,
            total=result.total,
            current_combo=result.combo,
            best_combo=new_best,
        )
        raw[tracker.id] = (broken, result.total, result.combo)

    # Climax order: group, salat, fire, perfect_day. Skipped trackers absent.
    events: list[TrackerEvent] = []
    for tid in ("group", "salat", "fire", "perfect_day"):
        if tid not in raw:
            continue
        broken, total, combo = raw[tid]
        if broken:
            events.append(TrackerEvent(tracker_id=tid, action="broken", total=total, combo=0))
        events.append(TrackerEvent(tracker_id=tid, action="increment", total=total, combo=combo))
    return events


def evaluate_batch(user_logs: Iterable[tuple[int, dict]]) -> list[dict]:
    """Run trackers for a list of (user_id, log) — typically the freshly
    inserted logs of a multi-user batch. Returns one entry per user with
    their events."""
    grouped: dict[int, list[TrackerEvent]] = {}
    for user_id, log in user_logs:
        for ev in evaluate_for_log(user_id, log):
            grouped.setdefault(user_id, []).append(ev)
    return [
        {
            "user_id": uid,
            "events": [ev.__dict__ for ev in evs],
        }
        for uid, evs in grouped.items()
    ]
