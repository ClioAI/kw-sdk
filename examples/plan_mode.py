"""
Plan Mode Example - Structured Execution with User-Defined Plan & Rubric

WHAT THIS DEMONSTRATES:
- User provides both plan AND rubric
- Orchestrator follows plan faithfully
- Evaluation against custom rubric

EXTRA SETUP NEEDED:
- .env file with API keys
- mode="plan" in run_single()
- plan=YOUR_PLAN (REQUIRED)
- rubric=YOUR_RUBRIC (OPTIONAL - will auto-create if not provided)

WHEN TO USE PLAN MODE:
- Complex multi-step tasks
- When you want control over execution strategy
- When you have domain-specific evaluation criteria
- Repeatable workflows (same plan, different inputs)
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
Write a comprehensive incident postmortem for a production database outage.
The outage lasted 47 minutes and affected 15% of customers.
Target audience: Engineering leadership and stakeholders.
"""

# =============================================================================
# USER-DEFINED PLAN (REQUIRED for plan mode)
# =============================================================================

PLAN = """
## Investigation Phase
1. Research best practices for incident postmortems (Google SRE, PagerDuty)
2. Identify key sections required in a blameless postmortem

## Writing Phase
3. Write executive summary (what happened, impact, resolution time)
4. Document timeline with specific timestamps
5. Describe root cause analysis (5 Whys methodology)
6. List what went well during incident response
7. List what went poorly / areas for improvement
8. Define action items with owners and due dates

## Quality Checks
9. Verify blameless language throughout
10. Ensure action items are specific and measurable
11. Check that timeline is coherent and complete
"""

# =============================================================================
# USER-DEFINED RUBRIC (OPTIONAL - omit to auto-create)
# =============================================================================

RUBRIC = """
## Structure & Completeness (40 points)
- [ ] Has executive summary at the top
- [ ] Includes detailed timeline with timestamps
- [ ] Contains root cause analysis section
- [ ] Has "what went well" section
- [ ] Has "what could be improved" section
- [ ] Includes specific action items with owners

## Blameless Culture (30 points)
- [ ] No individual blame or finger-pointing
- [ ] Focuses on systems and processes, not people
- [ ] Uses "we" language, not "they" or individual names
- [ ] Treats incident as learning opportunity

## Actionability (30 points)
- [ ] Action items are specific (not vague)
- [ ] Each action item has an owner assigned
- [ ] Action items have target completion dates
- [ ] Actions address root cause, not just symptoms
"""

# =============================================================================
# CONFIGURATION
# =============================================================================

harness = RLHarness(
    provider=ProviderConfig(name="gemini", thinking_level="MEDIUM"),
    enable_search=True,
    enable_bash=False,
    enable_code=False,
    on_event=on_event,
)

# =============================================================================
# TASK EXECUTION
# =============================================================================

print("=" * 60)
print("PLAN MODE EXECUTION")
print("=" * 60)
print(f"\nTask: {TASK.strip()[:80]}...")
print(f"\nPlan: {len(PLAN.strip().splitlines())} steps defined")
print(f"Rubric: Custom rubric provided (40+30+30 points)")
print("-" * 60)

try:
    result = harness.run_single(
        task=TASK,
        mode="plan",
        plan=PLAN,
        rubric=RUBRIC,
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

print("\n" + "=" * 60)
print("POSTMORTEM OUTPUT")
print("=" * 60)
print(result.answer)

# =============================================================================
# SAVE OUTPUT
# =============================================================================

output_dir = Path("examples/outputs")
output_dir.mkdir(parents=True, exist_ok=True)

output_file = output_dir / "plan_mode_output.md"
with open(output_file, "w") as f:
    f.write("# Plan Mode Example - Incident Postmortem\n\n")
    f.write(f"## Task\n{TASK}\n\n")
    f.write(f"## Plan Provided\n{PLAN}\n\n")
    f.write(f"## Rubric Provided\n{RUBRIC}\n\n")
    f.write("---\n\n")
    f.write(f"## Generated Postmortem\n\n{result.answer}\n\n")
    f.write("---\n\n")
    f.write("## Execution Trace\n\n")
    f.write(harness.get_history_markdown())

print(f"\n✓ Full output saved to {output_file}")
