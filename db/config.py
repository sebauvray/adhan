import sqlite3
import secrets
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


def get_prayer_volume(prayer, default=40):
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
