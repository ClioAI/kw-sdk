"""
iPhone 18 NPI Plan: Explore → Select → Execute

Demonstrates minimal-instruction workflow:
1. EXPLORE: Generate diverse strategic directions
2. SELECT: AI picks the best direction (one sentence)
3. EXECUTE: Standard mode - model creates its own brief & rubric

Run: PYTHONPATH=. python examples/npi_iphone18.py
"""

import sys
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

from verif import RLHarness, HistoryEntry
from verif.config import ProviderConfig
from verif.providers.gemini import GeminiProvider

# =============================================================================
# TASK - intentionally minimal, let the model explore
# =============================================================================

TASK = """
Create an NPI (New Product Introduction) plan for iPhone 18.

Product: First foldable iPhone with Apple Intelligence 2.0
Launch: September 2026, simultaneous in US/EU/China/Japan
Price: $1,499+ (premium segment)

Audience: Apple executive leadership (SVPs of Hardware, Software, Operations, Marketing)
"""

# =============================================================================
# WORKFLOW
# =============================================================================

def on_event(e: HistoryEntry):
    if e.entry_type == "tool_call":
        print(f"  → {e.content}")

print("=" * 70)
print("STAGE 1: EXPLORE")
print("=" * 70)

explorer = RLHarness(
    provider=ProviderConfig(name="gemini", thinking_level="HIGH"),
    enable_search=True,
    on_event=on_event,
)

explore_result = explorer.run_single(task=TASK, mode="explore", num_takes=3)
takes = [t.strip() for t in explore_result.answer.split("===") if t.strip()]
print(f"\n✓ Generated {len(takes)} strategic directions\n")

# -----------------------------------------------------------------------------

print("=" * 70)
print("STAGE 2: SELECT")
print("=" * 70)

selector = GeminiProvider()
selection = selector.generate(
    prompt=f"""
You are Apple's Chief Strategy Officer. Review these NPI directions:

{explore_result.answer}

Pick ONE direction (or synthesize). Output only:
SELECTED: [1, 2, or 3]
RATIONALE: [one sentence why]
""",
    system="Be decisive. One direction only.",
)

print(f"\n{selection}\n")

# Extract the full content of the selected take
selected_idx = None
for i in range(1, len(takes) + 1):
    if f"SELECTED: {i}" in selection or f"TAKE {i}" in selection.upper():
        selected_idx = i - 1
        break
selected_take = takes[selected_idx] if selected_idx is not None else takes[0]

# -----------------------------------------------------------------------------

print("=" * 70)
print("STAGE 3: EXECUTE (standard mode)")
print("=" * 70)

executor = RLHarness(
    provider=ProviderConfig(name="gemini", thinking_level="HIGH"),
    enable_search=True,
    on_event=on_event,
)

# Pass task + full selected take as context
task_with_direction = f"""{TASK}

Strategic Direction (selected from exploration):
{selection}

Full Context of Selected Direction:
{selected_take}
"""

final = executor.run_single(task=task_with_direction, mode="standard")

# =============================================================================
# OUTPUT
# =============================================================================

print("\n" + "=" * 70)
print("iPHONE 18 NPI PLAN")
print("=" * 70)
print(final.answer)

# Save
output = Path("examples/outputs")
output.mkdir(parents=True, exist_ok=True)
(output / "iphone18_npi.md").write_text(f"""# iPhone 18 NPI Plan

## Task
{TASK}

---

## Stage 1: Exploration
{chr(10).join(f'### Direction {i+1}{chr(10)}{t}{chr(10)}' for i, t in enumerate(takes))}

---

## Stage 2: Selection
{selected}

---

## Stage 3: Final NPI Document
{final.answer}

---

## Generated Rubric
{final.rubric}
""")

print(f"\n✓ Saved to examples/outputs/iphone18_npi.md")
print(f"""
Summary:
  • Explored {len(takes)} directions
  • Model selected direction autonomously
  • Standard mode: model created its own brief & rubric
  • Final document: {len(final.answer.split())} words
""")
