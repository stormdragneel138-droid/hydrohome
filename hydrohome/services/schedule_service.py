"""Water-saving reminder schedules (for example 'Evening usage check-in, every day at 8:00 PM').

A schedule fires an in-app notification (an alert of kind 'reminder') once per due day.
Quiet hours are respected: nothing fires while quiet hours are active, and a reminder that was
held back fires as soon as quiet hours end (within a 6-hour catch-up window).
"""
from datetime import datetime, timedelta

from hydrohome import config
from hydrohome.errors import NotFoundError, ValidationError

SCHEDULE_TYPES = ("Usage Check-in", "Garden Watering", "Leak Check", "Meter Reading",
                  "Conservation Tip", "Bill Payment", "Other")
CHANNELS = ("Push notification", "Email", "Push + Email")
DAY_CODES = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
DAY_LABELS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
CATCH_UP_HOURS = 6


def normalise_days(days):
    """Accept 'daily', 'weekdays', 'weekends', or a list / comma string of day codes."""
    if isinstance(days, str):
        text = days.replace(" ", "").lower()
        if text == "daily":
            return "daily"
        if text == "weekdays":
            return ",".join(DAY_CODES[:5])
        if text == "weekends":
            return "sat,sun"
        days = [d for d in text.split(",") if d]
    days = [str(d).strip().lower()[:3] for d in days]
    if not days:
        raise ValidationError("Choose at least one day (or 'daily').")
    if any(d not in DAY_CODES for d in days):
        raise ValidationError("Days must be daily, weekdays, weekends or a list of "
                              "mon, tue, wed, thu, fri, sat, sun.")
    if set(days) == set(DAY_CODES):
        return "daily"
    return ",".join(sorted(set(days), key=DAY_CODES.index))


def day_set(days_text):
    return set(DAY_CODES) if days_text == "daily" else set(days_text.split(","))


def format_time(hhmm):
    hour, minute = int(hhmm[:2]), int(hhmm[3:])
    return f"{hour % 12 or 12}:{minute:02d} {'AM' if hour < 12 else 'PM'}"


def describe_days(days_text):
    if days_text == "daily":
        return "Every day"
    codes = day_set(days_text)
    if codes == set(DAY_CODES[:5]):
        return "Weekdays"
    if codes == {"sat", "sun"}:
        return "Weekends"
    return ", ".join(DAY_LABELS[DAY_CODES.index(c)] for c in DAY_CODES if c in codes)


def in_quiet_hours(now_time, start, end):
    """True if the 'HH:MM' time falls in [start, end) - handles windows past midnight."""
    if start == end:
        return False
    if start < end:
        return start <= now_time < end
    return now_time >= start or now_time < end


