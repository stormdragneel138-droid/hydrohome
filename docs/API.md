# HydroHome REST API

Base URL: `http://127.0.0.1:8000` · Interactive docs (try every endpoint in the browser): `http://127.0.0.1:8000/docs`

This file is generated from real requests by `scripts/generate_api_docs.py`, so the examples are exactly what the API returns.

## Basics

* **Format:** JSON in, JSON out. Dates are `YYYY-MM-DD`, times `HH:MM` (24-hour), volumes are litres.
* **Authentication:** register or sign in, then send `Authorization: Bearer <token>` with every request
  (except `/api/health`, `/api/auth/register`, `/api/auth/login`). Tokens last 7 days.
* **Privacy:** you only ever see households you belong to. Anything else answers `404`.
* **Errors:** every failure uses one shape: `{"error": {"code": "...", "message": "...", "details": [...]}}`.

| Status | `code` | Meaning |
|---|---|---|
| 200 / 201 / 204 | | Success / created / success with no body |
| 401 | `unauthorized` | Missing, wrong or expired token |
| 404 | `not_found` | Record does not exist (or is not yours) |
| 409 | `conflict` | Duplicate name, or a source that still has usage |
| 422 | `validation_error` | Bad input. `message` is the first problem, `details` lists all of them |

## How high consumption is detected

Thresholds come from each household's limits (`PUT /api/households/{id}/limits`).

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
| `GET` | `/api/alerts/{alert_id}` | One alert | Bearer token |
| `PUT` | `/api/alerts/{alert_id}` | Acknowledge, dismiss, resolve or reopen an alert | Bearer token |
| `DELETE` | `/api/alerts/{alert_id}` | Delete an alert | Bearer token |
| `POST` | `/api/auth/login` | Sign in and get a bearer token | — |
| `POST` | `/api/auth/logout` | Invalidate the current token | Bearer token |
| `GET` | `/api/auth/me` | The signed-in user | Bearer token |
| `PUT` | `/api/auth/me` | Update your display name | Bearer token |
| `PUT` | `/api/auth/password` | Change your password | Bearer token |
| `POST` | `/api/auth/register` | Create an account | — |
| `GET` | `/api/health` | Is the API running? | — |
| `GET` | `/api/households` | Households you belong to | Bearer token |
| `POST` | `/api/households` | Create a household | Bearer token |
| `GET` | `/api/households/unclaimed` | Households (e.g. made in the desktop app) with no owner | Bearer token |
| `GET` | `/api/households/{household_id}` | One household with its limits | Bearer token |
| `PUT` | `/api/households/{household_id}` | Update household details | Bearer token |
| `DELETE` | `/api/households/{household_id}` | Delete a household and all its data | Bearer token |
| `GET` | `/api/households/{household_id}/alerts` | List alerts and notifications (open ones first by severity) | Bearer token |
| `POST` | `/api/households/{household_id}/alerts/mark-read` | Mark all as read | Bearer token |
| `POST` | `/api/households/{household_id}/alerts/scan` | Check a day's usage for unusually high consumption | Bearer token |
| `POST` | `/api/households/{household_id}/claim` | Become the admin of an unowned household | Bearer token |
| `GET` | `/api/households/{household_id}/dashboard` | Everything the dashboard shows, in one response | Bearer token |
| `GET` | `/api/households/{household_id}/export.csv` | Download usage entries as CSV | Bearer token |
| `POST` | `/api/households/{household_id}/flow-events` | Report continuous water flow (smart-meter style leak check) | Bearer token |
| `GET` | `/api/households/{household_id}/history` | Consumption history: daily totals with per-source breakdown | Bearer token |
| `GET` | `/api/households/{household_id}/limits` | Consumption limits | Bearer token |
| `PUT` | `/api/households/{household_id}/limits` | Update daily/weekly limits, alert threshold and water rate | Bearer token |
| `GET` | `/api/households/{household_id}/meter-readings` | Meter readings with usage since the previous reading | Bearer token |
| `POST` | `/api/households/{household_id}/meter-readings` | Add a meter reading (the meter can never run backwards) | Bearer token |
| `GET` | `/api/households/{household_id}/notification-settings` | Push/email preferences and quiet hours | Bearer token |
| `PUT` | `/api/households/{household_id}/notification-settings` | Update push/email preferences and quiet hours | Bearer token |
| `GET` | `/api/households/{household_id}/schedules` | Reminder schedules | Bearer token |
| `POST` | `/api/households/{household_id}/schedules` | Schedule a water-saving reminder | Bearer token |
| `POST` | `/api/households/{household_id}/schedules/check-due` | Fire any reminders that are due right now | Bearer token |
| `GET` | `/api/households/{household_id}/schedules/upcoming` | Next reminders to fire | Bearer token |
| `GET` | `/api/households/{household_id}/sources` | Water sources / sensors (showers, garden, ...) | Bearer token |
| `POST` | `/api/households/{household_id}/sources` | Add a water source | Bearer token |
| `POST` | `/api/households/{household_id}/usage` | Record water consumption for a day and source | Bearer token |
| `GET` | `/api/households/{household_id}/usage` | List usage entries (newest first) | Bearer token |
| `GET` | `/api/households/{household_id}/usage/by-source` | Where the water goes: totals per source | Bearer token |
| `GET` | `/api/households/{household_id}/usage/daily` | Zero-filled daily totals for a date range (default: last 7 days) | Bearer token |
| `GET` | `/api/households/{household_id}/usage/summary` | Daily total, week-to-date total and average usage | Bearer token |
| `PUT` | `/api/meter-readings/{reading_id}` | Edit a meter reading | Bearer token |
| `DELETE` | `/api/meter-readings/{reading_id}` | Delete a meter reading | Bearer token |
| `GET` | `/api/reminder-options` | Allowed reminder types and delivery channels | Bearer token |
| `GET` | `/api/schedules/{schedule_id}` | One reminder schedule | Bearer token |
| `PUT` | `/api/schedules/{schedule_id}` | Edit a schedule or switch it on/off | Bearer token |
| `DELETE` | `/api/schedules/{schedule_id}` | Delete a schedule | Bearer token |
| `PUT` | `/api/sources/{source_id}` | Rename, recolor, enable or disable | Bearer token |
| `DELETE` | `/api/sources/{source_id}` | Delete a source that has no usage entries | Bearer token |
| `GET` | `/api/usage/{usage_id}` | One usage entry | Bearer token |
| `PUT` | `/api/usage/{usage_id}` | Edit a usage entry | Bearer token |
| `DELETE` | `/api/usage/{usage_id}` | Delete a usage entry | Bearer token |

