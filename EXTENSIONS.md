# Extending the SDK

This guide covers how to add new providers and new execution modes.

---

## Adding a New Provider

Providers wrap LLM APIs. The SDK uses a `BaseProvider` abstract class that handles the orchestrator loop, tool execution, and context management. You implement the model-specific parts.

### 1. Create the Provider Class

Create a new file in `verif/providers/`:

```python
# verif/providers/my_provider.py
import os
from .base import BaseProvider, FunctionCall, TOOL_DEFINITIONS, retry_on_error

class MyProvider(BaseProvider):
    provider_name = "my_provider"  # Used for context token limits
    
    def __init__(self):
        super().__init__()
        self.client = ...  # Initialize your API client
```

### 2. Implement Required Abstract Methods

#### Core Generation

```python
def generate(
    self, 
    prompt: str, 
    system: str = None, 
    _log: bool = True, 
    enable_search: bool = False,
    stream: bool = False, 
    subagent_id: str = None
) -> str:
    """Simple generation without tools.
    
    Used by subagents and simple completions.
    If stream=True, emit 'subagent_chunk' events via self.emit().
    """
    ...

def search(
    self, 
    query: str, 
    stream: bool = False, 
    subagent_id: str = None
) -> str:
    """Search subagent - generation with web search enabled.
    
    If stream=True, emit 'subagent_chunk' events.
    """
    ...

def read_file_with_vision(self, file_path: str, prompt: str) -> str:
    """Read a file using vision/multimodal capabilities.
    
    Handle images, PDFs, etc. Return extracted content as text.
    """
    ...
```

#### Orchestrator Loop

The base class runs the orchestrator loop. You implement context management:

```python
def _init_context(
    self, 
    task: Prompt, 
    system: str, 
    tool_names: list[str]
) -> object:
    """Initialize provider-specific context for the orchestrator loop.
    
    Args:
        task: The user's task (string or multimodal Prompt)
        system: System prompt
        tool_names: List of tool names to enable
        
    Returns:
        Provider-specific context object (dict, list, etc.)
    """
    # Convert tool_names to your API's format using TOOL_DEFINITIONS
    tools = [self._to_my_format(TOOL_DEFINITIONS[t]) for t in tool_names]
    
    # Build initial messages
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": self._prompt_to_content(task)},
    ]
    
    return {"tools": tools, "messages": messages}

def _call_model(
    self, 
    context: object, 
    step_desc: str, 
    stream: bool = False
) -> tuple[list[FunctionCall], str]:
    """Call the model and extract function calls.
    
    Args:
        context: Your context object from _init_context
        step_desc: Description for logging
        stream: If True, emit 'model_chunk' events via self.emit()
        
    Returns:
        (list of FunctionCall, text output)
    """
    response = self.client.generate(...)
    
    # Extract function calls
    func_calls = [
        FunctionCall(
            name=fc.name,
            args=fc.arguments,  # dict
            raw=fc,  # original object for _append_tool_results
        )
        for fc in response.function_calls
    ]
    
    return func_calls, response.text

def _append_tool_results(
    self, 
    context: object, 
    func_calls: list[FunctionCall], 
    results: list[str]
):
    """Append tool results to context for the next model call.
    
    Args:
        context: Your context object
        func_calls: The function calls that were executed
        results: The string results from each tool
    """
    for i, fc in enumerate(func_calls):
        context["messages"].append({
            "role": "tool",
            "tool_call_id": fc.raw.id,
            "content": results[i],
        })
```

#### Context Compaction

For long-running tasks, the SDK compacts context when it grows too large:

```python
def _estimate_context_tokens(self, context: object) -> int:
    """Estimate token count for the context.
    
    Used to decide when to trigger compaction.
    Gemini: use count_tokens API. OpenAI: chars / 4.
    """
    ...

def _get_context_length(self, context: object) -> int:
    """Get number of messages/turns in context."""
    return len(context["messages"])

def _rebuild_context_with_summary(
    self, 
    context: object, 
    summary: str, 
    keep_recent: int
) -> object:
    """Rebuild context with summary replacing middle section.
    
    Args:
        context: Current context
        summary: AI-generated summary of middle section
        keep_recent: Number of recent turns to keep verbatim
        
    Returns:
        New context with compacted middle
    """
    ...
```

#### Debug Logging

```python
def _debug_log(self, message: str):
    """Log debug message to provider-specific logger."""
    self.logger.debug(message)
```

### 3. Register the Provider

In `verif/harness.py`, add your provider to `load_provider()`:

```python
def load_provider(config: ProviderConfig) -> BaseProvider:
    if config.name == "gemini":
        from .providers.gemini import GeminiProvider
        return GeminiProvider()
    elif config.name == "openai":
        from .providers.openai import OpenAIProvider
        return OpenAIProvider()
    elif config.name == "my_provider":  # Add this
        from .providers.my_provider import MyProvider
        return MyProvider()
    raise ValueError(f"Unknown provider: {config.name}")
```

### 4. Update Context Token Limits

In `verif/providers/base.py`, add your provider's context limit:

```python
MAX_CONTEXT_TOKENS = {
    "gemini": 1_000_000,
    "openai": 128_000,
    "my_provider": 200_000,  # Add this
}
```

### 5. Use It

```python
harness = RLHarness(provider="my_provider")
result = harness.run_single("Analyze market trends")
```

