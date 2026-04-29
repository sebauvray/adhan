"""Play adhan or iqama alert on OwnTone outputs configured for a prayer.

Replaces the bash adhan.sh + load_config.py + get_homepods.py trio.
Importable from the scheduler process (APScheduler), and runnable as a CLI for manual testing.
"""
import logging
import os
import sys
from datetime import datetime, time as dtime
from typing import Optional

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db.schema import init_db
from db.config import (
    get_value,
    get_outputs_for_prayer,
    get_prayer_volume,
)

LEVELS = {"DEBUG": logging.DEBUG, "INFO": logging.INFO, "WARN": logging.WARNING, "ERROR": logging.ERROR}

logger = logging.getLogger("adhan_player")


def _configure_logging():
    level_name = get_value("config", "LOG_LEVEL", "INFO")
    level = LEVELS.get(level_name, logging.INFO)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s", "%d.%m.%Y - %H:%M:%S"))
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
        logger.info(f"Quiet hours active ({quiet_start}-{quiet_end}): volume capped from {volume} to {quiet_volume}")
        return quiet_volume
    return volume


class OwnToneClient:
    def __init__(self, host: str, port: str, timeout: int = 5):
        self.base = f"http://{host}:{port}"
        self.timeout = timeout

    def list_outputs(self) -> list[dict]:
        resp = requests.get(f"{self.base}/api/outputs", timeout=self.timeout)
        resp.raise_for_status()
        return resp.json().get("outputs", [])

    def resolve_output_ids(self, names: list[str]) -> list[str]:
        outputs = self.list_outputs()
        by_name = {o["name"]: str(o["id"]) for o in outputs}
        ids = []
        for name in names:
            oid = by_name.get(name)
            if oid:
                logger.debug(f"Output found: {name} -> {oid}")
                ids.append(oid)
            else:
                logger.warning(f"Output not found: {name}")
        return ids

    def set_volume(self, output_ids: list[str], volume: int) -> None:
        for oid in output_ids:
            requests.put(
                f"{self.base}/api/outputs/{oid}",
                json={"volume": volume},
                timeout=self.timeout,
            )

    def select_outputs(self, output_ids: list[str]) -> None:
        requests.put(
            f"{self.base}/api/outputs/set",
            json={"outputs": output_ids},
            timeout=self.timeout,
        )

    def resolve_track_uri(self, file_path: str) -> Optional[str]:
        resp = requests.get(
            f"{self.base}/api/search",
            params={"type": "tracks", "expression": f'path is "{file_path}"'},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        items = resp.json().get("tracks", {}).get("items", [])
        if not items:
            return None
        return f"library:track:{items[0]['id']}"

    def play(self, track_uri: str) -> None:
        requests.post(
            f"{self.base}/api/queue/items/add",
            params={"uris": track_uri, "clear": "true", "playback": "start"},
            timeout=self.timeout,
        )


def play(prayer_name: str, mode: str = "adhan") -> bool:
    """Play the configured audio file for `prayer_name` on its configured OwnTone outputs.

    `mode` can be 'adhan' (the call to prayer) or 'alert' (the iqama reminder).
    Returns True on success, False if any precondition failed (no outputs configured,
    OwnTone unreachable, track missing, etc.). Errors are logged.
    """
    init_db()
    _configure_logging()

    if mode == "alert":
        logger.info(f"Iqama alert triggered for: {prayer_name}")
    else:
        logger.info(f"Adhan triggered for: {prayer_name}")

    homepods = get_outputs_for_prayer(prayer_name)
    if not homepods:
        logger.warning(f"No outputs configured for {prayer_name}")
        return False

    logger.debug(f"Outputs for {prayer_name}: {homepods}")

    base_volume = get_prayer_volume(prayer_name, int(get_value("owntone", "ADHAN_VOLUME", "40")))
    volume = _apply_quiet_hours(base_volume)
    logger.debug(f"Volume for {prayer_name}: {volume}")

    if mode == "alert":
        file_path = get_value("owntone", "ALERT_FILE", "/srv/media/alert.mp3")
    else:
        file_path = get_value("owntone", "ADHAN_FILE", "/srv/media/adhan.mp3")
    if not file_path:
        logger.error("Audio file not set")
        return False

    host = get_value("owntone", "HOST", "host.docker.internal")
    port = get_value("owntone", "PORT", "3689")
    client = OwnToneClient(host, port)

    try:
        output_ids = client.resolve_output_ids(homepods)
    except requests.RequestException as e:
        logger.error(f"OwnTone unreachable at {host}:{port}: {type(e).__name__}")
        return False

    if not output_ids:
        logger.error(f"No valid OwnTone outputs found for {prayer_name}")
        return False

    try:
        track_uri = client.resolve_track_uri(file_path)
    except requests.RequestException as e:
        logger.error(f"OwnTone search failed: {type(e).__name__}")
        return False

    if not track_uri:
        logger.error(f"Track not found: {file_path}")
        return False

    try:
        client.set_volume(output_ids, volume)
        client.select_outputs(output_ids)
        client.play(track_uri)
    except requests.RequestException as e:
        logger.error(f"Playback failed: {type(e).__name__}")
        return False

    logger.info(f"Playback started: {track_uri} on {output_ids}")
    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: adhan_player.py <prayer_name> [alert|adhan]", file=sys.stderr)
        sys.exit(1)
    prayer = sys.argv[1]
    play_mode = sys.argv[2] if len(sys.argv) > 2 else "adhan"
    ok = play(prayer, play_mode)
    sys.exit(0 if ok else 1)
