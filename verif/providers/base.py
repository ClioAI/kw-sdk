import time
import logging
import subprocess
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor

from ..prompts import (
    BRIEF_CREATOR, RUBRIC_CREATOR, VERIFICATION, FILE_SEARCH_AGENT, COMPACTION_SUMMARIZER,
    EXPLORE_ORCHESTRATOR, EXPLORE_BRIEF, EXPLORE_VERIFIER, ORCHESTRATOR, ORCHESTRATOR_WITH_PLAN,
    ITERATE_ORCHESTRATOR
)
from ..config import Prompt, Attachment, CompactionConfig, ModeConfig
from ..modes import get_mode, get_tools_for_mode


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
    "spawn_subagent": {
        "name": "spawn_subagent",
        "description": "Spawn a subagent to handle a specific subtask. Use for decomposing complex tasks.",
        "parameters": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "The task prompt for the subagent. Be specific."},
            },
            "required": ["prompt"],
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
        self.code_executor = None  # Set by harness if enable_code=True
        self.enable_search: bool = False  # Set by harness, used by spawn_subagent
        self.compaction_config = CompactionConfig()  # Default config
        self._brief_created = False  # Track if brief has been created
        # Streaming flags
        self.stream: bool = False
        self.stream_subagents: bool = False
        self._subagent_counter: int = 0
        # Mode tracking
        self.mode: str = "standard"  # "standard" | "plan" | "explore"

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

    # === Common tool execution ===
    def _execute_tool(self, name: str, args: dict) -> str:
        if name == "create_brief":
            # Get brief prompt from mode config via registry
            mode_config = get_mode(self.mode)
            brief_prompt = PROMPTS[mode_config.brief_prompt]
            result = self.generate(args.get("task", ""), system=brief_prompt, _log=False)
            self._brief_created = True
            self.brief = result
            return result

        elif name == "create_rubric":
            if self.rubric:
                return "Rubric already set (using pre-existing)."
            brief = args.get("brief", "")
            try:
                self.rubric = self.generate(brief, system=RUBRIC_CREATOR, _log=False)
                return "Rubric created."
            except Exception as e:
                self.rubric = f"ERROR: {e}"
                raise

        elif name == "spawn_subagent":
            prompt = args.get("prompt", "")
            if self.enable_search:
                prompt = prompt + "\n\nYou have web search available. Use it to find information."
            subagent_id = self._next_subagent_id()
            return self.generate(
                prompt, _log=False, enable_search=self.enable_search,
                stream=self.stream_subagents, subagent_id=subagent_id
            )

        elif name == "search_web":
            subagent_id = self._next_subagent_id()
            return self.search(args.get("query", ""), stream=self.stream_subagents, subagent_id=subagent_id)

        elif name == "verify_answer":
            answer = args.get("answer", "")
            if not self.rubric:
                return "ERROR: No rubric created. Call create_rubric first."
            verification_prompt = f"## Rubric\n{self.rubric}\n\n## Answer\n{answer}"
            return self.generate(verification_prompt, system=VERIFICATION, _log=False)

        elif name == "submit_answer":
            self.submitted_answer = args.get("answer", "")
            return "SUBMITTED"

        elif name == "bash":
            return self._execute_bash(
                args.get("command", ""),
                args.get("working_directory")
            )

        elif name == "read_file":
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
            query = args.get("query", "")
            path = args.get("path", ".")
            return self.search_files(query, path)

        elif name == "verify_exploration":
            takes = args.get("takes", "")
            # Use custom rubric if provided, else use default EXPLORE_VERIFIER
            verifier_prompt = self.rubric if self.rubric else EXPLORE_VERIFIER
            verification_prompt = f"## Exploration Output\n{takes}"
            return self.generate(verification_prompt, system=verifier_prompt, _log=False)

        return f"Unknown tool: {name}"

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

        # Run Gemini summarization in thread pool
        with ThreadPoolExecutor(max_workers=1) as executor:
            self._pending_compaction = executor.submit(
                self._run_gemini_compaction_sync,
                xml_content
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
        tool_names = get_tools_for_mode(mode, enable_search, enable_bash, enable_code)

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

        task_text = _prompt_to_log(task)
        self.log("user", task_text)
        self.log("system", f"[{mode.name.title()} Mode] {system[:200]}...")

        return self._orchestrator_loop(task, system, tool_names, max_iterations)

    # === Legacy methods for backwards compatibility ===
    def run_orchestrator(
        self,
        task: Prompt,
        system: str,
        enable_search: bool = False,
        enable_bash: bool = False,
        enable_code: bool = False,
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
    ) -> str:
        """Common orchestrator loop - providers implement the abstract methods."""
        context = self._init_context(task, system, tool_names)
        last_tools = []

        for iteration in range(max_iterations):
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

            # Apply pending compaction if ready
            context = self._apply_pending_compaction(context)

            # Start new compaction if needed (async, non-blocking)
            if self._check_compaction_needed(context):
                self._start_async_compaction(context)

            if self.submitted_answer:
                return self.submitted_answer

        return self.submitted_answer or "Max iterations reached"

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

            # Execute tools (bash, read_file only)
            results = []
            for fc in func_calls:
                if fc.name == "bash":
                    results.append(self._execute_bash(fc.args.get("command", ""), fc.args.get("working_directory", path)))
                elif fc.name == "read_file":
                    results.append(self.read_file_with_vision(fc.args.get("file_path", ""), fc.args.get("prompt", "Summarize this file.")))
                else:
                    results.append(f"Unknown tool: {fc.name}")

            self._append_tool_results(context, func_calls, results)

        return "File search reached max iterations."

    # === Abstract methods - provider must implement ===
    @abstractmethod
    def generate(self, prompt: str, system: str = None, _log: bool = True, enable_search: bool = False,
                 stream: bool = False, subagent_id: str = None) -> str:
        """Simple generation without tools. If stream=True and subagent_id provided, emit subagent_chunk events."""
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
