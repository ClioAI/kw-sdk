"""
Example: Documentation as File Attachment

Pattern:
1. Keep docs in a file alongside your utils (utils/README.md)
2. Attach the docs file to the prompt (with preview)
3. Model sees docs in context, then calls functions

Benefits:
- Docs live with code (easy to maintain)
- Model gets docs via attachment preview
- No "read file" step - docs are immediate context
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verif import RLHarness, ProviderConfig, Attachment, Prompt
from verif.executor import SubprocessExecutor

# =============================================================================
# EVENT HANDLER
# =============================================================================

def on_event(entry):
    """Print key events as they happen."""
    etype = entry.entry_type
    content = entry.content[:120].replace('\n', ' ')

    if etype == "tool_call":
        print(f"  → {content}...")
    elif etype == "tool_error":
        print(f"  ✗ {content}...")

# =============================================================================
# ATTACH DOCS FILE
# =============================================================================

EXAMPLES_DIR = Path(__file__).parent
DOCS_FILE = EXAMPLES_DIR / "utils" / "README.md"

docs_attachment = Attachment(
    content=str(DOCS_FILE.absolute()),
    mime_type="text/markdown",
    name="Weather Utils Documentation",
    preview=DOCS_FILE.read_text(),  # Model sees this immediately
)

# =============================================================================
# TASK WITH ATTACHMENT
# =============================================================================

task_text = f"""I'm planning a weekend trip: Tokyo, Sydney, or London.
Recommend based on current weather (15-25°C ideal, less rain better).

The attached documentation describes available weather functions.

IMPORTANT: Before importing, run:
```python
import sys
sys.path.insert(0, '{EXAMPLES_DIR}')
from utils.weather import compare_cities
```

Call compare_cities() and recommend with specific numbers.
"""

prompt: Prompt = [task_text, docs_attachment]

# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    config = ProviderConfig(name="gemini", thinking_level="MEDIUM")

    harness = RLHarness(
        provider=config,
        enable_code=True,
        code_executor=SubprocessExecutor(artifacts_dir=str(EXAMPLES_DIR / "outputs")),
        on_event=on_event,
    )

    print("Task: Weather recommendation (docs from file)")
    print(f"Docs: {DOCS_FILE}")
    print("-" * 60)

    result = harness.run_single(prompt)

    # Save output
    output_dir = EXAMPLES_DIR / "outputs"
    output_dir.mkdir(exist_ok=True)

    with open(output_dir / "docs_from_file_output.md", "w") as f:
        f.write("# Docs From File Example\n\n")
        f.write("## Pattern\n```python\n")
        f.write("docs = Attachment(content=path, preview=content)\n")
        f.write("prompt = [task_text, docs]\n```\n\n")
        f.write(f"## Answer\n{result.answer}\n")

    print(f"\nOutput: {output_dir}/docs_from_file_output.md")
    print(f"\nAnswer preview:\n{result.answer[:500]}...")
