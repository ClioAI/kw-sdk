# AGENTS.md

This file is a high-signal operating guide for AI coding agents working in this repository.

## 1. Project Snapshot

- Package: `verif`
- Domain: Knowledge-work orchestration harness with rubric-based verification loops.
- Key value: Supports both synchronous and asynchronous SDK usage for notebooks and web servers.

Primary modules:

- `/Users/ankit/Documents/dev/RL/harness/kw-sdk/verif/harness.py`
- `/Users/ankit/Documents/dev/RL/harness/kw-sdk/verif/providers/base.py`
- `/Users/ankit/Documents/dev/RL/harness/kw-sdk/verif/providers/gemini.py`
- `/Users/ankit/Documents/dev/RL/harness/kw-sdk/verif/providers/openai.py`
- `/Users/ankit/Documents/dev/RL/harness/kw-sdk/verif/providers/anthropic.py`
- `/Users/ankit/Documents/dev/RL/harness/kw-sdk/verif/config.py`

## 2. Sync + Async Coexistence (Important)

The SDK intentionally exposes two public entry points:

- Sync: `RLHarness`
- Async: `AsyncRLHarness`

Both live in `verif/harness.py` and are exported in `verif/__init__.py`.

### Design intent

- Keep API simple for notebook/data-science users (`RLHarness`).
- Support non-blocking server runtimes (FastAPI, async workers) with `AsyncRLHarness`.
- Avoid full code duplication by keeping shared orchestration logic in `BaseProvider` and adding async counterparts where needed.

## 3. Provider Contract

Each provider should implement both sync and async model paths.

Expected method families:

- `generate(...)` and `generate_async(...)`
- `search(...)` and `search_async(...)`
- `_call_model(...)` and `_call_model_async(...)`

Current status:

- OpenAI: native async client (`AsyncOpenAI`) wired.
- Anthropic: native async client (`AsyncAnthropic`) wired.
- Gemini: native `client.aio.models.*` methods wired (no thread fallback for async model calls).

## 4. Background Agents Semantics

Background agents are a subagent orchestration feature (`delegate(background=True)`) and are not a separate job system.

- Sync path uses thread-based futures.
- Async path uses `asyncio.create_task(...)`.
- Results are polled during orchestrator iterations and injected back into context.
- This is in-process state, not durable queueing.

Do not treat background agents as durable/restart-safe jobs.

## 5. Event and Streaming Model

Events are emitted via `HistoryEntry` callbacks (`on_event`).

Common streaming-related event types:

- `model_chunk`
- `subagent_start`
- `subagent_chunk`
- `subagent_end`
- `brief_start`
- `brief_chunk`
- `verification_chunk`

Async streaming integration scripts:

- `/Users/ankit/Documents/dev/RL/harness/kw-sdk/tests/test_streaming_async_gemini.py`
- `/Users/ankit/Documents/dev/RL/harness/kw-sdk/tests/test_streaming_async_openai.py`

Output artifacts:

- `/Users/ankit/Documents/dev/RL/harness/kw-sdk/tests/outputs/test_streaming_async_gemini_output.md`
- `/Users/ankit/Documents/dev/RL/harness/kw-sdk/tests/outputs/test_streaming_async_openai_output.md`

## 6. Gemini HTTP / AIOHTTP Plumbing

`ProviderConfig` now supports Gemini transport options:

- `gemini_http_options: dict | None`
- `gemini_async_client_args: dict | None`

These are mapped into `google.genai.types.HttpOptions` inside `load_provider(...)`.

Example:

```python
from verif import ProviderConfig, AsyncRLHarness

cfg = ProviderConfig(
    name="gemini",
    thinking_level="LOW",
    gemini_async_client_args={"ssl": True, "cookies": {}},
)

h = AsyncRLHarness(provider=cfg, enable_search=True, stream=True, stream_subagents=True)
```

## 7. Known Runtime Failure Mode

If you see:

- `[Errno 8] nodename nor servname provided, or not known`
- `httpx.ConnectError`

this is DNS/network environment failure, not necessarily SDK logic regression. Validate host resolution in the execution environment before changing provider code.

## 8. Test Commands

From repo root:

```bash
# Unit-level async harness checks
.venv/bin/python -m pytest -q tests/test_async_harness_unit.py

# Async streaming integration scripts
.venv/bin/python tests/test_streaming_async_gemini.py
.venv/bin/python tests/test_streaming_async_openai.py

# Syntax sanity
.venv/bin/python -m py_compile verif/config.py verif/harness.py verif/providers/gemini.py
```

## 9. Editing Guardrails for Future Agents

- Preserve dual-entrypoint architecture (`RLHarness` + `AsyncRLHarness`).
- Do not remove sync APIs to enforce async-only usage.
- Keep provider behavior consistent across sync/async paths where possible.
- Prefer shared logic in `BaseProvider`; avoid copy-paste divergence.
- Keep output markdown structure stable for test scripts in `tests/`.
- Do not commit generated output files unless explicitly requested.

## 10. FastAPI Guidance (Short)

In async web servers:

- Prefer `AsyncRLHarness` and `await harness.run_single(...)`.
- Avoid calling sync harness directly inside async request handlers.
- If sync harness must be used, isolate with threadpool execution.
