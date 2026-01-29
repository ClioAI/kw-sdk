"""
Standard Mode with Pre-Generated Rubric

WHAT THIS DEMONSTRATES:
- Start with acceptance criteria (business requirements)
- Use LLM to convert into proper rubric format
- Pass rubric to standard mode execution

THIS IS USEFUL WHEN:
- You have clear success criteria from stakeholders
- You want consistent evaluation across runs
- Building repeatable quality checks
- Separating "what to check" from "how to execute"

FLOW:
┌─────────────────────────────────────────────────────────────┐
│  ACCEPTANCE CRITERIA (your input)                           │
│  → Business requirements, success metrics                   │
│  → Plain language, not structured                           │
└─────────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────┐
│  RUBRIC GENERATION (LLM generate call)                      │
│  → Convert to structured rubric format                      │
│  → Add priority levels (must/good_to_have/ideal)            │
│  → Make criteria binary and verifiable                      │
└─────────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────┐
│  STANDARD MODE (with rubric)                                │
│  → Execute task normally                                    │
│  → Verify against YOUR rubric                               │
│  → Iterate until PASS                                       │
└─────────────────────────────────────────────────────────────┘
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
Write a technical RFC (Request for Comments) proposing a migration from REST to GraphQL
for our internal microservices API layer. Target audience: Engineering leads who will
review and approve/reject the proposal.
"""

# =============================================================================
# ACCEPTANCE CRITERIA (plain language from stakeholders)
# =============================================================================

ACCEPTANCE_CRITERIA = """
SUCCESS CRITERIA FROM ENGINEERING LEADERSHIP:

1. Must clearly state the problem with current REST implementation -
   over-fetching, N+1 queries, versioning complexity

2. Must include concrete migration path - not a "big bang" rewrite

3. Should address performance implications with data (latency, payload size)

4. Must acknowledge risks and mitigation strategies - don't be one-sided

5. Include rollback plan if migration fails

6. Estimate engineering effort in person-weeks, broken down by phase

7. Address backward compatibility for existing REST consumers

8. Keep it under 1500 words - leadership won't read longer

NICE TO HAVE:
- Reference similar migrations at other companies (learnings)
- Include schema design principles for the GraphQL layer
- Cost analysis (infrastructure, training)
"""

# =============================================================================
# STEP 1: Generate Rubric from Acceptance Criteria
# =============================================================================

print("=" * 70)
print("STEP 1: Converting Acceptance Criteria to Rubric")
print("=" * 70)

from verif.providers.openai import OpenAIProvider

rubric_generator = OpenAIProvider()

RUBRIC_PROMPT = f"""
Convert these acceptance criteria into a structured evaluation rubric.

## Acceptance Criteria
{ACCEPTANCE_CRITERIA}

## Output Format

Create a rubric with three priority levels:

### MUST HAVE (all required for PASS)
- [ ] Criterion (binary yes/no check)
- [ ] Criterion (binary yes/no check)

### GOOD TO HAVE (improves quality)
- [ ] Criterion (binary yes/no check)

### IDEAL (stretch goals)
- [ ] Criterion (binary yes/no check)

## Rules
1. Each criterion must be independently verifiable from the text alone
2. Make criteria binary (yes/no) not subjective
3. Be specific - "mentions X" not "is good"
4. Don't add criteria not in the acceptance criteria
5. Prioritize correctly - must-haves are dealbreakers

Output ONLY the rubric, no preamble.
"""

try:
    generated_rubric = rubric_generator.generate(
        prompt=RUBRIC_PROMPT,
        system="You are an expert at converting business requirements into precise, verifiable evaluation criteria.",
    )
except Exception as e:
    print(f"\n❌ Error generating rubric: {e}", file=sys.stderr)
    sys.exit(1)

print("\n--- Generated Rubric ---")
print(generated_rubric)

# =============================================================================
# STEP 2: Run Standard Mode with the Rubric
# =============================================================================

print("\n" + "=" * 70)
print("STEP 2: Executing Task with Generated Rubric")
print("=" * 70)

harness = RLHarness(
    provider=ProviderConfig(name="openai", reasoning_effort="medium"),
    enable_search=False,
    rubric=generated_rubric,
    on_event=on_event,
)

try:
    result = harness.run_single(task=TASK)
except Exception as e:
    print(f"\n❌ Error during execution: {e}", file=sys.stderr)
    sys.exit(1)

if not result.answer:
    print("\n❌ No answer was generated", file=sys.stderr)
    sys.exit(1)

# =============================================================================
# RESULTS
# =============================================================================

print("\n" + "=" * 70)
print("RFC OUTPUT")
print("=" * 70)
print(result.answer)

print("\n" + "=" * 70)
print("RUBRIC USED FOR VERIFICATION")
print("=" * 70)
print(result.rubric)

# =============================================================================
# SHOW VERIFICATION TRACE
# =============================================================================

print("\n" + "=" * 70)
print("VERIFICATION TRACE")
print("=" * 70)

for entry in result.history:
    if entry.entry_type == "tool_call" and "verify_answer" in entry.content:
        print("\n[VERIFY CALL]")
    elif entry.entry_type == "tool_response" and ("PASS" in entry.content or "FAIL" in entry.content):
        preview = entry.content[:500] + "..." if len(entry.content) > 500 else entry.content
        print(f"[VERIFY RESULT]\n{preview}")

# =============================================================================
# SAVE OUTPUT
# =============================================================================

output_dir = Path("examples/outputs")
output_dir.mkdir(parents=True, exist_ok=True)

output_file = output_dir / "standard_with_rubric_output.md"
with open(output_file, "w") as f:
    f.write("# Standard Mode with Pre-Generated Rubric\n\n")

    f.write("## Task\n")
    f.write(f"{TASK}\n\n")

    f.write("## Original Acceptance Criteria\n")
    f.write(f"```\n{ACCEPTANCE_CRITERIA}\n```\n\n")

    f.write("## Generated Rubric\n")
    f.write(f"{generated_rubric}\n\n")

    f.write("---\n\n")

    f.write("## Final Output\n")
    f.write(f"{result.answer}\n\n")

    f.write("---\n\n")
    f.write("## Execution Trace\n\n")
    f.write(harness.get_history_markdown())

print(f"\n✓ Full output saved to {output_file}")

# =============================================================================
# REUSABILITY: Same Rubric, Different Tasks
# =============================================================================

print("\n" + "=" * 70)
print("BONUS: Reusing the Rubric")
print("=" * 70)
print("""
You can reuse the same rubric for similar tasks:

# Save rubric to file
with open("rfc_rubric.md", "w") as f:
    f.write(generated_rubric)

# Load and reuse
with open("rfc_rubric.md") as f:
    saved_rubric = f.read()

harness = RLHarness(provider="openai", rubric=saved_rubric)
result = harness.run_single("Write RFC for migrating from Postgres to CockroachDB...")

This ensures consistent quality across all RFCs.
""")
