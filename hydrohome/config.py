"""Application-wide constants (single place to change behaviour)."""
from pathlib import Path

APP_NAME = "HydroHome"
APP_SUBTITLE = "Household Water Consumption Reminder System"

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
EXPORT_DIR = BASE_DIR / "exports"
DB_PATH = DATA_DIR / "hydrohome.db"

# External REST API: Open-Meteo (free, no API key). Docs: https://open-meteo.com/en/docs
GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
API_TIMEOUT_SECONDS = 8
FORECAST_DAYS = 3

# Reminder engine
REMINDER_CHECK_MS = 30_000          # how often the app looks for due reminders
REMINDER_TYPES = ("Meter Reading", "Bill Payment", "Leak Check",
                  "Garden Watering", "Conservation Tip", "Other")
REPEAT_RULES = ("None", "Daily", "Weekly", "Monthly")
STATUS_PENDING = "Pending"
STATUS_DONE = "Done"

# Consumption thresholds
DEFAULT_TARGET_LITERS = 100         # litres / person / day (editable per household)
NEAR_LIMIT_RATIO = 0.90
HOT_DAY_CELSIUS = 33.0
HEAVY_RAIN_MM = 5.0
HIGH_RAIN_PROBABILITY = 70

# Dashboard auto-update
DASHBOARD_REFRESH_MS = 10_000       # dashboard re-reads the database this often
WEATHER_REFRESH_SECONDS = 1800      # forecast is re-fetched automatically after 30 minutes
WEATHER_RETRY_SECONDS = 120         # after a failed fetch, wait before trying again

# Smart meter auto-sync
SYNC_CHECK_MS = 60_000              # how often the app checks which sources are due
METER_SOURCE_TYPES = ("URL", "FILE")
METER_UNITS = ("m3", "liters")

DATE_FMT = "%Y-%m-%d"
TIME_FMT = "%H:%M"
DATETIME_FMT = "%Y-%m-%d %H:%M"
