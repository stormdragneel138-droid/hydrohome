"""Shared FastAPI dependencies: services, the signed-in user, and household access checks."""
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from hydrohome.errors import AuthError, NotFoundError

bearer = HTTPBearer(auto_error=False, description="Token returned by /api/auth/login")


def get_services(request: Request):
    return request.app.state.services


def current_token(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AuthError("Sign in first (missing Authorization: Bearer token).")
    return credentials.credentials


def current_user(token: str = Depends(current_token), svc=Depends(get_services)):
    return svc.auth.user_for_token(token)


def household_access(household_id: int, user=Depends(current_user), svc=Depends(get_services)):
    """Path dependency: the household must exist AND belong to the signed-in user.
    Other people's households answer 404, so their existence is not revealed."""
    if svc.memberships.role_of(household_id, user["id"]) is None \
            or svc.base.households.get(household_id) is None:
        raise NotFoundError("Household not found.")
    return household_id


def _owned(svc, user, household_id):
    if svc.memberships.role_of(household_id, user["id"]) is None:
        raise NotFoundError("Not found.")


def usage_access(usage_id: int, user=Depends(current_user), svc=Depends(get_services)):
    row = svc.usage.get(usage_id)
    _owned(svc, user, row["household_id"])
    return usage_id


def alert_access(alert_id: int, user=Depends(current_user), svc=Depends(get_services)):
    row = svc.alerts.get(alert_id)
    _owned(svc, user, row["household_id"])
    return alert_id


def schedule_access(schedule_id: int, user=Depends(current_user), svc=Depends(get_services)):
    row = svc.schedules.get(schedule_id)
    _owned(svc, user, row["household_id"])
    return schedule_id


def source_access(source_id: int, user=Depends(current_user), svc=Depends(get_services)):
    row = svc.settings.get_source(source_id)
    _owned(svc, user, row["household_id"])
    return source_id
