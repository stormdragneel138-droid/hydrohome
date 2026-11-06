"""Meter readings recorded by the desktop app (cumulative m³ values)."""
from fastapi import APIRouter, Depends

from hydrohome.api.deps import current_user, get_services, household_access
from hydrohome.api.schemas import MeterReadingIn
from hydrohome.errors import NotFoundError

router = APIRouter(prefix="/api", tags=["Meter readings"])


def _owned_reading(reading_id, user, svc):
    row = svc.base.readings.readings.get(reading_id)
    if not row or svc.memberships.role_of(row["household_id"], user["id"]) is None:
        raise NotFoundError("Meter reading not found.")
    return row


def _form(household_id, body):
    return {"household_id": household_id, "reading_date": body.reading_date.isoformat(),
            "meter_reading": body.meter_reading, "notes": body.notes}


@router.get("/households/{household_id}/meter-readings",
            summary="Meter readings with usage since the previous reading")
def list_readings(household_id: int = Depends(household_access), svc=Depends(get_services)):
    return svc.base.readings.list_with_usage(household_id)


@router.post("/households/{household_id}/meter-readings", status_code=201,
             summary="Add a meter reading (the meter can never run backwards)")
def add_reading(body: MeterReadingIn, household_id: int = Depends(household_access),
                svc=Depends(get_services)):
    rid = svc.base.readings.add(_form(household_id, body))
    return svc.base.readings.readings.get(rid)


@router.put("/meter-readings/{reading_id}", summary="Edit a meter reading")
def update_reading(reading_id: int, body: MeterReadingIn, user=Depends(current_user),
                   svc=Depends(get_services)):
    row = _owned_reading(reading_id, user, svc)
    svc.base.readings.update(reading_id, _form(row["household_id"], body))
    return svc.base.readings.readings.get(reading_id)


@router.delete("/meter-readings/{reading_id}", status_code=204, summary="Delete a meter reading")
def delete_reading(reading_id: int, user=Depends(current_user), svc=Depends(get_services)):
    _owned_reading(reading_id, user, svc)
    svc.base.readings.delete(reading_id)
