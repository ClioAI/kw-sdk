"""
End-to-End Workflow: Explore → Select → Execute

WHAT THIS DEMONSTRATES:
- Complete workflow from ideation to execution
- Stage 1: EXPLORE - Generate multiple approaches
- Stage 2: SELECT - Use LLM to pick the best approach
- Stage 3: EXECUTE - Run plan mode with selected approach

THIS IS USEFUL WHEN:
- You want AI to brainstorm before committing
- Stakeholder review between exploration and execution
- Building agentic pipelines with human-in-the-loop

FLOW:
┌──────────────────────────────────────────────────────────┐
│  EXPLORE MODE                                            │
│  → Generate 3+ distinct approaches                       │
│  → Each with assumptions & counterfactuals               │
└──────────────────────────────────────────────────────────┘
                          ↓
┌──────────────────────────────────────────────────────────┐
│  SELECTION (LLM generate call)                           │
│  → Analyze all takes                                     │
│  → Pick best approach + synthesize plan                  │
└──────────────────────────────────────────────────────────┘
                          ↓
┌──────────────────────────────────────────────────────────┐
│  PLAN MODE                                               │
│  → Execute the selected approach                         │
│  → Verify against rubric                                 │
│  → Produce final deliverable                             │
└──────────────────────────────────────────────────────────┘
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
Write a technical design document for implementing rate limiting in a
high-traffic API gateway. The system serves 50,000 requests per second
and must support:
- Per-user rate limits
- Per-endpoint rate limits
- Graceful degradation under load
- Real-time monitoring and alerting
"""

# =============================================================================
# STAGE 1: EXPLORE - Generate Multiple Approaches
# =============================================================================

print("=" * 70)
print("STAGE 1: EXPLORE - Generating Multiple Approaches")
print("=" * 70)

explore_harness = RLHarness(
    provider=ProviderConfig(name="gemini", thinking_level="MEDIUM"),
    enable_search=True,
    on_event=on_event,
)

try:
    explore_result = explore_harness.run_single(
        task=TASK,
        mode="explore",
        num_takes=3,
    )
except Exception as e:
    print(f"\n❌ Error during exploration: {e}", file=sys.stderr)
    sys.exit(1)

# Parse takes
takes = [t.strip() for t in explore_result.answer.split("===") if t.strip()]
print(f"\nGenerated {len(takes)} distinct approaches")

for i, take in enumerate(takes, 1):
    print(f"\n--- Take {i} Preview ---")
    print(take[:400] + "...")

# =============================================================================
# STAGE 2: SELECT - Use LLM to Pick Best Approach
# =============================================================================

print("\n" + "=" * 70)
print("STAGE 2: SELECT - Analyzing and Choosing Best Approach")
print("=" * 70)

from verif.providers.gemini import GeminiProvider

selector = GeminiProvider()

SELECTION_PROMPT = f"""
You are a senior systems architect. Analyze these {len(takes)} rate limiting approaches.

## The Takes

{explore_result.answer}

## Your Task

1. Briefly analyze each take's strengths and weaknesses
2. Consider: 50K RPS requirement, multi-tenant support, operational complexity
3. Select the BEST approach (or synthesize from multiple)
4. Output a concrete EXECUTION PLAN for writing the design doc

## Output Format

### Analysis
[Brief analysis of each take]

### Selected Approach
[Which take or combination, and why]

### Execution Plan
1. [Step 1]
2. [Step 2]
...

### Rubric for Final Document
- [ ] Criterion 1
- [ ] Criterion 2
...
"""

try:
    selection_result = selector.generate(
        prompt=SELECTION_PROMPT,
        system="You are an expert systems architect specializing in high-scale distributed systems.",
    )
except Exception as e:
    print(f"\n❌ Error during selection: {e}", file=sys.stderr)
    sys.exit(1)

print("\n--- Selection Analysis ---")
print(selection_result[:1500] + "..." if len(selection_result) > 1500 else selection_result)

# =============================================================================
# PARSE PLAN AND RUBRIC FROM SELECTION
# =============================================================================

def extract_section(text: str, header: str) -> str:
    """Extract content under a markdown header."""
    lines = text.split("\n")
    capture = False
    result = []

    for line in lines:
        if line.strip().startswith("###") and header.lower() in line.lower():
            capture = True
            continue
        elif line.strip().startswith("###") and capture:
            break
        elif capture:
            result.append(line)

    return "\n".join(result).strip()

