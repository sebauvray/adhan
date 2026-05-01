"""Perfect-day tracker — consecutive days that are 5/5 AND all on time.

Backlog logs are forced `on_time = false`, so no amount of catch-up can
fake a perfect day after the fact. The strictest tracker."""
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Optional

from .base import Tracker, TrackerResult


def _perfect_dates(history: list[dict]) -> set[str]:
    by_date: dict[str, list[dict]] = defaultdict(list)
    for h in history:
        by_date[h["date"]].append(h)
    perfect = set()
    for d, logs in by_date.items():
        prayers = {l["prayer"] for l in logs}
        if len(prayers) >= 5 and all(l.get("on_time") for l in logs):
            perfect.add(d)
    return perfect


def _streak_back_from(date_str: str, perfect: set[str]) -> int:
    try:
        cur = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return 0
    combo = 0
    while cur.isoformat() in perfect:
        combo += 1
        cur -= timedelta(days=1)
    return combo


class PerfectDayTracker(Tracker):
    id = "perfect_day"

    def evaluate(self, log: dict, history: list[dict]) -> Optional[TrackerResult]:
        if not log.get("on_time"):
            return None
        date = log["date"]
        logs_for_date = [h for h in history if h["date"] == date]
        prayers_for_date = {l["prayer"] for l in logs_for_date}
        if len(prayers_for_date) < 5:
            return None
        if not all(l.get("on_time") for l in logs_for_date):
            return None
        perfect = _perfect_dates(history)
        if date not in perfect:
            return None
        return TrackerResult(total=len(perfect), combo=_streak_back_from(date, perfect))
