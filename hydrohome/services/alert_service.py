"""High-usage detection and the alert lifecycle.

Detection rules (all thresholds come from the household's consumption limits):
  * limit_exceeded : today's total is over the daily limit                      -> critical
  * near_limit     : today's total reached the alert threshold (default 90 %)    -> warning
  * high_source    : one source used >= spike_multiplier x its usual daily amount -> warning
                     ("usual" = average of that source over the previous 14 days,
                       needing at least 3 days of history and 20 L extra)
  * high_total     : the whole household used >= spike_multiplier x its usual total -> warning
  * continuous_flow: the meter reports water running for 20+ minutes             -> warning
  * reminder       : created by a reminder schedule                              -> info
Alerts fixed by the data (for example a wrongly typed entry that is then deleted) are
resolved automatically. An alert the user dismissed is never re-opened for that day.
"""
from datetime import date, timedelta

from hydrohome.errors import NotFoundError, ValidationError
from hydrohome.services.usage_service import iso

AUTO_KINDS = ("limit_exceeded", "near_limit", "high_source", "high_total")
ATTENTION_KINDS = ("limit_exceeded", "near_limit", "high_source", "high_total", "continuous_flow")
STATUSES = ("open", "acknowledged", "dismissed", "resolved")
BASELINE_DAYS = 14
MIN_HISTORY_DAYS = 3
MIN_EXTRA_LITERS = 20
FLOW_MINUTES = 20
FLOW_MIN_LPM = 0.2

_ADVICE = {"garden": "Check for a running hose.", "toilet": "Check for a leaking toilet.",
           "shower": "Try shorter showers.", "laundry": "Run full loads only.",
           "kitchen": "Check for a dripping tap."}


def _advice(source_name):
    lower = source_name.lower()
    for key, text in _ADVICE.items():
        if key in lower:
            return text
    return "Check for leaks or unusual activity."


def _times(ratio):
    text = f"{ratio:.1f}".rstrip("0").rstrip(".")
    return f"{text}×"


