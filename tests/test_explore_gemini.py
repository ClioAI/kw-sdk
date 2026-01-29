import os
import traceback
from dotenv import load_dotenv
load_dotenv()

from verif import RLHarness, ProviderConfig

# Explore mode task - creative writing with multiple angles
task = """In the climax of Ready Player One, Parzival broadcasts a passionate plea to the Gunters, asking them to fight for the future of the Oasis.

Imagine Nolan Sorrento hacks the feed immediately after and delivers his own counter-speech to the entire population of the Oasis.

Explore different approaches Sorrento could take in this counter-speech. Consider his character, motivations, and what arguments might actually land with the Oasis population."""

# Configure harness - Gemini with search disabled (creative task)
config = ProviderConfig(name="gemini", thinking_level="MEDIUM")
harness = RLHarness(
    provider=config,
    enable_search=False,   # no search needed for creative task
    enable_bash=False,
    enable_code=False,
)

print(f"Running EXPLORE mode (Gemini): {task[:80]}...")
print("-" * 50)

try:
    result = harness.run_single(
        task=task,
        mode="explore",
        num_takes=3,
    )
    error = None
except Exception as e:
    result = None
    error = f"**FATAL ERROR**\n```\n{traceback.format_exc()}\n```"

# Save results to markdown
with open("test_explore_gemini_output.md", "w") as f:
    f.write("# Explore Mode Test (Gemini)\n\n")

    if error:
        f.write(f"## Error\n\n{error}\n\n---\n\n")

    if result:
        f.write(f"## Task\n{result.task}\n\n")
        f.write(f"## Exploration Output\n\n{result.answer}\n\n")
        f.write("---\n\n")

    # Add execution trace
    f.write(harness.get_history_markdown())

print("Results saved to test_explore_gemini_output.md")
if error:
    print("RUN FAILED - see test_explore_gemini_output.md for details")
else:
    print(f"\nExploration preview:\n{result.answer[:1000]}...")
