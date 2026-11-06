"""End-to-end tests of the REST API (real FastAPI app, real SQLite file, no mocks)."""
from datetime import date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from hydrohome.api.app import create_app


def day(n=0):
    """ISO date n days ago."""
    return (date.today() - timedelta(days=n)).isoformat()


@pytest.fixture
def client(tmp_path):
    app = create_app(tmp_path / "api.db", start_scheduler=False)
    with TestClient(app) as c:
        c.app_ = app
        yield c


def signup(client, email="jamie@example.com", name="Jamie Lewis"):
    r = client.post("/api/auth/register", json={"name": name, "email": email,
                                                "password": "correct-horse"})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture
def auth(client):
    return signup(client)


@pytest.fixture
def hh(client, auth):
    r = client.post("/api/households", headers=auth, json={
        "name": "Maple House", "city": "Tarlac City", "members": 4, "daily_limit_liters": 500})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def add(client, auth, hid, liters, source="Garden", days_ago=0, notes=""):
    r = client.post(f"/api/households/{hid}/usage", headers=auth, json={
        "usage_date": day(days_ago), "liters": liters, "source": source, "notes": notes})
    assert r.status_code == 201, r.text
    return r.json()


def seed_week(client, auth, hid):
    """Seven days of ordinary use so detection has a baseline: garden 40 L, showers 100 L."""
    for n in range(1, 8):
        add(client, auth, hid, 40, "Garden", n)
        add(client, auth, hid, 100, "Showers & baths", n)


# ---------------------------------------------------------------- system + auth
def test_health(client):
    assert client.get("/api/health").json()["status"] == "ok"


def test_docs_and_dashboard_page_are_served(client):
    assert client.get("/docs").status_code == 200
    assert client.get("/openapi.json").status_code == 200
    assert "<html" in client.get("/").text.lower()


def test_register_login_me_logout(client):
    r = client.post("/api/auth/register", json={"name": "Jamie", "email": "J@Example.com",
                                                "password": "correct-horse"})
    assert r.status_code == 201 and r.json()["user"]["email"] == "j@example.com"
    assert "password" not in str(r.json())
    token = r.json()["token"]
    h = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/auth/me", headers=h).json()["name"] == "Jamie"
    ok = client.post("/api/auth/login", json={"email": "j@example.com", "password": "correct-horse"})
    assert ok.status_code == 200 and ok.json()["token"] != token
    assert client.post("/api/auth/logout", headers=h).status_code == 204
    assert client.get("/api/auth/me", headers=h).status_code == 401


def test_register_validation_and_duplicates(client):
    bad = client.post("/api/auth/register", json={"name": "A", "email": "nope", "password": "correct-horse"})
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "validation_error"
    short = client.post("/api/auth/register", json={"name": "A", "email": "a@b.co", "password": "123"})
    assert short.status_code == 422
    signup(client)
    dup = client.post("/api/auth/register", json={"name": "X", "email": "JAMIE@example.com",
                                                  "password": "correct-horse"})
    assert dup.status_code == 409


def test_login_failures(client, auth):
    for payload in ({"email": "jamie@example.com", "password": "wrong-password"},
                    {"email": "ghost@example.com", "password": "correct-horse"}):
        r = client.post("/api/auth/login", json=payload)
        assert r.status_code == 401 and r.json()["error"]["code"] == "unauthorized"


def test_protected_routes_need_a_token(client):
    for method, url in (("get", "/api/households"), ("get", "/api/households/1/dashboard"),
                        ("post", "/api/households/1/usage"), ("get", "/api/usage/1"),
                        ("put", "/api/alerts/1"), ("delete", "/api/schedules/1")):
        r = getattr(client, method)(url)
        assert r.status_code == 401, (method, url)
    assert client.get("/api/households", headers={"Authorization": "Bearer nonsense"}).status_code == 401


