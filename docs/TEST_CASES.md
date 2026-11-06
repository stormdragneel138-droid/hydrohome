# Test Cases

**A. Automated (pytest)** — run `python -m pytest -q`. Last run: **77 passed, 1 skipped**
(the skipped permission test needs a non-root user; run it on your own machine).

| ID | Test case | Input / action | Expected result | Actual | Status |
|---|---|---|---|---|---|
| TC-01 | Create household | Valid form | Row saved, retrievable | As expected | Pass |
| TC-02 | Update household | Change name | New name stored | As expected | Pass |
| TC-03 | Delete household | Delete with readings | Household and readings removed | As expected | Pass |
| TC-04 | Search | "Manila" | Only matching household | As expected | Pass |
| TC-05 | Persistence | Close and reopen DB | Data still present | As expected | Pass |
| TC-06 | Duplicate name | Add "Cruz" twice | DatabaseError with friendly message | As expected | Pass |
| TC-07 | SQL injection text | Name `x'); DROP TABLE…` | Stored literally, table intact | As expected | Pass |
| TC-08 | DB errors | Blocked folder; corrupted .db file | DatabaseError, no crash | As expected | Pass |
| TC-09 | Empty required fields | Blank name and city | 2 validation errors | As expected | Pass |
| TC-10 | Bad numbers | members = 0, -1, abc, 31, 2.5 | ValidationError | As expected | Pass |
| TC-11 | Bad reading values | Negative, text, wrong date format, future date | ValidationError | As expected | Pass |
| TC-12 | Valid reading normalised | " 12.34567 " | Stored as 12.346 | As expected | Pass |
| TC-13 | Reminder validation | Empty title, time 25:99, bad type/repeat | ValidationError | As expected | Pass |
| TC-16 | Usage maths | 100 → 104 m³ in 10 days, 4 people | 100 L/person/day, "Near limit" | As expected | Pass |
| TC-17 | Meter runs backwards | 100 then 90 | Rejected | As expected | Pass |
| TC-18 | Insert between readings | Lower/higher than neighbours | Rejected / accepted correctly | As expected | Pass |
| TC-19 | Duplicate date | Same date twice | Rejected | As expected | Pass |
| TC-20 | Unknown household | household_id 77 | Rejected | As expected | Pass |
| TC-21 | Status thresholds | 80 / 95 / 101 vs target 100 | Within / Near / Over | As expected | Pass |
| TC-22 | Due alert once | Past-due reminder, check twice | 1 alert, then none | As expected | Pass |
| TC-23 | Future reminder | Due next month | No alert | As expected | Pass |
| TC-24 | Complete one-off | Mark done | Status Done | As expected | Pass |
| TC-25 | Complete repeating | Weekly reminder | Rolls forward a week, alerts again | As expected | Pass |
| TC-26 | Monthly edge | Jan 31 + 1 month | Feb 28 | As expected | Pass |
| TC-27 | Reminder CRUD | Add / update / delete | Works | As expected | Pass |
| TC-28 | API success: geocode | "Tarlac City" (fallback "Tarlac") | lat/lon + label; timeout sent | As expected | Pass |
| TC-29 | API: unknown city | "Zzzz" | WeatherError "No location" | As expected | Pass |
| TC-30 | API: null JSON values | rain = null | Treated as 0 | As expected | Pass |
| TC-31 | API timeout | Timeout raised | Friendly WeatherError | As expected | Pass |
| TC-32 | API offline | ConnectionError | Friendly WeatherError | As expected | Pass |
| TC-33 | API HTTP 500 / bad JSON / error payload / wrong shape / missing fields | Simulated | WeatherError each time | As expected | Pass |
| TC-34 | Coordinate caching | Fetch twice | Geocoded once | As expected | Pass |
| TC-35 | Advice rules | Rain 9.5 mm, 34 °C | Skip-watering + hot-day suggestions | As expected | Pass |
| TC-36 | CSV export | Export 2 readings | Header + 2 rows | As expected | Pass |
| TC-37 | CSV import mixed | 4 rows, 2 bad | 2 added, 2 reported with line numbers | As expected | Pass |
| TC-38 | Import missing file | Wrong path | FileServiceError "not found" | As expected | Pass |
| TC-39 | Import wrong columns / empty | Bad header; no rows | FileServiceError | As expected | Pass |
| TC-40 | Import binary file | Random bytes | FileServiceError | As expected | Pass |
| TC-41 | Export permission denied | Read-only folder | FileServiceError | *(skipped as root)* | Run locally |
| TC-42 | Usage report | Save TXT report | Contains name, status, reminders | As expected | Pass |
| TC-43 | Meter source CRUD | Save, save again (update), delete | One row per household; updated; removed | As expected | Pass |
| TC-44 | Meter source validation | Empty URL, `ftp://`, empty path, bad unit, interval 0, bad type | ValidationError | As expected | Pass |
| TC-45 | Sync creates reading | JSON `data.total_m3 = 123.4` with API key | Reading saved; key sent in headers; timeout set | As expected | Pass |
| TC-46 | Repeat sync same day | Two syncs, values 100 then 101.5 | One reading, updated to 101.5 | As expected | Pass |
| TC-47 | Unit conversion + nested path | 98765 litres at `readings.0.v` | Stored as 98.765 m³ | As expected | Pass |
| TC-48 | Bad meter values | `abc`, null, negative, NaN, missing path | MeterSyncError | As expected | Pass |
| TC-49 | Meter failures | Timeout, offline, HTTP 401/500, non-JSON, missing field, non-number | Friendly error; recorded as Failed; no reading saved | As expected | Pass |
| TC-50 | Meter value goes backwards | Sync 50 after reading 100 | Rejected with reason | As expected | Pass |
| TC-51 | File source | Valid JSON; invalid JSON; deleted file | Reading saved; clear errors | As expected | Pass |
| TC-52 | No source configured | Sync a household with none | MeterSyncError | As expected | Pass |
| TC-53 | Scheduler | Interval, disabled source, failing meter | Only due+enabled run; failure isolated | As expected | Pass |
| TC-54 | End-to-end over real HTTP | Simulated meter: wrong key, right key, server stopped | 401 message; reading 150.0 saved; "Cannot reach" | As expected | Pass |
| TC-55 | Forecast cache TTL | Fetch, then 29 min / 30 min later | Cached until 30 min, then re-fetch | As expected | Pass |
| TC-56 | API failure back-off | Failed fetch | No retry for 2 min; old forecast kept | As expected | Pass |
| TC-57 | Failure with no data | First fetch fails | Back-off, then retry | As expected | Pass |
| TC-58 | City changed | Household city edited | Forecast re-fetched for new city | As expected | Pass |