## Examples

In the examples `$TOKEN` is the `token` returned by register/login.

### Accounts

#### Register

```bash
curl -X POST http://127.0.0.1:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"name": "Jamie Lewis", "email": "jamie@example.com", "password": "correct-horse"}'
```
**Response `201`**
```json
{
  "user": {
    "id": 1,
    "name": "Jamie Lewis",
    "email": "jamie@example.com",
    "created_at": "2026-11-06 10:38:08"
  },
  "token": "jaAaMY_DisgIGdj1zaIY4XtVg1W2RaipDE1yExr4PAE",
  "token_type": "bearer"
}
```

#### Sign in

```bash
curl -X POST http://127.0.0.1:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "jamie@example.com", "password": "correct-horse"}'
```
**Response `200`**
```json
{
  "user": {
    "id": 1,
    "name": "Jamie Lewis",
    "email": "jamie@example.com",
    "created_at": "2026-11-06 10:38:08"
  },
  "token": "B2YHivhaAR1Gl7YRV3-1GlAs_Z9-A7MuUKX6pq9-cYc",
  "token_type": "bearer"
}
```

#### Who am I

```bash
curl -X GET http://127.0.0.1:8000/api/auth/me \
  -H "Authorization: Bearer $TOKEN"
```
**Response `200`**
```json
{
  "id": 1,
  "name": "Jamie Lewis",
  "email": "jamie@example.com",
  "created_at": "2026-11-06 10:38:08"
}
```

### Households

#### Create a household

```bash
curl -X POST http://127.0.0.1:8000/api/households \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "Maple House", "city": "Tarlac City", "address": "12 Maple Street", "members": 4, "daily_limit_liters": 500}'
```
**Response `201`**
```json
{
  "id": 1,
  "name": "Maple House",
  "address": "12 Maple Street",
  "city": "Tarlac City",
  "members": 4,
  "daily_target_liters": 125,
  "created_at": "2026-11-06 10:38:08",
  "role": "admin"
}
```

#### List my households

```bash
curl -X GET http://127.0.0.1:8000/api/households \
  -H "Authorization: Bearer $TOKEN"
```
**Response `200`**
```json
[
  {
    "id": 1,
    "name": "Maple House",
    "address": "12 Maple Street",
    "city": "Tarlac City",
    "members": 4,
    "daily_target_liters": 125,
    "created_at": "2026-11-06 10:38:08",
    "role": "admin"
  }
]
```

#### Update household details

```bash
curl -X PUT http://127.0.0.1:8000/api/households/1 \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"members": 5}'
```
**Response `200`**
```json
{
  "id": 1,
  "name": "Maple House",
  "address": "12 Maple Street",
  "city": "Tarlac City",
  "members": 5,
  "daily_target_liters": 125,
  "created_at": "2026-11-06 10:38:08",
  "role": "admin"
}
```

#### Get one household (includes limits)

```bash
curl -X GET http://127.0.0.1:8000/api/households/1 \
  -H "Authorization: Bearer $TOKEN"
```
**Response `200`**
```json
{
  "id": 1,
  "name": "Maple House",
  "address": "12 Maple Street",
  "city": "Tarlac City",
  "members": 5,
  "daily_target_liters": 125,
  "created_at": "2026-11-06 10:38:08",
  "role": "admin",
  "limits": {
    "household_id": 1,
    "daily_limit_liters": 500.0,
    "weekly_limit_liters": 3500.0,
    "alert_threshold_pct": 90,
    "spike_multiplier": 1.5,
    "rate_per_1000_l": 3.0,
    "currency": "$",
    "updated_at": "2026-11-06 10:38:08"
  }
}
```

### Consumption limits and notification preferences

#### Read limits

