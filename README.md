# Knowledge Work SDK

A Python SDK for building AI agents that perform **knowledge work**—research, analysis, writing, and decision-making tasks that require iteration, verification, and structured thinking.

## Why Knowledge Work is Different from Code

Code has a tight feedback loop: write code → run tests → fix errors → repeat. The solution space is constrained—there's usually one correct answer, and automated tests tell you if you found it.

Knowledge work is fundamentally different. **The solution space is vast and underspecified.** A "market analysis" could be a two-paragraph summary or a 50-page deep dive. A "strategy recommendation" could emphasize cost, speed, risk, innovation, or any combination. There's no test suite that returns pass/fail.

**Our approach:** Since knowledge work lacks natural verification, we synthesize one using *rubrics*. A rubric defines what "good" looks like before execution begins, enabling:

- **Self-verification**: The agent checks its own work against explicit criteria
- **Iterative refinement**: Failed verification triggers targeted improvement
- **Transparent evaluation**: Humans can audit the rubric and verification process

This SDK implements a **self-verifying agentic loop** that brings structure to the inherently open-ended nature of knowledge work.

## The Verification Loop

```
┌─────────────────────────────────────────────────────────────┐
│  1. BRIEF CREATION                                          │
│     → Formalize task into structured requirements           │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  2. RUBRIC CREATION                                         │
│     → Generate evaluation criteria (hidden from executor)   │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  3. TASK EXECUTION                                          │
│     → Orchestrator delegates to subagents, runs searches    │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  4. VERIFICATION                                            │
│     → Check answer against rubric → PASS or FAIL            │
└─────────────────────────────────────────────────────────────┘
                          ↓ (if FAIL)
                    ← ITERATE ←
                          ↓ (if PASS)
┌─────────────────────────────────────────────────────────────┐
│  5. SUBMISSION                                              │
│     → Submit verified answer                                │
└─────────────────────────────────────────────────────────────┘
```

## Installation

### As a dependency (recommended)

```bash
uv pip install git+https://github.com/ClioAI/kw-sdk.git
```

Or add to your `pyproject.toml`:

```toml
dependencies = [
    "verif @ git+https://github.com/ClioAI/kw-sdk.git",
]
```

### For development

```bash
git clone https://github.com/ClioAI/kw-sdk.git
cd kw-sdk
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"
```

Create a `.env` file:
```bash
GEMINI_API_KEY=your_gemini_key
OPENAI_API_KEY=your_openai_key
```

## Quick Start

```python
from verif import RLHarness

harness = RLHarness(provider="gemini")
result = harness.run_single("Analyze the economic impact of remote work on urban real estate.")

print(result.answer)  # The analysis
print(result.rubric)  # Auto-generated evaluation criteria
```

---

## Execution Modes

The SDK provides different modes optimized for different types of knowledge work:

| Mode | Best For | Rubric Strategy |
|------|----------|-----------------|
| **`standard`** | General research & analysis | Auto-created during execution |
| **`plan`** | Complex multi-step tasks | User-provided or auto-created |
| **`explore`** | Creative/divergent thinking | Quality checklist (no accuracy rubric) |
| **`iterate`** | Refining existing work | Uses existing rubric + feedback |

### Standard Mode (Default)

For general tasks. The orchestrator creates brief and rubric automatically.

```python
from verif import RLHarness

harness = RLHarness(provider="gemini", enable_search=True)

result = harness.run_single(
    "Compare carbon tax vs cap-and-trade for reducing industrial emissions."
)

print(result.answer)
print(result.rubric)  # Auto-generated
```

See: [examples/standard_mode.py](examples/standard_mode.py)

### Plan Mode

For structured execution with explicit control over strategy.

```python
from verif import RLHarness

harness = RLHarness(provider="gemini", enable_search=True)

PLAN = """
## Investigation Phase
1. Research incident postmortem best practices
2. Identify key sections for blameless postmortems

## Writing Phase
3. Write executive summary
4. Document timeline with timestamps
5. Describe root cause analysis
"""

RUBRIC = """
## Structure (40 points)
- [ ] Has executive summary
- [ ] Includes timeline with timestamps
- [ ] Contains root cause analysis

## Blameless Culture (30 points)
- [ ] No individual blame
- [ ] Uses "we" language
"""

result = harness.run_single(
    task="Write a postmortem for a 47-minute database outage.",
    mode="plan",
    plan=PLAN,
    rubric=RUBRIC,  # Optional - omit to auto-create
)
```

