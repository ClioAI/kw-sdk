import os
import traceback
from dotenv import load_dotenv
load_dotenv()

from verif import RLHarness, ProviderConfig

# Test task
task = "What do the paternal genes contribute to the developing brain?"

# Configure harness - search enabled, file search disabled
config = ProviderConfig(name="gemini", thinking_level="MEDIUM")
harness = RLHarness(
    provider=config,
    enable_search=True,   # web search enabled
    enable_bash=False,    # file search disabled
    enable_code=False,    # code execution disabled
)

print(f"Running task: {task[:50]}...")
print("-" * 50)

try:
    result = harness.run_single(task)
    error = None
except Exception as e:
    result = None
    error = f"**FATAL ERROR**\n```\n{traceback.format_exc()}\n```"

# Save results to markdown
with open("test_sdk_output.md", "w") as f:
    if error:
        f.write(f"# Error\n\n{error}\n\n---\n\n")

    if result:
        f.write(f"# Result\n\n")
        f.write(f"## Task\n{result.task}\n\n")
        f.write(f"## Answer\n{result.answer}\n\n")
        f.write(f"## Rubric\n{result.rubric}\n\n")
        f.write("---\n\n")

    # Add execution trace
    f.write(harness.get_history_markdown())

print("Results saved to test_sdk_output.md")
if error:
    print("RUN FAILED - see test_sdk_output.md for details")
else:
    print(f"\nAnswer preview:\n{result.answer[:500]}...")
