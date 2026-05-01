"""Fire tracker — consecutive days where ALL 5 prayers were logged.

Doesn't care about timing — a 5/5 day with everything backlogged still
counts. Only triggers when the new log is the one that pushes a date
from 4/5 to 5/5 (i.e. the day "closes")."""
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Optional

from .base import Tracker, TrackerResult


def _complete_dates(history: list[dict]) -> set[str]:
    by_date: dict[str, set[str]] = defaultdict(set)
    for h in history:
        by_date[h["date"]].add(h["prayer"])
    return {d for d, prayers in by_date.items() if len(prayers) >= 5}


def _streak_back_from(date_str: str, complete: set[str]) -> int:
    try:
        cur = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return 0
    combo = 0
    while cur.isoformat() in complete:
        combo += 1
        cur -= timedelta(days=1)
    return combo


class FireTracker(Tracker):
    id = "fire"

    def evaluate(self, log: dict, history: list[dict]) -> Optional[TrackerResult]:
        date = log["date"]
        prayers_for_date = {h["prayer"] for h in history if h["date"] == date}
        if len(prayers_for_date) < 5:
            return None
        complete = _complete_dates(history)
        if date not in complete:
            return None
        return TrackerResult(total=len(complete), combo=_streak_back_from(date, complete))