**B. Manual GUI tests** — perform and fill in before your defense.

| ID | Test case | Action | Expected result | Actual | Status |
|---|---|---|---|---|---|
| M-01 | Add household in GUI | Fill form, click Add | Success message; row appears | | |
| M-02 | Empty form | Click Add on blank form | Warning lists every missing field | | |
| M-03 | Update / delete | Select row, change, Update; then Delete | Confirmation + table refreshes | | |
| M-04 | Add reading, then a lower one | Add 100, then 90 | Second rejected with explanation | | |
| M-05 | Dashboard chart | Add 3+ readings | Bars coloured by status, target line drawn | | |
| M-06 | Live forecast | Click "Get forecast" (internet on) | Temp, 3-day table, advice list | | |
| M-07 | Forecast offline | Disconnect Wi-Fi, click it | Error dialog; app stays responsive | | |
| M-08 | Advice → reminder | Select advice, click create | Reminder form prefilled | | |
| M-09 | Reminder popup | Add reminder due in 1–2 min; wait ≤ 30 s after due | Popup appears once | | |
| M-10 | Mark done (Weekly) | Select, Mark done | Due date moves forward 7 days | | |
| M-11 | Export / import CSV | Export, edit, import | Summary dialog with counts | | |
| M-12 | Restart app | Close and reopen | All records still there | | |
| M-13 | Smart meter manual sync | Run `python -m scripts.mock_smart_meter --start 200`; Smart Meter screen: URL `http://localhost:8765/meter`, path `data.total_m3`, Sync now | Success dialog; new reading in Meter Readings | | |
| M-14 | Automatic sync | Set interval 1 min, wait ~2 min | Status bar "Smart meter auto-sync: 1 updated"; reading value rises | | |
| M-15 | Meter offline | Stop the simulator, Sync now | Error dialog; row turns red; app stays responsive | | |
| M-16 | Wrong API key | Run simulator with `--key abc`, leave key empty | "check the API key" message | | |
| M-17 | Dashboard auto-update | Open Dashboard; add a reading or reminder in another screen / let a smart-meter sync run | Figures, chart and reminders change within ~10 s without clicking Refresh; forecast appears without clicking | | |
