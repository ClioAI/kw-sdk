"""
RLHarness - Unified Task Execution Harness

This module provides a unified interface for running tasks in different modes
(standard, plan, explore) with declarative mode configuration.
"""

import os
from dataclasses import dataclass, field
from typing import Callable

from .config import ProviderConfig, Prompt, Attachment, CompactionConfig, ModeConfig, Snapshot, SkillMatch
from .providers.base import BaseProvider, HistoryEntry, PlanResult, _prompt_to_log
from .executor import CodeExecutor
from .modes import get_mode, MODES
from .skills import build_skill_index, parse_skills, extract_rubric


def load_provider(config: ProviderConfig) -> BaseProvider:
    if config.name == "gemini":
        from .providers import gemini
        gemini.GEMINI_API_KEY = config.api_key or os.environ.get("GEMINI_API_KEY")
        return gemini.GeminiProvider(thinking_level=config.thinking_level)
    elif config.name == "openai":
        from .providers import openai as oai
        oai.OPENAI_API_KEY = config.api_key or os.environ.get("OPENAI_API_KEY")
        return oai.OpenAIProvider(reasoning_effort=config.reasoning_effort)
    elif config.name == "anthropic":
        from .providers import anthropic as anth
        anth.ANTHROPIC_API_KEY = config.api_key or os.environ.get("ANTHROPIC_API_KEY")
        return anth.AnthropicProvider()
    raise ValueError(f"Unknown provider: {config.name}. Available: gemini, openai, anthropic")


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
        skills_dir: str | None = None,
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
            skills_dir: Directory containing reusable skills (scanned at init)
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
        self.skills_dir = skills_dir
        self.max_iterations = max_iterations
        self.default_mode = default_mode
        self.stream = stream
        self.stream_subagents = stream_subagents
        self.history: list[HistoryEntry] = []
        self._skills: list[SkillMatch] = []  # Parsed skill metadata

        if rubric:
            self.provider.rubric = rubric
        if on_event:
            self.provider.on_log = on_event
        if compaction_config:
            self.provider.compaction_config = compaction_config
        if code_executor:
            self.provider.code_executor = code_executor
        elif enable_code:
            raise ValueError(
                "enable_code=True requires a code_executor. "
                "Use SubprocessExecutor(artifacts_dir) for unsandboxed local execution."
            )

        # Skills setup
        if skills_dir:
            self.provider._skills_dir = skills_dir
            self.provider._skill_index = build_skill_index(skills_dir)
            self._skills = parse_skills(skills_dir)
        self.provider._skill_output_dir = os.path.join(artifacts_dir, "learned_skills")

    def _sync_history(self):
        self.history = self.provider.history.copy()

    # =========================================================================
    # PUBLIC: UNIFIED ENTRY POINT
    # =========================================================================
    
    @property
    def snapshots(self) -> dict[str, Snapshot]:
        """Checkpoints from the last checkpointed run."""
        return self.provider.snapshots

    def run_single(
        self,
        task: Prompt,
        ground_truth: str = "",
        mode: str | None = None,
        checkpoint: bool = False,
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
        self.provider._checkpoint = checkpoint
        self.provider._run_id = ""
        self.provider.snapshots = {}

        # Check for workflow skill match (only when no plan/mode override)
        if not plan and mode_name == "standard" and self._skills:
            matched = self._match_workflow_skill(task_text)
            if matched:
                playbook = matched.approach
                skill_rubric = extract_rubric(playbook)
                return self.run_single(
                    task, ground_truth,
                    mode="plan",
                    plan=playbook,
                    rubric=rubric or skill_rubric,
                    checkpoint=checkpoint,
                )

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
    # RESUME: CHECKPOINT-BASED RESUME
    # =========================================================================

    def resume(
        self,
        checkpoint_id: str | None = None,
        snapshot: Snapshot | None = None,
        feedback: str | None = None,
        rubric_update: str | None = None,
        ground_truth: str = "",
    ) -> RunResult:
        """Resume execution from a checkpoint.

        Pass either checkpoint_id (looked up from last run's snapshots) or
        a Snapshot object directly. Optionally inject feedback and/or rubric update.

        Args:
            checkpoint_id: ID from self.snapshots
            snapshot: Snapshot object directly
            feedback: Optional feedback injected as user message before resuming
            rubric_update: Optional rubric changes to merge (e.g. "add criteria for demigod analysis")
            ground_truth: For eval tracking

        Returns:
            RunResult from the resumed trajectory
        """
        if snapshot is None:
            if checkpoint_id is None:
                raise ValueError("Provide checkpoint_id or snapshot")
            snapshot = self.snapshots.get(checkpoint_id)
            if snapshot is None:
                raise KeyError(f"Checkpoint '{checkpoint_id}' not found. Available: {list(self.snapshots.keys())}")

        self.provider._checkpoint = True  # keep checkpointing on resumed runs

        # Merge rubric update if provided and rubric exists at this checkpoint
        if rubric_update and snapshot.state.get("rubric"):
            from .prompts import RUBRIC_MERGER
            self.provider.log("system", "[Resume] Merging rubric update...")
            merged = self.provider.generate(
                RUBRIC_MERGER.format(rubric=snapshot.state["rubric"], update=rubric_update),
                _log=False,
            )
            snapshot.state["rubric"] = merged
            self.provider.log("system", f"[Resume] Rubric merged with: {rubric_update[:100]}...")

        try:
            answer = self.provider.resume_from_snapshot(
                snapshot=snapshot,
                feedback=feedback,
                max_iterations=self.max_iterations,
            )
        except Exception as e:
            self._sync_history()
            self.provider.log("system", f"Error: {e}")
            raise

        self._sync_history()

        return RunResult(
            task=snapshot.state.get("mode", "resumed"),
            ground_truth=ground_truth,
            answer=answer,
            rubric=self.provider.rubric or "",
            history=self.history,
            mode=snapshot.state.get("mode", "standard"),
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
        checkpoint: bool = False,
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
        self.provider._checkpoint = checkpoint
        self.provider.snapshots = {}
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

    # =========================================================================
    # SKILLS
    # =========================================================================

    def _match_workflow_skill(self, task: str) -> SkillMatch | None:
        """Match task to a workflow skill via single LLM call."""
        workflow_skills = [s for s in self._skills if s.type == "workflow"]
        if not workflow_skills:
            return None
        descriptions = "\n".join(
            f"- {s.name}: {s.description}" for s in workflow_skills
        )
        prompt = (
            f"Given this task:\n{task}\n\n"
            f"Which workflow skill (if any) is a good match?\n{descriptions}\n\n"
            f"Reply with ONLY the skill name, or 'none' if no match."
        )
        result = self.provider.generate(prompt, _log=False)
        match_name = result.strip().lower().replace("'", "").replace('"', '')
        if match_name == "none":
            return None
        for s in workflow_skills:
            if s.name.lower() == match_name:
                return s
        return None
