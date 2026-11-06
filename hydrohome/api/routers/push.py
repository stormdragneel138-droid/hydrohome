from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from hydrohome.api.deps import current_user, get_services

router = APIRouter(prefix="/api/push", tags=["Push"])


class SubscriptionKeys(BaseModel):
    p256dh: str = Field(min_length=1, max_length=300)
    auth: str = Field(min_length=1, max_length=100)


class SubscriptionIn(BaseModel):
    endpoint: str = Field(min_length=10, max_length=1000)
    keys: SubscriptionKeys


class EndpointIn(BaseModel):
    endpoint: str = Field(min_length=10, max_length=1000)


@router.get("/key", summary="The server's public VAPID key (needed by the browser to subscribe)")
def public_key(svc=Depends(get_services)):
    return {"public_key": svc.push.public_key()}


@router.post("/subscribe", status_code=204, summary="Register this browser for push notifications")
def subscribe(body: SubscriptionIn, user=Depends(current_user), svc=Depends(get_services)):
    svc.push.subscribe(user["id"], body.endpoint, body.keys.p256dh, body.keys.auth)


@router.post("/unsubscribe", status_code=204, summary="Stop push notifications on this browser")
def unsubscribe(body: EndpointIn, _=Depends(current_user), svc=Depends(get_services)):
    svc.push.unsubscribe(body.endpoint)


@router.post("/test", summary="Send yourself a test notification")
def test(user=Depends(current_user), svc=Depends(get_services)):
    households = svc.memberships.households_for_user(user["id"])
    sent = 0
    for h in households[:1]:
        hid = h["id"] if isinstance(h, dict) else h
        sent += svc.push.notify_alert({"id": 0, "household_id": hid, "title": "HydroHome test",
                                       "message": "Push notifications are working.",
                                       "severity": "critical", "kind": "test"})
    return {"sent": sent}
