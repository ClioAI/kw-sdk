import os
import sys
import subprocess
import tempfile
import json
from dataclasses import dataclass, field
from typing import Protocol
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
