import os
import traceback
from dotenv import load_dotenv
load_dotenv()

from verif import RLHarness, ProviderConfig

# Same task as test_sdk_openai.py
task = "What do the paternal genes contribute to the developing brain?"

# Event counter for summary
event_counts = {}

def on_event(entry):
    """Count events by type."""
    event_counts[entry.entry_type] = event_counts.get(entry.entry_type, 0) + 1

# Configure harness - Gemini with streaming enabled
config = ProviderConfig(name="gemini", thinking_level="LOW")
harness = RLHarness(
    provider=config,
    enable_search=True,
    enable_bash=False,
    enable_code=False,
    on_event=on_event,
    stream=True,
    stream_subagents=True,
)

print(f"Running task with Gemini (streaming): {task[:50]}...")
print("-" * 50)

try:
    result = harness.run_single(task)
    error = None
except Exception as e:
    result = None
    error = f"**FATAL ERROR**\n```\n{traceback.format_exc()}\n```"

# Save results to markdown (same format as test_sdk_openai.py)
with open("tests/test_streaming_full_output.md", "w") as f:
    if error:
        f.write(f"# Error\n\n{error}\n\n---\n\n")

    if result:
        f.write(f"# Result\n\n")
        f.write(f"## Task\n{result.task}\n\n")
        f.write(f"## Answer\n{result.answer}\n\n")
        f.write(f"## Rubric\n{result.rubric}\n\n")
        f.write("---\n\n")

    # Streaming summary
    f.write("## Streaming Summary\n\n")
    for etype, count in sorted(event_counts.items()):
        f.write(f"- {etype}: {count}\n")
    streaming_count = sum(event_counts.get(t, 0) for t in ("model_chunk", "subagent_chunk", "subagent_start", "subagent_end"))
    f.write(f"\n**Total streaming events:** {streaming_count}\n\n")
    f.write("---\n\n")

    # Add execution trace (same as test_sdk_openai.py)
    f.write(harness.get_history_markdown())

print("Results saved to tests/test_streaming_full_output.md")
if error:
    print("RUN FAILED - see output for details")
else:
    print(f"\nStreaming events: {sum(event_counts.get(t, 0) for t in ('model_chunk', 'subagent_chunk', 'subagent_start', 'subagent_end'))}")
    print(f"\nAnswer preview:\n{result.answer[:500]}...")