### OpenRouter Example

OpenRouter uses OpenAI-compatible API, so you can subclass `OpenAIProvider`:

```python
# verif/providers/openrouter.py
import os
from openai import OpenAI
from .openai import OpenAIProvider

class OpenRouterProvider(OpenAIProvider):
    provider_name = "openrouter"
    
    def __init__(self, model: str = "anthropic/claude-3.5-sonnet"):
        # Don't call super().__init__() - we override the client
        from .base import BaseProvider
        BaseProvider.__init__(self)
        
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.environ["OPENROUTER_API_KEY"],
        )
        self.model = model
        self.reasoning_effort = "medium"
```

---

## Adding a New Mode

Modes define how the orchestrator executes tasks. Each mode specifies:

> **Example:** See [examples/custom_mode_bizarro.py](examples/custom_mode_bizarro.py) for a complete working example of runtime mode registration.
- Which tools are available
- Which prompts to use
- How rubrics are handled
- What kwargs get passed to prompts

### 1. Define the Mode Config

In `verif/modes.py`, add a new `ModeConfig`:

```python
MY_MODE = ModeConfig(
    name="my_mode",
    
    # Prompt keys (resolved from verif/prompts.py at runtime)
    orchestrator_prompt="MY_ORCHESTRATOR",  # Main orchestrator prompt
    brief_prompt="MY_BRIEF",                 # Brief creation prompt (if used)
    
    # Tools available in this mode
    tools=[
        "create_brief",      # Optional: create structured brief
        "create_rubric",     # Optional: create verification rubric
        "spawn_subagent",    # Delegate subtasks
        "verify_answer",     # Verification tool
        "submit_answer",     # Submit final answer
    ],
    
    # Verification
    verification_tool="verify_answer",  # or "verify_exploration"
    
    # Rubric strategy
    rubric_strategy="create",  # "create" | "provided" | "skip"
    # - "create": Orchestrator creates rubric during execution
    # - "provided": Caller provides rubric (or orchestrator creates if missing)
    # - "skip": No rubric (e.g., explore mode uses checklist verifier)
    
    # Pre-execution phase
    has_pre_execution=False,  # True if mode needs setup before main loop
    
    # Kwargs formatted into the orchestrator prompt
    prompt_kwargs=["task", "custom_param"],  # {task} and {custom_param} in prompt
)
```

### 2. Register the Mode

Add to the `MODES` registry in `verif/modes.py`:

```python
MODES: dict[str, ModeConfig] = {
    "standard": STANDARD_MODE,
    "plan": PLAN_MODE,
    "explore": EXPLORE_MODE,
    "iterate": ITERATE_MODE,
    "my_mode": MY_MODE,  # Add this
}
```

### 3. Create the Orchestrator Prompt

In `verif/prompts.py`, add your orchestrator prompt:

```python
MY_ORCHESTRATOR = """You are an orchestrator for {task}.

Custom parameter: {custom_param}

## Available Tools
- spawn_subagent: Delegate research or writing tasks
- verify_answer: Check your answer against the rubric
- submit_answer: Submit your final answer

## Workflow
1. Analyze the task
2. Execute using subagents
3. Verify your answer
4. Submit when verification passes
"""
```

### 4. Handle Mode-Specific Logic (Optional)

If your mode needs special handling in the harness, update `run_single()` in `verif/harness.py`:

```python
def run_single(
    self,
    task: Prompt,
    mode: str | None = None,
    # Add your mode's kwargs
    custom_param: str | None = None,
    ...
) -> RunResult:
    mode_name = mode or self.default_mode
    mode_config = get_mode(mode_name)
    
    mode_kwargs = {}
    
    # Handle your mode
    if mode_config.name == "my_mode":
        if not custom_param:
            raise ValueError("my_mode requires custom_param")
        mode_kwargs["custom_param"] = custom_param
    
    # ... rest of method
```

### 5. Use It

```python
harness = RLHarness(provider="gemini")
result = harness.run_single(
    task="Do something custom",
    mode="my_mode",
    custom_param="value",
)
```

---

## Existing Modes Reference

| Mode | Rubric Strategy | Key Tools | Use Case |
|------|-----------------|-----------|----------|
| `standard` | `create` | create_brief, create_rubric, verify_answer | General research/analysis |
| `plan` | `provided` | create_rubric, verify_answer | Structured execution with user plan |
| `explore` | `skip` | create_brief, verify_exploration | Divergent thinking, multiple approaches |
| `iterate` | `provided` | verify_answer | Refining existing work with feedback |

---

## Tool Definitions

Tools are defined in `verif/providers/base.py` in `TOOL_DEFINITIONS`. To add a new tool:

1. Add the definition to `TOOL_DEFINITIONS`:

```python
TOOL_DEFINITIONS = {
    # ... existing tools
    "my_tool": {
        "name": "my_tool",
        "description": "Does something useful",
        "parameters": {
            "type": "object",
            "properties": {
                "param1": {"type": "string", "description": "First param"},
            },
            "required": ["param1"],
        },
    },
}
```

2. Handle the tool call in `_execute_tool()` in `BaseProvider`:

```python
def _execute_tool(self, name: str, args: dict, ...) -> str:
    if name == "my_tool":
        return self._handle_my_tool(args["param1"])
    # ... existing handlers
```

3. Include it in your mode's `tools` list.
