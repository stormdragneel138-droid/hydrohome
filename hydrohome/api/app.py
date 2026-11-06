"""FastAPI application factory.

    uvicorn hydrohome.api.app:app --reload          (or just:  python run_api.py)

* REST API:        /api/...      (interactive docs at /docs and /redoc)
* Web dashboard:   /             (static files from hydrohome/web)
"""
import asyncio
import contextlib
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from hydrohome.api.container import build_web_services
from hydrohome.api.errors import install_error_handlers
from hydrohome.api.routers import alerts, auth, dashboard, households, meter, push, schedules, usage

WEB_DIR = Path(__file__).resolve().parent.parent / "web"
REMINDER_CHECK_SECONDS = 30

TAGS = [
    {"name": "System", "description": "Health check."},
    {"name": "Auth", "description": "Accounts and sign-in (bearer token)."},
    {"name": "Households", "description": "Households you belong to."},
    {"name": "Limits", "description": "Consumption limits and notification preferences."},
    {"name": "Sources", "description": "Water sources / sensors."},
    {"name": "Usage", "description": "Record and read daily water consumption."},
    {"name": "Alerts", "description": "High-usage alerts and notifications."},
    {"name": "Reminders", "description": "Scheduled water-saving reminders."},
    {"name": "Dashboard", "description": "Dashboard statistics and CSV export."},
    {"name": "Push", "description": "Browser push notifications for alerts and reminders."},
    {"name": "Meter readings", "description": "Cumulative meter readings from the desktop app."},
]


def create_app(db_path=None, start_scheduler=True):
    services = build_web_services(db_path)

    @contextlib.asynccontextmanager
    async def lifespan(app):
        task = None
        if start_scheduler:
            async def loop():
                while True:
                    try:
                        await asyncio.to_thread(services.schedules.fire_due)
                    except Exception as exc:          # never let the loop die
                        print("Reminder check failed:", exc)
                    await asyncio.sleep(REMINDER_CHECK_SECONDS)
            task = asyncio.create_task(loop())
        yield
        if task:
            task.cancel()

    app = FastAPI(title="HydroHome API", version="1.0.0", openapi_tags=TAGS, lifespan=lifespan,
                  description="Household Water Consumption Reminder System: record usage, "
                              "monitor limits, detect high consumption and schedule reminders.")
    app.state.services = services
    install_error_handlers(app)
    for module in (dashboard, auth, households, usage, alerts, schedules, meter, push):
        app.include_router(module.router)

    if WEB_DIR.is_dir():
        @app.get("/", include_in_schema=False)
        def index():
            return FileResponse(WEB_DIR / "index.html")

        app.mount("/", StaticFiles(directory=WEB_DIR), name="web")
    return app


def __getattr__(name):
    """`uvicorn hydrohome.api.app:app` builds the app lazily (using data/hydrohome.db)."""
    if name == "app":
        return create_app()
    raise AttributeError(name)