def test_update_profile_and_password(client, auth):
    assert client.put("/api/auth/me", headers=auth, json={"name": "Jamie L."}).json()["name"] == "Jamie L."
    assert client.put("/api/auth/me", headers=auth, json={"name": ""}).status_code == 422
    wrong = client.put("/api/auth/password", headers=auth,
                       json={"current_password": "nope-nope", "new_password": "brand-new-pass"})
    assert wrong.status_code == 422
    ok = client.put("/api/auth/password", headers=auth,
                    json={"current_password": "correct-horse", "new_password": "brand-new-pass"})
    assert ok.status_code == 204
    assert client.post("/api/auth/login", json={"email": "jamie@example.com",
                                                "password": "brand-new-pass"}).status_code == 200


# ------------------------------------------------------------------ households
def test_household_crud(client, auth, hh):
    listing = client.get("/api/households", headers=auth).json()
    assert [h["name"] for h in listing] == ["Maple House"] and listing[0]["role"] == "admin"
    one = client.get(f"/api/households/{hh}", headers=auth).json()
    assert one["limits"]["daily_limit_liters"] == 500 and one["members"] == 4
    up = client.put(f"/api/households/{hh}", headers=auth, json={"members": 5, "city": "Manila"})
    assert up.status_code == 200 and up.json()["members"] == 5 and up.json()["city"] == "Manila"
    assert client.delete(f"/api/households/{hh}", headers=auth).status_code == 204
    assert client.get(f"/api/households/{hh}", headers=auth).status_code == 404


def test_household_validation(client, auth, hh):
    assert client.post("/api/households", headers=auth, json={"name": "X", "city": "Y", "members": 0}).status_code == 422
    assert client.post("/api/households", headers=auth, json={"name": "", "city": "Y", "members": 2}).status_code == 422
    assert client.post("/api/households", headers=auth, json={"name": "X", "city": "Y", "members": 2, "bogus": 1}).status_code == 422
    dup = client.post("/api/households", headers=auth, json={"name": "Maple House", "city": "Y", "members": 2})
    assert dup.status_code == 409
    assert client.put(f"/api/households/{hh}", headers=auth, json={"members": 99}).status_code == 422


def test_households_are_private_between_users(client, auth, hh):
    other = signup(client, "other@example.com", "Other")
    assert client.get("/api/households", headers=other).json() == []
    entry = add(client, auth, hh, 50)["entry"]
    for method, url in (("get", f"/api/households/{hh}"), ("get", f"/api/households/{hh}/dashboard"),
                        ("get", f"/api/households/{hh}/usage"), ("get", f"/api/usage/{entry['id']}"),
                        ("delete", f"/api/usage/{entry['id']}"), ("delete", f"/api/households/{hh}")):
        assert getattr(client, method)(url, headers=other).status_code == 404, url


def test_first_user_adopts_desktop_households_and_others_can_claim(tmp_path):
    app = create_app(tmp_path / "legacy.db", start_scheduler=False)
    app.state.services.base.households.add({"name": "Old House", "address": "", "city": "Cab",
                                            "members": "3", "daily_target_liters": "100"})
    with TestClient(app) as c:
        first = signup(c)
        assert [h["name"] for h in c.get("/api/households", headers=first).json()] == ["Old House"]
        app.state.services.base.households.add({"name": "Second", "address": "", "city": "Cab",
                                                "members": "2", "daily_target_liters": "100"})
        second = signup(c, "b@example.com", "B")
        assert c.get("/api/households", headers=second).json() == []
        loose = c.get("/api/households/unclaimed", headers=second).json()
        assert [h["name"] for h in loose] == ["Second"]
        assert c.post(f"/api/households/{loose[0]['id']}/claim", headers=second).status_code == 200
        assert c.post(f"/api/households/{loose[0]['id']}/claim", headers=first).status_code == 404


# ------------------------------------------------- limits / notifications / sources
def test_limits_defaults_and_update(client, auth, hh):
    assert client.get(f"/api/households/{hh}/limits", headers=auth).json()["alert_threshold_pct"] == 90
    r = client.put(f"/api/households/{hh}/limits", headers=auth,
                   json={"daily_limit_liters": 450, "weekly_limit_liters": 3000, "rate_per_1000_l": 4.5})
    assert r.status_code == 200
    assert (r.json()["daily_limit_liters"], r.json()["weekly_limit_liters"], r.json()["rate_per_1000_l"]) == (450, 3000, 4.5)
    assert client.get(f"/api/households/{hh}/limits", headers=auth).json()["daily_limit_liters"] == 450


