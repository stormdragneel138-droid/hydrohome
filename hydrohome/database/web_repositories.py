"""Repositories for the REST API tables. As elsewhere in the project, this is the only
place SQL is written and every query is parameterized."""
from hydrohome.database.repositories import BaseRepository


class UserRepository(BaseRepository):
    def add(self, name, email, password_hash):
        rid, _ = self._execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (name, email, password_hash))
        return rid

    def get(self, user_id):
        rows = self._query("SELECT * FROM users WHERE id = ?", (user_id,))
        return rows[0] if rows else None

    def get_by_email(self, email):
        rows = self._query("SELECT * FROM users WHERE email = ?", (email,))
        return rows[0] if rows else None

    def count(self):
        return self._query("SELECT COUNT(*) AS n FROM users")[0]["n"]

    def update_name(self, user_id, name):
        self._execute("UPDATE users SET name = ? WHERE id = ?", (name, user_id))

    def update_password(self, user_id, password_hash):
        self._execute("UPDATE users SET password_hash = ? WHERE id = ?", (password_hash, user_id))


class TokenRepository(BaseRepository):
    def add(self, token_hash, user_id, expires_at):
        self._execute("INSERT INTO auth_tokens (token_hash, user_id, expires_at) VALUES (?, ?, ?)",
                      (token_hash, user_id, expires_at))

    def get(self, token_hash):
        rows = self._query("SELECT * FROM auth_tokens WHERE token_hash = ?", (token_hash,))
        return rows[0] if rows else None

    def delete(self, token_hash):
        self._execute("DELETE FROM auth_tokens WHERE token_hash = ?", (token_hash,))

    def purge_expired(self, now_text):
        self._execute("DELETE FROM auth_tokens WHERE expires_at < ?", (now_text,))


class MembershipRepository(BaseRepository):
    def link(self, household_id, user_id, role="admin"):
        self._execute("INSERT OR IGNORE INTO household_members (household_id, user_id, role) "
                      "VALUES (?, ?, ?)", (household_id, user_id, role))

    def role_of(self, household_id, user_id):
        rows = self._query("SELECT role FROM household_members WHERE household_id = ? "
                           "AND user_id = ?", (household_id, user_id))
        return rows[0]["role"] if rows else None

    def households_for_user(self, user_id):
        return self._query(
            "SELECT h.*, m.role FROM households h JOIN household_members m "
            "ON m.household_id = h.id WHERE m.user_id = ? ORDER BY h.name COLLATE NOCASE",
            (user_id,))

    def unowned_households(self):
        return self._query(
            "SELECT * FROM households WHERE id NOT IN (SELECT household_id FROM household_members) "
            "ORDER BY name COLLATE NOCASE")

    def all_household_ids(self):
        return [r["id"] for r in self._query("SELECT id FROM households")]


class WaterSourceRepository(BaseRepository):
    def add(self, household_id, name, color, enabled=True):
        rid, _ = self._execute(
            "INSERT INTO water_sources (household_id, name, color, enabled) VALUES (?, ?, ?, ?)",
            (household_id, name, color, 1 if enabled else 0))
        return rid

    def get(self, source_id):
        rows = self._query("SELECT * FROM water_sources WHERE id = ?", (source_id,))
        return rows[0] if rows else None

    def for_household(self, household_id):
        return self._query("SELECT * FROM water_sources WHERE household_id = ? ORDER BY id",
                           (household_id,))

    def find_by_name(self, household_id, name):
        rows = self._query("SELECT * FROM water_sources WHERE household_id = ? AND name = ?",
                           (household_id, name))
        return rows[0] if rows else None

    def update(self, source_id, name, color, enabled):
        _, n = self._execute("UPDATE water_sources SET name = ?, color = ?, enabled = ? "
                             "WHERE id = ?", (name, color, 1 if enabled else 0, source_id))
        return n

    def delete(self, source_id):
        _, n = self._execute("DELETE FROM water_sources WHERE id = ?", (source_id,))
        return n

    def usage_count(self, source_id):
        return self._query("SELECT COUNT(*) AS n FROM daily_usage WHERE source_id = ?",
                           (source_id,))[0]["n"]