```bash
curl -X GET http://127.0.0.1:8000/api/households/1/limits \
  -H "Authorization: Bearer $TOKEN"
```
**Response `200`**
```json
{
  "household_id": 1,
  "daily_limit_liters": 500.0,
  "weekly_limit_liters": 3500.0,
  "alert_threshold_pct": 90,
  "spike_multiplier": 1.5,
  "rate_per_1000_l": 3.0,
  "currency": "$",
  "updated_at": "2026-11-06 10:38:08"
}
```

#### Update household water usage limits

```bash
curl -X PUT http://127.0.0.1:8000/api/households/1/limits \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"daily_limit_liters": 500, "weekly_limit_liters": 3500, "alert_threshold_pct": 90, "spike_multiplier": 1.5, "rate_per_1000_l": 3.0}'
```
**Response `200`**
```json
{
  "household_id": 1,
  "daily_limit_liters": 500.0,
  "weekly_limit_liters": 3500.0,
  "alert_threshold_pct": 90,
  "spike_multiplier": 1.5,
  "rate_per_1000_l": 3.0,
  "currency": "$",
  "updated_at": "2026-11-06 10:38:08"
}
```

#### Notification preferences

```bash
curl -X PUT http://127.0.0.1:8000/api/households/1/notification-settings \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"quiet_start": "22:00", "quiet_end": "06:00", "email_enabled": true}'
```
**Response `200`**
```json
{
  "household_id": 1,
  "push_enabled": true,
  "email_enabled": true,
  "quiet_start": "22:00",
  "quiet_end": "06:00"
}
```

### Water sources

#### List sources

```bash
curl -X GET http://127.0.0.1:8000/api/households/1/sources \
  -H "Authorization: Bearer $TOKEN"
```
**Response `200`**
```json
[
  {
    "id": 1,
    "household_id": 1,
    "name": "Showers & baths",
    "color": "#267e78",
    "enabled": true,
    "today_liters": 0.0
  },
  {
    "id": 2,
    "household_id": 1,
    "name": "Garden",
    "color": "#68a397",
    "enabled": true,
    "today_liters": 0.0
  },
  "... 3 more"
]
```

#### Add a source

```bash
curl -X POST http://127.0.0.1:8000/api/households/1/sources \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "Pool", "color": "#4a90a4"}'
```
**Response `201`**
```json
{
  "id": 6,
  "household_id": 1,
  "name": "Pool",
  "color": "#4a90a4",
  "enabled": true
}
```

#### Disable a source

```bash
curl -X PUT http://127.0.0.1:8000/api/sources/6 \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"enabled": false}'
```
**Response `200`**
```json
{
  "id": 6,
  "household_id": 1,
  "name": "Pool",
  "color": "#4a90a4",
  "enabled": false
}
```

#### Delete a source

```bash
curl -X DELETE http://127.0.0.1:8000/api/sources/6 \
  -H "Authorization: Bearer $TOKEN"
```
**Response `204`**
```json
(empty body)
```

### Recording and reading consumption

#### Record daily water consumption
The response also lists any alerts this entry triggered: here the garden used 2.4x its usual amount.
```bash
curl -X POST http://127.0.0.1:8000/api/households/1/usage \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"usage_date": "2026-11-06", "liters": 96, "source": "Garden", "notes": "sprinklers ran twice"}'
```
**Response `201`**
```json
{
  "entry": {
    "id": 22,
    "household_id": 1,
    "source_id": 2,
    "source_name": "Garden",
    "source_color": "#68a397",
    "usage_date": "2026-11-06",
    "liters": 96.0,
    "notes": "sprinklers ran twice",
    "created_at": "2026-11-06 10:38:08"
  },
  "alerts_triggered": [
    {
      "id": 1,
      "household_id": 1,
      "kind": "high_source",
      "severity": "warning",
      "title": "Unusually high garden use",
      "message": "The garden used 96 L today — 2.4× its usual amount. Check for a running hose.",
      "source_id": 2,
      "source_name": "Garden",
      "usage_date": "2026-11-06",
      "liters": 96.0,
      "status": "open",
      "is_read": false,
      "detected_at": "2026-11-06 10:38:08",
      "resolved_at": null
    }
  ]
}
```

#### List usage entries

```bash
curl -X GET http://127.0.0.1:8000/api/households/1/usage?limit=2&source_id=2 \
  -H "Authorization: Bearer $TOKEN"
```
**Response `200`**
```json
{
  "total": 8,
  "limit": 2,
  "offset": 0,
  "items": [
    {
      "id": 22,
      "household_id": 1,
      "source_id": 2,
      "source_name": "Garden",
      "source_color": "#68a397",
      "usage_date": "2026-11-06",
      "liters": 96.0,
      "notes": "sprinklers ran twice",
      "created_at": "2026-11-06 10:38:08"
    },
    {
      "id": 1,
      "household_id": 1,
      "source_id": 2,
      "source_name": "Garden",
      "source_color": "#68a397",
      "usage_date": "2026-11-05",
      "liters": 40.0,
      "notes": "",
      "created_at": "2026-11-06 10:38:08"
    }
  ]
}
```

#### Get one entry

```bash
curl -X GET http://127.0.0.1:8000/api/usage/22 \
  -H "Authorization: Bearer $TOKEN"
```
**Response `200`**
```json
{
  "id": 22,
  "household_id": 1,
  "source_id": 2,
  "source_name": "Garden",
  "source_color": "#68a397",
  "usage_date": "2026-11-06",
  "liters": 96.0,
  "notes": "sprinklers ran twice",
  "created_at": "2026-11-06 10:38:08"
}
```

