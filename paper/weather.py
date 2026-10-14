"""Today's forecast for the masthead weather box (Open-Meteo, free, no key)."""
from __future__ import annotations

import logging

import requests

from paper.models import Weather

URL = "https://api.open-meteo.com/v1/forecast"
log = logging.getLogger(__name__)

# WMO weather codes → (label, icon)
CODES: list[tuple[tuple[int, ...], str, str]] = [
    ((0,), "Clear", "sun"),
    ((1, 2), "Partly cloudy", "partly"),
    ((3,), "Overcast", "cloud"),
    ((45, 48), "Fog", "fog"),
    ((51, 53, 55, 56, 57), "Drizzle", "rain"),
    ((61, 63, 65, 66, 67, 80, 81, 82), "Rain", "rain"),
    ((71, 73, 75, 77, 85, 86), "Snow", "snow"),
    ((95, 96, 99), "Thunderstorms", "storm"),
]


def describe(code: int) -> tuple[str, str]:
    for codes, label, icon in CODES:
        if code in codes:
            return label, icon
    return "Cloudy", "cloud"


def parse_forecast(data: dict, place: str) -> Weather:
    daily = data["daily"]
    label, icon = describe(int(daily["weather_code"][0]))
    return Weather(place=place, high_f=round(daily["temperature_2m_max"][0]),
                   low_f=round(daily["temperature_2m_min"][0]), label=label, icon=icon)


def get_weather(place: str = "Fort Wayne", lat: float = 41.17, lon: float = -85.10) -> Weather | None:
    params = {
        "latitude": lat, "longitude": lon,
        "daily": "weather_code,temperature_2m_max,temperature_2m_min",
        "temperature_unit": "fahrenheit", "timezone": "America/New_York", "forecast_days": 1,
    }
    try:
        response = requests.get(URL, params=params, timeout=10)
        response.raise_for_status()
        return parse_forecast(response.json(), place)
    except Exception as exc:  # weather is optional; the box is simply left out
        log.warning("Weather unavailable: %s", exc)
        return None
