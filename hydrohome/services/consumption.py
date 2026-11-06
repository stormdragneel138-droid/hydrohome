"""Pure functions that turn meter readings into usage figures (easy to unit test)."""
from dataclasses import dataclass
from datetime import date

from hydrohome import config

STATUS_OK, STATUS_NEAR, STATUS_OVER = "Within target", "Near limit", "Over target"

TIPS = {
    STATUS_OK: ["Great job - keep it up!",
                "Re-check the meter every month to spot changes early.",
                "Collect rinse water for plants or cleaning."],
    STATUS_NEAR: ["You are close to your daily target.",
                  "Shorten showers by 1-2 minutes.",
                  "Run washing machines only with full loads."],
    STATUS_OVER: ["Usage is above target - look for leaks first.",
                  "Leak test: turn off all taps, then see if the meter still moves.",
                  "Fix dripping faucets and running toilets; use a basin when washing dishes.",
                  "Water plants early morning or evening to reduce evaporation."],
    "none": ["Add at least two meter readings to see your usage."],
}


@dataclass(frozen=True)
class UsagePeriod:
    reading_id: int
    start: date
    end: date
    days: int
    used_m3: float
    liters_per_day: float
    liters_per_person_day: float
    status: str


def classify(liters_per_person_day, target):
    ratio = liters_per_person_day / target
    if ratio > 1:
        return STATUS_OVER
    if ratio >= config.NEAR_LIMIT_RATIO:
        return STATUS_NEAR
    return STATUS_OK


def build_periods(readings, members, target):
    """readings: dicts with id/reading_date/meter_reading. Returns one UsagePeriod per
    consecutive pair of readings, ordered oldest -> newest."""
    ordered = sorted(readings, key=lambda r: (r["reading_date"], r["id"]))
    periods = []
    for prev, cur in zip(ordered, ordered[1:]):
        start = date.fromisoformat(prev["reading_date"])
        end = date.fromisoformat(cur["reading_date"])
        days = (end - start).days
        if days <= 0:
            continue
        used = max(cur["meter_reading"] - prev["meter_reading"], 0.0)
        per_day = used * 1000 / days
        per_person = per_day / members
        periods.append(UsagePeriod(cur["id"], start, end, days, round(used, 3),
                                   round(per_day, 1), round(per_person, 1),
                                   classify(per_person, target)))
    return periods


def summarize(periods, members, target):
    """Overall figures: weighted average across all periods plus the latest status."""
    if not periods:
        return {"periods": 0, "total_m3": 0.0, "avg_liters_per_person_day": 0.0,
                "latest": None, "status": "none", "target": target}
    total_l = sum(p.used_m3 * 1000 for p in periods)
    total_days = sum(p.days for p in periods)
    avg = total_l / total_days / members
    return {"periods": len(periods), "total_m3": round(sum(p.used_m3 for p in periods), 3),
            "avg_liters_per_person_day": round(avg, 1), "latest": periods[-1],
            "status": periods[-1].status, "target": target}


def tips_for(status):
    return TIPS.get(status, TIPS["none"])
