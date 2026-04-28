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
| `db/schema.py` | SQLite init + env→db migration |
| `db/config.py` | CRUD helpers for config tables + token management |
| `providers/mawaqit_http_provider.py` | HTTP fetch of confData (adhan + iqama + coords) |
| `providers/mawaqit_selenium_provider.py` | Selenium fallback for mawaqit |
| `providers/custom_selenium_provider.py` | [CONCEPT] Scrape any mosque site |
| `get_time_salat.py` | Router: reads config from SQLite, calls provider, writes crontab |
| `adhan.sh` | Cron script: loads config via `load_config.py`, plays audio |
| `load_config.py` | SQLite → shell exports (for adhan.sh) |
| `get_homepods.py` | SQLite → HomePod names for a period (for adhan.sh) |
| `admin_reset.py` | CLI for admin account recovery (run via `docker exec`) |

## Data Storage

**SQLite** (`data/adhan.db`) stores all app config:
- `config` table — MOSQUE_URL, LAT, LNG, CITY, LOG_LEVEL, time periods
- `owntone` table — HOST, PORT, ADHAN_FILE, ADHAN_VOLUME
- `homepods` table — name, morning, afternoon, evening booleans
- `auth` table — admin account (`username`, `password_hash` bcrypt)
- `sessions` table — active session cookies (`session_id`, `auth_id`, `expires_at`)
- `api_tokens` table — bearer tokens for external apps (SHA-256 hashed)
- `users` table — id, name, emoji, created_at
- `prayer_logs` table — user_id, prayer, date (unique per user/prayer/date)

**`.env`** is infrastructure only: TZ, ports, build versions, `COOKIE_SECURE`.

## Auth

Two parallel mechanisms guard admin endpoints:
- **Session cookie** (`adhan_session`, HttpOnly, SameSite=Strict, 30d) issued by `POST /api/login` → for the web UI
- **Bearer admin token** (`Authorization: Bearer …`, scope `admin`) for non-browser clients (Home Assistant, scripts)

`_require_admin()` in [web/app.py](web/app.py) accepts either. Public endpoints stay public (dashboard data); only admin actions and `/api/prayer-logs/me` require auth.

The `prayers`-scoped Bearer token (one per user) is for external apps that only log/read prayers — it never grants config access.

## API

- `GET /api/prayers` — prayer data with status (past/current/upcoming) + iqama + next prayer countdown
- `GET /api/weather` — Open-Meteo weather from stored lat/lng
- `POST /api/setup` — one-shot first-launch: creates admin account + saves base config + opens session
- `POST /api/login` — `{username, password}` → sets session cookie
- `POST /api/logout` — clears session
- `POST /api/config` — update a single config field `{table, key, value}` (admin)
- `POST /api/refresh` — re-run get_time_salat.py (admin)
- `POST /api/validate-url` — validate mawaqit URL, returns prayer preview
- `GET/POST /api/users` — list/create users (POST = admin)
- `PUT/DELETE /api/users/{id}` — update/delete user (admin)
- `POST/DELETE /api/prayer-log` — log/unlog a prayer for a user on a date
- `GET /api/prayer-logs/{date}` — get prayer logs + users for a date
- `GET /api/stats` — leaderboard or heatmap (params: period, user_id)

## Web UI Pages

- `/` — redirects to `/setup` (no admin) or `/dashboard`
- `/dashboard` — prayer times, weather, clock, countdown, prayer tracking avatars (public)
- `/setup` — first-launch wizard (creates admin) — refuses to load once admin exists
- `/login` — admin login (redirects to `/settings` once authenticated)
- `/settings` — all config editable (admin only)
- `/stats` — leaderboard + heatmap (admin only)

## Mawaqit confData Structure

The mawaqit provider extracts from the page:
- `conf.times` — `[Fajr, Dhuhr, Asr, Maghrib, Isha]` (adhan times, 5 strings "HH:MM")
- `conf.calendar[month][day]` — `[Fajr, Sunrise, Dhuhr, Asr, Maghrib, Isha]` (iqama, 6 strings)
- `conf.latitude`, `conf.longitude` — GPS coords for weather
- `conf.name` — mosque/city name

## Volumes

- `./data` → `/app/data` — shared SQLite database
- `cron-data` → `/etc/cron.d` — shared crontab between web and adhan containers
