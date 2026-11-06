"""Glue between households (cached coordinates) and the weather client."""
import time
from datetime import datetime

from hydrohome import config
from hydrohome.errors import WeatherError


class WeatherService:
    def __init__(self, households_repo, client):
        self.households = households_repo
        self.client = client

    def forecast_for_household(self, household_id):
        hh = self.households.get(household_id)
        if not hh:
            raise WeatherError("Select a household first.")
        lat, lon, place = hh["latitude"], hh["longitude"], hh["city"]
        if lat is None or lon is None:                 # first time: look up and cache
            lat, lon, place = self.client.geocode(hh["city"])
            self.households.set_coordinates(household_id, lat, lon)
        return self.client.get_forecast(lat, lon, place)


class ForecastCache:
    """Remembers the last forecast per household so the dashboard can refresh itself
    automatically without calling the API every few seconds."""

    def __init__(self, ttl=config.WEATHER_REFRESH_SECONDS, retry=config.WEATHER_RETRY_SECONDS,
                 clock=time.monotonic):
        self.ttl, self.retry, self.clock = ttl, retry, clock
        self._items = {}

    @staticmethod
    def _key(household_id, city):
        return (household_id, (city or "").strip().lower())   # a changed city = a new entry

    def store(self, household_id, city, forecast):
        self._items[self._key(household_id, city)] = {
            "forecast": forecast, "at": self.clock(), "when": datetime.now(), "failed_at": None}

    def mark_failed(self, household_id, city):
        entry = self._items.setdefault(self._key(household_id, city),
                                       {"forecast": None, "at": None, "when": None, "failed_at": None})
        entry["failed_at"] = self.clock()

    def get(self, household_id, city):
        entry = self._items.get(self._key(household_id, city))
        return (entry["forecast"], entry["when"]) if entry and entry["forecast"] else (None, None)

    def should_fetch(self, household_id, city):
        entry = self._items.get(self._key(household_id, city))
        if entry is None:
            return True
        if entry["failed_at"] is not None and self.clock() - entry["failed_at"] < self.retry:
            return False
        return entry["at"] is None or self.clock() - entry["at"] >= self.ttl
