from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query

from hydrohome.api.deps import alert_access, get_services, household_access
from hydrohome.api.schemas import AlertStatusIn, FlowIn

router = APIRouter(prefix="/api", tags=["Alerts"])


@router.get("/households/{household_id}/alerts",
            summary="List alerts and notifications (open ones first by severity)")
def list_alerts(household_id: int = Depends(household_access), svc=Depends(get_services),
                status: str = Query(default="open", description="open, acknowledged, dismissed, "
                                    "resolved, active (open+acknowledged) or all"),
                kind: Optional[str] = None, limit: int = Query(default=50, ge=1, le=200)):
    return {"counts": svc.alerts.counts(household_id),
            "items": svc.alerts.list(household_id, status, kind, limit)}


@router.post("/households/{household_id}/alerts/scan",
             summary="Check a day's usage for unusually high consumption")
def scan(household_id: int = Depends(household_access), svc=Depends(get_services),
         date_: Optional[date] = Query(default=None, alias="date")):
    found = svc.alerts.evaluate(household_id, date_ or date.today())
    return {"date": (date_ or date.today()).isoformat(),
            "alerts": [svc.alerts.alert_out(a) for a in found]}


@router.post("/households/{household_id}/flow-events",
             summary="Report continuous water flow (smart-meter style leak check)")
def flow_event(body: FlowIn, household_id: int = Depends(household_access),
               svc=Depends(get_services)):
    row = svc.alerts.check_flow(household_id, body.flow_lpm, body.minutes)
    return {"detected": row is not None,
            "alert": svc.alerts.alert_out(row) if row else None}


@router.post("/households/{household_id}/alerts/mark-read", summary="Mark all as read")
def mark_read(household_id: int = Depends(household_access), svc=Depends(get_services)):
    return {"marked": svc.alerts.mark_all_read(household_id)}


@router.get("/alerts/{alert_id}", summary="One alert")
def get_alert(alert_id: int = Depends(alert_access), svc=Depends(get_services)):
    return svc.alerts.alert_out(svc.alerts.get(alert_id))


@router.put("/alerts/{alert_id}", summary="Acknowledge, dismiss, resolve or reopen an alert")
def set_alert_status(body: AlertStatusIn, alert_id: int = Depends(alert_access),
                     svc=Depends(get_services)):
    return svc.alerts.set_status(alert_id, body.status)


@router.delete("/alerts/{alert_id}", status_code=204, summary="Delete an alert")
def delete_alert(alert_id: int = Depends(alert_access), svc=Depends(get_services)):
    svc.alerts.delete(alert_id)
