"""Push notifications: subscriptions, alert/reminder delivery, quiet hours, dead endpoints."""
import json
from datetime import datetime

import pytest

from hydrohome.api.container import build_web_services
from hydrohome.services.push_service import PushService, generate_vapid_keys


@pytest.fixture()
def env(tmp_path):
    svc = build_web_services(tmp_path / "t.db")
    sent = []
    svc.push._sender = lambda sub, payload, pem: sent.append((sub, json.loads(payload)))
    svc.push._background = False
    user, _ = svc.auth.register("Ann", "ann@example.com", "password123")
    hid = svc.base.households.add({"name": "Home", "address": "", "city": "Manila",
                                   "members": 3, "daily_target_liters": 100})
    svc.memberships.link(hid, user["id"], "admin")
    svc.settings.ensure_defaults(hid)
    hh = hid
    return svc, sent, user, hh


def _household(svc, user):
    return svc.memberships.households_for_user(user["id"])[0]["id"]


def test_vapid_keys_are_generated_once_and_reused(tmp_path):
    svc = build_web_services(tmp_path / "k.db")
    first = svc.push.public_key()
    assert len(first) > 80
    assert build_web_services(tmp_path / "k.db").push.public_key() == first
    pem, pub = generate_vapid_keys()
    assert pem.startswith("-----BEGIN PRIVATE KEY-----") and pub


def test_alert_is_pushed_to_member_devices(env):
    svc, sent, user, _ = env
    hid = _household(svc, user)
    svc.push.subscribe(user["id"], "https://push.example/abc", "p256", "authkey")
    svc.alerts.check_flow(hid, 2.0, 30)
    assert len(sent) == 1
    sub, payload = sent[0]
    assert sub["endpoint"] == "https://push.example/abc"
    assert payload["kind"] == "continuous_flow" and "Water running" in payload["title"]
    svc.alerts.check_flow(hid, 2.0, 35)           # same open alert refreshed: no second push
    assert len(sent) == 1


def test_dead_subscription_is_removed(env):
    svc, sent, user, _ = env
    hid = _household(svc, user)

    class Gone(Exception):
        response = type("R", (), {"status_code": 410})()

    def boom(*a):
        raise Gone()
    svc.push._sender = boom
    svc.push.subscribe(user["id"], "https://push.example/dead", "p", "a")
    svc.alerts.check_flow(hid, 2.0, 30)
    assert svc.push.repo.for_household(hid) == []


def test_push_off_and_quiet_hours(env):
    svc, sent, user, _ = env
    hid = _household(svc, user)
    svc.push.subscribe(user["id"], "https://push.example/q", "p", "a")
    warn = {"id": 1, "household_id": hid, "title": "t", "message": "m", "severity": "warning", "kind": "x"}
    svc.settings.get_notifications(hid)
    assert svc.push.notify_alert(warn, now=datetime(2026, 1, 1, 23, 30)) == 0     # quiet hours
    assert svc.push.notify_alert({**warn, "severity": "critical"}, now=datetime(2026, 1, 1, 23, 30)) == 1
    assert svc.push.notify_alert(warn, now=datetime(2026, 1, 1, 12, 0)) == 1
