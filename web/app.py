import subprocess
import sys
import os
from datetime import datetime, time as dtime, timedelta
from typing import Optional

from fastapi import FastAPI, Request, HTTPException, Header, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import requests as http_requests

sys.path.insert(0, '/app')

from db.schema import init_db
from db.config import (
    get_value, set_value, get_all, get_homepods, set_homepods,
    is_configured, get_token, create_token, validate_token,
    get_prayer_outputs, set_prayer_outputs,
    get_all_prayer_volumes, set_prayer_volume
)
from providers.mawaqit_http_provider import get_full_data

app = FastAPI(title="Adhan Home")

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

ARABIC = {
    'Fajr': 'الفجر',
    'Dhuhr': 'الظهر',
    'Asr': 'العصر',
    'Maghrib': 'المغرب',
    'Isha': 'العشاء',
}

# --- Cache simple en mémoire (1h) ---

_cache = {}


def _get_cached(url):
    now = datetime.now()
    key = f"{url}:{now.strftime('%Y-%m-%d-%H')}"
    if key not in _cache:
        _cache.clear()
        _cache[key] = get_full_data(url)
    return _cache[key]


# --- Events ---

@app.on_event("startup")
async def startup():
    init_db()


# --- Pages ---

@app.get("/", response_class=HTMLResponse)
async def root():
    if not is_configured():
        return RedirectResponse("/setup")
    return RedirectResponse("/dashboard")


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    if not is_configured():
        return RedirectResponse("/setup")
    return templates.TemplateResponse(request, "dashboard.html")


@app.get("/setup", response_class=HTMLResponse)
async def setup_page(request: Request):
    return templates.TemplateResponse(request, "setup.html")


@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    if not is_configured():
        return RedirectResponse("/setup")
    return templates.TemplateResponse(request, "settings.html")


# --- API ---

@app.get("/api/status")
async def api_status():
    return {"configured": is_configured()}


@app.get("/api/prayers")
async def api_prayers():
    mosque_url = get_value('config', 'MOSQUE_URL')
    if not mosque_url:
        raise HTTPException(status_code=503, detail="Non configuré")

    try:
        data = _get_cached(mosque_url)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))

    now = datetime.now()
    current_time = now.time()
    prayers_list = data['prayers']

    # Déterminer le statut de chaque prière
    last_passed_idx = -1
    for i, p in enumerate(prayers_list):
        h, m = map(int, p['adhan'].split(':'))
        if dtime(h, m) <= current_time:
            last_passed_idx = i

    result = []
    for i, p in enumerate(prayers_list):
        if i < last_passed_idx:
            status = 'past'
        elif i == last_passed_idx:
            status = 'current'
        else:
            status = 'upcoming'

        result.append({
            **p,
            'arabic': ARABIC.get(p['name'], ''),
            'status': status,
        })

    # Prochaine prière
    next_prayer = None
    for p in result:
        if p['status'] == 'upcoming':
            next_prayer = dict(p)
            h, m = map(int, p['adhan'].split(':'))
            next_dt = now.replace(hour=h, minute=m, second=0, microsecond=0)
            next_prayer['seconds_until'] = int((next_dt - now).total_seconds())
            break

    if not next_prayer and result:
        first = dict(result[0])
        h, m = map(int, first['adhan'].split(':'))
        next_dt = (now + timedelta(days=1)).replace(hour=h, minute=m, second=0, microsecond=0)
        first['seconds_until'] = int((next_dt - now).total_seconds())
        first['status'] = 'upcoming'
        next_prayer = first

    return {"prayers": result, "next": next_prayer}


@app.get("/api/weather")
async def api_weather():
    lat = get_value('config', 'LAT')
    lng = get_value('config', 'LNG')
    city = get_value('config', 'CITY', '')

    if not lat or not lng:
        raise HTTPException(status_code=503, detail="Coordonnées non configurées")

    try:
        resp = http_requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={"latitude": lat, "longitude": lng, "current_weather": "true"},
            timeout=5,
        )
        resp.raise_for_status()
        cw = resp.json().get("current_weather", {})
        return {
            "city": city,
            "temperature": round(cw.get("temperature", 0)),
            "weather_code": cw.get("weathercode", 0),
        }
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.get("/api/config")
async def api_get_config():
    return {
        "mosque_url": get_value('config', 'MOSQUE_URL', ''),
        "city": get_value('config', 'CITY', ''),
        "sound_enabled": get_value('config', 'SOUND_ENABLED', 'false'),
        "log_level": get_value('config', 'LOG_LEVEL', 'INFO'),
        "owntone_host": get_value('owntone', 'HOST', 'host.docker.internal'),
        "owntone_port": get_value('owntone', 'PORT', '3689'),
        "adhan_file": get_value('owntone', 'ADHAN_FILE', '/srv/media/adhan.mp3'),
        "adhan_volume": get_value('owntone', 'ADHAN_VOLUME', '40'),
        "homepods": get_homepods(),
    }


