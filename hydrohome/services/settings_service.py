"""Per-household settings: consumption limits, water sources, notification preferences."""
import re

from hydrohome import config
from hydrohome.errors import ConflictError, NotFoundError, ValidationError

DEFAULT_SOURCES = (("Showers & baths", "#267e78"), ("Garden", "#68a397"), ("Toilets", "#9bbcad"),
                   ("Laundry", "#c2d1ba"), ("Kitchen", "#dde2cf"))
_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")
_TIME = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def _num(value, label, lo, hi, errors):
    try:
        number = float(value)
    except (TypeError, ValueError):
        errors.append(f"{label} must be a number.")
        return None
    if not lo <= number <= hi:
        errors.append(f"{label} must be between {lo:g} and {hi:g}.")
        return None
    return number


class SettingsService:
    def __init__(self, households, limits, notifications, sources):
        self.households, self.limits = households, limits
        self.notifications, self.sources = notifications, sources

    # -- defaults -------------------------------------------------------------
    def ensure_defaults(self, household_id):
        """Create default limits, notification settings and sources the first time they are needed."""
        household = self.households.get(household_id)
        if not household:
            raise NotFoundError("Household not found.")
        if not self.limits.get(household_id):
            daily = float(household["members"] * household["daily_target_liters"])
            self.limits.upsert(household_id, {
                "daily_limit_liters": daily, "weekly_limit_liters": daily * 7,
                "alert_threshold_pct": int(config.NEAR_LIMIT_RATIO * 100),
                "spike_multiplier": 1.5, "rate_per_1000_l": 3.0, "currency": "$"})
        if not self.notifications.get(household_id):
            self.notifications.upsert(household_id, {"push_enabled": True, "email_enabled": True,
                                                     "quiet_start": "22:00", "quiet_end": "06:00"})
        if not self.sources.for_household(household_id):
            for name, color in DEFAULT_SOURCES:
                self.sources.add(household_id, name, color)

    # -- limits ---------------------------------------------------------------
    def get_limits(self, household_id):
        self.ensure_defaults(household_id)
        return self.limits.get(household_id)

    def update_limits(self, household_id, form):
        current = self.get_limits(household_id)
        merged = {**current, **{k: v for k, v in form.items() if v is not None}}
        errors = []
        daily = _num(merged["daily_limit_liters"], "Daily limit", 10, 100_000, errors)
        weekly = _num(merged["weekly_limit_liters"], "Weekly limit", 10, 700_000, errors)
        threshold = _num(merged["alert_threshold_pct"], "Alert threshold (%)", 50, 100, errors)
        spike = _num(merged["spike_multiplier"], "Spike multiplier", 1.1, 10, errors)
        rate = _num(merged["rate_per_1000_l"], "Water rate", 0, 10_000, errors)
        currency = str(merged["currency"]).strip()
        if not 1 <= len(currency) <= 3:
            errors.append("Currency symbol must be 1 to 3 characters.")
        if daily is not None and weekly is not None and weekly < daily:
            errors.append("Weekly limit cannot be lower than the daily limit.")
        if errors:
            raise ValidationError(errors)
        self.limits.upsert(household_id, {
            "daily_limit_liters": daily, "weekly_limit_liters": weekly,
            "alert_threshold_pct": int(threshold), "spike_multiplier": spike,
            "rate_per_1000_l": rate, "currency": currency})
        return self.limits.get(household_id)

    # -- notification preferences ---------------------------------------------
    def get_notifications(self, household_id):
        self.ensure_defaults(household_id)
        return self._notif_out(self.notifications.get(household_id))

    def update_notifications(self, household_id, form):
        current = self.get_notifications(household_id)
        merged = {**current, **{k: v for k, v in form.items() if v is not None}}
        errors = []
        for key, label in (("quiet_start", "Quiet hours start"), ("quiet_end", "Quiet hours end")):
            if not _TIME.match(str(merged[key])):
                errors.append(f"{label} must be a time like 22:00.")
        if errors:
            raise ValidationError(errors)
        self.notifications.upsert(household_id, merged)
        return self.get_notifications(household_id)

    @staticmethod
    def _notif_out(row):
        return {"household_id": row["household_id"], "push_enabled": bool(row["push_enabled"]),
                "email_enabled": bool(row["email_enabled"]),
                "quiet_start": row["quiet_start"], "quiet_end": row["quiet_end"]}

    # -- water sources (the "devices" / sensors) -------------------------------
    @staticmethod
    def source_out(row):
        return {"id": row["id"], "household_id": row["household_id"], "name": row["name"],
                "color": row["color"], "enabled": bool(row["enabled"])}

    def list_sources(self, household_id):
        self.ensure_defaults(household_id)
        return [self.source_out(r) for r in self.sources.for_household(household_id)]

    def _clean_source(self, form, household_id, exclude_id=None):
        name = str(form.get("name", "")).strip()
        color = str(form.get("color") or "#267e78").strip()
        errors = []
        if not name or len(name) > 40:
            errors.append("Source name is required (max 40 characters).")
        if not _COLOR.match(color):
            errors.append("Color must look like #267e78.")
        twin = self.sources.find_by_name(household_id, name) if name else None
        if twin and twin["id"] != exclude_id:
            errors.append("A source with this name already exists.")
        if errors:
            raise ValidationError(errors)
        return name, color

    def add_source(self, household_id, form):
        self.ensure_defaults(household_id)
        name, color = self._clean_source(form, household_id)
        sid = self.sources.add(household_id, name, color, form.get("enabled", True))
        return self.source_out(self.sources.get(sid))

    def get_source(self, source_id):
        row = self.sources.get(source_id)
        if not row:
            raise NotFoundError("Water source not found.")
        return row

    def update_source(self, source_id, form):
        row = self.get_source(source_id)
        merged = {"name": row["name"], "color": row["color"], "enabled": bool(row["enabled"]),
                  **{k: v for k, v in form.items() if v is not None}}
        name, color = self._clean_source(merged, row["household_id"], exclude_id=source_id)
        self.sources.update(source_id, name, color, merged["enabled"])
        return self.source_out(self.sources.get(source_id))

    def delete_source(self, source_id):
        self.get_source(source_id)
        used = self.sources.usage_count(source_id)
        if used:
            raise ConflictError(f"This source has {used} usage entries. Disable it instead of "
                                f"deleting it, or delete those entries first.")
        self.sources.delete(source_id)
