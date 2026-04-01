# CLAUDE.md — Adhan Home

## Project Overview

Automated Islamic prayer call system with web dashboard. Fetches prayer times from mawaqit.net, schedules cron jobs, plays audio on HomePods via OwnTone/AirPlay.

## Architecture

```
Web UI (FastAPI :8080) ←→ SQLite (data/adhan.db) ←→ Adhan container (cron)
                                                         ↓
                                                    adhan.sh → OwnTone → HomePods
```

Two Docker containers share a SQLite database and a cron volume:
- `web` — FastAPI (dashboard + setup wizard + settings + API)
- `adhan` — cron daemon + prayer triggering scripts

## Key Files

| File | Role |
|------|------|
| `web/app.py` | FastAPI app — API endpoints + page routing |
| `db/schema.py` | SQLite init + env→db + HomePod.json→db migrations |
| `db/config.py` | CRUD helpers for config tables + token management |
| `providers/mawaqit_http_provider.py` | HTTP fetch of confData (adhan + iqama + coords) |
| `providers/mawaqit_selenium_provider.py` | Selenium fallback for mawaqit |
| `providers/custom_selenium_provider.py` | [CONCEPT] Scrape any mosque site |
| `get_time_salat.py` | Router: reads config from SQLite, calls provider, writes crontab |
| `adhan.sh` | Cron script: loads config via `load_config.py`, plays audio |
| `_archive/home_assistant.py` | [ARCHIVED] HA REST API client — awaiting use case definition |
| `load_config.py` | SQLite → shell exports (for adhan.sh) |
| `get_homepods.py` | SQLite → HomePod names for a period (for adhan.sh) |

## Data Storage

**SQLite** (`data/adhan.db`) stores all app config:
- `config` table — MOSQUE_URL, LAT, LNG, CITY, LOG_LEVEL, time periods
- `owntone` table — HOST, PORT, ADHAN_FILE, ADHAN_VOLUME
- `homepods` table — name, morning, afternoon, evening booleans
- `api_tokens` table — bearer tokens for protected endpoints

**`.env`** is infrastructure only: TZ, ports, build versions.

## API

- `GET /api/prayers` — prayer data with status (past/current/upcoming) + iqama + next prayer countdown
- `GET /api/weather` — Open-Meteo weather from stored lat/lng
- `POST /api/setup` — first-time config, returns generated API token
- `POST /api/config` — update config (requires Bearer token)
- `POST /api/refresh` — re-run get_time_salat.py (requires Bearer token)
- `POST /api/validate-url` — validate mawaqit URL, returns prayer preview

## Web UI Pages

- `/` — redirects to `/setup` or `/dashboard`
- `/dashboard` — prayer times, weather, clock, countdown
- `/setup` — first-launch wizard
- `/settings` — all config editable (gear icon on dashboard)

## Mawaqit confData Structure

The mawaqit provider extracts from the page:
- `conf.times` — `[Fajr, Dhuhr, Asr, Maghrib, Isha]` (adhan times, 5 strings "HH:MM")
- `conf.calendar[month][day]` — `[Fajr, Sunrise, Dhuhr, Asr, Maghrib, Isha]` (iqama, 6 strings)
- `conf.latitude`, `conf.longitude` — GPS coords for weather
- `conf.name` — mosque/city name

## Volumes

- `./data` → `/app/data` — shared SQLite database
- `cron-data` → `/etc/cron.d` — shared crontab between web and adhan containers
