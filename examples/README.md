# Examples

Working examples that show what this harness can do and, more importantly, the patterns behind it.

## Setup

```bash
uv venv && source .venv/bin/activate
uv pip install -r requirements.txt

# .env file with API keys
echo "GEMINI_API_KEY=your_key" > .env
echo "OPENAI_API_KEY=your_key" >> .env
```

```bash
python examples/standard_mode.py
```

---

## The Core Idea

An LLM runs a task. Before it can submit, it must pass a rubric it never sees. If it fails, it gets feedback and tries again. The rubric is the quality gate.

```
Task → Brief → Rubric (hidden) → Work → Verify → Fail? → Retry → Pass → Submit
```

Everything below is a variation on this loop.

---

## Examples by Pattern

### 1. Basic Execution Modes

How you frame the task changes how the model works.

| Example | What it shows |
|---------|---------------|
| `standard_mode.py` | Minimal setup. Auto-generated brief and rubric. Just give it a task. |
| `plan_mode.py` | You provide the plan and rubric. Model executes within your structure. |
| `plan_mode_no_rubric.py` | You provide the plan, rubric is auto-generated. Middle ground. |
| `explore_mode.py` | Model generates multiple distinct approaches with assumptions and counterfactuals. |
| `standard_with_rubric.py` | You define acceptance criteria, LLM converts them to a rubric, then executes against it. |

### 2. Input & Output

Getting data in and results out.

