"""
Explore Mode Example - Divergent Thinking with Multiple Takes

WHAT THIS DEMONSTRATES:
- Generate multiple distinct perspectives on a task
- Each take includes counterfactual analysis
- Set-level gap analysis across all takes

EXTRA SETUP NEEDED:
- .env file with API keys
- mode="explore" in run_single()
- num_takes=N (OPTIONAL hint for number of takes, default 3+)

WHEN TO USE EXPLORE MODE:
- Creative writing with multiple angles
- Strategy brainstorming
- Problem exploration before committing to an approach
- Generating alternatives for stakeholder review

EXPLORE MODE DIFFERENCES:
- No accuracy rubric (uses quality checklist instead)
- Output contains multiple takes separated by ===
- Each take has assumptions + counterfactual analysis
- Focuses on DIVERGENCE, not convergence
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
# TASK DEFINITION
# =============================================================================

TASK = """
A fintech startup is choosing their primary database architecture for a new
payment processing system. They need to handle:
- 10,000 transactions per second at peak
- Strong consistency for financial data
- Multi-region deployment for latency
- Compliance with PCI-DSS requirements

Explore different architectural approaches with their trade-offs.
"""

# =============================================================================
# CONFIGURATION
# =============================================================================

harness = RLHarness(
    provider=ProviderConfig(name="openai", reasoning_effort="medium"),
    enable_search=True,
    enable_bash=False,
    enable_code=False,
    on_event=on_event,
)

# =============================================================================
# EXECUTION
# =============================================================================

print("=" * 60)
print("EXPLORE MODE - Multiple Architectural Approaches")
print("=" * 60)
print(f"\nTask: {TASK.strip()[:100]}...")
print("-" * 60)

try:
    result = harness.run_single(
        task=TASK,
        mode="explore",
        num_takes=3,
    )
except Exception as e:
    print(f"\n❌ Error during execution: {e}", file=sys.stderr)
    sys.exit(1)

if not result.answer:
    print("\n❌ No answer was generated", file=sys.stderr)
    sys.exit(1)

# =============================================================================
# PARSE TAKES
# =============================================================================

takes = result.answer.split("===")
takes = [t.strip() for t in takes if t.strip()]

print(f"\nGenerated {len(takes)} distinct takes")
print("=" * 60)

for i, take in enumerate(takes, 1):
    print(f"\n{'='*60}")
    print(f"TAKE {i}")
    print("=" * 60)
    preview = take[:800] + "..." if len(take) > 800 else take
    print(preview)

# =============================================================================
# SAVE OUTPUT
# =============================================================================

output_dir = Path("examples/outputs")
output_dir.mkdir(parents=True, exist_ok=True)

output_file = output_dir / "explore_mode_output.md"
with open(output_file, "w") as f:
    f.write("# Explore Mode Example - Database Architecture Decision\n\n")
    f.write(f"## Task\n{TASK}\n\n")
    f.write("---\n\n")

    for i, take in enumerate(takes, 1):
        f.write(f"## Take {i}\n\n{take}\n\n---\n\n")

    f.write("## Execution Trace\n\n")
    f.write(harness.get_history_markdown())

print(f"\n\n✓ Full output saved to {output_file}")

# =============================================================================
# EXPLORE MODE OUTPUT STRUCTURE
# =============================================================================

print("\n" + "=" * 60)
print("EXPLORE MODE OUTPUT STRUCTURE")
print("=" * 60)
print("""
Each take typically contains:
1. The actual deliverable (architecture recommendation)
2. **Assumptions:** What must be true for this to work
3. **Counterfactual:** What could make this approach fail

The final section includes:
- Set-level gaps: What perspectives are missing across all takes
- What all takes assume that might be wrong
""")
