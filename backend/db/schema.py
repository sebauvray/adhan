import sqlite3
import os

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

CREATE TABLE IF NOT EXISTS music_assistant (
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
    prayer        TEXT PRIMARY KEY,
    volume        INTEGER NOT NULL DEFAULT 30,
    alert_enabled INTEGER NOT NULL DEFAULT 0,
    alert_delay   INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS prayer_outputs (
    prayer      TEXT NOT NULL,
    output_id   TEXT NOT NULL,
    output_name TEXT NOT NULL,
    PRIMARY KEY (prayer, output_id)
);

CREATE TABLE IF NOT EXISTS prayer_times (
    date    TEXT NOT NULL,
    prayer  TEXT NOT NULL,
    adhan   TEXT NOT NULL,
    iqama   TEXT NOT NULL,
    PRIMARY KEY (date, prayer)
);

CREATE TABLE IF NOT EXISTS api_tokens (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    token       TEXT    UNIQUE NOT NULL,
    description TEXT,
    scope       TEXT    NOT NULL DEFAULT 'admin',
    user_id     INTEGER,
    created_at  TEXT    DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS users (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT    NOT NULL,
    emoji      TEXT    NOT NULL DEFAULT '🙂',
    created_at TEXT    DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS prayer_logs (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL,
    prayer     TEXT    NOT NULL,
    date       TEXT    NOT NULL,
    created_at TEXT    DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE (user_id, prayer, date)
);

CREATE TABLE IF NOT EXISTS auth (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT    UNIQUE NOT NULL,
    password_hash TEXT    NOT NULL,
    user_id       INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at    TEXT    DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    auth_id    INTEGER NOT NULL,
    created_at TEXT DEFAULT (datetime('now')),
    expires_at TEXT NOT NULL,
    last_seen  TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (auth_id) REFERENCES auth(id) ON DELETE CASCADE
);
"""


def get_db_path():
    return os.environ.get('DB_PATH', '/app/data/adhan.db')


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
            'ALERT_FILE': '/srv/media/alert.mp3',
        },
        'music_assistant': {
            'HOST': 'host.docker.internal',
            'PORT': '8095',
        },
        'config': {
            'LOG_LEVEL': 'INFO',
            'QUIET_START': '21:00',
            'QUIET_END': '07:00',
            'QUIET_VOLUME': '10',
            'MULTI_DAY_DISPLAY': 'false',
            'AUDIO_PROVIDER': 'owntone',
            'AUDIO_PROVIDER_MODE': 'bundled',
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


def _migrate_alert_columns(conn):
    """Add alert_enabled and alert_delay columns to prayer_config if missing."""
    try:
        cur = conn.execute("PRAGMA table_info(prayer_config)")
        columns = [row[1] for row in cur.fetchall()]
        if 'alert_enabled' not in columns:
            conn.execute("ALTER TABLE prayer_config ADD COLUMN alert_enabled INTEGER NOT NULL DEFAULT 0")
        if 'alert_delay' not in columns:
            conn.execute("ALTER TABLE prayer_config ADD COLUMN alert_delay INTEGER NOT NULL DEFAULT 0")
        conn.commit()
    except Exception:
        pass


def _migrate_token_scope(conn):
    """Add scope and user_id columns to api_tokens if missing."""
    try:
        cur = conn.execute("PRAGMA table_info(api_tokens)")
        columns = [row[1] for row in cur.fetchall()]
        if 'scope' not in columns:
            conn.execute("ALTER TABLE api_tokens ADD COLUMN scope TEXT NOT NULL DEFAULT 'admin'")
        if 'user_id' not in columns:
            conn.execute("ALTER TABLE api_tokens ADD COLUMN user_id INTEGER REFERENCES users(id) ON DELETE CASCADE")
        conn.commit()
    except Exception:
        pass


def _migrate_hash_tokens(conn):
    """Hash any plaintext tokens left in the api_tokens table.
    A SHA-256 hex digest is exactly 64 characters; anything else is plaintext."""
    import hashlib
    try:
        cur = conn.execute("SELECT id, token FROM api_tokens")
        rows = cur.fetchall()
        for token_id, value in rows:
            if not value or (len(value) == 64 and all(c in '0123456789abcdef' for c in value)):
                continue
            hashed = hashlib.sha256(value.encode('utf-8')).hexdigest()
            conn.execute("UPDATE api_tokens SET token = ? WHERE id = ?", (hashed, token_id))
        conn.commit()
    except Exception:
        pass


def _migrate_audio_provider(conn):
    """Migrate the legacy OWNTONE_MODE / 'local' values to the generic
    AUDIO_PROVIDER + AUDIO_PROVIDER_MODE pair shared by all providers."""
    try:
        cur = conn.execute(
            "SELECT key, value FROM config WHERE key IN ('OWNTONE_MODE', 'AUDIO_PROVIDER_MODE', 'AUDIO_PROVIDER')"
        )
        rows = dict(cur.fetchall())

        if 'AUDIO_PROVIDER' not in rows:
            conn.execute(
                "INSERT OR IGNORE INTO config (key, value) VALUES ('AUDIO_PROVIDER', 'owntone')"
            )

        legacy = rows.get('OWNTONE_MODE')
        if legacy is not None and 'AUDIO_PROVIDER_MODE' not in rows:
            new_value = 'bundled' if legacy in ('local', 'bundled') else 'external'
            conn.execute(
                "INSERT OR IGNORE INTO config (key, value) VALUES ('AUDIO_PROVIDER_MODE', ?)",
                (new_value,),
            )
            conn.execute("DELETE FROM config WHERE key = 'OWNTONE_MODE'")
        conn.commit()
    except Exception:
        pass


def _migrate_auth_user_id(conn):
    """Add user_id column to auth if missing (links admin to a tracking user)."""
    try:
        cur = conn.execute("PRAGMA table_info(auth)")
        columns = [row[1] for row in cur.fetchall()]
        if 'user_id' not in columns:
            conn.execute("ALTER TABLE auth ADD COLUMN user_id INTEGER REFERENCES users(id) ON DELETE SET NULL")
            conn.commit()
    except Exception:
        pass


def init_db():
    db_path = get_db_path()
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)
    _ensure_defaults(conn)
    _migrate_env_to_db(conn)
    _migrate_alert_columns(conn)
    _migrate_token_scope(conn)
    _migrate_hash_tokens(conn)
    _migrate_auth_user_id(conn)
    _migrate_audio_provider(conn)
    conn.close()
