"""
RLHarness - Unified Task Execution Harness

This module provides a unified interface for running tasks in different modes
(standard, plan, explore) with declarative mode configuration.
"""

import os
from dataclasses import dataclass, field
from typing import Callable

from .config import ProviderConfig, Prompt, Attachment, CompactionConfig, ModeConfig
from .providers.base import BaseProvider, HistoryEntry, PlanResult, _prompt_to_log
from .executor import CodeExecutor
from .modes import get_mode, MODES


def load_provider(config: ProviderConfig) -> BaseProvider:
    if config.name == "gemini":
        if config.api_key:
            os.environ["GEMINI_API_KEY"] = config.api_key
        from .providers.gemini import GeminiProvider
        return GeminiProvider()
    elif config.name == "openai":
        if config.api_key:
            os.environ["OPENAI_API_KEY"] = config.api_key
        from .providers.openai import OpenAIProvider
        return OpenAIProvider()
    raise ValueError(f"Unknown provider: {config.name}. Available: gemini, openai")


@dataclass
class RunResult:
    task: str
    ground_truth: str
    answer: str
    rubric: str
    history: list[HistoryEntry] = field(default_factory=list)
    # Mode that was used
    mode: str = "standard"
    # Pre-execution artifacts (for plan mode)
    plan: str = ""
    brief: str = ""


@dataclass
class IterateResult:
    """Result from iterate() - stateless refinement operation."""
    answer: str
    rubric: str
    history: list[HistoryEntry] = field(default_factory=list)


