"""APScheduler-based scheduler that replaces cron + get_time_salat.py.

Runs as a standalone process (managed by supervisord). Responsibilities:
  - Daily refresh at 04:00: fetch prayer times from mawaqit, save to SQLite, reschedule prayer triggers.
  - Per-prayer adhan triggers (5/day) and optional iqama alerts.
  - Boot-time refresh so the schedule is always populated when the process starts.
  - SIGUSR1 handler so the API can trigger an immediate refresh (used by /api/setup, /api/refresh, etc.).
  - SIGTERM/SIGINT: clean shutdown.

The PID is written to /app/data/scheduler.pid so the API can locate the process to signal.
"""
import logging
import os
import signal
import sys
import threading
from datetime import date, datetime, timedelta

import requests
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db.schema import init_db
from db.config import (
    get_value,
    set_value,
    is_configured,
    save_prayer_times,
    cleanup_old_prayer_times,
    get_all_alert_config,
    get_prayer_times_for_date,
)
from providers.mawaqit_http_provider import get_full_data_for_date
import adhan_player

PID_FILE = os.environ.get("SCHEDULER_PID_FILE", "/app/data/scheduler.pid")
DAILY_REFRESH_HOUR = 4
DAILY_REFRESH_MINUTE = 0
DAILY_REFRESH_JOB_ID = "daily_refresh"
PRAYER_JOB_PREFIX = "prayer:"
ALERT_JOB_PREFIX = "alert:"

logger = logging.getLogger("scheduler")

scheduler = BackgroundScheduler(timezone=os.environ.get("TZ", "Europe/Paris"))

# Used to wake the main loop when SIGUSR1 arrives.
refresh_event = threading.Event()
shutdown_event = threading.Event()


def _configure_logging():
    level_name = get_value("config", "LOG_LEVEL", "INFO")
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(
        level=level,
        format="[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%d.%m.%Y - %H:%M:%S",
    )


def _write_pid_file():
    os.makedirs(os.path.dirname(PID_FILE), exist_ok=True)
    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))
    logger.info(f"PID {os.getpid()} written to {PID_FILE}")


def _remove_pid_file():
    try:
        os.remove(PID_FILE)
    except FileNotFoundError:
        pass


def _check_url_reachable(url: str) -> bool:
    try:
        resp = requests.get(
            url,
            timeout=10,
            headers={"User-Agent": "Mozilla/5.0 (compatible; AdhanHome/1.0)"},
        )
        if resp.status_code >= 400:
            logger.error(f"MOSQUE_URL responded {resp.status_code}: {url}")
            return False
        return True
    except requests.RequestException as e:
        logger.error(f"MOSQUE_URL unreachable ({type(e).__name__}): {url}")
        return False


def _fetch_and_store(target_date: date, mosque_url: str) -> list[dict]:
    """Fetch prayer times from mawaqit and persist to SQLite. Returns the prayers list."""
    data = get_full_data_for_date(mosque_url, target_date)
    save_prayer_times(target_date.strftime("%Y-%m-%d"), data["prayers"])

    if data.get("lat"):
        set_value("config", "LAT", str(data["lat"]))
    if data.get("lng"):
        set_value("config", "LNG", str(data["lng"]))
    if data.get("city"):
        set_value("config", "CITY", data["city"])
    if data.get("jumua"):
        set_value("config", "JUMUA", ",".join(data["jumua"]))
    if data.get("sunrise"):
        set_value("config", "SUNRISE", data["sunrise"])

    logger.info(
        f"Stored prayers for {target_date.strftime('%Y-%m-%d')}: "
        f"{[p['adhan'] for p in data['prayers']]}"
    )
    return data["prayers"]


def _clear_dynamic_jobs():
    """Remove every prayer/alert job. The daily refresh job is preserved."""
    for job in scheduler.get_jobs():
        if job.id.startswith(PRAYER_JOB_PREFIX) or job.id.startswith(ALERT_JOB_PREFIX):
            scheduler.remove_job(job.id)


