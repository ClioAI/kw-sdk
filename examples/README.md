# SDK Examples

This folder contains working examples for each execution mode.

## Prerequisites

```bash
# 1. Create and activate virtual environment
uv venv
source .venv/bin/activate

# 2. Install dependencies
uv pip install -r requirements.txt

# 3. Create .env file with API keys
echo "GEMINI_API_KEY=your_key_here" > .env
echo "OPENAI_API_KEY=your_key_here" >> .env
```

## Examples

| File | Mode | Description |
|------|------|-------------|
| `standard_mode.py` | Standard | Basic task with auto rubric |
| `standard_with_rubric.py` | Standard | **Acceptance criteria → LLM-generated rubric → Execute** |
| `standard_with_search.py` | Standard | Research task with web search |
| `plan_mode.py` | Plan | User-defined plan and rubric |
| `plan_mode_no_rubric.py` | Plan | User-defined plan, auto rubric |
| `explore_mode.py` | Explore | Creative task with multiple takes |
| `with_files.py` | Standard | Multimodal prompt with file attachment |
| `with_streaming.py` | Standard | Real-time event streaming |
| `with_code_execution.py` | Standard | Python code execution for artifacts |
| `end_to_end_workflow.py` | All | **Complete pipeline: Explore → Select → Execute** |

## Running Examples

```bash
cd examples
python standard_mode.py
python plan_mode.py
python explore_mode.py
```

## Key Differences Between Modes

### Standard Mode
- **Setup**: Minimal - just provider config
- **Rubric**: Auto-created during execution
- **Use when**: General tasks, Q&A, research

### Plan Mode  
- **Setup**: Requires `plan` parameter (rubric optional)
- **Rubric**: User-provided OR auto-created
- **Use when**: Complex tasks needing structured execution

### Explore Mode
- **Setup**: Optional `num_takes` hint
- **Rubric**: Uses quality checklist (not accuracy rubric)
- **Use when**: Creative tasks, brainstorming, multiple perspectives

---

## End-to-End Pipeline

The `end_to_end_workflow.py` example shows a complete multi-stage workflow:

```
┌─────────────────────────────────────────────────────────┐
│  EXPLORE MODE                                           │
│  → Generate 3+ distinct approaches                      │
│  → Each with assumptions & counterfactuals              │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│  SELECTION (Gemini provider.generate() call)            │
│  → Analyze all takes                                    │
│  → Pick best approach + synthesize plan                 │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│  PLAN MODE                                              │
│  → Execute the selected approach                        │
│  → Verify against rubric                                │
│  → Produce final deliverable                            │
└─────────────────────────────────────────────────────────┘
```

**Key pattern**: Use `provider.generate()` directly between harness runs to make decisions, synthesize, or transform outputs.
