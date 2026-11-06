from datetime import date, timedelta
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query

from hydrohome.api.deps import current_user, get_services, household_access, usage_access
from hydrohome.api.schemas import UsageIn, UsageUpdate

router = APIRouter(prefix="/api", tags=["Usage"])


def _rescan(svc, household_id, *days):
    """Re-run high-usage detection for the affected days; return today's active alerts."""
    found = []
    for day in dict.fromkeys(days):
        found += svc.alerts.evaluate(household_id, day)
    return [svc.alerts.alert_out(a) for a in found]


@router.post("/households/{household_id}/usage", status_code=201,
             summary="Record water consumption for a day and source")
def record_usage(body: UsageIn, household_id: int = Depends(household_access),
                 user=Depends(current_user), svc=Depends(get_services)):
    entry = svc.usage.record(household_id, body.usage_date, body.liters, body.source_id,
                             body.source, body.notes, user["id"])
    return {"entry": entry, "alerts_triggered": _rescan(svc, household_id, body.usage_date)}


@router.get("/households/{household_id}/usage", summary="List usage entries (newest first)")
def list_usage(household_id: int = Depends(household_access), svc=Depends(get_services),
               start: Optional[date] = None, end: Optional[date] = None,
               source_id: Optional[int] = Query(default=None, ge=1),
               limit: int = Query(default=50, ge=1, le=500), offset: int = Query(default=0, ge=0)):
    return svc.usage.list_entries(household_id, start, end, source_id, limit, offset)


@router.get("/usage/{usage_id}", summary="One usage entry")
def get_usage(usage_id: int = Depends(usage_access), svc=Depends(get_services)):
    return svc.usage.entry_out(svc.usage.get(usage_id))


@router.put("/usage/{usage_id}", summary="Edit a usage entry")
def update_usage(body: UsageUpdate, usage_id: int = Depends(usage_access),
                 svc=Depends(get_services)):
    old = svc.usage.get(usage_id)
    entry = svc.usage.update(usage_id, body.usage_date, body.liters, body.source_id, body.source,
                             body.notes)
    days = [date.fromisoformat(old["usage_date"]), date.fromisoformat(entry["usage_date"])]
    return {"entry": entry, "alerts_triggered": _rescan(svc, old["household_id"], *days)}


@router.delete("/usage/{usage_id}", status_code=204, summary="Delete a usage entry")
def delete_usage(usage_id: int = Depends(usage_access), svc=Depends(get_services)):
    old = svc.usage.get(usage_id)
    svc.usage.delete(usage_id)
    _rescan(svc, old["household_id"], date.fromisoformat(old["usage_date"]))


@router.get("/households/{household_id}/usage/summary",
            summary="Daily total, week-to-date total and average usage")
def usage_summary(household_id: int = Depends(household_access), svc=Depends(get_services),
                  date_: Optional[date] = Query(default=None, alias="date")):
    return svc.usage.summary(household_id, date_)


@router.get("/households/{household_id}/usage/daily",
            summary="Zero-filled daily totals for a date range (default: last 7 days)")
def usage_daily(household_id: int = Depends(household_access), svc=Depends(get_services),
                start: Optional[date] = None, end: Optional[date] = None):
    end = end or date.today()
    return {"start": (start or end - timedelta(days=6)).isoformat(), "end": end.isoformat(),
            "days": svc.usage.daily_series(household_id, start or end - timedelta(days=6), end)}


@router.get("/households/{household_id}/usage/by-source",
            summary="Where the water goes: totals per source")
def usage_by_source(household_id: int = Depends(household_access), svc=Depends(get_services),
                    period: Literal["today", "week", "month"] = "today",
                    date_: Optional[date] = Query(default=None, alias="date")):
    return svc.usage.by_source(household_id, period, date_)


@router.get("/households/{household_id}/history",
            summary="Consumption history: daily totals with per-source breakdown")
def history(household_id: int = Depends(household_access), svc=Depends(get_services),
            start: Optional[date] = None, end: Optional[date] = None,
            days: int = Query(default=30, ge=1, le=400)):
    end = end or date.today()
    start = start or end - timedelta(days=days - 1)
    if start > end:
        from hydrohome.errors import ValidationError
        raise ValidationError("start must not be after end.")
    return svc.usage.history(household_id, start, end)