class UsageRepository(BaseRepository):
    _SELECT = ("SELECT u.*, s.name AS source_name, s.color AS source_color "
               "FROM daily_usage u JOIN water_sources s ON s.id = u.source_id ")

    def add(self, household_id, source_id, usage_date, liters, notes, created_by):
        rid, _ = self._execute(
            "INSERT INTO daily_usage (household_id, source_id, usage_date, liters, notes, created_by) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (household_id, source_id, usage_date, liters, notes, created_by))
        return rid

    def get(self, usage_id):
        rows = self._query(self._SELECT + "WHERE u.id = ?", (usage_id,))
        return rows[0] if rows else None

    def update(self, usage_id, source_id, usage_date, liters, notes):
        _, n = self._execute(
            "UPDATE daily_usage SET source_id = ?, usage_date = ?, liters = ?, notes = ? "
            "WHERE id = ?", (source_id, usage_date, liters, notes, usage_id))
        return n

    def delete(self, usage_id):
        _, n = self._execute("DELETE FROM daily_usage WHERE id = ?", (usage_id,))
        return n

    def list(self, household_id, start=None, end=None, source_id=None, limit=50, offset=0):
        return self._query(
            self._SELECT + "WHERE u.household_id = ? AND (? IS NULL OR u.usage_date >= ?) "
            "AND (? IS NULL OR u.usage_date <= ?) AND (? IS NULL OR u.source_id = ?) "
            "ORDER BY u.usage_date DESC, u.id DESC LIMIT ? OFFSET ?",
            (household_id, start, start, end, end, source_id, source_id, limit, offset))

    def count(self, household_id, start=None, end=None, source_id=None):
        return self._query(
            "SELECT COUNT(*) AS n FROM daily_usage WHERE household_id = ? "
            "AND (? IS NULL OR usage_date >= ?) AND (? IS NULL OR usage_date <= ?) "
            "AND (? IS NULL OR source_id = ?)",
            (household_id, start, start, end, end, source_id, source_id))[0]["n"]

    def daily_totals(self, household_id, start, end):
        """[{usage_date, liters}] for days that have data between start and end (inclusive)."""
        return self._query(
            "SELECT usage_date, SUM(liters) AS liters FROM daily_usage WHERE household_id = ? "
            "AND usage_date BETWEEN ? AND ? GROUP BY usage_date ORDER BY usage_date",
            (household_id, start, end))

    def source_totals(self, household_id, start, end):
        return self._query(
            "SELECT s.id AS source_id, s.name, s.color, SUM(u.liters) AS liters "
            "FROM daily_usage u JOIN water_sources s ON s.id = u.source_id "
            "WHERE u.household_id = ? AND u.usage_date BETWEEN ? AND ? "
            "GROUP BY s.id ORDER BY liters DESC", (household_id, start, end))

    def source_daily(self, household_id, start, end):
        """[{usage_date, source_id, liters}], one row per day per source."""
        return self._query(
            "SELECT usage_date, source_id, SUM(liters) AS liters FROM daily_usage "
            "WHERE household_id = ? AND usage_date BETWEEN ? AND ? "
            "GROUP BY usage_date, source_id", (household_id, start, end))

    def breakdown_by_day(self, household_id, start, end):
        """[{usage_date, source_name, liters}] used for the history endpoint and CSV."""
        return self._query(
            "SELECT u.usage_date, s.name AS source_name, SUM(u.liters) AS liters "
            "FROM daily_usage u JOIN water_sources s ON s.id = u.source_id "
            "WHERE u.household_id = ? AND u.usage_date BETWEEN ? AND ? "
            "GROUP BY u.usage_date, s.id ORDER BY u.usage_date DESC, liters DESC",
            (household_id, start, end))


class LimitRepository(BaseRepository):
    def get(self, household_id):
        rows = self._query("SELECT * FROM consumption_limits WHERE household_id = ?",
                           (household_id,))
        return rows[0] if rows else None

    def upsert(self, household_id, d):
        self._execute(
            "INSERT INTO consumption_limits (household_id, daily_limit_liters, weekly_limit_liters, "
            "alert_threshold_pct, spike_multiplier, rate_per_1000_l, currency) "
            "VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT(household_id) DO UPDATE SET "
            "daily_limit_liters = excluded.daily_limit_liters, "
            "weekly_limit_liters = excluded.weekly_limit_liters, "
            "alert_threshold_pct = excluded.alert_threshold_pct, "
            "spike_multiplier = excluded.spike_multiplier, "
            "rate_per_1000_l = excluded.rate_per_1000_l, currency = excluded.currency, "
            "updated_at = datetime('now','localtime')",
            (household_id, d["daily_limit_liters"], d["weekly_limit_liters"],
             d["alert_threshold_pct"], d["spike_multiplier"], d["rate_per_1000_l"], d["currency"]))


class NotificationSettingsRepository(BaseRepository):
    def get(self, household_id):
        rows = self._query("SELECT * FROM notification_settings WHERE household_id = ?",
                           (household_id,))
        return rows[0] if rows else None

    def upsert(self, household_id, d):
        self._execute(
            "INSERT INTO notification_settings (household_id, push_enabled, email_enabled, "
            "quiet_start, quiet_end) VALUES (?, ?, ?, ?, ?) ON CONFLICT(household_id) DO UPDATE SET "
            "push_enabled = excluded.push_enabled, email_enabled = excluded.email_enabled, "
            "quiet_start = excluded.quiet_start, quiet_end = excluded.quiet_end",
            (household_id, 1 if d["push_enabled"] else 0, 1 if d["email_enabled"] else 0,
             d["quiet_start"], d["quiet_end"]))


class AlertRepository(BaseRepository):
    _SELECT = ("SELECT a.*, s.name AS source_name FROM alerts a "
               "LEFT JOIN water_sources s ON s.id = a.source_id ")

    def get(self, alert_id):
        rows = self._query(self._SELECT + "WHERE a.id = ?", (alert_id,))
        return rows[0] if rows else None

    def find_by_key(self, household_id, dedupe_key):
        rows = self._query(self._SELECT + "WHERE a.household_id = ? AND a.dedupe_key = ?",
                           (household_id, dedupe_key))
        return rows[0] if rows else None

    def add(self, household_id, d):
        rid, _ = self._execute(
            "INSERT INTO alerts (household_id, kind, severity, title, message, source_id, "
            "usage_date, liters, status, dedupe_key) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'open', ?)",
            (household_id, d["kind"], d["severity"], d["title"], d["message"], d.get("source_id"),
             d["usage_date"], d.get("liters"), d["dedupe_key"]))
        return rid

    def refresh(self, alert_id, d):
        """Update the text/numbers of an existing alert and (re)open it."""
        self._execute(
            "UPDATE alerts SET severity = ?, title = ?, message = ?, liters = ?, status = 'open', "
            "resolved_at = NULL, detected_at = datetime('now','localtime') WHERE id = ?",
            (d["severity"], d["title"], d["message"], d.get("liters"), alert_id))

    def set_status(self, alert_id, status):
        resolved = None if status == "open" else "datetime('now','localtime')"
        sql = ("UPDATE alerts SET status = ?, is_read = 1, resolved_at = "
               + (resolved or "NULL") + " WHERE id = ?")
        _, n = self._execute(sql, (status, alert_id))
        return n

    def list(self, household_id, statuses=None, kinds=None, limit=50):
        sql = self._SELECT + "WHERE a.household_id = ?"
        params = [household_id]
        if statuses:
            sql += " AND a.status IN (%s)" % ",".join("?" * len(statuses))
            params += list(statuses)
        if kinds:
            sql += " AND a.kind IN (%s)" % ",".join("?" * len(kinds))
            params += list(kinds)
        sql += (" ORDER BY CASE a.severity WHEN 'critical' THEN 0 WHEN 'warning' THEN 1 ELSE 2 END, "
                "a.detected_at DESC, a.id DESC LIMIT ?")
        params.append(limit)
        return self._query(sql, params)

    def recent(self, household_id, limit=10):
        return self._query(self._SELECT + "WHERE a.household_id = ? AND a.status != 'resolved' "
                           "ORDER BY a.detected_at DESC, a.id DESC LIMIT ?", (household_id, limit))

    def open_for_date(self, household_id, usage_date, kinds):
        return self._query(
            self._SELECT + "WHERE a.household_id = ? AND a.usage_date = ? AND a.status = 'open' "
            "AND a.kind IN (%s)" % ",".join("?" * len(kinds)),
            [household_id, usage_date, *kinds])

    def count(self, household_id, status="open", kinds=None, exclude_kinds=None, unread=False):
        sql = "SELECT COUNT(*) AS n FROM alerts WHERE household_id = ? AND status = ?"
        params = [household_id, status]
        if kinds:
            sql += " AND kind IN (%s)" % ",".join("?" * len(kinds))
            params += list(kinds)
        if exclude_kinds:
            sql += " AND kind NOT IN (%s)" % ",".join("?" * len(exclude_kinds))
            params += list(exclude_kinds)
        if unread:
            sql += " AND is_read = 0"
        return self._query(sql, params)[0]["n"]

    def mark_all_read(self, household_id):
        _, n = self._execute("UPDATE alerts SET is_read = 1 WHERE household_id = ? AND is_read = 0",
                             (household_id,))
        return n

    def delete(self, alert_id):
        _, n = self._execute("DELETE FROM alerts WHERE id = ?", (alert_id,))
        return n


class ScheduleRepository(BaseRepository):
    def add(self, household_id, d):
        rid, _ = self._execute(
            "INSERT INTO reminder_schedules (household_id, title, reminder_type, days, time_of_day, "
            "channel, notes, enabled) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (household_id, d["title"], d["reminder_type"], d["days"], d["time_of_day"],
             d["channel"], d["notes"], 1 if d["enabled"] else 0))
        return rid

    def get(self, schedule_id):
        rows = self._query("SELECT * FROM reminder_schedules WHERE id = ?", (schedule_id,))
        return rows[0] if rows else None

    def for_household(self, household_id):
        return self._query("SELECT * FROM reminder_schedules WHERE household_id = ? "
                           "ORDER BY time_of_day, id", (household_id,))

    def all_enabled(self):
        return self._query("SELECT * FROM reminder_schedules WHERE enabled = 1")

    def update(self, schedule_id, d):
        _, n = self._execute(
            "UPDATE reminder_schedules SET title = ?, reminder_type = ?, days = ?, time_of_day = ?, "
            "channel = ?, notes = ?, enabled = ? WHERE id = ?",
            (d["title"], d["reminder_type"], d["days"], d["time_of_day"], d["channel"],
             d["notes"], 1 if d["enabled"] else 0, schedule_id))
        return n

    def mark_fired(self, schedule_id, day_text):
        self._execute("UPDATE reminder_schedules SET last_fired_on = ? WHERE id = ?",
                      (day_text, schedule_id))

    def delete(self, schedule_id):
        _, n = self._execute("DELETE FROM reminder_schedules WHERE id = ?", (schedule_id,))
        return n


class PushRepository(BaseRepository):
    """Browser push subscriptions (one row per browser/device) and the stored VAPID keys."""

    def upsert(self, user_id, endpoint, p256dh, auth):
        self._execute(
            "INSERT INTO push_subscriptions (user_id, endpoint, p256dh, auth) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(endpoint) DO UPDATE SET user_id = excluded.user_id, "
            "p256dh = excluded.p256dh, auth = excluded.auth",
            (user_id, endpoint, p256dh, auth))

    def remove(self, endpoint):
        self._execute("DELETE FROM push_subscriptions WHERE endpoint = ?", (endpoint,))

    def for_household(self, household_id):
        return self._query(
            "SELECT s.* FROM push_subscriptions s JOIN household_members m "
            "ON m.user_id = s.user_id WHERE m.household_id = ?", (household_id,))

    def get_secret(self, key):
        rows = self._query("SELECT value FROM app_secrets WHERE key = ?", (key,))
        return rows[0]["value"] if rows else None

    def set_secret(self, key, value):
        self._execute("INSERT INTO app_secrets (key, value) VALUES (?, ?) "
                      "ON CONFLICT(key) DO UPDATE SET value = excluded.value", (key, value))
