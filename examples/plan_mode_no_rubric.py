"""
Plan Mode WITHOUT Rubric - Auto-Create Rubric from Plan

WHAT THIS DEMONSTRATES:
- Plan mode with only a plan (no rubric)
- Orchestrator creates rubric from plan context
- Useful when plan is clear but rubric is tedious to write

EXTRA SETUP NEEDED:
- .env file with API keys
- mode="plan" in run_single()
- plan=YOUR_PLAN (REQUIRED)
- DO NOT pass rubric - let it auto-create

WHEN TO USE THIS:
- You have a clear plan but don't want to write a rubric
- Quick iterations where rubric precision isn't critical
- Exploratory work where requirements are still forming
"""

import sys
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

from verif import RLHarness, HistoryEntry
from verif.config import ProviderConfig

# =============================================================================
# EVENT HANDLER
# =============================================================================

def on_event(event: HistoryEntry):
    """Stream key events to console for progress visibility."""
    if event.entry_type == "tool_call":
        print(f"  → {event.content}")

# =============================================================================
# TASK & PLAN
# =============================================================================

TASK = """
Write a commit message for a major refactoring that:
- Migrated from class components to React hooks
- Affected 23 files across 5 directories
- No functional changes, purely structural
"""

PLAN = """
1. Start with a concise subject line (50 chars max, imperative mood)
2. Add blank line after subject
3. Write body explaining WHY the refactoring was done
4. List the scope of changes (number of files, directories)
5. Explicitly state what was NOT changed (no functional changes)
6. Follow conventional commits format (type: subject)
7. Keep total message under 72 chars per line
"""

# =============================================================================
# CONFIGURATION
# =============================================================================

harness = RLHarness(
    provider=ProviderConfig(name="gemini", thinking_level="LOW"),
    enable_search=False,
    on_event=on_event,
)

# =============================================================================
# EXECUTION
# =============================================================================

print("Plan mode WITHOUT USER PROVIDED rubric")
print("-" * 40)
print(f"Task: {TASK.strip()[:60]}...")
print(f"Plan: {len(PLAN.strip().splitlines())} steps")
print("-" * 40)

try:
    result = harness.run_single(
        task=TASK,
        mode="plan",
        plan=PLAN,
        # rubric NOT provided - will be auto-created
    )
except Exception as e:
    print(f"\n❌ Error during execution: {e}", file=sys.stderr)
    sys.exit(1)

if not result.answer:
    print("\n❌ No answer was generated", file=sys.stderr)
    sys.exit(1)

# =============================================================================
# RESULTS
# =============================================================================

print("\n" + "=" * 40)
print("COMMIT MESSAGE")
print("=" * 40)
print(result.answer)

print("\n" + "=" * 40)
print("AUTO-GENERATED RUBRIC")
print("=" * 40)
print(result.rubric)

# =============================================================================
# SHOW TOOL CALLS
# =============================================================================

print("\n" + "=" * 40)
print("TOOL CALLS (showing rubric creation)")
print("=" * 40)
for entry in result.history:
    if entry.entry_type == "tool_call" and "rubric" in entry.content.lower():
        print(f"  {entry.content[:150]}...")

# =============================================================================
# SAVE OUTPUT
# =============================================================================

output_dir = Path("examples/outputs")
output_dir.mkdir(parents=True, exist_ok=True)

output_file = output_dir / "plan_mode_no_rubric_output.md"
with open(output_file, "w") as f:
    f.write("# Plan Mode (No Rubric) Example\n\n")
    f.write(f"## Task\n{TASK}\n\n")
    f.write(f"## Plan\n{PLAN}\n\n")
    f.write("---\n\n")
    f.write(f"## Generated Commit Message\n```\n{result.answer}\n```\n\n")
    f.write(f"## Auto-Generated Rubric\n{result.rubric}\n\n")
    f.write("---\n\n")
    f.write("## Execution Trace\n\n")
    f.write(harness.get_history_markdown())

print(f"\n✓ Output saved to {output_file}")
