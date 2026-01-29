"""
Standard Mode Example - Basic Task Execution

WHAT THIS DEMONSTRATES:
- Minimal setup for a simple task
- Auto-generated brief and rubric
- Event streaming for real-time feedback
- Basic result handling with error checking

EXTRA SETUP NEEDED:
- .env file with GEMINI_API_KEY or OPENAI_API_KEY
- That's it! Standard mode requires no additional configuration.
"""

import sys
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

from verif import RLHarness, HistoryEntry  # ProviderConfig available for Option 2/3

# =============================================================================
# EVENT HANDLER
# =============================================================================

def on_event(event: HistoryEntry):
    """Stream key events to console for progress visibility."""
    if event.entry_type == "tool_call":
        print(f"  → {event.content}")

# =============================================================================
# CONFIGURATION
# =============================================================================

# Option 1: Simple string provider
harness = RLHarness(provider="openai", on_event=on_event)

# Option 2: Provider config with settings (uncomment to use)
# config = ProviderConfig(
#     name="gemini",
#     thinking_level="MEDIUM",  # LOW | MEDIUM | HIGH
# )
# harness = RLHarness(provider=config, on_event=on_event)

# Option 3: OpenAI instead (uncomment to use)
# config = ProviderConfig(
#     name="openai",
#     reasoning_effort="medium",  # low | medium | high
# )
# harness = RLHarness(provider=config, on_event=on_event)

# =============================================================================
# TASK EXECUTION
# =============================================================================

task = "Compare the economic implications of implementing a carbon tax versus cap-and-trade system for reducing industrial emissions."

print(f"Task: {task}")
print("-" * 60)

try:
    result = harness.run_single(task)
except Exception as e:
    print(f"\n❌ Error during execution: {e}", file=sys.stderr)
    sys.exit(1)

# Check for errors
if not result.answer:
    print("\n❌ No answer was generated", file=sys.stderr)
    sys.exit(1)

# =============================================================================
# RESULTS
# =============================================================================

print("\n" + "=" * 60)
print("ANSWER")
print("=" * 60)
print(result.answer)

print("\n" + "=" * 60)
print("AUTO-GENERATED RUBRIC")
print("=" * 60)
print(result.rubric)

# Save full execution trace (optional)
output_dir = Path("examples/outputs")
output_dir.mkdir(parents=True, exist_ok=True)

output_file = output_dir / "standard_mode_output.md"
with open(output_file, "w") as f:
    f.write(f"# Standard Mode Example\n\n")
    f.write(f"## Task\n{result.task}\n\n")
    f.write(f"## Answer\n{result.answer}\n\n")
    f.write("---")
    f.write(f"## Rubric\n{result.rubric}\n\n")
    f.write("---\n\n")
    f.write("## Execution Trace\n\n")
    f.write(harness.get_history_markdown())

print(f"\n✓ Full trace saved to {output_file}")