def test_limits_validation(client, auth, hh):
    url = f"/api/households/{hh}/limits"
    assert client.put(url, headers=auth, json={"daily_limit_liters": -5}).status_code == 422
    assert client.put(url, headers=auth, json={"alert_threshold_pct": 20}).status_code == 422
    assert client.put(url, headers=auth, json={"daily_limit_liters": "abc"}).status_code == 422
    weekly = client.put(url, headers=auth, json={"daily_limit_liters": 800, "weekly_limit_liters": 500})
    assert weekly.status_code == 422 and "Weekly limit" in weekly.json()["error"]["message"]


def test_notification_settings(client, auth, hh):
    url = f"/api/households/{hh}/notification-settings"
    assert client.get(url, headers=auth).json() == {"household_id": hh, "push_enabled": True,
                                                    "email_enabled": True, "quiet_start": "22:00",
                                                    "quiet_end": "06:00"}
    r = client.put(url, headers=auth, json={"email_enabled": False, "quiet_start": "23:30"})
    assert r.json()["email_enabled"] is False and r.json()["quiet_start"] == "23:30"
    assert client.put(url, headers=auth, json={"quiet_start": "25:99"}).status_code == 422


def test_sources_crud(client, auth, hh):
    base = f"/api/households/{hh}/sources"
    names = [s["name"] for s in client.get(base, headers=auth).json()]
    assert names == ["Showers & baths", "Garden", "Toilets", "Laundry", "Kitchen"]
    pool = client.post(base, headers=auth, json={"name": "Pool", "color": "#112233"})
    assert pool.status_code == 201
    sid = pool.json()["id"]
    assert client.post(base, headers=auth, json={"name": "pool"}).status_code == 422   # duplicate
    assert client.post(base, headers=auth, json={"name": "X", "color": "red"}).status_code == 422
    off = client.put(f"/api/sources/{sid}", headers=auth, json={"enabled": False})
    assert off.json()["enabled"] is False
    refused = client.post(f"/api/households/{hh}/usage", headers=auth,
                          json={"usage_date": day(), "liters": 10, "source_id": sid})
    assert refused.status_code == 422 and "disabled" in refused.json()["error"]["message"]
    assert client.delete(f"/api/sources/{sid}", headers=auth).status_code == 204
    assert client.put("/api/sources/9999", headers=auth, json={"name": "Z"}).status_code == 404


def test_cannot_delete_source_that_has_usage(client, auth, hh):
    add(client, auth, hh, 10, "Garden")
    garden = next(s for s in client.get(f"/api/households/{hh}/sources", headers=auth).json()
                  if s["name"] == "Garden")
    r = client.delete(f"/api/sources/{garden['id']}", headers=auth)
    assert r.status_code == 409 and r.json()["error"]["code"] == "conflict"


# ------------------------------------------------------------------------ usage
def test_record_list_get_update_delete_usage(client, auth, hh):
    created = add(client, auth, hh, 138, "Showers & baths", notes="family showers")["entry"]
    assert created["liters"] == 138 and created["source_name"] == "Showers & baths"
    by_id = client.post(f"/api/households/{hh}/usage", headers=auth,
                        json={"usage_date": day(1), "liters": 20.5, "source_id": created["source_id"]})
    assert by_id.status_code == 201
    listing = client.get(f"/api/households/{hh}/usage", headers=auth).json()
    assert listing["total"] == 2 and listing["items"][0]["usage_date"] == day()
    assert client.get(f"/api/households/{hh}/usage?limit=1&offset=1", headers=auth).json()["items"][0]["liters"] == 20.5
    assert client.get(f"/api/households/{hh}/usage?start={day()}&end={day()}", headers=auth).json()["total"] == 1
    assert client.get(f"/api/households/{hh}/usage?source_id={created['source_id']}", headers=auth).json()["total"] == 2
    assert client.get(f"/api/usage/{created['id']}", headers=auth).json()["notes"] == "family showers"
    upd = client.put(f"/api/usage/{created['id']}", headers=auth, json={"liters": 150, "source": "Kitchen"})
    assert upd.status_code == 200 and upd.json()["entry"]["liters"] == 150
    assert upd.json()["entry"]["source_name"] == "Kitchen"
    assert client.delete(f"/api/usage/{created['id']}", headers=auth).status_code == 204
    assert client.get(f"/api/usage/{created['id']}", headers=auth).status_code == 404
    assert client.delete(f"/api/usage/{created['id']}", headers=auth).status_code == 404