#### Edit an entry

```bash
curl -X PUT http://127.0.0.1:8000/api/usage/22 \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"liters": 90}'
```
**Response `200`**
```json
{
  "entry": {
    "id": 22,
    "household_id": 1,
    "source_id": 2,
    "source_name": "Garden",
    "source_color": "#68a397",
    "usage_date": "2026-11-06",
    "liters": 90.0,
    "notes": "sprinklers ran twice",
    "created_at": "2026-11-06 10:38:08"
  },
  "alerts_triggered": [
    {
      "id": 1,
      "household_id": 1,
      "kind": "high_source",
      "severity": "warning",
      "title": "Unusually high garden use",
      "message": "The garden used 90 L today — 2.2× its usual amount. Check for a running hose.",
      "source_id": 2,
      "source_name": "Garden",
      "usage_date": "2026-11-06",
      "liters": 90.0,
      "status": "open",
      "is_read": false,
      "detected_at": "2026-11-06 10:38:08",
      "resolved_at": null
    }
  ]
}
```

#### Daily total, weekly total and averages

```bash
curl -X GET http://127.0.0.1:8000/api/households/1/usage/summary \
  -H "Authorization: Bearer $TOKEN"
```
**Response `200`**
```json
{
  "date": "2026-11-06",
  "today": {
    "liters": 90.0,
    "limit": 500.0,
    "percent": 18,
    "remaining": 410.0,
    "status": "On track"
  },
  "yesterday": {
    "liters": 200.0,
    "difference": -110.0,
    "change_percent": -55.0
  },
  "week": {
    "start": "2026-11-02",
    "end": "2026-11-06",
    "liters": 890.0,
    "limit": 3500.0,
    "last_7_days_liters": 1290.0,
    "previous_week_same_days": 200.0,
    "change_percent": 345.0,
    "days_elapsed": 5
  },
  "averages": {
    "daily_7d": 184.3,
    "daily_30d": 186.2,
    "days_with_data_7d": 7,
    "days_with_data_30d": 8,
    "per_person_daily_7d": 36.9,
    "weekly_equivalent": 1303.4
  }
}
```

#### Daily series (zero-filled)

```bash
curl -X GET http://127.0.0.1:8000/api/households/1/usage/daily?start=2026-11-04&end=2026-11-06 \
  -H "Authorization: Bearer $TOKEN"
```
**Response `200`**
```json
{
  "start": "2026-11-04",
  "end": "2026-11-06",
  "days": [
    {
      "date": "2026-11-04",
      "liters": 200.0,
      "over_limit": false
    },
    {
      "date": "2026-11-05",
      "liters": 200.0,
      "over_limit": false
    },
    "... 1 more"
  ]
}
```

#### Where the water goes

```bash
curl -X GET http://127.0.0.1:8000/api/households/1/usage/by-source?period=week \
  -H "Authorization: Bearer $TOKEN"
```
**Response `200`**
```json
{
  "period": "week",
  "start": "2026-10-31",
  "end": "2026-11-06",
  "total_liters": 1290.0,
  "items": [
    {
      "source_id": 1,
      "name": "Showers & baths",
      "color": "#267e78",
      "liters": 600.0,
      "percent": 47
    },
    {
      "source_id": 3,
      "name": "Toilets",
      "color": "#9bbcad",
      "liters": 360.0,
      "percent": 28
    },
    "... 1 more"
  ]
}
```

#### Consumption history

```bash
curl -X GET http://127.0.0.1:8000/api/households/1/history?days=7 \
  -H "Authorization: Bearer $TOKEN"
```
**Response `200`**
```json
{
  "start": "2026-10-31",
  "end": "2026-11-06",
  "days": [
    {
      "date": "2026-11-06",
      "liters": 90.0,
      "limit": 500.0,
      "status": "On track",
      "by_source": [
        {
          "source": "Garden",
          "liters": 90.0
        }
      ]
    },
    {
      "date": "2026-11-05",
      "liters": 200.0,
      "limit": 500.0,
      "status": "On track",
      "by_source": [
        {
          "source": "Showers & baths",
          "liters": 100.0
        },
        {
          "source": "Toilets",
          "liters": 60.0
        },
        "... 1 more"
      ]
    },
    "... 5 more"
  ],
  "total_liters": 1290.0
}
```

#### Delete an entry

```bash
curl -X DELETE http://127.0.0.1:8000/api/usage/22 \
  -H "Authorization: Bearer $TOKEN"
```
**Response `204`**
```json
(empty body)
```

#### Record it again for the alert examples

