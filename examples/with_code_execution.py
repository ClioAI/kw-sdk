"""
Code Execution Example - Stateful Python REPL

WHAT THIS DEMONSTRATES:
- Enabling Python code execution
- Stateful REPL (variables persist across calls)
- Creating artifact files (xlsx, csv, images)
- Tracking generated artifacts

EXTRA SETUP NEEDED:
- .env file with API keys
- enable_code=True in harness config
- code_executor=SubprocessExecutor(artifacts_dir) - REQUIRED
- artifacts_dir for output files

EXECUTOR FEATURES:
- Variables persist across code calls
- Standard library always available
- Files saved to artifacts_dir are tracked
- Timeout protection (default 60s)
"""

import sys
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

from verif import RLHarness, HistoryEntry
from verif.config import ProviderConfig
from verif.executor import SubprocessExecutor

# =============================================================================
# EVENT HANDLER
# =============================================================================

def on_event(event: HistoryEntry):
    """Stream key events to console for progress visibility."""
    if event.entry_type == "tool_call":
        if "execute_code" in event.content:
            print(f"  → executing code...")
        else:
            print(f"  → {event.content}")

# =============================================================================
# SETUP ARTIFACTS DIRECTORY
# =============================================================================

ARTIFACTS_DIR = Path(__file__).parent / "artifacts"
ARTIFACTS_DIR.mkdir(exist_ok=True)

# Clean previous artifacts (optional)
for f in ARTIFACTS_DIR.glob("*"):
    if f.is_file():
        f.unlink()

print(f"Artifacts directory: {ARTIFACTS_DIR}")

# =============================================================================
# CREATE CODE EXECUTOR
# =============================================================================

# SubprocessExecutor runs Python in a subprocess with:
# - Persistent state (variables survive across calls)
# - File tracking (new files in artifacts_dir are reported)
# - Timeout protection

executor = SubprocessExecutor(
    artifacts_dir=str(ARTIFACTS_DIR),
    timeout=60,
)

# =============================================================================
# CONFIGURATION
# =============================================================================

harness = RLHarness(
    provider=ProviderConfig(name="gemini", thinking_level="MEDIUM"),
    enable_search=False,
    enable_bash=False,
    enable_code=True,
    code_executor=executor,
    artifacts_dir=str(ARTIFACTS_DIR),
    on_event=on_event,
)

# =============================================================================
# TASK EXECUTION
# =============================================================================

task = """
Analyze the following sales data and generate a summary report.

Data (monthly sales in thousands):
Jan: 45, Feb: 52, Mar: 48, Apr: 61, May: 58, Jun: 72,
Jul: 69, Aug: 75, Sep: 82, Oct: 78, Nov: 91, Dec: 95

Calculate:
1. Total annual sales
2. Average monthly sales
3. Best and worst performing months
4. Month-over-month growth rates
5. Quarter-over-quarter comparison (Q1 vs Q2 vs Q3 vs Q4)

Save the results to "sales_analysis.txt" with a formatted summary.
"""

print("\n" + "=" * 60)
print("CODE EXECUTION EXAMPLE")
print("=" * 60)
print(f"Task: Sales Data Analysis")
print("-" * 60)

try:
    result = harness.run_single(task)
except Exception as e:
    print(f"\n❌ Error during execution: {e}", file=sys.stderr)
    sys.exit(1)

if not result.answer:
    print("\n❌ No answer was generated", file=sys.stderr)
    sys.exit(1)

# =============================================================================
# RESULTS
# =============================================================================

print("\n" + "=" * 60)
print("ANALYSIS SUMMARY")
print("=" * 60)
print(result.answer)

# =============================================================================
# CHECK CREATED ARTIFACTS
# =============================================================================

print("\n" + "=" * 60)
print("CREATED ARTIFACTS")
print("=" * 60)

artifacts = list(ARTIFACTS_DIR.iterdir())
if artifacts:
    for f in artifacts:
        size = f.stat().st_size
        print(f"  ✓ {f.name} ({size:,} bytes)")
else:
    print("  No artifacts created")

# =============================================================================
# SHOW CODE EXECUTION TRACE
# =============================================================================

print("\n" + "=" * 60)
print("CODE EXECUTION TRACE")
print("=" * 60)

exec_count = 0
for entry in result.history:
    if entry.entry_type == "tool_call" and "execute_code" in entry.content:
        exec_count += 1
        print(f"\n[CODE CALL #{exec_count}]")
    elif entry.entry_type == "tool_response" and entry.content and exec_count > 0:
        # Show abbreviated result
        preview = entry.content[:300] + "..." if len(entry.content) > 300 else entry.content
        print(f"[RESULT] {preview}")

print(f"\nTotal code executions: {exec_count}")

# =============================================================================
# SAVE EXECUTION TRACE
# =============================================================================

output_dir = Path("examples/outputs")
output_dir.mkdir(parents=True, exist_ok=True)

output_file = output_dir / "with_code_execution_output.md"
with open(output_file, "w") as f:
    f.write("# Code Execution Example\n\n")
    f.write(f"## Task\n{task}\n\n")
    f.write(f"## Summary\n{result.answer}\n\n")
    f.write("---\n\n")
    f.write("## Created Artifacts\n\n")
    for artifact in artifacts:
        f.write(f"- `{artifact.name}` ({artifact.stat().st_size:,} bytes)\n")
    f.write("\n---\n\n")
    f.write("## Execution Trace\n\n")
    f.write(harness.get_history_markdown())

print(f"\n✓ Full trace saved to {output_file}")

# =============================================================================
# EXECUTOR CLEANUP (optional)
# =============================================================================

# Reset executor state if needed for subsequent runs
# executor.reset()
