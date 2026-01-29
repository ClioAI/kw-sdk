import os
import traceback
from dotenv import load_dotenv
load_dotenv()

from verif import RLHarness, ProviderConfig

# Simple task that will trigger subagents
task = "What is the capital of France? Use search to verify."

# Event logger to track all streaming events
events = []

def on_event(entry):
    """Log all events with their types and metadata."""
    meta_str = f" | meta={entry.metadata}" if entry.metadata else ""
    print(f"[{entry.entry_type}]{meta_str}: {entry.content[:100]}...")
    events.append(entry)

# Configure harness - Gemini with streaming enabled
config = ProviderConfig(name="gemini", thinking_level="LOW")
harness = RLHarness(
    provider=config,
    enable_search=True,
    enable_bash=False,
    enable_code=False,
    on_event=on_event,
    stream=True,           # Enable orchestrator streaming
    stream_subagents=True, # Enable subagent streaming
)

print(f"Running task with streaming: {task}")
print("-" * 60)

try:
    result = harness.run_single(task)
    error = None
except Exception as e:
    result = None
    error = f"**FATAL ERROR**\n```\n{traceback.format_exc()}\n```"

# Analyze events
print("\n" + "=" * 60)
print("EVENT SUMMARY")
print("=" * 60)

event_counts = {}
for e in events:
    event_counts[e.entry_type] = event_counts.get(e.entry_type, 0) + 1

for etype, count in sorted(event_counts.items()):
    print(f"  {etype}: {count}")

# Check for streaming-specific events
streaming_events = [e for e in events if e.entry_type in ("model_chunk", "subagent_chunk", "subagent_start", "subagent_end")]
print(f"\nStreaming events: {len(streaming_events)}")

# Check subagent IDs
subagent_ids = set()
for e in events:
    if e.metadata and "subagent_id" in e.metadata:
        subagent_ids.add(e.metadata["subagent_id"])
print(f"Unique subagent IDs: {subagent_ids}")

# Save results to markdown
with open("tests/test_streaming_output.md", "w") as f:
    f.write("# Streaming Test Results\n\n")

    if error:
        f.write(f"## Error\n\n{error}\n\n---\n\n")

    f.write("## Event Summary\n\n")
    for etype, count in sorted(event_counts.items()):
        f.write(f"- {etype}: {count}\n")

    f.write(f"\n**Streaming events:** {len(streaming_events)}\n")
    f.write(f"**Unique subagent IDs:** {subagent_ids}\n\n")

    if result:
        f.write(f"## Result\n\n")
        f.write(f"### Task\n{result.task}\n\n")
        f.write(f"### Answer\n{result.answer}\n\n")

    f.write("---\n\n")
    f.write("## Full Event Log\n\n")
    for i, e in enumerate(events):
        meta_str = f" `{e.metadata}`" if e.metadata else ""
        content = e.content[:500] + "..." if len(e.content) > 500 else e.content
        f.write(f"### {i+1}. [{e.entry_type}]{meta_str}\n```\n{content}\n```\n\n")

print("\nResults saved to tests/test_streaming_output.md")
if error:
    print("RUN FAILED - see output for details")
else:
    print(f"\nAnswer: {result.answer[:200]}...")
