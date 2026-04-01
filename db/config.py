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
