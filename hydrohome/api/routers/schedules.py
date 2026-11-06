from fastapi import APIRouter, Depends

from hydrohome.api.deps import get_services, household_access, schedule_access
from hydrohome.api.schemas import ScheduleIn, ScheduleUpdate
from hydrohome.services.schedule_service import CHANNELS, SCHEDULE_TYPES

router = APIRouter(prefix="/api", tags=["Reminders"])


@router.get("/reminder-options", summary="Allowed reminder types and delivery channels")
def options():
    return {"types": list(SCHEDULE_TYPES), "channels": list(CHANNELS),
            "days": ["daily", "weekdays", "weekends", "mon", "tue", "wed", "thu", "fri", "sat",
                     "sun"]}


@router.get("/households/{household_id}/schedules", summary="Reminder schedules")
def list_schedules(household_id: int = Depends(household_access), svc=Depends(get_services)):
    return svc.schedules.list(household_id)


@router.post("/households/{household_id}/schedules", status_code=201,
             summary="Schedule a water-saving reminder")
def add_schedule(body: ScheduleIn, household_id: int = Depends(household_access),
                 svc=Depends(get_services)):
    return svc.schedules.add(household_id, body.model_dump())


@router.get("/households/{household_id}/schedules/upcoming", summary="Next reminders to fire")
def upcoming(household_id: int = Depends(household_access), svc=Depends(get_services)):
    return svc.schedules.upcoming(household_id, 5)


@router.post("/households/{household_id}/schedules/check-due",
             summary="Fire any reminders that are due right now")
def check_due(household_id: int = Depends(household_access), svc=Depends(get_services)):
    fired = svc.schedules.fire_due(household_ids={household_id})
    return {"fired": [svc.alerts.alert_out(a) for a in fired]}


@router.get("/schedules/{schedule_id}", summary="One reminder schedule")
def get_schedule(schedule_id: int = Depends(schedule_access), svc=Depends(get_services)):
    return svc.schedules.schedule_out(svc.schedules.get(schedule_id))


@router.put("/schedules/{schedule_id}", summary="Edit a schedule or switch it on/off")
def update_schedule(body: ScheduleUpdate, schedule_id: int = Depends(schedule_access),
                    svc=Depends(get_services)):
    return svc.schedules.update(schedule_id, body.model_dump())


@router.delete("/schedules/{schedule_id}", status_code=204, summary="Delete a schedule")
def delete_schedule(schedule_id: int = Depends(schedule_access), svc=Depends(get_services)):
    svc.schedules.delete(schedule_id)
