from datetime import date

from fastapi import APIRouter, Depends

from hydrohome.api.deps import (current_user, get_services, household_access, source_access)
from hydrohome.api.schemas import (HouseholdIn, HouseholdUpdate, LimitsIn,
                                   NotificationSettingsIn, SourceIn, SourceUpdate)
from hydrohome.errors import NotFoundError

router = APIRouter(prefix="/api", tags=["Households"])


def household_out(row, role=None):
    return {"id": row["id"], "name": row["name"], "address": row["address"], "city": row["city"],
            "members": row["members"], "daily_target_liters": row["daily_target_liters"],
            "created_at": row["created_at"], "role": role}


@router.get("/households", summary="Households you belong to")
def list_households(user=Depends(current_user), svc=Depends(get_services)):
    return [household_out(r, r["role"]) for r in svc.memberships.households_for_user(user["id"])]


@router.post("/households", status_code=201, summary="Create a household")
def create_household(body: HouseholdIn, user=Depends(current_user), svc=Depends(get_services)):
    target, limit = body.daily_target_liters, body.daily_limit_liters
    if limit is not None:
        target = min(500, max(20, round(limit / body.members)))
    hid = svc.base.households.add({"name": body.name, "address": body.address, "city": body.city,
                                   "members": body.members, "daily_target_liters": target})
    svc.memberships.link(hid, user["id"], "admin")
    svc.settings.ensure_defaults(hid)
    if limit is not None:
        svc.settings.update_limits(hid, {"daily_limit_liters": limit,
                                         "weekly_limit_liters": limit * 7})
    return household_out(svc.base.households.get(hid), "admin")


@router.get("/households/unclaimed", summary="Households (e.g. made in the desktop app) with no owner")
def unclaimed(user=Depends(current_user), svc=Depends(get_services)):
    return [household_out(r) for r in svc.memberships.unowned_households()]


@router.post("/households/{household_id}/claim", summary="Become the admin of an unowned household")
def claim(household_id: int, user=Depends(current_user), svc=Depends(get_services)):
    if not any(h["id"] == household_id for h in svc.memberships.unowned_households()):
        raise NotFoundError("That household does not exist or already has an owner.")
    svc.memberships.link(household_id, user["id"], "admin")
    svc.settings.ensure_defaults(household_id)
    return household_out(svc.base.households.get(household_id), "admin")


@router.get("/households/{household_id}", summary="One household with its limits")
def get_household(household_id: int = Depends(household_access), user=Depends(current_user),
                  svc=Depends(get_services)):
    data = household_out(svc.base.households.get(household_id),
                         svc.memberships.role_of(household_id, user["id"]))
    data["limits"] = svc.settings.get_limits(household_id)
    return data


@router.put("/households/{household_id}", summary="Update household details")
def update_household(body: HouseholdUpdate, household_id: int = Depends(household_access),
                     user=Depends(current_user), svc=Depends(get_services)):
    current = svc.base.households.get(household_id)
    merged = {k: (getattr(body, k) if getattr(body, k) is not None else current[k])
              for k in ("name", "address", "city", "members", "daily_target_liters")}
    svc.base.households.update(household_id, merged)
    return household_out(svc.base.households.get(household_id),
                         svc.memberships.role_of(household_id, user["id"]))


@router.delete("/households/{household_id}", status_code=204,
               summary="Delete a household and all its data")
def delete_household(household_id: int = Depends(household_access), svc=Depends(get_services)):
    svc.base.households.delete(household_id)


# ---- consumption limits -----------------------------------------------------
@router.get("/households/{household_id}/limits", tags=["Limits"], summary="Consumption limits")
def get_limits(household_id: int = Depends(household_access), svc=Depends(get_services)):
    return svc.settings.get_limits(household_id)


@router.put("/households/{household_id}/limits", tags=["Limits"],
            summary="Update daily/weekly limits, alert threshold and water rate")
def put_limits(body: LimitsIn, household_id: int = Depends(household_access),
               svc=Depends(get_services)):
    return svc.settings.update_limits(household_id, body.model_dump())


# ---- notification preferences -------------------------------------------------
@router.get("/households/{household_id}/notification-settings", tags=["Limits"],
            summary="Push/email preferences and quiet hours")
def get_notification_settings(household_id: int = Depends(household_access),
                              svc=Depends(get_services)):
    return svc.settings.get_notifications(household_id)


@router.put("/households/{household_id}/notification-settings", tags=["Limits"],
            summary="Update push/email preferences and quiet hours")
def put_notification_settings(body: NotificationSettingsIn,
                              household_id: int = Depends(household_access),
                              svc=Depends(get_services)):
    return svc.settings.update_notifications(household_id, body.model_dump())


# ---- water sources (devices) --------------------------------------------------
@router.get("/households/{household_id}/sources", tags=["Sources"],
            summary="Water sources / sensors (showers, garden, ...)")
def list_sources(household_id: int = Depends(household_access), svc=Depends(get_services)):
    sources = svc.settings.list_sources(household_id)
    today = svc.usage.by_source(household_id, "today", date.today())["items"]
    liters = {i["source_id"]: i["liters"] for i in today}
    for s in sources:
        s["today_liters"] = liters.get(s["id"], 0.0)
    return sources


@router.post("/households/{household_id}/sources", status_code=201, tags=["Sources"],
             summary="Add a water source")
def add_source(body: SourceIn, household_id: int = Depends(household_access),
               svc=Depends(get_services)):
    return svc.settings.add_source(household_id, body.model_dump())


@router.put("/sources/{source_id}", tags=["Sources"], summary="Rename, recolor, enable or disable")
def update_source(body: SourceUpdate, source_id: int = Depends(source_access),
                  svc=Depends(get_services)):
    return svc.settings.update_source(source_id, body.model_dump())


@router.delete("/sources/{source_id}", status_code=204, tags=["Sources"],
               summary="Delete a source that has no usage entries")
def delete_source(source_id: int = Depends(source_access), svc=Depends(get_services)):
    svc.settings.delete_source(source_id)


