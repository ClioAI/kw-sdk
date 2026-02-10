# Contributing

Thanks for your interest in contributing to the Knowledge Work SDK.

## Setup

```bash
git clone https://github.com/ClioAI/kw-sdk.git
cd kw-sdk
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"
```

Create a `.env` file:
```bash
GEMINI_API_KEY=your_key
OPENAI_API_KEY=your_key      # optional
ANTHROPIC_API_KEY=your_key   # optional
```

## Running Examples

```bash
PYTHONPATH=. python examples/standard_mode.py
```

Examples save output to `examples/outputs/`. If your change affects execution behavior, run a relevant example end-to-end and check the trace.

## Running Tests

```bash
PYTHONPATH=. python tests/test_checkpoint.py
```

Tests are end-to-end — they make real API calls. They're not unit tests. Each test writes an output markdown file to `tests/outputs/` with the full execution trace.

## What to Contribute

Check the [TODO section in the README](README.md#todo) for planned work. Good first contributions:

- **Token usage tracking** — surface per-run token counts by phase
- **Eval framework** — scoring and reporting on top of the existing `run_eval`
- **Mixed-model orchestration** — different models for orchestrator vs subagents
- **Bug fixes from execution traces** — run examples, find failure modes, fix them

## How to Contribute

1. Fork the repo
2. Create a branch (`git checkout -b feature/my-feature`)
3. Make your changes
4. Run a relevant example or test end-to-end to verify
5. Open a PR with a description of what changed and why

## Code Style

- Concise over verbose. Minimum code to solve the problem.
- No hardcoded values or placeholder implementations.
- Type hints where they add clarity.
- If you add a new feature, add an example showing how to use it.

## Adding a New Provider

Implement the abstract methods in `verif/providers/base.py`:
- `_init_context`, `_call_model`, `_append_tool_results`
- `_estimate_context_tokens`, `_get_context_length`
- `_inject_feedback`, `_rebuild_context_with_summary`
- `generate`, `search`, `read_file_with_vision`

Register it in `verif/providers/__init__.py` and `verif/harness.py:load_provider()`.

## Adding a New Mode

See [EXTENSIONS.md](EXTENSIONS.md). Modes are config — define a `ModeConfig`, register prompts, and it works with the existing orchestrator loop.

## Adding a New Executor

Implement the `CodeExecutor` protocol (two methods: `execute` and `reset`). See `with_custom_executor.py` for examples.
