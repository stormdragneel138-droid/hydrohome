"""TC-01..TC-08: CRUD, search, persistence, DB errors."""
import pytest

from hydrohome.container import build_services
from hydrohome.database import connection
from hydrohome.errors import DatabaseError, ValidationError

FORM = {"name": "Reyes", "address": "", "city": "Manila", "members": "3", "daily_target_liters": "90"}


def test_create_and_read_household(services):
    hid = services.households.add(FORM)
    assert services.households.get(hid)["name"] == "Reyes"


def test_update_household(services, household):
    services.households.update(household, {**FORM, "name": "Cruz-Updated"})
    assert services.households.get(household)["name"] == "Cruz-Updated"


def test_delete_household_cascades(services, household):
    services.readings.add({"household_id": household, "reading_date": "2026-10-01",
                           "meter_reading": "10", "notes": ""})
    services.households.delete(household)
    assert services.households.get(household) is None
    assert services.readings.list_with_usage() == []


def test_search_households(services, household):
    services.households.add(FORM)
    assert [h["name"] for h in services.households.list("Manila")] == ["Reyes"]
    assert len(services.households.list("")) == 2


def test_data_persists_after_reopen(tmp_path):
    path = tmp_path / "p.db"
    build_services(path).households.add(FORM)
    assert len(build_services(path).households.list()) == 1      # "restart" the app


def test_duplicate_name_is_rejected(services, household):
    with pytest.raises(DatabaseError):
        services.households.add({**FORM, "name": "Cruz"})


def test_sql_injection_text_is_stored_literally(services):
    evil = "x'); DROP TABLE households;--"
    services.households.add({**FORM, "name": evil})
    assert services.households.list()[0]["name"] == evil           # table still exists


def test_blocked_data_folder_raises_database_error(tmp_path):
    blocker = tmp_path / "blocker"
    blocker.write_text("i am a file, not a folder")
    with pytest.raises(DatabaseError):
        connection.initialize(blocker / "x.db")


def test_corrupted_database_file_raises_database_error(tmp_path):
    bad = tmp_path / "bad.db"
    bad.write_bytes(b"this is definitely not a sqlite database" * 50)
    with pytest.raises(DatabaseError):
        build_services(bad)


def test_update_missing_record(services):
    with pytest.raises(ValidationError):
        services.households.update(999, FORM)
