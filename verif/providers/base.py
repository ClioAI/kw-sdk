import copy
import asyncio
import time
import logging
import subprocess
import re
import threading
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from concurrent.futures import ThreadPoolExecutor

from ..prompts import (
    BRIEF_CREATOR, RUBRIC_CREATOR, VERIFICATION, FILE_SEARCH_AGENT, COMPACTION_SUMMARIZER,
    EXPLORE_ORCHESTRATOR, EXPLORE_BRIEF, EXPLORE_VERIFIER, ORCHESTRATOR, ORCHESTRATOR_WITH_PLAN,
    ITERATE_ORCHESTRATOR, ASK_USER_ADDENDUM, SKILL_BUILDER,
)
from ..config import Prompt, Attachment, CompactionConfig, ModeConfig, Snapshot, BackgroundTask
from ..modes import get_mode, get_tools_for_mode

if TYPE_CHECKING:
    from ..executor import CodeExecutor


# Prompt registry - maps string names to actual prompt objects
PROMPTS = {
    "ORCHESTRATOR": ORCHESTRATOR,
    "ORCHESTRATOR_WITH_PLAN": ORCHESTRATOR_WITH_PLAN,
    "EXPLORE_ORCHESTRATOR": EXPLORE_ORCHESTRATOR,
    "ITERATE_ORCHESTRATOR": ITERATE_ORCHESTRATOR,
    "BRIEF_CREATOR": BRIEF_CREATOR,
    "EXPLORE_BRIEF": EXPLORE_BRIEF,
    "RUBRIC_CREATOR": RUBRIC_CREATOR,
    "VERIFICATION": VERIFICATION,
    "EXPLORE_VERIFIER": EXPLORE_VERIFIER,
    "SKILL_BUILDER": SKILL_BUILDER,
}


def _prompt_to_log(task: Prompt) -> str:
    """Extract text representation from Prompt for logging."""
    if isinstance(task, str):
        return task
    parts = []
    for item in task:
        if isinstance(item, str):
            parts.append(item)
        elif isinstance(item, Attachment):
            parts.append(f"[{item.mime_type}: {item.name or 'attachment'}]")
    return " ".join(parts)

# Allowed safe commands for filesystem navigation/search
ALLOWED_BASH_COMMANDS = {
    # Directory navigation
    "ls", "find", "pwd", "tree", "du", "df", "realpath", "dirname", "basename",
    # File reading
    "cat", "head", "tail", "less", "more", "file", "stat",
    # Text search/processing
    "grep", "wc", "sort", "uniq", "cut", "awk", "sed", "xargs",
    # Binary inspection
    "strings", "od", "hexdump", "sha256sum", "md5sum",
    # Utilities
    "which", "whereis",
}

# Patterns to block for security (pipe is allowed for safe command chaining)
DANGEROUS_PATTERNS = [
    r"[;&`]",  # Shell operators (semicolon, ampersand, backticks)
    r">",  # Output redirection
    r"<",  # Input redirection
    r"\$\(",  # Command substitution $()
    r"\$\{",  # Variable expansion ${}
    r"\$\w",  # Variable reference $VAR
    r"\|\s*(rm|mv|cp|chmod|chown|dd|mkfs|sudo|su|bash|sh|zsh)",  # Dangerous piped commands
]

# Max context tokens per provider
MAX_CONTEXT_TOKENS = {
    "openai": 1_000_000,
    "gemini": 1_000_000,
    "anthropic": 200_000,
}


# Base debug logger
debug_logger = logging.getLogger("harness_debug")
debug_logger.setLevel(logging.DEBUG)


def retry_on_error(func, max_retries=3, backoff=2, logger=None):
    """Retry with exponential backoff on API errors."""
    log = logger or debug_logger
    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            wait = backoff ** attempt
            log.warning(f"RETRY attempt {attempt + 1} failed: {e}")
            log.info(f"Waiting {wait}s before retry...")
            time.sleep(wait)


async def async_retry_on_error(func, max_retries=3, backoff=2, logger=None):
    """Async retry with exponential backoff on API errors."""
    log = logger or debug_logger
    for attempt in range(max_retries):
        try:
            return await func()
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            wait = backoff ** attempt
            log.warning(f"RETRY attempt {attempt + 1} failed: {e}")
            log.info(f"Waiting {wait}s before retry...")
            await asyncio.sleep(wait)


