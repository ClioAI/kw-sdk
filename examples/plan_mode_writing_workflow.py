"""
Plan Mode Example - Writing Workflow Plan (Auto-Generated Rubric)

WHAT THIS DEMONSTRATES:
- Plan mode used as a repeatable writing process/playbook
- Plan written as a phased workflow (Foundation → Structure → Draft → Refine)
- Real-time streaming events (model chunks + subagent chunks)
- No rubric provided: harness auto-creates one from the plan

EXTRA SETUP NEEDED:
- .env file with API keys
- mode="plan" in run_single()
- plan=PLAN (REQUIRED)
- DO NOT pass rubric - let it auto-create
"""

import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from verif import RLHarness, HistoryEntry
from verif.config import ProviderConfig


events: list[HistoryEntry] = []
event_counts: dict[str, int] = {}


def on_event(event: HistoryEntry):
    """Stream key events to console for progress visibility."""
    events.append(event)
    event_counts[event.entry_type] = event_counts.get(event.entry_type, 0) + 1

    if event.entry_type == "model_chunk":
        sys.stdout.write(event.content)
        sys.stdout.flush()
        return

    if event.entry_type == "subagent_chunk":
        sys.stdout.write(".")
        sys.stdout.flush()
        return

    if event.entry_type in ("subagent_start", "subagent_end"):
        meta = f" {event.metadata}" if event.metadata else ""
        print(f"\n[{event.entry_type}]{meta} {event.content[:140]}...")
        return

    if event.entry_type in ("tool_call", "tool_response", "tool_error"):
        print(f"\n[{event.entry_type}] {event.content[:160]}...")
        return

    if event.entry_type in ("system", "model", "user"):
        print(f"\n[{event.entry_type}] {event.content[:160]}...")


TASK = """
Write a ~1,200–1,600 word article for CTOs and engineering leaders on:

"Why most teams don't get productivity gains from AI coding assistants."

Constraints:
- Use web search to sanity-check the "conventional wisdom" section (no quotes; just representative mentions)
- The article must have ONE central insight (a single reframe)
- Address skeptical objections preemptively
- Include 2–3 concrete examples (realistic, anonymized is fine)
- Humanize the stakes (who gets hurt when this goes wrong)
- End with a lingering implication (no summary, no CTA)
"""


PLAN = """
## The Process (follow in order)

### Phase 1: Foundation
**Step 1 - Research the landscape**
Understand what's already written. What's the conventional wisdom? What do McKinsey/BCG/HBR say? What are the clichés?

**Step 2 - Find the gap**
What does everyone say that's actually wrong or incomplete? What do practitioners know that consultants miss? Where's the insight that isn't obvious?

**Step 3 - Identify your one key insight**
The article needs ONE central argument. Not a list of tips. What's the single reframe that changes how readers think?

### Phase 2: Structure
**Step 4 - Map the objections**
What will skeptical readers think? "That won't work because..." or "But what about..." Address these preemptively.

**Step 5 - Outline the arc**
Opening hook → Problem articulation → Conventional wisdom → Why it's wrong → Your insight → Evidence → Implications → Close

**Step 6 - Write the opening separately**
First 100 words determine if anyone reads further. Write 3 versions. Pick the one that creates tension or curiosity.

### Phase 3: Draft
**Step 7 - Write ugly first**
Get the ideas down. Don't polish. Don't edit. Momentum over perfection.

**Step 8 - Add specific examples**
Abstract advice is forgettable. "Company X tried Y and Z happened" is memorable. Real > hypothetical.

**Step 9 - Humanize the stakes**
Who suffers when this goes wrong? Not "shareholder value" - the CTO who gets fired, the team that gets burned out, the customers who get ignored.

### Phase 4: Refine
**Step 10 - Cut ruthlessly**
If a paragraph doesn't serve the central argument, delete it. If a sentence doesn't serve the paragraph, delete it.

**Step 11 - Read aloud**
Awkward sentences reveal themselves when spoken. If you stumble, rewrite.

**Step 12 - Nail the close**
Don't summarize. Don't add a CTA. End with the implication that lingers. What should they do Monday morning?
"""


harness = RLHarness(
    provider=ProviderConfig(name="gemini", thinking_level="MEDIUM"),
    enable_search=True,
    enable_bash=False,
    enable_code=False,
    on_event=on_event,
    stream=True,
    stream_subagents=True,
)


print("=" * 60)
print("PLAN MODE EXECUTION (WRITING WORKFLOW)")
print("=" * 60)
print(f"\nTask: {TASK.strip()[:80]}...")
print(f"\nPlan: {len(PLAN.strip().splitlines())} lines of workflow")
print("Rubric: Auto-generated from plan (not provided by user)")
print("-" * 60)

try:
    result = harness.run_single(
        task=TASK,
        mode="plan",
        plan=PLAN,
        # rubric NOT provided - will be auto-created
    )
except Exception as e:
    print(f"\n❌ Error during execution: {e}", file=sys.stderr)
    sys.exit(1)

if not result.answer:
    print("\n❌ No answer was generated", file=sys.stderr)
    sys.exit(1)


print("\n" + "=" * 60)
print("ARTICLE OUTPUT")
print("=" * 60)
print(result.answer)

print("\n" + "=" * 60)
print("AUTO-GENERATED RUBRIC")
print("=" * 60)
print(result.rubric)

print("\n" + "=" * 60)
print("EVENT SUMMARY")
print("=" * 60)
for entry_type, count in sorted(event_counts.items()):
    print(f"  {entry_type}: {count}")
streaming_total = sum(
    event_counts.get(t, 0) for t in ("model_chunk", "subagent_chunk", "subagent_start", "subagent_end")
)
print(f"\nTotal streaming events: {streaming_total}")


output_dir = Path("examples/outputs")
output_dir.mkdir(parents=True, exist_ok=True)

output_file = output_dir / "plan_mode_writing_workflow_output.md"
with open(output_file, "w") as f:
    f.write("# Plan Mode Example - Writing Workflow (No Rubric)\n\n")
    f.write("## Task\n")
    f.write(f"{TASK.strip()}\n\n")
    f.write("## Plan Provided\n")
    f.write(f"{PLAN.strip()}\n\n")
    f.write("---\n\n")
    f.write("## Generated Article\n\n")
    f.write(f"{result.answer}\n\n")
    f.write("---\n\n")
    f.write("## Auto-Generated Rubric\n\n")
    f.write(f"{result.rubric}\n\n")
    f.write("---\n\n")
    f.write("## Execution Trace\n\n")
    f.write(harness.get_history_markdown())

print(f"\n✓ Full output saved to {output_file}")
