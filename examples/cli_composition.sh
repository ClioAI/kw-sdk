#!/usr/bin/env bash
#
# CLI Composition Examples
#
# Shows how to use `verif` CLI with unix tools for multi-stage workflows.
# These patterns work identically whether you use `python cli.py` or the
# built binary `./dist/verif`.
#
# Prerequisites:
#   export GEMINI_API_KEY=...   (or OPENAI_API_KEY / ANTHROPIC_API_KEY)
#   uv pip install -e ".[dev]"
#
# Replace `python cli.py` with `./dist/verif` after running `python build.py`.

set -euo pipefail
VERIF="python cli.py"

# ─────────────────────────────────────────────────────────────────────────────
# 1. BASIC: run a task, extract answer with jq
# ─────────────────────────────────────────────────────────────────────────────

echo "=== 1. Basic run ==="

$VERIF run \
  --provider gemini \
  --task "What are the three laws of thermodynamics? One sentence each." \
  --output json | jq -r .answer

# ─────────────────────────────────────────────────────────────────────────────
# 2. STREAMING: events to stderr, result to stdout (pipe-friendly)
# ─────────────────────────────────────────────────────────────────────────────

echo "=== 2. Streaming (events hidden, answer piped) ==="

$VERIF run \
  --provider gemini \
  --task "Summarize the CAP theorem in 3 bullet points" \
  --stream \
  --output text 2>/dev/null

# To see events instead:
#   verif run ... --stream --output text 2>&1 >/dev/null | jq .

# ─────────────────────────────────────────────────────────────────────────────
# 3. PLAN MODE: task and plan from files
# ─────────────────────────────────────────────────────────────────────────────

echo "=== 3. Plan mode from files ==="

TASK_FILE=$(mktemp)
PLAN_FILE=$(mktemp)
trap 'rm -f "$TASK_FILE" "$PLAN_FILE"' EXIT

cat > "$TASK_FILE" <<'EOF'
Write a production incident postmortem for a 47-minute database outage
affecting 15% of customers. Target audience: engineering leadership.
EOF

cat > "$PLAN_FILE" <<'EOF'
1. Write executive summary (what, impact, resolution)
2. Document timeline with timestamps
3. Root cause analysis using 5 Whys
4. What went well / what to improve
5. Action items with owners and due dates
EOF

$VERIF run \
  --provider gemini \
  --mode plan \
  --task-file "$TASK_FILE" \
  --plan-file "$PLAN_FILE" \
  --enable-search \
  --output json | jq -r .answer > postmortem.md

echo "Saved to postmortem.md ($(wc -c < postmortem.md) bytes)"

# ─────────────────────────────────────────────────────────────────────────────
# 4. EXPLORE → SELECT → EXECUTE pipeline (end-to-end composition)
#
#    Same workflow as examples/end_to_end_workflow.py, but pure shell.
# ─────────────────────────────────────────────────────────────────────────────

echo "=== 4. Explore → Select → Execute ==="

TASK="Design a rate limiter for an API gateway handling 50K req/s. \
Support per-user limits, per-endpoint limits, graceful degradation, and monitoring."

# Stage 1: Explore
echo "  [1/3] Exploring approaches..."
EXPLORE_JSON=$($VERIF run \
  --provider gemini \
  --mode explore \
  --task "$TASK" \
  --enable-search \
  --output json)

EXPLORE_ANSWER=$(echo "$EXPLORE_JSON" | jq -r .answer)

# Stage 2: Select best approach (use standard mode as an LLM call)
echo "  [2/3] Selecting best approach..."
SELECT_JSON=$($VERIF run \
  --provider gemini \
  --task "You are a senior architect. Given these approaches, pick the best one and output an execution plan and rubric.

## Approaches
$EXPLORE_ANSWER

## Output exactly:
### PLAN
1. step...

### RUBRIC
- [ ] criterion..." \
  --output json)

SELECT_ANSWER=$(echo "$SELECT_JSON" | jq -r .answer)

# Extract plan and rubric into temp files
EXEC_PLAN=$(mktemp)
EXEC_RUBRIC=$(mktemp)
trap 'rm -f "$TASK_FILE" "$PLAN_FILE" "$EXEC_PLAN" "$EXEC_RUBRIC"' EXIT

echo "$SELECT_ANSWER" | sed -n '/^### PLAN/,/^### RUBRIC/{/^### /d;p}' > "$EXEC_PLAN"
echo "$SELECT_ANSWER" | sed -n '/^### RUBRIC/,$ {/^### RUBRIC/d;p}' > "$EXEC_RUBRIC"

# Stage 3: Execute with selected plan
echo "  [3/3] Executing with selected plan..."
$VERIF run \
  --provider gemini \
  --mode plan \
  --task "$TASK" \
  --plan-file "$EXEC_PLAN" \
  --rubric-file "$EXEC_RUBRIC" \
  --output json | jq -r .answer > design_doc.md

echo "  Done → design_doc.md ($(wc -c < design_doc.md) bytes)"

# ─────────────────────────────────────────────────────────────────────────────
# 5. ITERATE: refine an existing answer
# ─────────────────────────────────────────────────────────────────────────────

echo "=== 5. Iterate on an answer ==="

# Start with the postmortem from step 3
$VERIF iterate \
  --provider gemini \
  --task "Production incident postmortem for database outage" \
  --answer-file postmortem.md \
  --rubric "- [ ] Has executive summary\n- [ ] Has timeline\n- [ ] Has action items" \
  --feedback "Add a 3-year cost projection for the proposed fixes. The CFO will be reading this." \
  --output json | jq -r .answer > postmortem_v2.md

echo "Refined → postmortem_v2.md ($(wc -c < postmortem_v2.md) bytes)"

# ─────────────────────────────────────────────────────────────────────────────
# 6. BATCH: run over a set of tasks (one per line)
# ─────────────────────────────────────────────────────────────────────────────

echo "=== 6. Batch mode ==="

TASKS_FILE=$(mktemp)
cat > "$TASKS_FILE" <<'EOF'
Explain the difference between TCP and UDP in 2 sentences
What is the CAP theorem? One paragraph.
Compare REST vs GraphQL for mobile backends
EOF

i=0
while IFS= read -r line; do
  i=$((i + 1))
  echo "  [$i] $line"
  $VERIF run \
    --provider gemini \
    --task "$line" \
    --output json >> batch_results.jsonl
done < "$TASKS_FILE"

echo "  Results → batch_results.jsonl ($(wc -l < batch_results.jsonl) lines)"

# ─────────────────────────────────────────────────────────────────────────────
# 7. CROSS-PROVIDER: same task, compare outputs
# ─────────────────────────────────────────────────────────────────────────────

echo "=== 7. Cross-provider comparison ==="

COMPARE_TASK="What are the pros and cons of microservices? 5 bullet points."

for provider in gemini openai anthropic; do
  echo "  Running $provider..."
  $VERIF run \
    --provider "$provider" \
    --task "$COMPARE_TASK" \
    --output json | jq --arg p "$provider" '{provider: $p, answer: .answer}'
done | jq -s '.' > comparison.json

echo "  Results → comparison.json"

# ─────────────────────────────────────────────────────────────────────────────
# 8. LIST MODES
# ─────────────────────────────────────────────────────────────────────────────

echo "=== 8. Available modes ==="
$VERIF modes

echo ""
echo "Done. All examples completed."
