import asyncio
import time

import pytest

import verif.harness as harness_module


class DummyProvider:
    def __init__(self, delay: float = 0.0):
        self.history = []
        self.rubric = None
        self.brief = None
        self.snapshots = {}
        self._checkpoint = False
        self._run_id = ""
        self._skills_dir = ""
        self._skill_index = ""
        self._skill_output_dir = ""
        self.delay = delay

    def clear_history(self):
        self.history = []
        self.rubric = None
        self.brief = None
        self.snapshots = {}

    def log(self, entry_type: str, content: str):
        self.history.append({"entry_type": entry_type, "content": content})

    async def run_with_mode_async(self, task, mode, **kwargs):
        await asyncio.sleep(self.delay)
        self.rubric = "dummy-rubric"
        self.brief = "dummy-brief"
        return f"done:{task}"

    async def generate_async(self, prompt: str, _log: bool = True):
        return "none"

    async def resume_from_snapshot_async(self, snapshot, feedback=None, max_iterations=30):
        await asyncio.sleep(self.delay)
        return "resumed"


@pytest.mark.asyncio
async def test_async_harness_run_single(monkeypatch):
    monkeypatch.setattr(harness_module, "load_provider", lambda config: DummyProvider())
    harness = harness_module.AsyncRLHarness(provider="gemini")

    result = await harness.run_single("hello")

    assert result.answer == "done:hello"
    assert result.rubric == "dummy-rubric"
    assert result.brief == "dummy-brief"


@pytest.mark.asyncio
async def test_async_harness_concurrent_runs(monkeypatch):
    monkeypatch.setattr(harness_module, "load_provider", lambda config: DummyProvider(delay=0.15))

    h1 = harness_module.AsyncRLHarness(provider="gemini")
    h2 = harness_module.AsyncRLHarness(provider="gemini")

    start = time.perf_counter()
    await asyncio.gather(
        h1.run_single("task-1"),
        h2.run_single("task-2"),
    )
    elapsed = time.perf_counter() - start

    assert elapsed < 0.27
