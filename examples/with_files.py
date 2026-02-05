"""
Working with Files - Multimodal Prompts

WHAT THIS DEMONSTRATES:
- Attaching files to prompts
- Using file preview for context
- Enabling bash for file exploration
- Enabling code execution for output files

EXTRA SETUP NEEDED:
- .env file with API keys
- enable_bash=True for file system access
- enable_code=True + code_executor for file output
- Create Attachment with file path and preview

SUPPORTED FILE TYPES:
- Text files (.txt, .md, .json, .csv) - use preview
- Images (.png, .jpg) - vision models read directly
- PDFs - vision extraction
- Spreadsheets - read via search_files tool
"""

import os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

from verif import RLHarness, ProviderConfig, Attachment, Prompt
from verif.executor import SubprocessExecutor

# =============================================================================
# SETUP: Create sample input file
# =============================================================================

SAMPLE_DIR = Path(__file__).parent / "sample_data"
SAMPLE_DIR.mkdir(exist_ok=True)

SAMPLE_FILE = SAMPLE_DIR / "sales_data.csv"
SAMPLE_CONTENT = """date,product,quantity,revenue
2024-01-15,Widget A,150,4500
2024-01-15,Widget B,80,3200
2024-01-16,Widget A,200,6000
2024-01-16,Widget B,120,4800
2024-01-17,Widget A,175,5250
2024-01-17,Widget B,90,3600
2024-01-18,Widget A,225,6750
2024-01-18,Widget B,110,4400
"""

SAMPLE_FILE.write_text(SAMPLE_CONTENT)
print(f"Created sample file: {SAMPLE_FILE}")

# =============================================================================
# CREATE ATTACHMENT
# =============================================================================

# Read file preview (first N lines for context)
with open(SAMPLE_FILE) as f:
    preview = "".join(f.readlines()[:20])

# Create attachment object
attachment = Attachment(
    content=str(SAMPLE_FILE.absolute()),  # File path (absolute)
    mime_type="text/csv",                  # MIME type
    name="sales_data.csv",                 # Display name
    preview=preview,                        # Content preview for model context
)

# =============================================================================
# BUILD MULTIMODAL PROMPT
# =============================================================================

# Prompt is a list of text + attachments
prompt: Prompt = [
    """Analyze the attached sales data and:
1. Calculate total revenue by product
2. Identify the best performing day
3. Create a summary table
4. Save the analysis as analysis_output.md
""",
    attachment,  # <-- File attachment
]

# =============================================================================
# CONFIGURATION
# =============================================================================

ARTIFACTS_DIR = Path(__file__).parent / "artifacts"
ARTIFACTS_DIR.mkdir(exist_ok=True)

harness = RLHarness(
    provider=ProviderConfig(name="gemini", thinking_level="MEDIUM"),
    enable_search=False,   # Not needed
    enable_bash=True,      # <-- REQUIRED for file exploration
    enable_code=True,      # <-- REQUIRED for saving output files
    code_executor=SubprocessExecutor(str(ARTIFACTS_DIR)),  # <-- REQUIRED
    artifacts_dir=str(ARTIFACTS_DIR),
)

# =============================================================================
# EXECUTION
# =============================================================================

print("\n" + "=" * 60)
print("MULTIMODAL PROMPT WITH FILE ATTACHMENT")
print("=" * 60)
print(f"Input file: {SAMPLE_FILE}")
print(f"Artifacts dir: {ARTIFACTS_DIR}")
print("-" * 60)

result = harness.run_single(prompt)

# =============================================================================
# RESULTS
# =============================================================================

print("\n" + "=" * 60)
print("ANALYSIS OUTPUT")
print("=" * 60)
print(result.answer)

# Check for created artifacts
print("\n" + "=" * 60)
print("CREATED ARTIFACTS")
print("=" * 60)
for f in ARTIFACTS_DIR.iterdir():
    print(f"  - {f.name} ({f.stat().st_size} bytes)")

# Save execution trace
output_dir = Path(__file__).parent / "outputs"
output_dir.mkdir(exist_ok=True)
output_file = output_dir / "with_files_output.md"

with open(output_file, "w") as f:
    f.write("# File Processing Example\n\n")
    f.write(f"## Input File\n`{SAMPLE_FILE}`\n\n")
    f.write(f"## Analysis\n{result.answer}\n\n")
    f.write("---\n\n")
    f.write("## Execution Trace\n\n")
    f.write(harness.get_history_markdown())

print(f"\nFull trace saved to {output_file}")
