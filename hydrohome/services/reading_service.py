"""Meter-reading use-cases, including the rule that a meter never runs backwards."""
from hydrohome.errors import AppError, ValidationError
from hydrohome.services import consumption
from hydrohome.services.validators import validate_reading


class ReadingService:
    def __init__(self, readings_repo, households_repo):
        self.readings = readings_repo
        self.households = households_repo

    def _check_sequence(self, data, exclude_id=None):
        if not self.households.get(data["household_id"]):
            raise ValidationError("Please choose an existing household.")
        others = [r for r in self.readings.for_household(data["household_id"])
                  if r["id"] != exclude_id]
        errors = []
        if any(r["reading_date"] == data["reading_date"] for r in others):
            raise ValidationError("A reading for this household and date already exists.")
        before = [r for r in others if r["reading_date"] < data["reading_date"]]
        after = [r for r in others if r["reading_date"] > data["reading_date"]]
        if before and data["meter_reading"] < before[-1]["meter_reading"]:
            errors.append(f"Reading is lower than the earlier one "
                          f"({before[-1]['meter_reading']} m³ on {before[-1]['reading_date']}).")
        if after and data["meter_reading"] > after[0]["meter_reading"]:
            errors.append(f"Reading is higher than the later one "
                          f"({after[0]['meter_reading']} m³ on {after[0]['reading_date']}).")
        if errors:
            raise ValidationError(errors)

    def add(self, form):
        data = validate_reading(form)
        self._check_sequence(data)
        return self.readings.add(data)

    def update(self, reading_id, form):
        data = validate_reading(form)
        self._check_sequence(data, exclude_id=reading_id)
        if self.readings.update(reading_id, data) == 0:
            raise ValidationError("That reading no longer exists.")

    def delete(self, reading_id):
        if self.readings.delete(reading_id) == 0:
            raise ValidationError("That reading no longer exists.")

    def periods_for(self, household_id):
        hh = self.households.get(household_id)
        if not hh:
            return [], None
        periods = consumption.build_periods(
            self.readings.for_household(household_id), hh["members"], hh["daily_target_liters"])
        return periods, hh

    def list_with_usage(self, household_id=None, search=""):
        """Reading rows enriched with usage since the previous reading."""
        rows = self.readings.list_filtered(household_id, search)
        cache = {}
        for row in rows:
            hid = row["household_id"]
            if hid not in cache:
                periods, _ = self.periods_for(hid)
                cache[hid] = {p.reading_id: p for p in periods}
            p = cache[hid].get(row["id"])
            row["used_m3"] = p.used_m3 if p else None
            row["liters_per_person_day"] = p.liters_per_person_day if p else None
            row["status"] = p.status if p else "Baseline"
        return rows

    def import_rows(self, household_id, raw_rows):
        """Add many rows (e.g. from CSV). Returns (added_count, [error messages])."""
        added, errors = 0, []
        for line, raw in raw_rows:
            form = {"household_id": household_id, "reading_date": raw.get("reading_date", ""),
                    "meter_reading": raw.get("meter_reading", ""), "notes": raw.get("notes", "")}
            try:
                self.add(form)
                added += 1
            except AppError as exc:
                errors.append(f"Line {line}: {exc}")
        return added, errors
