"""TC-55..TC-58: dashboard auto-update logic (forecast cache)."""
from hydrohome.services.weather_service import ForecastCache


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def make():
    clock = Clock()
    return ForecastCache(ttl=1800, retry=120, clock=clock), clock


def test_fetches_when_empty_then_uses_cache_until_ttl():
    cache, clock = make()
    assert cache.should_fetch(1, "Tarlac")
    cache.store(1, "Tarlac", "FORECAST")
    assert cache.get(1, "Tarlac")[0] == "FORECAST"
    clock.t = 1799
    assert not cache.should_fetch(1, "Tarlac")          # dashboard refreshes do NOT hit the API
    clock.t = 1800
    assert cache.should_fetch(1, "Tarlac")              # 30 minutes later: automatic re-fetch


def test_failure_backs_off_then_retries_and_keeps_old_forecast():
    cache, clock = make()
    cache.store(1, "Tarlac", "OLD")
    clock.t = 2000
    cache.mark_failed(1, "Tarlac")
    assert not cache.should_fetch(1, "Tarlac")          # wait before retrying
    assert cache.get(1, "Tarlac")[0] == "OLD"           # last good data still shown
    clock.t = 2121
    assert cache.should_fetch(1, "Tarlac")


def test_failure_without_any_forecast_also_backs_off():
    cache, clock = make()
    cache.mark_failed(2, "X")
    assert not cache.should_fetch(2, "X")
    clock.t = 121
    assert cache.should_fetch(2, "X")


def test_changed_city_is_treated_as_new():
    cache, _ = make()
    cache.store(1, "Tarlac", "F")
    assert cache.should_fetch(1, "Manila")
    assert cache.get(1, "Manila") == (None, None)
