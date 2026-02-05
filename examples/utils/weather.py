"""
Pre-built weather utilities. Model just imports and calls.
No need to write requests code from scratch.
"""

import os
import requests
from typing import Optional

API_KEY = os.environ.get("OPENWEATHER_API_KEY")
BASE_URL = "https://api.openweathermap.org/data/2.5"


def get_current(city: str) -> dict:
    """Get current weather for a city.

    Args:
        city: City name (e.g., "London", "Tokyo,JP")

    Returns:
        dict with temp, feels_like, humidity, description, wind_speed
    """
    url = f"{BASE_URL}/weather?q={city}&appid={API_KEY}&units=metric"
    r = requests.get(url, timeout=10)
    data = r.json()

    if r.status_code != 200:
        return {"error": data.get("message", "API error"), "city": city}

    return {
        "city": data["name"],
        "country": data["sys"]["country"],
        "temp": data["main"]["temp"],
        "feels_like": data["main"]["feels_like"],
        "humidity": data["main"]["humidity"],
        "description": data["weather"][0]["description"],
        "wind_speed": data["wind"]["speed"],
    }


def get_forecast(city: str, days: int = 5) -> dict:
    """Get weather forecast for a city.

    Args:
        city: City name
        days: Number of days (max 5 for free tier)

    Returns:
        dict with city info and list of forecasts
    """
    url = f"{BASE_URL}/forecast?q={city}&appid={API_KEY}&units=metric"
    r = requests.get(url, timeout=10)
    data = r.json()

    if r.status_code != 200:
        return {"error": data.get("message", "API error"), "city": city}

    forecasts = []
    for item in data["list"][:days * 8]:  # 8 entries per day (3-hour intervals)
        forecasts.append({
            "datetime": item["dt_txt"],
            "temp": item["main"]["temp"],
            "feels_like": item["main"]["feels_like"],
            "humidity": item["main"]["humidity"],
            "description": item["weather"][0]["description"],
            "rain_chance": item.get("pop", 0) * 100,
        })

    return {
        "city": data["city"]["name"],
        "country": data["city"]["country"],
        "forecasts": forecasts,
    }


def compare_cities(cities: list[str]) -> dict:
    """Compare current weather across multiple cities.

    Args:
        cities: List of city names

    Returns:
        dict mapping city -> weather data
    """
    return {city: get_current(city) for city in cities}


# CLI interface for bash usage
if __name__ == "__main__":
    import sys
    import json

    if len(sys.argv) < 2:
        print("Usage: python weather.py <city> [--forecast]")
        sys.exit(1)

    city = sys.argv[1]
    if "--forecast" in sys.argv:
        print(json.dumps(get_forecast(city), indent=2))
    else:
        print(json.dumps(get_current(city), indent=2))
