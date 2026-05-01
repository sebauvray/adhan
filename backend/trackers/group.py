"""Group tracker — total in-group prayers, never resets.

The user explicitly asked that this one not require consecutiveness:
    "pas besoin de les avoir enchainees. on compte juste les prieres en groupe"
So combo == total. The animation still shows COMBO x{n} but the value
just keeps climbing — this is the "always-positive" tracker."""
from typing import Optional

from .base import Tracker, TrackerResult


class GroupTracker(Tracker):
    id = "group"

    def evaluate(self, log: dict, history: list[dict]) -> Optional[TrackerResult]:
        if not log.get("in_group"):
            return None
        total = sum(1 for h in history if h.get("in_group"))
        return TrackerResult(total=total, combo=total)
