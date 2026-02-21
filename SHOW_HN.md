# Show HN: Open-source SDK for AI knowledge work — self-verifying agents that research, write, and iterate

**GitHub:** https://github.com/ClioAI/kw-sdk

Most AI agent frameworks target code. Write code, run tests, fix errors, repeat. That works because code has a natural verification signal — tests pass or they don't.

Knowledge work has no such signal. When you ask an AI to "analyze the competitive landscape" or "write a strategy memo," how does it know when it's done? How does it know it's good? The solution space is vast and underspecified. There's no test suite that returns pass/fail.

We built a Python SDK that synthesizes that missing signal using **rubrics** — structured evaluation criteria generated before execution begins. The agent works against the rubric, verifies its own output, and iterates until it passes. The human can audit the rubric, override it, or provide their own.

## How it works

```
Task → Brief → Rubric (hidden from executor) → Work → Verify → Fail? → Retry → Pass → Submit
```

The orchestrator coordinates subagents, web search, code execution, and file I/O — then checks its own work against criteria it can't game (the rubric is generated in a separate call and the executor never sees it directly).

```python
from verif import RLHarness

harness = RLHarness(provider="gemini", enable_search=True)
result = harness.run_single("Analyze the EV market opportunity in Southeast Asia.")

print(result.answer)   # The analysis
print(result.rubric)   # What "good" looked like
```

## What makes this different

**1. Explore mode — map the solution space, don't collapse it**

Most agents optimize for a single answer. But for strategy, design, or any creative problem, you want to see the space first. Explore mode generates N distinct approaches, each with explicit assumptions and counterfactuals ("this works if X, breaks if Y"). The output ends with set-level gaps — what angles the entire set missed. The gaps are often more valuable than the takes.

```python
result = harness.run_single(
    "Database architecture for a fintech: 10K TPS, strong consistency, multi-region.",
    mode="explore",
    num_takes=3,
)
# 3 distinct approaches, each with assumptions + what would break it
# + gaps: "all assumes single cloud provider, none considered regulatory constraints"
```

You can then pipe explore output into a selector (LLM picks the best approach) and execute it as a structured plan. Divergent thinking → convergent execution.

**2. Checkpointing — fork any execution mid-run**

The agent does brief → rubric → research → draft. At step 7, you look at the intermediate state and think "good research, but also cover X." Instead of re-running from scratch, you fork from any checkpoint, inject feedback, and the agent continues with all prior context intact.

```python
result = harness.run_single(task, checkpoint=True)

# Inspect what happened at each step
for snap_id, snap in harness.snapshots.items():
    print(f"{snap_id} — rubric={'yes' if snap.state.get('rubric') else 'no'}")

# Fork with new direction + updated evaluation criteria
resumed = harness.resume(
    checkpoint_id="abc:step:7",
    feedback="Also analyze demigods as proxies of divine power.",
    rubric_update="Must cover at least 3 god-demigod relationships.",
)
```

This is "what if I changed my mind at step 5?" without paying for steps 1-4 again.

**3. The verification loop is the product, not a feature**

The verify step is where the real leverage is. A model that can accurately assess its own work against a rubric is more valuable than one that generates slightly better first drafts. The rubric makes quality legible — to the agent, to the human, and potentially to a training signal.

We originally built this as a harness for RL training on knowledge tasks. The rubric is the reward function. If you're training models on knowledge work, the brief→rubric→execute→verify loop gives you a structured reward signal for tasks that normally don't have one.

**4. Multi-agent orchestration without the framework tax**

The orchestrator spawns subagents for parallel research, delegates to a search agent, runs code in a stateful REPL, and reads/writes files. But there's no agent graph DSL, no YAML config, no node-and-edge abstractions. It's function calls in a loop. The orchestrator decides what to parallelize based on the task, not based on a predefined graph.

Tools are pluggable. Code execution is a protocol — swap `SubprocessExecutor` for `DockerExecutor` or `RemoteExecutor` (we built a version where the model's code runs entirely in the browser via WebContainers). The harness doesn't know or care where code runs.

**5. Code as tools (both sides of it)**

Instead of building tool servers with JSON schemas for every capability, we document utility functions and let the model call them via `execute_code`. The terminal is already a universal function-calling interface — `argv` in, `stdout` out.

Anthropic recently formalized a version of this as [Programmatic Tool Calling](https://www.anthropic.com/engineering/advanced-tool-use) — where the model writes code that orchestrates tools, and intermediate results flow through the script instead of back into context. That's about where results flow. What we describe is about what you build: functions, not tool servers.

In practice, we support both patterns:

- **Model as caller**: Document your utility functions, model imports and calls them. It's a caller of tested code, not a writer of untested code. (`no_tools_needed.py`, `docs_from_file.py`)
- **Model as writer**: Give it raw data or a pre-loaded environment, it writes the orchestration code itself — loops, transforms, aggregations. (`csv_research_and_calc.py`, `with_custom_executor.py`)

The second pattern is essentially what PTC formalizes. We just do it through `execute_code` with a stateful REPL rather than a special API mode.

**6. Code execution is a two-method protocol**

Most agent frameworks couple you to a specific sandbox. Ours doesn't. Code execution is a protocol — implement `execute(code) -> result` and `reset()`, and the harness will use it. The model never knows where its code runs.

```python
# Local subprocess
executor = SubprocessExecutor("./artifacts")

# Docker container
executor = DockerExecutor("python:3.11", "./artifacts")

# Browser sandbox (model's code runs in WebContainers on the frontend)
executor = RemoteExecutor(session_id, emit_event, sandbox_config={"type": "webcontainer"})

# Same harness, same interface
harness = RLHarness(enable_code=True, code_executor=executor)
```

We built a web app where the model's Python runs entirely in the user's browser. The `RemoteExecutor` emits a `tool_request` SSE event, the frontend catches it, executes in its sandbox, and posts the result back. The model just calls `execute_code` and gets stdout — it has no idea it's running in a browser tab.

This also means you can drop in E2B, Modal, Firecracker microVMs, or whatever your security model requires. One line change, same orchestration.

## Supports Gemini, OpenAI, and Anthropic

All three providers with their respective thinking/reasoning controls. Streaming, context compaction for long tasks, and the full tool suite work across all of them.

## Limitations (being honest)

- **Verification is only as good as the model.** The rubric is generated by the same model that does the work. Blind spots propagate.
- **Rubrics can be gamed.** A clever model could write an easy rubric. Human review matters for high-stakes work.
- **This is for knowledge work, not code.** If your task has a test suite, you don't need synthetic verification.

## Why open source

Knowledge workflows are underexplored. Most AI tooling focuses on code, but research, analysis, strategy, and writing is where most professionals actually spend their time. The primitives for building these systems aren't well established yet.

If this gets adoption, maybe an open-source model provider trains specifically on rubric-based verification — that would improve the entire ecosystem. I'd rather see these ideas spread than keep them proprietary.

MIT licensed. Feedback welcome.

https://github.com/ClioAI/kw-sdk