# Base tool definitions (provider converts to its format)
TOOL_DEFINITIONS = {
    "create_brief": {
        "name": "create_brief",
        "description": "Create a structured brief from the task. Call this first to understand and formalize the task requirements.",
        "parameters": {
            "type": "object",
            "properties": {
                "task": {"type": "string", "description": "The original task to create a brief for."},
            },
            "required": ["task"],
        },
    },
    "create_rubric": {
        "name": "create_rubric",
        "description": "Create an evaluation rubric based on the brief. Call after create_brief. You won't see the rubric directly - it will be used by verify_answer.",
        "parameters": {
            "type": "object",
            "properties": {
                "brief": {"type": "string", "description": "The brief to create a rubric from."},
            },
            "required": ["brief"],
        },
    },
    "delegate": {
        "name": "delegate",
        "description": "Delegate a subtask. Without tools: single LLM call for quick synthesis. "
                       "With tools: single round — model calls tools, then synthesizes. No loop. "
                       "Set background=true for async.",
        "parameters": {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "Complete instructions for the delegate. Be specific about "
                                   "expected output.",
                },
                "tools": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ["execute_code", "bash"],
                    },
                    "description": "Tools for the delegate. Omit for single LLM call. "
                                   "search_web/search_files are NOT valid — call them directly.",
                },
                "background": {
                    "type": "boolean",
                    "default": False,
                    "description": "Run in background. Results delivered asynchronously.",
                },
                "skill": {
                    "type": "string",
                    "description": "Skill name. SDK reads skill.md + script.py and injects into delegate context.",
                },
            },
            "required": ["prompt"],
        },
    },
    "build_skill": {
        "name": "build_skill",
        "description": "Capture a reusable skill from what was learned. Always runs in background. "
                       "Produces skill.md + script.py with tested code.",
        "parameters": {
            "type": "object",
            "properties": {
                "context": {
                    "type": "string",
                    "description": "What was learned: approach, key insights, working code snippets. "
                                   "Include everything the skill builder needs to generalize.",
                },
                "name": {
                    "type": "string",
                    "description": "Skill name (becomes folder name). Lowercase with underscores.",
                },
            },
            "required": ["context", "name"],
        },
    },
    "notify": {
        "name": "notify",
        "description": "Send a progress update or alert to the user.",
        "parameters": {
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "The update message."},
                "level": {
                    "type": "string",
                    "enum": ["info", "alert"],
                    "default": "info",
                    "description": "'info' for progress, 'alert' for important findings.",
                },
            },
            "required": ["message"],
        },
    },
    "search_web": {
        "name": "search_web",
        "description": "Delegate web search to a search subagent. Returns synthesized summary with source URLs.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search query. Be specific about what information you need."},
            },
            "required": ["query"],
        },
    },
    "verify_answer": {
        "name": "verify_answer",
        "description": "Verify your answer against the rubric. Returns PASS or FAIL with feedback.",
        "parameters": {
            "type": "object",
            "properties": {
                "answer": {"type": "string", "description": "Your current answer to verify."},
            },
            "required": ["answer"],
        },
    },
    "submit_answer": {
        "name": "submit_answer",
        "description": "Submit your final answer. Only call after verify_answer returns PASS.",
        "parameters": {
            "type": "object",
            "properties": {
                "answer": {"type": "string", "description": "Your final answer."},
            },
            "required": ["answer"],
        },
    },
    "bash": {
        "name": "bash",
        "description": "Execute safe bash commands for filesystem navigation and search. Allowed commands: ls, find, grep, cat, head, tail, wc, pwd, tree, file, stat, du, df, sort, uniq, cut, awk, sed. Use this to explore directories, search for files, and read file contents.",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string", 
                    "description": "The bash command to execute. Must start with an allowed command. Examples: 'ls -la /path', 'find . -name *.py', 'grep -r pattern directory', 'cat file.txt | head -20'"
                },
                "working_directory": {
                    "type": "string",
                    "description": "Optional working directory for command execution. Defaults to current directory."
                },
            },
            "required": ["command"],
        },
    },
    "read_file": {
        "name": "read_file",
        "description": "Read and summarize any file using vision/document understanding. Works with images (png, jpg, gif, webp), PDFs, videos, and other documents. Returns a detailed summary of the file contents. Use this for understanding visual content, extracting text from images/PDFs, or analyzing media files.",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Absolute path to the file to read and summarize."
                },
                "prompt": {
                    "type": "string",
                    "description": "Optional specific question or focus for the summary. E.g., 'Extract all text', 'Describe the diagram', 'What are the key findings?'"
                },
            },
            "required": ["file_path"],
        },
    },
    "execute_code": {
        "name": "execute_code",
        "description": "Execute Python code in a stateful REPL. Variables persist across calls. Use for calculations, data processing, and creating files. Print outputs to see results. Save artifacts (xlsx, csv, images, docs) to current directory - they will be tracked and returned.",
        "parameters": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Python code to execute. Common libraries available (pandas, numpy, openpyxl, matplotlib, Pillow). Use print() to output results. Save files to current directory."
                },
            },
            "required": ["code"],
        },
    },
    "search_files": {
        "name": "search_files",
        "description": "Read or search local files and return a summary. Handles both: (1) specific file reads - 'summarize /path/to/doc.pdf', 'what does config.json contain', (2) exploratory search - 'find all API endpoints', 'search for auth logic in src/'. A subagent reads/searches files and returns a clean summary.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "What to read or search for. Can be a specific file path to read, or a search query to find information across files."
                },
                "path": {
                    "type": "string",
                    "description": "Directory context. For specific files, can be omitted. For searches, the directory to search in. Defaults to current directory."
                },
            },
            "required": ["query"],
        },
    },
    "verify_exploration": {
        "name": "verify_exploration",
        "description": "Verify exploration output against quality checklist. Checks structure and completeness, not correctness. Always passes through - tags issues but does not reject.",
        "parameters": {
            "type": "object",
            "properties": {
                "takes": {
                    "type": "string",
                    "description": "The exploration output with all takes in === separated markdown format."
                },
            },
            "required": ["takes"],
        },
    },
    "ask_user": {
        "name": "ask_user",
        "description": "Ask user for clarification or intermediate feedback. Use when you need user input to proceed. Can run in parallel with other tools. IMPORTANT: Cannot proceed to verification while questions are pending.",
        "parameters": {
            "type": "object",
            "properties": {
                "questions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "question": {"type": "string", "description": "The question to ask."},
                            "options": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Optional list of choices for the user to pick from."
                            },
                        },
                        "required": ["question"],
                    },
                    "description": "List of questions to ask the user."
                },
                "context": {
                    "type": "string",
                    "description": "Context about why you're asking and what you've done so far."
                },
            },
            "required": ["questions"],
        },
    },
}


@dataclass
class HistoryEntry:
    timestamp: str
    entry_type: str  # "user" | "model" | "thinking" | "tool_call" | "tool_response" | "tool_error" | "system"
    content: str
    metadata: dict = field(default_factory=dict)


@dataclass
class PlanResult:
    task: str
    brief: str
    plan: str
    rubric: str
    plan_file: str = ""


@dataclass
class FunctionCall:
    """Normalized function call across providers."""
    name: str
    args: dict
    raw: object = None  # Provider-specific raw object


