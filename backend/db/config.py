import sqlite3
import secrets
import hashlib
from collections import defaultdict
from datetime import datetime, timedelta
from db.schema import get_db_path

SESSION_DURATION_DAYS = 30


def _connect():
    return sqlite3.connect(get_db_path())


def _hash_token(token):
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def get_value(table, key, default=None):
    try:
        conn = _connect()
        cur = conn.execute(f"SELECT value FROM [{table}] WHERE key = ?", (key,))
        row = cur.fetchone()
        conn.close()
        return row[0] if row else default
    except Exception:
        return default


def set_value(table, key, value):
    conn = _connect()
    conn.execute(
        f"INSERT OR REPLACE INTO [{table}] (key, value) VALUES (?, ?)",
        (key, str(value))
    )
    conn.commit()
    conn.close()


def get_all(table):
    try:
        conn = _connect()
        cur = conn.execute(f"SELECT key, value FROM [{table}]")
        rows = dict(cur.fetchall())
        conn.close()
        return rows
    except Exception:
        return {}


def get_homepods():
    try:
        conn = _connect()
        cur = conn.execute("SELECT name, morning, afternoon, evening FROM homepods ORDER BY name")
        rows = [
            {"name": r[0], "morning": bool(r[1]), "afternoon": bool(r[2]), "evening": bool(r[3])}
            for r in cur.fetchall()
        ]
        conn.close()
        return rows
    except Exception:
        return []


def set_homepods(homepods):
    conn = _connect()
    conn.execute("DELETE FROM homepods")
    for pod in homepods:
        conn.execute(
            "INSERT INTO homepods (name, morning, afternoon, evening) VALUES (?, ?, ?, ?)",
            (pod['name'], int(pod.get('morning', False)),
             int(pod.get('afternoon', True)), int(pod.get('evening', False)))
        )
    conn.commit()
    conn.close()


def is_configured():
    url = get_value('config', 'MOSQUE_URL')
    return bool(url)


# --- Auth (admin login) ---

def has_auth():
    """Return True if an admin account exists."""
    try:
        conn = _connect()
        cur = conn.execute("SELECT 1 FROM auth LIMIT 1")
        exists = cur.fetchone() is not None
        conn.close()
        return exists
    except Exception:
        return False


def create_auth(username, password, user_id=None):
    """Create the admin account. password is hashed with bcrypt.
    Optionally link this admin to a tracking user (`users` table)."""
    import bcrypt
    pw_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    conn = _connect()
    conn.execute(
        "INSERT INTO auth (username, password_hash, user_id) VALUES (?, ?, ?)",
        (username, pw_hash, user_id)
    )
    conn.commit()
    conn.close()


def verify_auth(username, password):
    """Verify credentials. Returns auth_id if valid, else None."""
    import bcrypt
    try:
        conn = _connect()
        cur = conn.execute(
            "SELECT id, password_hash FROM auth WHERE username = ?",
            (username,)
        )
        row = cur.fetchone()
        conn.close()
        if not row:
            return None
        auth_id, pw_hash = row
        if bcrypt.checkpw(password.encode('utf-8'), pw_hash.encode('utf-8')):
            return auth_id
        return None
    except Exception:
        return None


def list_auth():
    """Returns [{id, username, created_at}, ...]."""
    try:
        conn = _connect()
        cur = conn.execute("SELECT id, username, created_at FROM auth ORDER BY id")
        rows = [{"id": r[0], "username": r[1], "created_at": r[2]} for r in cur.fetchall()]
        conn.close()
        return rows
    except Exception:
        return []


def update_auth_password(username, new_password):
    """Update password for an existing admin. Invalidates all their sessions.
    Returns True if updated, False if no such account."""
    import bcrypt
    pw_hash = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    conn = _connect()
    cur = conn.execute(
        "UPDATE auth SET password_hash = ? WHERE username = ?",
        (pw_hash, username)
    )
    if cur.rowcount == 0:
        conn.close()
        return False
    conn.execute(
        "DELETE FROM sessions WHERE auth_id IN (SELECT id FROM auth WHERE username = ?)",
        (username,)
    )
    conn.commit()
    conn.close()
    return True


def delete_auth(username):
    """Delete an admin account and all its sessions. Returns True if deleted."""
    conn = _connect()
    cur = conn.execute("DELETE FROM auth WHERE username = ?", (username,))
    deleted = cur.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


# --- Sessions (cookie-based admin auth) ---

