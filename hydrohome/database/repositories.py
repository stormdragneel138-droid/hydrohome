"""Repositories: the ONLY place SQL is written. All queries are parameterized."""
from hydrohome.database.connection import get_connection


class BaseRepository:
    def __init__(self, db_path=None):
        self.db_path = db_path

    def _query(self, sql, params=()):
        with get_connection(self.db_path) as conn:
            return [dict(row) for row in conn.execute(sql, params).fetchall()]

    def _execute(self, sql, params=()):
        """Run a write statement; return (lastrowid, rowcount)."""
        with get_connection(self.db_path) as conn:
            cur = conn.execute(sql, params)
            return cur.lastrowid, cur.rowcount

    @staticmethod
    def _like(text):
        return f"%{(text or '').strip()}%"


class HouseholdRepository(BaseRepository):
    def add(self, d):
        rid, _ = self._execute(
            "INSERT INTO households (name, address, city, members, daily_target_liters) "
            "VALUES (?, ?, ?, ?, ?)",
            (d["name"], d["address"], d["city"], d["members"], d["daily_target_liters"]))
        return rid

    def get(self, household_id):
        rows = self._query("SELECT * FROM households WHERE id = ?", (household_id,))
        return rows[0] if rows else None

    def list_all(self, search=""):
        like = self._like(search)
        return self._query(
            "SELECT * FROM households WHERE name LIKE ? OR city LIKE ? OR address LIKE ? "
            "ORDER BY name COLLATE NOCASE", (like, like, like))

    def update(self, household_id, d):
        # If the city changes, the cached coordinates are no longer valid.
        _, n = self._execute(
            "UPDATE households SET name=?, address=?, city=?, members=?, daily_target_liters=?, "
            "latitude  = CASE WHEN city = ? THEN latitude  ELSE NULL END, "
            "longitude = CASE WHEN city = ? THEN longitude ELSE NULL END "
            "WHERE id = ?",
            (d["name"], d["address"], d["city"], d["members"], d["daily_target_liters"],
             d["city"], d["city"], household_id))
        return n

    def delete(self, household_id):
        _, n = self._execute("DELETE FROM households WHERE id = ?", (household_id,))
        return n

    def set_coordinates(self, household_id, latitude, longitude):
        self._execute("UPDATE households SET latitude=?, longitude=? WHERE id=?",
                      (latitude, longitude, household_id))


class ReadingRepository(BaseRepository):
    def add(self, d):
        rid, _ = self._execute(
            "INSERT INTO water_readings (household_id, reading_date, meter_reading, notes) "
            "VALUES (?, ?, ?, ?)",
            (d["household_id"], d["reading_date"], d["meter_reading"], d["notes"]))
        return rid

    def get(self, reading_id):
        rows = self._query("SELECT * FROM water_readings WHERE id = ?", (reading_id,))
        return rows[0] if rows else None

    def for_household(self, household_id):
        return self._query(
            "SELECT * FROM water_readings WHERE household_id = ? "
            "ORDER BY reading_date, id", (household_id,))

    def list_filtered(self, household_id=None, search=""):
        like = self._like(search)
        return self._query(
            "SELECT r.*, h.name AS household_name FROM water_readings r "
            "JOIN households h ON h.id = r.household_id "
            "WHERE (? IS NULL OR r.household_id = ?) "
            "AND (r.reading_date LIKE ? OR r.notes LIKE ? OR h.name LIKE ?) "
            "ORDER BY r.reading_date DESC, r.id DESC",
            (household_id, household_id, like, like, like))

    def update(self, reading_id, d):
        _, n = self._execute(
            "UPDATE water_readings SET household_id=?, reading_date=?, meter_reading=?, notes=? "
            "WHERE id = ?",
            (d["household_id"], d["reading_date"], d["meter_reading"], d["notes"], reading_id))
        return n

    def delete(self, reading_id):
        _, n = self._execute("DELETE FROM water_readings WHERE id = ?", (reading_id,))
        return n