def test_usage_validation(client, auth, hh):
    url = f"/api/households/{hh}/usage"
    ok = {"usage_date": day(), "liters": 10, "source": "Garden"}
    assert client.post(url, headers=auth, json={**ok, "liters": -1}).status_code == 422
    assert client.post(url, headers=auth, json={**ok, "liters": "lots"}).status_code == 422
    assert client.post(url, headers=auth, json={**ok, "usage_date": "not-a-date"}).status_code == 422
    future = client.post(url, headers=auth, json={**ok, "usage_date": (date.today() + timedelta(days=2)).isoformat()})
    assert future.status_code == 422 and "future" in future.json()["error"]["message"]
    assert client.post(url, headers=auth, json={**ok, "source": "Nope"}).status_code == 422
    assert client.post(url, headers=auth, json={"usage_date": day(), "liters": 5}).status_code == 422
    assert client.post(url, headers=auth, json={**ok, "extra": 1}).status_code == 422
    assert client.get(f"{url}?limit=0", headers=auth).status_code == 422
    assert client.get(f"{url}?start={day()}&end={day(5)}", headers=auth).status_code == 422
    assert client.get(f"/api/households/{hh}/usage/by-source?period=year", headers=auth).status_code == 422


def test_summary_daily_by_source_history_and_averages(client, auth, hh):
    for n in range(0, 4):
        add(client, auth, hh, 100, "Showers & baths", n)
        add(client, auth, hh, 50, "Garden", n)
    s = client.get(f"/api/households/{hh}/usage/summary", headers=auth).json()
    assert s["today"]["liters"] == 150 and s["today"]["limit"] == 500
    assert s["today"]["percent"] == 30 and s["today"]["remaining"] == 350
    assert s["today"]["status"] == "On track"
    assert s["yesterday"]["liters"] == 150 and s["yesterday"]["difference"] == 0
    assert s["averages"]["daily_7d"] == 150 and s["averages"]["days_with_data_7d"] == 4
    assert s["averages"]["per_person_daily_7d"] == 37.5
    assert s["week"]["liters"] <= s["week"]["last_7_days_liters"] == 600
    daily = client.get(f"/api/households/{hh}/usage/daily", headers=auth).json()
    assert len(daily["days"]) == 7 and daily["days"][-1]["liters"] == 150 and daily["days"][0]["liters"] == 0
    src = client.get(f"/api/households/{hh}/usage/by-source?period=week", headers=auth).json()
    assert src["total_liters"] == 600
    assert [(i["name"], i["liters"], i["percent"]) for i in src["items"]] == [("Showers & baths", 400, 67), ("Garden", 200, 33)]
    hist = client.get(f"/api/households/{hh}/history?days=10", headers=auth).json()
    assert len(hist["days"]) == 4 and hist["total_liters"] == 600
    assert hist["days"][0]["date"] == day() and hist["days"][0]["by_source"][0]["source"] == "Showers & baths"
    one = client.get(f"/api/households/{hh}/usage/summary?date={day(3)}", headers=auth).json()
    assert one["date"] == day(3) and one["today"]["liters"] == 150
    assert client.get(f"/api/households/{hh}/usage/daily?start={day()}&end={day(3)}", headers=auth).status_code == 422


def test_week_to_date_compares_with_same_weekdays_last_week(client, auth, hh):
    monday = date.today() - timedelta(days=date.today().weekday())
    add_on = lambda d, l: client.post(f"/api/households/{hh}/usage", headers=auth,
                                      json={"usage_date": d.isoformat(), "liters": l, "source": "Kitchen"})
    add_on(monday, 100)
    add_on(monday - timedelta(days=7), 200)
    s = client.get(f"/api/households/{hh}/usage/summary", headers=auth).json()["week"]
    assert s["start"] == monday.isoformat() and s["liters"] == 100
    assert s["previous_week_same_days"] == 200 and s["change_percent"] == -50.0


