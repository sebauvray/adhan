# Adhan Home — Automated Prayer Call

A home automation system that plays the Islamic call to prayer (Adhan) on HomePods at the correct times, fetched daily from [mawaqit.net](https://mawaqit.net). Comes with a web dashboard for configuration and real-time prayer display.

## How It Works

```
mawaqit.net
     │ HTTP fetch (daily 4 AM)
     ▼
Prayer times → crontab
                  │ cron fires at each prayer
                  ▼
             adhan.sh → OwnTone → HomePods
```

1. **Daily fetch** — At 4:00 AM, prayer times are retrieved from mawaqit.net for your mosque.
2. **Dynamic scheduling** — Times are written as cron entries.
3. **Smart playback** — At prayer time, OwnTone streams the Adhan over AirPlay to selected HomePods.
4. **Context-aware** — Device selection and volume adapt to the time of day.

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
| `make clean` | Supprime tout : containers, volumes, images et base SQLite (fresh install) |
| `make help` | Affiche les commandes disponibles |

## Web Interface

### Dashboard
- Real-time clock and date
- All 5 prayers with adhan and iqama times
- Current prayer highlighted (golden, larger)
- Next prayer countdown with Arabic name
- Weather widget (Open-Meteo, no API key needed)

### Setup Wizard
On first launch, the UI asks for:
- **Mosque URL** — your mosque's mawaqit.net page (validated live with prayer preview)
- **OwnTone** — host, port, audio file, volume
- **Time periods** — morning/afternoon/evening ranges

### Settings
All configuration is editable via the gear icon (top right of dashboard). Changes are saved to SQLite and the crontab is regenerated automatically.

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
├── get_time_salat.py       # Router: provider → crontab
├── next_salat.py           # Next prayer reporter
├── load_config.py          # SQLite → shell env bridge
├── get_homepods.py         # SQLite → HomePod list for a period
├── docker-compose.yml
└── .env_example
```

### Data Flow

| Component | Source | Storage |
|-----------|--------|---------|
| App config (mosque URL, HA, OwnTone...) | Web UI | SQLite (`data/adhan.db`) |
| Docker/infra config (TZ, ports, versions) | `.env` | File |
| Prayer schedule | mawaqit.net | `/etc/cron.d/salat.crontab` |
| HomePod config | Web UI (migrated from `HomePod.json`) | SQLite |

## Fetching Modes

| Mode | `AUTONOMOUS` | Method | Image size | Raspberry Pi |
|------|-------------|--------|-----------|-------------|
| Mawaqit HTTP | `false` (default) | HTTP + regex | ~80 MB | Recommended |
| Mawaqit Selenium | `true` | Firefox headless | ~500 MB | Heavy |
| Custom (concept) | — | Selenium + custom XPath | ~500 MB | Heavy |

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
| `GET` | `/api/prayers` | — | Prayer times + statuses + next prayer |
| `GET` | `/api/weather` | — | Weather for mosque location |
| `GET` | `/api/config` | — | Current configuration |
| `POST` | `/api/setup` | — | Initial setup (returns API token) |
| `POST` | `/api/config` | Bearer token | Update configuration |
| `POST` | `/api/refresh` | Bearer token | Force prayer time re-fetch |
| `POST` | `/api/validate-url` | — | Validate a mawaqit.net URL |

## Next Prayer

```bash
docker compose exec adhan python3 /app/next_salat.py
# La prochaine prière Fadjer aura lieu à 05:42
```

## Home Assistant

La logique d'intégration Home Assistant a été archivée dans `_archive/home_assistant.py`. Le script permettait de déclencher des appels API vers Home Assistant (turn_on/turn_off d'entités). Cette fonctionnalité est en attente de réflexion sur le cas d'usage exact avant d'être réintégrée dans le projet.
