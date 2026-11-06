"""Builds the one JSON document the web dashboard needs (every card, chart and list)."""
import csv
import io
from datetime import date, datetime, timedelta

from hydrohome.errors import ValidationError
from hydrohome.services.alert_service import ATTENTION_KINDS
from hydrohome.services.usage_service import iso, pct_change

ALL_TIPS = (
    "Water the roots, not the afternoon sun: water the garden before 8 AM to cut evaporation.",
    "Shorten showers by one or two minutes; a low-flow showerhead can save up to 40 %.",
    "Run washing machines and dishwashers only with full loads.",
    "Turn the tap off while brushing teeth or scrubbing dishes.",
    "Add a few drops of food colouring to the toilet tank: if it shows in the bowl, it leaks.",
    "Fix dripping taps quickly; one drip per second wastes about 10 L a day.",
    "Collect rainwater for the garden and for washing the yard.",
    "Read your water meter at the same time each day to spot hidden leaks early.",
)

_TIPS = {
    "garden": ("Water the roots, not the afternoon sun.",
               "Your garden is using more than usual. Try watering before 8 AM to reduce "
               "evaporation.", "Up to 30%", "less outdoor water use"),
    "shower": ("Trim a minute off every shower.",
               "Showers and baths are your biggest use today. A low-flow showerhead can cut "
               "shower water noticeably.", "Up to 40%", "less shower water"),
    "toilet": ("Check your toilets for silent leaks.",
               "Add a few drops of food colouring to the tank. If it reaches the bowl without "
               "flushing, it is leaking.", "Up to 20%", "less toilet water"),
    "laundry": ("Wash only full loads.",
                "Laundry is a large share of today's usage. Full loads use far less water per "
                "item.", "Up to 15%", "less laundry water"),
    "kitchen": ("Fill a basin instead of running the tap.",
                "Washing dishes in a basin instead of under a running tap saves water every day.",
                "Up to 25%", "less kitchen water"),
}
_DEFAULT_TIP = ("Log today's water use.",
                "Record your readings by source and you will get tips tailored to your household.",
                "—", "once you add data")


def _tip(top_source, flagged_source):
    for name in (flagged_source, top_source):
        for key, tip in _TIPS.items():
            if name and key in name.lower():
                return {"eyebrow": "A SMALL CHANGE FOR YOUR HOME", "title": tip[0], "text": tip[1],
                        "savings": tip[2], "savings_label": tip[3]}
    t = _DEFAULT_TIP
    return {"eyebrow": "A SMALL CHANGE FOR YOUR HOME", "title": t[0], "text": t[1],
            "savings": t[2], "savings_label": t[3]}


def _range_label(start, end):
    return f"{start.strftime('%b')} {start.day} – {end.strftime('%b')} {end.day}, {end.year}"


