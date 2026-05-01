"""On-time tracker — consecutive prayers logged within their adhan window.

Total: every prayer ever logged with on_time=true.
Combo: consecutive on-time prayers walking back through the daily sequence
       (Fajr → Dhuhr → Asr → Maghrib → Isha → next day Fajr…). Breaks if
       any preceding slot is missing OR was logged late."""
from typing import Optional

from .base import ALL_PRAYERS, Tracker, TrackerResult, prayer_order
from .salat import _previous_slot


class OnTimeTracker(Tracker):
    id = "on_time"

    def evaluate(self, log: dict, history: list[dict]) -> Optional[TrackerResult]:
        if not log.get("on_time"):
            return None
        total = sum(1 for h in history if h.get("on_time"))
        # Map each (date, prayer) to its on_time flag for backward walking.
        by_slot = {(h["date"], h["prayer"]): bool(h.get("on_time")) for h in history}
        combo = 0
        cur = (log["date"], log["prayer"])
        while cur in by_slot and by_slot[cur]:
            combo += 1
            prev = _previous_slot(*cur)
            if prev is None:
                break
            cur = prev
        return TrackerResult(total=total, combo=combo)
