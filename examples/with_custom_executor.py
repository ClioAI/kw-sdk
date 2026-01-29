"""
Custom Code Executor Example - Configurable Python Environment

WHAT THIS DEMONSTRATES:
- Creating a custom executor with preamble code
- Passing environment setup to code execution
- Pre-loading variables, functions, or imports

THIS IS USEFUL WHEN:
- You need specific imports available by default
- You want to inject data/context into the execution environment
- You need custom helper functions available to the LLM
- You want to restrict or extend the execution environment

FLOW:
┌─────────────────────────────────────────────────────────────┐
│  CUSTOM EXECUTOR                                            │
│  → Define preamble code (imports, helpers, data)            │
│  → Executor runs preamble before each reset                 │
└─────────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────┐
│  HARNESS                                                    │
│  → Pass custom executor via code_executor param             │
│  → LLM code has access to preamble environment              │
└─────────────────────────────────────────────────────────────┘
"""

import sys
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

from verif import RLHarness, HistoryEntry
from verif.config import ProviderConfig
from verif.executor import SubprocessExecutor, CodeResult

# =============================================================================
# CUSTOM EXECUTOR WITH PREAMBLE
# =============================================================================

class PreambleExecutor:
    """
    Executor that runs preamble code to set up the environment.

    The preamble runs once on initialization and after each reset,
    making variables, functions, and imports available to all subsequent code.
    """

    def __init__(self, artifacts_dir: str, preamble: str, timeout: int = 60):
        self.artifacts_dir = artifacts_dir
        self.preamble = preamble
        self.timeout = timeout
        self._inner = SubprocessExecutor(artifacts_dir=artifacts_dir, timeout=timeout)
        # Run preamble on init
        self._run_preamble()

    def _run_preamble(self):
        """Execute preamble code to set up environment."""
        if self.preamble.strip():
            result = self._inner.execute(self.preamble)
            if result.error:
                print(f"Warning: Preamble error: {result.error}", file=sys.stderr)

    def execute(self, code: str) -> CodeResult:
        """Execute code in the pre-configured environment."""
        return self._inner.execute(code)

    def reset(self):
        """Reset executor and re-run preamble."""
        self._inner.reset()
        self._run_preamble()

# =============================================================================
# EVENT HANDLER
# =============================================================================

def on_event(event: HistoryEntry):
    """Stream key events to console for progress visibility."""
    if event.entry_type == "tool_call":
        if "execute_code" in event.content:
            print(f"  → executing code...")
        else:
            print(f"  → {event.content}")

# =============================================================================
# SETUP
# =============================================================================

ARTIFACTS_DIR = Path(__file__).parent / "artifacts"
ARTIFACTS_DIR.mkdir(exist_ok=True)

# Clean previous artifacts
for f in ARTIFACTS_DIR.glob("*"):
    if f.is_file():
        f.unlink()

# =============================================================================
# DEFINE PREAMBLE - Environment Setup
# =============================================================================

# This code runs BEFORE any LLM-generated code
# Variables, functions, and imports defined here are available to the LLM

PREAMBLE = '''
# =============================================================================
# PRE-LOADED ENVIRONMENT
# =============================================================================

# Data that the LLM can use
COMPANY_DATA = {
    "name": "Acme Corp",
    "founded": 2015,
    "employees": 150,
    "revenue_millions": [12, 18, 25, 32, 41],  # Last 5 years
    "departments": ["Engineering", "Sales", "Marketing", "Operations", "HR"],
}

QUARTERLY_METRICS = {
    "Q1": {"revenue": 8.2, "costs": 6.1, "customers": 1200},
    "Q2": {"revenue": 9.5, "costs": 6.8, "customers": 1450},
    "Q3": {"revenue": 11.1, "costs": 7.2, "customers": 1680},
    "Q4": {"revenue": 12.3, "costs": 7.9, "customers": 1920},
}

# Helper functions available to LLM
def calculate_growth(values):
    """Calculate year-over-year growth rates."""
    return [(values[i] - values[i-1]) / values[i-1] * 100
            for i in range(1, len(values))]

def format_currency(amount):
    """Format number as currency."""
    return f"${amount:,.2f}"

def save_report(filename, content):
    """Save content to a file in artifacts directory."""
    with open(filename, 'w') as f:
        f.write(content)
    return f"Saved to {filename}"

print("Environment loaded: COMPANY_DATA, QUARTERLY_METRICS, helper functions available")
'''

print(f"Artifacts directory: {ARTIFACTS_DIR}")
print(f"Preamble: {len(PREAMBLE.splitlines())} lines of setup code")

# =============================================================================
# CREATE CUSTOM EXECUTOR
# =============================================================================

executor = PreambleExecutor(
    artifacts_dir=str(ARTIFACTS_DIR),
    preamble=PREAMBLE,
    timeout=60,
)

