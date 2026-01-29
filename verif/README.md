# verif SDK

Standalone SDK for AI-powered task orchestration with iterative verification.

## Installation

```bash
uv pip install -e .
```

Requires `GEMINI_API_KEY` or `OPENAI_API_KEY` in environment (or pass via `ProviderConfig`).

## Quick Start

```python
from verif import RLHarness

result = RLHarness().run_single("What is 2+2?")
print(result.answer)
```

## Usage

### With Provider Config

```python
from verif import RLHarness, ProviderConfig

config = ProviderConfig(
    name="gemini",           # "gemini" | "openai"
    api_key="...",           # Optional, defaults to env var
    thinking_level="HIGH",   # Gemini: LOW/MEDIUM/HIGH
)
harness = RLHarness(provider=config, enable_search=True)
result = harness.run_single("Research quantum computing")
```

### With Event Streaming

```python
from verif import RLHarness

def on_event(e):
    print(f"[{e.entry_type}] {e.content[:100]}")

harness = RLHarness(on_event=on_event)
result = harness.run_single("Analyze this dataset")
```

### With Pre-set Rubric

```python
rubric = "Must include: executive summary, methodology, conclusions"
harness = RLHarness(rubric=rubric)
result = harness.run_single("Write a report on...")
```

### Plan Mode (Execute with Pre-defined Plan)

```python
harness = RLHarness(provider="gemini", enable_search=True)

# User provides a plan (created externally or by the user)
plan = """
# Execution Plan
## Steps
1. Research market size and growth trends
2. Analyze top 3 competitors
3. Synthesize findings into executive summary
"""

result = harness.run_single(
    task="Analyze the EV market opportunity",
    mode="plan",
    plan=plan,
    rubric="Must include: market sizing, competitor analysis, recommendations"  # optional
)
```

## RLHarness Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `provider` | `str \| ProviderConfig` | `"gemini"` | Provider name or config object |
| `enable_search` | `bool` | `False` | Enable web search tool |
| `enable_bash` | `bool` | `False` | Enable bash command execution |
| `enable_code` | `bool` | `False` | Enable Python code execution |
| `max_iterations` | `int` | `30` | Max orchestrator loop iterations |
| `default_mode` | `str` | `"standard"` | Default mode ("standard", "plan", "explore") |
| `rubric` | `str \| None` | `None` | Pre-set evaluation rubric |
| `on_event` | `callable` | `None` | Event callback for streaming |
| `attachments` | `list[Attachment]` | `[]` | Files to include with task |

## Wrapper Responsibilities

The SDK handles orchestration. Wrappers must handle:

| Concern | SDK | Wrapper |
|---------|-----|---------|
| Task orchestration | ✓ | |
| Provider abstraction | ✓ | |
| Tool execution | ✓ | |
| Event emission | ✓ | |
| API key management | | ✓ |
| Rubric persistence | | ✓ |
| Event → UI transform | | ✓ |
| SSE/HTTP serialization | | ✓ |
| Filesystem sandboxing | | ✓ |

### Event Handling

SDK emits `HistoryEntry` events via `on_event` callback:

```python
@dataclass
class HistoryEntry:
    entry_type: str  # "thought", "tool_call", "tool_response", "error", "system"
    content: str
    timestamp: float
    metadata: dict | None
```

Wrappers transform these to UI-appropriate formats (SSE, WebSocket, TTY output).

### Rubric Storage

SDK accepts rubrics but doesn't persist them. Wrappers manage storage:

```python
# Wrapper example
rubric_store: dict[str, str] = {}

def save_rubric(plan_id: str, rubric: str):
    rubric_store[plan_id] = rubric

def load_rubric(plan_id: str) -> str | None:
    return rubric_store.get(plan_id)
```

### Attachments

For file-based tasks, wrappers create `Attachment` objects:

```python
from verif import RLHarness, Attachment

attachments = [
    Attachment(
        content="/path/to/file.csv",
        mime_type="text/csv",
        name="data.csv",
        preview="col1,col2\n1,2\n3,4..."  # First 100 lines for text files
    )
]
harness = RLHarness(attachments=attachments)
```

- **Images/PDFs**: No preview needed, LLM processes directly
- **Text files**: Wrapper provides preview; orchestrator uses `search_files` tool for full access

### Handling DOCX, XLSX, PPTX

Office documents must be converted to text before passing to the SDK. The wrapper handles conversion:

