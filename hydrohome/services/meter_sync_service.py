"""Smart-meter auto-sync: pull the cumulative meter value from a JSON source and store it
as a normal reading, so usage, status, charts and reports update without manual typing.

Supported sources
  URL  - an HTTP(S) endpoint returning JSON (optional API key sent as Bearer + X-API-Key)
  FILE - a local JSON file that the meter/utility software keeps up to date
The value is located with a dotted path such as  data.total_m3  or  readings.0.value.
"""
import json
from datetime import datetime
from pathlib import Path

import requests

from hydrohome import config
from hydrohome.errors import AppError, MeterSyncError
from hydrohome.services.validators import validate_meter_source


def extract_value(payload, path):
    """Walk a dotted path through dicts/lists and return the node."""
    node = payload
    for part in path.split("."):
        try:
            node = node[int(part)] if isinstance(node, list) else node[part]
        except (KeyError, IndexError, ValueError, TypeError) as exc:
            raise MeterSyncError(f"Could not find '{path}' in the meter data "
                                 f"(stopped at '{part}').") from exc
    return node


def to_cubic_metres(raw, unit):
    try:
        value = float(raw)
    except (TypeError, ValueError) as exc:
        raise MeterSyncError(f"The meter value '{raw}' is not a number.") from exc
    if value != value or value < 0:
        raise MeterSyncError("The meter value must be zero or higher.")
    return round(value / 1000 if unit == "liters" else value, 3)


class MeterSyncService:
    def __init__(self, sources_repo, reading_service, session=None,
                 timeout=config.API_TIMEOUT_SECONDS):
        self.sources = sources_repo
        self.readings = reading_service
        self.session = session or requests.Session()
        self.timeout = timeout

    # ---- configuration (CRUD) -------------------------------------------------
    def list_sources(self):
        return self.sources.list_all()

    def get_for_household(self, household_id):
        return self.sources.get_for_household(household_id)

    def save(self, form):
        data = validate_meter_source(form)
        if not self.readings.households.get(data["household_id"]):
            raise MeterSyncError("Please choose an existing household.")
        self.sources.save(data)

    def delete(self, source_id):
        if self.sources.delete(source_id) == 0:
            raise MeterSyncError("That meter source no longer exists.")

    # ---- fetching -------------------------------------------------------------
    def _load_payload(self, source):
        if source["source_type"] == "FILE":
            path = Path(source["location"])
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except FileNotFoundError as exc:
                raise MeterSyncError(f"Meter file not found: {path}") from exc
            except PermissionError as exc:
                raise MeterSyncError(f"Permission denied reading: {path}") from exc
            except (ValueError, UnicodeDecodeError) as exc:
                raise MeterSyncError("The meter file is not valid JSON.") from exc
            except OSError as exc:
                raise MeterSyncError(f"Cannot read meter file: {exc}") from exc
        headers = {"Accept": "application/json"}
        if source["api_key"]:
            headers["Authorization"] = f"Bearer {source['api_key']}"
            headers["X-API-Key"] = source["api_key"]
        try:
            response = self.session.get(source["location"], headers=headers, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except requests.Timeout as exc:
            raise MeterSyncError("The smart meter took too long to respond.") from exc
        except requests.ConnectionError as exc:
            raise MeterSyncError("Cannot reach the smart meter. Check the address "
                                 "and your network.") from exc
        except requests.HTTPError as exc:
            code = exc.response.status_code if exc.response is not None else "?"
            hint = " (check the API key)" if code in (401, 403) else ""
            raise MeterSyncError(f"The smart meter returned HTTP {code}{hint}.") from exc
        except requests.RequestException as exc:
            raise MeterSyncError(f"Smart meter request failed: {exc}") from exc
        except ValueError as exc:
            raise MeterSyncError("The smart meter sent an invalid (non-JSON) response.") from exc

    def fetch_value_m3(self, source):
        payload = self._load_payload(source)
        return to_cubic_metres(extract_value(payload, source["reading_path"]), source["unit"])

    # ---- syncing --------------------------------------------------------------
    def _store(self, source, value, now):
        today = now.strftime(config.DATE_FMT)
        form = {"household_id": source["household_id"], "reading_date": today,
                "meter_reading": value, "notes": "Smart meter auto-sync"}
        existing = next((r for r in self.readings.readings.for_household(source["household_id"])
                         if r["reading_date"] == today), None)
        if existing:
            self.readings.update(existing["id"], form)
            return f"Updated today's reading: {value} m³"
        self.readings.add(form)
        return f"New reading saved: {value} m³"

    def sync_source(self, source, now=None):
        """Fetch + store one reading. Records the outcome on the source and re-raises failures."""
        now = now or datetime.now()
        stamp = now.strftime(config.DATETIME_FMT)
        try:
            message = self._store(source, self.fetch_value_m3(source), now)
        except AppError as exc:
            problem = (exc if isinstance(exc, MeterSyncError)
                       else MeterSyncError("Reading rejected: " + str(exc)))
            self.sources.record_sync(source["id"], stamp, "Failed: " + str(problem))
            raise problem from exc
        self.sources.record_sync(source["id"], stamp, "OK: " + message)
        return message

    def sync_household(self, household_id, now=None):
        source = self.sources.get_for_household(household_id)
        if not source:
            raise MeterSyncError("This household has no smart meter source configured.")
        return self.sync_source(source, now)

    def is_due(self, source, now):
        if not source["last_sync_at"]:
            return True
        last = datetime.strptime(source["last_sync_at"], config.DATETIME_FMT)
        return (now - last).total_seconds() >= source["interval_minutes"] * 60

    def sync_due(self, now=None):
        """Sync every enabled source whose interval has elapsed.
        Returns [(household_id, ok, message)]; one failing meter never blocks the others."""
        now = now or datetime.now()
        results = []
        for source in self.sources.list_enabled():
            if not self.is_due(source, now):
                continue
            try:
                results.append((source["household_id"], True, self.sync_source(source, now)))
            except AppError as exc:
                results.append((source["household_id"], False, str(exc)))
        return results
