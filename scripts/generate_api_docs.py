"""Regenerates docs/API.md by calling the real API (fresh temporary database) and recording
every request and response. Run:  python scripts/generate_api_docs.py"""
import json
import sys
import tempfile
import warnings
from datetime import date, timedelta
from pathlib import Path

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from hydrohome.api.app import create_app  # noqa: E402

app = create_app(Path(tempfile.mkdtemp()) / "docs.db", start_scheduler=False)
client = TestClient(app)
out, state = [], {"token": ""}
day = lambda n=0: (date.today() - timedelta(days=n)).isoformat()


def short(obj, depth=0):
    """Shorten long lists so the docs stay readable."""
    if isinstance(obj, list):
        keep = [short(x, depth + 1) for x in obj[:2]]
        return keep + ([f"... {len(obj) - 2} more"] if len(obj) > 2 else [])
    if isinstance(obj, dict):
        return {k: short(v, depth + 1) for k, v in obj.items()}
    return obj


def ex(title, method, path, body=None, auth=True, note="", trim=True, show_path=None):
    headers = {"Authorization": f"Bearer {state['token']}"} if auth else {}
    res = client.request(method, path, json=body, headers=headers)
    curl = f"curl -X {method} http://127.0.0.1:8000{show_path or path}"
    if auth:
        curl += ' \\\n  -H "Authorization: Bearer $TOKEN"'
    if body is not None:
        curl += f" \\\n  -H \"Content-Type: application/json\" \\\n  -d '{json.dumps(body)}'"
    if res.headers.get("content-type", "").startswith("text/csv"):
        text = res.text
    elif res.status_code == 204 or not res.content:
        text = "(empty body)"
    else:
        data = res.json()
        text = json.dumps(short(data) if trim else data, indent=2, ensure_ascii=False)
    out.append(f"#### {title}\n{note}\n```bash\n{curl}\n```\n**Response `{res.status_code}`**\n```{'csv' if 'csv' in res.headers.get('content-type','') else 'json'}\n{text}\n```\n")
    return res


# --------------------------------------------------------------------------- scenario
out.append("### Accounts\n")
r = ex("Register", "POST", "/api/auth/register", {"name": "Jamie Lewis", "email": "jamie@example.com", "password": "correct-horse"}, auth=False)
state["token"] = r.json()["token"]
ex("Sign in", "POST", "/api/auth/login", {"email": "jamie@example.com", "password": "correct-horse"}, auth=False)
ex("Who am I", "GET", "/api/auth/me")

out.append("### Households\n")
r = ex("Create a household", "POST", "/api/households", {"name": "Maple House", "city": "Tarlac City", "address": "12 Maple Street", "members": 4, "daily_limit_liters": 500})
hid = r.json()["id"]
ex("List my households", "GET", "/api/households")
ex("Update household details", "PUT", f"/api/households/{hid}", {"members": 5})
ex("Get one household (includes limits)", "GET", f"/api/households/{hid}")

out.append("### Consumption limits and notification preferences\n")
ex("Read limits", "GET", f"/api/households/{hid}/limits")
ex("Update household water usage limits", "PUT", f"/api/households/{hid}/limits", {"daily_limit_liters": 500, "weekly_limit_liters": 3500, "alert_threshold_pct": 90, "spike_multiplier": 1.5, "rate_per_1000_l": 3.0})
ex("Notification preferences", "PUT", f"/api/households/{hid}/notification-settings", {"quiet_start": "22:00", "quiet_end": "06:00", "email_enabled": True})

out.append("### Water sources\n")
ex("List sources", "GET", f"/api/households/{hid}/sources")
r = ex("Add a source", "POST", f"/api/households/{hid}/sources", {"name": "Pool", "color": "#4a90a4"})
ex("Disable a source", "PUT", f"/api/sources/{r.json()['id']}", {"enabled": False})
ex("Delete a source", "DELETE", f"/api/sources/{r.json()['id']}")

