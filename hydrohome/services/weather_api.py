"""HTTP client for the Open-Meteo REST APIs (geocoding + forecast).

Purpose in the system: weather changes how much water a household needs. A rainy day
means garden watering can be skipped; a hot day means earlier watering and leak checks.
Open-Meteo needs no API key. Docs: https://open-meteo.com/en/docs
"""
from dataclasses import dataclass, field

import requests

from hydrohome import config
from hydrohome.errors import WeatherError


@dataclass(frozen=True)
class DayForecast:
    date: str
    temp_max: float
    temp_min: float
    rain_mm: float
    rain_probability: int


@dataclass(frozen=True)
class Forecast:
    place: str
    latitude: float
    longitude: float
    current_temp: float
    humidity: int
    days: list = field(default_factory=list)


class WeatherClient:
    def __init__(self, session=None, timeout=config.API_TIMEOUT_SECONDS):
        self.session = session or requests.Session()
        self.timeout = timeout

    def _get_json(self, url, params):
        try:
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            payload = response.json()
        except requests.Timeout as exc:
            raise WeatherError("The weather service took too long to respond. "
                               "Please try again.") from exc
        except requests.ConnectionError as exc:
            raise WeatherError("Cannot reach the weather service. "
                               "Check your internet connection.") from exc
        except requests.HTTPError as exc:
            code = exc.response.status_code if exc.response is not None else "?"
            raise WeatherError(f"The weather service returned an error (HTTP {code}).") from exc
        except requests.RequestException as exc:
            raise WeatherError(f"Weather request failed: {exc}") from exc
        except ValueError as exc:
            raise WeatherError("The weather service sent an invalid (non-JSON) response.") from exc
        if not isinstance(payload, dict):
            raise WeatherError("Unexpected weather response format.")
        if payload.get("error"):
            raise WeatherError(f"Weather service: {payload.get('reason', 'unknown error')}")
        return payload

    def geocode(self, city):
        """Return (latitude, longitude, display name) for a city name."""
        candidates = [city]
        trimmed = city.strip()
        if trimmed.lower().endswith(" city"):          # "Tarlac City" -> "Tarlac"
            candidates.append(trimmed[:-5].strip())
        for name in candidates:
            data = self._get_json(config.GEOCODE_URL,
                                  {"name": name, "count": 1, "language": "en", "format": "json"})
            results = data.get("results") or []
            if results:
                try:
                    first = results[0]
                    label = ", ".join(p for p in (first.get("name"), first.get("admin1"),
                                                  first.get("country")) if p)
                    return float(first["latitude"]), float(first["longitude"]), label
                except (KeyError, TypeError, ValueError) as exc:
                    raise WeatherError("Unexpected geocoding response format.") from exc
        raise WeatherError(f"No location found for '{city}'. Check the city spelling.")

    def get_forecast(self, latitude, longitude, place):
        data = self._get_json(config.FORECAST_URL, {
            "latitude": latitude, "longitude": longitude, "timezone": "auto",
            "forecast_days": config.FORECAST_DAYS,
            "current": "temperature_2m,relative_humidity_2m",
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,"
                     "precipitation_probability_max"})
        try:
            cur, daily = data["current"], data["daily"]
            days = [DayForecast(
                        date=daily["time"][i],
                        temp_max=float(daily["temperature_2m_max"][i]),
                        temp_min=float(daily["temperature_2m_min"][i]),
                        rain_mm=float(daily["precipitation_sum"][i] or 0),
                        rain_probability=int(daily["precipitation_probability_max"][i] or 0))
                    for i in range(len(daily["time"]))]
            return Forecast(place, latitude, longitude, float(cur["temperature_2m"]),
                            int(cur["relative_humidity_2m"]), days)
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise WeatherError("The weather data was incomplete or in an unexpected format.") from exc
