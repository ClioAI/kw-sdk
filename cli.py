#!/usr/bin/env python3
"""CLI entry point for the verif SDK."""

import argparse
import json
import sys
from pathlib import Path


def _read_file_or_str(value: str | None, file_path: str | None) -> str | None:
    if file_path:
        return Path(file_path).read_text().strip()
    return value


def _stream_callback(entry):
    event = {"role": entry.role, "content": entry.content[:500]}
    if entry.tool_name:
        event["tool"] = entry.tool_name
    print(json.dumps(event), file=sys.stderr, flush=True)


def _format_output(result, fmt: str, output_file: str | None):
    if fmt == "json":
        out = json.dumps({
            "answer": result.answer,
            "rubric": getattr(result, "rubric", ""),
            "mode": getattr(result, "mode", ""),
            "task": getattr(result, "task", ""),
        }, indent=2)
    elif fmt == "text":
        out = result.answer
    elif fmt == "markdown":
        out = getattr(result, "get_history_markdown", lambda: result.answer)()
        if hasattr(result, "history"):
            lines = []
            for h in result.history:
                lines.append(f"### {h.role}" + (f" ({h.tool_name})" if h.tool_name else ""))
                lines.append(h.content)
                lines.append("")
            out = "\n".join(lines) + f"\n---\n\n## Answer\n\n{result.answer}"
    else:
        out = result.answer

    if output_file:
        Path(output_file).write_text(out)
    else:
        print(out)


def cmd_run(args):
    from verif import RLHarness

    task = _read_file_or_str(args.task, args.task_file)
    if not task:
        print("Error: --task or --task-file required", file=sys.stderr)
        sys.exit(1)

    plan = _read_file_or_str(args.plan, args.plan_file)
    rubric = _read_file_or_str(args.rubric, args.rubric_file)

    on_event = _stream_callback if args.stream else None

    harness = RLHarness(
        provider=args.provider,
        enable_search=args.enable_search,
        enable_code=args.enable_code,
        enable_bash=args.enable_bash,
        max_iterations=args.max_iterations,
        default_mode=args.mode,
        rubric=rubric if args.mode != "plan" else None,
        on_event=on_event,
        stream=args.stream,
    )

    kwargs = {}
    if args.mode == "plan":
        if not plan:
            print("Error: plan mode requires --plan or --plan-file", file=sys.stderr)
            sys.exit(1)
        kwargs["plan"] = plan
        if rubric:
            kwargs["rubric"] = rubric

    result = harness.run_single(task, mode=args.mode, **kwargs)
    _format_output(result, args.output, args.output_file)


def cmd_iterate(args):
    from verif import RLHarness

    task = _read_file_or_str(args.task, None)
    if not task:
        print("Error: --task required", file=sys.stderr)
        sys.exit(1)

    answer = ""
    if args.answer_file:
        answer = Path(args.answer_file).read_text().strip()

    rubric = _read_file_or_str(args.rubric, args.rubric_file) or ""

    harness = RLHarness(
        provider=args.provider,
        enable_search=args.enable_search,
        enable_code=args.enable_code,
        enable_bash=args.enable_bash,
        max_iterations=args.max_iterations,
        stream=args.stream,
        on_event=_stream_callback if args.stream else None,
    )

    result = harness.iterate(
        task=task,
        answer=answer,
        rubric=rubric,
        feedback=args.feedback,
        rubric_update=args.rubric_update,
    )
    _format_output(result, args.output, None)


def cmd_modes(args):
    from verif import MODES
    for name, mode in MODES.items():
        tools = ", ".join(mode.tools)
        print(f"  {name:12s}  rubric={mode.rubric_strategy:10s}  tools=[{tools}]")


def main():
    p = argparse.ArgumentParser(prog="verif", description="verif SDK CLI")
    sub = p.add_subparsers(dest="command", required=True)

    # --- run ---
    run_p = sub.add_parser("run", help="Run a task")
    run_p.add_argument("--provider", required=True, choices=["gemini", "openai", "anthropic"])
    run_p.add_argument("--mode", default="standard", choices=["standard", "plan", "explore"])
    run_p.add_argument("--task", type=str)
    run_p.add_argument("--task-file", type=str)
    run_p.add_argument("--plan", type=str)
    run_p.add_argument("--plan-file", type=str)
    run_p.add_argument("--rubric", type=str)
    run_p.add_argument("--rubric-file", type=str)
    run_p.add_argument("--enable-search", action="store_true")
    run_p.add_argument("--enable-code", action="store_true")
    run_p.add_argument("--enable-bash", action="store_true")
    run_p.add_argument("--max-iterations", type=int, default=30)
    run_p.add_argument("--output", default="json", choices=["json", "text", "markdown"])
    run_p.add_argument("--output-file", type=str)
    run_p.add_argument("--stream", action="store_true")
    run_p.set_defaults(func=cmd_run)

    # --- iterate ---
    iter_p = sub.add_parser("iterate", help="Iterate on an answer")
    iter_p.add_argument("--provider", required=True, choices=["gemini", "openai", "anthropic"])
    iter_p.add_argument("--task", required=True, type=str)
    iter_p.add_argument("--answer-file", type=str)
    iter_p.add_argument("--rubric", type=str)
    iter_p.add_argument("--rubric-file", type=str)
    iter_p.add_argument("--feedback", type=str)
    iter_p.add_argument("--rubric-update", type=str)
    iter_p.add_argument("--enable-search", action="store_true")
    iter_p.add_argument("--enable-code", action="store_true")
    iter_p.add_argument("--enable-bash", action="store_true")
    iter_p.add_argument("--max-iterations", type=int, default=30)
    iter_p.add_argument("--output", default="json", choices=["json", "text"])
    iter_p.add_argument("--stream", action="store_true")
    iter_p.set_defaults(func=cmd_iterate)

    # --- modes ---
    modes_p = sub.add_parser("modes", help="List available modes")
    modes_p.set_defaults(func=cmd_modes)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
