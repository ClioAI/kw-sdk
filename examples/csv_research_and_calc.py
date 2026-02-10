"""
CSV Research + Calculation: SaaS Company Benchmarking

Starts with a CSV of 10 SaaS companies (only name + ARR filled).
Model must research missing fields AND compute derived metrics.

Research: founding year, HQ, CEO, employee count, stock ticker
Calculation: ARR per employee, implied revenue multiple, YoY growth rate

The prompt is intentionally minimal - model decides how to
decompose, what to search, and how to compute.

Run: PYTHONPATH=. python examples/csv_research_and_calc.py
"""

import csv
import io
import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from verif import RLHarness, HistoryEntry
from verif.config import ProviderConfig
from verif.executor import SubprocessExecutor

# =============================================================================
# INPUT CSV - only Company and ARR_USD_M filled
# =============================================================================

INPUT_CSV = """Company,ARR_USD_M,Founded,HQ_City,CEO,Employees,Stock_Ticker,Market_Cap_USD_B,ARR_Per_Employee,Revenue_Multiple_X,YoY_ARR_Growth_Pct
Datadog,2800,,,,,,,,,
CrowdStrike,4000,,,,,,,,,
Snowflake,3400,,,,,,,,,
MongoDB,2000,,,,,,,,,
Cloudflare,1700,,,,,,,,,
HubSpot,2600,,,,,,,,,
Twilio,4100,,,,,,,,,
Atlassian,4400,,,,,,,,,
Palantir,2900,,,,,,,,,
ServiceNow,10500,,,,,,,,,"""

# =============================================================================
# TASK - minimal, model figures out the rest
# =============================================================================

TASK = f"""Fill in this SaaS benchmarking CSV. Research the factual columns,
compute the derived ones.

Derived columns:
- ARR_Per_Employee = ARR_USD_M * 1_000_000 / Employees
- Revenue_Multiple_X = Market_Cap_USD_B / (ARR_USD_M / 1000)
- YoY_ARR_Growth_Pct = year-over-year ARR growth rate (research this)

Save completed CSV as 'saas_benchmark.csv'.

```csv
{INPUT_CSV.strip()}
```"""

# =============================================================================
# RUN
# =============================================================================

ARTIFACTS_DIR = Path(__file__).parent / "artifacts"
ARTIFACTS_DIR.mkdir(exist_ok=True)

def on_event(e: HistoryEntry):
    if e.entry_type == "tool_call":
        print(f"  -> {e.content[:150]}")

harness = RLHarness(
    provider=ProviderConfig(name="gemini", thinking_level="MEDIUM"),
    enable_search=True,
    enable_code=True,
    code_executor=SubprocessExecutor(str(ARTIFACTS_DIR)),
    on_event=on_event,
)

print("=" * 60)
print("SaaS Benchmarking: Research + Calculation")
print("=" * 60)

result = harness.run_single(TASK)

# =============================================================================
# OUTPUT
# =============================================================================

csv_file = ARTIFACTS_DIR / "saas_benchmark.csv"
if csv_file.exists():
    print(f"\n{'=' * 60}")
    print(f"OUTPUT: {csv_file}")
    print("=" * 60)
    print(csv_file.read_text())
else:
    print("\nNo CSV artifact found. Model answer:")
    print(result.answer)

# Save trace
output_dir = Path(__file__).parent / "outputs"
output_dir.mkdir(parents=True, exist_ok=True)
trace = output_dir / "saas_benchmark_output.md"
trace.write_text(
    f"# SaaS Benchmarking\n\n## Answer\n{result.answer}\n\n"
    f"## Rubric\n{result.rubric}\n\n## Trace\n{harness.get_history_markdown()}"
)
print(f"\nTrace: {trace}")
print(f"History entries: {len(result.history)}")