# ----------------------------------------------------------------------- alerts
def test_high_source_alert_is_detected_and_described(client, auth, hh):
    seed_week(client, auth, hh)
    res = add(client, auth, hh, 96, "Garden")          # usual 40 L -> 2.4x
    alerts = res["alerts_triggered"]
    assert [a["kind"] for a in alerts] == ["high_source"]
    assert alerts[0]["title"] == "Unusually high garden use"
    assert "96 L today — 2.4× its usual amount" in alerts[0]["message"]
    assert "running hose" in alerts[0]["message"]
    listing = client.get(f"/api/households/{hh}/alerts", headers=auth).json()
    assert listing["counts"]["open"] == 1 and listing["items"][0]["source_name"] == "Garden"


def test_no_alert_for_normal_use_or_without_history(client, auth, hh):
    # with no history there is nothing to compare against, so a big day is not "unusual" yet
    assert add(client, auth, hh, 400, "Garden")["alerts_triggered"] == []
    other = client.post("/api/households", headers=auth, json={
        "name": "Second Home", "city": "Tarlac City", "members": 4, "daily_limit_liters": 500}).json()["id"]
    seed_week(client, auth, other)
    assert add(client, auth, other, 5, "Kitchen")["alerts_triggered"] == []     # normal day


def test_limit_alerts_and_auto_resolve(client, auth, hh):
    near = add(client, auth, hh, 460, "Showers & baths")["alerts_triggered"]    # 92 % of 500
    assert [a["kind"] for a in near] == ["near_limit"]
    over = add(client, auth, hh, 100, "Laundry")
    assert "limit_exceeded" in [a["kind"] for a in over["alerts_triggered"]]
    open_now = client.get(f"/api/households/{hh}/alerts", headers=auth).json()["items"]
    assert open_now[0]["kind"] == "limit_exceeded" and open_now[0]["severity"] == "critical"
    # removing the entries that caused it resolves the alerts automatically
    for e in client.get(f"/api/households/{hh}/usage", headers=auth).json()["items"]:
        client.delete(f"/api/usage/{e['id']}", headers=auth)
    assert client.get(f"/api/households/{hh}/alerts", headers=auth).json()["items"] == []
    resolved = client.get(f"/api/households/{hh}/alerts?status=resolved", headers=auth).json()["items"]
    assert {a["kind"] for a in resolved} == {"near_limit", "limit_exceeded"}


def test_alert_lifecycle_status_read_delete(client, auth, hh):
    seed_week(client, auth, hh)
    alert = add(client, auth, hh, 96, "Garden")["alerts_triggered"][0]
    aid = alert["id"]
    assert client.get(f"/api/alerts/{aid}", headers=auth).json()["status"] == "open"
    assert client.put(f"/api/alerts/{aid}", headers=auth, json={"status": "bogus"}).status_code == 422
    dismissed = client.put(f"/api/alerts/{aid}", headers=auth, json={"status": "dismissed"})
    assert dismissed.json()["status"] == "dismissed" and dismissed.json()["is_read"] is True
    assert client.get(f"/api/households/{hh}/alerts", headers=auth).json()["items"] == []
    # a dismissed alert is not re-opened by another scan on the same day
    again = client.post(f"/api/households/{hh}/alerts/scan", headers=auth).json()
    assert again["alerts"] == []
    assert client.get(f"/api/households/{hh}/alerts?status=all", headers=auth).json()["items"][0]["status"] == "dismissed"
    assert client.get(f"/api/households/{hh}/alerts?status=sideways", headers=auth).status_code == 422
    client.put(f"/api/alerts/{aid}", headers=auth, json={"status": "open"})
    assert client.post(f"/api/households/{hh}/alerts/mark-read", headers=auth).json()["marked"] == 0
    assert client.delete(f"/api/alerts/{aid}", headers=auth).status_code == 204
    assert client.get(f"/api/alerts/{aid}", headers=auth).status_code == 404


