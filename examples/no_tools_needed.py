"""
Example: No Custom Tools Needed

Demonstrates why you don't need MCP servers or custom tools for every API.
Pattern: Pre-built utility functions + execute_code = infinite capabilities.

The model becomes a CALLER of your tested code, not a WRITER of untested code.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verif import RLHarness, ProviderConfig
from verif.executor import SubprocessExecutor

# =============================================================================
# DOCUMENT YOUR UTILITY FUNCTIONS
# =============================================================================

EXAMPLES_DIR = Path(__file__).parent

WEATHER_UTILS_DOCS = """
## Available: Weather Utilities

Pre-built functions in `utils.weather` - just import and call.

```python
from utils.weather import get_current, get_forecast, compare_cities

# Get current weather
get_current("London")
# Returns: {"city": "London", "temp": 15.2, "humidity": 72, "description": "overcast clouds"}

# Compare multiple cities
compare_cities(["London", "Tokyo", "Sydney"])
# Returns: {"London": {...}, "Tokyo": {...}, "Sydney": {...}}
```

All functions return {"error": "message"} on failure.
"""

# =============================================================================
# TASK
# =============================================================================

task = f"""I'm planning a weekend trip: Tokyo, Sydney, or London.
Recommend based on current weather (15-25°C ideal, less rain better).

{WEATHER_UTILS_DOCS}

IMPORTANT: Before importing, run:
```python
import sys
sys.path.insert(0, '{EXAMPLES_DIR}')
```

Use compare_cities() to get data, then recommend with specific numbers.
"""

# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    if not os.environ.get("OPENWEATHER_API_KEY"):
        print("Set OPENWEATHER_API_KEY for live API calls")
        print("Get free key at: https://openweathermap.org/api")
        print("-" * 60)

    config = ProviderConfig(name="gemini", thinking_level="MEDIUM")

    harness = RLHarness(
        provider=config,
        enable_code=True,
        code_executor=SubprocessExecutor(artifacts_dir=str(EXAMPLES_DIR / "outputs")),
    )

    print("Task: Weather recommendation (no custom tools)")
    print("-" * 60)

    result = harness.run_single(task)

    # Save output
    output_dir = EXAMPLES_DIR / "outputs"
    output_dir.mkdir(exist_ok=True)

    with open(output_dir / "no_tools_needed_output.md", "w") as f:
        f.write("# No Custom Tools Needed\n\n")
        f.write("## Pattern\n")
        f.write("Pre-built utils + execute_code = infinite capabilities\n\n")
        f.write(f"## Task\n{task}\n\n")
        f.write(f"## Answer\n{result.answer}\n")

    print(f"\nOutput: {output_dir}/no_tools_needed_output.md")
    print(f"\nAnswer preview:\n{result.answer[:500]}...")

# =============================================================================
# THE PATTERN
# =============================================================================
#
# 1. BUILD ONCE: utils/weather.py (tested, reliable)
# 2. DOCUMENT: Tell the model what functions exist
# 3. EXECUTE: Model imports and calls - no boilerplate
#
# Scales to any integration:
#   utils/stripe.py     -> create_charge(amount, customer)
#   utils/slack.py      -> send_message(channel, text)
#   utils/database.py   -> query(sql)
