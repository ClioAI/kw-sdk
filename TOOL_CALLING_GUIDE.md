# Tool Calling Guide: Code as Tools

An opinionated approach to AI tool calling that eliminates boilerplate.

**Examples:**
- [examples/no_tools_needed.py](examples/no_tools_needed.py) – Inline documentation pattern
- [examples/docs_from_file.py](examples/docs_from_file.py) – Docs as file attachment
- [examples/with_memory.py](examples/with_memory.py) – Memory/context file for complex decisions
- [examples/utils/](examples/utils/) – Sample utilities and documentation

## The Problem with Traditional Tool Calling

Most AI tool-calling frameworks require:

1. **Schema definitions** – JSON schemas for every tool
2. **Handler registration** – Wiring functions to the AI runtime
3. **MCP servers** – Running separate processes for tool access
4. **Serialization** – Converting between AI-friendly formats and your code

This is unnecessary complexity. The model can already execute code.

## The Philosophy: Code *Is* the Tool

Instead of building tool infrastructure, write Python functions and let the model call them directly via `execute_code`.

```
Traditional:                          This approach:
┌─────────────┐                       ┌─────────────┐
│ Define tool │                       │ Write       │
│ JSON schema │                       │ Python func │
└──────┬──────┘                       └──────┬──────┘
       ↓                                     ↓
┌─────────────┐                       ┌─────────────┐
│ Implement   │                       │ Document it │
│ handler     │                       │ (docstring) │
└──────┬──────┘                       └──────┬──────┘
       ↓                                     ↓
┌─────────────┐                       ┌─────────────┐
│ Register    │                       │ Model calls │
│ with runtime│                       │ via execute │
└──────┬──────┘                       └─────────────┘
       ↓
┌─────────────┐
│ Serialize   │
│ responses   │
└─────────────┘
```

**Result:** You write tested code once. The model imports and calls it.

---

## Pattern 1: Inline Documentation

Embed function docs directly in the task prompt.

```python
from verif import RLHarness
from verif.executor import SubprocessExecutor

# Document your utilities
WEATHER_DOCS = """
## Available: Weather Utilities

```python
from utils.weather import get_current, get_forecast, compare_cities

# Get current weather
get_current("London")
# Returns: {"city": "London", "temp": 15.2, "humidity": 72, ...}

# Compare multiple cities
compare_cities(["London", "Tokyo", "Sydney"])
# Returns: {"London": {...}, "Tokyo": {...}, "Sydney": {...}}
```

All functions return `{"error": "message"}` on failure.
"""

# Include docs in the task
task = f"""Recommend the best city for a weekend trip based on weather.
Consider: temperature (15-25°C ideal), humidity, rain chance.

{WEATHER_DOCS}

Use compare_cities() to get data, then recommend with specific numbers.
"""

harness = RLHarness(
    provider="gemini",
    enable_code=True,
    code_executor=SubprocessExecutor("./artifacts"),
)

result = harness.run_single(task)
```

The model sees the documentation, writes import statements, and calls your tested functions.

See: [examples/no_tools_needed.py](examples/no_tools_needed.py)

---

## Pattern 2: Docs as File Attachment

Keep documentation in a file alongside your utilities. Attach it to prompts.

```
examples/
├── utils/
│   ├── README.md      # Documentation
│   ├── weather.py     # Implementation
│   └── __init__.py
└── docs_from_file.py  # Example usage
```

```python
from pathlib import Path
from verif import RLHarness, Attachment, Prompt
from verif.executor import SubprocessExecutor

DOCS_FILE = Path("utils/README.md")

# Create attachment with full content as preview
docs_attachment = Attachment(
    content=str(DOCS_FILE.absolute()),
    mime_type="text/markdown",
    name="Weather Utils Documentation",
    preview=DOCS_FILE.read_text(),  # Model sees this immediately
)

task_text = """Recommend the best city for a weekend trip based on weather.
The attached documentation describes available weather functions.
"""

prompt: Prompt = [task_text, docs_attachment]

harness = RLHarness(
    provider="gemini",
    enable_code=True,
    code_executor=SubprocessExecutor("./artifacts"),
)

result = harness.run_single(prompt)
```

**Benefits:**
- Docs live with code (easy to maintain)
- No "read file" step – docs are immediate context
- Reusable across multiple tasks

See: [examples/docs_from_file.py](examples/docs_from_file.py)

---

## Writing Effective Utility Functions

### 1. Return dicts, not custom objects

