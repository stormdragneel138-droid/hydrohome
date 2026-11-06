"""TC-43..TC-58: smart meter auto-sync (config CRUD, parsing, errors, scheduling)."""
import json
import threading
from datetime import datetime, timedelta
from http.server import HTTPServer

import pytest
import requests

from hydrohome.container import build_services
from hydrohome.errors import MeterSyncError, ValidationError
from hydrohome.services.meter_sync_service import extract_value, to_cubic_metres
from scripts.mock_smart_meter import make_handler

NOW = datetime(2026, 11, 5, 10, 0)


class FakeResponse:
    def __init__(self, payload=None, status=200, bad_json=False):
        self.payload, self.status_code, self.bad_json = payload, status, bad_json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(response=self)

    def json(self):
        if self.bad_json:
            raise ValueError("x")
        return self.payload


class FakeSession:
    def __init__(self, *items):
        self.items, self.calls = list(items), []

    def get(self, url, headers=None, timeout=None):
        self.calls.append((url, headers, timeout))
        item = self.items.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def source_form(hid, **over):
    base = {"household_id": hid, "source_type": "URL", "location": "http://meter.local/api",
            "api_key": "", "reading_path": "data.total_m3", "unit": "m3",
            "interval_minutes": "60", "enabled": True}
    return {**base, **over}


def make(tmp_path, *responses):
    s = build_services(tmp_path / "m.db", meter_session=FakeSession(*responses))
    hid = s.households.add({"name": "Cruz", "address": "", "city": "Tarlac City",
                            "members": "4", "daily_target_liters": "100"})
    return s, hid


def ok(value):
    return FakeResponse({"data": {"total_m3": value}})


def test_config_crud(tmp_path):
    s, hid = make(tmp_path)
    s.meters.save(source_form(hid))
    s.meters.save(source_form(hid, interval_minutes="15"))          # upsert = update
    rows = s.meters.list_sources()
    assert len(rows) == 1 and rows[0]["interval_minutes"] == 15
    s.meters.delete(rows[0]["id"])
    assert s.meters.list_sources() == []


@pytest.mark.parametrize("bad", [{"location": ""}, {"location": "ftp://x"}, {"reading_path": ""},
                                 {"unit": "gallons"}, {"interval_minutes": "0"}, {"source_type": "BLE"}])
def test_config_validation(tmp_path, bad):
    s, hid = make(tmp_path)
    with pytest.raises(ValidationError):
        s.meters.save(source_form(hid, **bad))


def test_sync_creates_reading_with_api_key_headers(tmp_path):
    s, hid = make(tmp_path, ok(123.4))
    s.meters.save(source_form(hid, api_key="k1"))
    assert "123.4" in s.meters.sync_household(hid, NOW)
    row = s.readings.list_with_usage(hid)[0]
    assert row["meter_reading"] == 123.4 and row["reading_date"] == "2026-11-05"
    _url, headers, timeout = s.meters.session.calls[0]
    assert headers["Authorization"] == "Bearer k1" and headers["X-API-Key"] == "k1" and timeout


def test_second_sync_same_day_updates_not_duplicates(tmp_path):
    s, hid = make(tmp_path, ok(100), ok(101.5))
    s.meters.save(source_form(hid))
    s.meters.sync_household(hid, NOW)
    s.meters.sync_household(hid, NOW + timedelta(hours=2))
    rows = s.readings.list_with_usage(hid)
    assert len(rows) == 1 and rows[0]["meter_reading"] == 101.5


def test_liters_are_converted_and_nested_paths_work(tmp_path):
    s, hid = make(tmp_path, FakeResponse({"readings": [{"v": 98765}]}))
    s.meters.save(source_form(hid, unit="liters", reading_path="readings.0.v"))
    s.meters.sync_household(hid, NOW)
    assert s.readings.list_with_usage(hid)[0]["meter_reading"] == 98.765


