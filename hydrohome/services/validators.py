"""Input validation. Each function returns cleaned data or raises ValidationError
listing EVERY problem at once (better UX than one error at a time)."""
from datetime import date, datetime

from hydrohome import config
from hydrohome.errors import ValidationError


def _text(form, key):
    return str(form.get(key, "")).strip()


def _int(form, key, label, lo, hi, errors):
    raw = _text(form, key)
    try:
        value = int(raw)
    except ValueError:
        errors.append(f"{label} must be a whole number.")
        return None
    if not lo <= value <= hi:
        errors.append(f"{label} must be between {lo} and {hi}.")
        return None
    return value


def _max_len(value, label, limit, errors):
    if len(value) > limit:
        errors.append(f"{label} must be at most {limit} characters.")


def parse_date(text):
    return datetime.strptime(text.strip(), config.DATE_FMT).date()


def validate_household(form):
    errors = []
    name, city = _text(form, "name"), _text(form, "city")
    address, notes = _text(form, "address"), ""
    if not name:
        errors.append("Household name is required.")
    if not city:
        errors.append("City is required.")
    _max_len(name, "Household name", 60, errors)
    _max_len(city, "City", 60, errors)
    _max_len(address, "Address", 120, errors)
    members = _int(form, "members", "Number of members", 1, 30, errors)
    target = _int(form, "daily_target_liters", "Daily target (litres/person)", 20, 500, errors)
    if errors:
        raise ValidationError(errors)
    return {"name": name, "address": address, "city": city,
            "members": members, "daily_target_liters": target}


def validate_reading(form):
    errors = []
    hid = _int(form, "household_id", "Household", 1, 10**9, errors)
    reading_date = None
    try:
        reading_date = parse_date(_text(form, "reading_date"))
        if reading_date > date.today():
            errors.append("Reading date cannot be in the future.")
    except ValueError:
        errors.append("Reading date must use the format YYYY-MM-DD.")
    meter = None
    try:
        meter = float(_text(form, "meter_reading"))
        if meter < 0 or meter != meter or meter > 9_999_999:
            errors.append("Meter reading must be between 0 and 9,999,999 m³.")
    except ValueError:
        errors.append("Meter reading must be a number (cubic metres).")
    notes = _text(form, "notes")
    _max_len(notes, "Notes", 200, errors)
    if errors:
        raise ValidationError(errors)
    return {"household_id": hid, "reading_date": reading_date.strftime(config.DATE_FMT),
            "meter_reading": round(meter, 3), "notes": notes}


def validate_reminder(form):
    errors = []
    hid = _int(form, "household_id", "Household", 1, 10**9, errors)
    title = _text(form, "title")
    if not title:
        errors.append("Reminder title is required.")
    _max_len(title, "Title", 80, errors)
    rtype = _text(form, "reminder_type")
    if rtype not in config.REMINDER_TYPES:
        errors.append("Please choose a reminder type.")
    repeat = _text(form, "repeat_rule") or "None"
    if repeat not in config.REPEAT_RULES:
        errors.append("Please choose a valid repeat option.")
    due_at = None
    try:
        due = datetime.strptime(f"{_text(form, 'due_date')} {_text(form, 'due_time')}",
                                config.DATETIME_FMT)
        due_at = due.strftime(config.DATETIME_FMT)
    except ValueError:
        errors.append("Due date/time must use YYYY-MM-DD and HH:MM (24-hour).")
    notes = _text(form, "notes")
    _max_len(notes, "Notes", 200, errors)
    if errors:
        raise ValidationError(errors)
    return {"household_id": hid, "title": title, "reminder_type": rtype,
            "due_at": due_at, "repeat_rule": repeat, "notes": notes}


def validate_meter_source(form):
    errors = []
    hid = _int(form, "household_id", "Household", 1, 10**9, errors)
    stype = _text(form, "source_type")
    if stype not in config.METER_SOURCE_TYPES:
        errors.append("Source type must be URL or FILE.")
    location = _text(form, "location")
    if not location:
        errors.append("Source location (URL or file path) is required.")
    elif stype == "URL" and not location.lower().startswith(("http://", "https://")):
        errors.append("A URL source must start with http:// or https://")
    _max_len(location, "Location", 300, errors)
    path = _text(form, "reading_path")
    if not path:
        errors.append("The JSON path of the meter value is required (example: data.total_m3).")
    unit = _text(form, "unit")
    if unit not in config.METER_UNITS:
        errors.append("Unit must be m3 or liters.")
    api_key = _text(form, "api_key")
    _max_len(api_key, "API key", 200, errors)
    interval = _int(form, "interval_minutes", "Sync interval (minutes)", 1, 1440, errors)
    if errors:
        raise ValidationError(errors)
    return {"household_id": hid, "source_type": stype, "location": location, "api_key": api_key,
            "reading_path": path, "unit": unit, "interval_minutes": interval,
            "enabled": 1 if form.get("enabled") in (True, 1, "1", "true", "True") else 0}
