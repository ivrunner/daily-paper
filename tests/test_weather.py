import requests

from paper import weather
from paper.weather import describe, get_weather, parse_forecast

SAMPLE = {"daily": {"time": ["2026-10-13"], "weather_code": [2],
                    "temperature_2m_max": [71.4], "temperature_2m_min": [51.6]}}


def test_describe_codes():
    assert describe(0) == ("Clear", "sun")
    assert describe(2) == ("Partly cloudy", "partly")
    assert describe(63) == ("Rain", "rain")
    assert describe(75) == ("Snow", "snow")
    assert describe(95) == ("Thunderstorms", "storm")
    assert describe(12345) == ("Cloudy", "cloud")


def test_parse_forecast_rounds_temperatures():
    w = parse_forecast(SAMPLE, "Fort Wayne")
    assert (w.place, w.high_f, w.low_f, w.label, w.icon) == ("Fort Wayne", 71, 52, "Partly cloudy", "partly")


class FakeResponse:
    def __init__(self, data):
        self.data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self.data


def test_get_weather_success_sends_expected_params(monkeypatch):
    def fake_get(url, params, timeout):
        assert params["latitude"] == 41.17 and params["temperature_unit"] == "fahrenheit"
        assert params["timezone"] == "America/New_York"
        return FakeResponse(SAMPLE)

    monkeypatch.setattr(weather.requests, "get", fake_get)
    assert get_weather().high_f == 71


def test_get_weather_returns_none_on_any_failure(monkeypatch):
    def boom(*a, **k):
        raise requests.ConnectionError("down")

    monkeypatch.setattr(weather.requests, "get", boom)
    assert get_weather() is None
    monkeypatch.setattr(weather.requests, "get", lambda *a, **k: FakeResponse({"daily": {"weather_code": [None]}}))
    assert get_weather() is None
