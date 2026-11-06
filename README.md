# 💧 HydroHome – Household Water Consumption Reminder System

A Python Tkinter desktop information system for *Integrative Programming and Technologies*.
Households record their water-meter readings, the system computes litres per person per day
against a target, and **reminds** them (meter reading, bill payment, leak checks, garden
watering). A live weather forecast (Open-Meteo REST API) produces smart suggestions such as
*"Rain expected – skip garden watering"*.

## Problem statement
Many households only notice high water use when the monthly bill arrives. They forget to read
the meter, pay on time, or check for leaks, and they water gardens when rain is coming.
HydroHome tracks consumption, flags over-use early, and sends timed reminders.

## Features
| Screen | What it does |
|---|---|
| **Dashboard** (auto-updating) | Refreshes itself every 10 s; forecast loads automatically and re-fetches every 30 min (cached, retries after a failure). Shows latest usage, average L/person/day, status (Within / Near / Over target), bar chart vs. target, tips, upcoming reminders, weather forecast + advice |
| **Households** | Create / read / update / delete households, search |
| **Meter Readings** | CRUD, filter + search, usage computed per reading, **CSV export**, **CSV import**, **usage report (TXT)** |
| **Smart Meter** | Auto-sync: connect a smart meter (JSON endpoint or JSON file), choose the field holding the meter value, set an interval. Readings then arrive automatically; **Sync now** tests the connection |
| **Reminders** | CRUD, status filter + search, mark done (Daily/Weekly/Monthly repeats roll forward), overdue highlighting, **CSV export** |
| **Reminder engine** | Checks every 30 s and pops up reminders that have just become due (once each) |

## Setup & run
```bash
python -m venv .venv
.venv\Scripts\activate          # Windows      (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
python main.py
```
Optional demo data: `python -m scripts.seed_demo`   ·   Run tests: `python -m pytest -q`

Linux only: Tkinter may need `sudo apt install python3-tk`.

## REST API: Open-Meteo (no API key)
* Geocoding: `https://geocoding-api.open-meteo.com/v1/search` (city → latitude/longitude, cached in the DB)
* Forecast: `https://api.open-meteo.com/v1/forecast` (current temp/humidity + 3-day max/min temp, rain mm, rain probability)
* **Why it matters here:** water need depends on weather. Rain ≥ 5 mm or ≥ 70 % → suggest skipping garden watering
  and collecting rainwater; max temp ≥ 33 °C → suggest early watering + leak check. The user can turn any
  suggestion into a real reminder with one click. Thresholds are in `hydrohome/config.py`.
* Handles timeouts, connection failures, HTTP errors, non-JSON, API error payloads, and missing fields.
* The call runs in a background thread so the window never freezes.
* Free tier is for non-commercial use with generous rate limits; acknowledge Open-Meteo.com in your report.

## Smart meter auto-sync (automatic consumption data)
HydroHome cannot read a physical meter by itself, and there is no universal smart-meter API: each
utility or brand differs. So the app pulls from any meter that exposes **JSON**:

| Source | Example location | When to use |
|---|---|---|
| `URL` | `http://192.168.1.50/api/meter` or your utility's endpoint | meter/gateway/utility with an HTTP API (optional API key sent as `Authorization: Bearer` and `X-API-Key`) |
| `FILE` | `C:\meter\latest.json` | meter software that writes a JSON file |

1. **Smart Meter** screen → choose household, type, location, and the **JSON path** to the cumulative
   value (e.g. `data.total_m3`, or `readings.0.value`). Pick the unit (m3 or liters).
2. Click **Sync now** to test. After that the app syncs by itself in the background every N minutes
   (checked each minute, window never freezes). Several syncs in one day update that day's reading.
3. Failures (offline, wrong key, bad JSON, meter value lower than before) are shown and recorded; one failing meter never blocks others.

**Demo without hardware:** `python -m scripts.mock_smart_meter --start 200` runs a *simulated* meter at
`http://localhost:8765/meter` (path `data.total_m3`). `--start` must be at least the household's latest reading.
It is simulated data, so say so in your defense. For a real meter, ask your provider for its API/export format.

## Project structure
```
main.py                     entry point
hydrohome/
  config.py  errors.py  container.py
  database/   connection.py (schema)  repositories.py (ALL SQL, parameterized)
  services/   validators  consumption  household_service  reading_service
              reminder_service  advisor  weather_api  weather_service
              file_service  report_service  meter_sync_service
  ui/         app  widgets  dashboard_view  households_view  readings_view  meter_view  reminders_view
tests/        automated pytest suite      docs/  architecture, database, test cases
scripts/      seed_demo.py  mock_smart_meter.py
```
See `docs/ARCHITECTURE.md`, `docs/DATABASE.md`, `docs/TEST_CASES.md`.

## Web dashboard + REST API (new)
The same households, readings and rules are now also available as a REST API with a web dashboard
(based on the Figma design). The desktop app keeps working and shares the same database.

```
python run_api.py                    # then open http://127.0.0.1:8000
python scripts/seed_demo_data.py     # optional: a SEPARATE demo database with sample data
python run_api.py --db data/demo.db  # run the dashboard on the demo data
```
* Interactive API docs: http://127.0.0.1:8000/docs  ·  written reference with samples: `docs/API.md`
* Step-by-step beginner guide: `docs/WEB_SETUP.md`
* Code: `hydrohome/api/` (routers) · `hydrohome/services/{auth,usage,alert,schedule,settings,dashboard}_service.py`
  · `hydrohome/database/web_*.py` · `hydrohome/web/` (HTML/CSS/JS)

## Automatic updates
* **Dashboard** re-reads the database every 10 seconds (usage, status, chart, reminders) and shows "last updated".
* **Weather** loads when a household is selected and refreshes every 30 minutes. A cache prevents calling the API on
  every refresh; after a failure it retries after 2 minutes and keeps showing the last good forecast.
* **Smart meter** readings sync in the background on their own interval, then the dashboard picks them up.
* **Reminders** pop up when due. Intervals are in `hydrohome/config.py`.

## Known limitations
* Reminders alert only while the app is open (no background OS service).
* The desktop app is single-user with no login; the web dashboard has accounts (email + password).
* Weather needs internet; everything else works offline.
* Smart-meter sync needs a meter/utility that provides JSON; the API key is stored unencrypted in the local database.
* The default 100 L/person/day target is a configurable assumption, not an official standard.

## Acknowledgements
Open-Meteo.com (weather data, CC BY 4.0) · Python `requests` · `pytest`.
