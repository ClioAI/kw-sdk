"""
Checkpointing & Resume: Fork an Execution Mid-Run

WHAT THIS DEMONSTRATES:
- checkpoint=True saves state at every orchestrator step
- You can inspect what the model has done so far at each checkpoint
- Resume from any checkpoint with new feedback + rubric updates
- The resumed run continues from that point — no re-execution of prior steps

WHY THIS IS USEFUL:
Imagine you kick off a research task. The model does brief → rubric → 3 subagent
searches → starts drafting. You look at the intermediate state and realize: "Good
research, but I want it to also cover X." Instead of re-running from scratch, you
fork from the checkpoint after research completed, inject your feedback, and the
model picks up from there — with all prior context intact.

This is the "what if I changed my mind at step 5?" pattern.

FLOW:
┌──────────────────────────────────────────────────────────────┐
│  PHASE 1: RUN WITH CHECKPOINTING                             │
│  → run_single(task, checkpoint=True)                         │
│  → Snapshots saved at every orchestrator step                │
└──────────────────────────────────────────────────────────────┘
                          ↓
┌──────────────────────────────────────────────────────────────┐
│  INSPECT CHECKPOINTS                                          │
│  → See what state (brief, rubric, tools called) at each step │
│  → Pick a fork point                                         │
└──────────────────────────────────────────────────────────────┘
                          ↓
┌──────────────────────────────────────────────────────────────┐
│  PHASE 2: RESUME FROM CHECKPOINT                              │
│  → Inject feedback: "also cover demigods as proxies"         │
│  → Inject rubric_update: new criteria merged into rubric     │
│  → Model continues from fork point with updated direction    │
└──────────────────────────────────────────────────────────────┘

Run: PYTHONPATH=. python examples/with_checkpointing.py
"""

from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from verif import RLHarness, HistoryEntry
from verif.config import ProviderConfig


# =============================================================================
# EVENT HANDLER
# =============================================================================

events_phase1: list[HistoryEntry] = []
events_phase2: list[HistoryEntry] = []

def on_event_phase1(event: HistoryEntry):
    """Stream key events during original run."""
    events_phase1.append(event)
    if event.entry_type in ("tool_call", "tool_response"):
        print(f"  [{event.entry_type}] {event.content[:120]}...")
    elif event.entry_type == "system":
        print(f"  [system] {event.content[:120]}...")

def on_event_phase2(event: HistoryEntry):
    """Stream key events during resumed run."""
    events_phase2.append(event)
    if event.entry_type in ("tool_call", "tool_response"):
        print(f"  [FORK][{event.entry_type}] {event.content[:120]}...")
    elif event.entry_type == "system":
        print(f"  [FORK][system] {event.content[:120]}...")


# =============================================================================
# TASK
# =============================================================================

TASK = """Analyze the power dynamics among the Olympian gods in Greek mythology.

Cover:
- The division of domains after the Titanomachy
- Tensions between Zeus and other major deities (Poseidon, Hera, Athena, Apollo)
- How these rivalries shaped key mythological narratives (Trojan War, Odyssey, city-state founding myths)

Include primary source references where possible (Iliad, Theogony, Homeric Hymns)."""


# =============================================================================
# PHASE 1: ORIGINAL RUN WITH CHECKPOINTING
# =============================================================================

print("=" * 70)
print("PHASE 1: RUN WITH CHECKPOINTING")
print("=" * 70)
print(f"\nTask: {TASK.strip()[:80]}...")
print("-" * 70)

harness = RLHarness(
    provider=ProviderConfig(name="gemini", thinking_level="LOW"),
    enable_search=True,
    on_event=on_event_phase1,
    stream=True,
    stream_subagents=True,
)

result_original = harness.run_single(TASK, checkpoint=True)

print(f"\n--- Original answer: {len(result_original.answer)} chars ---")
print(result_original.answer[:500] + "...")


# =============================================================================
# INSPECT CHECKPOINTS
# =============================================================================

print("\n" + "=" * 70)
print("CHECKPOINTS CAPTURED")
print("=" * 70)
print(f"Total: {len(harness.snapshots)} snapshots\n")

for snap_id, snap in sorted(harness.snapshots.items()):
    rubric_status = "SET" if snap.state.get("rubric") else "—"
    brief_status = "SET" if snap.state.get("brief") else "—"
    print(f"  {snap_id}")
    print(f"    step={snap.step}  history_idx={snap.history_index}  rubric={rubric_status}  brief={brief_status}")

# Pick a fork point: after research is done (rubric exists, several steps in)
# We want to fork late enough that research happened, but before final submission
checkpoint_ids = sorted(harness.snapshots.keys())
fork_id = None
for cid in reversed(checkpoint_ids):
    snap = harness.snapshots[cid]
    # Fork from a point where rubric exists and we're past the early steps
    if snap.state.get("rubric") and snap.step >= 5:
        fork_id = cid
        break

