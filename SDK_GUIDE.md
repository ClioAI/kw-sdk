# RL Harness SDK Guide

A Python SDK for building AI applications with self-verifying, agentic workflows. The harness orchestrates tasks using AI models with automatic rubric creation, iterative verification, and parallel subagent execution.

## Installation

```bash
# Clone the repository
git clone https://github.com/ClioAI/rh.git
cd rubrics

# Create virtual environment
uv venv
source .venv/bin/activate

# Install dependencies
uv pip install -r requirements.txt
```

## Environment Setup

Create a `.env` file with your API keys:

```bash
GEMINI_API_KEY=your_gemini_key
OPENAI_API_KEY=your_openai_key
```

---

## Quick Start

### Basic Usage

```python
from verif import RLHarness, ProviderConfig

# Initialize with Gemini
harness = RLHarness(provider="gemini")

# Run a task
result = harness.run_single("What is the capital of France?")

print(result.answer)   # "Paris"
print(result.rubric)   # Auto-generated evaluation criteria
```

### With OpenAI

```python
from verif import RLHarness, ProviderConfig

config = ProviderConfig(name="openai", reasoning_effort="medium")
harness = RLHarness(provider=config)

result = harness.run_single("Explain quantum entanglement in simple terms.")
print(result.answer)
```

---

## Core Concepts

### The Verification Loop

The SDK implements a **self-verifying agentic loop**:

1. **Brief Creation** - Formalize the task into structured requirements
2. **Rubric Creation** - Generate evaluation criteria (hidden from orchestrator)
3. **Task Execution** - Orchestrator delegates to subagents, runs searches
4. **Verification** - Check answer against rubric (PASS/FAIL)
5. **Iteration** - If FAIL, improve and verify again
6. **Submission** - Submit final answer after PASS

### Execution Modes

| Mode | Use Case | Rubric Strategy |
|------|----------|-----------------|
| `standard` | General tasks | Auto-created during execution |
| `plan` | Structured execution | User-provided or auto-created |
| `explore` | Creative/divergent tasks | Uses quality checklist |

---

## RLHarness Configuration

```python
from verif import RLHarness, ProviderConfig, CompactionConfig
from verif.executor import SubprocessExecutor

harness = RLHarness(
    # Provider: "gemini" | "openai" | ProviderConfig
    provider=ProviderConfig(
        name="gemini",
        thinking_level="MEDIUM",  # Gemini: LOW | MEDIUM | HIGH
        # OR for OpenAI:
        # name="openai",
        # reasoning_effort="medium",  # low | medium | high
    ),
    
    # Tool Capabilities
    enable_search=True,     # Web search tool
    enable_bash=False,      # Filesystem navigation (ls, find, grep, cat)
    enable_code=False,      # Python code execution
    enable_ask_user=False,  # User clarification tool
    
    # Code Execution (required if enable_code=True)
    code_executor=SubprocessExecutor("./artifacts"),
    artifacts_dir="./artifacts",
    
    # Execution Limits
    max_iterations=30,
    
    # Mode Selection
    default_mode="standard",  # "standard" | "plan" | "explore"
    
    # Pre-set Rubric (optional)
    rubric="1. Answer must be accurate\n2. Must cite sources",
    
    # Event Streaming
    on_event=lambda e: print(f"[{e.entry_type}] {e.content[:100]}"),
    stream=True,              # Stream orchestrator output
    stream_subagents=True,    # Stream subagent output
    
    # Context Compaction (for long tasks)
    compaction_config=CompactionConfig(
        enabled=True,
        threshold=0.8,        # Trigger at 80% context capacity
        keep_recent_turns=3,
    ),
)
```

---

## Execution Modes

### Standard Mode (Default)

Best for general tasks. The orchestrator creates the brief and rubric automatically.

```python
from verif import RLHarness

harness = RLHarness(provider="gemini", enable_search=True)

result = harness.run_single(
    "What do paternal genes contribute to brain development?"
)

print(result.answer)
print(result.rubric)  # Auto-generated
```

### Plan Mode

Best for complex tasks where you want control over execution strategy.

