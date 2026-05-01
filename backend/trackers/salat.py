"""Salat tracker — the most basic counter.

Total: every prayer ever logged.
Combo: consecutive prayers without missing one in the daily sequence
       (Fajr → Dhuhr → Asr → Maghrib → Isha → next day Fajr → …).
       Breaks the moment any slot is missed."""
from datetime import datetime, timedelta
from typing import Optional

from .base import ALL_PRAYERS, Tracker, TrackerResult, prayer_order


def _previous_slot(date_str: str, prayer: str) -> Optional[tuple[str, str]]:
    idx = prayer_order(prayer)
    if idx < 0:
        return None
    if idx > 0:
        return (date_str, ALL_PRAYERS[idx - 1])
    try:
        prev_day = (datetime.strptime(date_str, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
    except ValueError:
        return None
    return (prev_day, ALL_PRAYERS[-1])


class SalatTracker(Tracker):
    id = "salat"

    def evaluate(self, log: dict, history: list[dict]) -> Optional[TrackerResult]:
        total = len(history)
        logged = {(h["date"], h["prayer"]) for h in history}
        combo = 0
        cur = (log["date"], log["prayer"])
        while cur in logged:
            combo += 1
            prev = _previous_slot(*cur)
            if prev is None:
                break
            cur = prev
        return TrackerResult(total=total, combo=combo)
