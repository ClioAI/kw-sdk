"""
Iterate Workflow: Refining Answers Based on User Feedback

WHAT THIS DEMONSTRATES:
- Using iterate() for post-answer refinement
- CLIENT responsibility: classifying user feedback into rubric vs answer feedback
- Handling both feedback types in a single turn
- Chained iterations for progressive refinement

KEY ASSUMPTION:
The SDK's iterate() expects STRUCTURED input:
  - feedback: "Use Q3 numbers instead" (answer-level correction)
  - rubric_update: "Must include regulatory risk analysis" (criteria-level)

The CLIENT is responsible for taking raw user input and classifying it.
This example shows how to do that with an LLM call.

SCENARIO:
A senior analyst asks the SDK to evaluate a market expansion opportunity.
After reviewing the initial output, they provide feedback - some about the
content ("wrong data source"), some about criteria ("needs board-level summary").

FLOW:
┌──────────────────────────────────────────────────────────────┐
│  STAGE 1: INITIAL EXECUTION                                  │
│  → run_single() produces market analysis + rubric            │
│  → Client stores both for later iteration                    │
└──────────────────────────────────────────────────────────────┘
                          ↓
┌──────────────────────────────────────────────────────────────┐
│  USER FEEDBACK (raw, unstructured)                           │
│  "Use McKinsey's 2024 data, not the 2023 figures. Also       │
│   this is going to the board - needs executive summary."     │
└──────────────────────────────────────────────────────────────┘
                          ↓
┌──────────────────────────────────────────────────────────────┐
│  STAGE 2: CLIENT CLASSIFIES FEEDBACK (LLM call)              │
│  → Separates into: rubric_update vs answer_feedback          │
│  → This is CLIENT responsibility, not SDK                    │
└──────────────────────────────────────────────────────────────┘
                          ↓
┌──────────────────────────────────────────────────────────────┐
│  STAGE 3: ITERATE                                            │
│  → SDK merges rubric_update into rubric (if provided)        │
│  → SDK runs orchestrator with feedback                       │
│  → Verifies until PASS, returns refined answer               │
└──────────────────────────────────────────────────────────────┘
"""

import re
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

from verif import RLHarness, HistoryEntry
from verif.config import ProviderConfig
from verif.providers.gemini import GeminiProvider

# =============================================================================
# EVENT HANDLER
# =============================================================================

def on_event(event: HistoryEntry):
    """Stream key events to console."""
    if event.entry_type == "system":
        print(f"  ⚙️  {event.content[:80]}...")
    elif event.entry_type == "tool_call":
        print(f"  🔧 {event.content[:80]}...")

# =============================================================================
# TASK DEFINITION
# =============================================================================

TASK = """
Evaluate the opportunity for expanding into the Southeast Asian market
for our B2B SaaS platform (enterprise project management software).

Consider:
- Market size and growth trajectory
- Competitive landscape
- Regulatory environment
- Go-to-market strategy options
- Key risks and mitigations

Produce a recommendation memo for the executive team.
"""

# =============================================================================
# STAGE 1: INITIAL EXECUTION
# =============================================================================

print("=" * 70)
print("STAGE 1: INITIAL EXECUTION")
print("=" * 70)
print(f"Task: {TASK.strip()}")
print("-" * 70)

harness = RLHarness(
    provider=ProviderConfig(name="gemini"),
    enable_search=True,
    on_event=on_event,
)

initial_result = harness.run_single(task=TASK)

print(f"\n✓ Initial answer: {len(initial_result.answer)} chars")
print(f"✓ Rubric created: {len(initial_result.rubric)} chars")

# CLIENT STORES THESE FOR LATER ITERATION
stored_answer = initial_result.answer
stored_rubric = initial_result.rubric

print("\n--- Answer Preview ---")
print(initial_result.answer[:500] + "...")

# =============================================================================
# SIMULATED USER FEEDBACK (raw, unstructured)
# =============================================================================

print("\n" + "=" * 70)
print("USER FEEDBACK (raw input)")
print("=" * 70)

# This is what a real user might type - mixed feedback
# Some is about the CONTENT, some is about the CRITERIA
USER_FEEDBACK_RAW = """
A few things:

1. please use Gartner's 2024 SEA SaaS report

2. You missed Atlassian's recent push into Singapore - they're the main
   competitor we need to address.

3. This is going to the board next week, so I need an executive summary
   at the top - 3 bullet points max with the key recommendation.

4. Also add a criterion that we must address data residency requirements
   for each country - that's a dealbreaker for enterprise customers.
"""

print(USER_FEEDBACK_RAW)

# =============================================================================
# STAGE 2: CLIENT CLASSIFIES FEEDBACK
# =============================================================================

print("\n" + "=" * 70)
print("STAGE 2: CLIENT CLASSIFIES FEEDBACK")
print("=" * 70)
print("Using LLM to separate rubric changes from answer feedback...")
print("-" * 70)

# This is the CLIENT's responsibility - not the SDK
classifier = GeminiProvider()

CLASSIFICATION_PROMPT = f"""
Analyze this user feedback and separate it into two categories.

## User Feedback
{USER_FEEDBACK_RAW}

## Categories

1. **Answer Feedback**: Comments about the answer content itself
   - "Add a table", "Make it shorter", "Include more examples"
   - "Use different data source", "Missing competitor X"

2. **Rubric Update**: Comments about evaluation criteria/requirements
   - "Must include citations", "Should cover security"
   - "Add criterion for X", "Criteria should check for Y"

## Output Format

### ANSWER_FEEDBACK
[Write the consolidated feedback for improving the answer content]

### RUBRIC_UPDATE
[Write the new criteria to add to rubric, or "None" if no criteria changes]
"""

