"""Extra tables used by the REST API and web dashboard.

Every statement uses CREATE ... IF NOT EXISTS, so it is safe to run against your
existing hydrohome.db: your households, readings, reminders and meter data are not touched.
"""

WEB_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL,
    email         TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    created_at    TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS auth_tokens (
    token_hash TEXT PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    expires_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS household_members (
    household_id INTEGER NOT NULL REFERENCES households(id) ON DELETE CASCADE,
    user_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role         TEXT NOT NULL DEFAULT 'admin',
    PRIMARY KEY (household_id, user_id)
);

CREATE TABLE IF NOT EXISTS water_sources (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    household_id INTEGER NOT NULL REFERENCES households(id) ON DELETE CASCADE,
    name         TEXT NOT NULL COLLATE NOCASE,
    color        TEXT NOT NULL DEFAULT '#267e78',
    enabled      INTEGER NOT NULL DEFAULT 1,
    created_at   TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    UNIQUE (household_id, name)
);

CREATE TABLE IF NOT EXISTS daily_usage (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    household_id INTEGER NOT NULL REFERENCES households(id) ON DELETE CASCADE,
    source_id    INTEGER NOT NULL REFERENCES water_sources(id) ON DELETE CASCADE,
    usage_date   TEXT NOT NULL,
    liters       REAL NOT NULL CHECK (liters >= 0),
    notes        TEXT NOT NULL DEFAULT '',
    created_by   INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at   TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS consumption_limits (
    household_id        INTEGER PRIMARY KEY REFERENCES households(id) ON DELETE CASCADE,
    daily_limit_liters  REAL NOT NULL CHECK (daily_limit_liters > 0),
    weekly_limit_liters REAL NOT NULL CHECK (weekly_limit_liters > 0),
    alert_threshold_pct INTEGER NOT NULL DEFAULT 90,
    spike_multiplier    REAL NOT NULL DEFAULT 1.5,
    rate_per_1000_l     REAL NOT NULL DEFAULT 3.0,
    currency            TEXT NOT NULL DEFAULT '$',
    updated_at          TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS notification_settings (
    household_id  INTEGER PRIMARY KEY REFERENCES households(id) ON DELETE CASCADE,
    push_enabled  INTEGER NOT NULL DEFAULT 1,
    email_enabled INTEGER NOT NULL DEFAULT 1,
    quiet_start   TEXT NOT NULL DEFAULT '22:00',
    quiet_end     TEXT NOT NULL DEFAULT '06:00'
);

CREATE TABLE IF NOT EXISTS alerts (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    household_id INTEGER NOT NULL REFERENCES households(id) ON DELETE CASCADE,
    kind         TEXT NOT NULL,
    severity     TEXT NOT NULL DEFAULT 'warning',
    title        TEXT NOT NULL,
    message      TEXT NOT NULL,
    source_id    INTEGER REFERENCES water_sources(id) ON DELETE SET NULL,
    usage_date   TEXT NOT NULL,
    liters       REAL,
    status       TEXT NOT NULL DEFAULT 'open',
    is_read      INTEGER NOT NULL DEFAULT 0,
    dedupe_key   TEXT NOT NULL,
    detected_at  TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    resolved_at  TEXT,
    UNIQUE (household_id, dedupe_key)
);

CREATE TABLE IF NOT EXISTS reminder_schedules (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    household_id  INTEGER NOT NULL REFERENCES households(id) ON DELETE CASCADE,
    title         TEXT NOT NULL,
    reminder_type TEXT NOT NULL DEFAULT 'Usage Check-in',
    days          TEXT NOT NULL DEFAULT 'daily',
    time_of_day   TEXT NOT NULL,
    channel       TEXT NOT NULL DEFAULT 'Push notification',
    notes         TEXT NOT NULL DEFAULT '',
    enabled       INTEGER NOT NULL DEFAULT 1,
    last_fired_on TEXT,
    created_at    TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS push_subscriptions (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    endpoint   TEXT NOT NULL UNIQUE,
    p256dh     TEXT NOT NULL,
    auth       TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS app_secrets (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_usage_hh_date   ON daily_usage (household_id, usage_date);
CREATE INDEX IF NOT EXISTS idx_alerts_hh       ON alerts (household_id, status);
CREATE INDEX IF NOT EXISTS idx_schedules_hh    ON reminder_schedules (household_id, enabled);
"""