# =============================================================================
# CONFIGURATION
# =============================================================================

harness = RLHarness(
    provider=ProviderConfig(name="gemini", thinking_level="MEDIUM"),
    enable_search=False,
    enable_bash=False,
    enable_code=True,
    code_executor=executor,  # <-- Custom executor with preamble
    artifacts_dir=str(ARTIFACTS_DIR),
    on_event=on_event,
)

# =============================================================================
# TASK EXECUTION
# =============================================================================

# The LLM doesn't need to define COMPANY_DATA or helpers - they're pre-loaded!
task = """
Using the pre-loaded COMPANY_DATA and QUARTERLY_METRICS:

1. Calculate the 5-year revenue growth rate using calculate_growth()
2. Analyze quarterly performance (which quarter was best?)
3. Calculate total annual revenue and profit margin
4. Generate a brief executive summary

Save the analysis to "company_analysis.txt" using save_report()
"""

print("\n" + "=" * 60)
print("CUSTOM EXECUTOR EXAMPLE")
print("=" * 60)
print(f"Task: Company Data Analysis (using pre-loaded environment)")
print("-" * 60)

try:
    result = harness.run_single(task)
except Exception as e:
    print(f"\n❌ Error during execution: {e}", file=sys.stderr)
    sys.exit(1)

if not result.answer:
    print("\n❌ No answer was generated", file=sys.stderr)
    sys.exit(1)

# =============================================================================
# RESULTS
# =============================================================================

print("\n" + "=" * 60)
print("ANALYSIS SUMMARY")
print("=" * 60)
print(result.answer)

# =============================================================================
# CHECK CREATED ARTIFACTS
# =============================================================================

print("\n" + "=" * 60)
print("CREATED ARTIFACTS")
print("=" * 60)

artifacts = list(ARTIFACTS_DIR.iterdir())
if artifacts:
    for f in artifacts:
        size = f.stat().st_size
        print(f"  ✓ {f.name} ({size:,} bytes)")
        # Show content of text files
        if f.suffix == '.txt' and size < 2000:
            print(f"    Content preview:")
            content = f.read_text()[:500]
            for line in content.split('\n')[:10]:
                print(f"      {line}")
else:
    print("  No artifacts created")

# =============================================================================
# SAVE OUTPUT
# =============================================================================

output_dir = Path("examples/outputs")
output_dir.mkdir(parents=True, exist_ok=True)

output_file = output_dir / "with_custom_executor_output.md"
with open(output_file, "w") as f:
    f.write("# Custom Executor Example\n\n")
    f.write(f"## Preamble Code\n```python\n{PREAMBLE}\n```\n\n")
    f.write(f"## Task\n{task}\n\n")
    f.write(f"## Summary\n{result.answer}\n\n")
    f.write("---\n\n")
    f.write("## Created Artifacts\n\n")
    for artifact in artifacts:
        f.write(f"- `{artifact.name}` ({artifact.stat().st_size:,} bytes)\n")
    f.write("\n---\n\n")
    f.write("## Execution Trace\n\n")
    f.write(harness.get_history_markdown())

print(f"\n✓ Full trace saved to {output_file}")

# =============================================================================
# USAGE NOTES
# =============================================================================

print(f"\n✓ Done")

# =============================================================================
# ALTERNATIVE EXECUTOR IMPLEMENTATIONS (commented out examples)
# =============================================================================

# The CodeExecutor protocol only requires two methods:
#   - execute(code: str) -> CodeResult
#   - reset() -> None
#
# This means you can implement ANY execution backend:

# -----------------------------------------------------------------------------
# DOCKER EXECUTOR
# -----------------------------------------------------------------------------
#
# class DockerExecutor:
#     """Execute code in an isolated Docker container."""
#
#     def __init__(self, image: str = "python:3.11-slim", artifacts_dir: str = "./artifacts"):
#         import docker
#         self.client = docker.from_env()
#         self.image = image
#         self.artifacts_dir = Path(artifacts_dir).resolve()
#         self.artifacts_dir.mkdir(parents=True, exist_ok=True)
#         self.container = None
#         self._start_container()
#
#     def _start_container(self):
#         self.container = self.client.containers.run(
#             self.image,
#             command="python -u -i",
#             stdin_open=True,
#             tty=True,
#             detach=True,
#             volumes={str(self.artifacts_dir): {"bind": "/artifacts", "mode": "rw"}},
#             working_dir="/artifacts",
#             mem_limit="512m",
#             cpu_period=100000,
#             cpu_quota=50000,  # 50% CPU
#         )
#
#     def execute(self, code: str) -> CodeResult:
#         exit_code, output = self.container.exec_run(
#             ["python", "-c", code],
#             workdir="/artifacts",
#         )
#         return CodeResult(
#             stdout=output.decode() if exit_code == 0 else "",
#             stderr=output.decode() if exit_code != 0 else "",
#             error=None if exit_code == 0 else f"Exit code: {exit_code}",
#         )
#
#     def reset(self):
#         if self.container:
#             self.container.stop()
#             self.container.remove()
#         self._start_container()
#
# # Usage:
# # executor = DockerExecutor(image="python:3.11-slim", artifacts_dir="./artifacts")
# # harness = RLHarness(enable_code=True, code_executor=executor, ...)