out.append("### Recording and reading consumption\n")
for n in range(1, 8):                                  # a week of normal history (not shown)
    for src, liters in (("Garden", 40), ("Showers & baths", 100), ("Toilets", 60)):
        client.post(f"/api/households/{hid}/usage", json={"usage_date": day(n), "liters": liters, "source": src}, headers={"Authorization": f"Bearer {state['token']}"})
r = ex("Record daily water consumption", "POST", f"/api/households/{hid}/usage", {"usage_date": day(), "liters": 96, "source": "Garden", "notes": "sprinklers ran twice"},
       note="The response also lists any alerts this entry triggered: here the garden used 2.4x its usual amount.")
eid = r.json()["entry"]["id"]
ex("List usage entries", "GET", f"/api/households/{hid}/usage?limit=2&source_id={r.json()['entry']['source_id']}")
ex("Get one entry", "GET", f"/api/usage/{eid}")
ex("Edit an entry", "PUT", f"/api/usage/{eid}", {"liters": 90})
ex("Daily total, weekly total and averages", "GET", f"/api/households/{hid}/usage/summary", trim=False)
ex("Daily series (zero-filled)", "GET", f"/api/households/{hid}/usage/daily?start={day(2)}&end={day()}")
ex("Where the water goes", "GET", f"/api/households/{hid}/usage/by-source?period=week")
ex("Consumption history", "GET", f"/api/households/{hid}/history?days=7")
ex("Delete an entry", "DELETE", f"/api/usage/{eid}")
ex("Record it again for the alert examples", "POST", f"/api/households/{hid}/usage", {"usage_date": day(), "liters": 96, "source": "Garden"})

out.append("### Alerts\n")
r = ex("List open alerts", "GET", f"/api/households/{hid}/alerts?status=open")
aid = r.json()["items"][0]["id"]
ex("Scan a day for unusually high consumption", "POST", f"/api/households/{hid}/alerts/scan")
ex("Report running water (leak check)", "POST", f"/api/households/{hid}/flow-events", {"flow_lpm": 1.8, "minutes": 25})
ex("Dismiss (or acknowledge / reopen) an alert", "PUT", f"/api/alerts/{aid}", {"status": "dismissed"})
ex("Mark everything read", "POST", f"/api/households/{hid}/alerts/mark-read")
ex("Delete an alert", "DELETE", f"/api/alerts/{aid}")

out.append("### Reminder schedules\n")
r = ex("Schedule a reminder", "POST", f"/api/households/{hid}/schedules", {"title": "Evening usage check-in", "reminder_type": "Usage Check-in", "days": "daily", "time_of_day": "20:00", "channel": "Push notification"})
sid = r.json()["id"]
ex("Weekly schedule on chosen days", "POST", f"/api/households/{hid}/schedules", {"title": "Check garden watering", "reminder_type": "Garden Watering", "days": ["mon", "wed", "fri"], "time_of_day": "06:30"})
ex("List schedules", "GET", f"/api/households/{hid}/schedules")
ex("Switch a schedule off", "PUT", f"/api/schedules/{sid}", {"enabled": False})
ex("Upcoming reminders", "GET", f"/api/households/{hid}/schedules/upcoming")
ex("Fire due reminders now", "POST", f"/api/households/{hid}/schedules/check-due")
ex("Allowed types and channels", "GET", "/api/reminder-options")
ex("Delete a schedule", "DELETE", f"/api/schedules/{sid}")

out.append("### Dashboard\n")
ex("Dashboard statistics (everything the screen shows)", "GET", f"/api/households/{hid}/dashboard?period=week", trim=True,
   note="Lists are shortened here; the real response contains every bar, alert and reminder.")
ex("Export CSV", "GET", f"/api/households/{hid}/export.csv?start={day(1)}&end={day()}")

out.append("### Meter readings (shared with the desktop app)\n")
ex("Add a reading", "POST", f"/api/households/{hid}/meter-readings", {"reading_date": day(3), "meter_reading": 120.5})
r = ex("Add the next reading", "POST", f"/api/households/{hid}/meter-readings", {"reading_date": day(), "meter_reading": 121.1})
ex("List readings with usage", "GET", f"/api/households/{hid}/meter-readings")
ex("A meter can never run backwards", "POST", f"/api/households/{hid}/meter-readings", {"reading_date": day(1), "meter_reading": 100})

