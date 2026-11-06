"""Web Push: sends alerts and reminders to the browsers/phones that turned notifications on.

* The server owns one VAPID key pair (created on first use and kept in the database; set the
  VAPID_PRIVATE_PEM / VAPID_PUBLIC_KEY environment variables to keep the same keys across
  database resets).
* Each browser registers a *subscription* (endpoint + keys) through /api/push/subscribe.
* A notification goes to every subscription of every member of the household, unless the
  household turned push off, or quiet hours are active (critical alerts ignore quiet hours).
* Sending happens in a background thread, so a slow push service never delays the request.
* Subscriptions the push service reports as gone (404/410) are deleted automatically.
"""
import base64
import json
import os
import threading
from datetime import datetime

from hydrohome import config
from hydrohome.services.schedule_service import in_quiet_hours

VAPID_CLAIM_EMAIL = os.environ.get("VAPID_CONTACT", "mailto:admin@hydrohome.local")


def _b64url(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def generate_vapid_keys():
    """Return (private_pem_text, public_key_b64url) for a new P-256 VAPID key pair."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    key = ec.generate_private_key(ec.SECP256R1())
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                            serialization.NoEncryption()).decode()
    public = key.public_key().public_bytes(serialization.Encoding.X962,
                                           serialization.PublicFormat.UncompressedPoint)
    return pem, _b64url(public)


def _default_sender(subscription, payload, private_pem):
    from pywebpush import webpush
    from py_vapid import Vapid
    webpush(subscription_info=subscription, data=payload,
            vapid_private_key=Vapid.from_pem(private_pem.encode()),
            vapid_claims={"sub": VAPID_CLAIM_EMAIL}, ttl=3600)


class PushService:
    def __init__(self, repo, settings, sender=None, background=True):
        self.repo, self.settings = repo, settings
        self._sender = sender or _default_sender
        self._background = background
        self._keys = None
        self._lock = threading.Lock()

    # -- keys -------------------------------------------------------------------
    def keys(self):
        with self._lock:
            if self._keys:
                return self._keys
            pem, pub = os.environ.get("VAPID_PRIVATE_PEM"), os.environ.get("VAPID_PUBLIC_KEY")
            if pem and pub:
                self._keys = (pem.replace("\\n", "\n"), pub)
                return self._keys
            pem, pub = self.repo.get_secret("vapid_private_pem"), self.repo.get_secret("vapid_public")
            if not (pem and pub):
                pem, pub = generate_vapid_keys()
                self.repo.set_secret("vapid_private_pem", pem)
                self.repo.set_secret("vapid_public", pub)
            self._keys = (pem, pub)
            return self._keys

    def public_key(self):
        return self.keys()[1]

    # -- subscriptions ----------------------------------------------------------
    def subscribe(self, user_id, endpoint, p256dh, auth):
        self.repo.upsert(user_id, endpoint, p256dh, auth)

    def unsubscribe(self, endpoint):
        self.repo.remove(endpoint)

    # -- sending ----------------------------------------------------------------
    def notify_alert(self, alert, now=None):
        """Push one alert row (an info alert is a reminder) to the household's devices."""
        hid = alert["household_id"]
        prefs = self.settings.get_notifications(hid)
        if not prefs["push_enabled"]:
            return 0
        now = now or datetime.now()
        if alert["severity"] != "critical" and in_quiet_hours(
                now.strftime(config.TIME_FMT), prefs["quiet_start"], prefs["quiet_end"]):
            return 0
        subs = self.repo.for_household(hid)
        if not subs:
            return 0
        payload = json.dumps({"id": alert["id"], "title": alert["title"], "body": alert["message"],
                              "severity": alert["severity"], "kind": alert["kind"],
                              "url": "/#/alerts"})
        if self._background:
            threading.Thread(target=self._send_all, args=(subs, payload), daemon=True).start()
        else:
            self._send_all(subs, payload)
        return len(subs)

    def notify_reminder(self, alert, schedule):
        return self.notify_alert(alert)

    def _send_all(self, subs, payload):
        private_pem = self.keys()[0]
        for sub in subs:
            info = {"endpoint": sub["endpoint"], "keys": {"p256dh": sub["p256dh"], "auth": sub["auth"]}}
            try:
                self._sender(info, payload, private_pem)
            except Exception as exc:
                status = getattr(getattr(exc, "response", None), "status_code", None)
                if status in (404, 410):
                    self.repo.remove(sub["endpoint"])
                else:
                    print("Push failed:", exc)
