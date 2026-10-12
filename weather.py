"""Get current weather, distinct from historic uploaded video conditions."""
import requests


def current_weather(latitude, longitude):
    response = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params={"latitude": latitude, "longitude": longitude,
                "current": "temperature_2m,precipitation,wind_speed_10m,weather_code",
                "timezone": "auto"},
        timeout=12,
    )
    response.raise_for_status()
    data = response.json()
    return data["current"]
