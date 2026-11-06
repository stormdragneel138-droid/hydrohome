"""TC-36..TC-42: CSV export/import, report, file errors."""
import os

import pytest

from hydrohome.errors import FileServiceError


def add_two(services, hid):
    for d, m in (("2026-10-01", 100), ("2026-10-11", 104)):
        services.readings.add({"household_id": hid, "reading_date": d, "meter_reading": m, "notes": ""})


def test_export_readings_csv(services, household, tmp_path):
    add_two(services, household)
    out = tmp_path / "r.csv"
    assert services.reports.export_readings(out) == 2
    text = out.read_text().splitlines()
    assert text[0].startswith("Date,Household") and len(text) == 3


def test_import_valid_and_invalid_rows(services, household, tmp_path):
    f = tmp_path / "in.csv"
    f.write_text("reading_date,meter_reading,notes\n2026-10-01,100,a\n2026-10-11,abc,b\n"
                 "2026-10-21,110,c\n2026-10-15,50,d\n")
    added, errors = services.reports.import_readings(f, household)
    assert added == 2 and len(errors) == 2
    assert errors[0].startswith("Line 3")


def test_import_missing_file(services, household, tmp_path):
    with pytest.raises(FileServiceError, match="not found"):
        services.reports.import_readings(tmp_path / "missing.csv", household)


def test_import_wrong_columns_and_empty(services, household, tmp_path):
    f = tmp_path / "bad.csv"
    f.write_text("a,b\n1,2\n")
    with pytest.raises(FileServiceError, match="missing required"):
        services.reports.import_readings(f, household)
    f.write_text("reading_date,meter_reading\n")
    with pytest.raises(FileServiceError, match="no data rows"):
        services.reports.import_readings(f, household)


def test_import_binary_file(services, household, tmp_path):
    f = tmp_path / "x.csv"
    f.write_bytes(b"\xff\xfe\x00\x81\x82")
    with pytest.raises(FileServiceError):
        services.reports.import_readings(f, household)


@pytest.mark.skipif(os.name == "nt" or os.geteuid() == 0, reason="needs a non-root POSIX user")
def test_export_permission_denied(services, household, tmp_path):
    locked = tmp_path / "locked"
    locked.mkdir()
    locked.chmod(0o500)
    with pytest.raises(FileServiceError, match="Permission denied"):
        services.reports.export_readings(locked / "r.csv")


def test_usage_report_contents(services, household, tmp_path):
    add_two(services, household)
    out = tmp_path / "rep.txt"
    services.reports.save_usage_report(out, household)
    body = out.read_text()
    assert "Cruz" in body and "Near limit" in body and "PENDING REMINDERS" in body
