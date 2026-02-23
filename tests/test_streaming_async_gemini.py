import asyncio
import os
import traceback

from dotenv import load_dotenv

load_dotenv()

from verif import AsyncRLHarness, ProviderConfig
from verif.providers import gemini as gemini_provider

# Force the requested model for this test.
gemini_provider.MODEL_ID = "gemini-3-flash-preview"

# Realistic task that should trigger subagent search behavior.
TASK = (
    "Compare the GDP of Japan and Germany in 2024. Which is larger and by how much? "
    "Use multiple searches to find each country's GDP separately and cite source URLs."
)

events = []


def on_event(entry):
    """Capture all emitted events and print a short live preview."""
    meta_str = f" | meta={entry.metadata}" if entry.metadata else ""
    preview = entry.content[:100].replace("\n", " ")
    print(f"[{entry.entry_type}]{meta_str}: {preview}...")
    events.append(entry)


def _event_counts() -> dict[str, int]:
    counts: dict[str, int] = {}
    for e in events:
        counts[e.entry_type] = counts.get(e.entry_type, 0) + 1
    return counts


async def main():
    config = ProviderConfig(name="gemini", thinking_level="LOW")
    harness = AsyncRLHarness(
        provider=config,
        enable_search=True,
        enable_bash=False,
        enable_code=False,
        on_event=on_event,
        stream=True,
        stream_subagents=True,
    )

    print(f"Running async streaming task with Gemini: {TASK}")
    print("-" * 60)

    result = None
    error = None
    try:
        result = await harness.run_single(TASK)
    except Exception:
        error = f"**FATAL ERROR**\n```\n{traceback.format_exc()}\n```"

    counts = _event_counts()
    streaming_events = [
        e for e in events
        if e.entry_type in ("model_chunk", "subagent_chunk", "subagent_start", "subagent_end")
    ]
    subagent_start_count = counts.get("subagent_start", 0)
    subagent_end_count = counts.get("subagent_end", 0)
    subagent_behavior_ok = subagent_start_count > 0 and subagent_end_count > 0
    streaming_behavior_ok = len(streaming_events) > 0
    subagent_ids = set()
    for e in events:
        if e.metadata and "subagent_id" in e.metadata:
            subagent_ids.add(e.metadata["subagent_id"])

    print("\n" + "=" * 60)
    print("EVENT SUMMARY")
    print("=" * 60)
    for event_type, count in sorted(counts.items()):
        print(f"  {event_type}: {count}")
    print(f"\nStreaming events: {len(streaming_events)}")
    print(f"Unique subagent IDs: {subagent_ids}")
    print(f"Subagent behavior respected: {'YES' if subagent_behavior_ok else 'NO'}")

    os.makedirs("tests/outputs", exist_ok=True)
    output_path = "tests/outputs/test_streaming_async_gemini_output.md"
    with open(output_path, "w") as f:
        f.write("# Streaming Test Results (Gemini Async)\n\n")

        if error:
            f.write(f"## Error\n\n{error}\n\n---\n\n")

        f.write("## Event Summary\n\n")
        for event_type, count in sorted(counts.items()):
            f.write(f"- {event_type}: {count}\n")

        f.write(f"\n**Streaming events:** {len(streaming_events)}\n")
        f.write(f"**Unique subagent IDs:** {subagent_ids}\n\n")
        f.write("## Subagent Behavior Checks\n\n")
        f.write(f"- subagent_start events: {subagent_start_count}\n")
        f.write(f"- subagent_end events: {subagent_end_count}\n")
        f.write(f"- streaming events present: {streaming_behavior_ok}\n")
        f.write(f"- subagent behavior respected: {subagent_behavior_ok}\n\n")

        if result:
            f.write("## Result\n\n")
            f.write(f"### Task\n{result.task}\n\n")
            f.write(f"### Answer\n{result.answer}\n\n")
            f.write(f"### Rubric\n{result.rubric}\n\n")

        f.write("---\n\n")
        f.write("## Full Event Log\n\n")
        for i, e in enumerate(events):
            meta_str = f" `{e.metadata}`" if e.metadata else ""
            f.write(f"### {i + 1}. [{e.entry_type}]{meta_str}\n```\n{e.content}\n```\n\n")

        f.write("---\n\n")
        f.write("## Execution Trace\n\n")
        f.write(harness.get_history_markdown())

    print(f"\nResults saved to {output_path}")
    if error:
        print("RUN FAILED")
        print("\nERROR DETAILS")
        print("=" * 60)
        print(error)
    elif result:
        print(f"\nAnswer preview: {result.answer[:200]}...")


if __name__ == "__main__":
    asyncio.run(main())