classification_result = classifier.generate(
    prompt=CLASSIFICATION_PROMPT,
    system="You are a feedback classifier. Separate user feedback into answer changes vs criteria changes.",
)

# Parse markdown sections with regex
def extract_section(text: str, header: str) -> str | None:
    """Extract content under a markdown header."""
    pattern = rf"###\s*{header}\s*\n(.*?)(?=###|\Z)"
    match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    if match:
        content = match.group(1).strip()
        return None if content.lower() == "none" else content
    return None

answer_feedback = extract_section(classification_result, "ANSWER_FEEDBACK")
rubric_update = extract_section(classification_result, "RUBRIC_UPDATE")

# Fallback if parsing fails
if not answer_feedback and not rubric_update:
    print("⚠️  Classification parsing failed, using raw feedback")
    answer_feedback = USER_FEEDBACK_RAW

print("\n--- Classification Result ---")
print(f"Answer Feedback: {answer_feedback}")
print(f"Rubric Update: {rubric_update}")

# =============================================================================
# STAGE 3: ITERATE WITH CLASSIFIED FEEDBACK
# =============================================================================

print("\n" + "=" * 70)
print("STAGE 3: ITERATE")
print("=" * 70)

if rubric_update:
    print(f"→ Will merge rubric update: {rubric_update[:50]}...")
if answer_feedback:
    print(f"→ Will apply feedback: {answer_feedback[:50]}...")

print("-" * 70)

iterate_result = harness.iterate(
    task=TASK,
    answer=stored_answer,
    rubric=stored_rubric,
    feedback=answer_feedback,
    rubric_update=rubric_update,
)

print(f"\n✓ Refined answer: {len(iterate_result.answer)} chars")
print(f"✓ Updated rubric: {len(iterate_result.rubric)} chars")

print("\n--- Refined Answer Preview ---")
print(iterate_result.answer[:800] + "...")

# =============================================================================
# OPTIONAL: CHAINED ITERATION
# =============================================================================

print("\n" + "=" * 70)
print("STAGE 4: CHAINED ITERATION (second round)")
print("=" * 70)

# User provides more feedback after reviewing refined version
SECOND_FEEDBACK = """
Good improvements. One more thing - the CFO will be in this meeting.
Add a rough 3-year financial projection for the expansion
(investment required, expected ARR, break-even timeline).
"""

print(f"Second feedback: {SECOND_FEEDBACK}")
print("-" * 70)

# For simple content feedback, no classification needed
iterate_result_2 = harness.iterate(
    task=TASK,
    answer=iterate_result.answer,  # Use previous iteration's answer
    rubric=iterate_result.rubric,  # Use previous iteration's rubric
    feedback=SECOND_FEEDBACK,
    # No rubric_update this time - just content addition
)

print(f"\n✓ Final answer: {len(iterate_result_2.answer)} chars")

# =============================================================================
# SAVE OUTPUTS
# =============================================================================

output_dir = Path("examples/outputs")
output_dir.mkdir(parents=True, exist_ok=True)

output_file = output_dir / "iterate_workflow_output.md"
with open(output_file, "w") as f:
    f.write("# Iterate Workflow Output\n\n")

    f.write("## Original Task\n")
    f.write(f"{TASK}\n\n")

    f.write("---\n\n")
    f.write("## Stage 1: Initial Answer\n\n")
    f.write(f"{initial_result.answer}\n\n")
    f.write("### Initial Rubric\n\n")
    f.write(f"{initial_result.rubric}\n\n")

    f.write("---\n\n")
    f.write("## User Feedback (Raw)\n\n")
    f.write(f"{USER_FEEDBACK_RAW}\n\n")

    f.write("## Classified Feedback\n\n")
    f.write(f"**Answer Feedback:** {answer_feedback}\n\n")
    f.write(f"**Rubric Update:** {rubric_update}\n\n")

    f.write("---\n\n")
    f.write("## Stage 3: After First Iteration\n\n")
    f.write(f"{iterate_result.answer}\n\n")
    f.write("### Updated Rubric\n\n")
    f.write(f"{iterate_result.rubric}\n\n")

    f.write("---\n\n")
    f.write("## Stage 4: After Second Iteration\n\n")
    f.write(f"{iterate_result_2.answer}\n\n")

print(f"\n✓ Output saved to {output_file}")

# =============================================================================
# SUMMARY
# =============================================================================

print("\n" + "=" * 70)
print("WORKFLOW SUMMARY")
print("=" * 70)
print(f"""
✓ Stage 1: INITIAL EXECUTION
  - run_single() produced market analysis memo + rubric
  - Client stored both for later iteration

✓ Stage 2: CLIENT CLASSIFIED FEEDBACK
  - Raw user input contained MIXED feedback:
    • Content fixes: "use 2024 data", "add Atlassian competitor analysis"
    • Format request: "add executive summary"
    • Criteria change: "must address data residency requirements"
  - CLIENT's LLM separated these into:
    • answer_feedback → content/format changes
    • rubric_update → new evaluation criteria

✓ Stage 3: FIRST ITERATION
  - SDK merged "data residency" into rubric criteria
  - Orchestrator refined answer (2024 data, Atlassian, exec summary)
  - Verified against updated rubric until PASS

✓ Stage 4: SECOND ITERATION
  - Added financial projections for CFO
  - No rubric change needed

KEY POINTS FOR CLIENT INTEGRATION:
  - SDK expects STRUCTURED input (feedback + rubric_update)
  - CLIENT must classify raw user feedback (this example shows how)
  - iterate() is STATELESS - pass task, answer, rubric each time
  - Chain iterations for progressive refinement
  - Same tools available as run_single() (search, bash, code)
""")