def test_scan_finds_alerts_for_a_given_day(client, auth, hh):
    seed_week(client, auth, hh)
    add(client, auth, hh, 200, "Garden", days_ago=0)
    r = client.post(f"/api/households/{hh}/alerts/scan?date={day()}", headers=auth).json()
    assert r["alerts"] and r["alerts"][0]["kind"] == "high_source"
    assert client.post(f"/api/households/{hh}/alerts/scan?date={day(30)}", headers=auth).json()["alerts"] == []
    assert client.post(f"/api/households/{hh}/alerts/scan?date=oops", headers=auth).status_code == 422


def test_continuous_flow_detection(client, auth, hh):
    url = f"/api/households/{hh}/flow-events"
    assert client.post(url, headers=auth, json={"flow_lpm": 1.8, "minutes": 5}).json() == {"detected": False, "alert": None}
    hit = client.post(url, headers=auth, json={"flow_lpm": 1.8, "minutes": 25}).json()
    assert hit["detected"] and hit["alert"]["title"] == "Water running for 25 minutes"
    assert "1.8 L/min" in hit["alert"]["message"]
    assert client.post(url, headers=auth, json={"flow_lpm": 0, "minutes": 25}).status_code == 422
    assert client.post(url, headers=auth, json={"flow_lpm": 1, "minutes": 0}).status_code == 422


def test_mark_read_counts_unread(client, auth, hh):
    client.post(f"/api/households/{hh}/flow-events", headers=auth, json={"flow_lpm": 2, "minutes": 30})
    counts = client.get(f"/api/households/{hh}/alerts", headers=auth).json()["counts"]
    assert counts["unread"] == 1 and counts["open_attention"] == 1
    assert client.post(f"/api/households/{hh}/alerts/mark-read", headers=auth).json()["marked"] == 1
    assert client.get(f"/api/households/{hh}/alerts", headers=auth).json()["counts"]["unread"] == 0


# -------------------------------------------------------------------- schedules
def sched(**over):
    return {"title": "Evening usage check-in", "reminder_type": "Usage Check-in", "days": "daily",
            "time_of_day": "20:00", "channel": "Push notification", **over}


def test_schedule_crud_and_toggle(client, auth, hh):
    base = f"/api/households/{hh}/schedules"
    made = client.post(base, headers=auth, json=sched())
    assert made.status_code == 201
    s = made.json()
    assert s["description"] == "Every day · 8:00 PM · Push notification" and s["enabled"] and s["next_run"]
    garden = client.post(base, headers=auth, json=sched(title="Check garden watering", reminder_type="Garden Watering",
                                                        days=["mon", "wed", "fri"], time_of_day="06:30")).json()
    assert garden["description"] == "Mon, Wed, Fri · 6:30 AM · Push notification"
    assert [x["title"] for x in client.get(base, headers=auth).json()] == ["Check garden watering", "Evening usage check-in"]
    off = client.put(f"/api/schedules/{s['id']}", headers=auth, json={"enabled": False}).json()
    assert off["enabled"] is False and off["next_run"] is None
    edited = client.put(f"/api/schedules/{s['id']}", headers=auth, json={"time_of_day": "21:15", "days": "weekdays", "enabled": True}).json()
    assert edited["description"] == "Weekdays · 9:15 PM · Push notification"
    assert client.get(f"/api/schedules/{s['id']}", headers=auth).json()["time_of_day"] == "21:15"
    up = client.get(f"{base}/upcoming", headers=auth).json()
    assert len(up) == 2 and up[0]["when"]
    assert client.delete(f"/api/schedules/{s['id']}", headers=auth).status_code == 204
    assert client.get(f"/api/schedules/{s['id']}", headers=auth).status_code == 404


def test_schedule_validation(client, auth, hh):
    base = f"/api/households/{hh}/schedules"
    assert client.post(base, headers=auth, json=sched(time_of_day="25:00")).status_code == 422
    assert client.post(base, headers=auth, json=sched(title="")).status_code == 422
    assert client.post(base, headers=auth, json=sched(days=["funday"])).status_code == 422
    assert client.post(base, headers=auth, json=sched(reminder_type="Nonsense")).status_code == 422
    assert client.post(base, headers=auth, json=sched(channel="Pigeon")).status_code == 422
    assert client.get("/api/reminder-options", headers=auth).json()["types"][0] == "Usage Check-in"


