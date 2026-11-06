"""Composition root: wires repositories -> services. The UI receives one Services object."""
from dataclasses import dataclass

from hydrohome.database import connection
from hydrohome.database.repositories import (HouseholdRepository, MeterSourceRepository,
                                             ReadingRepository, ReminderRepository)
from hydrohome.services.household_service import HouseholdService
from hydrohome.services.meter_sync_service import MeterSyncService
from hydrohome.services.reading_service import ReadingService
from hydrohome.services.reminder_service import ReminderService
from hydrohome.services.report_service import ReportService
from hydrohome.services.weather_api import WeatherClient
from hydrohome.services.weather_service import WeatherService


@dataclass
class Services:
    households: HouseholdService
    readings: ReadingService
    reminders: ReminderService
    weather: WeatherService
    reports: ReportService
    meters: MeterSyncService


def build_services(db_path=None, weather_client=None, meter_session=None):
    connection.initialize(db_path)
    hh_repo = HouseholdRepository(db_path)
    rd_repo = ReadingRepository(db_path)
    rm_repo = ReminderRepository(db_path)
    households = HouseholdService(hh_repo)
    readings = ReadingService(rd_repo, hh_repo)
    reminders = ReminderService(rm_repo, hh_repo)
    weather = WeatherService(hh_repo, weather_client or WeatherClient())
    meters = MeterSyncService(MeterSourceRepository(db_path), readings, session=meter_session)
    return Services(households, readings, reminders, weather,
                    ReportService(households, readings, reminders), meters)
