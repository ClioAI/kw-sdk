"""
Example: Memory as File Attachment

Demonstrates passing institutional knowledge / context as a memory file.
The model uses this context to make informed decisions on complex tasks
that would otherwise require extensive back-and-forth.

Pattern:
1. Maintain a memory file (project context, decisions, constraints)
2. Attach it to prompts for tasks requiring that knowledge
3. Model references memory to ground its reasoning

This is especially useful for:
- Strategic decisions requiring company context
- Technical decisions requiring architecture knowledge
- Prioritization requiring stakeholder understanding
"""

import os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

from verif import RLHarness, ProviderConfig, Attachment, Prompt

# =============================================================================
# LOAD MEMORY FILE
# =============================================================================

EXAMPLES_DIR = Path(__file__).parent
MEMORY_FILE = EXAMPLES_DIR / "utils" / "project_context.md"

memory_attachment = Attachment(
    content=str(MEMORY_FILE.absolute()),
    mime_type="text/markdown",
    name="Project Context (Memory)",
    preview=MEMORY_FILE.read_text(),  # Full context available immediately
)

# =============================================================================
# HARD TASK REQUIRING MEMORY
# =============================================================================

# This task requires understanding:
# - Current technical debt and constraints
# - Stakeholder priorities (CEO vs CTO vs VP Sales)
# - Customer segment economics
# - Competitive positioning
# - Pending decisions and deadlines

task_text = """You are a strategic advisor to TechFlow's leadership team.

**Decision Required:** The VP of Sales (James) is pushing hard for native iOS/Android 
SDKs to close two enterprise deals worth $180K ARR combined. The CTO (Marcus) argues 
the team should focus on platform stability (technical debt is causing reliability issues). 
The CEO (Sarah) wants to prioritize enterprise growth.

Using the attached project context, provide a recommendation that:

1. **Analyzes the trade-offs** between the three paths:
   - Path A: Prioritize native mobile SDKs
   - Path B: Prioritize platform stability sprint
   - Path C: Split the team (parallel execution)

2. **Quantifies the impact** using data from the context:
   - Revenue implications
   - Churn/reliability risks
   - Opportunity costs

3. **Makes a clear recommendation** with:
   - What to do in the next 6 weeks
   - How to communicate the decision to each stakeholder
   - What to explicitly deprioritize and why

Be specific. Reference actual numbers, dates, and stakeholder concerns from the context.
"""

prompt: Prompt = [task_text, memory_attachment]

# =============================================================================
# EVENT HANDLER
# =============================================================================

def on_event(entry):
    """Print key events."""
    etype = entry.entry_type
    content = entry.content[:100].replace('\n', ' ')
    
    if etype == "tool_call":
        print(f"  → {content}...")
    elif etype == "model":
        # Show when model is reasoning
        if "rubric" in content.lower():
            print(f"  📋 Creating evaluation criteria...")
        elif "brief" in content.lower():
            print(f"  📝 Formalizing requirements...")

# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("WITH MEMORY EXAMPLE")
    print("=" * 60)
    print(f"Memory file: {MEMORY_FILE}")
    print(f"Memory size: {len(MEMORY_FILE.read_text())} chars")
    print("-" * 60)
    print("Task: Strategic SDK vs Stability decision")
    print("-" * 60)

    config = ProviderConfig(name="gemini", thinking_level="MEDIUM")

    harness = RLHarness(
        provider=config,
        enable_search=True,  # Allow market research if needed
        on_event=on_event,
    )

    result = harness.run_single(prompt)

    # Save output
    output_dir = EXAMPLES_DIR / "outputs"
    output_dir.mkdir(exist_ok=True)

    with open(output_dir / "with_memory_output.md", "w") as f:
        f.write("# With Memory Example Output\n\n")
        f.write("## Pattern\n")
        f.write("Pass institutional knowledge as file attachment for context-heavy decisions.\n\n")
        f.write("## Task\n")
        f.write(task_text + "\n\n")
        f.write("## Memory File Used\n")
        f.write(f"`{MEMORY_FILE.name}` ({len(MEMORY_FILE.read_text())} chars)\n\n")
        f.write("## Answer\n")
        f.write(result.answer + "\n\n")
        f.write("## Rubric\n")
        f.write(result.rubric + "\n")

    print(f"\nOutput: {output_dir}/with_memory_output.md")
    print(f"\n{'=' * 60}")
    print("RECOMMENDATION")
    print("=" * 60)
    print(result.answer[:1500] + "..." if len(result.answer) > 1500 else result.answer)

# =============================================================================
# THE PATTERN
# =============================================================================
#
# Memory files are useful for:
#
# 1. PROJECT CONTEXT
#    - Architecture decisions and rationale
#    - Technical debt inventory
#    - Team structure and responsibilities
#
# 2. DOMAIN KNOWLEDGE
#    - Industry terminology
#    - Regulatory requirements
#    - Competitive intelligence
#
# 3. HISTORICAL DECISIONS
#    - Past decisions and outcomes
#    - Lessons learned
#    - Rejected alternatives
#
# 4. STAKEHOLDER CONTEXT
#    - Priorities and concerns
#    - Communication preferences
#    - Political dynamics
#
# Keep memory files:
# - Up to date (review monthly)
# - Structured (headings, tables)
# - Factual (numbers, dates, names)
# - Concise (remove stale info)
