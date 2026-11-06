"""Wires the web services together. Reuses your existing build_services() so the desktop
app and the API share the same database and business rules."""
from dataclasses import dataclass
from pathlib import Path

from hydrohome.container import Services, build_services
from hydrohome.database import web_repositories as wr
from hydrohome.services.alert_service import AlertService
from hydrohome.services.auth_service import AuthService
from hydrohome.services.dashboard_service import DashboardService
from hydrohome.services.push_service import PushService
from hydrohome.services.schedule_service import ScheduleService
from hydrohome.services.settings_service import SettingsService
from hydrohome.services.usage_service import UsageService


@dataclass
class WebServices:
    base: Services           # existing desktop services (households, readings, ...)
    memberships: wr.MembershipRepository
    auth: AuthService
    settings: SettingsService
    usage: UsageService
    alerts: AlertService
    schedules: ScheduleService
    dashboard: DashboardService
    push: PushService
    db_path: Path | None


def build_web_services(db_path=None):
    base = build_services(db_path)          # also creates every table (old + new)
    households_repo = base.households.repo
    users, tokens, members = wr.UserRepository(db_path), wr.TokenRepository(db_path), \
        wr.MembershipRepository(db_path)
    sources, usage_repo = wr.WaterSourceRepository(db_path), wr.UsageRepository(db_path)
    settings = SettingsService(households_repo, wr.LimitRepository(db_path),
                               wr.NotificationSettingsRepository(db_path), sources)
    usage = UsageService(usage_repo, sources, households_repo, settings)
    push = PushService(wr.PushRepository(db_path), settings)
    alerts = AlertService(wr.AlertRepository(db_path), usage_repo, sources, settings,
                          on_alert=push.notify_alert)
    schedules = ScheduleService(wr.ScheduleRepository(db_path), wr.AlertRepository(db_path),
                                settings, on_fire=push.notify_reminder)
    dashboard = DashboardService(households_repo, usage, alerts, schedules, settings)
    return WebServices(base=base, memberships=members,
                       auth=AuthService(users, tokens, members), settings=settings,
                       usage=usage, alerts=alerts, schedules=schedules, dashboard=dashboard, push=push,
                       db_path=db_path)
