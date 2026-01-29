"""
Standard Mode with Web Search - Research Task

WHAT THIS DEMONSTRATES:
- Enabling web search capability
- Research-style task execution
- Subagent delegation for searches
- Real-time information retrieval

EXTRA SETUP NEEDED:
- .env file with API keys
- enable_search=True in harness config

WHEN TO USE:
- Tasks requiring current/recent information
- Market research, competitive analysis
- Technical research with latest developments
- Fact-checking against authoritative sources
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
    elif event.entry_type == "subagent_start":
        name = event.metadata.get("subagent_id", "search") if event.metadata else "search"
        print(f"    ⤷ [{name}] searching...")

# =============================================================================
# CONFIGURATION
# =============================================================================

config = ProviderConfig(name="openai", reasoning_effort="medium")

harness = RLHarness(
    provider=config,
    enable_search=True,   # <-- REQUIRED: Enable web search tool
    enable_bash=False,
    enable_code=False,
    max_iterations=30,
    on_event=on_event,
)

# =============================================================================
# TASK EXECUTION
# =============================================================================

task = """
Analyze the current state of AI regulation in the European Union versus the United States.
Compare the EU AI Act (now in force) with US executive orders and proposed legislation.
Focus on: compliance requirements for foundation model providers, enforcement mechanisms,
and practical implications for companies operating in both markets.
"""

print(f"Task: {task.strip()[:100]}...")
print("-" * 60)
print("Running with web search enabled...\n")

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
print("ANSWER")
print("=" * 60)
print(result.answer)

print("\n" + "=" * 60)
print("AUTO-GENERATED RUBRIC")
print("=" * 60)
print(result.rubric)

# =============================================================================
# SEARCH ACTIVITY SUMMARY
# =============================================================================

print("\n" + "=" * 60)
print("SEARCH ACTIVITY")
print("=" * 60)

search_count = 0
for entry in result.history:
    if entry.entry_type == "tool_call" and "search_web" in entry.content:
        search_count += 1
        # Extract query from the tool call
        print(f"  {search_count}. {entry.content}")

if search_count == 0:
    print("  (No web searches performed)")
else:
    print(f"\n  Total searches: {search_count}")

# =============================================================================
# SAVE OUTPUT
# =============================================================================

output_dir = Path("examples/outputs")
output_dir.mkdir(parents=True, exist_ok=True)

output_file = output_dir / "standard_with_search_output.md"
with open(output_file, "w") as f:
    f.write("# Research Task with Web Search\n\n")
    f.write(f"## Task\n{result.task}\n\n")
    f.write(f"## Answer\n{result.answer}\n\n")
    f.write(f"## Rubric\n{result.rubric}\n\n")
    f.write("---\n\n")
    f.write("## Execution Trace\n\n")
    f.write(harness.get_history_markdown())

print(f"\n✓ Full output saved to {output_file}")
