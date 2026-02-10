import os
import traceback
from dotenv import load_dotenv
load_dotenv()

from verif import RLHarness, ProviderConfig

task = """Analyze the power dynamics among the Olympian gods in Greek mythology.
Cover the division of domains after the Titanomachy, the tensions between Zeus and other major deities
(Poseidon, Hera, Athena, Apollo), and how these rivalries shaped key mythological narratives
(Trojan War, Odyssey, founding myths of city-states).
Include primary source references where possible (Iliad, Theogony, Homeric Hymns)."""

events_original = []
events_resumed = []

def on_event_original(entry):
    meta_str = f" | meta={entry.metadata}" if entry.metadata else ""
    print(f"[ORIG][{entry.entry_type}]{meta_str}: {entry.content[:120]}...")
    events_original.append(entry)

def on_event_resumed(entry):
    meta_str = f" | meta={entry.metadata}" if entry.metadata else ""
    print(f"[FORK][{entry.entry_type}]{meta_str}: {entry.content[:120]}...")
    events_resumed.append(entry)

config = ProviderConfig(name="gemini", thinking_level="LOW")
harness = RLHarness(
    provider=config,
    enable_search=True,
    enable_bash=False,
    enable_code=False,
    on_event=on_event_original,
    stream=True,
    stream_subagents=True,
)

print(f"Task: {task[:80]}...")
print("=" * 60)
print("PHASE 1: ORIGINAL RUN (checkpoint=True)")
print("=" * 60)

error = None
result_original = None
result_resumed = None

try:
    result_original = harness.run_single(task, checkpoint=True)
except Exception as e:
    error = f"**ORIGINAL RUN FATAL**\n```\n{traceback.format_exc()}\n```"

# Show checkpoints
print("\n" + "=" * 60)
print("CHECKPOINTS CAPTURED")
print("=" * 60)
for snap_id, snap in sorted(harness.snapshots.items()):
    state_summary = {k: (v[:60] + "..." if isinstance(v, str) and len(v) > 60 else v) for k, v in snap.state.items()}
    print(f"  {snap_id} | step={snap.step} | history_idx={snap.history_index} | rubric={'SET' if snap.state.get('rubric') else 'None'}")

# Fork from after brief+rubric created, inject feedback to expand scope to demigods
# This tests whether the model can adapt an existing research trajectory
if not error and len(harness.snapshots) >= 3:
    checkpoint_ids = sorted(harness.snapshots.keys())
    # Fork late — after research is done, just before verification/submission
    # Step 7 means the model has already done brief, rubric, subagent research
    target_step = 7
    resume_id = None
    for cid in checkpoint_ids:
        if harness.snapshots[cid].step == target_step:
            resume_id = cid
            break
    # Fallback to last available checkpoint if step 7 doesn't exist
    if not resume_id:
        resume_id = checkpoint_ids[-1]

    print(f"\n{'=' * 60}")
    print(f"PHASE 2: FORKED RUN from {resume_id}")
    print(f"Rubric at fork point: {'EXISTS' if harness.snapshots[resume_id].state.get('rubric') else 'None'}")
    print(f"{'=' * 60}")

    harness.provider.on_log = on_event_resumed

    feedback = (
        "The analysis so far focuses only on the gods themselves. Add a substantial section analyzing "
        "demigods (Heracles, Perseus, Achilles, Theseus) as agents of divine will in the mortal world. "
        "Cover how gods used their mortal children as proxies in their rivalries — e.g. Athena championing "
        "Perseus, Hera persecuting Heracles, Thetis manipulating Zeus for Achilles. "
        "This should be a structural addition, not a footnote — treat demigods as the mechanism through "
        "which Olympian power dynamics actually played out on earth."
    )

    rubric_update = (
        "Add criteria: must include a substantial section analyzing demigods (Heracles, Perseus, "
        "Achilles, Theseus) as operational proxies of Olympian rivalries. Must cover at least 3 specific "
        "god-demigod relationships showing how divine parents/patrons used mortal children to project power."
    )

    try:
        result_resumed = harness.resume(
            checkpoint_id=resume_id,
            feedback=feedback,
            rubric_update=rubric_update,
        )
    except Exception as e:
        error = (error or "") + f"\n\n**RESUME FATAL**\n```\n{traceback.format_exc()}\n```"

# Write output
with open("tests/test_checkpoint_output.md", "w") as f:
    f.write("# Checkpoint Fork Test: Greek Mythology Analysis\n\n")

    if error:
        f.write(f"## Errors\n\n{error}\n\n---\n\n")

    # Original
    f.write("## Original Run: Olympian Power Dynamics\n\n")
    if result_original:
        f.write(f"### Answer\n\n{result_original.answer}\n\n")
        f.write(f"### Rubric\n\n{result_original.rubric}\n\n")
    f.write(f"**Events:** {len(events_original)}\n\n")

    f.write("---\n\n")

    # Checkpoints
    f.write("## Checkpoints\n\n")
    for snap_id, snap in sorted(harness.snapshots.items()):
        f.write(f"- `{snap_id}` step={snap.step} history_idx={snap.history_index} rubric={'SET' if snap.state.get('rubric') else 'None'}\n")
    f.write("\n---\n\n")

    # Forked
    f.write("## Forked Run: Added Demigod Analysis\n\n")
    if result_resumed:
        f.write(f"**Fork point:** `{resume_id}`\n\n")
        f.write(f"**Feedback injected:**\n> {feedback}\n\n")
        f.write(f"**Rubric update:**\n> {rubric_update}\n\n")
        f.write(f"### Answer\n\n{result_resumed.answer}\n\n")
        f.write(f"### Rubric\n\n{result_resumed.rubric}\n\n")
    f.write(f"**Events:** {len(events_resumed)}\n\n")

    f.write("---\n\n")

    # Comparison
    f.write("## Comparison\n\n")
    if result_original and result_resumed:
        orig_has_demigods = any(w in result_original.answer.lower() for w in ["demigod", "heracles", "perseus", "theseus"])
        fork_has_demigods = any(w in result_resumed.answer.lower() for w in ["demigod", "heracles", "perseus", "theseus"])
        fork_has_proxy = "proxy" in result_resumed.answer.lower() or "agent" in result_resumed.answer.lower()
        f.write(f"| Aspect | Original | Forked |\n")
        f.write(f"|--------|----------|--------|\n")
        f.write(f"| Length (chars) | {len(result_original.answer)} | {len(result_resumed.answer)} |\n")
        f.write(f"| Mentions demigods | {'Yes' if orig_has_demigods else 'No'} | {'Yes' if fork_has_demigods else 'No'} |\n")
        f.write(f"| Demigods as proxies/agents | N/A | {'Yes' if fork_has_proxy else 'No'} |\n")
        f.write(f"| Rubric same | — | {'Yes' if result_original.rubric == result_resumed.rubric else 'No (diverged)'} |\n")

print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)
if result_original:
    print(f"Original: {len(result_original.answer)} chars")
if result_resumed:
    print(f"Forked:   {len(result_resumed.answer)} chars")
    fork_has_demigods = any(w in result_resumed.answer.lower() for w in ["demigod", "heracles", "perseus", "theseus"])
    print(f"Fork mentions demigods: {fork_has_demigods}")
print(f"Total checkpoints: {len(harness.snapshots)}")
print("Output: tests/test_checkpoint_output.md")
if error:
    print(f"\nERRORS:\n{error}")
