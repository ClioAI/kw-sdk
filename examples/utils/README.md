# Weather Utilities

Pre-built functions for weather data. Import and call.

## Setup
```python
import sys
sys.path.insert(0, '/path/to/examples')  # Adjust path as needed
from utils.weather import get_current, get_forecast, compare_cities
```

## Functions

### get_current(city: str) -> dict
Get current weather for a city.

```python
get_current("London")
# Returns:
{
    "city": "London",
    "country": "GB",
    "temp": 15.2,
    "feels_like": 14.1,
    "humidity": 72,
    "description": "overcast clouds",
    "wind_speed": 4.5
}
```

### get_forecast(city: str, days: int = 5) -> dict
Get weather forecast (3-hour intervals).

```python
get_forecast("Tokyo", days=2)
# Returns:
{
    "city": "Tokyo",
    "country": "JP",
    "forecasts": [
        {"datetime": "2024-01-15 12:00:00", "temp": 8.5, "rain_chance": 20, ...},
        {"datetime": "2024-01-15 15:00:00", "temp": 10.2, "rain_chance": 15, ...},
        ...
    ]
}
```

### compare_cities(cities: list[str]) -> dict
Compare current weather across multiple cities.

```python
compare_cities(["London", "Tokyo", "Sydney"])
# Returns:
{
    "London": {"temp": 15.2, "humidity": 72, ...},
    "Tokyo": {"temp": 8.5, "humidity": 45, ...},
    "Sydney": {"temp": 22.1, "humidity": 60, ...}
}
```

## Error Handling
All functions return `{"error": "message", "city": "..."}` on failure.
Always check for "error" key before accessing data.