| Example | What it shows |
|---------|---------------|
| `with_files.py` | Attach files (CSV, text, images) to prompts. Model reads them as context. |
| `with_streaming.py` | Real-time event callbacks — see tool calls, model chunks, subagent activity as they happen. |
| `with_code_execution.py` | Model writes and runs Python. Variables persist across calls. Files saved to artifacts dir. |
| `with_file_artifact.py` | **Model saves CSV artifacts, post-generation script converts to .xlsx.** See [File Artifacts](#file-artifacts). |

### 3. Multi-Stage Workflows

Chain multiple harness runs into pipelines.

| Example | What it shows |
|---------|---------------|
| `end_to_end_workflow.py` | **Explore → Select → Execute.** Model brainstorms, LLM picks best approach, then executes it. |
| `iterate_workflow.py` | Run → get user feedback → classify feedback → iterate with refined rubric. Progressive refinement. |
| `npi_iphone18.py` | Minimal-instruction variant: explore, select in one sentence, execute with auto rubric. |
| `npi_iterate.py` | Load previous output, provide targeted feedback, iterate to refine. |

### 4. Extensibility

| Example | What it shows |
|---------|---------------|
| `no_tools_needed.py` | Pre-built utility functions + execute_code. Model calls your tested code, not writes its own. |
| `docs_from_file.py` | Attach documentation files alongside utilities. Model sees docs in context. |
| `with_custom_executor.py` | Custom code executor with preamble — pre-loaded variables, imports, environment setup. |
| `custom_mode_bizarro.py` | Define entirely new execution modes. Custom prompts, custom flow, registered at runtime. |
| `standard_with_search.py` | Enable web search. Model delegates research to a search subagent. |

---

## Key Patterns

### The Verify-Iterate Loop

The model doesn't just generate — it checks its own work against a rubric and self-corrects. In the `with_file_artifact.py` trace, the first verification **failed** because the answer referenced files without showing the data. The model read the files back, included the content, and passed on retry. No human intervention needed.

### File Artifacts

Models can generate Excel, Word, PDF directly if given code execution — they'll write the openpyxl or python-docx code themselves. But that means the model controls both the analysis *and* the formatting. Here we separate the two:

1. Model saves basic files (CSV, JSON, markdown) to `artifacts_dir`
2. Your script converts to the target format with your styles, templates, branding

The model controls *what*. You control *how it looks*.

**Alternative:** Instead of a post-generation script, the model can run a pre-built converter directly — `python utils/csv_to_xlsx.py artifacts/ report.xlsx`. No code writing, no import hacking. Just CLI execution with args. The model becomes a shell orchestrator calling your tested scripts.

### Script Execution vs Tool Calling

Two ways to give a model capabilities:

**Tool calling** (current industry paradigm):
```
You define JSON schema → Model outputs structured JSON → You parse, route, execute → You serialize result back
```
For every new capability: schema + handler + dispatch wiring.

**Script execution** (what these examples do):
```
You write a Python script with argparse → Model runs it → Model reads stdout
```
For every new capability: write the script.

The terminal is already a universal function-calling interface. `argv` in, `stdout` out, `stderr` for errors, exit codes for status. The model doesn't need a special JSON schema to call a function — it already knows how to use a command line.

Script execution gives a tighter feedback loop: the model sees raw output immediately, can chain commands, retry with different args, and inspect results — no orchestrator middleman. Tool calling gives you structured validation and security boundaries.

### Explore → Select → Execute

When you don't know the right approach upfront:

1. **Explore:** Generate 3+ distinct approaches, each with assumptions and counterfactuals
2. **Select:** Use an LLM call to analyze all approaches and pick the best (or synthesize)
3. **Execute:** Run plan mode with the selected approach and a rubric

This separates divergent thinking from convergent execution. You can insert human review between any stage.

### Pre-built Utilities

Instead of the model writing API integration code from scratch every time:

1. Write tested, reliable utility scripts (`utils/weather.py`, `utils/stripe.py`)
2. Model calls them via execute_code or bash
3. Model is a **caller** of tested code, not a **writer** of untested code

---

## Outputs

All examples save execution traces to `examples/outputs/` as markdown files. These include the task, model answer, rubric used, and full tool-call-by-tool-call execution history.

File artifacts (xlsx, csv, etc.) are saved to `examples/artifacts/`.

Pre-generated outputs are in `outputs/` — you can see what the harness produces without running anything.

A few worth opening:

- **`file_artifact_output.md`** — The model's first answer got rejected by the verifier. It referenced CSV files but didn't show the data. Watch it self-correct: read the files back, include the content, pass on retry. Then scroll down to see the 4 CSV artifacts it saved — and the `.xlsx` in `artifacts/` that a 40-line script converted them into.

- **`iterate_workflow_output.md`** — The model submits an answer. User says "use McKinsey data, needs board-level summary." Watch the feedback get classified into rubric-level vs answer-level changes, then the rubric itself gets rewritten before the next attempt.

- **`bizarro_output.md`** — What happens when you invert the entire workflow. Anti-brief, failure rubric, deliberately break the answer, then rebuild. A custom mode registered at runtime.

---

## Code Execution is Pluggable

The examples here use `SubprocessExecutor` — runs Python locally in a subprocess. But the harness doesn't care where code runs. It ships with a `RemoteExecutor` that delegates execution to whatever environment you provide:

- A Docker container with specific packages
- A browser-based sandbox (WebContainer, Pyodide)
- A locked-down VM with network restrictions
- Your own runtime with custom pre-installed tools

Swapping where code runs is one line:

```python
# Local: runs in a subprocess on your machine
code_executor = SubprocessExecutor(artifacts_dir)

# Remote: delegates to any sandbox you control
code_executor = RemoteExecutor(
    session_id, on_event_callback,
    sandbox_config={"type": "docker", "packages": ["pandas", "openpyxl"]}
)

# Harness doesn't know or care which one it got
harness = RLHarness(
    provider=config,
    enable_code=True,
    code_executor=code_executor,  # <-- same interface
)
```

We built a web app where the model's code runs entirely in the browser. Here's roughly how:

```python
# Server side: wrap harness in a FastAPI SSE endpoint
from fastapi import FastAPI
from fastapi.responses import StreamingResponse

app = FastAPI()

@app.post("/run")
async def run(req: RunRequest):
    # RemoteExecutor pushes code to the frontend instead of running locally
    code_executor = RemoteExecutor(
        session_id=req.session_id,
        emit_event=lambda event_type, data: sse_queue.put(UIEvent(event_type, data)),
        sandbox_config={"type": "webcontainer", "packages": ["pandas"]}
    )

    harness = RLHarness(
        provider=ProviderConfig(name="gemini"),
        enable_code=True,
        code_executor=code_executor,
    )

    # Stream events to frontend as SSE
    async def stream():
        result = harness.run_single(task)
        # During execution, RemoteExecutor emits tool_request events
        # Frontend catches them, runs code in its sandbox, posts back:
        #   POST /tool/respond {request_id, session_id, result: {stdout, stderr}}
        yield format_sse("result", result)

    return StreamingResponse(stream(), media_type="text/event-stream")
```

The frontend listens for `tool_request` events, executes code in its sandbox, and returns output via a callback endpoint. The model has no idea it's running in a browser — it just calls `execute_code` and gets stdout back.

P.S. You'll need a callback endpoint for the frontend to post results back to:

```python
@app.post("/tool/respond")
async def tool_respond(req: ToolResponseRequest):
    executor = sandbox_sessions.get(req.session_id)
    if executor:
        executor.receive_response(req.request_id, req.result)
        return {"acknowledged": True}
    return {"acknowledged": False, "error": "Session not found"}
```
