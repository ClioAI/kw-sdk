"""
Test harness performance - compaction + parallelization.
Task: Same as test_sdk_openai.py with event timestamps for analysis.
"""
import os
import sys
import time
import traceback
import threading
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

# Patch context limit BEFORE importing providers
import verif.providers.base as base_module
base_module.MAX_CONTEXT_TOKENS["gemini"] = 5_000  # 5k limit for testing compaction

from verif import RLHarness, ProviderConfig
from verif.providers.base import HistoryEntry, BaseProvider

# Track timing
start_time = None
event_times = []
tool_exec_times = []  # Granular tool execution timing

# Monkey-patch _execute_tool to add timing
_original_execute_tool = BaseProvider._execute_tool

def _timed_execute_tool(self, name: str, args: dict) -> str:
    thread_id = threading.current_thread().name
    t_start = datetime.now()
    elapsed_start = (t_start - start_time).total_seconds() if start_time else 0
    print(f"\033[93m  >> TOOL START [{thread_id}] +{elapsed_start:6.2f}s: {name}\033[0m")
    sys.stdout.flush()

    result = _original_execute_tool(self, name, args)

    t_end = datetime.now()
    elapsed_end = (t_end - start_time).total_seconds() if start_time else 0
    duration = (t_end - t_start).total_seconds()
    print(f"\033[95m  << TOOL END   [{thread_id}] +{elapsed_end:6.2f}s: {name} ({duration:.2f}s)\033[0m")
    sys.stdout.flush()

    tool_exec_times.append({
        "name": name,
        "thread": thread_id,
        "start": elapsed_start,
        "end": elapsed_end,
        "duration": duration,
    })
    return result

BaseProvider._execute_tool = _timed_execute_tool


def print_event(entry: HistoryEntry):
    """Print harness events with timestamps for performance analysis."""
    global event_times

    now = datetime.now()
    elapsed = (now - start_time).total_seconds() if start_time else 0

    entry_type = entry.entry_type.upper()
    content = entry.content[:300] + "..." if len(entry.content) > 300 else entry.content

    # Track timing
    event_times.append({
        "time": now.isoformat(),
        "elapsed": elapsed,
        "type": entry_type,
        "preview": content[:100],
    })

    # Color coding
    colors = {
        "SYSTEM": "\033[94m",       # Blue
        "MODEL": "\033[92m",        # Green
        "TOOL_CALL": "\033[93m",    # Yellow
        "TOOL_RESPONSE": "\033[95m",# Magenta
        "TOOL_ERROR": "\033[91m",   # Red
        "USER": "\033[96m",         # Cyan
    }
    color = colors.get(entry_type, "")
    reset = "\033[0m" if color else ""

    print(f"\n{color}[+{elapsed:6.2f}s] [{entry_type}]{reset} {content}")
    sys.stdout.flush()


def main():
    global start_time

    # Same task as test_sdk_openai.py
    task = "What do the paternal genes contribute to the developing brain?"

    # Configure harness - OpenAI with search enabled
    config = ProviderConfig(name="gemini", thinking_level="MEDIUM")
    harness = RLHarness(
        provider=config,
        enable_search=True,   # web search enabled
        enable_bash=False,    # file search disabled
        enable_code=False,    # code execution disabled
        max_iterations=30,
        on_event=print_event,
    )

    print(f"Testing compaction + parallelization with OpenAI")
    print(f"Task: {task}")
    print("-" * 60)

    start_time = datetime.now()

    try:
        result = harness.run_single(task)
        error = None
    except Exception as e:
        result = None
        error = f"**FATAL ERROR**\n```\n{traceback.format_exc()}\n```"

    end_time = datetime.now()
    total_elapsed = (end_time - start_time).total_seconds()

    # Save results with timing analysis
    output_file = Path(__file__).parent / "test_parallel_perf_gemini_5k_output.md"
    with open(output_file, "w") as f:
        f.write(f"# Performance Test: Compaction + Parallelization\n\n")
        f.write(f"**Total Time**: {total_elapsed:.2f}s\n")
        f.write(f"**Start**: {start_time.isoformat()}\n")
        f.write(f"**End**: {end_time.isoformat()}\n\n")

        if error:
            f.write(f"## Error\n\n{error}\n\n---\n\n")

        if result:
            f.write(f"## Result\n\n")
            f.write(f"### Task\n{result.task}\n\n")
            f.write(f"### Answer\n{result.answer}\n\n")
            f.write(f"### Rubric\n{result.rubric}\n\n")
            f.write("---\n\n")

        # Granular tool execution timing
        f.write("## Tool Execution Timing (Granular)\n\n")
        f.write("| Start | End | Duration | Thread | Tool |\n")
        f.write("|-------|-----|----------|--------|------|\n")
        for t in tool_exec_times:
            f.write(f"| {t['start']:6.2f}s | {t['end']:6.2f}s | {t['duration']:5.2f}s | {t['thread']} | {t['name']} |\n")
        f.write("\n")

        # Timing analysis
        f.write("## Event Timeline\n\n")
        f.write("| Elapsed | Type | Preview |\n")
        f.write("|---------|------|--------|\n")
        for evt in event_times:
            preview = evt["preview"].replace("|", "\\|").replace("\n", " ")[:60]
            f.write(f"| {evt['elapsed']:6.2f}s | {evt['type']} | {preview} |\n")
        f.write("\n")

        # Add execution trace
        f.write("---\n\n")
        f.write(harness.get_history_markdown())

    print(f"\n{'='*60}")
    print(f"TOTAL TIME: {total_elapsed:.2f}s")
    print(f"Results saved to {output_file}")
    if error:
        print("RUN FAILED - see output file for details")
    else:
        print(f"\nAnswer preview:\n{result.answer[:400]}...")


if __name__ == "__main__":
    main()
