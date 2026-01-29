"""
Event Streaming Example - Real-time Execution Monitoring

WHAT THIS DEMONSTRATES:
- Real-time event callbacks
- Tracking subagent execution
- Streaming model output chunks
- Building a custom event log

EXTRA SETUP NEEDED:
- .env file with API keys
- on_event=callback in harness config
- stream=True for orchestrator streaming
- stream_subagents=True for subagent streaming

EVENT TYPES:
- user: User input
- system: System messages
- model: Complete model output
- model_chunk: Streaming model chunk
- tool_call: Tool invocation
- tool_response: Tool result
- tool_error: Tool error
- subagent_start: Subagent spawned
- subagent_chunk: Subagent streaming output
- subagent_end: Subagent complete
"""

import sys
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

from verif import RLHarness, HistoryEntry
from verif.config import ProviderConfig

# =============================================================================
# EVENT TRACKING
# =============================================================================

events = []
subagent_outputs = {}

def on_event(entry: HistoryEntry):
    """
    Handle streaming events in real-time.

    entry.entry_type: Event type (see list above)
    entry.content: Event content
    entry.timestamp: ISO timestamp
    entry.metadata: Optional dict with extra info (e.g., subagent_id)
    """
    events.append(entry)

    # Color coding for terminal output
    COLORS = {
        "system": "\033[94m",      # Blue
        "model": "\033[92m",       # Green
        "model_chunk": "\033[92m", # Green
        "tool_call": "\033[93m",   # Yellow
        "tool_response": "\033[95m", # Magenta
        "tool_error": "\033[91m",  # Red
        "subagent_start": "\033[96m", # Cyan
        "subagent_chunk": "\033[96m", # Cyan
        "subagent_end": "\033[96m",   # Cyan
        "user": "\033[97m",        # White
    }
    RESET = "\033[0m"

    color = COLORS.get(entry.entry_type, "")

    # Handle different event types
    if entry.entry_type == "subagent_start":
        subagent_id = entry.metadata.get("subagent_id", "?") if entry.metadata else "?"
        print(f"\n{color}[SUBAGENT {subagent_id} START]{RESET}")
        print(f"  Instruction: {entry.content[:100]}...")
        subagent_outputs[subagent_id] = []

    elif entry.entry_type == "subagent_chunk":
        subagent_id = entry.metadata.get("subagent_id", "?") if entry.metadata else "?"
        # Accumulate chunks (don't print each one to avoid noise)
        if subagent_id in subagent_outputs:
            subagent_outputs[subagent_id].append(entry.content)
        sys.stdout.write(".")  # Progress indicator
        sys.stdout.flush()

    elif entry.entry_type == "subagent_end":
        subagent_id = entry.metadata.get("subagent_id", "?") if entry.metadata else "?"
        print(f"\n{color}[SUBAGENT {subagent_id} END]{RESET}")
        print(f"  Result: {entry.content[:200]}...")

    elif entry.entry_type == "model_chunk":
        # Stream model output character by character
        sys.stdout.write(entry.content)
        sys.stdout.flush()

    elif entry.entry_type == "tool_call":
        print(f"\n{color}[TOOL CALL]{RESET} {entry.content[:100]}...")

    elif entry.entry_type == "tool_response":
        print(f"{color}[TOOL RESPONSE]{RESET} {entry.content[:150]}...")

    elif entry.entry_type == "tool_error":
        print(f"{color}[TOOL ERROR]{RESET} {entry.content}")

    elif entry.entry_type in ("system", "model"):
        print(f"{color}[{entry.entry_type.upper()}]{RESET} {entry.content[:150]}...")

# =============================================================================
# CONFIGURATION
# =============================================================================

harness = RLHarness(
    provider=ProviderConfig(name="openai", reasoning_effort="medium"),
    enable_search=True,
    enable_bash=False,
    enable_code=False,
    on_event=on_event,
    stream=True,
    stream_subagents=True,
)

# =============================================================================
# EXECUTION
# =============================================================================

task = """
What are the latest developments in nuclear fusion energy?
Search for announcements from the past year about commercial fusion projects.
"""

print("=" * 60)
print("STREAMING EXECUTION")
print("=" * 60)
print(f"Task: {task.strip()}")
print("-" * 60)
print("Real-time events:\n")

try:
    result = harness.run_single(task)
except Exception as e:
    print(f"\n❌ Error during execution: {e}", file=sys.stderr)
    sys.exit(1)

if not result.answer:
    print("\n❌ No answer was generated", file=sys.stderr)
    sys.exit(1)

# =============================================================================
# EVENT ANALYSIS
# =============================================================================

print("\n\n" + "=" * 60)
print("EVENT SUMMARY")
print("=" * 60)

event_counts = {}
for e in events:
    event_counts[e.entry_type] = event_counts.get(e.entry_type, 0) + 1

for etype, count in sorted(event_counts.items()):
    print(f"  {etype}: {count}")

# Streaming-specific events
streaming_events = [e for e in events if e.entry_type in
                    ("model_chunk", "subagent_chunk", "subagent_start", "subagent_end")]
print(f"\nTotal streaming events: {len(streaming_events)}")

# Unique subagent IDs
subagent_ids = set()
for e in events:
    if e.metadata and "subagent_id" in e.metadata:
        subagent_ids.add(e.metadata["subagent_id"])
print(f"Unique subagents spawned: {len(subagent_ids)}")

print("\n" + "=" * 60)
print("FINAL ANSWER")
print("=" * 60)
print(result.answer)

# =============================================================================
# SAVE OUTPUT
# =============================================================================

output_dir = Path("examples/outputs")
output_dir.mkdir(parents=True, exist_ok=True)

output_file = output_dir / "with_streaming_output.md"
with open(output_file, "w") as f:
    f.write("# Streaming Example - Event Log\n\n")
    f.write(f"## Task\n{task}\n\n")
    f.write(f"## Answer\n{result.answer}\n\n")
    f.write("---\n\n")
    f.write("## Event Summary\n\n")
    for etype, count in sorted(event_counts.items()):
        f.write(f"- {etype}: {count}\n")
    f.write("\n---\n\n")
    f.write("## Full Event Log\n\n")
    for i, e in enumerate(events):
        meta_str = f" `{e.metadata}`" if e.metadata else ""
        content = e.content[:300] + "..." if len(e.content) > 300 else e.content
        f.write(f"### {i+1}. [{e.entry_type}]{meta_str}\n```\n{content}\n```\n\n")

print(f"\n✓ Full event log saved to {output_file}")