if not fork_id:
    fork_id = checkpoint_ids[-1]  # fallback to last

print(f"\nSelected fork point: {fork_id}")
print(f"  Step {harness.snapshots[fork_id].step}, rubric={'exists' if harness.snapshots[fork_id].state.get('rubric') else 'none'}")


# =============================================================================
# PHASE 2: RESUME WITH NEW DIRECTION
# =============================================================================

print("\n" + "=" * 70)
print(f"PHASE 2: RESUME FROM {fork_id}")
print("=" * 70)

# The original analysis focused on Olympian gods only.
# We want to expand scope: demigods as proxies of divine power.
FEEDBACK = (
    "The analysis focuses only on the gods themselves. Add a substantial section "
    "analyzing demigods (Heracles, Perseus, Achilles, Theseus) as agents of divine "
    "will in the mortal world. Cover how gods used their mortal children as proxies "
    "in their rivalries — e.g. Athena championing Perseus, Hera persecuting Heracles, "
    "Thetis manipulating Zeus for Achilles."
)

RUBRIC_UPDATE = (
    "Must include a section on demigods as operational proxies of Olympian rivalries. "
    "Must cover at least 3 specific god-demigod relationships showing how divine "
    "parents/patrons used mortal children to project power."
)

print(f"\nFeedback: {FEEDBACK[:80]}...")
print(f"Rubric update: {RUBRIC_UPDATE[:80]}...")
print("-" * 70)

# Switch event handler for the resumed run
harness.provider.on_log = on_event_phase2

result_forked = harness.resume(
    checkpoint_id=fork_id,
    feedback=FEEDBACK,
    rubric_update=RUBRIC_UPDATE,
)

print(f"\n--- Forked answer: {len(result_forked.answer)} chars ---")
print(result_forked.answer[:500] + "...")


# =============================================================================
# COMPARISON
# =============================================================================

print("\n" + "=" * 70)
print("COMPARISON: ORIGINAL vs FORKED")
print("=" * 70)

demigod_terms = ["demigod", "heracles", "perseus", "theseus", "achilles"]
orig_has = any(t in result_original.answer.lower() for t in demigod_terms)
fork_has = any(t in result_forked.answer.lower() for t in demigod_terms)
fork_proxy = any(t in result_forked.answer.lower() for t in ["proxy", "proxies", "agent of"])

print(f"""
  {'Aspect':<30} {'Original':<15} {'Forked':<15}
  {'-'*60}
  {'Length (chars)':<30} {len(result_original.answer):<15} {len(result_forked.answer):<15}
  {'Mentions demigods':<30} {'Yes' if orig_has else 'No':<15} {'Yes' if fork_has else 'No':<15}
  {'Demigods as proxies':<30} {'—':<15} {'Yes' if fork_proxy else 'No':<15}
  {'Rubric diverged':<30} {'—':<15} {'Yes' if result_original.rubric != result_forked.rubric else 'No':<15}
  {'Events (original)':<30} {len(events_phase1):<15} {'—':<15}
  {'Events (forked)':<30} {'—':<15} {len(events_phase2):<15}
""")


# =============================================================================
# SAVE OUTPUT
# =============================================================================

output_dir = Path("examples/outputs")
output_dir.mkdir(parents=True, exist_ok=True)

output_file = output_dir / "with_checkpointing_output.md"
with open(output_file, "w") as f:
    f.write("# Checkpointing & Resume Example\n\n")

    f.write("## Task\n\n")
    f.write(f"{TASK.strip()}\n\n")

    f.write("---\n\n")
    f.write("## Phase 1: Original Answer\n\n")
    f.write(f"{result_original.answer}\n\n")
    f.write("### Rubric (auto-generated)\n\n")
    f.write(f"{result_original.rubric}\n\n")

    f.write("---\n\n")
    f.write("## Checkpoints\n\n")
    for snap_id, snap in sorted(harness.snapshots.items()):
        rubric_status = "SET" if snap.state.get("rubric") else "—"
        f.write(f"- `{snap_id}` step={snap.step} rubric={rubric_status}\n")
    f.write("\n")

    f.write("---\n\n")
    f.write(f"## Phase 2: Forked from `{fork_id}`\n\n")
    f.write(f"**Feedback injected:**\n> {FEEDBACK}\n\n")
    f.write(f"**Rubric update:**\n> {RUBRIC_UPDATE}\n\n")
    f.write(f"### Forked Answer\n\n")
    f.write(f"{result_forked.answer}\n\n")
    f.write(f"### Updated Rubric\n\n")
    f.write(f"{result_forked.rubric}\n\n")

    f.write("---\n\n")
    f.write("## Execution Trace (Original)\n\n")
    f.write(harness.get_history_markdown())

print(f"\nOutput saved to {output_file}")