class ScheduleService:
    def __init__(self, schedules, alerts, settings, on_fire=None):
        self.schedules, self.alerts, self.settings = schedules, alerts, settings
        self.on_fire = on_fire        # optional callback(alert_row, schedule_row): push notification

    # -- validation / output ----------------------------------------------------
    def _clean(self, form):
        title = str(form["title"]).strip()
        errors = []
        if not title or len(title) > 80:
            errors.append("Title is required (max 80 characters).")
        if form["reminder_type"] not in SCHEDULE_TYPES:
            errors.append("Type must be one of: " + ", ".join(SCHEDULE_TYPES) + ".")
        if form["channel"] not in CHANNELS:
            errors.append("Channel must be one of: " + ", ".join(CHANNELS) + ".")
        try:
            datetime.strptime(form["time_of_day"], config.TIME_FMT)
        except ValueError:
            errors.append("Time must look like 20:00 (24-hour HH:MM).")
        try:
            days = normalise_days(form["days"])
        except ValidationError as exc:
            errors.extend(exc.errors)
            days = None
        if errors:
            raise ValidationError(errors)
        return {"title": title, "reminder_type": form["reminder_type"], "days": days,
                "time_of_day": form["time_of_day"], "channel": form["channel"],
                "notes": str(form.get("notes", "")).strip()[:200],
                "enabled": bool(form.get("enabled", True))}

    def schedule_out(self, row, now=None):
        nxt = self.next_run(row, now or datetime.now()) if row["enabled"] else None
        return {"id": row["id"], "household_id": row["household_id"], "title": row["title"],
                "reminder_type": row["reminder_type"], "days": row["days"],
                "time_of_day": row["time_of_day"], "channel": row["channel"],
                "notes": row["notes"], "enabled": bool(row["enabled"]),
                "description": f"{describe_days(row['days'])} · {format_time(row['time_of_day'])}"
                               f" · {row['channel']}",
                "next_run": nxt.strftime("%Y-%m-%d %H:%M") if nxt else None,
                "last_fired_on": row["last_fired_on"], "created_at": row["created_at"]}

    # -- CRUD -------------------------------------------------------------------
    def add(self, household_id, form):
        self.settings.ensure_defaults(household_id)
        sid = self.schedules.add(household_id, self._clean(form))
        return self.schedule_out(self.schedules.get(sid))

    def get(self, schedule_id):
        row = self.schedules.get(schedule_id)
        if not row:
            raise NotFoundError("Reminder schedule not found.")
        return row

    def update(self, schedule_id, form):
        row = self.get(schedule_id)
        merged = {"title": row["title"], "reminder_type": row["reminder_type"],
                  "days": row["days"], "time_of_day": row["time_of_day"],
                  "channel": row["channel"], "notes": row["notes"], "enabled": bool(row["enabled"]),
                  **{k: v for k, v in form.items() if v is not None}}
        self.schedules.update(schedule_id, self._clean(merged))
        return self.schedule_out(self.schedules.get(schedule_id))

    def delete(self, schedule_id):
        self.get(schedule_id)
        self.schedules.delete(schedule_id)

    def list(self, household_id):
        now = datetime.now()
        return [self.schedule_out(r, now) for r in self.schedules.for_household(household_id)]

    # -- next run ---------------------------------------------------------------
    @staticmethod
    def next_run(row, now):
        codes = day_set(row["days"])
        hour, minute = int(row["time_of_day"][:2]), int(row["time_of_day"][3:])
        for offset in range(0, 8):
            day = now + timedelta(days=offset)
            candidate = day.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if DAY_CODES[candidate.weekday()] in codes and candidate > now:
                return candidate
        return None

    def upcoming(self, household_id, limit=3, now=None):
        now = now or datetime.now()
        items = []
        for row in self.schedules.for_household(household_id):
            if row["enabled"]:
                nxt = self.next_run(row, now)
                if nxt:
                    items.append((nxt, row))
        items.sort(key=lambda pair: pair[0])
        out = []
        for nxt, row in items[:limit]:
            data = self.schedule_out(row, now)
            if nxt.date() == now.date():
                data["when"] = f"Tonight, {format_time(row['time_of_day'])}" if nxt.hour >= 18 \
                    else f"Today, {format_time(row['time_of_day'])}"
            elif nxt.date() == (now + timedelta(days=1)).date():
                data["when"] = f"Tomorrow, {format_time(row['time_of_day'])}"
            else:
                data["when"] = f"{DAY_LABELS[nxt.weekday()]}, {format_time(row['time_of_day'])}"
            out.append(data)
        return out

    # -- firing -----------------------------------------------------------------
    def fire_due(self, now=None, household_ids=None):
        """Create a notification for every enabled schedule that is due. Safe to call often:
        each schedule fires at most once per day. Returns the notifications created."""
        now = now or datetime.now()
        today, hhmm = now.strftime(config.DATE_FMT), now.strftime(config.TIME_FMT)
        quiet_cache, fired = {}, []
        for row in self.schedules.all_enabled():
            hid = row["household_id"]
            if household_ids is not None and hid not in household_ids:
                continue
            if row["last_fired_on"] == today:
                continue
            if DAY_CODES[now.weekday()] not in day_set(row["days"]):
                continue
            scheduled = datetime.strptime(f"{today} {row['time_of_day']}", "%Y-%m-%d %H:%M")
            if scheduled > now or now - scheduled > timedelta(hours=CATCH_UP_HOURS):
                continue
            if hid not in quiet_cache:
                quiet_cache[hid] = self.settings.get_notifications(hid)
            prefs = quiet_cache[hid]
            if in_quiet_hours(hhmm, prefs["quiet_start"], prefs["quiet_end"]):
                continue
            alert_id = self.alerts.add(hid, {
                "kind": "reminder", "severity": "info", "title": row["title"],
                "message": row["notes"] or f"Reminder: {row['title']}",
                "usage_date": today, "dedupe_key": f"reminder:{row['id']}:{today}"})
            self.schedules.mark_fired(row["id"], today)
            alert = self.alerts.get(alert_id)
            fired.append(alert)
            if self.on_fire and "push" in str(row["channel"]).lower():
                try:
                    self.on_fire(alert, row)
                except Exception as exc:      # never let a notification failure stop reminders
                    print("Reminder notification failed:", exc)
        return fired