def test_extract_and_convert_helpers():
    assert extract_value({"a": {"b": [5, 6]}}, "a.b.1") == 6
    with pytest.raises(MeterSyncError):
        extract_value({"a": 1}, "a.b")
    for bad in ("abc", None, -4, float("nan")):
        with pytest.raises(MeterSyncError):
            to_cubic_metres(bad, "m3")


@pytest.mark.parametrize("failure,text", [
    (requests.Timeout(), "too long"), (requests.ConnectionError(), "Cannot reach"),
    (FakeResponse(status=401), "API key"), (FakeResponse(status=500), "HTTP 500"),
    (FakeResponse(bad_json=True), "non-JSON"), (FakeResponse({"other": 1}), "Could not find"),
    (FakeResponse({"data": {"total_m3": "n/a"}}), "not a number")])
def test_failures_are_reported_and_recorded(tmp_path, failure, text):
    s, hid = make(tmp_path, failure)
    s.meters.save(source_form(hid))
    with pytest.raises(MeterSyncError, match=text):
        s.meters.sync_household(hid, NOW)
    assert s.meters.list_sources()[0]["last_status"].startswith("Failed")
    assert s.readings.list_with_usage(hid) == []


def test_meter_value_lower_than_previous_is_rejected(tmp_path):
    s, hid = make(tmp_path, ok(50))
    s.readings.add({"household_id": hid, "reading_date": "2026-10-01", "meter_reading": 100, "notes": ""})
    s.meters.save(source_form(hid))
    with pytest.raises(MeterSyncError, match="rejected"):
        s.meters.sync_household(hid, NOW)


def test_file_source(tmp_path):
    f = tmp_path / "meter.json"
    f.write_text(json.dumps({"data": {"total_m3": 77.7}}))
    s, hid = make(tmp_path)
    s.meters.save(source_form(hid, source_type="FILE", location=str(f)))
    s.meters.sync_household(hid, NOW)
    assert s.readings.list_with_usage(hid)[0]["meter_reading"] == 77.7
    f.write_text("{not json")
    with pytest.raises(MeterSyncError, match="not valid JSON"):
        s.meters.sync_household(hid, NOW + timedelta(hours=1))
    f.unlink()
    with pytest.raises(MeterSyncError, match="not found"):
        s.meters.sync_household(hid, NOW + timedelta(hours=2))


def test_sync_without_configuration(tmp_path):
    s, hid = make(tmp_path)
    with pytest.raises(MeterSyncError, match="no smart meter"):
        s.meters.sync_household(hid)


def test_scheduler_respects_interval_enabled_and_isolates_failures(tmp_path):
    s, hid = make(tmp_path, ok(10), requests.Timeout(), ok(11))
    s.meters.save(source_form(hid, interval_minutes="30"))
    first = s.meters.sync_due(NOW)
    assert first[0][1] is True
    assert s.meters.sync_due(NOW + timedelta(minutes=10)) == []           # not due yet
    second = s.meters.sync_due(NOW + timedelta(minutes=31))
    assert second[0][1] is False                                           # failure reported, no crash
    s.meters.save(source_form(hid, enabled=False))
    assert s.meters.sync_due(NOW + timedelta(hours=5)) == []               # disabled


def test_end_to_end_against_simulated_meter_over_real_http(tmp_path):
    server = HTTPServer(("127.0.0.1", 0), make_handler(start=150.0, rate=0.0, key="secret"))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_port}/meter"
    s = build_services(tmp_path / "e2e.db")                                 # real requests.Session
    hid = s.households.add({"name": "E2E", "address": "", "city": "X", "members": "2",
                            "daily_target_liters": "100"})
    try:
        s.meters.save(source_form(hid, location=url, api_key="wrong"))
        with pytest.raises(MeterSyncError, match="API key"):
            s.meters.sync_household(hid)
        s.meters.save(source_form(hid, location=url, api_key="secret"))
        s.meters.sync_household(hid)
        assert s.readings.list_with_usage(hid)[0]["meter_reading"] == 150.0
    finally:
        server.shutdown()
        server.server_close()
    with pytest.raises(MeterSyncError, match="Cannot reach"):               # server now down
        s.meters.sync_household(hid)
