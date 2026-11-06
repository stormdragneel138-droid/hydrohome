from datetime import date, timedelta
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response

from hydrohome.api.deps import get_services, household_access

router = APIRouter(prefix="/api", tags=["Dashboard"])


@router.get("/health", tags=["System"], summary="Is the API running?")
def health():
    return {"status": "ok", "time": date.today().isoformat()}


@router.get("/households/{household_id}/dashboard",
            summary="Everything the dashboard shows, in one response")
def dashboard(household_id: int = Depends(household_access), svc=Depends(get_services),
              period: Literal["day", "week", "month"] = "week",
              source_period: Literal["today", "week", "month"] = "today",
              date_: Optional[date] = Query(default=None, alias="date")):
    return svc.dashboard.build(household_id, period, date_, source_period)


@router.get("/households/{household_id}/export.csv", summary="Download usage entries as CSV")
def export_csv(household_id: int = Depends(household_access), svc=Depends(get_services),
               start: Optional[date] = None, end: Optional[date] = None):
    end = end or date.today()
    start = start or end - timedelta(days=89)
    text = svc.dashboard.export_csv(household_id, start, end)
    name = f"water-usage-{start.isoformat()}-to-{end.isoformat()}.csv"
    return Response(text, media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})