def _schedule_prayers_for_date(target_date: date, prayers: list[dict]):
    """Create one DateTrigger per prayer (and per enabled iqama alert) for `target_date`.

    Past times for `target_date` (i.e. earlier today) are skipped, since a DateTrigger
    in the past would just be ignored by APScheduler with a warning.
    """
    now = datetime.now()
    alert_config = get_all_alert_config()

    for p in prayers:
        name = p["name"]
        h, m = map(int, p["adhan"].split(":"))
        run_at = datetime.combine(target_date, datetime.min.time()).replace(hour=h, minute=m)
        if run_at > now:
            scheduler.add_job(
                adhan_player.play,
                trigger=DateTrigger(run_date=run_at),
                args=[name, "adhan"],
                id=f"{PRAYER_JOB_PREFIX}{name}:{target_date.isoformat()}",
                replace_existing=True,
                misfire_grace_time=300,
            )
            logger.debug(f"Scheduled adhan {name} at {run_at.isoformat()}")

        cfg = alert_config.get(name, {})
        if cfg.get("enabled") and p.get("iqama"):
            iq_h, iq_m = map(int, p["iqama"].split(":"))
            delay = int(cfg.get("delay", 0))
            alert_at = datetime.combine(target_date, datetime.min.time()).replace(hour=iq_h, minute=iq_m) + timedelta(minutes=delay)
            if alert_at > now:
                scheduler.add_job(
                    adhan_player.play,
                    trigger=DateTrigger(run_date=alert_at),
                    args=[name, "alert"],
                    id=f"{ALERT_JOB_PREFIX}{name}:{target_date.isoformat()}",
                    replace_existing=True,
                    misfire_grace_time=300,
                )
                logger.debug(f"Scheduled iqama alert {name} at {alert_at.isoformat()} (+{delay}min)")


def refresh_jobs():
    """Re-fetch prayer times and rebuild the day's triggers.

    Called at boot, daily at 04:00, and on SIGUSR1 (API-triggered).
    """
    if not is_configured():
        logger.info("Project not configured. Skipping refresh.")
        return

    mosque_url = get_value("config", "MOSQUE_URL")
    if not mosque_url:
        logger.error("MOSQUE_URL is empty in DB")
        return

    if not _check_url_reachable(mosque_url):
        return

    today = date.today()
    tomorrow = today + timedelta(days=1)
    now = datetime.now()

    today_data = get_prayer_times_for_date(today.strftime("%Y-%m-%d"))
    isha_today = next((p for p in today_data if p["name"] == "Isha"), None) if today_data else None
    isha_past = False
    if isha_today:
        ih, im = map(int, isha_today["adhan"].split(":"))
        isha_past = (now.hour, now.minute) >= (ih, im)

    try:
        if isha_past:
            target = tomorrow
            prayers = _fetch_and_store(tomorrow, mosque_url)
        else:
            target = today
            prayers = _fetch_and_store(today, mosque_url)
    except Exception as e:
        logger.error(f"Failed to fetch prayer times: {type(e).__name__}: {e}")
        return

    _clear_dynamic_jobs()
    _schedule_prayers_for_date(target, prayers)
    cleanup_old_prayer_times()
    logger.info(f"Refresh complete: {len(scheduler.get_jobs())} jobs scheduled")


def _handle_sigusr1(signum, frame):
    logger.info("SIGUSR1 received: requesting refresh")
    refresh_event.set()


def _handle_shutdown(signum, frame):
    logger.info(f"Signal {signum} received: shutting down")
    shutdown_event.set()
    refresh_event.set()  # unblock the main loop


def main():
    init_db()
    _configure_logging()
    _write_pid_file()

    signal.signal(signal.SIGUSR1, _handle_sigusr1)
    signal.signal(signal.SIGTERM, _handle_shutdown)
    signal.signal(signal.SIGINT, _handle_shutdown)

    scheduler.add_job(
        refresh_jobs,
        trigger=CronTrigger(hour=DAILY_REFRESH_HOUR, minute=DAILY_REFRESH_MINUTE),
        id=DAILY_REFRESH_JOB_ID,
        replace_existing=True,
        misfire_grace_time=3600,
    )

    scheduler.start()
    logger.info("Scheduler started")

    try:
        refresh_jobs()
    except Exception as e:
        logger.error(f"Initial refresh failed: {type(e).__name__}: {e}")

    try:
        while not shutdown_event.is_set():
            refresh_event.wait()
            refresh_event.clear()
            if shutdown_event.is_set():
                break
            try:
                refresh_jobs()
            except Exception as e:
                logger.error(f"Refresh failed: {type(e).__name__}: {e}")
    finally:
        scheduler.shutdown(wait=False)
        _remove_pid_file()
        logger.info("Scheduler stopped")


if __name__ == "__main__":
    main()