```python
from verif import RLHarness

harness = RLHarness(provider="gemini", enable_search=True)

# Define your plan
PLAN = """
## Research Phase
1. Research the iridium anomaly discovery (Walter Alvarez, 1980)
2. Research Chicxulub crater confirmation (Hildebrand, 1991)
3. Research supporting evidence (shocked quartz, tektites)

## Writing Phase
4. Draft introduction with engaging hook
5. Structure narrative as detective story
6. Conclude with reflection on scientific method
"""

# Optional: Define your rubric
RUBRIC = """
## Factual Accuracy (25 points)
- [ ] Correctly identifies Walter Alvarez
- [ ] Accurately describes iridium layer significance
- [ ] Mentions Luis Alvarez (father, Nobel physicist)

## Writing Quality (25 points)
- [ ] Clear introduction
- [ ] Logical flow
- [ ] Word count: 800-1200
"""

# Run with plan (rubric optional)
result = harness.run_single(
    task="Write an article about the dinosaur extinction discovery.",
    mode="plan",
    plan=PLAN,
    rubric=RUBRIC,  # Optional - omit to auto-create
)

print(result.answer)
```

### Explore Mode

Best for creative tasks requiring multiple perspectives.

```python
from verif import RLHarness

harness = RLHarness(provider="gemini", enable_search=False)

result = harness.run_single(
    task="""Write a counter-speech from Sorrento's perspective 
    responding to Parzival's plea in Ready Player One.""",
    mode="explore",
    num_takes=3,  # Hint for number of distinct approaches
)

# Result contains multiple takes separated by ===
takes = result.answer.split("===")
for i, take in enumerate(takes):
    print(f"\n--- Take {i+1} ---\n{take[:500]}...")
```

---

## Working with Files

### Multimodal Prompts (Text + Attachments)

```python
from verif import RLHarness, ProviderConfig, Attachment, Prompt
from verif.executor import SubprocessExecutor
from pathlib import Path

# Read file preview
file_path = Path("vendor_quotes.txt")
with open(file_path) as f:
    preview = "".join(f.readlines()[:100])

# Create attachment
attachment = Attachment(
    content=str(file_path),      # File path
    mime_type="text/plain",
    name="vendor_quotes.txt",
    preview=preview,              # First 100 lines for context
)

# Build multimodal prompt
prompt: Prompt = [
    "Analyze the attached vendor quotes and recommend the best option.",
    attachment,
]

# Configure harness with code execution for file output
harness = RLHarness(
    provider=ProviderConfig(name="openai", reasoning_effort="medium"),
    enable_search=False,
    enable_bash=True,   # Enable file search
    enable_code=True,   # Enable code execution
    code_executor=SubprocessExecutor("./artifacts"),
    artifacts_dir="./artifacts",
)

result = harness.run_single(prompt)
print(result.answer)
```

### Supported Attachment Types

| Type | MIME Type | Handling |
|------|-----------|----------|
| Images | `image/png`, `image/jpeg`, `image/gif`, `image/webp` | Sent directly to model vision |
| Text | `text/plain`, `text/markdown`, `text/csv` | Use `preview` field for content |
| PDFs | `application/pdf` | Requires `enable_bash=True` to read |
| Other | Any | Requires `preview` or `enable_bash=True` |

**Important:** Only images are sent directly to the model. For all other file types:
- Provide `preview` with the file content (model sees this immediately)
- Or enable `enable_bash=True` so the orchestrator can read files via `search_files`

```python
# Good: Text file with preview
attachment = Attachment(
    content="/path/to/doc.md",
    mime_type="text/markdown",
    name="doc.md",
    preview=Path("/path/to/doc.md").read_text(),  # Model sees this
)

# Good: Image (no preview needed)
image = Attachment(
    content="/path/to/chart.png",
    mime_type="image/png",
    name="chart.png",
)

# Requires enable_bash: PDF without preview
pdf = Attachment(
    content="/path/to/report.pdf",
    mime_type="application/pdf",
    name="report.pdf",
)
# Model will call search_files to read it
```

**For complex files, preprocess first.** Don't rely on the model to parse PDFs, spreadsheets, or binary formats. Extract content yourself and pass as text:

```python
import pdfplumber  # or PyMuPDF, pdfminer, etc.

# Preprocess PDF → text
with pdfplumber.open("report.pdf") as pdf:
    text = "\n".join(page.extract_text() for page in pdf.pages)

attachment = Attachment(
    content="report.pdf",
    mime_type="text/plain",  # Now it's text
    name="report.pdf",
    preview=text,  # Extracted content
)

# Preprocess Excel → CSV or markdown table
import pandas as pd
df = pd.read_excel("data.xlsx")
preview = df.to_markdown()  # or df.to_csv()

attachment = Attachment(
    content="data.xlsx",
    mime_type="text/markdown",
    name="data.xlsx", 
    preview=preview,
)
```

