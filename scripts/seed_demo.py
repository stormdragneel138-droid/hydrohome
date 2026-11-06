"""Optional: load demo data for the defense.   python -m scripts.seed_demo"""
from datetime import date, datetime, timedelta

from hydrohome.container import build_services
from hydrohome.errors import AppError


def main():
    s = build_services()
    try:
        hid = s.households.add({"name": "Santos Family", "address": "Brgy. San Roque",
                                "city": "Tarlac City", "members": 4, "daily_target_liters": 100})
    except AppError as exc:
        print("Demo data already loaded or could not be added:", exc)
        return
    start, meter = date.today() - timedelta(days=150), 120.0
    for i, m3 in enumerate((0, 11.2, 12.0, 13.9, 14.4, 12.6)):
        meter += m3
        s.readings.add({"household_id": hid, "reading_date": (start + timedelta(days=30 * i)).isoformat(),
                        "meter_reading": meter, "notes": "demo"})
    soon = datetime.now() + timedelta(minutes=2)
    for title, rtype, when, rep in (
            ("Read the water meter", "Meter Reading", soon, "Monthly"),
            ("Pay water bill", "Bill Payment", datetime.now() + timedelta(days=3), "Monthly"),
            ("Weekly leak check (taps off, meter still?)", "Leak Check", datetime.now() + timedelta(days=1), "Weekly")):
        s.reminders.add({"household_id": hid, "title": title, "reminder_type": rtype,
                         "due_date": when.strftime("%Y-%m-%d"), "due_time": when.strftime("%H:%M"),
                         "repeat_rule": rep, "notes": ""})
    print("Demo data loaded.")


if __name__ == "__main__":
    main()