class RLHarness:
    """Unified task execution harness with declarative mode configuration.
    
    Modes are defined at the same layer via ModeConfig, not as separate code paths.
    This makes behavior predictable and modes easy to extend.
    """
    
    def __init__(
        self,
        provider: str | ProviderConfig = "gemini",
        enable_search: bool = False,
        enable_bash: bool = False,
        enable_code: bool = False,
        enable_ask_user: bool = False,
        code_executor: CodeExecutor | None = None,
        artifacts_dir: str = "./artifacts",
        max_iterations: int = 30,
        default_mode: str = "standard",  # Renamed from plan_mode for clarity
        rubric: str | None = None,
        on_event: Callable[[HistoryEntry], None] | None = None,
        compaction_config: CompactionConfig | None = None,
        stream: bool = False,
        stream_subagents: bool = False,
    ):
        """Initialize harness.

        Args:
            provider: Provider name or config
            enable_search: Enable web search tool
            enable_bash: Enable bash/file tools
            enable_code: Enable code execution
            enable_ask_user: Enable ask_user tool
            code_executor: Code executor instance (required if enable_code=True)
            artifacts_dir: Directory for artifacts
            max_iterations: Max orchestrator iterations
            default_mode: Default mode ("standard", "plan", "explore")
            rubric: Pre-set rubric (optional)
            on_event: Event callback for streaming
            compaction_config: Context compaction config
            stream: Enable streaming for orchestrator
            stream_subagents: Enable streaming for subagents
        """
        config = provider if isinstance(provider, ProviderConfig) else ProviderConfig(name=provider)
        self.provider = load_provider(config)
        self.enable_search = enable_search
        self.enable_bash = enable_bash
        self.enable_code = enable_code
        self.enable_ask_user = enable_ask_user
        self.artifacts_dir = artifacts_dir
        self.max_iterations = max_iterations
        self.default_mode = default_mode
        self.stream = stream
        self.stream_subagents = stream_subagents
        self.history: list[HistoryEntry] = []
        
        if rubric:
            self.provider.rubric = rubric
        if on_event:
            self.provider.on_log = on_event
        if compaction_config:
            self.provider.compaction_config = compaction_config
        if enable_code:
            if not code_executor:
                raise ValueError(
                    "enable_code=True requires a code_executor. "
                    "Use SubprocessExecutor(artifacts_dir) for unsandboxed local execution."
                )
            self.provider.code_executor = code_executor

    def _sync_history(self):
        self.history = self.provider.history.copy()

    # =========================================================================
    # PUBLIC: UNIFIED ENTRY POINT
    # =========================================================================
    
    def run_single(
        self,
        task: Prompt,
        ground_truth: str = "",
        mode: str | None = None,
        # Mode-specific kwargs
        num_takes: int = 0,  # explore mode
        plan: str | None = None,  # plan mode (skip pre-execution if provided)
        rubric: str | None = None,  # plan mode (skip pre-execution if provided)
    ) -> RunResult:
        """Run orchestrator on a single task.

        This is the unified entry point for all modes. Mode behavior is
        determined by ModeConfig, not by branching code paths.

        Args:
            task: The task prompt
            ground_truth: Expected answer (for eval)
            mode: "standard" | "plan" | "explore" (defaults to self.default_mode)
            num_takes: Hint for explore mode (0 = orchestrator decides)
            plan: Execution plan (required for plan mode)
            rubric: Verification rubric (optional, used if provided)

        Returns:
            RunResult with answer, rubric, history, and mode artifacts
        """
        mode_name = mode or self.default_mode
        mode_config = get_mode(mode_name)
        task_text = _prompt_to_log(task)
        
        self.provider.clear_history()
        
        # Collect mode-specific kwargs for orchestrator
        mode_kwargs = {}
        
        # Handle plan mode: plan is required, passed directly
        if mode_config.name == "plan":
            if not plan:
                raise ValueError("Plan mode requires a plan. Use run_single(mode='plan', plan=your_plan)")
            mode_kwargs["plan"] = plan
            if rubric:
                self.provider.rubric = rubric
        
        # Handle explore mode kwargs
        if mode_config.name == "explore":
            mode_kwargs["num_takes"] = num_takes
        
        # Handle rubric for standard mode
        if rubric and mode_config.name == "standard":
            self.provider.rubric = rubric

        # Run the orchestrator with unified mode config
        try:
            answer = self.provider.run_with_mode(
                task=task,
                mode=mode_config,
                enable_search=self.enable_search,
                enable_bash=self.enable_bash,
                enable_code=self.enable_code,
                enable_ask_user=self.enable_ask_user,
                max_iterations=self.max_iterations,
                stream=self.stream,
                stream_subagents=self.stream_subagents,
                **mode_kwargs,
            )
        except Exception as e:
            self._sync_history()
            self.provider.log("system", f"Error: {e}")
            raise

        self._sync_history()

        return RunResult(
            task=task_text,
            ground_truth=ground_truth,
            answer=answer,
            rubric=self.provider.rubric or "",
            history=self.history,
            mode=mode_name,
            plan=plan or "",
            brief=self.provider.brief or "",
        )

    # =========================================================================
    # ITERATE: STATELESS REFINEMENT
    # =========================================================================

    def iterate(
        self,
        task: str,
        answer: str,
        rubric: str,
        feedback: str | None = None,
        rubric_update: str | None = None,
    ) -> IterateResult:
        """Stateless refinement operation.

        Client provides everything. SDK refines answer based on feedback
        and/or rubric update, then verifies until PASS.

        Uses full orchestrator loop with all tools (search, bash, code).

        Args:
            task: Original task (for context)
            answer: Current answer to iterate on
            rubric: Current rubric
            feedback: Answer-level feedback (optional)
            rubric_update: Rubric changes to merge (optional)

        Returns:
            IterateResult with new answer, new rubric, history
        """
        from .prompts import RUBRIC_MERGER

        self.provider.clear_history()
        self.provider.log("system", f"[Iterate] task={task[:100]}...")

        # 1. Merge rubric if update provided
        if rubric_update:
            self.provider.log("system", "[Iterate] Merging rubric update...")
            rubric = self.provider.generate(
                RUBRIC_MERGER.format(rubric=rubric, update=rubric_update),
                _log=False
            )
            self.provider.log("tool_response", f"Merged rubric:\n{rubric}")

        # 2. Set rubric on provider (iterate mode uses "provided" strategy)
        self.provider.rubric = rubric

        # 3. Run orchestrator with iterate mode
        mode_config = get_mode("iterate")
        feedback_text = feedback or "Improve the answer based on the rubric."

        new_answer = self.provider.run_with_mode(
            task=f"Refine this answer based on feedback.",  # Simple task prompt
            mode=mode_config,
            enable_search=self.enable_search,
            enable_bash=self.enable_bash,
            enable_code=self.enable_code,
            enable_ask_user=self.enable_ask_user,
            max_iterations=self.max_iterations,
            stream=self.stream,
            stream_subagents=self.stream_subagents,
            # Mode kwargs - formatted into ITERATE_ORCHESTRATOR prompt
            original_task=task,
            current_answer=answer,
            user_feedback=feedback_text,
        )

        self._sync_history()

        return IterateResult(
            answer=new_answer,
            rubric=rubric,
            history=self.history,
        )

    # =========================================================================
    # EVAL & UTILITIES
    # =========================================================================

    def run_eval(
        self,
        eval_set: list[dict],
        task_key: str = "question",
        gt_key: str = "answer",
        mode: str | None = None,
    ) -> list[RunResult]:
        """Run harness on eval set."""
        results = []
        for i, item in enumerate(eval_set):
            task = item.get(task_key, "")
            ground_truth = item.get(gt_key, "")
            self.provider.log("system", f"Eval {i + 1}/{len(eval_set)}")

            try:
                result = self.run_single(task, ground_truth, mode=mode)
                results.append(result)
            except Exception as e:
                self._sync_history()
                results.append(RunResult(
                    task=task,
                    ground_truth=ground_truth,
                    answer=f"ERROR: {e}",
                    rubric="",
                    history=self.history,
                ))

        return results

    def reward(self, answer: str, ground_truth: str) -> float:
        """Stub - override per eval set."""
        raise NotImplementedError("Override for your eval set")

    def get_history_text(self) -> str:
        return self.provider.get_history_text()

    def get_history_markdown(self) -> str:
        return self.provider.get_history_markdown()

    @staticmethod
    def list_modes() -> list[str]:
        """List available modes."""
        return list(MODES.keys())

    @staticmethod
    def get_mode_config(name: str) -> ModeConfig:
        """Get mode configuration by name."""
        return get_mode(name)