See: [examples/plan_mode.py](examples/plan_mode.py)

### Explore Mode

For divergent thinking—generate multiple distinct perspectives.

```python
from verif import RLHarness

harness = RLHarness(provider="gemini", enable_search=True)

result = harness.run_single(
    task="""Explore database architectures for a fintech handling 10K TPS 
    with strong consistency and multi-region deployment.""",
    mode="explore",
    num_takes=3,  # Generate 3 distinct approaches
)

# Result contains multiple takes separated by ===
takes = result.answer.split("===")
for i, take in enumerate(takes, 1):
    print(f"--- Approach {i} ---\n{take[:500]}...")
```

Each take includes:
- The solution/recommendation
- **Assumptions**: What must be true for this to work
- **Counterfactual**: What could make this fail

See: [examples/explore_mode.py](examples/explore_mode.py)

### Iterate Mode

For refining existing work based on user feedback.

```python
# Initial execution
result = harness.run_single(task="Write a market analysis memo.")

# User provides feedback
iterate_result = harness.iterate(
    task="Write a market analysis memo.",
    answer=result.answer,
    rubric=result.rubric,
    feedback="Use 2024 data instead of 2023. Add executive summary.",
    rubric_update="Must address data residency requirements.",  # Optional
)

print(iterate_result.answer)  # Refined version
```

See: [examples/iterate_workflow.py](examples/iterate_workflow.py)

---

## Composing Workflows

### Explore → Select → Execute

The most powerful pattern: brainstorm, pick the best approach, then execute.

```python
# Stage 1: Explore multiple approaches
explore_result = harness.run_single(task=TASK, mode="explore", num_takes=3)
takes = explore_result.answer.split("===")

# Stage 2: Use LLM to select best approach
selector = GeminiProvider()
selection = selector.generate(f"Pick the best approach:\n{explore_result.answer}")

# Stage 3: Execute with selected plan
final_result = harness.run_single(
    task=TASK,
    mode="plan",
    plan=selected_plan,
    rubric=selected_rubric,
)
```

See: [examples/end_to_end_workflow.py](examples/end_to_end_workflow.py)

---

## Enabling Capabilities

### Web Search

```python
harness = RLHarness(
    provider="gemini",
    enable_search=True,  # Adds search_web tool
)
```

### File System Access

```python
harness = RLHarness(
    provider="gemini",
    enable_bash=True,  # Adds search_files tool (ls, find, grep, cat)
)
```

### Code Execution

```python
from verif.executor import SubprocessExecutor

harness = RLHarness(
    provider="gemini",
    enable_code=True,
    code_executor=SubprocessExecutor("./artifacts"),
    artifacts_dir="./artifacts",
)
```

The code executor is **stateful**—variables persist across calls. Files saved to `artifacts_dir` are tracked and returned.

See: [examples/with_code_execution.py](examples/with_code_execution.py)

### Working with Files

```python
from verif import RLHarness, Attachment, Prompt

# Create attachment with preview
attachment = Attachment(
    content="/path/to/data.csv",
    mime_type="text/csv",
    name="data.csv",
    preview="col1,col2\n1,2\n3,4...",  # First N lines
)

# Build multimodal prompt
prompt: Prompt = [
    "Analyze the attached sales data and create a summary.",
    attachment,
]

result = harness.run_single(prompt)
```

See: [examples/with_files.py](examples/with_files.py)

---

## Streaming Events

```python
from verif import RLHarness, HistoryEntry

def on_event(event: HistoryEntry):
    if event.entry_type == "tool_call":
        print(f"→ {event.content}")
    elif event.entry_type == "thought":
        print(f"💭 {event.content[:100]}...")

harness = RLHarness(
    provider="gemini",
    on_event=on_event,
    stream=True,           # Stream orchestrator output
    stream_subagents=True, # Stream subagent output
)
```

See: [examples/with_streaming.py](examples/with_streaming.py)