```bash
curl -X POST http://127.0.0.1:8000/api/households/1/usage \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"usage_date": "2026-11-06", "liters": 96, "source": "Garden"}'
```
**Response `201`**
```json
{
  "entry": {
    "id": 23,
    "household_id": 1,
    "source_id": 2,
    "source_name": "Garden",
    "source_color": "#68a397",
    "usage_date": "2026-11-06",
    "liters": 96.0,
    "notes": "",
    "created_at": "2026-11-06 10:38:08"
  },
  "alerts_triggered": [
    {
      "id": 1,
      "household_id": 1,
      "kind": "high_source",
      "severity": "warning",
      "title": "Unusually high garden use",
      "message": "The garden used 96 L today — 2.4× its usual amount. Check for a running hose.",
      "source_id": 2,
      "source_name": "Garden",
      "usage_date": "2026-11-06",
      "liters": 96.0,
      "status": "open",
      "is_read": true,
      "detected_at": "2026-11-06 10:38:08",
      "resolved_at": null
    }
  ]
}
```

### Alerts

#### List open alerts

```bash
curl -X GET http://127.0.0.1:8000/api/households/1/alerts?status=open \
  -H "Authorization: Bearer $TOKEN"
```
**Response `200`**
```json
{
  "counts": {
    "open": 1,
    "open_attention": 1,
    "unread": 0
  },
  "items": [
    {
      "id": 1,
      "household_id": 1,
      "kind": "high_source",
      "severity": "warning",
      "title": "Unusually high garden use",
      "message": "The garden used 96 L today — 2.4× its usual amount. Check for a running hose.",
      "source_id": 2,
      "source_name": "Garden",
      "usage_date": "2026-11-06",
      "liters": 96.0,
      "status": "open",
      "is_read": true,
      "detected_at": "2026-11-06 10:38:08",
      "resolved_at": null
    }
  ]
}
```

#### Scan a day for unusually high consumption

```bash
curl -X POST http://127.0.0.1:8000/api/households/1/alerts/scan \
  -H "Authorization: Bearer $TOKEN"
```
**Response `200`**
```json
{
  "date": "2026-11-06",
  "alerts": [
    {
      "id": 1,
      "household_id": 1,
      "kind": "high_source",
      "severity": "warning",
      "title": "Unusually high garden use",
      "message": "The garden used 96 L today — 2.4× its usual amount. Check for a running hose.",
      "source_id": 2,
      "source_name": "Garden",
      "usage_date": "2026-11-06",
      "liters": 96.0,
      "status": "open",
      "is_read": true,
      "detected_at": "2026-11-06 10:38:08",
      "resolved_at": null
    }
  ]
}
```

#### Report running water (leak check)

```bash
curl -X POST http://127.0.0.1:8000/api/households/1/flow-events \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"flow_lpm": 1.8, "minutes": 25}'
```
**Response `200`**
```json
{
  "detected": true,
  "alert": {
    "id": 2,
    "household_id": 1,
    "kind": "continuous_flow",
    "severity": "warning",
    "title": "Water running for 25 minutes",
    "message": "Main meter is reading 1.8 L/min. If nothing is in use, check taps and toilets.",
    "source_id": null,
    "source_name": null,
    "usage_date": "2026-11-06",
    "liters": 45.0,
    "status": "open",
    "is_read": false,
    "detected_at": "2026-11-06 10:38:08",
    "resolved_at": null
  }
}
```

#### Dismiss (or acknowledge / reopen) an alert

```bash
curl -X PUT http://127.0.0.1:8000/api/alerts/1 \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"status": "dismissed"}'
```
**Response `200`**
```json
{
  "id": 1,
  "household_id": 1,
  "kind": "high_source",
  "severity": "warning",
  "title": "Unusually high garden use",
  "message": "The garden used 96 L today — 2.4× its usual amount. Check for a running hose.",
  "source_id": 2,
  "source_name": "Garden",
  "usage_date": "2026-11-06",
  "liters": 96.0,
  "status": "dismissed",
  "is_read": true,
  "detected_at": "2026-11-06 10:38:08",
  "resolved_at": "2026-11-06 10:38:08"
}
```

#### Mark everything read

```bash
curl -X POST http://127.0.0.1:8000/api/households/1/alerts/mark-read \
  -H "Authorization: Bearer $TOKEN"
```
**Response `200`**
```json
{
  "marked": 1
}
```

#### Delete an alert

```bash
curl -X DELETE http://127.0.0.1:8000/api/alerts/1 \
  -H "Authorization: Bearer $TOKEN"
```
**Response `204`**
```json
(empty body)
```

### Reminder schedules

#### Schedule a reminder

```bash
curl -X POST http://127.0.0.1:8000/api/households/1/schedules \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title": "Evening usage check-in", "reminder_type": "Usage Check-in", "days": "daily", "time_of_day": "20:00", "channel": "Push notification"}'
```
**Response `201`**
```json
{
  "id": 1,
  "household_id": 1,
  "title": "Evening usage check-in",
  "reminder_type": "Usage Check-in",
  "days": "daily",
  "time_of_day": "20:00",
  "channel": "Push notification",
  "notes": "",
  "enabled": true,
  "description": "Every day · 8:00 PM · Push notification",
  "next_run": "2026-11-06 20:00",
  "last_fired_on": null,
  "created_at": "2026-11-06 10:38:08"
}
```

#### Weekly schedule on chosen days