This gives you control over extraction quality and reduces model errors.

---

## Event Streaming

### Real-time Event Handling

```python
from verif import RLHarness, ProviderConfig
from verif.providers.base import HistoryEntry

events = []

def on_event(entry: HistoryEntry):
    """Handle streaming events."""
    print(f"[{entry.entry_type}] {entry.content[:100]}...")
    events.append(entry)
    
    # Access metadata for subagent tracking
    if entry.metadata and "subagent_id" in entry.metadata:
        print(f"  Subagent ID: {entry.metadata['subagent_id']}")

harness = RLHarness(
    provider=ProviderConfig(name="gemini", thinking_level="LOW"),
    enable_search=True,
    on_event=on_event,
    stream=True,           # Stream orchestrator
    stream_subagents=True, # Stream subagents
)

result = harness.run_single("Research AI safety developments in 2024.")

# Analyze events
event_counts = {}
for e in events:
    event_counts[e.entry_type] = event_counts.get(e.entry_type, 0) + 1
print(f"Event summary: {event_counts}")
```

### Event Types

| Event Type | Description |
|------------|-------------|
| `user` | User input/task |
| `system` | System messages |
| `model` | Model output |
| `model_chunk` | Streaming model chunk |
| `tool_call` | Tool invocation |
| `tool_response` | Tool result |
| `tool_error` | Tool error |
| `subagent_start` | Subagent spawned |
| `subagent_chunk` | Subagent streaming |
| `subagent_end` | Subagent complete |
| `user_question` | ask_user questions pending response |

---

## Code Execution

### Stateful Python REPL

```python
from verif import RLHarness, ProviderConfig
from verif.executor import SubprocessExecutor

# Create executor (variables persist across calls)
executor = SubprocessExecutor(
    artifacts_dir="./artifacts",
    timeout=60,
)

harness = RLHarness(
    provider="gemini",
    enable_code=True,
    code_executor=executor,
    artifacts_dir="./artifacts",
)

result = harness.run_single("""
Calculate compound interest:
- Principal: $10,000
- Rate: 5% annual
- Time: 10 years
- Compounding: monthly

Save the results to a CSV file.
""")

# Check for created artifacts
import os
print(os.listdir("./artifacts"))
```

### Custom Executor Protocol

```python
from verif.executor import CodeExecutor, CodeResult

class MyExecutor:
    """Implement the CodeExecutor protocol."""
    
    def execute(self, code: str) -> CodeResult:
        # Run code in your environment
        return CodeResult(
            stdout="output",
            stderr="",
            artifacts=["path/to/created/file.xlsx"],
            error=None,
        )
    
    def reset(self) -> None:
        # Reset state
        pass
```

### Remote Executor (Frontend Delegation)

For browser-based sandboxed execution, use `RemoteExecutor` to delegate code execution to the frontend via SSE events:

```python
from verif.executor import RemoteExecutor

def emit_sse_event(event_type: str, data: dict):
    """Your SSE emit function."""
    pass

executor = RemoteExecutor(
    session_id="session-123",
    emit_event=emit_sse_event,
    timeout=30,
    sandbox_config={
        "type": "pyodide",
        "packages": ["pandas", "numpy"],
        "constraints": "No network access",
    },
)

# Executor emits 'tool_request' events, expects responses via receive_response()
executor.receive_response(request_id, {"success": True, "data": {"stdout": "..."}})
```

---

## User Clarification (ask_user)

Enable interactive clarification for ambiguous tasks:

```python
import threading
from verif import RLHarness, ProviderConfig

def on_event(entry, harness):
    if entry.entry_type == "user_question":
        question_id = entry.metadata["question_id"]
        questions = entry.metadata["questions"]
        context = entry.metadata.get("context", "")
        
        # Collect or generate answers
        answers = {0: "B2B SaaS platform", 1: "$50,000 budget"}
        
        # Send response back (threaded to avoid blocking)
        threading.Thread(
            target=lambda: harness.provider.receive_user_response(question_id, answers)
        ).start()

harness = RLHarness(
    provider=ProviderConfig(name="gemini", thinking_level="MEDIUM"),
    enable_ask_user=True,
    on_event=lambda e: on_event(e, harness),
)

result = harness.run_single("Create a detailed project plan for my product launch.")
```

Key behaviors:
- `verify_answer` blocks until all pending questions are answered
- User clarifications are included in verification context
- Answers are keyed by question index (0, 1, 2...)

---

## Batch Evaluation

### Running Eval Sets

