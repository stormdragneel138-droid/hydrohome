"""TC-22..TC-27: reminder engine."""
from datetime import datetime

import pytest

from hydrohome.errors import ValidationError
from hydrohome.services.reminder_service import add_repeat


def form(hid, when="2026-11-01", time="08:00", repeat="None"):
    return {"household_id": hid, "title": "Read meter", "reminder_type": "Meter Reading",
            "due_date": when, "due_time": time, "repeat_rule": repeat, "notes": ""}


def test_due_reminder_alerts_only_once(services, household):
    services.reminders.add(form(household))
    now = datetime(2026, 11, 2, 9, 0)
    assert len(services.reminders.collect_due_alerts(now)) == 1
    assert services.reminders.collect_due_alerts(now) == []


def test_future_reminder_does_not_alert(services, household):
    services.reminders.add(form(household, when="2026-12-25"))
    assert services.reminders.collect_due_alerts(datetime(2026, 11, 5, 9, 0)) == []


def test_complete_one_off_marks_done(services, household):
    rid = services.reminders.add(form(household))
    services.reminders.complete(rid)
    assert services.reminders.list("Done")[0]["id"] == rid


def test_complete_repeating_rolls_forward_and_alerts_again(services, household):
    rid = services.reminders.add(form(household, repeat="Weekly"))
    services.reminders.collect_due_alerts(datetime(2026, 11, 2, 9, 0))
    services.reminders.complete(rid, now=datetime(2026, 11, 2, 9, 0))
    r = services.reminders.list("Pending")[0]
    assert r["due_at"] == "2026-11-08 08:00"
    assert len(services.reminders.collect_due_alerts(datetime(2026, 11, 8, 8, 5))) == 1


def test_monthly_clamps_to_month_end():
    assert add_repeat(datetime(2026, 1, 31, 8, 0), "Monthly") == datetime(2026, 2, 28, 8, 0)
    assert add_repeat(datetime(2026, 12, 15, 8, 0), "Monthly") == datetime(2027, 1, 15, 8, 0)


def test_reminder_crud_and_validation(services, household):
    rid = services.reminders.add(form(household))
    services.reminders.update(rid, {**form(household), "title": "Changed"})
    assert services.reminders.list(search="Changed")
    with pytest.raises(ValidationError):
        services.reminders.add({**form(household), "title": ""})
    services.reminders.delete(rid)
    assert services.reminders.list() == []