```bash
curl -X POST http://127.0.0.1:8000/api/households/1/schedules \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title": "Check garden watering", "reminder_type": "Garden Watering", "days": ["mon", "wed", "fri"], "time_of_day": "06:30"}'
```
**Response `201`**
```json
{
  "id": 2,
  "household_id": 1,
  "title": "Check garden watering",
  "reminder_type": "Garden Watering",
  "days": "mon,wed,fri",
  "time_of_day": "06:30",
  "channel": "Push notification",
  "notes": "",
  "enabled": true,
  "description": "Mon, Wed, Fri · 6:30 AM · Push notification",
  "next_run": "2026-11-09 06:30",
  "last_fired_on": null,
  "created_at": "2026-11-06 10:38:08"
}
```

#### List schedules

```bash
curl -X GET http://127.0.0.1:8000/api/households/1/schedules \
  -H "Authorization: Bearer $TOKEN"
```
**Response `200`**
```json
[
  {
    "id": 2,
    "household_id": 1,
    "title": "Check garden watering",
    "reminder_type": "Garden Watering",
    "days": "mon,wed,fri",
    "time_of_day": "06:30",
    "channel": "Push notification",
    "notes": "",
    "enabled": true,
    "description": "Mon, Wed, Fri · 6:30 AM · Push notification",
    "next_run": "2026-11-09 06:30",
    "last_fired_on": null,
    "created_at": "2026-11-06 10:38:08"
  },
  {
    "id": 1,
    "household_id": 1,
    "title": "Evening usage check-in",
    "reminder_type": "Usage Check-in",
    "days": "daily",
    "time_of_day": "20:00",
    "channel": "Push notification",
    "notes": "",
    "enabled": true,
    "description": "Every day · 8:00 PM · Push notification",
    "next_run": "2026-11-06 20:00",
    "last_fired_on": null,
    "created_at": "2026-11-06 10:38:08"
  }
]
```

#### Switch a schedule off

```bash
curl -X PUT http://127.0.0.1:8000/api/schedules/1 \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"enabled": false}'
```
**Response `200`**
```json
{
  "id": 1,
  "household_id": 1,
  "title": "Evening usage check-in",
  "reminder_type": "Usage Check-in",
  "days": "daily",
  "time_of_day": "20:00",
  "channel": "Push notification",
  "notes": "",
  "enabled": false,
  "description": "Every day · 8:00 PM · Push notification",
  "next_run": null,
  "last_fired_on": null,
  "created_at": "2026-11-06 10:38:08"
}
```

#### Upcoming reminders

```bash
curl -X GET http://127.0.0.1:8000/api/households/1/schedules/upcoming \
  -H "Authorization: Bearer $TOKEN"
```
**Response `200`**
```json
[
  {
    "id": 2,
    "household_id": 1,
    "title": "Check garden watering",
    "reminder_type": "Garden Watering",
    "days": "mon,wed,fri",
    "time_of_day": "06:30",
    "channel": "Push notification",
    "notes": "",
    "enabled": true,
    "description": "Mon, Wed, Fri · 6:30 AM · Push notification",
    "next_run": "2026-11-09 06:30",
    "last_fired_on": null,
    "created_at": "2026-11-06 10:38:08",
    "when": "Mon, 6:30 AM"
  }
]
```

#### Fire due reminders now

```bash
curl -X POST http://127.0.0.1:8000/api/households/1/schedules/check-due \
  -H "Authorization: Bearer $TOKEN"
```
**Response `200`**
```json
{
  "fired": [
    {
      "id": 3,
      "household_id": 1,
      "kind": "reminder",
      "severity": "info",
      "title": "Check garden watering",
      "message": "Reminder: Check garden watering",
      "source_id": null,
      "source_name": null,
      "usage_date": "2026-11-06",
      "liters": null,
      "status": "open",
      "is_read": false,
      "detected_at": "2026-11-06 10:38:08",
      "resolved_at": null
    }
  ]
}
```

#### Allowed types and channels

```bash
curl -X GET http://127.0.0.1:8000/api/reminder-options \
  -H "Authorization: Bearer $TOKEN"
```
**Response `200`**
```json
{
  "types": [
    "Usage Check-in",
    "Garden Watering",
    "... 5 more"
  ],
  "channels": [
    "Push notification",
    "Email",
    "... 1 more"
  ],
  "days": [
    "daily",
    "weekdays",
    "... 8 more"
  ]
}
```

#### Delete a schedule

```bash
curl -X DELETE http://127.0.0.1:8000/api/schedules/1 \
  -H "Authorization: Bearer $TOKEN"
```
**Response `204`**
```json
(empty body)
```

### Dashboard

