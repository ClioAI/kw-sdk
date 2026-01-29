"""
Test plan mode with Gemini provider.

This test provides a user-defined plan and rubric to the harness,
running execution in plan mode to generate an article.
"""

import os
import traceback
from dotenv import load_dotenv
load_dotenv()

from verif import RLHarness, ProviderConfig

# =============================================================================
# Task Definition
# =============================================================================

TASK = """
Write an article about tracing the lineage of how the dinosaur extinction event 
was discovered. The article should explain the scientific journey from Walter 
Alvarez's discovery in 1980 to the confirmation of the Chicxulub crater.

Written in the style of Matt Levine - dry wit, tangential observations, 
financial metaphors where unexpected, conversational tone, and occasional 
self-aware meta-commentary about the writing itself.

Target length: 800-1200 words.
"""

# =============================================================================
# User-Defined Plan
# =============================================================================

PLAN = """
## Research Phase
1. Research the Walter Alvarez discovery of iridium anomaly (1980)
2. Research the iridium layer significance and extraterrestrial origin hypothesis
3. Research the scientific community's initial skepticism and debate
4. Research the discovery/confirmation of Chicxulub crater (Hildebrand, 1991)
5. Research supporting evidence (shocked quartz, tektites, tsunami deposits)

## Writing Phase
6. Draft introduction with a Matt Levine-style hook (perhaps comparing extinction 
   events to market crashes?)
7. Structure the narrative as a detective story - following the scientific clues
8. Include characteristic Levine tangents and asides
9. Use financial/business metaphors unexpectedly (e.g., "the dinosaurs were 
   experiencing some liquidity issues")
10. Add self-aware meta-commentary about the article itself
11. Conclude with reflection on how science works - building consensus through 
    evidence (like due diligence, perhaps)

## Quality Checks
12. Verify factual accuracy of scientific claims
13. Ensure the Matt Levine voice is consistent throughout
14. Check word count is within 800-1200 range
"""

# =============================================================================
# Evaluation Rubric
# =============================================================================

RUBRIC = """
## Factual Accuracy (25 points)
- [ ] Correctly identifies Walter Alvarez and the iridium anomaly discovery (1980)
- [ ] Accurately describes the iridium layer significance
- [ ] Correctly references Luis Alvarez (father, Nobel laureate physicist)
- [ ] Accurately describes Chicxulub crater discovery and timeline
- [ ] Mentions key supporting evidence (shocked quartz, etc.)

## Matt Levine Style (35 points)
- [ ] Uses dry, understated humor throughout
- [ ] Includes unexpected tangential observations
- [ ] Employs financial/business metaphors in unexpected contexts
- [ ] Has conversational, accessible tone
- [ ] Contains self-aware meta-commentary about the writing
- [ ] Features Levine's characteristic parenthetical asides
- [ ] Avoids taking itself too seriously

## Narrative Structure (20 points)
- [ ] Clear introduction that hooks the reader
- [ ] Logical flow following the scientific discovery timeline
- [ ] Smooth transitions between topics
- [ ] Satisfying conclusion that ties themes together

## Writing Quality (20 points)
- [ ] Word count within 800-1200 range
- [ ] No grammatical errors
- [ ] Clear, engaging prose
- [ ] Appropriate pacing (not rushed, not padded)
"""

# =============================================================================
# Test Execution
# =============================================================================

def main():
    # Configure harness - Gemini in plan mode
    config = ProviderConfig(name="gemini")
    harness = RLHarness(
        provider=config,
        enable_search=True,   # web search enabled for research
        enable_bash=False,    # file search disabled
        enable_code=False,    # code execution disabled
    )

    print(f"Running plan mode test with Gemini")
    print(f"Task: {TASK[:80]}...")
    print("-" * 60)
    print(f"Plan:\n{PLAN[:300]}...")
    print("-" * 60)

    try:
        # Run in plan mode with user-provided plan and rubric
        result = harness.run_single(
            task=TASK,
            mode="plan",
            plan=PLAN,
            rubric=RUBRIC
        )
        error = None
    except Exception as e:
        result = None
        error = f"**FATAL ERROR**\n```\n{traceback.format_exc()}\n```"

    # Save results to markdown
    output_file = "outputs/test_plan_gemini_output.md"
    os.makedirs("outputs", exist_ok=True)
    
    with open(output_file, "w") as f:
        f.write(f"# Plan Mode Test - Gemini\n\n")
        f.write(f"## Task\n{TASK}\n\n")
        f.write(f"## Plan\n{PLAN}\n\n")
        f.write(f"## Rubric\n{RUBRIC}\n\n")
        f.write("---\n\n")
        
        if error:
            f.write(f"# Error\n\n{error}\n\n---\n\n")

        if result:
            f.write(f"# Result\n\n")
            f.write(f"## Answer\n{result.answer}\n\n")
            f.write(f"## Final Rubric\n{result.rubric}\n\n")
            f.write("---\n\n")

        # Add execution trace
        f.write("# Execution History\n\n")
        f.write(harness.get_history_markdown())

    print(f"\nResults saved to {output_file}")
    
    if error:
        print("RUN FAILED - see output file for details")
        return False
    else:
        print(f"\n{'='*60}")
        print("SUCCESS!")
        print(f"{'='*60}")
        print(f"\nAnswer preview:\n{result.answer[:800]}...")
        return True


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