class ReminderRepository(BaseRepository):
    def add(self, d):
        rid, _ = self._execute(
            "INSERT INTO reminders (household_id, title, reminder_type, due_at, repeat_rule, notes) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (d["household_id"], d["title"], d["reminder_type"], d["due_at"],
             d["repeat_rule"], d["notes"]))
        return rid

    def get(self, reminder_id):
        rows = self._query("SELECT * FROM reminders WHERE id = ?", (reminder_id,))
        return rows[0] if rows else None

    def list_filtered(self, status=None, search="", household_id=None):
        like = self._like(search)
        return self._query(
            "SELECT rm.*, h.name AS household_name FROM reminders rm "
            "JOIN households h ON h.id = rm.household_id "
            "WHERE (? IS NULL OR rm.status = ?) AND (? IS NULL OR rm.household_id = ?) "
            "AND (rm.title LIKE ? OR rm.notes LIKE ? OR rm.reminder_type LIKE ? OR h.name LIKE ?) "
            "ORDER BY rm.due_at, rm.id",
            (status, status, household_id, household_id, like, like, like, like))

    def update(self, reminder_id, d):
        # A changed schedule must be allowed to alert again.
        _, n = self._execute(
            "UPDATE reminders SET household_id=?, title=?, reminder_type=?, due_at=?, "
            "repeat_rule=?, notes=?, last_notified=NULL WHERE id = ?",
            (d["household_id"], d["title"], d["reminder_type"], d["due_at"],
             d["repeat_rule"], d["notes"], reminder_id))
        return n

    def delete(self, reminder_id):
        _, n = self._execute("DELETE FROM reminders WHERE id = ?", (reminder_id,))
        return n

    def set_status(self, reminder_id, status):
        self._execute("UPDATE reminders SET status = ? WHERE id = ?", (status, reminder_id))

    def reschedule(self, reminder_id, due_at):
        self._execute("UPDATE reminders SET due_at=?, status='Pending', last_notified=NULL "
                      "WHERE id = ?", (due_at, reminder_id))

    def due_unnotified(self, now_text):
        return self._query(
            "SELECT rm.*, h.name AS household_name FROM reminders rm "
            "JOIN households h ON h.id = rm.household_id "
            "WHERE rm.status = 'Pending' AND rm.due_at <= ? "
            "AND (rm.last_notified IS NULL OR rm.last_notified < rm.due_at) "
            "ORDER BY rm.due_at", (now_text,))

    def mark_notified(self, reminder_id, when_text):
        self._execute("UPDATE reminders SET last_notified = ? WHERE id = ?",
                      (when_text, reminder_id))


class MeterSourceRepository(BaseRepository):
    def get(self, source_id):
        rows = self._query("SELECT * FROM meter_sources WHERE id = ?", (source_id,))
        return rows[0] if rows else None

    def get_for_household(self, household_id):
        rows = self._query("SELECT * FROM meter_sources WHERE household_id = ?", (household_id,))
        return rows[0] if rows else None

    def list_all(self):
        return self._query(
            "SELECT s.*, h.name AS household_name FROM meter_sources s "
            "JOIN households h ON h.id = s.household_id ORDER BY h.name COLLATE NOCASE")

    def list_enabled(self):
        return self._query("SELECT * FROM meter_sources WHERE enabled = 1 ORDER BY id")

    def save(self, d):
        """Create the household's source, or update it if one already exists."""
        self._execute(
            "INSERT INTO meter_sources (household_id, source_type, location, api_key, "
            "reading_path, unit, interval_minutes, enabled) VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(household_id) DO UPDATE SET source_type=excluded.source_type, "
            "location=excluded.location, api_key=excluded.api_key, "
            "reading_path=excluded.reading_path, unit=excluded.unit, "
            "interval_minutes=excluded.interval_minutes, enabled=excluded.enabled",
            (d["household_id"], d["source_type"], d["location"], d["api_key"],
             d["reading_path"], d["unit"], d["interval_minutes"], d["enabled"]))

    def delete(self, source_id):
        _, n = self._execute("DELETE FROM meter_sources WHERE id = ?", (source_id,))
        return n

    def record_sync(self, source_id, when_text, status):
        self._execute("UPDATE meter_sources SET last_sync_at=?, last_status=? WHERE id=?",
                      (when_text, status, source_id))
