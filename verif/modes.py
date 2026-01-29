"""
Mode definitions for the harness.

This module defines the three execution modes as ModeConfig instances,
providing a unified abstraction for mode-specific behavior.
"""

from .config import ModeConfig


# =============================================================================
# MODE DEFINITIONS
# =============================================================================

STANDARD_MODE = ModeConfig(
    name="standard",
    orchestrator_prompt="ORCHESTRATOR",
    brief_prompt="BRIEF_CREATOR",
    tools=["create_brief", "create_rubric", "spawn_subagent", "verify_answer", "submit_answer"],
    verification_tool="verify_answer",
    rubric_strategy="create",  # Orchestrator creates rubric during execution
    has_pre_execution=False,
    prompt_kwargs=[],
)

PLAN_MODE = ModeConfig(
    name="plan",
    orchestrator_prompt="ORCHESTRATOR_WITH_PLAN",
    brief_prompt="BRIEF_CREATOR",
    # create_rubric included so orchestrator can create one if caller doesn't provide
    tools=["create_rubric", "spawn_subagent", "verify_answer", "submit_answer"],
    verification_tool="verify_answer",
    rubric_strategy="provided",  # Rubric may be provided by caller, or created via tool
    has_pre_execution=False,  # Plan provided by user, no auto-creation
    prompt_kwargs=["task", "plan"],  # These get formatted into the prompt
)

EXPLORE_MODE = ModeConfig(
    name="explore",
    orchestrator_prompt="EXPLORE_ORCHESTRATOR",
    brief_prompt="EXPLORE_BRIEF",
    tools=["create_brief", "spawn_subagent", "verify_exploration", "submit_answer"],  # No create_rubric
    verification_tool="verify_exploration",
    rubric_strategy="skip",  # Uses predefined checklist verifier
    has_pre_execution=False,
    prompt_kwargs=[],
)

ITERATE_MODE = ModeConfig(
    name="iterate",
    orchestrator_prompt="ITERATE_ORCHESTRATOR",
    brief_prompt="BRIEF_CREATOR",  # Not used, but required
    tools=["spawn_subagent", "verify_answer", "submit_answer"],  # No brief/rubric creation
    verification_tool="verify_answer",
    rubric_strategy="provided",  # Rubric provided by caller
    has_pre_execution=False,
    prompt_kwargs=["original_task", "current_answer", "user_feedback"],
)


# Registry for easy lookup
MODES: dict[str, ModeConfig] = {
    "standard": STANDARD_MODE,
    "plan": PLAN_MODE,
    "explore": EXPLORE_MODE,
    "iterate": ITERATE_MODE,
}


def get_mode(name: str) -> ModeConfig:
    """Get mode configuration by name.
    
    Args:
        name: Mode name ("standard", "plan", "explore")
        
    Returns:
        ModeConfig for the specified mode
        
    Raises:
        ValueError: If mode name is unknown
    """
    if name not in MODES:
        raise ValueError(f"Unknown mode: {name}. Available: {list(MODES.keys())}")
    return MODES[name]


def get_tools_for_mode(
    mode: ModeConfig,
    enable_search: bool = False,
    enable_bash: bool = False,
    enable_code: bool = False,
) -> list[str]:
    """Get the full tool list for a mode with optional capabilities.
    
    Args:
        mode: The mode configuration
        enable_search: Whether to include search_web tool
        enable_bash: Whether to include search_files tool
        enable_code: Whether to include execute_code tool
        
    Returns:
        List of tool names in the order they should appear
    """
    tools = mode.tools.copy()
    
    # Find insertion point (before verification tool)
    verification_idx = len(tools)
    for i, tool in enumerate(tools):
        if tool in ("verify_answer", "verify_exploration"):
            verification_idx = i
            break
    
    # Insert optional tools before verification
    optional_tools = []
    if enable_search:
        optional_tools.append("search_web")
    if enable_bash:
        optional_tools.append("search_files")
    if enable_code:
        optional_tools.append("execute_code")
    
    for i, tool in enumerate(optional_tools):
        tools.insert(verification_idx + i, tool)
    
    return tools
