import sqlite3
import os
import json

DB_PATH = os.environ.get('DB_PATH', '/app/data/adhan.db')

SCHEMA = """
CREATE TABLE IF NOT EXISTS config (
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS owntone (
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS homepods (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    name      TEXT    UNIQUE NOT NULL,
    morning   INTEGER NOT NULL DEFAULT 0,
    afternoon INTEGER NOT NULL DEFAULT 1,
    evening   INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS prayer_config (
    prayer TEXT PRIMARY KEY,
    volume INTEGER NOT NULL DEFAULT 30
);

CREATE TABLE IF NOT EXISTS prayer_outputs (
    prayer      TEXT NOT NULL,
    output_id   TEXT NOT NULL,
    output_name TEXT NOT NULL,
    PRIMARY KEY (prayer, output_id)
);

CREATE TABLE IF NOT EXISTS api_tokens (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    token       TEXT    UNIQUE NOT NULL,
    description TEXT,
    created_at  TEXT    DEFAULT (datetime('now'))
);
"""


def get_db_path():
    return os.environ.get('DB_PATH', '/app/data/adhan.db')


def _migrate_homepod_json(conn):
    """Migre HomePod.json vers la table homepods si elle est vide."""
    homepod_file = os.environ.get('HOMEPOD_FILE', '/app/HomePod.json')
    if not os.path.exists(homepod_file):
        return
    cur = conn.execute("SELECT COUNT(*) FROM homepods")
    if cur.fetchone()[0] > 0:
        return
    try:
        with open(homepod_file) as f:
            data = json.load(f)
        for pod in data.get('ListHomePod', []):
            conn.execute(
                "INSERT OR IGNORE INTO homepods (name, morning, afternoon, evening) VALUES (?, ?, ?, ?)",
                (pod['name'], int(pod.get('morning', False)),
                 int(pod.get('afternoon', True)), int(pod.get('evening', False)))
            )
        conn.commit()
        print(f"Migration HomePod.json → SQLite : {len(data.get('ListHomePod', []))} appareils importés")
    except Exception as e:
        print(f"Avertissement migration HomePod.json : {e}")


def _migrate_env_to_db(conn):
    """Migre les variables d'environnement vers SQLite au premier lancement."""
    cur = conn.execute("SELECT COUNT(*) FROM config")
    if cur.fetchone()[0] > 0:
        return

    env_map = {
        'config': {
            'MOSQUE_URL': os.environ.get('MOSQUE_URL', ''),
            'LOG_LEVEL': os.environ.get('LOG_LEVEL', 'INFO'),
            'MORNING_TIME': os.environ.get('MORNING_TIME', '07:00-11:00'),
            'AFTERNOON_TIME': os.environ.get('AFTERNOON_TIME', '11:00-20:00'),
            'EVENING_TIME': os.environ.get('EVENING_TIME', '20:00-06:00'),
        },
        'owntone': {
            'HOST': os.environ.get('OWNTONE_HOST', 'host.docker.internal'),
            'PORT': os.environ.get('OWNTONE_PORT', '3689'),
            'ADHAN_FILE': os.environ.get('ADHAN_FILE', '/srv/media/adhan.mp3'),
            'ADHAN_VOLUME': os.environ.get('ADHAN_VOLUME', '40'),
        },
    }
    for table, values in env_map.items():
        for key, value in values.items():
            if value:
                conn.execute(
                    f"INSERT OR IGNORE INTO [{table}] (key, value) VALUES (?, ?)",
                    (key, value)
                )
    conn.commit()


def _ensure_defaults(conn):
    """Ensure essential default values exist in the database."""
    defaults = {
        'owntone': {
            'HOST': 'host.docker.internal',
            'PORT': '3689',
            'ADHAN_FILE': '/srv/media/adhan.mp3',
            'ADHAN_VOLUME': '40',
        },
        'config': {
            'LOG_LEVEL': 'INFO',
        },
    }
    for table, values in defaults.items():
        for key, value in values.items():
            # Insert if missing, or update if empty
            conn.execute(
                f"INSERT INTO [{table}] (key, value) VALUES (?, ?) "
                f"ON CONFLICT(key) DO UPDATE SET value = ? WHERE value = '' OR value IS NULL",
                (key, value, value)
            )
    conn.commit()


def init_db():
    db_path = get_db_path()
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)
    _ensure_defaults(conn)
    _migrate_env_to_db(conn)
    _migrate_homepod_json(conn)
    conn.close()
