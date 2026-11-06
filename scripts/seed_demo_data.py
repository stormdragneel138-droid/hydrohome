"""Fill a SEPARATE demo database with a ready-to-explore household (never your real data).

    python scripts/seed_demo_data.py            # creates data/demo.db
    python run_api.py --db data/demo.db         # then sign in with the account printed below
"""
import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hydrohome.api.container import build_web_services  # noqa: E402

EMAIL, PASSWORD = "demo@hydrohome.local", "demo-pass-123"
PAST_TOTALS = [436, 520, 570, 510, 478, 466, 540, 452, 498, 530, 470, 505, 462, 515]   # 1..14 days ago
TODAY = {"Showers & baths": 138, "Garden": 96, "Toilets": 78, "Laundry": 46, "Kitchen": 26}  # = 384 L


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=str(Path(__file__).resolve().parent.parent / "data" / "demo.db"))
    db = Path(parser.parse_args().db)
    if db.exists():
        db.unlink()
    svc = build_web_services(db)
    user, _ = svc.auth.register("Jamie Lewis", EMAIL, PASSWORD)
    hid = svc.base.households.add({"name": "Maple House", "address": "12 Maple Street", "city": "Tarlac City",
                                   "members": "4", "daily_target_liters": "125"})
    svc.memberships.link(hid, user["id"], "admin")
    svc.settings.ensure_defaults(hid)
    names = {s["name"]: s["id"] for s in svc.settings.list_sources(hid)}
    today = date.today()

    for ago, total in enumerate(PAST_TOTALS, start=1):
        day, garden = today - timedelta(days=ago), 44 + (ago * 7) % 9
        rest = total - garden
        shares = {"Showers & baths": .42, "Toilets": .24, "Laundry": .20, "Kitchen": .14}
        svc.usage.record(hid, day, garden, names["Garden"], user_id=user["id"])
        for name, share in shares.items():
            svc.usage.record(hid, day, round(rest * share, 1), names[name], user_id=user["id"])
    for name, liters in TODAY.items():
        svc.usage.record(hid, today, liters, names[name], user_id=user["id"])

    svc.alerts.evaluate(hid, today)
    svc.alerts.check_flow(hid, 1.8, 25)
    for title, kind, days, at, enabled in (
            ("Evening usage check-in", "Usage Check-in", "daily", "20:00", True),
            ("Check garden watering", "Garden Watering", ["mon", "wed", "fri"], "06:30", True),
            ("Weekly leak check", "Leak Check", ["sun"], "09:00", False)):
        svc.schedules.add(hid, {"title": title, "reminder_type": kind, "days": days, "time_of_day": at,
                                "channel": "Push notification", "notes": "", "enabled": enabled})
    print(f"Demo database ready: {db}\nSign in with  {EMAIL}  /  {PASSWORD}\n"
          f"Start it with:  python run_api.py --db \"{db}\"")


if __name__ == "__main__":
    main()
