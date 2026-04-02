# Adhan Home — Automated Prayer Call

A home automation system that plays the Islamic call to prayer (Adhan) on HomePods at the correct times, fetched daily from [mawaqit.net](https://mawaqit.net). Comes with a web dashboard for configuration and real-time prayer display.

## How It Works

```
mawaqit.net
     │ HTTP fetch (after Isha)
     ▼
Prayer times → SQLite → crontab (next day)
                           │ cron fires at each prayer
                           ▼
                      adhan.sh → OwnTone → HomePods
```

1. **Daily fetch** — After Isha, prayer times for the next day are retrieved from mawaqit.net.
2. **SQLite storage** — Adhan and iqama times are stored in the database (single source of truth).
3. **Dynamic scheduling** — The crontab is rewritten with tomorrow's prayer times.
4. **Smart playback** — At prayer time, OwnTone streams the Adhan over AirPlay to configured speakers.
5. **Per-prayer config** — Each prayer has its own speakers and volume.

## Quick Start

```bash
git clone <repo-url>
cd adhan
cp .env_example .env
make up
```

Open **http://localhost:8080** — the setup wizard guides you through configuration.

## Commandes Make

| Commande | Description |
|----------|-------------|
| `make up` | Build et démarre tous les containers |
| `make down` | Arrête les containers (conserve les données) |
| `make clean` | Supprime tout : containers, volumes, images (fresh install) |
| `make help` | Affiche les commandes disponibles |

## Web Interface

### Dashboard
- Header: weather widget + real-time clock + settings
- All 5 prayers with adhan and iqama times
- Current prayer highlighted, next prayer countdown with Arabic name
- Diagonal split design (dark/light)
- Friday footer with Jumu'a prayer times

### Setup Wizard
On first launch, the UI asks for:
- **Mosque URL** — your mosque's mawaqit.net page (validated live with prayer preview)
- **Sound alerts** — enable/disable, custom audio file upload

### Settings
All configuration is editable via the gear icon on the dashboard. Changes are saved to SQLite and the crontab is regenerated automatically.

## Architecture

```
adhan/
├── web/                    # FastAPI web service
│   ├── app.py              # API + Jinja2 templates
│   ├── dockerfile
│   ├── static/             # CSS + JS
│   └── templates/          # Dashboard, Setup, Settings
├── db/                     # SQLite module
│   ├── schema.py           # DB init + migrations
│   └── config.py           # CRUD helpers
├── providers/              # Prayer time fetchers
│   ├── mawaqit_http_provider.py      # HTTP (default)
│   ├── mawaqit_selenium_provider.py  # Selenium fallback
│   └── custom_selenium_provider.py   # [concept] any site
├── docker/
│   ├── dockerfile          # Adhan container
│   └── requirements.txt
├── adhan.sh                # Cron script: volume + play on HomePods
├── get_time_salat.py       # Fetch → SQLite → crontab
├── load_config.py          # SQLite → shell env bridge
├── get_homepods.py         # SQLite → speaker list for a prayer
├── docker-compose.yml
├── Makefile
└── .env_example
```

### Data Flow

| Component | Source | Storage |
|-----------|--------|---------|
| App config (mosque URL, OwnTone...) | Web UI | SQLite (`adhan-data` volume) |
| Prayer times (adhan + iqama) | mawaqit.net | SQLite `prayer_times` table |
| Docker/infra config (TZ, ports) | `.env` | File |
| Prayer schedule | SQLite | `/etc/cron.d/salat.crontab` |
| Speaker config per prayer | Web UI | SQLite `prayer_outputs` table |

## Docker Services

| Service | Port | Purpose |
|---------|------|---------|
| `web` | 8080 (configurable via `WEB_PORT`) | Dashboard + API |
| `adhan` | — | Cron + prayer triggering |
| `owntone` | 3689 (host network) | AirPlay audio server |

## Build Variables

Override in `.env` without touching Dockerfiles:

| Variable | Default | Description |
|----------|---------|-------------|
| `WEB_PORT` | `8080` | Web interface port |
| `AUTONOMOUS` | `false` | Fetching mode |
| `DEBIAN_VERSION` | `bookworm` | Base image |
| `GECKODRIVER_VERSION` | `v0.34.0` | Selenium mode only |

## API Endpoints

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `GET` | `/api/status` | — | Check if configured |
| `GET` | `/api/prayers` | — | Prayer times + statuses + next prayer countdown |
| `GET` | `/api/next-prayer` | — | Next prayer name, time, countdown |
| `GET` | `/api/jumua` | — | Friday prayer times |
| `GET` | `/api/weather` | — | Weather for mosque location |
| `GET` | `/api/config` | — | Current configuration |
| `GET` | `/api/outputs` | — | Available AirPlay speakers |
| `GET` | `/api/prayer-outputs` | — | Speaker config per prayer |
| `POST` | `/api/setup` | — | Initial setup (returns API token) |
| `POST` | `/api/config` | Bearer | Update configuration |
| `POST` | `/api/config-field` | — | Update a single config field |
| `POST` | `/api/refresh` | Bearer | Force prayer time re-fetch |
| `POST` | `/api/validate-url` | — | Validate a mawaqit.net URL |
| `POST` | `/api/prayer-outputs` | — | Save speaker config per prayer |
| `POST` | `/api/test-prayer/{prayer}` | — | Test adhan on configured speakers |
| `POST` | `/api/stop-playback` | — | Stop OwnTone playback |
| `POST` | `/api/upload-adhan` | — | Upload custom audio file |
| `DELETE` | `/api/upload-adhan` | — | Delete custom audio file |