class ConfigPayload(BaseModel):
    mosque_url: str
    sound_enabled: str = "false"
    owntone_host: str = ""
    owntone_port: str = "3689"
    adhan_file: str = "/srv/media/adhan.mp3"
    adhan_volume: str = "40"
    log_level: str = "INFO"
    homepods: list = []


async def _save_config(data: ConfigPayload):
    """Sauvegarde toute la configuration dans SQLite."""
    # Fetch mawaqit pour lat/lng/city
    try:
        mawaqit_data = get_full_data(data.mosque_url)
        set_value('config', 'LAT', str(mawaqit_data.get('lat', '')))
        set_value('config', 'LNG', str(mawaqit_data.get('lng', '')))
        set_value('config', 'CITY', mawaqit_data.get('city', ''))
    except Exception:
        pass

    set_value('config', 'MOSQUE_URL', data.mosque_url)
    set_value('config', 'SOUND_ENABLED', data.sound_enabled)
    set_value('config', 'LOG_LEVEL', data.log_level)
    set_value('owntone', 'HOST', data.owntone_host)
    set_value('owntone', 'PORT', data.owntone_port)
    set_value('owntone', 'ADHAN_FILE', data.adhan_file)
    set_value('owntone', 'ADHAN_VOLUME', data.adhan_volume)

    if data.homepods:
        set_homepods(data.homepods)

    # Vider le cache pour forcer le refresh
    _cache.clear()


@app.post("/api/setup")
async def api_setup(data: ConfigPayload):
    await _save_config(data)

    # Générer le token au premier setup
    token = get_token()
    new_token = None
    if not token:
        new_token = create_token("setup")

    # Déclencher le premier fetch des horaires
    subprocess.Popen([sys.executable, '/app/get_time_salat.py'])

    return {"success": True, "token": new_token}


@app.post("/api/config")
async def api_update_config(data: ConfigPayload, authorization: Optional[str] = Header(None)):
    token = authorization.replace("Bearer ", "") if authorization else None
    if not validate_token(token):
        raise HTTPException(status_code=401, detail="Token invalide")

    await _save_config(data)

    # Relancer le fetch pour mettre à jour le crontab
    subprocess.Popen([sys.executable, '/app/get_time_salat.py'])

    return {"success": True}


@app.post("/api/refresh")
async def api_refresh(authorization: Optional[str] = Header(None)):
    token = authorization.replace("Bearer ", "") if authorization else None
    if not validate_token(token):
        raise HTTPException(status_code=401, detail="Token invalide")

    subprocess.Popen([sys.executable, '/app/get_time_salat.py'])
    return {"success": True}