#### Dashboard statistics (everything the screen shows)
Lists are shortened here; the real response contains every bar, alert and reminder.
```bash
curl -X GET http://127.0.0.1:8000/api/households/1/dashboard?period=week \
  -H "Authorization: Bearer $TOKEN"
```
**Response `200`**
```json
{
  "generated_at": "2026-11-06 10:38:08",
  "household": {
    "id": 1,
    "name": "Maple House",
    "members": 5,
    "city": "Tarlac City"
  },
  "date": "2026-11-06",
  "today": {
    "liters": 96.0,
    "limit": 500.0,
    "percent": 19,
    "remaining": 404.0,
    "status": "On track"
  },
  "yesterday": {
    "liters": 200.0,
    "difference": -104.0,
    "change_percent": -52.0
  },
  "week": {
    "start": "2026-11-02",
    "end": "2026-11-06",
    "liters": 896.0,
    "limit": 3500.0,
    "last_7_days_liters": 1296.0,
    "previous_week_same_days": 200.0,
    "change_percent": 348.0,
    "days_elapsed": 5
  },
  "averages": {
    "daily_7d": 185.1,
    "daily_30d": 187.0,
    "days_with_data_7d": 7,
    "days_with_data_30d": 8,
    "per_person_daily_7d": 37.0,
    "weekly_equivalent": 1309.0
  },
  "cost": {
    "today": 0.29,
    "currency": "$",
    "rate_per_1000_l": 3.0
  },
  "limits": {
    "household_id": 1,
    "daily_limit_liters": 500.0,
    "weekly_limit_liters": 3500.0,
    "alert_threshold_pct": 90,
    "spike_multiplier": 1.5,
    "rate_per_1000_l": 3.0,
    "currency": "$",
    "updated_at": "2026-11-06 10:38:08"
  },
  "chart": {
    "period": "week",
    "mode": "days",
    "start": "2026-10-31",
    "end": "2026-11-06",
    "target": 500.0,
    "subtitle": "Oct 31 – Nov 6, 2026 · Daily household usage",
    "bars": [
      {
        "date": "2026-10-31",
        "label": "Sat",
        "liters": 200.0,
        "is_today": false,
        "over_limit": false
      },
      {
        "date": "2026-11-01",
        "label": "Sun",
        "liters": 200.0,
        "is_today": false,
        "over_limit": false
      },
      "... 5 more"
    ],
    "average": 185.1,
    "change_percent": -7.5,
    "insight": "Your daily average is down 8% this week. Small changes add up."
  },
  "alerts": {
    "open_count": 2,
    "items": [
      {
        "id": 4,
        "household_id": 1,
        "kind": "high_source",
        "severity": "warning",
        "title": "Unusually high garden use",
        "message": "The garden used 96 L today — 2.4× its usual amount. Check for a running hose.",
        "source_id": 2,
        "source_name": "Garden",
        "usage_date": "2026-11-06",
        "liters": 96.0,
        "status": "open",
        "is_read": false,
        "detected_at": "2026-11-06 10:38:08",
        "resolved_at": null
      },
      {
        "id": 2,
        "household_id": 1,
        "kind": "continuous_flow",
        "severity": "warning",
        "title": "Water running for 25 minutes",
        "message": "Main meter is reading 1.8 L/min. If nothing is in use, check taps and toilets.",
        "source_id": null,
        "source_name": null,
        "usage_date": "2026-11-06",
        "liters": 45.0,
        "status": "open",
        "is_read": true,
        "detected_at": "2026-11-06 10:38:08",
        "resolved_at": null
      }
    ],
    "counts": {
      "open": 3,
      "open_attention": 2,
      "unread": 2
    }
  },
  "sources": {
    "period": "today",
    "total_liters": 96.0,
    "items": [
      {
        "source_id": 2,
        "name": "Garden",
        "color": "#68a397",
        "liters": 96.0,
        "percent": 100,
        "flagged": true
      }
    ],
    "connected": 5,
    "note": "Record usage by source to see where your water goes."
  },
  "reminders": {
    "items": [
      {
        "id": 2,
        "household_id": 1,
        "title": "Check garden watering",
        "reminder_type": "Garden Watering",
        "days": "mon,wed,fri",
        "time_of_day": "06:30",
        "channel": "Push notification",
        "notes": "",
        "enabled": true,
        "description": "Mon, Wed, Fri · 6:30 AM · Push notification",
        "next_run": "2026-11-09 06:30",
        "last_fired_on": "2026-11-06",
        "created_at": "2026-11-06 10:38:08"
      }
    ],
    "next": {
      "id": 2,
      "household_id": 1,
      "title": "Check garden watering",
      "reminder_type": "Garden Watering",
      "days": "mon,wed,fri",
      "time_of_day": "06:30",
      "channel": "Push notification",
      "notes": "",
      "enabled": true,
      "description": "Mon, Wed, Fri · 6:30 AM · Push notification",
      "next_run": "2026-11-09 06:30",
      "last_fired_on": "2026-11-06",
      "created_at": "2026-11-06 10:38:08",
      "when": "Mon, 6:30 AM"
    },
    "upcoming": [
      {
        "id": 2,
        "household_id": 1,
        "title": "Check garden watering",
        "reminder_type": "Garden Watering",
        "days": "mon,wed,fri",
        "time_of_day": "06:30",
        "channel": "Push notification",
        "notes": "",
        "enabled": true,
        "description": "Mon, Wed, Fri · 6:30 AM · Push notification",
        "next_run": "2026-11-09 06:30",
        "last_fired_on": "2026-11-06",
        "created_at": "2026-11-06 10:38:08",
        "when": "Mon, 6:30 AM"
      }
    ]
  },
  "notifications": {
    "household_id": 1,
    "push_enabled": true,
    "email_enabled": true,
    "quiet_start": "22:00",
    "quiet_end": "06:00"
  },
  "tip": {
    "eyebrow": "A SMALL CHANGE FOR YOUR HOME",
    "title": "Water the roots, not the afternoon sun.",
    "text": "Your garden is using more than usual. Try watering before 8 AM to reduce evaporation.",
    "savings": "Up to 30%",
    "savings_label": "less outdoor water use"
  },
  "all_tips": [
    "Water the roots, not the afternoon sun: water the garden before 8 AM to cut evaporation.",
    "Shorten showers by one or two minutes; a low-flow showerhead can save up to 40 %.",
    "... 6 more"
  ]
}
```

