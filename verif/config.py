from dataclasses import dataclass, field
from typing import Union, Callable, Any


@dataclass
class ModeConfig:
    """Configuration for a specific execution mode.
    
    This abstraction unifies plan mode and explore mode at the same layer,
    making modes first-class citizens with declarative configuration.
    """
    name: str  # "standard" | "plan" | "explore"
    
    # Prompt selection (prompt names, not actual strings - resolved at runtime)
    orchestrator_prompt: str  # Key into prompts module
    brief_prompt: str         # Key into prompts module
    
    # Tool configuration
    tools: list[str] = field(default_factory=list)  # Base tools for this mode
    verification_tool: str = "verify_answer"  # "verify_answer" | "verify_exploration"
    
    # Rubric strategy
    rubric_strategy: str = "create"  # "create" | "pre_create" | "skip"
    # - "create": Orchestrator calls create_rubric during execution
    # - "pre_create": Rubric created in pre-execution phase, hidden from orchestrator
    # - "skip": No rubric (e.g., explore mode uses checklist verifier)
    
    # Pre-execution phase (e.g., plan creation)
    has_pre_execution: bool = False  # Whether mode has a pre-execution phase
    
    # Mode-specific prompt kwargs (e.g., {task}, {plan} for plan mode)
    prompt_kwargs: list[str] = field(default_factory=list)


@dataclass
class ProviderConfig:
    name: str  # "gemini" | "openai"
    api_key: str | None = None  # None = read from env
    thinking_level: str = "MEDIUM"  # gemini
    reasoning_effort: str = "medium"  # openai


@dataclass
class Attachment:
    content: bytes | str  # bytes for data, str for file path or URL
    mime_type: str  # "image/png", "application/pdf", etc.
    name: str = ""  # optional filename
    preview: str | None = None  # first N lines for text files; None for PDF/images (use search_files)


# Prompt can be text or multimodal (list of text/attachments)
Prompt = Union[str, list[Union[str, Attachment]]]


@dataclass
class CompactionConfig:
    enabled: bool = True
    threshold: float = 0.8  # Trigger at 80% of max context
    keep_recent_turns: int = 3  # Keep last N tool exchanges verbatim
    max_summary_tokens: int = 1000  # Max tokens for summary section