@app.get("/api/outputs")
async def api_outputs():
    """Fetch available AirPlay devices from OwnTone."""
    host = get_value('owntone', 'HOST', 'host.docker.internal')
    port = get_value('owntone', 'PORT', '3689')
    try:
        resp = http_requests.get(f"http://{host}:{port}/api/outputs", timeout=5)
        resp.raise_for_status()
        outputs = resp.json().get('outputs', [])
        return {
            "outputs": [
                {
                    "id": o['id'],
                    "name": o['name'],
                    "type": o['type'],
                    "selected": o['selected'],
                    "volume": o['volume'],
                }
                for o in outputs
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"OwnTone inaccessible : {type(e).__name__}")


@app.post("/api/config-field")
async def api_config_field(payload: dict):
    """Save a single config field. Expects {table, key, value}."""
    table = payload.get('table')
    key = payload.get('key')
    value = payload.get('value', '')
    if not table or not key:
        raise HTTPException(status_code=400, detail="table and key required")
    set_value(table, key, value)

    # If mosque URL changed, refresh lat/lng/city
    if table == 'config' and key == 'MOSQUE_URL' and value:
        try:
            data = get_full_data(value)
            set_value('config', 'LAT', str(data.get('lat', '')))
            set_value('config', 'LNG', str(data.get('lng', '')))
            set_value('config', 'CITY', data.get('city', ''))
            _cache.clear()
        except Exception:
            pass

    return {"success": True}


@app.get("/api/prayer-outputs")
async def api_get_prayer_outputs():
    """Get speaker config and volumes per prayer."""
    return {
        "outputs": get_prayer_outputs(),
        "volumes": get_all_prayer_volumes(),
    }


@app.post("/api/prayer-outputs")
async def api_set_prayer_outputs(payload: dict):
    """Save speaker config per prayer. Expects {outputs: {prayer: [{id, name}]}, volumes: {prayer: int}}."""
    outputs = payload.get('outputs', {})
    volumes = payload.get('volumes', {})
    for prayer, outs in outputs.items():
        set_prayer_outputs(prayer, outs)
    for prayer, vol in volumes.items():
        set_prayer_volume(prayer, vol)
    return {"success": True}


@app.post("/api/test-prayer/{prayer}")
async def api_test_prayer(prayer: str):
    """Play adhan on configured outputs for a specific prayer."""
    from db.config import get_outputs_for_prayer, get_prayer_volume
    host = get_value('owntone', 'HOST', 'host.docker.internal')
    port = get_value('owntone', 'PORT', '3689')
    adhan_file = get_value('owntone', 'ADHAN_FILE', '/srv/media/adhan.mp3')

    outputs = get_outputs_for_prayer(prayer)
    if not outputs:
        raise HTTPException(status_code=400, detail=f"Aucune enceinte configurée pour {prayer}")

    volume = get_prayer_volume(prayer, 30)
    base = f"http://{host}:{port}"

    # Get all OwnTone outputs
    resp = http_requests.get(f"{base}/api/outputs", timeout=5)
    all_outputs = resp.json().get('outputs', [])

    # Find IDs for configured names
    ids = []
    for o in all_outputs:
        if o['name'] in outputs:
            ids.append(str(o['id']))
            # Set volume
            http_requests.put(f"{base}/api/outputs/{o['id']}",
                json={"volume": volume}, timeout=5)

    if not ids:
        raise HTTPException(status_code=400, detail="Enceintes introuvables dans OwnTone")

    # Select outputs
    http_requests.put(f"{base}/api/outputs/set",
        json={"outputs": ids}, timeout=5)

    # Search track
    resp = http_requests.get(f"{base}/api/search",
        params={"type": "tracks", "expression": f'path is "{adhan_file}"'}, timeout=5)
    tracks = resp.json().get('tracks', {}).get('items', [])
    if not tracks:
        raise HTTPException(status_code=400, detail="Fichier audio introuvable dans OwnTone")

    track_uri = f"library:track:{tracks[0]['id']}"

    # Play
    http_requests.post(f"{base}/api/queue/items/add?uris={track_uri}&clear=true&playback=start", timeout=5)

    return {"success": True, "outputs": outputs, "volume": volume}


@app.post("/api/stop-playback")
async def api_stop_playback():
    """Stop OwnTone playback."""
    host = get_value('owntone', 'HOST', 'host.docker.internal')
    port = get_value('owntone', 'PORT', '3689')
    http_requests.put(f"http://{host}:{port}/api/player/stop", timeout=5)
    return {"success": True}


MEDIA_DIR = '/srv/media'
ALLOWED_AUDIO = {'.mp3', '.wav', '.ogg', '.m4a', '.flac'}


@app.post("/api/upload-adhan")
async def api_upload_adhan(file: UploadFile = File(...)):
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_AUDIO:
        raise HTTPException(status_code=400, detail=f"Format non supporté ({ext}). Formats acceptés : {', '.join(ALLOWED_AUDIO)}")

    os.makedirs(MEDIA_DIR, exist_ok=True)
    dest = os.path.join(MEDIA_DIR, f"adhan{ext}")

    with open(dest, 'wb') as f:
        content = await file.read()
        f.write(content)

    set_value('owntone', 'ADHAN_FILE', dest)
    return {"success": True, "filename": file.filename, "path": dest}


@app.delete("/api/upload-adhan")
async def api_delete_adhan():
    adhan_file = get_value('owntone', 'ADHAN_FILE', '')
    if adhan_file and os.path.exists(adhan_file):
        os.remove(adhan_file)
    set_value('owntone', 'ADHAN_FILE', '/srv/media/adhan.mp3')
    return {"success": True}


@app.post("/api/validate-url")
async def api_validate_url(payload: dict):
    url = payload.get('url', '')
    if not url:
        return {"valid": False, "error": "URL vide"}
    try:
        resp = http_requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0 (compatible; AdhanHome/1.0)"})
        if resp.status_code >= 400:
            return {"valid": False, "error": f"L'URL répond {resp.status_code}"}
        preview = get_full_data(url)
        return {
            "valid": True,
            "city": preview.get('city', ''),
            "prayers": preview.get('prayers', []),
        }
    except ValueError as e:
        return {"valid": False, "error": str(e)}
    except Exception as e:
        return {"valid": False, "error": f"Impossible de joindre l'URL : {type(e).__name__}"}