```python
from docx import Document
from pathlib import Path
from verif import RLHarness, Attachment, Prompt

def extract_docx_to_text(docx_path: Path) -> Path:
    """Convert DOCX to plain text file."""
    txt_path = docx_path.with_suffix(".txt")
    if txt_path.exists():
        return txt_path
    
    doc = Document(str(docx_path))
    content = []
    
    # Extract paragraphs
    for para in doc.paragraphs:
        if para.text.strip():
            content.append(para.text)
    
    # Extract tables
    for table in doc.tables:
        content.append("\n--- TABLE ---")
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells]
            content.append(" | ".join(cells))
        content.append("--- END TABLE ---\n")
    
    txt_path.write_text("\n".join(content))
    return txt_path

# Convert and create attachment
txt_path = extract_docx_to_text(Path("quotes.docx"))

# Read preview (first 100 lines)
with open(txt_path, 'r') as f:
    preview = ''.join(f.readlines()[:100])

attachment = Attachment(
    content=str(txt_path),
    mime_type="text/plain",
    name="quotes.txt",
    preview=preview,
)

# Create multimodal prompt
prompt: Prompt = [
    "Analyze the attached vendor quotes and recommend a supplier.",
    attachment,
]

# Run with code execution for saving output files
harness = RLHarness(
    enable_code=True,
    artifacts_dir="./artifacts",
)
result = harness.run_single(prompt)
```

### Supported File Types

| Format | SDK Support | Wrapper Options |
|--------|-------------|-----------------|
| `.txt`, `.csv`, `.md`, `.json` | ✓ Direct | Provide preview (any length) |
| `.pdf`, images | ✓ Direct | Pass as-is (LLM vision) |
| `.docx`, `.xlsx`, `.pptx` | ✗ | Convert to `.txt` or `.pdf` |

### Hybrid Approach: Preview + PDF

For best results with complex documents, send both a text preview AND the PDF:

```python
from verif import Attachment, Prompt

# Extract text for searchable preview (can be full document)
text_content = extract_docx_to_text(Path("report.docx")).read_text()

# Convert to PDF for visual fidelity
pdf_path = convert_to_pdf(Path("report.docx"))  # wrapper implements this

prompt: Prompt = [
    "Analyze the attached report.",
    Attachment(
        content=text_content,  # Full text as preview
        mime_type="text/plain",
        name="report_text.txt",
        preview=text_content,  # Orchestrator sees this in context
    ),
    Attachment(
        content=str(pdf_path),  # PDF for visual analysis
        mime_type="application/pdf",
        name="report.pdf",
    ),
]
```

This gives the orchestrator:
- **Text preview**: Searchable, can be any length (full doc or excerpt)
- **PDF**: Visual layout, tables, charts via LLM vision

## Code Execution

The SDK supports stateful Python code execution via the `execute_code` tool.

### Executor Protocol

Wrappers **must provide** an executor—no default to prevent accidental unsandboxed execution:

```python
from verif import RLHarness
from verif.executor import SubprocessExecutor, CodeExecutor, CodeResult

# SubprocessExecutor: unsandboxed, local execution (dev/trusted environments)
harness = RLHarness(
    enable_code=True,
    code_executor=SubprocessExecutor("./artifacts"),
    artifacts_dir="./artifacts",
)
```

### Custom Executor (Sandboxed)

Implement `CodeExecutor` protocol for Docker, Firecracker, or other sandboxed environments:

```python
from dataclasses import dataclass
from typing import Protocol

@dataclass
class CodeResult:
    stdout: str
    stderr: str
    artifacts: list[str]  # paths to created files
    error: str | None = None

class CodeExecutor(Protocol):
    def execute(self, code: str) -> CodeResult: ...
    def reset(self) -> None: ...  # clear state between runs

# Example: Docker-based executor
class DockerExecutor:
    def __init__(self, image: str, artifacts_dir: str):
        self.image = image
        self.artifacts_dir = artifacts_dir
    
    def execute(self, code: str) -> CodeResult:
        # Run code in container, copy artifacts out
        ...
    
    def reset(self) -> None:
        # Destroy container, start fresh
        ...

harness = RLHarness(
    enable_code=True,
    code_executor=DockerExecutor("python:3.11", "./artifacts"),
    artifacts_dir="./artifacts",
)
```

### Execution Behavior

- **Stateful**: Variables persist across `execute_code` calls within a run
- **Artifacts**: Files saved to `artifacts_dir` are tracked and returned in result
- **Libraries**: Common packages available (pandas, openpyxl, matplotlib, etc.)

## Exports

```python
from verif import (
    RLHarness,      # Main orchestrator
    RunResult,      # Result from run_single()
    ProviderConfig, # Provider configuration
    HistoryEntry,   # Event type
    Attachment,     # File attachment
)
```