```python
from verif import RLHarness

harness = RLHarness(provider="gemini", enable_search=True)

eval_set = [
    {"question": "What is 2 + 2?", "answer": "4"},
    {"question": "Capital of Japan?", "answer": "Tokyo"},
    {"question": "Who wrote 1984?", "answer": "George Orwell"},
]

results = harness.run_eval(
    eval_set,
    task_key="question",
    gt_key="answer",
    mode="standard",
)

for r in results:
    print(f"Q: {r.task}")
    print(f"A: {r.answer}")
    print(f"GT: {r.ground_truth}")
    print("---")
```

---

## Advanced Configuration

### Context Compaction

For long-running tasks that approach context limits:

```python
from verif import RLHarness, CompactionConfig

harness = RLHarness(
    provider="gemini",
    compaction_config=CompactionConfig(
        enabled=True,
        threshold=0.8,           # Trigger at 80% of max context
        keep_recent_turns=3,     # Keep last 3 turns verbatim
        max_summary_tokens=1000, # Max tokens for summary
    ),
)
```

### Provider-Specific Settings

```python
from verif import ProviderConfig

# Gemini with high thinking
gemini_config = ProviderConfig(
    name="gemini",
    thinking_level="HIGH",  # LOW | MEDIUM | HIGH
)

# OpenAI with high reasoning
openai_config = ProviderConfig(
    name="openai",
    reasoning_effort="high",  # low | medium | high
)
```

### Listing Available Modes

```python
from verif import RLHarness

# List all modes
modes = RLHarness.list_modes()
print(modes)  # ['standard', 'plan', 'explore']

# Get mode configuration
config = RLHarness.get_mode_config("plan")
print(config.tools)  # ['create_rubric', 'spawn_subagent', ...]
```

### Custom Modes

Create custom execution modes by registering prompts and ModeConfig:

```python
from verif import RLHarness, ProviderConfig
from verif.config import ModeConfig
from verif.modes import MODES
from verif.providers.base import PROMPTS

# Define custom prompts
BIZARRO_ORCHESTRATOR = """You are BIZARRO orchestrator. Everything is OPPOSITE.
To find the best answer, first find the WORST answer..."""

BIZARRO_BRIEF = """Create an ANTI-BRIEF identifying everything that could go WRONG..."""

# Define mode config
BIZARRO_MODE = ModeConfig(
    name="bizarro",
    orchestrator_prompt="BIZARRO_ORCHESTRATOR",
    brief_prompt="BIZARRO_BRIEF",
    tools=["create_brief", "create_rubric", "spawn_subagent", "verify_answer", "submit_answer"],
    verification_tool="verify_answer",
    rubric_strategy="create",
    has_pre_execution=False,
    prompt_kwargs=[],
)

# Register at runtime
PROMPTS["BIZARRO_ORCHESTRATOR"] = BIZARRO_ORCHESTRATOR
PROMPTS["BIZARRO_BRIEF"] = BIZARRO_BRIEF
MODES["bizarro"] = BIZARRO_MODE

# Use like any built-in mode
harness = RLHarness(provider="gemini", default_mode="bizarro")
result = harness.run_single(task, mode="bizarro")
```

See: [examples/custom_mode_bizarro.py](examples/custom_mode_bizarro.py)

---

## Patterns

### Pre-built Utils + execute_code (No Custom Tools Needed)

Instead of creating MCP servers, document utility functions and let the model call them:

```python
WEATHER_UTILS_DOCS = """
## Available: Weather Utilities
```python
from utils.weather import get_current, get_forecast, compare_cities
get_current("London")  # {"city": "London", "temp": 15.2, ...}
```
"""

task = f"Recommend a travel destination based on weather.\n\n{WEATHER_UTILS_DOCS}"
result = harness.run_single(task)  # Model imports and calls your tested code
```

See: [examples/no_tools_needed.py](examples/no_tools_needed.py)

### Docs as File Attachment

Keep documentation alongside code and attach to prompts:

```python
from verif import Attachment, Prompt

docs_attachment = Attachment(
    content=str(Path("utils/README.md")),
    mime_type="text/markdown",
    name="Utils Documentation",
    preview=Path("utils/README.md").read_text(),
)

prompt: Prompt = ["Recommend based on weather data.", docs_attachment]
result = harness.run_single(prompt)
```

See: [examples/docs_from_file.py](examples/docs_from_file.py)

---

## RunResult Object