def create_session(auth_id):
    """Create a new session for an authenticated admin. Returns session_id."""
    session_id = secrets.token_urlsafe(48)
    expires_at = (datetime.utcnow() + timedelta(days=SESSION_DURATION_DAYS)).isoformat(timespec='seconds')
    conn = _connect()
    conn.execute(
        "INSERT INTO sessions (session_id, auth_id, expires_at) VALUES (?, ?, ?)",
        (session_id, auth_id, expires_at)
    )
    conn.commit()
    conn.close()
    return session_id


def validate_session(session_id):
    """Returns {auth_id, username} if session is valid and not expired, else None.
    Also refreshes last_seen."""
    if not session_id:
        return None
    try:
        conn = _connect()
        cur = conn.execute(
            "SELECT s.auth_id, s.expires_at, a.username "
            "FROM sessions s JOIN auth a ON a.id = s.auth_id "
            "WHERE s.session_id = ?",
            (session_id,)
        )
        row = cur.fetchone()
        if not row:
            conn.close()
            return None
        auth_id, expires_at, username = row
        if datetime.fromisoformat(expires_at) < datetime.utcnow():
            conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
            conn.commit()
            conn.close()
            return None
        conn.execute(
            "UPDATE sessions SET last_seen = ? WHERE session_id = ?",
            (datetime.utcnow().isoformat(timespec='seconds'), session_id)
        )
        conn.commit()
        conn.close()
        return {"auth_id": auth_id, "username": username}
    except Exception:
        return None


def delete_session(session_id):
    if not session_id:
        return
    try:
        conn = _connect()
        conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
        conn.commit()
        conn.close()
    except Exception:
        pass