class DashboardService:
    def __init__(self, households, usage_service, alert_service, schedule_service,
                 settings_service):
        self.households, self.usage = households, usage_service
        self.alerts, self.schedules, self.settings = alert_service, schedule_service, settings_service

    def _chart(self, household_id, period, as_of, limits):
        if period == "day":
            by_source = self.usage.by_source(household_id, "today", as_of)
            return {"period": "day", "mode": "sources", "target": None,
                    "subtitle": f"{as_of.strftime('%a, %b')} {as_of.day}, {as_of.year} · "
                                f"Usage by source",
                    "bars": [{"label": i["name"], "liters": i["liters"], "is_today": False,
                              "color": i["color"]} for i in by_source["items"]],
                    "average": None, "change_percent": None,
                    "insight": "Today's water by source." if by_source["items"]
                    else "No water recorded for this day yet."}
        days = 7 if period == "week" else 30
        start = as_of - timedelta(days=days - 1)
        series = self.usage.daily_series(household_id, start, as_of)
        bars = []
        for point in series:
            d = date.fromisoformat(point["date"])
            is_today = d == as_of
            label = "Today" if is_today else (d.strftime("%a") if days == 7 else str(d.day))
            bars.append({"date": point["date"], "label": label, "liters": point["liters"],
                         "is_today": is_today, "over_limit": point["over_limit"]})
        cur = self.usage.average_daily(household_id, as_of, days)
        prev = self.usage.average_daily(household_id, start - timedelta(days=1), days)
        change = pct_change(cur["average"], prev["average"])
        unit = "week" if days == 7 else "month"
        if cur["days_with_data"] == 0:
            insight = "No usage recorded in this period yet. Log your first reading to see trends."
        elif change is None:
            insight = f"Your daily average is {cur['average']:.0f} L this {unit}."
        elif change <= -0.5:
            insight = f"Your daily average is down {abs(change):.0f}% this {unit}. " \
                      f"Small changes add up."
        elif change >= 0.5:
            insight = f"Your daily average is up {change:.0f}% this {unit}. " \
                      f"Check the alerts for what changed."
        else:
            insight = f"Your daily average is steady this {unit}."
        return {"period": period, "mode": "days", "start": iso(start), "end": iso(as_of),
                "target": limits["daily_limit_liters"],
                "subtitle": f"{_range_label(start, as_of)} · Daily household usage",
                "bars": bars, "average": cur["average"], "change_percent": change,
                "insight": insight}

    def build(self, household_id, period="week", as_of=None, source_period="today"):
        if period not in ("day", "week", "month"):
            raise ValidationError("period must be day, week or month.")
        as_of = as_of or date.today()
        if as_of > date.today():
            raise ValidationError("The dashboard date cannot be in the future.")
        household = self.households.get(household_id)
        limits = self.settings.get_limits(household_id)
        summary = self.usage.summary(household_id, as_of)
        by_source = self.usage.by_source(household_id, source_period, as_of)
        # keep the alert state fresh for the day being shown
        self.alerts.evaluate(household_id, as_of)
        active = [a for a in self.alerts.list(household_id, "open")
                  if a["kind"] in ATTENTION_KINDS]
        flagged_ids = {a["source_id"] for a in active if a["kind"] == "high_source"}
        for item in by_source["items"]:
            item["flagged"] = item["source_id"] in flagged_ids
        flagged_name = next((a["source_name"] for a in active if a["kind"] == "high_source"), None)
        top = by_source["items"][0]["name"] if by_source["items"] else None
        sources = self.settings.list_sources(household_id)
        top_two = by_source["items"][:2]
        share = sum(i["percent"] for i in top_two)
        if len(top_two) == 2:
            names = " and ".join(i["name"].lower() for i in top_two)
            when = "today’s" if source_period == "today" else "this period’s"
            source_note = f"{names[0].upper()}{names[1:]} account for {share}% of {when} usage."
        else:
            source_note = "Record usage by source to see where your water goes."
        cost = round(summary["today"]["liters"] / 1000 * limits["rate_per_1000_l"], 2)
        return {
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "household": {"id": household["id"], "name": household["name"],
                          "members": household["members"], "city": household["city"]},
            "date": iso(as_of),
            "today": summary["today"],
            "yesterday": summary["yesterday"],
            "week": summary["week"],
            "averages": summary["averages"],
            "cost": {"today": cost, "currency": limits["currency"],
                     "rate_per_1000_l": limits["rate_per_1000_l"]},
            "limits": limits,
            "chart": self._chart(household_id, period, as_of, limits),
            "alerts": {"open_count": len(active), "items": active[:4],
                       "counts": self.alerts.counts(household_id)},
            "sources": {"period": source_period, "total_liters": by_source["total_liters"],
                        "items": by_source["items"], "connected": len([s for s in sources
                                                                       if s["enabled"]]),
                        "note": source_note},
            "reminders": {"items": self.schedules.list(household_id),
                          "next": (self.schedules.upcoming(household_id, 3) or [None])[0],
                          "upcoming": self.schedules.upcoming(household_id, 3)},
            "notifications": self.settings.get_notifications(household_id),
            "tip": _tip(top, flagged_name),
            "all_tips": list(ALL_TIPS),
        }

    def export_csv(self, household_id, start, end):
        """Every usage entry between two dates as CSV text."""
        if start > end:
            raise ValidationError("start must not be after end.")
        rows = self.usage.usage.list(household_id, iso(start), iso(end), None, 100000, 0)
        out = io.StringIO()
        writer = csv.writer(out)
        writer.writerow(["date", "source", "liters", "notes"])
        for r in sorted(rows, key=lambda x: (x["usage_date"], x["id"])):
            writer.writerow([r["usage_date"], r["source_name"], round(r["liters"], 1), r["notes"]])
        return out.getvalue()

