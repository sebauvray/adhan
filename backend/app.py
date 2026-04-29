import os
import signal
import sys
from datetime import datetime, time as dtime, timedelta
from typing import Optional

from fastapi import FastAPI, Request, Response, HTTPException, Header, Cookie, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import requests as http_requests

sys.path.insert(0, '/app')

from db.schema import init_db
from db.config import (
    get_value, set_value, get_all, get_homepods, set_homepods,
    is_configured, has_token, create_token, validate_token,
    list_tokens, delete_token,
    has_auth, create_auth, verify_auth,
    create_session, validate_session, delete_session,
    SESSION_DURATION_DAYS,
    get_prayer_outputs, set_prayer_outputs,
    get_all_prayer_volumes, set_prayer_volume,
    get_prayer_times_for_date,
    get_users, create_user, update_user, delete_user,
    log_prayer, unlog_prayer, get_prayer_logs_for_date,
    get_prayer_logs_for_user_date,
    get_prayer_stats, get_user_streak,
    get_all_alert_config, set_alert_enabled, set_alert_delay,
)
from providers.mawaqit_http_provider import get_full_data

SESSION_COOKIE = "adhan_session"
COOKIE_SECURE = os.environ.get('COOKIE_SECURE', 'false').lower() == 'true'
SCHEDULER_PID_FILE = os.environ.get('SCHEDULER_PID_FILE', '/app/data/scheduler.pid')


def _trigger_refresh() -> bool:
    """Signal the scheduler process (sibling under supervisord) to refresh prayer times now.

    Returns True if SIGUSR1 was delivered, False if the scheduler isn't ready yet
    (e.g. PID file missing right after boot) or the process is gone.
    """
    try:
        with open(SCHEDULER_PID_FILE) as f:
            pid = int(f.read().strip())
        os.kill(pid, signal.SIGUSR1)
        return True
    except (FileNotFoundError, ValueError, ProcessLookupError, PermissionError):
        return False

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

# --- Events ---

@app.on_event("startup")
async def startup():
    init_db()


# --- Pages ---

def _is_logged_in(adhan_session: Optional[str]) -> bool:
    return bool(adhan_session and validate_session(adhan_session))


@app.get("/", response_class=HTMLResponse)
async def root():
    if not has_auth():
        return RedirectResponse("/setup")
    return RedirectResponse("/dashboard")


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    if not has_auth():
        return RedirectResponse("/setup")
    return templates.TemplateResponse(request, "dashboard.html")


@app.get("/setup", response_class=HTMLResponse)
async def setup_page(request: Request):
    if has_auth():
        return RedirectResponse("/dashboard")
    return templates.TemplateResponse(request, "setup.html")


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, adhan_session: Optional[str] = Cookie(None)):
    if not has_auth():
        return RedirectResponse("/setup")
    if _is_logged_in(adhan_session):
        return RedirectResponse("/settings")
    return templates.TemplateResponse(request, "login.html")


@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request, adhan_session: Optional[str] = Cookie(None)):
    if not has_auth():
        return RedirectResponse("/setup")
    if not _is_logged_in(adhan_session):
        return RedirectResponse("/login?next=/settings")
    return templates.TemplateResponse(request, "settings.html", {"title": "Paramètres", "subtitle": "Sauvegarde automatique"})


@app.get("/stats", response_class=HTMLResponse)
async def stats_page(request: Request, adhan_session: Optional[str] = Cookie(None)):
    if not has_auth():
        return RedirectResponse("/setup")
    if not _is_logged_in(adhan_session):
        return RedirectResponse("/login?next=/stats")
    return templates.TemplateResponse(request, "stats.html", {"title": "Statistiques", "subtitle": "Suivi des prieres"})


# --- API ---

@app.get("/api/status")
async def api_status():
    return {"configured": is_configured()}


def _require_admin(authorization: Optional[str], session_cookie: Optional[str]):
    """Admin auth: accepts either a session cookie (web UI) or a Bearer admin token (external apps).
    Returns context dict or raises 401."""
    if session_cookie:
        sess = validate_session(session_cookie)
        if sess:
            return {"kind": "session", "auth_id": sess["auth_id"], "username": sess["username"]}
    if authorization and authorization.startswith("Bearer "):
        info = validate_token(authorization[7:])
        if info and info["scope"] == "admin":
            return {"kind": "token", **info}
    raise HTTPException(status_code=401, detail="Authentification requise")