---

## Configuration Reference

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
    enable_bash=False,      # File system navigation
    enable_code=False,      # Python code execution
    
    # Code Execution (required if enable_code=True)
    code_executor=SubprocessExecutor("./artifacts"),
    artifacts_dir="./artifacts",
    
    # Execution Limits
    max_iterations=30,
    
    # Mode Selection
    default_mode="standard",  # "standard" | "plan" | "explore"
    
    # Pre-set Rubric (optional)
    rubric="1. Must be accurate\n2. Must cite sources",
    
    # Event Streaming
    on_event=lambda e: print(f"[{e.entry_type}] {e.content[:100]}"),
    stream=True,
    stream_subagents=True,
    
    # Context Compaction (for long tasks)
    compaction_config=CompactionConfig(
        enabled=True,
        threshold=0.8,        # Trigger at 80% context capacity
        keep_recent_turns=3,
    ),
)
```

---

## Result Objects

### RunResult

```python
result = harness.run_single(task)

result.task          # Original task text
result.answer        # Final submitted answer
result.rubric        # Evaluation rubric used
result.history       # List[HistoryEntry] - full execution trace
result.mode          # Mode used: "standard" | "plan" | "explore"
result.plan          # Plan (if plan mode)
result.brief         # Brief (if available)
```

### Execution Trace

```python
# Get formatted history
print(harness.get_history_markdown())
print(harness.get_history_text())

# Access raw entries
for entry in result.history:
    print(f"[{entry.timestamp}] {entry.entry_type}: {entry.content[:100]}")
```

---

## Tools Available to Orchestrator

| Tool | Description | When Available |
|------|-------------|----------------|
| `create_brief` | Formalize task requirements | standard, explore |
| `create_rubric` | Generate evaluation criteria | standard, plan |
| `spawn_subagent` | Delegate subtasks | All modes |
| `search_web` | Web search | `enable_search=True` |
| `search_files` | File read/search | `enable_bash=True` |
| `execute_code` | Python REPL | `enable_code=True` |
| `verify_answer` | Check against rubric | standard, plan, iterate |
| `verify_exploration` | Check quality checklist | explore |
| `submit_answer` | Submit final answer | All modes |

---

## Pending Work / Roadmap

### Computer Use Subagent
Attach a computer-use capable subagent for tasks requiring GUI interaction—filling forms, navigating apps, extracting data from web interfaces.

### Multi-App Support
Enable working across different applications (browsers, spreadsheets, documents) in a single workflow.

### State Checkpointing
Save execution state at any step. Resume or re-execute from any checkpoint with modifications—"what if I changed step 3?"

### Step Replay
Re-run from any intermediate step with different parameters or context, without re-executing prior steps.

### Custom Provider Support
Enable adding new model providers (Anthropic, OpenRouter, local models) via a clean `BaseProvider` interface. Currently supports Gemini and OpenAI.

---

## Examples

| Example | Description |
|---------|-------------|
| [standard_mode.py](examples/standard_mode.py) | Basic task with auto rubric |
| [plan_mode.py](examples/plan_mode.py) | User-defined plan and rubric |
| [explore_mode.py](examples/explore_mode.py) | Multiple divergent approaches |
| [iterate_workflow.py](examples/iterate_workflow.py) | Refining with user feedback |
| [end_to_end_workflow.py](examples/end_to_end_workflow.py) | Explore → Select → Execute |
| [with_code_execution.py](examples/with_code_execution.py) | Stateful Python REPL |
| [with_files.py](examples/with_files.py) | Multimodal prompts with attachments |
| [with_streaming.py](examples/with_streaming.py) | Real-time event streaming |
| [with_custom_executor.py](examples/with_custom_executor.py) | Custom sandboxed executor |

### Example Outputs

See [examples/outputs/](examples/outputs/) for sample execution results:

| Output | Description |
|--------|-------------|
| [standard_mode_output.md](examples/outputs/standard_mode_output.md) | Carbon tax vs cap-and-trade analysis with auto-generated rubric |
| [iterate_workflow_output.md](examples/outputs/iterate_workflow_output.md) | Iteration example showing refinement based on feedback |

---

## License

MIT