def test_reminders_fire_once_per_day_and_respect_quiet_hours(client, auth, hh):
    svc = client.app_.state.services
    client.post(f"/api/households/{hh}/schedules", headers=auth, json=sched())
    at = lambda h, m: datetime.combine(date.today(), datetime.min.time()).replace(hour=h, minute=m)
    assert svc.schedules.fire_due(at(19, 59)) == []                    # not yet
    fired = svc.schedules.fire_due(at(20, 1))
    assert [a["title"] for a in fired] == ["Evening usage check-in"] and fired[0]["kind"] == "reminder"
    assert svc.schedules.fire_due(at(20, 5)) == []                     # once per day only
    items = client.get(f"/api/households/{hh}/alerts?status=all&kind=reminder", headers=auth).json()["items"]
    assert len(items) == 1 and items[0]["severity"] == "info"
    # quiet hours hold a reminder back, then it fires when they end (within the catch-up window)
    client.post(f"/api/households/{hh}/schedules", headers=auth, json=sched(title="Late", time_of_day="23:00"))
    assert svc.schedules.fire_due(at(23, 5)) == []                     # inside 22:00-06:00
    client.put(f"/api/households/{hh}/notification-settings", headers=auth, json={"quiet_start": "00:00", "quiet_end": "00:00"})
    assert [a["title"] for a in svc.schedules.fire_due(at(23, 10))] == ["Late"]


def test_disabled_and_wrong_day_schedules_do_not_fire(client, auth, hh):
    svc = client.app_.state.services
    other_day = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"][(date.today().weekday() + 1) % 7]
    client.post(f"/api/households/{hh}/schedules", headers=auth, json=sched(days=[other_day], time_of_day="08:00"))
    client.post(f"/api/households/{hh}/schedules", headers=auth, json=sched(title="Off", time_of_day="08:00", enabled=False))
    now = datetime.combine(date.today(), datetime.min.time()).replace(hour=8, minute=30)
    assert svc.schedules.fire_due(now) == []


def test_check_due_endpoint(client, auth, hh):
    r = client.post(f"/api/households/{hh}/schedules/check-due", headers=auth)
    assert r.status_code == 200 and r.json() == {"fired": []}


# -------------------------------------------------------------------- dashboard
def test_dashboard_contains_everything_the_screen_needs(client, auth, hh):
    seed_week(client, auth, hh)
    add(client, auth, hh, 96, "Garden")
    add(client, auth, hh, 138, "Showers & baths")
    client.post(f"/api/households/{hh}/schedules", headers=auth, json=sched())
    d = client.get(f"/api/households/{hh}/dashboard", headers=auth).json()
    assert d["household"]["name"] == "Maple House" and d["date"] == day()
    assert d["today"] == {"liters": 234, "limit": 500, "percent": 47, "remaining": 266, "status": "On track"}
    assert d["yesterday"]["liters"] == 140 and d["yesterday"]["difference"] == 94
    assert d["cost"] == {"today": 0.7, "currency": "$", "rate_per_1000_l": 3.0}
    assert len(d["chart"]["bars"]) == 7 and d["chart"]["bars"][-1] == {
        "date": day(), "label": "Today", "liters": 234, "is_today": True, "over_limit": False}
    assert d["chart"]["target"] == 500 and d["chart"]["mode"] == "days"
    # garden is 2.4x usual AND the household total (234 L) is 1.7x its usual 140 L
    assert d["alerts"]["open_count"] == 2
    assert {a["kind"] for a in d["alerts"]["items"]} == {"high_source", "high_total"}
    assert "Unusually high garden use" in [a["title"] for a in d["alerts"]["items"]]
    src = {i["name"]: i for i in d["sources"]["items"]}
    assert src["Garden"]["flagged"] is True and src["Showers & baths"]["flagged"] is False
    assert d["sources"]["total_liters"] == 234 and d["sources"]["connected"] == 5
    assert d["reminders"]["items"][0]["title"] == "Evening usage check-in" and d["reminders"]["next"]["when"]
    assert d["tip"]["title"].startswith("Water the roots") and d["all_tips"]
    assert d["averages"]["daily_7d"] > 0 and "week" in d and "limits" in d