out.append("### Error responses\n")
ex("Validation error (422)", "POST", f"/api/households/{hid}/usage", {"usage_date": day(), "liters": -5, "source": "Garden"})
ex("Several problems at once (422)", "POST", "/api/auth/register", {"name": "A", "email": "nope", "password": "123"}, auth=False)
ex("Future date (422)", "POST", f"/api/households/{hid}/usage", {"usage_date": (date.today() + timedelta(days=3)).isoformat(), "liters": 5, "source": "Garden"})
ex("Not signed in (401)", "GET", "/api/households", auth=False)
ex("Not found (404)", "GET", "/api/usage/99999")
ex("Conflict (409)", "POST", "/api/households", {"name": "Maple House", "city": "X", "members": 2})
ex("Source in use (409)", "DELETE", "/api/sources/2")

# --------------------------------------------------------------------------- reference table
rows = []
for path, ops in sorted(app.openapi()["paths"].items()):
    for method, spec in ops.items():
        auth = "—" if path in ("/api/health", "/api/auth/register", "/api/auth/login") else "Bearer token"
        rows.append(f"| `{method.upper()}` | `{path}` | {spec.get('summary', '')} | {auth} |")

head = f"""# HydroHome REST API

Base URL: `http://127.0.0.1:8000` · Interactive docs (try every endpoint in the browser): `http://127.0.0.1:8000/docs`

This file is generated from real requests by `scripts/generate_api_docs.py`, so the examples are exactly what the API returns.

## Basics

* **Format:** JSON in, JSON out. Dates are `YYYY-MM-DD`, times `HH:MM` (24-hour), volumes are litres.
* **Authentication:** register or sign in, then send `Authorization: Bearer <token>` with every request
  (except `/api/health`, `/api/auth/register`, `/api/auth/login`). Tokens last 7 days.
* **Privacy:** you only ever see households you belong to. Anything else answers `404`.
* **Errors:** every failure uses one shape: `{{"error": {{"code": "...", "message": "...", "details": [...]}}}}`.

| Status | `code` | Meaning |
|---|---|---|
| 200 / 201 / 204 | | Success / created / success with no body |
| 401 | `unauthorized` | Missing, wrong or expired token |
| 404 | `not_found` | Record does not exist (or is not yours) |
| 409 | `conflict` | Duplicate name, or a source that still has usage |
| 422 | `validation_error` | Bad input. `message` is the first problem, `details` lists all of them |

## How high consumption is detected

Thresholds come from each household's limits (`PUT /api/households/{{id}}/limits`).

| Alert `kind` | Raised when | Severity |
|---|---|---|
| `limit_exceeded` | today's total is over the daily limit | critical |
| `near_limit` | today's total reached `alert_threshold_pct` of the daily limit (default 90%) | warning |
| `high_source` | one source used at least `spike_multiplier` (default 1.5x) its average of the previous 14 days (needs 3+ days of history and 20+ L extra) | warning |
| `high_total` | the whole household used at least `spike_multiplier` x its usual daily total | warning |
| `continuous_flow` | `POST .../flow-events` reports 20+ minutes of flow at 0.2+ L/min | warning |
| `reminder` | a reminder schedule fired | info |

Detection runs automatically whenever you record, edit or delete usage, and when the dashboard loads.
Alerts that stop being true (for example after you delete a typo) are resolved automatically,
and an alert you dismissed is not re-opened for the same day.

## Endpoint reference

| Method | Path | What it does | Auth |
|---|---|---|---|
{chr(10).join(rows)}

## Examples

In the examples `$TOKEN` is the `token` returned by register/login.

"""
(ROOT / "docs").mkdir(exist_ok=True)
(ROOT / "docs" / "API.md").write_text(head + "\n".join(out), encoding="utf-8")
print("Wrote docs/API.md with", len(out), "example blocks")
