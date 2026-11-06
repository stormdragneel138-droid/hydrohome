# Database Design (SQLite, `data/hydrohome.db`)

```mermaid
erDiagram
    households ||--o{ water_readings : has
    households ||--o{ reminders : has
    households ||--o| meter_sources : feeds_from
    households { int id PK
      text name UK
      text address
      text city
      int members
      int daily_target_liters
      real latitude
      real longitude }
    water_readings { int id PK
      int household_id FK
      text reading_date
      real meter_reading
      text notes }
    reminders { int id PK
      int household_id FK
      text title
      text reminder_type
      text due_at
      text repeat_rule
      text status
      text notes
      text last_notified }
    meter_sources { int id PK
      int household_id FK_UK
      text source_type
      text location
      text api_key
      text reading_path
      text unit
      int interval_minutes
      int enabled
      text last_sync_at
      text last_status }
```
* `meter_sources` holds one smart-meter connection per household (`UNIQUE household_id`; saved with an upsert).
* `ON DELETE CASCADE`: deleting a household removes its readings and reminders (the UI warns first).
* `UNIQUE(household_id, reading_date)`: one reading per household per day.
* `CHECK` constraints back up the validators (members > 0, meter ≥ 0).
* All queries are parameterized (`?`); verified by `test_sql_injection_text_is_stored_literally`.
