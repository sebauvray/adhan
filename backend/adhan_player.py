"""Apply prayer business rules (configured speakers, per-prayer volume, quiet
hours) and delegate the actual playback to whichever AudioProvider is selected
by the AUDIO_PROVIDER env var.

Importable from the scheduler process (APScheduler) and runnable as a CLI for
manual testing.
"""
import logging
import os
import sys
from datetime import datetime
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db.schema import init_db
from db.config import (
    get_value,
    get_outputs_for_prayer,
    get_prayer_volume,
)
from audio import AudioProviderError, get_provider

LEVELS = {"DEBUG": logging.DEBUG, "INFO": logging.INFO, "WARN": logging.WARNING, "ERROR": logging.ERROR}

logger = logging.getLogger("adhan_player")


def _configure_logging():
    level_name = get_value("config", "LOG_LEVEL", "INFO")
    level = LEVELS.get(level_name, logging.INFO)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s", "%d.%m.%Y - %H:%M:%S")
        )
        logger.addHandler(handler)
    logger.setLevel(level)


def _parse_hhmm(value: str) -> int:
    """'HH:MM' -> minutes since midnight."""
    h, m = value.split(":")
    return int(h) * 60 + int(m)


def _is_quiet_hours(now: datetime, quiet_start: str, quiet_end: str) -> bool:
    """Returns True if `now` falls inside the quiet window.

    Handles same-day windows (14:00-16:00) and overnight windows (21:00-07:00).
    """
    now_min = now.hour * 60 + now.minute
    qs = _parse_hhmm(quiet_start)
    qe = _parse_hhmm(quiet_end)
    if qs > qe:
        return now_min >= qs or now_min < qe
    return qs <= now_min < qe


def _apply_quiet_hours(volume: int, now: Optional[datetime] = None) -> int:
    """Cap volume to QUIET_VOLUME if `now` is in the configured quiet window."""
    quiet_start = get_value("config", "QUIET_START", "21:00")
    quiet_end = get_value("config", "QUIET_END", "07:00")
    quiet_volume = int(get_value("config", "QUIET_VOLUME", "10"))
    when = now or datetime.now()
    if _is_quiet_hours(when, quiet_start, quiet_end) and volume > quiet_volume:
        logger.info(
            f"Quiet hours active ({quiet_start}-{quiet_end}): volume capped from {volume} to {quiet_volume}"
        )
        return quiet_volume
    return volume


def play(prayer_name: str, mode: str = "adhan") -> bool:
    """Resolve the speakers and volume for `prayer_name`, then play `mode`
    ('adhan' | 'alert') through the configured AudioProvider.

    Returns True on success, False if any precondition failed (no speakers
    configured, provider unreachable, file missing, …). Errors are logged.
    """
    init_db()
    _configure_logging()

    if mode == "alert":
        logger.info(f"Iqama alert triggered for: {prayer_name}")
    else:
        logger.info(f"Adhan triggered for: {prayer_name}")

    speaker_names = get_outputs_for_prayer(prayer_name)
    if not speaker_names:
        logger.warning(f"No speakers configured for {prayer_name}")
        return False
    logger.debug(f"Speakers for {prayer_name}: {speaker_names}")

    base_volume = get_prayer_volume(prayer_name, int(get_value("owntone", "ADHAN_VOLUME", "40")))
    volume = _apply_quiet_hours(base_volume)
    logger.debug(f"Volume for {prayer_name}: {volume}")

    try:
        provider = get_provider()
        provider.play_announcement(mode, speaker_names, volume)
    except AudioProviderError as e:
        logger.error(f"Playback failed: {type(e).__name__}: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error during playback: {type(e).__name__}: {e}")
        return False

    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: adhan_player.py <prayer_name> [alert|adhan]", file=sys.stderr)
        sys.exit(1)
    prayer = sys.argv[1]
    play_mode = sys.argv[2] if len(sys.argv) > 2 else "adhan"
    ok = play(prayer, play_mode)
    sys.exit(0 if ok else 1)