def cleanup_expired_sessions():
    try:
        conn = _connect()
        conn.execute(
            "DELETE FROM sessions WHERE expires_at < ?",
            (datetime.utcnow().isoformat(timespec='seconds'),)
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


def has_token():
    """Return True if at least one API token exists."""
    try:
        conn = _connect()
        cur = conn.execute("SELECT 1 FROM api_tokens LIMIT 1")
        exists = cur.fetchone() is not None
        conn.close()
        return exists
    except Exception:
        return False


def create_token(description="default", scope="admin", user_id=None):
    """Create a new API token. Returns the plaintext value once; only its hash is stored."""
    token = secrets.token_urlsafe(32)
    conn = _connect()
    conn.execute(
        "INSERT INTO api_tokens (token, description, scope, user_id) VALUES (?, ?, ?, ?)",
        (_hash_token(token), description, scope, user_id)
    )
    conn.commit()
    conn.close()
    return token


def validate_token(token):
    """Returns {id, scope, user_id, description} if valid, else None."""
    if not token:
        return None
    try:
        conn = _connect()
        cur = conn.execute(
            "SELECT id, scope, user_id, description FROM api_tokens WHERE token = ?",
            (_hash_token(token),)
        )
        row = cur.fetchone()
        conn.close()
        if not row:
            return None
        return {"id": row[0], "scope": row[1], "user_id": row[2], "description": row[3]}
    except Exception:
        return None


def list_tokens():
    """List tokens (without their values) joined with user info."""
    try:
        conn = _connect()
        cur = conn.execute(
            "SELECT t.id, t.description, t.scope, t.user_id, t.created_at, u.name, u.emoji "
            "FROM api_tokens t LEFT JOIN users u ON t.user_id = u.id "
            "ORDER BY t.created_at DESC"
        )
        rows = [
            {
                "id": r[0],
                "description": r[1],
                "scope": r[2],
                "user_id": r[3],
                "created_at": r[4],
                "user_name": r[5],
                "user_emoji": r[6],
            }
            for r in cur.fetchall()
        ]
        conn.close()
        return rows
    except Exception:
        return []


def delete_token(token_id):
    conn = _connect()
    conn.execute("DELETE FROM api_tokens WHERE id = ?", (token_id,))
    conn.commit()
    conn.close()


def get_alert_enabled(prayer):
    try:
        conn = _connect()
        cur = conn.execute("SELECT alert_enabled FROM prayer_config WHERE prayer = ?", (prayer,))
        row = cur.fetchone()
        conn.close()
        return bool(row[0]) if row else False
    except Exception:
        return False


def set_alert_enabled(prayer, enabled):
    conn = _connect()
    conn.execute(
        "INSERT INTO prayer_config (prayer, alert_enabled) VALUES (?, ?) "
        "ON CONFLICT(prayer) DO UPDATE SET alert_enabled = ?",
        (prayer, int(enabled), int(enabled))
    )
    conn.commit()
    conn.close()


def set_alert_delay(prayer, delay):
    conn = _connect()
    conn.execute(
        "INSERT INTO prayer_config (prayer, alert_delay) VALUES (?, ?) "
        "ON CONFLICT(prayer) DO UPDATE SET alert_delay = ?",
        (prayer, int(delay), int(delay))
    )
    conn.commit()
    conn.close()


def get_all_alert_config():
    try:
        conn = _connect()
        cur = conn.execute("SELECT prayer, alert_enabled, alert_delay FROM prayer_config")
        result = {r[0]: {"enabled": bool(r[1]), "delay": r[2]} for r in cur.fetchall()}
        conn.close()
        return result
    except Exception:
        return {}


def get_prayer_volume(prayer, default=30):
    try:
        conn = _connect()
        cur = conn.execute("SELECT volume FROM prayer_config WHERE prayer = ?", (prayer,))
        row = cur.fetchone()
        conn.close()
        return row[0] if row else default
    except Exception:
        return default


def set_prayer_volume(prayer, volume):
    conn = _connect()
    conn.execute(
        "INSERT OR REPLACE INTO prayer_config (prayer, volume) VALUES (?, ?)",
        (prayer, int(volume))
    )
    conn.commit()
    conn.close()


def get_all_prayer_volumes():
    try:
        conn = _connect()
        cur = conn.execute("SELECT prayer, volume FROM prayer_config")
        result = {r[0]: r[1] for r in cur.fetchall()}
        conn.close()
        return result
    except Exception:
        return {}


def get_prayer_outputs(prayer=None):
    """Get configured outputs per prayer. Returns dict {prayer: [output_names]}."""
    try:
        conn = _connect()
        if prayer:
            cur = conn.execute(
                "SELECT prayer, output_id, output_name FROM prayer_outputs WHERE prayer = ?",
                (prayer,)
            )
        else:
            cur = conn.execute("SELECT prayer, output_id, output_name FROM prayer_outputs")
        rows = cur.fetchall()
        conn.close()

        result = {}
        for p, oid, oname in rows:
            if p not in result:
                result[p] = []
            result[p].append({"id": oid, "name": oname})
        return result
    except Exception:
        return {}


def set_prayer_outputs(prayer, outputs):
    """Set outputs for a prayer. outputs = [{"id": "...", "name": "..."}]."""
    conn = _connect()
    conn.execute("DELETE FROM prayer_outputs WHERE prayer = ?", (prayer,))
    for o in outputs:
        conn.execute(
            "INSERT INTO prayer_outputs (prayer, output_id, output_name) VALUES (?, ?, ?)",
            (prayer, o['id'], o['name'])
        )
    conn.commit()
    conn.close()


def get_outputs_for_prayer(prayer):
    """Get output names for a specific prayer (used by adhan.sh)."""
    try:
        conn = _connect()
        cur = conn.execute(
            "SELECT output_name FROM prayer_outputs WHERE prayer = ?",
            (prayer,)
        )
        names = [r[0] for r in cur.fetchall()]
        conn.close()
        return names
    except Exception:
        return []


def save_prayer_times(date_str, prayers):
    """Save prayer times for a date. prayers = [{name, adhan, iqama}, ...]."""
    conn = _connect()
    for p in prayers:
        conn.execute(
            "INSERT OR REPLACE INTO prayer_times (date, prayer, adhan, iqama) VALUES (?, ?, ?, ?)",
            (date_str, p['name'], p['adhan'], p['iqama'])
        )
    conn.commit()
    conn.close()


def get_prayer_times_for_date(date_str):
    """Get prayer times for a date. Returns [{name, adhan, iqama}, ...] ordered by adhan."""
    try:
        conn = _connect()
        cur = conn.execute(
            "SELECT prayer, adhan, iqama FROM prayer_times WHERE date = ? ORDER BY adhan",
            (date_str,)
        )
        rows = [{'name': r[0], 'adhan': r[1], 'iqama': r[2]} for r in cur.fetchall()]
        conn.close()
        return rows
    except Exception:
        return []


def has_prayer_times(date_str):
    """Check if prayer times exist for a date."""
    try:
        conn = _connect()
        cur = conn.execute("SELECT COUNT(*) FROM prayer_times WHERE date = ?", (date_str,))
        count = cur.fetchone()[0]
        conn.close()
        return count > 0
    except Exception:
        return False


def cleanup_old_prayer_times():
    """Delete prayer times older than 7 days."""
    try:
        conn = _connect()
        conn.execute("DELETE FROM prayer_times WHERE date < date('now', '-7 days')")
        conn.commit()
        conn.close()
    except Exception:
        pass


# --- Users ---

def get_users():
    try:
        conn = _connect()
        cur = conn.execute("SELECT id, name, emoji FROM users ORDER BY name")
        rows = [{"id": r[0], "name": r[1], "emoji": r[2]} for r in cur.fetchall()]
        conn.close()
        return rows
    except Exception:
        return []


def create_user(name, emoji='🙂'):
    conn = _connect()
    cur = conn.execute(
        "INSERT INTO users (name, emoji) VALUES (?, ?)",
        (name, emoji)
    )
    user_id = cur.lastrowid
    conn.commit()
    conn.close()
    return user_id


def update_user(user_id, name, emoji):
    conn = _connect()
    conn.execute(
        "UPDATE users SET name = ?, emoji = ? WHERE id = ?",
        (name, emoji, user_id)
    )
    conn.commit()
    conn.close()


def delete_user(user_id):
    conn = _connect()
    conn.execute("DELETE FROM prayer_logs WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()


# --- Prayer Logs ---

def _is_on_time(prayer, date_str):
    """A log is 'on time' iff it's logged for today within the prayer's adhan
    window — `[adhan, next prayer's adhan)`. Backlog logs (date != today) are
    always off-time: we can't know whether the user actually prayed within
    the window, so they don't count toward on-time or perfect_day trackers."""
    today = datetime.now().strftime('%Y-%m-%d')
    if date_str != today:
        return False
    times = get_prayer_times_for_date(date_str)
    if not times:
        return False
    now = datetime.now()
    target_idx = next((i for i, p in enumerate(times) if p['name'] == prayer), -1)
    if target_idx < 0:
        return False
    try:
        adhan_dt = datetime.strptime(f"{date_str} {times[target_idx]['adhan']}", "%Y-%m-%d %H:%M")
    except ValueError:
        return False
    if now < adhan_dt:
        return False
    if target_idx + 1 < len(times):
        try:
            next_dt = datetime.strptime(f"{date_str} {times[target_idx + 1]['adhan']}", "%Y-%m-%d %H:%M")
            return now < next_dt
        except ValueError:
            return True
    return True


def log_prayer(user_id, prayer, date, in_group=False):
    """Insert a prayer log and return the canonical row dict (or None if
    the row already existed — UNIQUE conflict)."""
    on_time = 1 if _is_on_time(prayer, date) else 0
    conn = _connect()
    cur = conn.execute(
        "INSERT OR IGNORE INTO prayer_logs (user_id, prayer, date, on_time, in_group) VALUES (?, ?, ?, ?, ?)",
        (user_id, prayer, date, on_time, 1 if in_group else 0)
    )
    inserted = cur.rowcount > 0
    conn.commit()
    conn.close()
    if not inserted:
        return None
    return {
        "user_id": user_id,
        "prayer": prayer,
        "date": date,
        "on_time": bool(on_time),
        "in_group": bool(in_group),
    }


# --- Tracker state ---

def fetch_user_history(user_id):
    """Full prayer history for a user, ordered chronologically — used by
    every tracker for combo/streak math."""
    PRAYER_ORDER_SQL = (
        "CASE prayer "
        "WHEN 'Fajr' THEN 0 "
        "WHEN 'Dhuhr' THEN 1 "
        "WHEN 'Asr' THEN 2 "
        "WHEN 'Maghrib' THEN 3 "
        "WHEN 'Isha' THEN 4 "
        "ELSE 5 END"
    )
    try:
        conn = _connect()
        cur = conn.execute(
            f"SELECT user_id, prayer, date, on_time, in_group FROM prayer_logs "
            f"WHERE user_id = ? ORDER BY date, {PRAYER_ORDER_SQL}",
            (user_id,)
        )
        rows = [
            {"user_id": r[0], "prayer": r[1], "date": r[2],
             "on_time": bool(r[3]), "in_group": bool(r[4])}
            for r in cur.fetchall()
        ]
        conn.close()
        return rows
    except Exception:
        return []


def get_tracker_state(user_id, tracker_id):
    """Return {total, current_combo, best_combo} for a user/tracker
    pair — zeros if no row yet."""
    try:
        conn = _connect()
        cur = conn.execute(
            "SELECT total, current_combo, best_combo FROM tracker_state "
            "WHERE user_id = ? AND tracker_id = ?",
            (user_id, tracker_id)
        )
        row = cur.fetchone()
        conn.close()
        if not row:
            return {"total": 0, "current_combo": 0, "best_combo": 0}
        return {"total": row[0], "current_combo": row[1], "best_combo": row[2]}
    except Exception:
        return {"total": 0, "current_combo": 0, "best_combo": 0}


def update_tracker_state(user_id, tracker_id, *, total, current_combo, best_combo):
    """Upsert the tracker_state row. Caller computes the new values."""
    try:
        conn = _connect()
        conn.execute(
            "INSERT INTO tracker_state (user_id, tracker_id, total, current_combo, best_combo) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(user_id, tracker_id) DO UPDATE SET "
            "total=excluded.total, current_combo=excluded.current_combo, best_combo=excluded.best_combo",
            (user_id, tracker_id, total, current_combo, best_combo)
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


def get_all_tracker_states(user_id):
    """All tracker rows for a user — used by the dashboard to render
    the current `x{total}` badges."""
    try:
        conn = _connect()
        cur = conn.execute(
            "SELECT tracker_id, total, current_combo, best_combo FROM tracker_state "
            "WHERE user_id = ?",
            (user_id,)
        )
        rows = {r[0]: {"total": r[1], "current_combo": r[2], "best_combo": r[3]} for r in cur.fetchall()}
        conn.close()
        return rows
    except Exception:
        return {}


def unlog_prayer(user_id, prayer, date):
    conn = _connect()
    conn.execute(
        "DELETE FROM prayer_logs WHERE user_id = ? AND prayer = ? AND date = ?",
        (user_id, prayer, date)
    )
    conn.commit()
    conn.close()


def get_prayer_logs_for_user_date(user_id, date_str):
    """Returns list of prayer names logged by a user for a given date."""
    try:
        conn = _connect()
        cur = conn.execute(
            "SELECT prayer FROM prayer_logs WHERE user_id = ? AND date = ?",
            (user_id, date_str)
        )
        prayers = [r[0] for r in cur.fetchall()]
        conn.close()
        return prayers
    except Exception:
        return []


def get_prayer_logs_for_date(date_str):
    """Returns {prayer: [user_id, ...]} for a given date."""
    try:
        conn = _connect()
        cur = conn.execute(
            "SELECT prayer, user_id FROM prayer_logs WHERE date = ?",
            (date_str,)
        )
        result = defaultdict(list)
        for prayer, user_id in cur.fetchall():
            result[prayer].append(user_id)
        conn.close()
        return dict(result)
    except Exception:
        return {}


def get_prayer_stats(user_id=None, period='month'):
    """Get prayer stats. period: 'month', 'year', 'all'."""
    try:
        conn = _connect()
        if period == 'month':
            date_filter = "date >= date('now', 'start of month')"
        elif period == 'year':
            date_filter = "date >= date('now', '-365 days')"
        else:
            date_filter = "1=1"

        if user_id:
            cur = conn.execute(
                f"SELECT date, prayer FROM prayer_logs WHERE user_id = ? AND {date_filter} ORDER BY date",
                (user_id,)
            )
        else:
            cur = conn.execute(
                f"SELECT user_id, date, prayer FROM prayer_logs WHERE {date_filter} ORDER BY date"
            )

        rows = cur.fetchall()
        conn.close()

        if user_id:
            # Heatmap data: {date: count}
            heatmap = defaultdict(int)
            for date, prayer in rows:
                heatmap[date] += 1
            return dict(heatmap)
        else:
            # Leaderboard: {user_id: total_count}
            leaderboard = defaultdict(int)
            for uid, date, prayer in rows:
                leaderboard[uid] += 1
            return dict(leaderboard)
    except Exception:
        return {}


def get_user_streak(user_id):
    """Get current streak (consecutive days with all 5 prayers logged)."""
    try:
        conn = _connect()
        cur = conn.execute(
            "SELECT date FROM prayer_logs WHERE user_id = ? GROUP BY date HAVING COUNT(*) = 5 ORDER BY date DESC",
            (user_id,)
        )
        dates = [r[0] for r in cur.fetchall()]
        conn.close()

        if not dates:
            return 0

        from datetime import datetime, timedelta
        streak = 0
        today = datetime.now().strftime('%Y-%m-%d')
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        # Start from today, or yesterday if not all 5 done today yet
        if dates[0] == today:
            expected = today
        elif dates[0] == yesterday:
            expected = yesterday
        else:
            return 0
        for d in dates:
            if d == expected:
                streak += 1
                prev = datetime.strptime(d, '%Y-%m-%d') - timedelta(days=1)
                expected = prev.strftime('%Y-%m-%d')
            else:
                break
        return streak
    except Exception:
        return 0
