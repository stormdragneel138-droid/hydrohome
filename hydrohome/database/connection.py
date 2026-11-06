"""SQLite connection handling and schema creation."""
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from hydrohome import config
from hydrohome.database.web_schema import WEB_SCHEMA
from hydrohome.errors import DatabaseError

SCHEMA = """
CREATE TABLE IF NOT EXISTS households (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    name                TEXT    NOT NULL UNIQUE,
    address             TEXT    NOT NULL DEFAULT '',
    city                TEXT    NOT NULL,
    members             INTEGER NOT NULL CHECK (members > 0),
    daily_target_liters INTEGER NOT NULL CHECK (daily_target_liters > 0),
    latitude            REAL,
    longitude           REAL,
    created_at          TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS water_readings (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    household_id INTEGER NOT NULL REFERENCES households(id) ON DELETE CASCADE,
    reading_date TEXT    NOT NULL,
    meter_reading REAL   NOT NULL CHECK (meter_reading >= 0),
    notes        TEXT    NOT NULL DEFAULT '',
    UNIQUE (household_id, reading_date)
);

CREATE TABLE IF NOT EXISTS reminders (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    household_id  INTEGER NOT NULL REFERENCES households(id) ON DELETE CASCADE,
    title         TEXT    NOT NULL,
    reminder_type TEXT    NOT NULL,
    due_at        TEXT    NOT NULL,
    repeat_rule   TEXT    NOT NULL DEFAULT 'None',
    status        TEXT    NOT NULL DEFAULT 'Pending',
    notes         TEXT    NOT NULL DEFAULT '',
    last_notified TEXT
);

CREATE TABLE IF NOT EXISTS meter_sources (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    household_id     INTEGER NOT NULL UNIQUE REFERENCES households(id) ON DELETE CASCADE,
    source_type      TEXT    NOT NULL,
    location         TEXT    NOT NULL,
    api_key          TEXT    NOT NULL DEFAULT '',
    reading_path     TEXT    NOT NULL,
    unit             TEXT    NOT NULL DEFAULT 'm3',
    interval_minutes INTEGER NOT NULL DEFAULT 60,
    enabled          INTEGER NOT NULL DEFAULT 1,
    last_sync_at     TEXT,
    last_status      TEXT    NOT NULL DEFAULT 'Never synced'
);

CREATE INDEX IF NOT EXISTS idx_readings_hh_date ON water_readings (household_id, reading_date);
CREATE INDEX IF NOT EXISTS idx_reminders_due    ON reminders (status, due_at);
"""


@contextmanager
def get_connection(db_path=None):
    """Yield a connection; commit on success, roll back and wrap errors on failure."""
    conn = None
    try:
        conn = sqlite3.connect(str(db_path or config.DB_PATH))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        yield conn
        conn.commit()
    except sqlite3.IntegrityError as exc:
        if conn:
            conn.rollback()
        raise DatabaseError(
            "That change breaks a rule in the database (for example a duplicate "
            "household name or a second reading on the same date)."
        ) from exc
    except sqlite3.Error as exc:
        if conn:
            conn.rollback()
        raise DatabaseError(f"Database error: {exc}") from exc
    except Exception:
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()


def initialize(db_path=None):
    """Create the data folder and all tables if they do not exist yet."""
    path = Path(db_path or config.DB_PATH)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise DatabaseError(f"Cannot create the data folder: {exc}") from exc
    with get_connection(path) as conn:
        conn.executescript(SCHEMA)
        conn.executescript(WEB_SCHEMA)   # tables used by the REST API / web dashboard
