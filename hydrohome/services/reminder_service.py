"""Reminder use-cases and the due-date engine."""
import calendar
from datetime import datetime, timedelta

from hydrohome import config
from hydrohome.errors import ValidationError
from hydrohome.services.validators import validate_reminder


def add_repeat(due, rule):
    """Return the next occurrence of `due` for a repeat rule (Monthly clamps to month end)."""
    if rule == "Daily":
        return due + timedelta(days=1)
    if rule == "Weekly":
        return due + timedelta(days=7)
    if rule == "Monthly":
        month = due.month % 12 + 1
        year = due.year + (1 if due.month == 12 else 0)
        day = min(due.day, calendar.monthrange(year, month)[1])
        return due.replace(year=year, month=month, day=day)
    return due


class ReminderService:
    def __init__(self, repo, households_repo):
        self.repo = repo
        self.households = households_repo

    def _validated(self, form):
        data = validate_reminder(form)
        if not self.households.get(data["household_id"]):
            raise ValidationError("Please choose an existing household.")
        return data

    def add(self, form):
        return self.repo.add(self._validated(form))

    def update(self, reminder_id, form):
        if self.repo.update(reminder_id, self._validated(form)) == 0:
            raise ValidationError("That reminder no longer exists.")

    def delete(self, reminder_id):
        if self.repo.delete(reminder_id) == 0:
            raise ValidationError("That reminder no longer exists.")

    def list(self, status=None, search="", household_id=None):
        return self.repo.list_filtered(status, search, household_id)

    def upcoming(self, household_id=None, limit=5):
        return self.repo.list_filtered(config.STATUS_PENDING, "", household_id)[:limit]

    def complete(self, reminder_id, now=None):
        """Mark done. Repeating reminders roll forward instead of closing."""
        now = now or datetime.now()
        reminder = self.repo.get(reminder_id)
        if not reminder:
            raise ValidationError("That reminder no longer exists.")
        if reminder["repeat_rule"] == "None":
            self.repo.set_status(reminder_id, config.STATUS_DONE)
            return "Reminder marked as done."
        nxt = datetime.strptime(reminder["due_at"], config.DATETIME_FMT)
        while nxt <= now:
            nxt = add_repeat(nxt, reminder["repeat_rule"])
        self.repo.reschedule(reminder_id, nxt.strftime(config.DATETIME_FMT))
        return f"Done. Next reminder: {nxt.strftime(config.DATETIME_FMT)}."

    def collect_due_alerts(self, now=None):
        """Return reminders that just became due, flagging them so they alert only once."""
        stamp = (now or datetime.now()).strftime(config.DATETIME_FMT)
        due = self.repo.due_unnotified(stamp)
        for row in due:
            self.repo.mark_notified(row["id"], stamp)
        return due

    def overdue_count(self, now=None):
        stamp = (now or datetime.now()).strftime(config.DATETIME_FMT)
        return len([r for r in self.repo.list_filtered(config.STATUS_PENDING)
                    if r["due_at"] <= stamp])
