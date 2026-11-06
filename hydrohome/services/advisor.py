"""Turns weather data into suggested reminders (this is where the API data is *used*)."""
from dataclasses import dataclass
from datetime import datetime, timedelta

from hydrohome import config


@dataclass(frozen=True)
class Suggestion:
    title: str
    reminder_type: str
    due_at: str
    reason: str


def _due(day_text, hour, minute, now):
    due = datetime.strptime(day_text, config.DATE_FMT).replace(hour=hour, minute=minute)
    if due <= now:                                   # slot already passed today
        due = (now + timedelta(hours=1)).replace(second=0, microsecond=0)
    return due.strftime(config.DATETIME_FMT)


def weather_suggestions(forecast, now=None):
    now = now or datetime.now()
    out = []
    rainy = next((d for d in forecast.days
                  if d.rain_mm >= config.HEAVY_RAIN_MM
                  or d.rain_probability >= config.HIGH_RAIN_PROBABILITY), None)
    hot = next((d for d in forecast.days if d.temp_max >= config.HOT_DAY_CELSIUS), None)
    if rainy:
        out.append(Suggestion(
            f"Rain expected {rainy.date}: skip garden watering", "Conservation Tip",
            _due(rainy.date, 6, 0, now),
            f"{rainy.rain_mm:.1f} mm rain, {rainy.rain_probability}% chance. "
            "Collect rainwater instead."))
    if hot:
        out.append(Suggestion(
            f"Hot day {hot.date}: water plants early and check for leaks", "Garden Watering",
            _due(hot.date, 5, 30, now),
            f"High of {hot.temp_max:.0f}°C. Water before sunrise to cut evaporation; "
            "usage tends to rise in heat."))
    return out