def test_dashboard_periods_and_empty_state(client, auth, hh):
    empty = client.get(f"/api/households/{hh}/dashboard", headers=auth).json()
    assert empty["today"]["liters"] == 0 and empty["alerts"]["open_count"] == 0
    assert empty["chart"]["insight"].startswith("No usage recorded") and empty["tip"]["savings"] == "—"
    add(client, auth, hh, 80, "Kitchen")
    month = client.get(f"/api/households/{hh}/dashboard?period=month", headers=auth).json()["chart"]
    assert len(month["bars"]) == 30 and month["bars"][-1]["label"] == "Today"
    today = client.get(f"/api/households/{hh}/dashboard?period=day", headers=auth).json()["chart"]
    assert today["mode"] == "sources" and today["bars"][0]["label"] == "Kitchen"
    assert client.get(f"/api/households/{hh}/dashboard?period=year", headers=auth).status_code == 422
    future = (date.today() + timedelta(days=1)).isoformat()
    assert client.get(f"/api/households/{hh}/dashboard?date={future}", headers=auth).status_code == 422
    past = client.get(f"/api/households/{hh}/dashboard?date={day(5)}", headers=auth).json()
    assert past["date"] == day(5) and past["today"]["liters"] == 0


def test_dashboard_change_limit_changes_status(client, auth, hh):
    add(client, auth, hh, 300, "Showers & baths")
    assert client.get(f"/api/households/{hh}/dashboard", headers=auth).json()["today"]["status"] == "On track"
    client.put(f"/api/households/{hh}/limits", headers=auth, json={"daily_limit_liters": 320, "weekly_limit_liters": 2240})
    assert client.get(f"/api/households/{hh}/dashboard", headers=auth).json()["today"]["status"] == "Near limit"
    client.put(f"/api/households/{hh}/limits", headers=auth, json={"daily_limit_liters": 250, "weekly_limit_liters": 1750})
    d = client.get(f"/api/households/{hh}/dashboard", headers=auth).json()
    assert d["today"]["status"] == "Over limit" and d["alerts"]["items"][0]["kind"] == "limit_exceeded"


def test_export_csv(client, auth, hh):
    add(client, auth, hh, 12.5, "Kitchen", notes="dishes, big pot")
    r = client.get(f"/api/households/{hh}/export.csv", headers=auth)
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    assert "attachment" in r.headers["content-disposition"]
    lines = r.text.strip().splitlines()
    assert lines[0] == "date,source,liters,notes" and lines[1] == f'{day()},Kitchen,12.5,"dishes, big pot"'


# ----------------------------------------------------------------- meter readings
def test_meter_readings_crud_and_rules(client, auth, hh):
    base = f"/api/households/{hh}/meter-readings"
    first = client.post(base, headers=auth, json={"reading_date": day(10), "meter_reading": 100})
    assert first.status_code == 201
    client.post(base, headers=auth, json={"reading_date": day(5), "meter_reading": 102})
    backwards = client.post(base, headers=auth, json={"reading_date": day(2), "meter_reading": 90})
    assert backwards.status_code == 422 and "lower" in backwards.json()["error"]["details"][0]
    dup = client.post(base, headers=auth, json={"reading_date": day(5), "meter_reading": 103})
    assert dup.status_code == 422
    rows = client.get(base, headers=auth).json()
    assert len(rows) == 2 and rows[0]["used_m3"] == 2
    rid = rows[0]["id"]
    up = client.put(f"/api/meter-readings/{rid}", headers=auth, json={"reading_date": day(5), "meter_reading": 104, "notes": "fixed"})
    assert up.status_code == 200 and up.json()["meter_reading"] == 104
    assert client.delete(f"/api/meter-readings/{rid}", headers=auth).status_code == 204
    assert client.delete(f"/api/meter-readings/{rid}", headers=auth).status_code == 404
    assert client.post(base, headers=auth, json={"reading_date": day(), "meter_reading": -4}).status_code == 422


def test_unknown_routes_use_the_same_error_shape(client):
    r = client.get("/api/does-not-exist")
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"
