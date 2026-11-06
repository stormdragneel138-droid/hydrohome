"""Request bodies. Pydantic checks types and ranges before any service code runs."""
from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class _Body(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


# ---- auth -------------------------------------------------------------------
class RegisterIn(_Body):
    name: str = Field(min_length=1, max_length=60, examples=["Jamie Lewis"])
    email: str = Field(min_length=3, max_length=120, examples=["jamie@example.com"])
    password: str = Field(min_length=8, max_length=128, examples=["a-strong-password"])


class LoginIn(_Body):
    email: str = Field(min_length=3, max_length=120)
    password: str = Field(min_length=1, max_length=128)


class ProfileIn(_Body):
    name: str = Field(min_length=1, max_length=60)


class PasswordIn(_Body):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


# ---- households -------------------------------------------------------------
class HouseholdIn(_Body):
    name: str = Field(min_length=1, max_length=60, examples=["Maple House"])
    address: str = Field(default="", max_length=120)
    city: str = Field(min_length=1, max_length=60, examples=["Tarlac City"])
    members: int = Field(ge=1, le=30, examples=[4])
    daily_target_liters: int = Field(default=100, ge=20, le=500,
                                     description="Litres per person per day (desktop-app target)")
    daily_limit_liters: Optional[float] = Field(default=None, gt=0, le=100000,
                                                description="Household daily limit; defaults to "
                                                            "members x daily_target_liters")


class HouseholdUpdate(_Body):
    name: Optional[str] = Field(default=None, min_length=1, max_length=60)
    address: Optional[str] = Field(default=None, max_length=120)
    city: Optional[str] = Field(default=None, min_length=1, max_length=60)
    members: Optional[int] = Field(default=None, ge=1, le=30)
    daily_target_liters: Optional[int] = Field(default=None, ge=20, le=500)


class LimitsIn(_Body):
    daily_limit_liters: Optional[float] = Field(default=None, gt=0, le=100000, examples=[500])
    weekly_limit_liters: Optional[float] = Field(default=None, gt=0, le=700000, examples=[3500])
    alert_threshold_pct: Optional[int] = Field(default=None, ge=50, le=100, examples=[90])
    spike_multiplier: Optional[float] = Field(default=None, ge=1.1, le=10, examples=[1.5])
    rate_per_1000_l: Optional[float] = Field(default=None, ge=0, le=10000, examples=[3.0])
    currency: Optional[str] = Field(default=None, min_length=1, max_length=3, examples=["$"])


class NotificationSettingsIn(_Body):
    push_enabled: Optional[bool] = None
    email_enabled: Optional[bool] = None
    quiet_start: Optional[str] = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$",
                                       examples=["22:00"])
    quiet_end: Optional[str] = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$",
                                     examples=["06:00"])


class SourceIn(_Body):
    name: str = Field(min_length=1, max_length=40, examples=["Pool"])
    color: Optional[str] = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$", examples=["#267e78"])
    enabled: bool = True


class SourceUpdate(_Body):
    name: Optional[str] = Field(default=None, min_length=1, max_length=40)
    color: Optional[str] = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    enabled: Optional[bool] = None


# ---- usage ------------------------------------------------------------------
class UsageIn(_Body):
    usage_date: date = Field(examples=["2026-11-05"])
    liters: float = Field(ge=0, le=100000, examples=[138])
    source_id: Optional[int] = Field(default=None, ge=1)
    source: Optional[str] = Field(default=None, max_length=40, examples=["Showers & baths"],
                                  description="Source name (alternative to source_id)")
    notes: str = Field(default="", max_length=200)

    @field_validator("liters")
    @classmethod
    def _finite(cls, v):
        if v != v or v in (float("inf"), float("-inf")):
            raise ValueError("liters must be a finite number")
        return v


class UsageUpdate(_Body):
    usage_date: Optional[date] = None
    liters: Optional[float] = Field(default=None, ge=0, le=100000)
    source_id: Optional[int] = Field(default=None, ge=1)
    source: Optional[str] = Field(default=None, max_length=40)
    notes: Optional[str] = Field(default=None, max_length=200)


class FlowIn(_Body):
    flow_lpm: float = Field(gt=0, le=500, examples=[1.8], description="Litres per minute")
    minutes: int = Field(ge=1, le=1440, examples=[25], description="Minutes it has been running")


# ---- alerts / schedules -----------------------------------------------------
class AlertStatusIn(_Body):
    status: Literal["open", "acknowledged", "dismissed", "resolved"]


class ScheduleIn(_Body):
    title: str = Field(min_length=1, max_length=80, examples=["Evening usage check-in"])
    reminder_type: str = Field(default="Usage Check-in", examples=["Usage Check-in"])
    days: str | list[str] = Field(default="daily", examples=["daily", ["mon", "wed", "fri"]])
    time_of_day: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$", examples=["20:00"])
    channel: str = Field(default="Push notification", examples=["Push notification"])
    notes: str = Field(default="", max_length=200)
    enabled: bool = True


class ScheduleUpdate(_Body):
    title: Optional[str] = Field(default=None, min_length=1, max_length=80)
    reminder_type: Optional[str] = None
    days: Optional[str | list[str]] = None
    time_of_day: Optional[str] = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    channel: Optional[str] = None
    notes: Optional[str] = Field(default=None, max_length=200)
    enabled: Optional[bool] = None


# ---- meter readings (existing desktop-app data) ------------------------------
class MeterReadingIn(_Body):
    reading_date: date
    meter_reading: float = Field(ge=0, le=10_000_000, description="Cumulative meter value in m³")
    notes: str = Field(default="", max_length=200)
