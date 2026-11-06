"""TC-09..TC-15: invalid / incomplete input."""
from datetime import date, timedelta

import pytest

from hydrohome.errors import ValidationError
from hydrohome.services import validators as v


def test_household_requires_name_and_city():
    with pytest.raises(ValidationError) as e:
        v.validate_household({"name": " ", "city": "", "members": "2", "daily_target_liters": "100"})
    assert len(e.value.errors) == 2


@pytest.mark.parametrize("members", ["0", "-1", "abc", "31", "2.5", ""])
def test_household_bad_members(members):
    with pytest.raises(ValidationError):
        v.validate_household({"name": "A", "city": "B", "members": members, "daily_target_liters": "100"})


def test_reading_rejects_bad_values():
    base = {"household_id": 1, "reading_date": "2026-10-01", "meter_reading": "5", "notes": ""}
    for bad in ({"meter_reading": "-3"}, {"meter_reading": "abc"}, {"reading_date": "10/01/2026"},
                {"reading_date": (date.today() + timedelta(days=2)).isoformat()}):
        with pytest.raises(ValidationError):
            v.validate_reading({**base, **bad})


def test_reading_valid_is_normalised():
    out = v.validate_reading({"household_id": "2", "reading_date": " 2026-10-01 ",
                              "meter_reading": "12.34567", "notes": " hi "})
    assert out == {"household_id": 2, "reading_date": "2026-10-01", "meter_reading": 12.346, "notes": "hi"}


def test_reminder_validation():
    good = {"household_id": 1, "title": "Pay", "reminder_type": "Bill Payment",
            "due_date": "2026-12-01", "due_time": "09:30", "repeat_rule": "None", "notes": ""}
    assert v.validate_reminder(good)["due_at"] == "2026-12-01 09:30"
    for bad in ({"title": ""}, {"due_time": "25:99"}, {"due_date": "tomorrow"},
                {"reminder_type": "Nope"}, {"repeat_rule": "Hourly"}):
        with pytest.raises(ValidationError):
            v.validate_reminder({**good, **bad})
