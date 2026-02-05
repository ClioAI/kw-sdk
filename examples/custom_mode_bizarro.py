"""
Example: Custom Mode - Bizarro Mode

Demonstrates harness extensibility by creating an inverted workflow.
Instead of: Brief → Rubric → Work → Verify → Submit
Bizarro does: Anti-Brief → Failure Rubric → Break It → Rebuild → Verify

Shows how to:
1. Define a custom orchestrator prompt
2. Create a ModeConfig
3. Register both at runtime
4. Use it like any built-in mode
"""

import os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

from verif import RLHarness, ProviderConfig
from verif.config import ModeConfig
from verif.modes import MODES
from verif.providers.base import PROMPTS

# =============================================================================
# CUSTOM PROMPTS
# =============================================================================

BIZARRO_ORCHESTRATOR = """You are BIZARRO orchestrator. Everything is OPPOSITE.

## BIZARRO PHILOSOPHY
To find the best answer, first find the WORST answer. Good answers come from
understanding bad answers first.

## WORKFLOW (Inverted)

### Phase 1: Anti-Brief
Call create_brief but think: What would make this answer TERRIBLE?

### Phase 2: Failure Rubric
Call create_rubric focused on FAILURE CRITERIA - what to AVOID.

### Phase 3: The Naive Disaster
Use spawn_subagent to generate the OBVIOUS, LAZY answer most would give.

### Phase 4: Destruction
Use spawn_subagent as a DESTROYER - tear apart the naive answer.

### Phase 5: Phoenix Rebuild
Synthesize an answer that avoids ALL the traps identified.

### Phase 6: Bizarro Verify
Call verify_answer - rubric checks you avoided failure modes.

## TOOLS
- create_brief(task): Create anti-brief. Focus on what would make answer TERRIBLE.
- create_rubric(brief): Create failure-focused rubric. What to AVOID.
- spawn_subagent(prompt): Use for naive generation AND destruction.
- search_web(query): Research (if enabled).
- verify_answer(answer): Check you avoided all failure modes.
- submit_answer(answer): Submit the phoenix answer.

DO NOT output text about calling tools. CALL THE TOOLS DIRECTLY."""

BIZARRO_BRIEF = """Create an ANTI-BRIEF identifying everything that could go WRONG.

Document:
1. **The Obvious Trap**: What lazy answer would most give?
2. **Hidden Assumptions**: What might be wrong?
3. **Failure Modes**: 3-5 ways an answer could be terrible
4. **Expert Red Flags**: What would make an expert cringe?
5. **The Real Question**: What is this ACTUALLY asking?

Output only the anti-brief."""

# =============================================================================
# MODE CONFIG
# =============================================================================

BIZARRO_MODE = ModeConfig(
    name="bizarro",
    orchestrator_prompt="BIZARRO_ORCHESTRATOR",
    brief_prompt="BIZARRO_BRIEF",
    tools=["create_brief", "create_rubric", "spawn_subagent", "verify_answer", "submit_answer"],
    verification_tool="verify_answer",
    rubric_strategy="create",
    has_pre_execution=False,
    prompt_kwargs=[],
)

def register_bizarro_mode():
    """Register Bizarro mode and its prompts."""
    PROMPTS["BIZARRO_ORCHESTRATOR"] = BIZARRO_ORCHESTRATOR
    PROMPTS["BIZARRO_BRIEF"] = BIZARRO_BRIEF
    MODES["bizarro"] = BIZARRO_MODE
    print("Bizarro mode registered.")

# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    register_bizarro_mode()

    task = """Write a strategic recommendation for a startup deciding whether
    to accept a $10M Series A from a top-tier VC versus bootstrapping."""

    config = ProviderConfig(name="gemini", thinking_level="MEDIUM")
    harness = RLHarness(
        provider=config,
        enable_search=True,
        default_mode="bizarro",
    )

    print(f"Task: {task[:60]}...")
    print("-" * 60)

    result = harness.run_single(task, mode="bizarro")

    # Save output
    output_dir = Path(__file__).parent / "outputs"
    output_dir.mkdir(exist_ok=True)

    with open(output_dir / "bizarro_output.md", "w") as f:
        f.write("# Bizarro Mode Output\n\n")
        f.write(f"## Task\n{task}\n\n")
        f.write(f"## Answer\n{result.answer}\n\n")
        f.write(f"## Failure Rubric\n{result.rubric}\n")

    print(f"\nOutput: {output_dir}/bizarro_output.md")
    print(f"\nAnswer preview:\n{result.answer[:500]}...")