```python
# Good - JSON-serializable, model can read directly
def get_weather(city: str) -> dict:
    return {"city": city, "temp": 15.2, "humidity": 72}

# Avoid - requires understanding class structure
def get_weather(city: str) -> WeatherData:
    return WeatherData(city=city, temp=15.2, humidity=72)
```

### 2. Include error handling in return values

```python
def get_weather(city: str) -> dict:
    try:
        response = requests.get(f"{API}/weather?q={city}", timeout=10)
        if response.status_code != 200:
            return {"error": response.json().get("message"), "city": city}
        return parse_response(response.json())
    except requests.Timeout:
        return {"error": "Request timed out", "city": city}
```

Model can check for `"error"` key and handle gracefully.

### 3. Document with examples, not just descriptions

```python
def compare_cities(cities: list[str]) -> dict:
    """Compare current weather across multiple cities.

    Args:
        cities: List of city names

    Returns:
        dict mapping city -> weather data

    Example:
        >>> compare_cities(["London", "Tokyo"])
        {"London": {"temp": 15.2, ...}, "Tokyo": {"temp": 8.5, ...}}
    """
```

### 4. Provide CLI interface for bash fallback

```python
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
```

Now it works with `execute_code` or `search_files` (bash).

---

## Scaling to Real Integrations

This pattern scales to any API:

```
utils/
├── stripe.py       # create_charge(amount, customer), get_customer(id)
├── slack.py        # send_message(channel, text), list_channels()
├── database.py     # query(sql), insert(table, data)
├── s3.py           # upload(bucket, key, data), download(bucket, key)
└── README.md       # Document all of them
```

Each file:
1. Handles authentication (via env vars)
2. Returns dicts with consistent error format
3. Is independently testable

The model becomes a **caller** of your tested code, not a **writer** of untested code.

---

## When to Use Traditional Tools Instead

This pattern works best when:
- ✅ You control the utility code
- ✅ Operations are stateless or use simple state
- ✅ Latency of code execution is acceptable

Consider traditional tools when:
- ❌ You need streaming responses
- ❌ Tool requires long-running connections (websockets)
- ❌ Security isolation is critical (untrusted code)
- ❌ You're integrating with existing MCP infrastructure

---

## Complete Example: Weather Utilities

### utils/weather.py

```python
"""Pre-built weather utilities. Model just imports and calls."""

import os
import requests

API_KEY = os.environ.get("OPENWEATHER_API_KEY")
BASE_URL = "https://api.openweathermap.org/data/2.5"


def get_current(city: str) -> dict:
    """Get current weather for a city.

    Returns:
        dict with temp, feels_like, humidity, description, wind_speed
        or {"error": "message"} on failure
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


def compare_cities(cities: list[str]) -> dict:
    """Compare current weather across multiple cities."""
    return {city: get_current(city) for city in cities}
```

### utils/README.md

```markdown
# Weather Utilities

Pre-built functions for weather data. Import and call.

## Setup
```python
import sys
sys.path.insert(0, '/path/to/examples')
from utils.weather import get_current, compare_cities
```

## Functions

### get_current(city: str) -> dict
```python
get_current("London")
# {"city": "London", "temp": 15.2, "humidity": 72, ...}
```

### compare_cities(cities: list[str]) -> dict
```python
compare_cities(["London", "Tokyo"])
# {"London": {...}, "Tokyo": {...}}
```

## Error Handling
All functions return `{"error": "message"}` on failure.
```

### Task Execution

```python
from pathlib import Path
from verif import RLHarness, Attachment, Prompt
from verif.executor import SubprocessExecutor

EXAMPLES_DIR = Path(__file__).parent
DOCS_FILE = EXAMPLES_DIR / "utils" / "README.md"

docs = Attachment(
    content=str(DOCS_FILE),
    mime_type="text/markdown",
    name="Weather Docs",
    preview=DOCS_FILE.read_text(),
)

task = f"""Compare weather in Tokyo, Sydney, and London.
Recommend the best for outdoor activities this weekend.

Before importing, run:
```python
import sys
sys.path.insert(0, '{EXAMPLES_DIR}')
```
"""

prompt: Prompt = [task, docs]

harness = RLHarness(
    provider="gemini",
    enable_code=True,
    code_executor=SubprocessExecutor(str(EXAMPLES_DIR / "outputs")),
)

result = harness.run_single(prompt)
print(result.answer)
```

---

## Summary

| Approach | Lines of code | Maintenance | Testability |
|----------|---------------|-------------|-------------|
| MCP Server | 200+ | High | Moderate |
| JSON Schema Tools | 100+ | Medium | Moderate |
| **Code as Tools** | 20-50 | Low | High |

Write Python. Document it. Let the model call it.