def _require_token(authorization: Optional[str], allowed_scopes: list):
    """Validate Bearer token and check scope. Returns the token row or raises 401/403."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token requis")
    info = validate_token(authorization[7:])
    if not info:
        raise HTTPException(status_code=401, detail="Token invalide")
    if info["scope"] not in allowed_scopes:
        raise HTTPException(status_code=403, detail="Scope insuffisant")
    return info


def _optional_token(authorization: Optional[str]):
    """Validate Bearer token if present. Returns the token row or None.
    Raises 401 if a token is provided but invalid."""
    if not authorization:
        return None
    if not authorization.startswith("Bearer "):
        return None
    info = validate_token(authorization[7:])
    if not info:
        raise HTTPException(status_code=401, detail="Token invalide")
    return info


def _set_session_cookie(response: Response, session_id: str):
    response.set_cookie(
        key=SESSION_COOKIE,
        value=session_id,
        max_age=SESSION_DURATION_DAYS * 86400,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="strict",
        path="/",
    )


def _clear_session_cookie(response: Response):
    response.delete_cookie(SESSION_COOKIE, path="/")


def _can_edit(prayer: str, log_date_str: str) -> bool:
    """Server-side guard: can this prayer/date pair be logged right now?
    Allowed: yesterday (any prayer) and today (only if adhan time has passed).
    """
    now = datetime.now()
    today = now.date()
    yesterday = today - timedelta(days=1)
    log_date = datetime.strptime(log_date_str, '%Y-%m-%d').date()

    if log_date == yesterday:
        return True

    if log_date == today:
        prayers = get_prayer_times_for_date(today.strftime('%Y-%m-%d'))
        target = next((p for p in prayers if p['name'] == prayer), None)
        if not target:
            return False
        h, m = map(int, target['adhan'].split(':'))
        return now >= datetime.combine(today, dtime(h, m))

    return False


@app.get("/api/prayers")
async def api_prayers(date: Optional[str] = None):
    if not is_configured():
        raise HTTPException(status_code=503, detail="Non configuré")

    now = datetime.now()
    current_time = now.time()

    today = now.date()
    yesterday = today - timedelta(days=1)
    tomorrow = today + timedelta(days=1)

    multi_day = get_value('config', 'MULTI_DAY_DISPLAY', 'false') == 'true'
    tomorrow_available = multi_day and bool(get_prayer_times_for_date(tomorrow.strftime('%Y-%m-%d')))

    if date:
        try:
            view_date = datetime.strptime(date, '%Y-%m-%d').date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Date invalide")
        if not multi_day and view_date != today:
            raise HTTPException(status_code=403, detail="Navigation multi-jours désactivée")
        if view_date == tomorrow and not tomorrow_available:
            raise HTTPException(status_code=403, detail="Lendemain non disponible")
        if view_date not in (yesterday, today, tomorrow):
            raise HTTPException(status_code=403, detail="Date hors plage")
    else:
        view_date = today

    prayers_list = get_prayer_times_for_date(view_date.strftime('%Y-%m-%d'))
    if not prayers_list:
        raise HTTPException(status_code=503, detail="Horaires non disponibles")

    # Status per prayer
    last_passed_idx = -1
    if view_date == today:
        for i, p in enumerate(prayers_list):
            h, m = map(int, p['adhan'].split(':'))
            if dtime(h, m) <= current_time:
                last_passed_idx = i
    elif view_date < today:
        last_passed_idx = len(prayers_list)
    # view_date > today: all upcoming

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

    # Next prayer (across day boundary if needed)
    next_prayer = None
    for p in result:
        if p['status'] == 'upcoming':
            next_prayer = dict(p)
            h, m = map(int, p['adhan'].split(':'))
            next_dt = datetime.combine(view_date, dtime(h, m))
            next_prayer['seconds_until'] = max(0, int((next_dt - now).total_seconds()))
            break

    if not next_prayer and view_date == today and result:
        next_day = view_date + timedelta(days=1)
        next_day_prayers = get_prayer_times_for_date(next_day.strftime('%Y-%m-%d'))
        if next_day_prayers:
            first = dict(next_day_prayers[0])
            first['arabic'] = ARABIC.get(first['name'], '')
            h, m = map(int, first['adhan'].split(':'))
            next_dt = datetime.combine(next_day, dtime(h, m))
            first['seconds_until'] = max(0, int((next_dt - now).total_seconds()))
            first['status'] = 'upcoming'
            next_prayer = first

    current_salat = next((p['name'] for p in result if p['status'] == 'current'), None)

    can_view_previous = multi_day and view_date != yesterday
    can_view_next = multi_day and ((view_date == yesterday) or (view_date == today and tomorrow_available))

    return {
        "prayers": result,
        "next": next_prayer,
        "current_salat": current_salat,
        "view_date": view_date.strftime('%Y-%m-%d'),
        "today": today.strftime('%Y-%m-%d'),
        "yesterday": yesterday.strftime('%Y-%m-%d'),
        "tomorrow": tomorrow.strftime('%Y-%m-%d'),
        "can_view_previous": can_view_previous,
        "can_view_next": can_view_next,
    }


@app.get("/api/next-prayer")
async def api_next_prayer():
    data = await api_prayers()
    n = data.get("next")
    if not n:
        raise HTTPException(status_code=503, detail="Aucune prière à venir")
    h = n['seconds_until'] // 3600
    m = (n['seconds_until'] % 3600) // 60
    return {
        "name": n['name'],
        "arabic": n.get('arabic', ''),
        "adhan": n['adhan'],
        "iqama": n['iqama'],
        "seconds_until": n['seconds_until'],
        "time_until": f"{h}h{m:02d}",
    }


@app.get("/api/jumua")
async def api_jumua():
    jumua_str = get_value('config', 'JUMUA', '')
    if not jumua_str:
        return {"times": []}
    return {"times": jumua_str.split(',')}


@app.get("/api/sunrise")
async def api_sunrise():
    sunrise = get_value('config', 'SUNRISE', '')
    return {"time": sunrise}


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
            "is_day": cw.get("is_day", 1),  # 1 for day, 0 for night
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
        "alert_file": get_value('owntone', 'ALERT_FILE', '/srv/media/alert.mp3'),
        "quiet_start": get_value('config', 'QUIET_START', '21:00'),
        "quiet_end": get_value('config', 'QUIET_END', '07:00'),
        "quiet_volume": get_value('config', 'QUIET_VOLUME', '10'),
        "multi_day_display": get_value('config', 'MULTI_DAY_DISPLAY', 'false'),
        "homepods": get_homepods(),
    }


class SetupPayload(BaseModel):
    username: str
    password: str
    emoji: str = "🙂"
    mosque_url: str
    sound_enabled: str = "false"
    owntone_mode: str = "local"            # "local" (bundled service) or "external"
    owntone_host: str = "host.docker.internal"
    owntone_port: str = "3689"
    adhan_file: str = "/srv/media/adhan.mp3"
    adhan_volume: str = "40"
    log_level: str = "INFO"


@app.post("/api/setup")
async def api_setup(data: SetupPayload, response: Response):
    """First-launch setup: creates the admin account, saves base config, opens a session.
    Also creates a tracking user (same name, chosen emoji) and links it to the admin."""
    if has_auth():
        raise HTTPException(status_code=409, detail="Configuration déjà initialisée")

    username = (data.username or '').strip()
    password = data.password or ''
    emoji = (data.emoji or '🙂').strip() or '🙂'
    if len(username) < 3:
        raise HTTPException(status_code=400, detail="Identifiant trop court (3 caractères minimum)")
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Mot de passe trop court (8 caractères minimum)")

    tracking_user_id = create_user(username, emoji)
    create_auth(username, password, user_id=tracking_user_id)

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

    # OwnTone: in "local" mode we ignore user inputs and force the bundled defaults.
    # In "external" mode we trust whatever host/port the user typed.
    owntone_mode = data.owntone_mode if data.owntone_mode in ('local', 'external') else 'local'
    set_value('config', 'OWNTONE_MODE', owntone_mode)
    if owntone_mode == 'local':
        set_value('owntone', 'HOST', 'host.docker.internal')
        set_value('owntone', 'PORT', '3689')
    else:
        set_value('owntone', 'HOST', (data.owntone_host or '').strip() or 'host.docker.internal')
        set_value('owntone', 'PORT', (data.owntone_port or '').strip() or '3689')
    set_value('owntone', 'ADHAN_FILE', data.adhan_file)
    set_value('owntone', 'ADHAN_VOLUME', data.adhan_volume)

    auth_id = verify_auth(username, password)
    session_id = create_session(auth_id)
    _set_session_cookie(response, session_id)

    _trigger_refresh()

    return {"success": True}


# --- Login / Logout ---

class LoginPayload(BaseModel):
    username: str
    password: str


@app.post("/api/login")
async def api_login(data: LoginPayload, response: Response):
    auth_id = verify_auth((data.username or '').strip(), data.password or '')
    if not auth_id:
        raise HTTPException(status_code=401, detail="Identifiants invalides")
    session_id = create_session(auth_id)
    _set_session_cookie(response, session_id)
    return {"success": True}


@app.post("/api/logout")
async def api_logout(
    response: Response,
    adhan_session: Optional[str] = Cookie(None),
):
    delete_session(adhan_session)
    _clear_session_cookie(response)
    return {"success": True}


@app.get("/api/auth/status")
async def api_auth_status(adhan_session: Optional[str] = Cookie(None)):
    """Reports whether the current request carries a valid session.
    Used by the frontend to decide between /login and /dashboard."""
    sess = validate_session(adhan_session) if adhan_session else None
    return {"authenticated": bool(sess), "username": sess["username"] if sess else None}


@app.post("/api/refresh")
async def api_refresh(
    authorization: Optional[str] = Header(None),
    adhan_session: Optional[str] = Cookie(None),
):
    _require_admin(authorization, adhan_session)

    _trigger_refresh()
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


@app.post("/api/config")
async def api_config(
    payload: dict,
    authorization: Optional[str] = Header(None),
    adhan_session: Optional[str] = Cookie(None),
):
    """Save a single config field. Expects {table, key, value}."""
    _require_admin(authorization, adhan_session)

    table = payload.get('table')
    key = payload.get('key')
    value = payload.get('value', '')
    if not table or not key:
        raise HTTPException(status_code=400, detail="table and key required")
    set_value(table, key, value)

    # If mosque URL changed, refresh lat/lng/city and regenerate crontab
    if table == 'config' and key == 'MOSQUE_URL' and value:
        try:
            data = get_full_data(value)
            set_value('config', 'LAT', str(data.get('lat', '')))
            set_value('config', 'LNG', str(data.get('lng', '')))
            set_value('config', 'CITY', data.get('city', ''))
        except Exception:
            pass
        _trigger_refresh()

    return {"success": True}


@app.get("/api/prayer-outputs")
async def api_get_prayer_outputs():
    """Get speaker config, volumes and alert config per prayer."""
    return {
        "outputs": get_prayer_outputs(),
        "volumes": get_all_prayer_volumes(),
        "alerts": get_all_alert_config(),
    }


@app.post("/api/prayer-outputs")
async def api_set_prayer_outputs(
    payload: dict,
    authorization: Optional[str] = Header(None),
    adhan_session: Optional[str] = Cookie(None),
):
    """Save speaker config per prayer. Expects {outputs: {prayer: [{id, name}]}, volumes: {prayer: int}}."""
    _require_admin(authorization, adhan_session)
    outputs = payload.get('outputs', {})
    volumes = payload.get('volumes', {})
    alerts = payload.get('alerts', {})
    for prayer, outs in outputs.items():
        set_prayer_outputs(prayer, outs)
    for prayer, vol in volumes.items():
        set_prayer_volume(prayer, vol)
    for prayer, cfg in alerts.items():
        if isinstance(cfg, dict):
            set_alert_enabled(prayer, cfg.get('enabled', False))
            set_alert_delay(prayer, cfg.get('delay', 0))
        else:
            set_alert_enabled(prayer, cfg)
    return {"success": True}


@app.post("/api/test-prayer/{prayer}")
async def api_test_prayer(
    prayer: str,
    authorization: Optional[str] = Header(None),
    adhan_session: Optional[str] = Cookie(None),
):
    """Play adhan on configured outputs for a specific prayer."""
    _require_admin(authorization, adhan_session)
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
async def api_stop_playback(
    authorization: Optional[str] = Header(None),
    adhan_session: Optional[str] = Cookie(None),
):
    """Stop OwnTone playback."""
    _require_admin(authorization, adhan_session)
    host = get_value('owntone', 'HOST', 'host.docker.internal')
    port = get_value('owntone', 'PORT', '3689')
    http_requests.put(f"http://{host}:{port}/api/player/stop", timeout=5)
    return {"success": True}


MEDIA_DIR = '/srv/media'
ALLOWED_AUDIO = {'.mp3', '.wav', '.ogg', '.m4a', '.flac'}


@app.post("/api/upload-adhan")
async def api_upload_adhan(
    file: UploadFile = File(...),
    authorization: Optional[str] = Header(None),
    adhan_session: Optional[str] = Cookie(None),
):
    _require_admin(authorization, adhan_session)
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
async def api_delete_adhan(
    authorization: Optional[str] = Header(None),
    adhan_session: Optional[str] = Cookie(None),
):
    _require_admin(authorization, adhan_session)
    adhan_file = get_value('owntone', 'ADHAN_FILE', '')
    if adhan_file and os.path.exists(adhan_file):
        os.remove(adhan_file)
    set_value('owntone', 'ADHAN_FILE', '/srv/media/adhan.mp3')
    return {"success": True}


@app.post("/api/upload-alert")
async def api_upload_alert(
    file: UploadFile = File(...),
    authorization: Optional[str] = Header(None),
    adhan_session: Optional[str] = Cookie(None),
):
    _require_admin(authorization, adhan_session)
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_AUDIO:
        raise HTTPException(status_code=400, detail=f"Format non supporté ({ext}). Formats acceptés : {', '.join(ALLOWED_AUDIO)}")

    os.makedirs(MEDIA_DIR, exist_ok=True)
    dest = os.path.join(MEDIA_DIR, f"alert{ext}")

    with open(dest, 'wb') as f:
        content = await file.read()
        f.write(content)

    set_value('owntone', 'ALERT_FILE', dest)
    return {"success": True, "filename": file.filename, "path": dest}


@app.delete("/api/upload-alert")
async def api_delete_alert(
    authorization: Optional[str] = Header(None),
    adhan_session: Optional[str] = Cookie(None),
):
    _require_admin(authorization, adhan_session)
    alert_file = get_value('owntone', 'ALERT_FILE', '')
    if alert_file and os.path.exists(alert_file):
        os.remove(alert_file)
    set_value('owntone', 'ALERT_FILE', '/srv/media/alert.mp3')
    return {"success": True}


# --- Users API ---

@app.get("/api/users")
async def api_get_users():
    return {"users": get_users()}


@app.post("/api/users")
async def api_create_user(
    payload: dict,
    authorization: Optional[str] = Header(None),
    adhan_session: Optional[str] = Cookie(None),
):
    _require_admin(authorization, adhan_session)
    name = payload.get('name', '').strip()
    emoji = payload.get('emoji', '🙂').strip()
    if not name:
        raise HTTPException(status_code=400, detail="Nom requis")
    user_id = create_user(name, emoji)
    return {"success": True, "id": user_id}


@app.put("/api/users/{user_id}")
async def api_update_user(
    user_id: int,
    payload: dict,
    authorization: Optional[str] = Header(None),
    adhan_session: Optional[str] = Cookie(None),
):
    _require_admin(authorization, adhan_session)
    name = payload.get('name', '').strip()
    emoji = payload.get('emoji', '🙂').strip()
    if not name:
        raise HTTPException(status_code=400, detail="Nom requis")
    update_user(user_id, name, emoji)
    return {"success": True}


@app.delete("/api/users/{user_id}")
async def api_delete_user(
    user_id: int,
    authorization: Optional[str] = Header(None),
    adhan_session: Optional[str] = Cookie(None),
):
    _require_admin(authorization, adhan_session)
    delete_user(user_id)
    return {"success": True}


# --- Prayer Logs API ---

def _resolve_log_user(payload: dict, authorization: Optional[str]) -> int:
    """Determine which user_id to log against.
    If a 'prayers' scoped token is present, it overrides the payload user_id.
    Otherwise the payload user_id is used (anonymous dashboard mode or admin token)."""
    info = _optional_token(authorization)
    if info and info["scope"] == "prayers":
        if not info["user_id"]:
            raise HTTPException(status_code=400, detail="Token sans user_id")
        return info["user_id"]
    user_id = payload.get('user_id')
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id requis")
    return user_id


@app.post("/api/prayer-log")
async def api_log_prayer(payload: dict, authorization: Optional[str] = Header(None)):
    user_id = _resolve_log_user(payload, authorization)
    prayer = payload.get('prayer')
    date = payload.get('date')
    if not all([prayer, date]):
        raise HTTPException(status_code=400, detail="prayer et date requis")
    if not _can_edit(prayer, date):
        raise HTTPException(status_code=403, detail="Validation interdite pour cette prière")
    log_prayer(user_id, prayer, date)
    return {"success": True}


@app.delete("/api/prayer-log")
async def api_unlog_prayer(payload: dict, authorization: Optional[str] = Header(None)):
    user_id = _resolve_log_user(payload, authorization)
    prayer = payload.get('prayer')
    date = payload.get('date')
    if not all([prayer, date]):
        raise HTTPException(status_code=400, detail="prayer et date requis")
    if not _can_edit(prayer, date):
        raise HTTPException(status_code=403, detail="Validation interdite pour cette prière")
    unlog_prayer(user_id, prayer, date)
    return {"success": True}


@app.get("/api/prayer-logs/me")
async def api_get_my_prayer_logs(date: Optional[str] = None, authorization: Optional[str] = Header(None)):
    """Get prayers logged by the authenticated user for a date (default: today)."""
    info = _require_token(authorization, ["prayers"])
    if not info["user_id"]:
        raise HTTPException(status_code=400, detail="Token sans user_id")
    log_date = date or datetime.now().strftime('%Y-%m-%d')
    return {
        "date": log_date,
        "user_id": info["user_id"],
        "prayers": get_prayer_logs_for_user_date(info["user_id"], log_date),
    }


@app.get("/api/prayer-logs/{date}")
async def api_get_prayer_logs(date: str):
    logs = get_prayer_logs_for_date(date)
    users = get_users()
    return {"logs": logs, "users": users}


# --- Stats API ---

@app.get("/api/stats")
async def api_stats(period: str = 'month', user_id: int = None):
    users = get_users()
    if user_id:
        heatmap = get_prayer_stats(user_id=user_id, period=period)
        streak = get_user_streak(user_id)
        return {"heatmap": heatmap, "streak": streak}
    else:
        leaderboard_data = get_prayer_stats(period=period)
        leaderboard = []
        for u in users:
            count = leaderboard_data.get(u['id'], 0)
            streak = get_user_streak(u['id'])
            leaderboard.append({**u, "count": count, "streak": streak})
        leaderboard.sort(key=lambda x: x['count'], reverse=True)
        return {"leaderboard": leaderboard, "users": users}


# --- Tokens API (admin only) ---

@app.get("/api/tokens")
async def api_list_tokens(
    authorization: Optional[str] = Header(None),
    adhan_session: Optional[str] = Cookie(None),
):
    _require_admin(authorization, adhan_session)
    return {"tokens": list_tokens()}


@app.post("/api/tokens")
async def api_create_token(
    payload: dict,
    authorization: Optional[str] = Header(None),
    adhan_session: Optional[str] = Cookie(None),
):
    _require_admin(authorization, adhan_session)
    scope = payload.get('scope', 'prayers')
    if scope not in ('admin', 'prayers'):
        raise HTTPException(status_code=400, detail="Scope invalide")
    description = (payload.get('description') or '').strip() or 'API'
    user_id = payload.get('user_id')
    if scope == 'prayers':
        if not user_id:
            raise HTTPException(status_code=400, detail="user_id requis pour scope 'prayers'")
        if not any(u['id'] == user_id for u in get_users()):
            raise HTTPException(status_code=400, detail="Utilisateur introuvable")
    else:
        user_id = None
    token = create_token(description=description, scope=scope, user_id=user_id)
    return {"success": True, "token": token}


@app.delete("/api/tokens/{token_id}")
async def api_delete_token(
    token_id: int,
    authorization: Optional[str] = Header(None),
    adhan_session: Optional[str] = Cookie(None),
):
    _require_admin(authorization, adhan_session)
    delete_token(token_id)
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