```python
from verif import RunResult

result: RunResult = harness.run_single(task)

result.task          # Original task text
result.answer        # Final submitted answer
result.rubric        # Evaluation rubric used
result.ground_truth  # Expected answer (for eval)
result.history       # List[HistoryEntry] - full execution trace
result.mode          # Mode used: "standard" | "plan" | "explore"
result.plan          # Plan (if plan mode)
result.brief         # Brief (if available)
```

### Execution History

```python
# Get formatted history
print(harness.get_history_markdown())  # Markdown format
print(harness.get_history_text())      # Plain text

# Access raw history entries
for entry in result.history:
    print(f"[{entry.timestamp}] {entry.entry_type}: {entry.content[:100]}")
```

---

## Tools Available to Orchestrator

| Tool | Description | Parallel? |
|------|-------------|-----------|
| `create_brief` | Formalize task requirements | First |
| `create_rubric` | Generate evaluation criteria | Yes |
| `spawn_subagent` | Delegate subtasks | Yes (batch 2-4) |
| `search_web` | Web search (if enabled) | Yes |
| `search_files` | File read/search (if enabled) | Yes |
| `execute_code` | Python REPL (if enabled) | No (sequential) |
| `ask_user` | Request user clarification (if enabled) | Yes |
| `verify_answer` | Check against rubric | No (blocks if questions pending) |
| `submit_answer` | Submit final answer | Last |

---

## Error Handling

```python
import traceback
from verif import RLHarness

harness = RLHarness(provider="gemini")

try:
    result = harness.run_single(task)
except Exception as e:
    # Access partial history even on failure
    print(harness.get_history_markdown())
    print(f"Error: {e}")
```

---

## Complete Example

```python
"""Full example: Research task with streaming and file output."""

import os
from dotenv import load_dotenv
from verif import RLHarness, ProviderConfig
from verif.executor import SubprocessExecutor

load_dotenv()

def main():
    # Event handler for real-time output
    def on_event(entry):
        colors = {
            "system": "\033[94m",
            "model": "\033[92m",
            "tool_call": "\033[93m",
            "tool_response": "\033[95m",
        }
        color = colors.get(entry.entry_type, "")
        reset = "\033[0m" if color else ""
        print(f"{color}[{entry.entry_type.upper()}]{reset} {entry.content[:100]}...")

    # Configure harness
    harness = RLHarness(
        provider=ProviderConfig(name="gemini", thinking_level="MEDIUM"),
        enable_search=True,
        enable_code=True,
        code_executor=SubprocessExecutor("./artifacts"),
        artifacts_dir="./artifacts",
        on_event=on_event,
    )

    # Run task
    result = harness.run_single("""
    Research the top 3 AI frameworks in 2024.
    Create a comparison table and save as comparison.md
    """)

    print("\n" + "="*50)
    print("RESULT")
    print("="*50)
    print(result.answer)
    
    # Save full execution trace
    with open("execution_trace.md", "w") as f:
        f.write(harness.get_history_markdown())

if __name__ == "__main__":
    main()
```

---

## API Reference Summary

### Main Classes

| Class | Purpose |
|-------|---------|
| `RLHarness` | Main orchestrator interface |
| `ProviderConfig` | Provider settings (model, thinking level) |
| `Attachment` | File attachment for multimodal prompts |
| `CompactionConfig` | Context compaction settings |
| `SubprocessExecutor` | Stateful Python code executor |
| `RemoteExecutor` | Frontend-delegated code executor (SSE) |
| `ModeConfig` | Custom mode configuration |
| `RunResult` | Task execution result |
| `HistoryEntry` | Single event in execution trace |

### Key Methods

| Method | Description |
|--------|-------------|
| `harness.run_single(task, mode, ...)` | Execute single task |
| `harness.run_eval(eval_set, ...)` | Batch evaluation |
| `harness.get_history_markdown()` | Get formatted trace |
| `harness.list_modes()` | List available modes |
| `harness.get_mode_config(name)` | Get mode configuration |
| `harness.provider.receive_user_response(id, answers)` | Respond to ask_user questions |

---

## Migration from UI_GUIDE.md

If you were using the FastAPI endpoints, here's how SDK usage maps:

| API Endpoint | SDK Equivalent |
|--------------|----------------|
| `POST /run` | `harness.run_single(task)` |
| `POST /plan/create` | Create plan manually, pass to `run_single(mode="plan", plan=...)` |
| `POST /plan/execute` | `harness.run_single(task, mode="plan", plan=..., rubric=...)` |
| SSE events | `on_event` callback |

The SDK provides more flexibility and direct access to the execution engine.