class AlertService:
    def __init__(self, alerts, usage, sources, settings, on_alert=None):
        self.alerts, self.usage, self.sources, self.settings = alerts, usage, sources, settings
        self.on_alert = on_alert      # optional callback(alert_row): used for push notifications

    def _announce(self, row):
        if self.on_alert and row:
            try:
                self.on_alert(row)
            except Exception as exc:          # a failing notification must never break detection
                print("Alert notification failed:", exc)

    # -- output ---------------------------------------------------------------
    @staticmethod
    def alert_out(row):
        return {"id": row["id"], "household_id": row["household_id"], "kind": row["kind"],
                "severity": row["severity"], "title": row["title"], "message": row["message"],
                "source_id": row["source_id"], "source_name": row.get("source_name"),
                "usage_date": row["usage_date"], "liters": row["liters"], "status": row["status"],
                "is_read": bool(row["is_read"]), "detected_at": row["detected_at"],
                "resolved_at": row["resolved_at"]}

    # -- creation -------------------------------------------------------------
    def raise_alert(self, household_id, d):
        """Create an alert, or refresh the existing one with the same dedupe key.
        Returns the alert row, or None if the user already dismissed/acknowledged it."""
        existing = self.alerts.find_by_key(household_id, d["dedupe_key"])
        if existing is None:
            row = self.alerts.get(self.alerts.add(household_id, d))
            self._announce(row)
            return row
        if existing["status"] in ("dismissed", "acknowledged"):
            return None
        was_open = existing["status"] == "open"
        self.alerts.refresh(existing["id"], d)
        row = self.alerts.get(existing["id"])
        if not was_open:                       # re-opened: tell the user again
            self._announce(row)
        return row

    def evaluate(self, household_id, day=None):
        """Scan one day of usage, raise alerts for anything unusual, resolve ones that no
        longer apply. Returns the list of alerts that are active for that day."""
        day = day or date.today()
        limits = self.settings.get_limits(household_id)
        sources = {s["id"]: s for s in self.sources.for_household(household_id)}
        baseline_start = day - timedelta(days=BASELINE_DAYS)
        baseline_end = day - timedelta(days=1)
        today_by_source = {r["source_id"]: r["liters"] for r in
                           self.usage.source_daily(household_id, iso(day), iso(day))}
        history = {}
        for r in self.usage.source_daily(household_id, iso(baseline_start), iso(baseline_end)):
            history.setdefault(r["source_id"], []).append(r["liters"])
        total_today = sum(today_by_source.values())
        multiplier = limits["spike_multiplier"]
        found, triggered = [], set()

        def raise_(kind, severity, title, message, source_id=None, liters=None, key=None):
            key = key or f"{kind}:{iso(day)}"
            triggered.add(key)
            row = self.raise_alert(household_id, {
                "kind": kind, "severity": severity, "title": title, "message": message,
                "source_id": source_id, "usage_date": iso(day), "liters": liters,
                "dedupe_key": key})
            if row:
                found.append(row)

        daily_limit = limits["daily_limit_liters"]
        if total_today > daily_limit:
            raise_("limit_exceeded", "critical", "Daily limit exceeded",
                   f"The household used {total_today:.0f} L today, over the {daily_limit:.0f} L "
                   f"daily limit.", liters=total_today)
        elif total_today >= daily_limit * limits["alert_threshold_pct"] / 100:
            raise_("near_limit", "warning", "Close to the daily limit",
                   f"{total_today:.0f} L used so far — {total_today / daily_limit * 100:.0f}% of "
                   f"the {daily_limit:.0f} L daily limit.", liters=total_today)

        for source_id, liters in today_by_source.items():
            past = history.get(source_id, [])
            if len(past) < MIN_HISTORY_DAYS:
                continue
            usual = sum(past) / len(past)
            if usual > 0 and liters >= usual * multiplier and liters - usual >= MIN_EXTRA_LITERS:
                name = sources[source_id]["name"]
                raise_("high_source", "warning", f"Unusually high {name.lower()} use",
                       f"The {name.lower()} used {liters:.0f} L today — {_times(liters / usual)} "
                       f"its usual amount. {_advice(name)}",
                       source_id=source_id, liters=liters, key=f"high_source:{source_id}:{iso(day)}")

        past_totals = {}
        for r in self.usage.daily_totals(household_id, iso(baseline_start), iso(baseline_end)):
            past_totals[r["usage_date"]] = r["liters"]
        if len(past_totals) >= MIN_HISTORY_DAYS:
            usual_total = sum(past_totals.values()) / len(past_totals)
            if (usual_total > 0 and total_today >= usual_total * multiplier
                    and total_today - usual_total >= MIN_EXTRA_LITERS):
                raise_("high_total", "warning", "Household usage is unusually high",
                       f"{total_today:.0f} L today is {_times(total_today / usual_total)} your "
                       f"usual daily total ({usual_total:.0f} L).", liters=total_today)

        for row in self.alerts.open_for_date(household_id, iso(day), AUTO_KINDS):
            if row["dedupe_key"] not in triggered:
                self.alerts.set_status(row["id"], "resolved")
        return found

    def check_flow(self, household_id, flow_lpm, minutes, when=None):
        """Smart-meter style check: water has been flowing for `minutes` at `flow_lpm`."""
        self.settings.ensure_defaults(household_id)
        if minutes < FLOW_MINUTES or flow_lpm < FLOW_MIN_LPM:
            return None
        when = when or date.today()
        row = self.raise_alert(household_id, {
            "kind": "continuous_flow", "severity": "warning",
            "title": f"Water running for {minutes} minutes",
            "message": f"Main meter is reading {flow_lpm:g} L/min. If nothing is in use, "
                       f"check taps and toilets.",
            "usage_date": iso(when), "liters": round(flow_lpm * minutes, 1),
            "dedupe_key": f"continuous_flow:{iso(when)}"})
        return row

    # -- queries --------------------------------------------------------------
    def get(self, alert_id):
        row = self.alerts.get(alert_id)
        if not row:
            raise NotFoundError("Alert not found.")
        return row

    def list(self, household_id, status="open", kind=None, limit=50):
        if status == "all":
            statuses = None
        elif status == "active":
            statuses = ("open", "acknowledged")
        elif status in STATUSES:
            statuses = (status,)
        else:
            raise ValidationError("status must be open, acknowledged, dismissed, resolved, "
                                  "active or all.")
        return [self.alert_out(r) for r in
                self.alerts.list(household_id, statuses, (kind,) if kind else None, limit)]

    def recent(self, household_id, limit=10):
        return [self.alert_out(r) for r in self.alerts.recent(household_id, limit)]

    def counts(self, household_id):
        return {"open": self.alerts.count(household_id, "open"),
                "open_attention": self.alerts.count(household_id, "open", kinds=ATTENTION_KINDS),
                "unread": sum(self.alerts.count(household_id, s, unread=True)
                              for s in ("open", "acknowledged", "dismissed"))}

    # -- lifecycle ------------------------------------------------------------
    def set_status(self, alert_id, status):
        if status not in STATUSES:
            raise ValidationError("status must be open, acknowledged, dismissed or resolved.")
        self.get(alert_id)
        self.alerts.set_status(alert_id, status)
        return self.alert_out(self.alerts.get(alert_id))

    def mark_all_read(self, household_id):
        return self.alerts.mark_all_read(household_id)

    def delete(self, alert_id):
        self.get(alert_id)
        self.alerts.delete(alert_id)