class BaseProvider(ABC):
    provider_name: str = "base"  # Override in subclass

    def __init__(self):
        self.history: list[HistoryEntry] = []
        self.rubric: str | None = None
        self.brief: str | None = None
        self.submitted_answer: str | None = None
        self.on_log: callable = None
        self.code_executor: "CodeExecutor | None" = None  # Set by harness if enable_code=True
        self.enable_search: bool = False  # Set by harness, used by delegate
        self.compaction_config = CompactionConfig()  # Default config
        self._brief_created = False  # Track if brief has been created
        self._brief_counter: int = 0
        # Streaming flags
        self.stream: bool = False
        self.stream_subagents: bool = False
        self._subagent_counter: int = 0
        # Mode tracking
        self.mode: str = "standard"  # "standard" | "plan" | "explore"
        # User question tracking
        self._user_responses: dict[str, dict] = {}  # question_id -> response dict
        self._user_response_events: dict[str, threading.Event] = {}
        self._pending_user_questions: set[str] = set()
        self._user_clarifications: list[dict] = []  # [{question_id, questions, response, timestamp}]
        # Checkpointing
        self.snapshots: dict[str, Snapshot] = {}
        self._checkpoint: bool = False
        self._run_id: str = ""
        # Delegation & background
        self._background_tasks: dict[str, BackgroundTask] = {}
        self._bg_executor = ThreadPoolExecutor(max_workers=3)
        self._compaction_executor = ThreadPoolExecutor(max_workers=1)
        # Skills
        self._skill_index: str = ""  # Injected by harness
        self._skills_dir: str = ""  # Set by harness
        self._skill_output_dir: str = ""  # artifacts_dir + /learned_skills

    def _next_subagent_id(self) -> str:
        """Generate unique ID for subagent tracking."""
        self._subagent_counter += 1
        return f"sa_{self._subagent_counter:03d}"

    def log(self, entry_type: str, content: str, metadata: dict = None):
        entry = HistoryEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            entry_type=entry_type,
            content=content,
            metadata=metadata or {},
        )
        self.history.append(entry)
        if self.on_log:
            self.on_log(entry)

    def emit(self, entry_type: str, content: str, metadata: dict = None):
        """Emit streaming event to callback without storing in history."""
        if self.on_log:
            entry = HistoryEntry(
                timestamp=datetime.now(timezone.utc).isoformat(),
                entry_type=entry_type,
                content=content,
                metadata=metadata or {},
            )
            self.on_log(entry)

    def clear_history(self):
        self.history = []
        self.rubric = None
        self.brief = None
        self.submitted_answer = None
        self._brief_created = False
        self._brief_counter = 0
        self._user_responses = {}
        self._user_response_events = {}
        self._pending_user_questions = set()
        self._user_clarifications = []
        self._background_tasks = {}

    def get_history_text(self) -> str:
        lines = []
        for e in self.history:
            prefix = {
                "user": ">>> USER", "model": "<<< MODEL", "thinking": "... THINKING",
                "tool_call": "--> TOOL", "tool_response": "<-- RESULT",
                "tool_error": "!!! ERROR", "system": "=== SYSTEM",
            }.get(e.entry_type, e.entry_type.upper())
            lines.append(f"[{e.timestamp}] {prefix}\n{e.content}\n")
        return "\n".join(lines)

    def get_history_markdown(self) -> str:
        lines = ["# Execution Trace\n"]
        for i, e in enumerate(self.history):
            icon = {
                "user": "📝", "model": "🤖", "thinking": "💭", "tool_call": "🔧",
                "tool_response": "📥", "tool_error": "❌", "system": "⚙️",
            }.get(e.entry_type, "•")
            lines.append(f"### {i+1}. {icon} {e.entry_type.upper()}\n```\n{e.content}\n```\n")
        return "\n".join(lines)

    def _is_remote_executor(self) -> bool:
        return self.code_executor is not None and hasattr(self.code_executor, "execute_tool")

    def get_tool_definition(self, name: str) -> dict:
        """Get tool definition, with sandbox-aware overrides for execute_code."""
        defn = TOOL_DEFINITIONS[name]
        if name == "execute_code" and self._is_remote_executor():
            cfg = getattr(self.code_executor, "sandbox_config", {}) or {}
            lang = cfg.get("type", "Python")
            caps = cfg.get("capabilities", [])
            # Build concise helper list from capabilities beyond execute_code
            helpers = [c for c in caps if c != "execute_code"]
            desc = f"Execute {lang} code in a remote sandbox."
            # Extract helper functions from constraints for the code param description
            code_desc = f"{lang} code to execute."
            constraints = cfg.get("constraints", "")
            if constraints:
                code_desc += f" {constraints}"
            defn = {**defn, "description": desc, "parameters": {
                "type": "object",
                "properties": {"code": {"type": "string", "description": code_desc}},
                "required": ["code"],
            }}
        return defn

    async def generate_async(
        self,
        prompt: str,
        system: str = None,
        _log: bool = True,
        enable_search: bool = False,
        stream: bool = False,
        subagent_id: str = None,
        stream_event_type: str = None,
        stream_meta: dict = None,
        tools: list[str] = None,
        _tool_depth: int = 0,
    ) -> str:
        """Async generation fallback for providers without native async support."""
        return await asyncio.to_thread(
            self.generate,
            prompt,
            system,
            _log,
            enable_search,
            stream,
            subagent_id,
            stream_event_type,
            stream_meta,
            tools,
            _tool_depth,
        )

    async def search_async(self, query: str, stream: bool = False, subagent_id: str = None) -> str:
        """Async search fallback for providers without native async support."""
        return await asyncio.to_thread(self.search, query, stream, subagent_id)

    async def _call_model_async(self, context: object, step_desc: str, stream: bool = False) -> tuple[list[FunctionCall], str]:
        """Async model-call fallback for providers without native async support."""
        return await asyncio.to_thread(self._call_model, context, step_desc, stream)

    # === Common tool execution ===
    def _execute_tool(self, name: str, args: dict) -> str:
        if name == "create_brief":
            # Get brief prompt from mode config via registry
            mode_config = get_mode(self.mode)
            brief_prompt = PROMPTS[mode_config.brief_prompt]
            self._brief_counter += 1
            instruction = args.get("task", "")
            self.emit("brief_start", instruction, {
                "brief_index": self._brief_counter,
            })
            result = self.generate(
                instruction, system=brief_prompt, _log=False,
                stream=self.stream, stream_event_type="brief_chunk",
                stream_meta={"brief_index": self._brief_counter},
            )
            self._brief_created = True
            self.brief = result
            return result

        elif name == "create_rubric":
            if self.rubric:
                return "Rubric already set (using pre-existing)."
            brief = args.get("brief", "")
            try:
                self.rubric = self.generate(brief, system=RUBRIC_CREATOR, _log=False)
                self.emit("rubric_created", self.rubric)
                return "Rubric created."
            except Exception as e:
                self.rubric = f"ERROR: {e}"
                raise

        elif name == "delegate":
            prompt = args.get("prompt", "")
            tools = args.get("tools") or None
            background = args.get("background", False)
            subagent_id = self._next_subagent_id()

            # Inject skill if provided
            skill_name = args.get("skill")
            if skill_name:
                if self._skills_dir:
                    from pathlib import Path
                    skill_dir = Path(self._skills_dir) / skill_name
                    if skill_dir.exists():
                        from ..skills import inject_skill
                        prompt = inject_skill(prompt, skill_name, self._skills_dir)
                    else:
                        self.log("tool_response", f"Skill '{skill_name}' not found, proceeding without it.")
                else:
                    self.log("tool_response", f"No skills configured, ignoring skill='{skill_name}'.")

            if background:
                future = self._bg_executor.submit(
                    lambda p=prompt, t=tools: self.generate(
                        p, _log=False, enable_search=self.enable_search if not t else False,
                        subagent_id=subagent_id, tools=t,
                    ),
                )
                self._background_tasks[subagent_id] = BackgroundTask(
                    id=subagent_id, future=future, prompt=prompt, started_at=time.time(),
                )
                return f"Agent {subagent_id} running in background. Results delivered when ready."

            return self.generate(
                prompt, _log=False, enable_search=self.enable_search if not tools else False,
                stream=self.stream_subagents, subagent_id=subagent_id, tools=tools,
            )

        elif name == "build_skill":
            context_text = args.get("context", "")
            skill_name = args.get("name", "unnamed_skill")
            subagent_id = self._next_subagent_id()
            skill_prompt = (
                f"Skill name: {skill_name}\n\n"
                f"Learning context:\n{context_text}\n\n"
                f"Save to: {self._skill_output_dir}/{skill_name}/"
            )
            future = self._bg_executor.submit(
                lambda: self.generate(
                    skill_prompt, system=SKILL_BUILDER, _log=False, tools=["execute_code", "search_web"],
                ),
            )
            self._background_tasks[subagent_id] = BackgroundTask(
                id=subagent_id, future=future,
                prompt=f"build_skill:{skill_name}", started_at=time.time(),
            )
            return f"Skill '{skill_name}' capture started in background."

        elif name == "notify":
            message = args.get("message", "")
            level = args.get("level", "info")
            self.emit("agent_notify", message, {"level": level})
            return "Notified."

        elif name == "search_web":
            subagent_id = self._next_subagent_id()
            return self.search(args.get("query", ""), stream=self.stream_subagents, subagent_id=subagent_id)

        elif name == "verify_answer":
            # Block if user questions are pending
            if self._pending_user_questions:
                pending = ", ".join(self._pending_user_questions)
                return f"ERROR: Cannot verify - awaiting user response to pending questions: {pending}. Wait for ask_user responses first."
            answer = args.get("answer", "")
            if not self.rubric:
                return "ERROR: No rubric created. Call create_rubric first."
            verification_prompt = f"## Rubric\n{self.rubric}\n\n## Answer\n{answer}"
            # Include user clarifications if any
            if self._user_clarifications:
                clarifications_text = "\n".join(
                    f"- Q: {c['questions']} → A: {c['response']}"
                    for c in self._user_clarifications
                )
                verification_prompt += f"\n\n## User Clarifications\nThe user provided these clarifications during execution. Rubric may be stale around these points - verify intent based on clarifications, not just literal rubric criteria:\n{clarifications_text}"
            return self.generate(
                verification_prompt, system=VERIFICATION, _log=False,
                stream=self.stream, stream_event_type="verification_chunk",
            )

        elif name == "submit_answer":
            self.submitted_answer = args.get("answer", "")
            return "SUBMITTED"

        elif name == "bash":
            if self._is_remote_executor():
                return self.code_executor.execute_tool("bash", args)
            return self._execute_bash(
                args.get("command", ""),
                args.get("working_directory")
            )

        elif name == "read_file":
            if self._is_remote_executor():
                return self.code_executor.execute_tool("read_file", args)
            file_path = args.get("file_path", "")
            prompt = args.get("prompt", "Provide a detailed summary of this file's contents.")
            return self.read_file_with_vision(file_path, prompt)

        elif name == "execute_code":
            if not self.code_executor:
                return "Error: Code execution not enabled."
            code = args.get("code", "")
            result = self.code_executor.execute(code)
            output = result.stdout if result.stdout else ""
            if result.stderr:
                output += f"\n[stderr]: {result.stderr}"
            if result.error:
                output += f"\n[error]: {result.error}"
            if result.artifacts:
                output += f"\n[artifacts]: {', '.join(result.artifacts)}"
            return output if output.strip() else "[Code executed with no output]"

        elif name == "search_files":
            if self._is_remote_executor():
                return self.code_executor.execute_tool("search_files", args)
            query = args.get("query", "")
            path = args.get("path", ".")
            return self.search_files(query, path)

        elif name == "verify_exploration":
            # Block if user questions are pending
            if self._pending_user_questions:
                pending = ", ".join(self._pending_user_questions)
                return f"ERROR: Cannot verify - awaiting user response to pending questions: {pending}. Wait for ask_user responses first."
            takes = args.get("takes", "")
            # Use custom rubric if provided, else use default EXPLORE_VERIFIER
            verifier_prompt = self.rubric if self.rubric else EXPLORE_VERIFIER
            verification_prompt = f"## Exploration Output\n{takes}"
            return self.generate(verification_prompt, system=verifier_prompt, _log=False)

        elif name == "ask_user":
            questions = args.get("questions", [])
            context = args.get("context", "")
            return self._ask_user(questions, context)

        return f"Unknown tool: {name}"

    async def _execute_tool_async(self, name: str, args: dict) -> str:
        """Async tool execution path used by AsyncRLHarness."""
        if name == "create_brief":
            mode_config = get_mode(self.mode)
            brief_prompt = PROMPTS[mode_config.brief_prompt]
            self._brief_counter += 1
            instruction = args.get("task", "")
            self.emit("brief_start", instruction, {
                "brief_index": self._brief_counter,
            })
            result = await self.generate_async(
                instruction,
                system=brief_prompt,
                _log=False,
                stream=self.stream,
                stream_event_type="brief_chunk",
                stream_meta={"brief_index": self._brief_counter},
            )
            self._brief_created = True
            self.brief = result
            return result

        if name == "create_rubric":
            if self.rubric:
                return "Rubric already set (using pre-existing)."
            brief = args.get("brief", "")
            try:
                self.rubric = await self.generate_async(brief, system=RUBRIC_CREATOR, _log=False)
                self.emit("rubric_created", self.rubric)
                return "Rubric created."
            except Exception as e:
                self.rubric = f"ERROR: {e}"
                raise

        if name == "delegate":
            prompt = args.get("prompt", "")
            tools = args.get("tools") or None
            background = args.get("background", False)
            subagent_id = self._next_subagent_id()

            skill_name = args.get("skill")
            if skill_name:
                if self._skills_dir:
                    from pathlib import Path
                    skill_dir = Path(self._skills_dir) / skill_name
                    if skill_dir.exists():
                        from ..skills import inject_skill
                        prompt = inject_skill(prompt, skill_name, self._skills_dir)
                    else:
                        self.log("tool_response", f"Skill '{skill_name}' not found, proceeding without it.")
                else:
                    self.log("tool_response", f"No skills configured, ignoring skill='{skill_name}'.")

            if background:
                task = asyncio.create_task(
                    self.generate_async(
                        prompt,
                        _log=False,
                        enable_search=self.enable_search if not tools else False,
                        subagent_id=subagent_id,
                        tools=tools,
                    )
                )
                self._background_tasks[subagent_id] = BackgroundTask(
                    id=subagent_id,
                    future=task,
                    prompt=prompt,
                    started_at=time.time(),
                )
                return f"Agent {subagent_id} running in background. Results delivered when ready."

            return await self.generate_async(
                prompt,
                _log=False,
                enable_search=self.enable_search if not tools else False,
                stream=self.stream_subagents,
                subagent_id=subagent_id,
                tools=tools,
            )

        if name == "build_skill":
            context_text = args.get("context", "")
            skill_name = args.get("name", "unnamed_skill")
            subagent_id = self._next_subagent_id()
            skill_prompt = (
                f"Skill name: {skill_name}\n\n"
                f"Learning context:\n{context_text}\n\n"
                f"Save to: {self._skill_output_dir}/{skill_name}/"
            )
            task = asyncio.create_task(
                self.generate_async(
                    skill_prompt,
                    system=SKILL_BUILDER,
                    _log=False,
                    tools=["execute_code", "search_web"],
                )
            )
            self._background_tasks[subagent_id] = BackgroundTask(
                id=subagent_id,
                future=task,
                prompt=f"build_skill:{skill_name}",
                started_at=time.time(),
            )
            return f"Skill '{skill_name}' capture started in background."

        if name == "notify":
            message = args.get("message", "")
            level = args.get("level", "info")
            self.emit("agent_notify", message, {"level": level})
            return "Notified."

        if name == "search_web":
            subagent_id = self._next_subagent_id()
            return await self.search_async(
                args.get("query", ""),
                stream=self.stream_subagents,
                subagent_id=subagent_id,
            )

        if name == "verify_answer":
            if self._pending_user_questions:
                pending = ", ".join(self._pending_user_questions)
                return f"ERROR: Cannot verify - awaiting user response to pending questions: {pending}. Wait for ask_user responses first."
            answer = args.get("answer", "")
            if not self.rubric:
                return "ERROR: No rubric created. Call create_rubric first."
            verification_prompt = f"## Rubric\n{self.rubric}\n\n## Answer\n{answer}"
            if self._user_clarifications:
                clarifications_text = "\n".join(
                    f"- Q: {c['questions']} → A: {c['response']}"
                    for c in self._user_clarifications
                )
                verification_prompt += (
                    "\n\n## User Clarifications\n"
                    "The user provided these clarifications during execution. Rubric may be stale "
                    "around these points - verify intent based on clarifications, not just literal "
                    f"rubric criteria:\n{clarifications_text}"
                )
            return await self.generate_async(
                verification_prompt,
                system=VERIFICATION,
                _log=False,
                stream=self.stream,
                stream_event_type="verification_chunk",
            )

        if name == "submit_answer":
            self.submitted_answer = args.get("answer", "")
            return "SUBMITTED"

        if name == "verify_exploration":
            if self._pending_user_questions:
                pending = ", ".join(self._pending_user_questions)
                return f"ERROR: Cannot verify - awaiting user response to pending questions: {pending}. Wait for ask_user responses first."
            takes = args.get("takes", "")
            verifier_prompt = self.rubric if self.rubric else EXPLORE_VERIFIER
            verification_prompt = f"## Exploration Output\n{takes}"
            return await self.generate_async(verification_prompt, system=verifier_prompt, _log=False)

        if name == "search_files" and not self._is_remote_executor():
            query = args.get("query", "")
            path = args.get("path", ".")
            return await self.search_files_async(query, path)

        return await asyncio.to_thread(self._execute_tool, name, args)

    def _execute_bash(self, command: str, working_directory: str = None) -> str:
        """Execute a safe bash command for filesystem navigation/search."""
        if not command or not command.strip():
            return "Error: Empty command provided."

        command = command.strip()
        
        # Extract the base command (handle pipes)
        parts = command.split("|")
        base_cmd = parts[0].strip().split()[0] if parts[0].strip() else ""

        # Validate base command is allowed
        if base_cmd not in ALLOWED_BASH_COMMANDS:
            return f"Error: Command '{base_cmd}' is not allowed. Allowed commands: {', '.join(sorted(ALLOWED_BASH_COMMANDS))}"

        # Check for dangerous patterns
        for pattern in DANGEROUS_PATTERNS:
            if re.search(pattern, command):
                return f"Error: Command contains disallowed pattern for security reasons."

        # If command has pipes, validate each piped command
        for part in parts[1:]:
            piped_cmd = part.strip().split()[0] if part.strip() else ""
            if piped_cmd and piped_cmd not in ALLOWED_BASH_COMMANDS:
                # Allow some additional safe commands in pipes
                extra_safe = {"head", "tail", "sort", "uniq", "wc", "grep", "cut", "awk", "sed"}
                if piped_cmd not in extra_safe:
                    return f"Error: Piped command '{piped_cmd}' is not allowed."

        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30,  # 30 second timeout
                cwd=working_directory,
            )
            
            output = result.stdout
            if result.stderr:
                output += f"\n[stderr]: {result.stderr}"
            if result.returncode != 0:
                output += f"\n[exit code: {result.returncode}]"
            
            # Truncate very long outputs
            if len(output) > 50000:
                output = output[:50000] + f"\n... [truncated, {len(output) - 50000} chars omitted]"
            
            return output if output.strip() else "[Command completed with no output]"
            
        except subprocess.TimeoutExpired:
            return "Error: Command timed out after 30 seconds."
        except Exception as e:
            return f"Error executing command: {str(e)}"

    def _ask_user(self, questions: list[dict], context: str, timeout: float = 300) -> str:
        """Ask user for clarification. Emits event and blocks waiting for response."""
        question_id = f"q_{int(time.time() * 1000)}"

        # Format questions for display
        questions_text = "\n".join(
            f"{i+1}. {q['question']}" + (f" (options: {', '.join(q['options'])})" if q.get('options') else "")
            for i, q in enumerate(questions)
        )

        # Track as pending
        self._pending_user_questions.add(question_id)

        # Create wait event
        event = threading.Event()
        self._user_response_events[question_id] = event

        # Emit the question event
        self.emit("user_question", questions_text, {
            "question_id": question_id,
            "questions": questions,
            "context": context,
        })

        # Wait for response
        if event.wait(timeout=timeout):
            response = self._user_responses.pop(question_id, {})
            self._user_response_events.pop(question_id, None)
            self._pending_user_questions.discard(question_id)

            # Store clarification for verification context
            self._user_clarifications.append({
                "question_id": question_id,
                "questions": questions_text,
                "response": response,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

            # Format response for model
            if isinstance(response, dict):
                return "\n".join(f"Q{k}: {v}" for k, v in response.items())
            return str(response)
        else:
            self._user_response_events.pop(question_id, None)
            self._pending_user_questions.discard(question_id)
            return f"User response timeout after {timeout}s - no answer received."

    def receive_user_response(self, question_id: str, response: dict) -> bool:
        """Receive a response to a user question. Returns True if question was pending."""
        if question_id not in self._user_response_events:
            return False
        self._user_responses[question_id] = response
        self._user_response_events[question_id].set()
        return True

    def _execute_tools_parallel(self, func_calls: list[FunctionCall], step_desc: str) -> tuple[list[str], set[int]]:
        """Execute tools in parallel, return results and error indices."""
        results = [None] * len(func_calls)
        errors = set()

        with ThreadPoolExecutor(max_workers=max(1, len(func_calls))) as executor:
            futures = [executor.submit(self._execute_tool, fc.name, fc.args) for fc in func_calls]
            for i, future in enumerate(futures):
                try:
                    results[i] = future.result()
                except Exception as e:
                    self._debug_log(f"_execute_tool({func_calls[i].name}) failed at {step_desc} | error: {e}")
                    results[i] = f"Error: {e}"
                    errors.add(i)

        # Log results
        for i, fc in enumerate(func_calls):
            res = results[i]
            self.log("tool_error" if i in errors else "tool_response", f"{fc.name} -> {res}")

        return results, errors

    async def _execute_tools_parallel_async(self, func_calls: list[FunctionCall], step_desc: str) -> tuple[list[str], set[int]]:
        """Execute tools in parallel (async), return results and error indices."""
        raw_results = await asyncio.gather(
            *[self._execute_tool_async(fc.name, fc.args) for fc in func_calls],
            return_exceptions=True,
        )

        results: list[str] = []
        errors: set[int] = set()
        for i, value in enumerate(raw_results):
            if isinstance(value, Exception):
                self._debug_log(f"_execute_tool_async({func_calls[i].name}) failed at {step_desc} | error: {value}")
                results.append(f"Error: {value}")
                errors.add(i)
            else:
                results.append(value)

        for i, fc in enumerate(func_calls):
            self.log("tool_error" if i in errors else "tool_response", f"{fc.name} -> {results[i]}")

        return results, errors

    # === Context compaction ===
    _pending_compaction = None  # Future from executor
    _pending_context_snapshot: object = None  # Context state when compaction started
    _pending_keep_recent: int = 0

    def _check_compaction_needed(self, context: object) -> bool:
        """Check if context exceeds threshold and compaction should be triggered."""
        if not self.compaction_config.enabled:
            return False
        if not self._brief_created:
            return False  # Don't compact until brief exists
        if self._pending_compaction is not None:
            return False  # Already compacting
        current_tokens = self._estimate_context_tokens(context)
        max_tokens = MAX_CONTEXT_TOKENS.get(self.provider_name, 128_000)
        return current_tokens >= max_tokens * self.compaction_config.threshold

    def _start_async_compaction(self, context: object) -> None:
        """Start async compaction using Gemini. Non-blocking."""
        keep_recent = self.compaction_config.keep_recent_turns  # Number of pairs to keep
        context_len = self._get_context_length(context)

        if context_len <= 2 + keep_recent * 2:  # Rough estimate: each pair ~2 messages
            return  # Nothing to compact

        middle_start = 1  # After task (index 0)
        middle_end = context_len - keep_recent
        if middle_end <= middle_start:
            return

        # Build XML from middle section
        xml_content = self._build_compaction_xml(context, middle_start, middle_end)
        if not xml_content:
            return

        self.log("system", f"[COMPACTION] Starting async summarization of {middle_end - middle_start} items...")
        self._pending_keep_recent = keep_recent
        self._pending_context_snapshot = context

        # Submit to long-lived executor so this remains non-blocking.
        self._pending_compaction = self._compaction_executor.submit(
            self._run_gemini_compaction_sync,
            xml_content,
        )

    def _build_compaction_xml(self, context: object, start_idx: int, end_idx: int) -> str:
        """Build structured XML from context section for LLM summarization."""
        items = self._extract_context_section(context, start_idx, end_idx)
        if not items:
            return ""

        xml = "<execution-history>\n"
        for item in items:
            xml += self._item_to_xml(item)
        xml += "</execution-history>"
        return xml

    def _run_gemini_compaction_sync(self, xml_content: str) -> str:
        """Run compaction with Gemini (blocking, runs in thread)."""
        from google import genai
        from google.genai import types
        import os

        try:
            client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
            response = client.models.generate_content(
                model="gemini-3-flash-preview",
                contents=xml_content,
                config=types.GenerateContentConfig(
                    system_instruction=COMPACTION_SUMMARIZER,
                    thinking_config=types.ThinkingConfig(thinking_level="LOW"),
                ),
            )
            return response.text or ""
        except Exception as e:
            self._debug_log(f"Gemini compaction failed: {e}")
            return ""

    def _apply_pending_compaction(self, context: object) -> object:
        """Apply completed compaction if ready. Returns updated or original context."""
        if self._pending_compaction is None:
            return context

        # Check if done (non-blocking)
        if not self._pending_compaction.done():
            return context

        try:
            summary = self._pending_compaction.result()
        except Exception as e:
            self._debug_log(f"Compaction result failed: {e}")
            summary = ""
        finally:
            self._pending_compaction = None

        if not summary:
            self.log("system", "[COMPACTION] Failed - continuing with full context")
            return context

        tokens_before = self._estimate_context_tokens(context)
        new_context = self._rebuild_context_with_summary(context, summary, self._pending_keep_recent)
        tokens_after = self._estimate_context_tokens(new_context)

        self.log("system", f"[COMPACTION] Complete: {tokens_before} → {tokens_after} tokens ({tokens_after/tokens_before:.1%})")
        return new_context

    @abstractmethod
    def _item_to_xml(self, item: object) -> str:
        """Convert a context item to XML string for compaction."""
        pass

    @abstractmethod
    def _extract_context_section(self, context: object, start_idx: int, end_idx: int) -> list:
        """Extract raw context items for compaction."""
        pass

    # === Unified orchestrator ===
    def run_with_mode(
        self,
        task: Prompt,
        mode: ModeConfig,
        enable_search: bool = False,
        enable_bash: bool = False,
        enable_code: bool = False,
        enable_ask_user: bool = False,
        max_iterations: int = 30,
        stream: bool = False,
        stream_subagents: bool = False,
        # Mode-specific kwargs (e.g., plan for plan mode, num_takes for explore)
        **mode_kwargs,
    ) -> str:
        """Unified orchestrator that reads all behavior from ModeConfig.

        Args:
            task: The task prompt
            mode: ModeConfig defining orchestrator behavior
            enable_search: Enable search_web tool
            enable_bash: Enable search_files tool
            enable_code: Enable execute_code tool
            enable_ask_user: Enable ask_user tool
            max_iterations: Max orchestrator iterations
            stream: Enable streaming for main orchestrator
            stream_subagents: Enable streaming for subagents
            **mode_kwargs: Mode-specific arguments:
                - plan mode: plan=str (pre-created plan)
                - explore mode: num_takes=int (hint for number of takes)
        """
        # Reset state based on rubric strategy
        # 'pre_create' and 'provided' mean rubric is already set by caller
        if mode.rubric_strategy not in ("pre_create", "provided"):
            self.rubric = None
        self.submitted_answer = None
        self._brief_created = False
        self.mode = mode.name
        self.enable_search = enable_search
        self.stream = stream
        self.stream_subagents = stream_subagents

        # Get tools for this mode
        tool_names = get_tools_for_mode(mode, enable_search, enable_bash, enable_code, enable_ask_user)

        has_skills = bool(self._skills_dir and self._skill_index)

        # Get orchestrator prompt
        system = PROMPTS[mode.orchestrator_prompt]
        
        # Handle prompt kwargs (e.g., {task} and {plan} for plan mode)
        if mode.prompt_kwargs:
            task_text = _prompt_to_log(task)
            format_args = {"task": task_text}
            format_args.update(mode_kwargs)
            system = system.format(**format_args)
        
        # Handle explore-specific: inject num_takes hint
        if mode.name == "explore":
            num_takes = mode_kwargs.get("num_takes", 0)
            if num_takes > 0:
                system = system.replace(
                    "## MINIMUM TAKES",
                    f"## TARGET TAKES\nGenerate approximately {num_takes} takes.\n\n## MINIMUM TAKES"
                )

        # Inject skill context — build_skill always available, skill= for delegate only when skills exist
        if has_skills:
            system += self._skill_index
            system += "\nYou can pass `skill=<name>` to delegate to inject a skill's approach and code into the delegate's context."
        else:
            system += "\n\n## SKILLS\nNo learned skills yet. Use build_skill(name, context) after solving a task to capture reusable approaches. Do NOT pass `skill` to delegate."

        # Inject sandbox context if using RemoteExecutor
        if enable_code and self.code_executor and hasattr(self.code_executor, "get_sandbox_context"):
            sandbox_ctx = self.code_executor.get_sandbox_context()
            if sandbox_ctx:
                system += f"\n\n## CODE EXECUTION ENVIRONMENT\n{sandbox_ctx}\nWrite code compatible with this environment."

        # Inject ask_user addendum if enabled
        if enable_ask_user:
            system += ASK_USER_ADDENDUM

        task_text = _prompt_to_log(task)
        self.log("user", task_text)
        self.log("system", f"[{mode.name.title()} Mode] {system[:200]}...")

        return self._orchestrator_loop(task, system, tool_names, max_iterations)

    async def run_with_mode_async(
        self,
        task: Prompt,
        mode: ModeConfig,
        enable_search: bool = False,
        enable_bash: bool = False,
        enable_code: bool = False,
        enable_ask_user: bool = False,
        max_iterations: int = 30,
        stream: bool = False,
        stream_subagents: bool = False,
        **mode_kwargs,
    ) -> str:
        """Async orchestrator entrypoint."""
        if mode.rubric_strategy not in ("pre_create", "provided"):
            self.rubric = None
        self.submitted_answer = None
        self._brief_created = False
        self.mode = mode.name
        self.enable_search = enable_search
        self.stream = stream
        self.stream_subagents = stream_subagents

        tool_names = get_tools_for_mode(mode, enable_search, enable_bash, enable_code, enable_ask_user)
        has_skills = bool(self._skills_dir and self._skill_index)
        system = PROMPTS[mode.orchestrator_prompt]

        if mode.prompt_kwargs:
            task_text = _prompt_to_log(task)
            format_args = {"task": task_text}
            format_args.update(mode_kwargs)
            system = system.format(**format_args)

        if mode.name == "explore":
            num_takes = mode_kwargs.get("num_takes", 0)
            if num_takes > 0:
                system = system.replace(
                    "## MINIMUM TAKES",
                    f"## TARGET TAKES\nGenerate approximately {num_takes} takes.\n\n## MINIMUM TAKES",
                )

        if has_skills:
            system += self._skill_index
            system += "\nYou can pass `skill=<name>` to delegate to inject a skill's approach and code into the delegate's context."
        else:
            system += "\n\n## SKILLS\nNo learned skills yet. Use build_skill(name, context) after solving a task to capture reusable approaches. Do NOT pass `skill` to delegate."

        if enable_code and self.code_executor and hasattr(self.code_executor, "get_sandbox_context"):
            sandbox_ctx = self.code_executor.get_sandbox_context()
            if sandbox_ctx:
                system += f"\n\n## CODE EXECUTION ENVIRONMENT\n{sandbox_ctx}\nWrite code compatible with this environment."

        if enable_ask_user:
            system += ASK_USER_ADDENDUM

        task_text = _prompt_to_log(task)
        self.log("user", task_text)
        self.log("system", f"[{mode.name.title()} Mode] {system[:200]}...")

        return await self._orchestrator_loop_async(task, system, tool_names, max_iterations)

    # === Legacy methods for backwards compatibility ===
    def run_orchestrator(
        self,
        task: Prompt,
        system: str,
        enable_search: bool = False,
        enable_bash: bool = False,
        enable_code: bool = False,
        enable_ask_user: bool = False,
        max_iterations: int = 30,
        stream: bool = False,
        stream_subagents: bool = False,
    ) -> str:
        """Legacy: Run standard orchestrator. Use run_with_mode instead."""
        return self.run_with_mode(
            task=task,
            mode=get_mode("standard"),
            enable_search=enable_search,
            enable_bash=enable_bash,
            enable_code=enable_code,
            enable_ask_user=enable_ask_user,
            max_iterations=max_iterations,
            stream=stream,
            stream_subagents=stream_subagents,
        )

    def run_orchestrator_with_plan(
        self,
        task: Prompt,
        plan: str,
        system: str,
        enable_search: bool = False,
        enable_bash: bool = False,
        enable_code: bool = False,
        enable_ask_user: bool = False,
        max_iterations: int = 30,
        stream: bool = False,
        stream_subagents: bool = False,
    ) -> str:
        """Legacy: Run plan mode. Use run_with_mode instead."""
        return self.run_with_mode(
            task=task,
            mode=get_mode("plan"),
            enable_search=enable_search,
            enable_bash=enable_bash,
            enable_code=enable_code,
            enable_ask_user=enable_ask_user,
            max_iterations=max_iterations,
            stream=stream,
            stream_subagents=stream_subagents,
            plan=plan,
        )

    def run_explore_orchestrator(
        self,
        task: Prompt,
        num_takes: int = 0,
        enable_search: bool = False,
        enable_bash: bool = False,
        enable_code: bool = False,
        enable_ask_user: bool = False,
        max_iterations: int = 30,
        stream: bool = False,
        stream_subagents: bool = False,
    ) -> str:
        """Legacy: Run explore mode. Use run_with_mode instead."""
        return self.run_with_mode(
            task=task,
            mode=get_mode("explore"),
            enable_search=enable_search,
            enable_bash=enable_bash,
            enable_code=enable_code,
            enable_ask_user=enable_ask_user,
            max_iterations=max_iterations,
            stream=stream,
            stream_subagents=stream_subagents,
            num_takes=num_takes,
        )

    def _orchestrator_loop(
        self,
        task: Prompt,
        system: str,
        tool_names: list[str],
        max_iterations: int,
        _context: object = None,
        _start_iteration: int = 0,
    ) -> str:
        """Common orchestrator loop - providers implement the abstract methods.

        Args:
            _context: Pre-built context for resume. If None, initializes fresh.
            _start_iteration: Starting iteration (for resume, adjusts remaining iterations).
        """
        context = _context if _context is not None else self._init_context(task, system, tool_names)
        last_tools = []

        if self._checkpoint and not self._run_id:
            self._run_id = uuid.uuid4().hex[:12]

        for iteration in range(_start_iteration, max_iterations):
            # Snapshot before model call
            if self._checkpoint:
                snap_id = f"{self._run_id}:step:{iteration}"
                self.snapshots[snap_id] = Snapshot(
                    id=snap_id,
                    step=iteration,
                    context=copy.deepcopy(context),
                    state={
                        "rubric": self.rubric,
                        "brief": self.brief,
                        "submitted_answer": self.submitted_answer,
                        "_brief_created": self._brief_created,
                        "mode": self.mode,
                    },
                    history_index=len(self.history),
                    tool_names=list(tool_names),
                    system=system,
                )

            step_desc = f"iteration {iteration}" + (f" (after {', '.join(last_tools)})" if last_tools else "")

            try:
                func_calls, output_text = self._call_model(context, step_desc, stream=self.stream)
            except Exception as e:
                self._debug_log(f"_call_model failed at {step_desc} | error: {e}")
                self.log("tool_error", f"orchestrator {step_desc}: {e}")
                raise

            if not func_calls:
                return output_text or self.submitted_answer or ""

            if self.submitted_answer:
                return self.submitted_answer

            last_tools = [fc.name for fc in func_calls]
            results, _ = self._execute_tools_parallel(func_calls, step_desc)
            self._append_tool_results(context, func_calls, results)

            # Poll completed background tasks
            for tid in list(self._background_tasks):
                bt = self._background_tasks[tid]
                if bt.future.done():
                    self._background_tasks.pop(tid)
                    try:
                        bg_result = bt.future.result()
                        self._inject_feedback(
                            context,
                            f"[Background agent {tid} completed]\nTask: {bt.prompt[:300]}\nResult:\n{bg_result}",
                        )
                        self.log("tool_response", f"background_{tid} -> {bg_result[:500]}")
                    except Exception as e:
                        self._inject_feedback(context, f"[Background agent {tid} failed]: {e}")
                        self.log("tool_error", f"background_{tid}: {e}")

            # Apply pending compaction if ready
            context = self._apply_pending_compaction(context)

            # Start new compaction if needed (async, non-blocking)
            if self._check_compaction_needed(context):
                self._start_async_compaction(context)

            if self.submitted_answer:
                return self.submitted_answer

        return self.submitted_answer or "Max iterations reached"

    async def _orchestrator_loop_async(
        self,
        task: Prompt,
        system: str,
        tool_names: list[str],
        max_iterations: int,
        _context: object = None,
        _start_iteration: int = 0,
    ) -> str:
        """Async orchestrator loop."""
        context = _context if _context is not None else self._init_context(task, system, tool_names)
        last_tools = []

        if self._checkpoint and not self._run_id:
            self._run_id = uuid.uuid4().hex[:12]

        for iteration in range(_start_iteration, max_iterations):
            if self._checkpoint:
                snap_id = f"{self._run_id}:step:{iteration}"
                self.snapshots[snap_id] = Snapshot(
                    id=snap_id,
                    step=iteration,
                    context=copy.deepcopy(context),
                    state={
                        "rubric": self.rubric,
                        "brief": self.brief,
                        "submitted_answer": self.submitted_answer,
                        "_brief_created": self._brief_created,
                        "mode": self.mode,
                    },
                    history_index=len(self.history),
                    tool_names=list(tool_names),
                    system=system,
                )

            step_desc = f"iteration {iteration}" + (f" (after {', '.join(last_tools)})" if last_tools else "")

            try:
                func_calls, output_text = await self._call_model_async(context, step_desc, stream=self.stream)
            except Exception as e:
                self._debug_log(f"_call_model_async failed at {step_desc} | error: {e}")
                self.log("tool_error", f"orchestrator {step_desc}: {e}")
                raise

            if not func_calls:
                return output_text or self.submitted_answer or ""

            if self.submitted_answer:
                return self.submitted_answer

            last_tools = [fc.name for fc in func_calls]
            results, _ = await self._execute_tools_parallel_async(func_calls, step_desc)
            self._append_tool_results(context, func_calls, results)

            for tid in list(self._background_tasks):
                bt = self._background_tasks[tid]
                if bt.future.done():
                    self._background_tasks.pop(tid)
                    try:
                        bg_result = bt.future.result()
                        self._inject_feedback(
                            context,
                            f"[Background agent {tid} completed]\nTask: {bt.prompt[:300]}\nResult:\n{bg_result}",
                        )
                        self.log("tool_response", f"background_{tid} -> {str(bg_result)[:500]}")
                    except Exception as e:
                        self._inject_feedback(context, f"[Background agent {tid} failed]: {e}")
                        self.log("tool_error", f"background_{tid}: {e}")

            context = self._apply_pending_compaction(context)
            if self._check_compaction_needed(context):
                self._start_async_compaction(context)

            if self.submitted_answer:
                return self.submitted_answer

            # Explicit event-loop yield between iterations for fairness.
            await asyncio.sleep(0)

        return self.submitted_answer or "Max iterations reached"

    def resume_from_snapshot(
        self,
        snapshot: Snapshot,
        feedback: str | None = None,
        max_iterations: int = 30,
    ) -> str:
        """Resume orchestrator from a snapshot, optionally injecting feedback.

        Returns the answer string. Caller (harness) wraps into RunResult.
        """
        # Restore state
        context = copy.deepcopy(snapshot.context)
        self.rubric = snapshot.state["rubric"]
        self.brief = snapshot.state["brief"]
        self.submitted_answer = snapshot.state["submitted_answer"]
        self._brief_created = snapshot.state["_brief_created"]
        self.mode = snapshot.state["mode"]

        # Trim history to snapshot point
        self.history = self.history[:snapshot.history_index]

        # New run_id for the resumed trajectory
        self._run_id = uuid.uuid4().hex[:12]

        # Inject feedback if provided
        if feedback:
            self._inject_feedback(context, feedback)
            self.log("user", f"[Resume feedback] {feedback}")

        self.log("system", f"[Resume] from {snapshot.id}, step {snapshot.step}")

        return self._orchestrator_loop(
            task="",  # unused when _context is provided
            system=snapshot.system,
            tool_names=snapshot.tool_names,
            max_iterations=max_iterations,
            _context=context,
            _start_iteration=snapshot.step,
        )

    def search_files(self, query: str, path: str = ".") -> str:
        """File search subagent - uses bash + read_file, returns summary."""
        prompt = f"Search in directory: {path}\n\nQuery: {query}"
        tool_names = ["bash", "read_file"]
        context = self._init_context(prompt, FILE_SEARCH_AGENT, tool_names)

        for iteration in range(15):  # Max 15 iterations for file search
            try:
                func_calls, output_text = self._call_model(context, f"file_search_{iteration}")
            except Exception as e:
                self._debug_log(f"search_files failed at iteration {iteration} | error: {e}")
                return f"Error searching files: {e}"

            if not func_calls:
                return output_text or "No results found."

            # Execute tools via _execute_tool (respects remote executor routing)
            results = []
            for fc in func_calls:
                if fc.name in ("bash", "read_file"):
                    results.append(self._execute_tool(fc.name, fc.args))
                else:
                    results.append(f"Unknown tool: {fc.name}")

            self._append_tool_results(context, func_calls, results)

        return "File search reached max iterations."

    async def resume_from_snapshot_async(
        self,
        snapshot: Snapshot,
        feedback: str | None = None,
        max_iterations: int = 30,
    ) -> str:
        """Async resume orchestrator from a snapshot."""
        context = copy.deepcopy(snapshot.context)
        self.rubric = snapshot.state["rubric"]
        self.brief = snapshot.state["brief"]
        self.submitted_answer = snapshot.state["submitted_answer"]
        self._brief_created = snapshot.state["_brief_created"]
        self.mode = snapshot.state["mode"]
        self.history = self.history[:snapshot.history_index]
        self._run_id = uuid.uuid4().hex[:12]

        if feedback:
            self._inject_feedback(context, feedback)
            self.log("user", f"[Resume feedback] {feedback}")

        self.log("system", f"[Resume] from {snapshot.id}, step {snapshot.step}")
        return await self._orchestrator_loop_async(
            task="",
            system=snapshot.system,
            tool_names=snapshot.tool_names,
            max_iterations=max_iterations,
            _context=context,
            _start_iteration=snapshot.step,
        )

    async def search_files_async(self, query: str, path: str = ".") -> str:
        """Async file search subagent."""
        prompt = f"Search in directory: {path}\n\nQuery: {query}"
        tool_names = ["bash", "read_file"]
        context = self._init_context(prompt, FILE_SEARCH_AGENT, tool_names)

        for iteration in range(15):
            try:
                func_calls, output_text = await self._call_model_async(context, f"file_search_{iteration}")
            except Exception as e:
                self._debug_log(f"search_files_async failed at iteration {iteration} | error: {e}")
                return f"Error searching files: {e}"

            if not func_calls:
                return output_text or "No results found."

            results = []
            for fc in func_calls:
                if fc.name in ("bash", "read_file"):
                    results.append(await self._execute_tool_async(fc.name, fc.args))
                else:
                    results.append(f"Unknown tool: {fc.name}")

            self._append_tool_results(context, func_calls, results)

        return "File search reached max iterations."

    # === Abstract methods - provider must implement ===
    @abstractmethod
    def generate(self, prompt: str, system: str = None, _log: bool = True, enable_search: bool = False,
                 stream: bool = False, subagent_id: str = None, stream_event_type: str = None,
                 stream_meta: dict = None, tools: list[str] = None, _tool_depth: int = 0) -> str:
        """Generation. When tools provided (e.g. ["execute_code", "bash"]):
        iterates tool calls up to 5 rounds, then synthesizes. Returns clean text.
        Like search(), the caller gets clean text back. Tools are a black box."""
        pass

    @abstractmethod
    def search(self, query: str, stream: bool = False, subagent_id: str = None) -> str:
        """Dedicated search subagent. If stream=True and subagent_id provided, emit subagent_chunk events."""
        pass

    @abstractmethod
    def read_file_with_vision(self, file_path: str, prompt: str) -> str:
        """Read a file using vision/multimodal capabilities and return a summary."""
        pass

    @abstractmethod
    def _init_context(self, task: Prompt, system: str, tool_names: list[str]) -> object:
        """Initialize provider-specific context for orchestrator loop."""
        pass

    @abstractmethod
    def _call_model(self, context: object, step_desc: str, stream: bool = False) -> tuple[list[FunctionCall], str]:
        """Call model, return (func_calls, output_text). If stream=True, emit events via self.log() as chunks arrive."""
        pass

    @abstractmethod
    def _append_tool_results(self, context: object, func_calls: list[FunctionCall], results: list[str]):
        """Append tool results to context."""
        pass

    @abstractmethod
    def _debug_log(self, message: str):
        """Log debug message to provider-specific logger."""
        pass

    # === Abstract methods for context compaction ===
    @abstractmethod
    def _estimate_context_tokens(self, context: object) -> int:
        """Estimate token count for the context.
        Gemini: use count_tokens API. OpenAI: chars / 4."""
        pass

    @abstractmethod
    def _get_context_length(self, context: object) -> int:
        """Get number of messages/turns in context."""
        pass

    @abstractmethod
    def _rebuild_context_with_summary(self, context: object, summary: str, keep_recent: int) -> object:
        """Rebuild context with summary replacing middle section."""
        pass

    @abstractmethod
    def _inject_feedback(self, context: object, text: str) -> None:
        """Append a user message with feedback text to context in provider-native format.

        Required for checkpointing resume. New providers must implement this.
        """
        pass
