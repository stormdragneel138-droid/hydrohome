"""Builds the exportable outputs: CSV exports and the household usage report."""
from datetime import datetime

from hydrohome import config
from hydrohome.errors import ValidationError
from hydrohome.services import consumption, file_service

READING_FIELDS = ("reading_date", "household_name", "meter_reading", "used_m3",
                  "liters_per_person_day", "status", "notes")
READING_HEADERS = ("Date", "Household", "Meter (m3)", "Used (m3)",
                   "Litres/person/day", "Status", "Notes")
REMINDER_FIELDS = ("due_at", "household_name", "title", "reminder_type",
                   "repeat_rule", "status", "notes")
REMINDER_HEADERS = ("Due", "Household", "Title", "Type", "Repeat", "Status", "Notes")


class ReportService:
    def __init__(self, households, readings, reminders):
        self.households, self.readings, self.reminders = households, readings, reminders

    def export_readings(self, path, household_id=None, search=""):
        rows = self.readings.list_with_usage(household_id, search)
        return file_service.export_csv(path, READING_FIELDS, READING_HEADERS, rows)

    def export_reminders(self, path, status=None, search=""):
        rows = self.reminders.list(status, search)
        return file_service.export_csv(path, REMINDER_FIELDS, REMINDER_HEADERS, rows)

    def import_readings(self, path, household_id):
        raw = file_service.read_readings_csv(path)
        return self.readings.import_rows(household_id, raw)

    def build_usage_report(self, household_id, now=None):
        periods, hh = self.readings.periods_for(household_id)
        if not hh:
            raise ValidationError("Select a household to report on.")
        s = consumption.summarize(periods, hh["members"], hh["daily_target_liters"])
        now = now or datetime.now()
        lines = [f"{config.APP_NAME} - Water Usage Report",
                 f"Generated: {now.strftime(config.DATETIME_FMT)}", "=" * 60,
                 f"Household : {hh['name']}", f"Location  : {', '.join(x for x in (hh['address'], hh['city']) if x)}",
                 f"Members   : {hh['members']}",
                 f"Target    : {hh['daily_target_liters']} L/person/day", "",
                 "USAGE PERIODS", "-" * 60,
                 f"{'From':<11}{'To':<11}{'Days':>5}{'m3':>9}{'L/person/day':>14}  Status"]
        for p in periods:
            lines.append(f"{p.start.isoformat():<11}{p.end.isoformat():<11}{p.days:>5}"
                         f"{p.used_m3:>9.3f}{p.liters_per_person_day:>14.1f}  {p.status}")
        if not periods:
            lines.append("(not enough readings yet)")
        lines += ["", "SUMMARY", "-" * 60,
                  f"Total used        : {s['total_m3']} m3",
                  f"Average           : {s['avg_liters_per_person_day']} L/person/day",
                  f"Latest status     : {s['status'] if s['status'] != 'none' else 'n/a'}", "",
                  "PENDING REMINDERS", "-" * 60]
        pending = self.reminders.list(config.STATUS_PENDING, "", household_id)
        lines += [f"{r['due_at']}  [{r['reminder_type']}]  {r['title']}  (repeat: {r['repeat_rule']})"
                  for r in pending] or ["(none)"]
        return "\n".join(lines) + "\n"

    def save_usage_report(self, path, household_id):
        file_service.write_text(path, self.build_usage_report(household_id))