#### Export CSV

```bash
curl -X GET http://127.0.0.1:8000/api/households/1/export.csv?start=2026-11-05&end=2026-11-06 \
  -H "Authorization: Bearer $TOKEN"
```
**Response `200`**
```csv
date,source,liters,notes
2026-11-05,Garden,40.0,
2026-11-05,Showers & baths,100.0,
2026-11-05,Toilets,60.0,
2026-11-06,Garden,96.0,

```

### Meter readings (shared with the desktop app)

#### Add a reading

```bash
curl -X POST http://127.0.0.1:8000/api/households/1/meter-readings \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"reading_date": "2026-11-03", "meter_reading": 120.5}'
```
**Response `201`**
```json
{
  "id": 1,
  "household_id": 1,
  "reading_date": "2026-11-03",
  "meter_reading": 120.5,
  "notes": ""
}
```

#### Add the next reading

```bash
curl -X POST http://127.0.0.1:8000/api/households/1/meter-readings \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"reading_date": "2026-11-06", "meter_reading": 121.1}'
```
**Response `201`**
```json
{
  "id": 2,
  "household_id": 1,
  "reading_date": "2026-11-06",
  "meter_reading": 121.1,
  "notes": ""
}
```

#### List readings with usage

```bash
curl -X GET http://127.0.0.1:8000/api/households/1/meter-readings \
  -H "Authorization: Bearer $TOKEN"
```
**Response `200`**
```json
[
  {
    "id": 2,
    "household_id": 1,
    "reading_date": "2026-11-06",
    "meter_reading": 121.1,
    "notes": "",
    "household_name": "Maple House",
    "used_m3": 0.6,
    "liters_per_person_day": 40.0,
    "status": "Within target"
  },
  {
    "id": 1,
    "household_id": 1,
    "reading_date": "2026-11-03",
    "meter_reading": 120.5,
    "notes": "",
    "household_name": "Maple House",
    "used_m3": null,
    "liters_per_person_day": null,
    "status": "Baseline"
  }
]
```

#### A meter can never run backwards

```bash
curl -X POST http://127.0.0.1:8000/api/households/1/meter-readings \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"reading_date": "2026-11-05", "meter_reading": 100}'
```
**Response `422`**
```json
{
  "error": {
    "code": "validation_error",
    "message": "Reading is lower than the earlier one (120.5 m³ on 2026-11-03).",
    "details": [
      "Reading is lower than the earlier one (120.5 m³ on 2026-11-03)."
    ]
  }
}
```

### Error responses

#### Validation error (422)

```bash
curl -X POST http://127.0.0.1:8000/api/households/1/usage \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"usage_date": "2026-11-06", "liters": -5, "source": "Garden"}'
```
**Response `422`**
```json
{
  "error": {
    "code": "validation_error",
    "message": "liters: Input should be greater than or equal to 0",
    "details": [
      "liters: Input should be greater than or equal to 0"
    ]
  }
}
```

#### Several problems at once (422)

```bash
curl -X POST http://127.0.0.1:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"name": "A", "email": "nope", "password": "123"}'
```
**Response `422`**
```json
{
  "error": {
    "code": "validation_error",
    "message": "password: String should have at least 8 characters",
    "details": [
      "password: String should have at least 8 characters"
    ]
  }
}
```

#### Future date (422)

```bash
curl -X POST http://127.0.0.1:8000/api/households/1/usage \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"usage_date": "2026-11-09", "liters": 5, "source": "Garden"}'
```
**Response `422`**
```json
{
  "error": {
    "code": "validation_error",
    "message": "Usage cannot be recorded for a future date.",
    "details": [
      "Usage cannot be recorded for a future date."
    ]
  }
}
```

#### Not signed in (401)

```bash
curl -X GET http://127.0.0.1:8000/api/households
```
**Response `401`**
```json
{
  "error": {
    "code": "unauthorized",
    "message": "Sign in first (missing Authorization: Bearer token).",
    "details": []
  }
}
```

#### Not found (404)

```bash
curl -X GET http://127.0.0.1:8000/api/usage/99999 \
  -H "Authorization: Bearer $TOKEN"
```
**Response `404`**
```json
{
  "error": {
    "code": "not_found",
    "message": "Usage entry not found.",
    "details": []
  }
}
```

#### Conflict (409)

```bash
curl -X POST http://127.0.0.1:8000/api/households \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "Maple House", "city": "X", "members": 2}'
```
**Response `409`**
```json
{
  "error": {
    "code": "conflict",
    "message": "That change breaks a rule in the database (for example a duplicate household name or a second reading on the same date).",
    "details": []
  }
}
```

#### Source in use (409)

```bash
curl -X DELETE http://127.0.0.1:8000/api/sources/2 \
  -H "Authorization: Bearer $TOKEN"
```
**Response `409`**
```json
{
  "error": {
    "code": "conflict",
    "message": "This source has 8 usage entries. Disable it instead of deleting it, or delete those entries first.",
    "details": []
  }
}
```
