import traceback
from dotenv import load_dotenv
load_dotenv()

from verif import RLHarness, ProviderConfig
from verif.providers.base import HistoryEntry

# Track all events
events = []

def on_event(entry: HistoryEntry):
    """Log events with type and metadata."""
    prefix = {
        "user": "📝", "model": "🤖", "thinking": "💭", "tool_call": "🔧",
        "tool_response": "📥", "tool_error": "❌", "system": "⚙️",
        "model_chunk": "▶️", "subagent_chunk": "▸",
    }.get(entry.entry_type, "•")
    meta_str = f" | {entry.metadata}" if entry.metadata else ""
    content = entry.content[:150] + "..." if len(entry.content) > 150 else entry.content
    print(f"{prefix} [{entry.entry_type}]{meta_str}: {content}")
    events.append(entry)

# Test task
task = "What are the key differences between TCP and UDP protocols?"

# Configure harness with streaming + search
config = ProviderConfig(name="gemini")
harness = RLHarness(
    provider=config,
    enable_search=True,
    enable_bash=False,
    enable_code=False,
    on_event=on_event,
    stream=True,
    stream_subagents=True,
)

print("=" * 60)
print("PHASE 1: Initial run_single()")
print("=" * 60)
print(f"Task: {task}")
print("-" * 60)

result = None
iterate_result = None
iterate_result2 = None

try:
    result = harness.run_single(task)
    print("\n" + "=" * 60)
    print("INITIAL RESULT")
    print("=" * 60)
    print(f"Answer length: {len(result.answer)} chars")
    print(f"Answer preview:\n{result.answer[:400]}...")
except Exception as e:
    print(f"FATAL ERROR in run_single:\n{traceback.format_exc()}")

if result:
    events.clear()  # Reset for phase 2

    print("\n" + "=" * 60)
    print("PHASE 2: iterate() with feedback")
    print("=" * 60)

    feedback = "Add a comparison table and include real-world use cases for each protocol."
    print(f"Feedback: {feedback}")
    print("-" * 60)

    try:
        iterate_result = harness.iterate(
            task=task,
            answer=result.answer,
            rubric=result.rubric,
            feedback=feedback,
        )
        print("\n" + "=" * 60)
        print("ITERATE RESULT (feedback only)")
        print("=" * 60)
        print(f"Answer length: {len(iterate_result.answer)} chars")
        print(f"Answer preview:\n{iterate_result.answer[:400]}...")
    except Exception as e:
        print(f"ERROR in iterate (feedback):\n{traceback.format_exc()}")

    events.clear()  # Reset for phase 3

    print("\n" + "=" * 60)
    print("PHASE 3: iterate() with rubric_update")
    print("=" * 60)

    rubric_update = "Must include: security considerations for each protocol"
    print(f"Rubric update: {rubric_update}")
    print("-" * 60)

    try:
        iterate_result2 = harness.iterate(
            task=task,
            answer=iterate_result.answer if iterate_result else result.answer,
            rubric=iterate_result.rubric if iterate_result else result.rubric,
            rubric_update=rubric_update,
        )
        print("\n" + "=" * 60)
        print("ITERATE RESULT (rubric update)")
        print("=" * 60)
        print(f"Answer length: {len(iterate_result2.answer)} chars")
        print(f"Answer preview:\n{iterate_result2.answer[:400]}...")
    except Exception as e:
        print(f"ERROR in iterate (rubric_update):\n{traceback.format_exc()}")

# Save results to markdown
with open("tests/test_iterate_output.md", "w") as f:
    f.write("# Iterate Test Results\n\n")

    f.write("## Configuration\n")
    f.write("- Provider: gemini\n")
    f.write("- Streaming: enabled\n")
    f.write("- Search: enabled\n\n")

    f.write("---\n\n")

    # Phase 1
    f.write("## Phase 1: run_single()\n\n")
    if result:
        f.write(f"**Task:** {result.task}\n\n")
        f.write(f"**Answer ({len(result.answer)} chars):**\n\n{result.answer}\n\n")
        f.write(f"**Rubric:**\n\n{result.rubric}\n\n")
    else:
        f.write("FAILED\n\n")

    f.write("---\n\n")

    # Phase 2
    f.write("## Phase 2: iterate(feedback)\n\n")
    f.write(f"**Feedback:** {feedback}\n\n")
    if iterate_result:
        f.write(f"**Answer ({len(iterate_result.answer)} chars):**\n\n{iterate_result.answer}\n\n")
    else:
        f.write("FAILED\n\n")

    f.write("---\n\n")

    # Phase 3
    f.write("## Phase 3: iterate(rubric_update)\n\n")
    f.write(f"**Rubric Update:** {rubric_update}\n\n")
    if iterate_result2:
        f.write(f"**Answer ({len(iterate_result2.answer)} chars):**\n\n{iterate_result2.answer}\n\n")
        f.write(f"**Updated Rubric:**\n\n{iterate_result2.rubric}\n\n")
    else:
        f.write("FAILED\n\n")

    f.write("---\n\n")

    # Final history from last phase
    f.write("## Execution History (Phase 3)\n\n")
    if iterate_result2:
        for i, entry in enumerate(iterate_result2.history):
            meta_str = f" `{entry.metadata}`" if entry.metadata else ""
            content = entry.content[:800] + "..." if len(entry.content) > 800 else entry.content
            f.write(f"### {i+1}. [{entry.entry_type}]{meta_str}\n```\n{content}\n```\n\n")

print("\n" + "=" * 60)
print("TEST COMPLETE")
print("=" * 60)
print("Results saved to tests/test_iterate_output.md")
