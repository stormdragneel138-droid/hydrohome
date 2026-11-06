"""TC-16..TC-21: meter logic and usage calculations."""
import pytest

from hydrohome.errors import ValidationError
from hydrohome.services import consumption


def reading(hid, day, meter):
    return {"household_id": hid, "reading_date": day, "meter_reading": str(meter), "notes": ""}


def test_usage_calculation(services, household):
    services.readings.add(reading(household, "2026-10-01", 100))
    services.readings.add(reading(household, "2026-10-11", 104))     # 4 m3 / 10 days / 4 people
    rows = services.readings.list_with_usage(household)
    latest = rows[0]
    assert latest["used_m3"] == 4.0
    assert latest["liters_per_person_day"] == 100.0
    assert latest["status"] == "Near limit"
    assert rows[1]["status"] == "Baseline"


def test_meter_cannot_run_backwards(services, household):
    services.readings.add(reading(household, "2026-10-01", 100))
    with pytest.raises(ValidationError):
        services.readings.add(reading(household, "2026-10-05", 90))


def test_insert_between_readings_checked_both_sides(services, household):
    services.readings.add(reading(household, "2026-10-01", 100))
    services.readings.add(reading(household, "2026-10-20", 120))
    with pytest.raises(ValidationError):
        services.readings.add(reading(household, "2026-10-10", 130))
    services.readings.add(reading(household, "2026-10-10", 110))


def test_duplicate_date_rejected(services, household):
    services.readings.add(reading(household, "2026-10-01", 100))
    with pytest.raises(ValidationError):
        services.readings.add(reading(household, "2026-10-01", 101))


def test_reading_for_missing_household(services):
    with pytest.raises(ValidationError):
        services.readings.add(reading(77, "2026-10-01", 1))


def test_classify_and_summary():
    assert consumption.classify(80, 100) == "Within target"
    assert consumption.classify(95, 100) == "Near limit"
    assert consumption.classify(101, 100) == "Over target"
    assert consumption.summarize([], 4, 100)["status"] == "none"
    periods = consumption.build_periods(
        [{"id": 1, "reading_date": "2026-01-01", "meter_reading": 0},
         {"id": 2, "reading_date": "2026-01-11", "meter_reading": 2},
         {"id": 3, "reading_date": "2026-01-21", "meter_reading": 6}], 2, 100)
    s = consumption.summarize(periods, 2, 100)
    assert s["total_m3"] == 6 and s["avg_liters_per_person_day"] == 150.0
