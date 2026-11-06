"""Daily water-consumption use-cases: record, edit, totals, averages, history, breakdown."""
from datetime import date, timedelta

from hydrohome import config
from hydrohome.errors import NotFoundError, ValidationError


def week_start(day):
    """Weeks run Monday to Sunday (matches the dashboard's 'this week so far')."""
    return day - timedelta(days=day.weekday())


def iso(day):
    return day.strftime(config.DATE_FMT)


def pct_change(current, previous):
    """Percent change from previous to current, or None when there is nothing to compare with."""
    if not previous:
        return None
    return round((current - previous) / previous * 100, 1)


def status_for(liters, limit, threshold_pct):
    if limit <= 0 or liters <= 0:
        return "On track"
    ratio = liters / limit * 100
    if ratio > 100:
        return "Over limit"
    if ratio >= threshold_pct:
        return "Near limit"
    return "On track"


class UsageService:
    def __init__(self, usage, sources, households, settings):
        self.usage, self.sources = usage, sources
        self.households, self.settings = households, settings

    # -- helpers --------------------------------------------------------------
    @staticmethod
    def entry_out(row):
        return {"id": row["id"], "household_id": row["household_id"], "source_id": row["source_id"],
                "source_name": row["source_name"], "source_color": row["source_color"],
                "usage_date": row["usage_date"], "liters": round(row["liters"], 1),
                "notes": row["notes"], "created_at": row["created_at"]}

    def _resolve_source(self, household_id, source_id=None, source_name=None):
        self.settings.ensure_defaults(household_id)
        if source_id is not None:
            row = self.sources.get(source_id)
        elif source_name:
            row = self.sources.find_by_name(household_id, source_name.strip())
        else:
            raise ValidationError("Choose a water source (source_id or source).")
        if not row or row["household_id"] != household_id:
            raise ValidationError("That water source does not exist in this household.")
        if not row["enabled"]:
            raise ValidationError(f"The source '{row['name']}' is disabled.")
        return row

    @staticmethod
    def _check_date(usage_date):
        if usage_date > date.today():
            raise ValidationError("Usage cannot be recorded for a future date.")
        if usage_date < date.today() - timedelta(days=3650):
            raise ValidationError("Usage date is too far in the past.")

    # -- CRUD -----------------------------------------------------------------
    def record(self, household_id, usage_date, liters, source_id=None, source_name=None,
               notes="", user_id=None):
        self._check_date(usage_date)
        source = self._resolve_source(household_id, source_id, source_name)
        rid = self.usage.add(household_id, source["id"], iso(usage_date), liters,
                             (notes or "").strip(), user_id)
        return self.entry_out(self.usage.get(rid))

    def get(self, usage_id):
        row = self.usage.get(usage_id)
        if not row:
            raise NotFoundError("Usage entry not found.")
        return row

    def update(self, usage_id, usage_date=None, liters=None, source_id=None, source_name=None,
               notes=None):
        row = self.get(usage_id)
        new_date = usage_date or date.fromisoformat(row["usage_date"])
        self._check_date(new_date)
        if source_id is None and not source_name:
            source_id = row["source_id"]
        source = self._resolve_source(row["household_id"], source_id, source_name)
        self.usage.update(usage_id, source["id"], iso(new_date),
                          row["liters"] if liters is None else liters,
                          row["notes"] if notes is None else notes.strip())
        return self.entry_out(self.usage.get(usage_id))

    def delete(self, usage_id):
        self.get(usage_id)
        self.usage.delete(usage_id)

    def list_entries(self, household_id, start=None, end=None, source_id=None, limit=50, offset=0):
        if start and end and start > end:
            raise ValidationError("start must not be after end.")
        s, e = (iso(start) if start else None), (iso(end) if end else None)
        rows = self.usage.list(household_id, s, e, source_id, limit, offset)
        return {"total": self.usage.count(household_id, s, e, source_id), "limit": limit,
                "offset": offset, "items": [self.entry_out(r) for r in rows]}

    # -- totals / series ------------------------------------------------------
    def total_between(self, household_id, start, end):
        rows = self.usage.daily_totals(household_id, iso(start), iso(end))
        return round(sum(r["liters"] for r in rows), 1)

    def daily_series(self, household_id, start, end):
        """One point per calendar day from start to end, zero-filled."""
        if start > end:
            raise ValidationError("start must not be after end.")
        if (end - start).days > 400:
            raise ValidationError("Range is too long (maximum 400 days).")
        limit = self.settings.get_limits(household_id)["daily_limit_liters"]
        totals = {r["usage_date"]: r["liters"]
                  for r in self.usage.daily_totals(household_id, iso(start), iso(end))}
        points, day = [], start
        while day <= end:
            liters = round(totals.get(iso(day), 0.0), 1)
            points.append({"date": iso(day), "liters": liters, "over_limit": liters > limit})
            day += timedelta(days=1)
        return points

    def history(self, household_id, start, end):
        """Daily totals (newest first) with a per-source breakdown for each day."""
        limits = self.settings.get_limits(household_id)
        breakdown = {}
        for r in self.usage.breakdown_by_day(household_id, iso(start), iso(end)):
            breakdown.setdefault(r["usage_date"], []).append(
                {"source": r["source_name"], "liters": round(r["liters"], 1)})
        days = []
        for r in sorted(self.usage.daily_totals(household_id, iso(start), iso(end)),
                        key=lambda x: x["usage_date"], reverse=True):
            liters = round(r["liters"], 1)
            days.append({"date": r["usage_date"], "liters": liters,
                         "limit": limits["daily_limit_liters"],
                         "status": status_for(liters, limits["daily_limit_liters"],
                                              limits["alert_threshold_pct"]),
                         "by_source": breakdown.get(r["usage_date"], [])})
        return {"start": iso(start), "end": iso(end), "days": days,
                "total_liters": round(sum(d["liters"] for d in days), 1)}

    def average_daily(self, household_id, end, days):
        """Average litres per day over the last `days` days, counting only days that have data."""
        start = end - timedelta(days=days - 1)
        rows = self.usage.daily_totals(household_id, iso(start), iso(end))
        if not rows:
            return {"average": 0.0, "days_with_data": 0}
        return {"average": round(sum(r["liters"] for r in rows) / len(rows), 1),
                "days_with_data": len(rows)}

    def summary(self, household_id, as_of=None):
        as_of = as_of or date.today()
        household = self.households.get(household_id)
        limits = self.settings.get_limits(household_id)
        today = self.total_between(household_id, as_of, as_of)
        yesterday = self.total_between(household_id, as_of - timedelta(days=1),
                                       as_of - timedelta(days=1))
        monday = week_start(as_of)
        week_total = self.total_between(household_id, monday, as_of)
        elapsed = (as_of - monday).days
        last_monday = monday - timedelta(days=7)
        last_week_same_days = self.total_between(household_id, last_monday,
                                                 last_monday + timedelta(days=elapsed))
        avg7 = self.average_daily(household_id, as_of, 7)
        avg30 = self.average_daily(household_id, as_of, 30)
        daily_limit = limits["daily_limit_liters"]
        return {
            "date": iso(as_of),
            "today": {"liters": today, "limit": daily_limit,
                      "percent": round(today / daily_limit * 100) if daily_limit else 0,
                      "remaining": round(max(daily_limit - today, 0), 1),
                      "status": status_for(today, daily_limit, limits["alert_threshold_pct"])},
            "yesterday": {"liters": yesterday, "difference": round(today - yesterday, 1),
                          "change_percent": pct_change(today, yesterday)},
            "week": {"start": iso(monday), "end": iso(as_of), "liters": week_total,
                     "limit": limits["weekly_limit_liters"],
                     "last_7_days_liters": self.total_between(household_id,
                                                              as_of - timedelta(days=6), as_of),
                     "previous_week_same_days": last_week_same_days,
                     "change_percent": pct_change(week_total, last_week_same_days),
                     "days_elapsed": elapsed + 1},
            "averages": {"daily_7d": avg7["average"], "daily_30d": avg30["average"],
                         "days_with_data_7d": avg7["days_with_data"],
                         "days_with_data_30d": avg30["days_with_data"],
                         "per_person_daily_7d": round(avg7["average"] / household["members"], 1),
                         "weekly_equivalent": round(avg30["average"] * 7, 1)},
        }

    def by_source(self, household_id, period="today", as_of=None):
        as_of = as_of or date.today()
        days = {"today": 1, "week": 7, "month": 30}.get(period)
        if days is None:
            raise ValidationError("period must be today, week or month.")
        start = as_of - timedelta(days=days - 1)
        rows = self.usage.source_totals(household_id, iso(start), iso(as_of))
        total = sum(r["liters"] for r in rows)
        items = [{"source_id": r["source_id"], "name": r["name"], "color": r["color"],
                  "liters": round(r["liters"], 1),
                  "percent": round(r["liters"] / total * 100) if total else 0} for r in rows]
        return {"period": period, "start": iso(start), "end": iso(as_of),
                "total_liters": round(total, 1), "items": items}