# -----------------------------------------------------------------------------
# E2B EXECUTOR (cloud sandboxed execution)
# -----------------------------------------------------------------------------
#
# class E2BExecutor:
#     """Execute code in E2B cloud sandbox."""
#
#     def __init__(self, api_key: str = None):
#         from e2b_code_interpreter import CodeInterpreter
#         self.api_key = api_key or os.environ.get("E2B_API_KEY")
#         self.sandbox = CodeInterpreter(api_key=self.api_key)
#
#     def execute(self, code: str) -> CodeResult:
#         execution = self.sandbox.notebook.exec_cell(code)
#         return CodeResult(
#             stdout="\n".join(str(r) for r in execution.results),
#             stderr=execution.error.traceback if execution.error else "",
#             error=str(execution.error) if execution.error else None,
#         )
#
#     def reset(self):
#         self.sandbox.close()
#         from e2b_code_interpreter import CodeInterpreter
#         self.sandbox = CodeInterpreter(api_key=self.api_key)
#
# # Usage:
# # executor = E2BExecutor()
# # harness = RLHarness(enable_code=True, code_executor=executor, ...)

# -----------------------------------------------------------------------------
# MODAL EXECUTOR (serverless cloud execution)
# -----------------------------------------------------------------------------
#
# class ModalExecutor:
#     """Execute code on Modal serverless infrastructure."""
#
#     def __init__(self):
#         import modal
#         self.app = modal.App("code-executor")
#         self.sandbox = modal.Sandbox.create(app=self.app)
#
#     def execute(self, code: str) -> CodeResult:
#         process = self.sandbox.exec("python", "-c", code)
#         process.wait()
#         return CodeResult(
#             stdout=process.stdout.read(),
#             stderr=process.stderr.read(),
#             error=None if process.returncode == 0 else f"Exit: {process.returncode}",
#         )
#
#     def reset(self):
#         self.sandbox.terminate()
#         import modal
#         self.sandbox = modal.Sandbox.create(app=self.app)
#
# # Usage:
# # executor = ModalExecutor()
# # harness = RLHarness(enable_code=True, code_executor=executor, ...)

# -----------------------------------------------------------------------------
# PYODIDE/WASM EXECUTOR (browser-safe execution)
# -----------------------------------------------------------------------------
#
# class PyodideExecutor:
#     """Execute code in Pyodide WebAssembly runtime."""
#
#     def __init__(self):
#         from pyodide import eval_code
#         self.globals = {}
#
#     def execute(self, code: str) -> CodeResult:
#         import io, sys
#         stdout_capture = io.StringIO()
#         old_stdout = sys.stdout
#         try:
#             sys.stdout = stdout_capture
#             exec(code, self.globals)
#             return CodeResult(stdout=stdout_capture.getvalue(), stderr="", error=None)
#         except Exception as e:
#             return CodeResult(stdout="", stderr="", error=str(e))
#         finally:
#             sys.stdout = old_stdout
#
#     def reset(self):
#         self.globals = {}
#
# # Usage:
# # executor = PyodideExecutor()
# # harness = RLHarness(enable_code=True, code_executor=executor, ...)

# -----------------------------------------------------------------------------
# FIRECRACKER/MICROVM EXECUTOR (maximum isolation)
# -----------------------------------------------------------------------------
#
# class FirecrackerExecutor:
#     """Execute code in Firecracker microVM for maximum isolation."""
#
#     def __init__(self, kernel_path: str, rootfs_path: str):
#         # Firecracker setup is complex - this is a simplified example
#         self.kernel_path = kernel_path
#         self.rootfs_path = rootfs_path
#         self.vm = None
#         self._start_vm()
#
#     def _start_vm(self):
#         # Start Firecracker microVM via API
#         # See: https://github.com/firecracker-microvm/firecracker
#         pass
#
#     def execute(self, code: str) -> CodeResult:
#         # Send code to VM via vsock or SSH
#         # Return result
#         pass
#
#     def reset(self):
#         # Destroy and recreate VM for clean state
#         pass
#
# # Usage:
# # executor = FirecrackerExecutor(kernel_path="...", rootfs_path="...")
# # harness = RLHarness(enable_code=True, code_executor=executor, ...)