selected_plan = extract_section(selection_result, "Execution Plan")
selected_rubric = extract_section(selection_result, "Rubric")

# Fallback if parsing fails
if not selected_plan:
    selected_plan = """
1. Write executive summary with chosen algorithm
2. Document system architecture with diagram description
3. Specify data model and storage requirements
4. Define API contracts for rate limit configuration
5. Describe failure modes and graceful degradation
6. Include monitoring and alerting requirements
7. Provide capacity planning guidelines
"""

if not selected_rubric:
    selected_rubric = """
- [ ] Specifies chosen algorithm with justification
- [ ] Includes capacity calculations for 50K RPS
- [ ] Defines per-user and per-endpoint limit structure
- [ ] Describes graceful degradation behavior
- [ ] Includes monitoring metrics and alerts
- [ ] Addresses failure scenarios
- [ ] Has clear API contracts
"""

print("\n--- Extracted Plan ---")
print(selected_plan)

print("\n--- Extracted Rubric ---")
print(selected_rubric)

# =============================================================================
# STAGE 3: EXECUTE - Run Plan Mode with Selected Approach
# =============================================================================

print("\n" + "=" * 70)
print("STAGE 3: EXECUTE - Producing Final Deliverable")
print("=" * 70)

execute_harness = RLHarness(
    provider=ProviderConfig(name="gemini", thinking_level="MEDIUM"),
    enable_search=False,
    on_event=on_event,
)

try:
    final_result = execute_harness.run_single(
        task=TASK,
        mode="plan",
        plan=selected_plan,
        rubric=selected_rubric,
    )
except Exception as e:
    print(f"\n❌ Error during execution: {e}", file=sys.stderr)
    sys.exit(1)

if not final_result.answer:
    print("\n❌ No answer was generated", file=sys.stderr)
    sys.exit(1)

# =============================================================================
# FINAL OUTPUT
# =============================================================================

print("\n" + "=" * 70)
print("FINAL DESIGN DOCUMENT")
print("=" * 70)
print(final_result.answer)

# =============================================================================
# SAVE COMPLETE WORKFLOW
# =============================================================================

output_dir = Path("examples/outputs")
output_dir.mkdir(parents=True, exist_ok=True)

output_file = output_dir / "end_to_end_output.md"
with open(output_file, "w") as f:
    f.write("# End-to-End Workflow: Explore → Select → Execute\n\n")
    f.write(f"## Original Task\n{TASK}\n\n")

    f.write("---\n\n")
    f.write("# Stage 1: Exploration\n\n")
    for i, take in enumerate(takes, 1):
        f.write(f"## Take {i}\n\n{take}\n\n---\n\n")

    f.write("---\n\n")
    f.write("# Stage 2: Selection\n\n")
    f.write(f"## Analysis\n{selection_result}\n\n")
    f.write(f"## Extracted Plan\n{selected_plan}\n\n")
    f.write(f"## Extracted Rubric\n{selected_rubric}\n\n")

    f.write("---\n\n")
    f.write("# Stage 3: Final Execution\n\n")
    f.write(f"## Final Design Document\n\n{final_result.answer}\n\n")

    f.write("---\n\n")
    f.write("# Execution Traces\n\n")
    f.write("## Explore Trace\n\n")
    f.write(explore_harness.get_history_markdown())
    f.write("\n\n## Execute Trace\n\n")
    f.write(execute_harness.get_history_markdown())

print(f"\n\n✓ Complete workflow saved to {output_file}")

# =============================================================================
# WORKFLOW SUMMARY
# =============================================================================

print("\n" + "=" * 70)
print("WORKFLOW SUMMARY")
print("=" * 70)
print(f"""
✓ Stage 1: EXPLORE
  - Generated {len(takes)} distinct approaches
  - Each with assumptions and counterfactuals

✓ Stage 2: SELECT
  - Analyzed all takes with Gemini
  - Synthesized best approach into execution plan
  - Generated evaluation rubric

✓ Stage 3: EXECUTE
  - Ran plan mode with selected strategy
  - Verified against rubric
  - Produced final design document

This pattern enables:
  - Divergent thinking before convergent execution
  - Human review between stages (add input() prompts)
  - Audit trail of decision process
  - Reusable plans for similar tasks
""")
