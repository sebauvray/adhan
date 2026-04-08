import sqlite3
import secrets
from collections import defaultdict
from db.schema import get_db_path


def _connect():
    return sqlite3.connect(get_db_path())


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


def get_token():
    try:
        conn = _connect()
        cur = conn.execute("SELECT token FROM api_tokens LIMIT 1")
        row = cur.fetchone()
        conn.close()
        return row[0] if row else None
    except Exception:
        return None


def create_token(description="default"):
    token = secrets.token_urlsafe(32)
    conn = _connect()
    conn.execute(
        "INSERT INTO api_tokens (token, description) VALUES (?, ?)",
        (token, description)
    )
    conn.commit()
    conn.close()
    return token


def validate_token(token):
    if not token:
        return False
    try:
        conn = _connect()
        cur = conn.execute("SELECT id FROM api_tokens WHERE token = ?", (token,))
        row = cur.fetchone()
        conn.close()
        return row is not None
    except Exception:
        return False


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

def log_prayer(user_id, prayer, date):
    conn = _connect()
    conn.execute(
        "INSERT OR IGNORE INTO prayer_logs (user_id, prayer, date) VALUES (?, ?, ?)",
        (user_id, prayer, date)
    )
    conn.commit()
    conn.close()


def unlog_prayer(user_id, prayer, date):
    conn = _connect()
    conn.execute(
        "DELETE FROM prayer_logs WHERE user_id = ? AND prayer = ? AND date = ?",
        (user_id, prayer, date)
    )
    conn.commit()
    conn.close()


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
            date_filter = "date >= date('now', 'start of year')"
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
    """Get current streak (consecutive days with at least one prayer)."""
    try:
        conn = _connect()
        cur = conn.execute(
            "SELECT DISTINCT date FROM prayer_logs WHERE user_id = ? ORDER BY date DESC",
            (user_id,)
        )
        dates = [r[0] for r in cur.fetchall()]
        conn.close()

        if not dates:
            return 0

        from datetime import datetime, timedelta
        streak = 0
        expected = datetime.now().strftime('%Y-%m-%d')
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
