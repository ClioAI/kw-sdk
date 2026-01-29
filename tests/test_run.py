import os
import traceback
from dotenv import load_dotenv
load_dotenv()

from verif.harness import RLHarness

evalset2 = [
    {
        "question": "What do the paternal genes contribute to the developing brain?",
        "answer": "Checking if this works."
    }
]

harness = RLHarness(provider="gemini", enable_search=True)

try:
    results = harness.run_eval(evalset2)
    error = None
except Exception as e:
    results = []
    error = f"**FATAL ERROR**\n```\n{traceback.format_exc()}\n```"

# Save results to markdown
with open("output_genes.md", "w") as f:
    if error:
        f.write(f"# Error\n\n{error}\n\n---\n\n")

    for i, r in enumerate(results):
        f.write(f"# Result {i+1}\n\n")
        f.write(f"## Task\n{r.task}\n\n")
        f.write(f"## Answer\n{r.answer}\n\n")
        f.write(f"## Rubric\n{r.rubric}\n\n")
        f.write("---\n\n")

    # Add execution trace (even on error)
    f.write(harness.get_history_markdown())

print("Results saved to output.md")
if error:
    print("RUN FAILED - see output.md for details")
