"""
iPhone 18 NPI Plan: Iteration Flow

Demonstrates iterate() for refining outputs:
1. Load initial NPI output from explore → select → execute
2. Provide targeted feedback
3. Iterate to refine

Run: PYTHONPATH=. python examples/npi_iterate.py
(Requires running npi_iphone18.py first)
"""

from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

from verif import RLHarness, HistoryEntry
from verif.config import ProviderConfig

# =============================================================================
# LOAD INITIAL OUTPUT
# =============================================================================

output_file = Path("examples/outputs/iphone18_npi.md")
if not output_file.exists():
    print("Run npi_iphone18.py first to generate initial output")
    exit(1)

content = output_file.read_text()

# Extract sections
def extract_after(text: str, marker: str) -> str:
    idx = text.find(marker)
    if idx == -1:
        return ""
    return text[idx + len(marker):].strip()

# Answer is between "Stage 3" and "Generated Rubric"
stage3_start = content.find("## Stage 3: Final NPI Document\n")
rubric_start = content.find("## Generated Rubric\n")
initial_answer = content[stage3_start + len("## Stage 3: Final NPI Document\n"):rubric_start].strip().rstrip("-").strip()

# Rubric is everything after "Generated Rubric"
initial_rubric = extract_after(content, "## Generated Rubric\n")

TASK = """
Create an NPI (New Product Introduction) plan for iPhone 18.

Product: First foldable iPhone with Apple Intelligence 2.0
Launch: September 2026, simultaneous in US/EU/China/Japan
Price: $1,499+ (premium segment)

Audience: Apple executive leadership (SVPs of Hardware, Software, Operations, Marketing)
"""

print("=" * 70)
print("LOADED INITIAL OUTPUT")
print("=" * 70)
print(f"Answer: {len(initial_answer.split())} words")
print(f"Rubric: {len(initial_rubric)} chars")

# =============================================================================
# FEEDBACK
# =============================================================================

FEEDBACK = """
The CFO and COO will be in the board meeting. Strengthen:

1. FINANCIALS: Add unit volume projections (Q1-Q4 2026), revenue forecast,
   and BOM breakdown to justify the 45% margin claim.

2. COMPETITIVE: How will Samsung/Huawei respond? Add scenario planning.

3. POST-LAUNCH KPIs: What does success look like at Day 30/90/365?
   Quantitative metrics only.
"""

def on_event(e: HistoryEntry):
    if e.entry_type == "tool_call":
        print(f"  → {e.content}")

print("\n" + "=" * 70)
print("ITERATING")
print("=" * 70)
print(FEEDBACK)

harness = RLHarness(
    provider=ProviderConfig(name="gemini", thinking_level="HIGH"),
    enable_search=True,
    on_event=on_event,
)

result = harness.iterate(
    task=TASK,
    answer=initial_answer,
    rubric=initial_rubric,
    feedback=FEEDBACK,
)

# =============================================================================
# OUTPUT
# =============================================================================

print("\n" + "=" * 70)
print("REFINED NPI PLAN")
print("=" * 70)
print(result.answer)

# Save
(Path("examples/outputs") / "iphone18_npi_v2.md").write_text(f"""# iPhone 18 NPI Plan (v2 - Iterated)

## Feedback Applied
{FEEDBACK}

---

## Refined Document
{result.answer}

---

## Rubric
{result.rubric}
""")

print(f"""
✓ Saved to examples/outputs/iphone18_npi_v2.md

Summary:
  • Initial: {len(initial_answer.split())} words
  • Refined: {len(result.answer.split())} words
  • Added: Financials, Competitive scenarios, KPIs
""")
