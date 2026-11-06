"""TC-28..TC-35: REST API success and failure paths (HTTP layer replaced with fakes
so failures can be triggered on demand; the real endpoint is exercised by running the app)."""
from datetime import datetime

import pytest
import requests

from hydrohome.errors import WeatherError
from hydrohome.services import advisor
from hydrohome.services.weather_api import WeatherClient

GEO = {"results": [{"name": "Tarlac", "admin1": "Central Luzon", "country": "Philippines",
                    "latitude": 15.48, "longitude": 120.59}]}
FORECAST = {"current": {"temperature_2m": 31.0, "relative_humidity_2m": 72},
            "daily": {"time": ["2026-11-06", "2026-11-07", "2026-11-08"],
                      "temperature_2m_max": [34.1, 30.0, 29.0], "temperature_2m_min": [25, 24, 24],
                      "precipitation_sum": [0.0, 9.5, None],
                      "precipitation_probability_max": [10, 90, None]}}


class FakeResponse:
    def __init__(self, payload=None, status=200, bad_json=False):
        self.payload, self.status_code, self.bad_json = payload, status, bad_json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(response=self)

    def json(self):
        if self.bad_json:
            raise ValueError("not json")
        return self.payload


class FakeSession:
    def __init__(self, *responses):
        self.responses, self.calls = list(responses), []

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, params, timeout))
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def client(*responses):
    return WeatherClient(FakeSession(*responses), timeout=3)


def test_geocode_success_and_city_suffix_fallback():
    c = client(FakeResponse({}), FakeResponse(GEO))              # "Tarlac City" -> retry "Tarlac"
    lat, lon, label = c.geocode("Tarlac City")
    assert (lat, lon) == (15.48, 120.59) and "Philippines" in label
    assert c.session.calls[1][1]["name"] == "Tarlac"
    assert c.session.calls[0][2] == 3                              # timeout is always sent


def test_geocode_unknown_city():
    with pytest.raises(WeatherError, match="No location"):
        client(FakeResponse({})).geocode("Zzzz")


def test_forecast_parsed_with_null_values():
    f = client(FakeResponse(FORECAST)).get_forecast(15.48, 120.59, "Tarlac")
    assert f.current_temp == 31.0 and len(f.days) == 3
    assert f.days[2].rain_mm == 0 and f.days[2].rain_probability == 0


@pytest.mark.parametrize("failure,text", [
    (requests.Timeout(), "too long"),
    (requests.ConnectionError(), "Cannot reach"),
    (FakeResponse(status=500), "HTTP 500"),
    (FakeResponse(bad_json=True), "invalid"),
    (FakeResponse({"error": True, "reason": "bad coords"}), "bad coords"),
    (FakeResponse([1, 2]), "Unexpected"),
    (FakeResponse({"current": {}, "daily": {}}), "incomplete"),
])
def test_failures_become_weather_error(failure, text):
    with pytest.raises(WeatherError, match=text):
        client(failure).get_forecast(1, 2, "X")


def test_weather_service_caches_coordinates(services, household):
    fake = FakeSession(FakeResponse(GEO), FakeResponse(FORECAST), FakeResponse(FORECAST))
    services.weather.client = WeatherClient(fake)
    services.weather.forecast_for_household(household)
    services.weather.forecast_for_household(household)
    assert len(fake.calls) == 3                                    # geocoded only once
    assert services.households.get(household)["latitude"] == 15.48


def test_advice_from_forecast():
    f = client(FakeResponse(FORECAST)).get_forecast(1, 2, "Tarlac")
    s = advisor.weather_suggestions(f, now=datetime(2026, 11, 5, 12, 0))
    titles = " ".join(x.title for x in s)
    assert "skip garden watering" in titles and "Hot day" in titles
    assert s[0].due_at == "2026-11-07 06:00"
