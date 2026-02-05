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
- Which tools are available
- Which prompts to use
- How rubrics are handled
- What kwargs get passed to prompts

> **Example:** See [examples/custom_mode_bizarro.py](examples/custom_mode_bizarro.py) for a complete working example.

### Runtime Registration (SDK Usage)

When using the SDK as a dependency, register modes at runtime by importing and modifying the registries:

```python
from verif import RLHarness, ProviderConfig
from verif.config import ModeConfig
from verif.modes import MODES
from verif.providers.base import PROMPTS

# 1. Define your orchestrator prompt
MY_ORCHESTRATOR = """You are a specialized orchestrator for {task}.

## Your Custom Workflow
1. Do step one
2. Do step two
3. Verify and submit

## Tools
- spawn_subagent: Delegate work
- verify_answer: Check against rubric
- submit_answer: Submit final answer
"""

# 2. Define the mode config
MY_MODE = ModeConfig(
    name="my_mode",
    orchestrator_prompt="MY_ORCHESTRATOR",  # Key in PROMPTS dict
    brief_prompt=None,                       # Optional
    tools=["spawn_subagent", "verify_answer", "submit_answer"],
    verification_tool="verify_answer",
    rubric_strategy="create",  # "create" | "provided" | "skip"
    has_pre_execution=False,
    prompt_kwargs=[],
)

# 3. Register at runtime (before creating harness)
PROMPTS["MY_ORCHESTRATOR"] = MY_ORCHESTRATOR
MODES["my_mode"] = MY_MODE

# 4. Use it
harness = RLHarness(provider="gemini")
result = harness.run_single(task, mode="my_mode")
```

### ModeConfig Reference

```python
ModeConfig(
    name="my_mode",
    
    # Prompt keys (must exist in PROMPTS dict)
    orchestrator_prompt="MY_ORCHESTRATOR",
    brief_prompt="MY_BRIEF",  # Optional: for create_brief tool
    
    # Tools available to orchestrator
    tools=[
        "create_brief",      # Formalize task requirements
        "create_rubric",     # Generate evaluation criteria
        "spawn_subagent",    # Delegate subtasks
        "search_web",        # Web search (if enable_search=True)
        "search_files",      # File access (if enable_bash=True)
        "execute_code",      # Python REPL (if enable_code=True)
        "ask_user",          # User clarification (if enable_ask_user=True)
        "verify_answer",     # Standard verification
        "verify_exploration",# Explore mode verification
        "submit_answer",     # Final submission
    ],
    
    # Verification
    verification_tool="verify_answer",  # or "verify_exploration" or None
    
    # Rubric strategy
    rubric_strategy="create",
    # - "create": Orchestrator calls create_rubric during execution
    # - "provided": Caller provides rubric, or orchestrator creates if missing
    # - "skip": No rubric (uses custom verifier like explore mode)
    
    # Pre-execution phase (for future use)
    has_pre_execution=False,
    
    # Kwargs formatted into orchestrator prompt via {key}
    prompt_kwargs=["custom_param"],  # Passed from run_single()
)
```

### Creating the Orchestrator Prompt

Your prompt should:
1. Describe the workflow clearly
2. List available tools with usage guidance
3. End with clear success criteria

```python
MY_ORCHESTRATOR = """You are an orchestrator for {task}.

## Available Tools
- spawn_subagent: Delegate research or writing tasks
- verify_answer: Check your answer against the rubric
- submit_answer: Submit your final answer

## Workflow
1. Analyze the task
2. Execute using subagents
3. Verify your answer
4. Submit when verification passes

IMPORTANT: Call tools directly. Do not describe what you will do.
"""

# Register before use
PROMPTS["MY_ORCHESTRATOR"] = MY_ORCHESTRATOR
```

### Modes Without Verification

For modes that skip verification (like fact-checking where the task *is* verification):

```python
FACT_CHECK_MODE = ModeConfig(
    name="fact_check",
    orchestrator_prompt="FACT_CHECKER",
    tools=["search_web", "spawn_subagent", "submit_answer"],
    verification_tool=None,  # No verification step
    rubric_strategy="skip",
    has_pre_execution=False,
    prompt_kwargs=[],
)
```

### Passing Custom Parameters

If your mode needs custom parameters, include them in `prompt_kwargs` and pass via `run_single()`:

```python
# Mode config
MY_MODE = ModeConfig(
    name="my_mode",
    orchestrator_prompt="MY_ORCHESTRATOR",  # Contains {custom_param}
    tools=["spawn_subagent", "submit_answer"],
    prompt_kwargs=["custom_param"],  # Will be formatted into prompt
    ...
)

# Prompt with placeholder
MY_ORCHESTRATOR = """You are working on {task}.
Target audience: {custom_param}
..."""

# Usage - pass as kwarg
result = harness.run_single(
    task="Write a report",
    mode="my_mode",
    custom_param="technical executives",
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

## Adding Custom Capabilities

**You don't need to define custom tools.** The SDK provides `execute_code`—use it to call your own Python functions.

Instead of building tool infrastructure, write tested utility functions and let the model call them via code execution. This is simpler, more testable, and doesn't require modifying the SDK.

### Pattern: Utilities + Documentation

```python
# 1. Write your utility (utils/crm.py)
def get_customer(customer_id: str) -> dict:
    """Fetch customer from CRM."""
    response = requests.get(f"{CRM_API}/customers/{customer_id}")
    return response.json()

def update_customer(customer_id: str, data: dict) -> dict:
    """Update customer record."""
    response = requests.patch(f"{CRM_API}/customers/{customer_id}", json=data)
    return response.json()
```

```python
# 2. Document it for the model
CRM_DOCS = """
## Available: CRM Utilities

```python
from utils.crm import get_customer, update_customer

get_customer("cust_123")
# Returns: {"id": "cust_123", "name": "Acme Corp", "tier": "enterprise"}

update_customer("cust_123", {"tier": "premium"})
# Returns: {"id": "cust_123", "name": "Acme Corp", "tier": "premium"}
```
"""
```

```python
# 3. Include docs in task
harness = RLHarness(provider="gemini", enable_code=True)

result = harness.run_single(f"""
Update customer cust_456 to premium tier and verify the change.

{CRM_DOCS}
""")
```

The model imports your functions and calls them. No tool registration needed.

### Why This Works Better

| Approach | Pros | Cons |
|----------|------|------|
| Custom tool definition | Native to model | Requires SDK modification, hard to test |
| **Utilities + execute_code** | Testable, reusable, no SDK changes | Slightly more tokens for docs |

### When You Actually Need Custom Tools

If you're forking the SDK and need deeply integrated tools (e.g., a new verification method), see the source in `verif/providers/base.py`:
- `TOOL_DEFINITIONS`: JSON schemas for tools
- `_execute_tool()`: Handler dispatch

But for most use cases, `execute_code` + documented utilities is the right pattern.

See [TOOL_CALLING_GUIDE.md](TOOL_CALLING_GUIDE.md) for the full philosophy and examples.
