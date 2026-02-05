import os
import sys
import subprocess
import tempfile
import json
import asyncio
import uuid
import time
from dataclasses import dataclass, field
from typing import Protocol, Callable, Any
from pathlib import Path


@dataclass
class CodeResult:
    stdout: str
    stderr: str
    artifacts: list[str] = field(default_factory=list)
    error: str | None = None


class CodeExecutor(Protocol):
    def execute(self, code: str) -> CodeResult: ...
    def reset(self) -> None: ...


class SubprocessExecutor:
    """Default stateful executor using persistent Python subprocess."""

    def __init__(self, artifacts_dir: str = "./artifacts", timeout: int = 60):
        self.artifacts_dir = Path(artifacts_dir).resolve()
        self.timeout = timeout
        self._proc: subprocess.Popen | None = None
        self._sentinel = "__CODE_EXEC_DONE__"
        self._start_proc()

    def _start_proc(self):
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        wrapper = f'''
import sys, json, traceback, os
os.chdir({repr(str(self.artifacts_dir))})
_artifacts_dir = {repr(str(self.artifacts_dir))}
_sentinel = {repr(self._sentinel)}
_existing_files = set(os.listdir(_artifacts_dir)) if os.path.exists(_artifacts_dir) else set()

while True:
    try:
        line = sys.stdin.readline()
        if not line:
            break
        code = json.loads(line)
        _existing_files = set(os.listdir(_artifacts_dir)) if os.path.exists(_artifacts_dir) else set()
        try:
            exec(code, globals())
            err = None
        except Exception:
            err = traceback.format_exc()
        new_files = set(os.listdir(_artifacts_dir)) - _existing_files
        artifacts = [os.path.join(_artifacts_dir, f) for f in new_files]
        print(json.dumps({{"error": err, "artifacts": artifacts}}))
        print(_sentinel)
        sys.stdout.flush()
    except Exception as e:
        print(json.dumps({{"error": str(e), "artifacts": []}}))
        print(_sentinel)
        sys.stdout.flush()
'''
        self._proc = subprocess.Popen(
            [sys.executable, "-u", "-c", wrapper],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(self.artifacts_dir),
        )

    def execute(self, code: str) -> CodeResult:
        if not self._proc or self._proc.poll() is not None:
            self._start_proc()

        try:
            self._proc.stdin.write(json.dumps(code) + "\n")
            self._proc.stdin.flush()
        except BrokenPipeError:
            self._start_proc()
            self._proc.stdin.write(json.dumps(code) + "\n")
            self._proc.stdin.flush()

        stdout_lines = []
        try:
            while True:
                line = self._proc.stdout.readline()
                if not line:
                    break
                line = line.rstrip("\n")
                if line == self._sentinel:
                    break
                stdout_lines.append(line)
        except Exception as e:
            return CodeResult(stdout="", stderr="", error=f"Read error: {e}")

        if not stdout_lines:
            return CodeResult(stdout="", stderr="", error="No output from executor")

        # Last line is JSON result, rest is stdout from code
        result_json = stdout_lines[-1] if stdout_lines else "{}"
        output_lines = stdout_lines[:-1]

        try:
            result = json.loads(result_json)
        except json.JSONDecodeError:
            output_lines.append(result_json)
            result = {"error": None, "artifacts": []}

        return CodeResult(
            stdout="\n".join(output_lines),
            stderr="",
            artifacts=result.get("artifacts", []),
            error=result.get("error"),
        )

    def reset(self):
        if self._proc:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._proc.kill()
            self._proc = None
        self._start_proc()

    def __del__(self):
        if self._proc:
            self._proc.terminate()


class RemoteExecutor:
    """Executor that delegates to frontend via SSE/HTTP callback."""

    def __init__(
        self,
        session_id: str,
        emit_event: Callable[[str, dict], None],
        timeout: int = 30,
        sandbox_config: dict | None = None,
    ):
        self.session_id = session_id
        self.emit_event = emit_event
        self.timeout = timeout
        self.sandbox_config = sandbox_config or {}
        self.pending: dict[str, asyncio.Event] = {}
        self.results: dict[str, dict] = {}
        self._loop: asyncio.AbstractEventLoop | None = None

    def set_loop(self, loop: asyncio.AbstractEventLoop):
        self._loop = loop

    def execute(self, code: str) -> CodeResult:
        """Execute code by delegating to frontend. Blocks until response."""
        request_id = str(uuid.uuid4())

        if self._loop and self._loop.is_running():
            # Create event in the event loop's context
            future = asyncio.run_coroutine_threadsafe(
                self._execute_async(request_id, code), self._loop
            )
            try:
                return future.result(timeout=self.timeout + 5)
            except Exception as e:
                return CodeResult(stdout="", stderr="", error=f"Remote execution failed: {e}")
        else:
            return CodeResult(stdout="", stderr="", error="No event loop available")

    async def _execute_async(self, request_id: str, code: str) -> CodeResult:
        event = asyncio.Event()
        self.pending[request_id] = event

        event_data = {
            "request_id": request_id,
            "session_id": self.session_id,
            "tool": "execute_code",
            "args": {"code": code},
            "timeout_ms": self.timeout * 1000,
        }
        if self.sandbox_config:
            event_data["sandbox"] = self.sandbox_config
        self.emit_event("tool_request", event_data)

        try:
            await asyncio.wait_for(event.wait(), timeout=self.timeout)
            result = self.results.pop(request_id, {})
            if result.get("success"):
                data = result.get("data", {})
                return CodeResult(
                    stdout=data.get("stdout", ""),
                    stderr=data.get("stderr", ""),
                    artifacts=data.get("artifacts", []),
                    error=None,
                )
            else:
                return CodeResult(stdout="", stderr="", error=result.get("error", "Unknown error"))
        except asyncio.TimeoutError:
            self.pending.pop(request_id, None)
            return CodeResult(stdout="", stderr="", error=f"Tool timed out after {self.timeout}s")

    def receive_response(self, request_id: str, result: dict):
        """Called by /tool/respond endpoint."""
        if request_id in self.pending:
            self.results[request_id] = result
            self.pending[request_id].set()

    def get_pending_requests(self) -> list[dict]:
        return [{"request_id": rid, "tool": "execute_code"} for rid in self.pending]

    def get_sandbox_context(self) -> str | None:
        """Return sandbox description for orchestrator prompt."""
        if not self.sandbox_config:
            return None
        lines = []
        if t := self.sandbox_config.get("type"):
            lines.append(f"- Runtime: {t}")
        if pkgs := self.sandbox_config.get("packages"):
            lines.append(f"- Available packages: {', '.join(pkgs)}")
        if constraints := self.sandbox_config.get("constraints"):
            lines.append(f"- Constraints: {constraints}")
        return "\n".join(lines) if lines else None

    def reset(self):
        self.pending.clear()
        self.results.clear()
