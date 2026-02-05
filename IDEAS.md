# Ideas: Unexpected Things You Can Do

This SDK is built for knowledge work, but the primitives are flexible. Here are some unintuitive applications.

---

## Adversarial Red Teaming

Use **explore mode** to generate attack vectors against your own systems.

```python
result = harness.run_single(
    task="You are a malicious actor. Find 5 ways to exploit our authentication flow.",
    mode="explore",
    num_takes=5,
)
```

The verification step checks each attack is *distinct* and *plausible*. You get a structured threat model instead of a single response.

---

## Debate-Style Decision Making

Spawn subagents that argue *opposite* positions, then synthesize.

```python
PLAN = """
1. Spawn subagent: Argue strongly FOR the acquisition
2. Spawn subagent: Argue strongly AGAINST the acquisition  
3. Spawn subagent: Identify which arguments are weakest on each side
4. Synthesize a recommendation based on which side survives scrutiny
"""
```

The rubric checks that the final answer *engages with counterarguments*, not just picks a side.

---

## Self-Improving Prompts

Use the harness to optimize its own prompts.

```python
task = """
Here is a prompt I use for summarization: {current_prompt}

Run it on these 3 test cases. Analyze failures. 
Propose an improved prompt. Test the improved version.
Return the better prompt with evidence.
"""
```

The rubric checks the new prompt *actually performs better* on the test cases.

---

## Synthetic Data Generation with Quality Gates

Generate training data that passes verification.

```python
RUBRIC = """
Each generated example must:
- [ ] Be factually consistent (no internal contradictions)
- [ ] Match the target format exactly
- [ ] Not duplicate existing examples
- [ ] Cover an edge case not yet represented
"""

for _ in range(100):
    result = harness.run_single(
        task="Generate one new training example for customer support classification.",
        rubric=RUBRIC,
    )
    if "PASS" in result.history[-2].content:
        dataset.append(result.answer)
```

Failed verification = example discarded. You get a curated dataset.

---

## Document Archaeology

Feed in a large, messy document. Ask for structure.

```python
attachment = Attachment(
    content="legacy_spec.pdf",
    mime_type="application/pdf",
    preview="[200 page PDF from 2008]",
)

result = harness.run_single(
    prompt=[
        "Extract all requirements from this legacy spec. Flag contradictions.",
        attachment,
    ],
    mode="plan",
    plan="""
    1. Identify document sections
    2. Extract requirements per section
    3. Cross-reference for contradictions
    4. Output structured requirements.json
    """,
)
```

The rubric verifies *every* requirement is traceable to a page number.

---

## Automated Grant Writing

Grants have explicit rubrics. Use them.

```python
GRANT_RUBRIC = """
## Intellectual Merit (40%)
- [ ] Clear problem statement
- [ ] Novel approach justified
- [ ] Feasibility evidence

## Broader Impacts (30%)
- [ ] Societal benefits articulated
- [ ] Outreach plan included

## Budget Justification (30%)
- [ ] All items justified
- [ ] No prohibited expenses
"""

result = harness.run_single(
    task="Write an NSF CAREER proposal for AI-assisted scientific discovery.",
    rubric=GRANT_RUBRIC,
)
```

The model iterates until it passes the *actual* evaluation criteria.

---

## Dungeon Master

Run a tabletop RPG session with verified world consistency.

```python
WORLD_STATE = Attachment(
    content="world_state.json",
    preview='{"characters": [...], "locations": [...], "plot_threads": [...]}',
)

RUBRIC = """
- [ ] Response is consistent with world state
- [ ] NPC actions match their established motivations
- [ ] No retcons of established facts
- [ ] Advances at least one plot thread
"""

result = harness.run_single(
    prompt=["Player says: I try to persuade the guard to let us pass.", WORLD_STATE],
    rubric=RUBRIC,
)
```

Verification catches when the AI contradicts its own lore.

---

## Code Review with Teeth

Review code, but the rubric is your style guide.

```python
STYLE_GUIDE = Path("STYLE_GUIDE.md").read_text()

RUBRIC = f"""
Based on our style guide:
{STYLE_GUIDE}

The review must:
- [ ] Identify all style violations with line numbers
- [ ] Distinguish blocking vs. non-blocking issues
- [ ] Suggest specific fixes, not vague feedback
"""

result = harness.run_single(
    task=f"Review this PR:\n{pr_diff}",
    rubric=RUBRIC,
)
```

---

## Therapy Session Prep

Prepare for a difficult conversation by exploring scenarios.

```python
result = harness.run_single(
    task="""
    I need to give critical feedback to a direct report about missed deadlines.
    
    Generate 3 ways this conversation could go wrong, and how to recover from each.
    """,
    mode="explore",
    num_takes=3,
)
```

Each "take" is a failure mode + recovery strategy. Verification checks they're *distinct* scenarios.

---

## Contract Clause Extraction

Extract structured data from legal documents.

```python
RUBRIC = """
For each clause:
- [ ] Clause type identified (indemnification, liability, termination, etc.)
- [ ] Parties involved extracted
- [ ] Key obligations listed
- [ ] Unusual terms flagged
- [ ] Page/section reference included
"""

result = harness.run_single(
    prompt=["Extract all clauses from this contract.", contract_attachment],
    rubric=RUBRIC,
    enable_code=True,  # For structured JSON output
)
```

---

## Recursive Self-Critique

Ask the model to critique its own critique.

```python
# First pass
result1 = harness.run_single(task="Write a product strategy memo.")

# Second pass: critique
result2 = harness.run_single(
    task=f"Critique this memo. Be harsh.\n\n{result1.answer}",
)

# Third pass: critique the critique
result3 = harness.run_single(
    task=f"""
    Original: {result1.answer}
    Critique: {result2.answer}
    
    Which criticisms are valid? Which are nitpicking? 
    Produce a final memo addressing only the valid ones.
    """,
)
```

---

## Meeting Simulator

Simulate a meeting before it happens.

```python
ATTENDEES = """
- Sarah (CEO): Wants to cut costs
- Mike (Eng): Wants to hire 3 more engineers  
- Lisa (Product): Wants to delay launch for quality
"""

result = harness.run_single(
    task=f"""
    Simulate this meeting. Generate the likely dialogue.
    Then: what's the most likely outcome? What would change it?
    
    Attendees:
    {ATTENDEES}
    
    Agenda: Discuss Q3 priorities
    """,
    mode="explore",
    num_takes=2,  # Optimistic vs. pessimistic scenarios
)
```

---

## The Anti-Pattern Detector

Find bad patterns in your codebase by describing the *symptoms*.

```python
result = harness.run_single(
    task="""
    Search this codebase for signs of:
    - God objects (classes doing too much)
    - Shotgun surgery (one change requires touching 5+ files)
    - Feature envy (methods that use other classes more than their own)
    
    For each: file, line, severity, suggested fix.
    """,
    enable_bash=True,
)
```

---

## Competitive Intelligence

Structured analysis of a competitor.

```python
RUBRIC = """
## Required Sections
- [ ] Business model (how they make money)
- [ ] Product differentiation (what's unique)
- [ ] Pricing analysis (with tiers)
- [ ] Weaknesses (at least 3)
- [ ] Our advantages (be honest)

## Quality Checks
- [ ] All claims cite sources
- [ ] No unsupported speculation
- [ ] Actionable recommendations included
"""

result = harness.run_single(
    task="Competitive analysis of [Company X] vs. our product.",
    rubric=RUBRIC,
    enable_search=True,
)
```

---

## Reverse Engineering Rubrics

Given an output you like, generate the rubric that would produce it.

```python
GOOD_EXAMPLE = Path("excellent_report.md").read_text()

result = harness.run_single(
    task=f"""
    Here's an example of excellent work:
    
    {GOOD_EXAMPLE}
    
    Reverse-engineer the rubric. What criteria would someone need to follow 
    to produce work of this quality? Be specific and actionable.
    """,
)

# Now use that rubric for future tasks
future_result = harness.run_single(
    task="Write a similar report for Q4.",
    rubric=result.answer,
)
```

---

## The "Explain Like I'm 5" Verifier

Force simple explanations.

```python
RUBRIC = """
- [ ] No jargon (or jargon is immediately defined)
- [ ] Uses concrete analogies
- [ ] A 10-year-old could follow the logic
- [ ] Under 200 words
"""

result = harness.run_single(
    task="Explain how HTTPS encryption works.",
    rubric=RUBRIC,
)
```

Verification *actually checks* the criteria, not just vibes.

---

## Chained Refinement Across Modes

Use different modes for different phases.

```python
# Phase 1: Explore approaches
explore = harness.run_single(task=TASK, mode="explore", num_takes=3)

# Phase 2: Plan the best approach
plan = harness.run_single(
    task=f"Create a detailed plan for approach #2:\n{explore.answer}",
    mode="plan",
)

# Phase 3: Execute with strict rubric
final = harness.run_single(
    task=TASK,
    mode="plan", 
    plan=plan.answer,
    rubric=STRICT_RUBRIC,
)

# Phase 4: Iterate based on feedback
refined = harness.iterate(
    task=TASK,
    answer=final.answer,
    rubric=final.rubric,
    feedback="Make it more concise. Remove section 3.",
)
```

---

## Mode Composition: Research → Debate → Decide

Chain modes for complex decisions.

```python
# Phase 1: EXPLORE - Generate options
options = harness.run_single(
    task="What are our options for entering the European market?",
    mode="explore",
    num_takes=4,
)

# Phase 2: STANDARD - Deep research on top 2
research_1 = harness.run_single(
    task=f"Research feasibility of option 1:\n{options.answer.split('===')[0]}",
    enable_search=True,
)
research_2 = harness.run_single(
    task=f"Research feasibility of option 2:\n{options.answer.split('===')[1]}",
    enable_search=True,
)

# Phase 3: PLAN - Structured comparison
comparison = harness.run_single(
    task="Compare these two options and recommend one.",
    mode="plan",
    plan="""
    1. Summarize option 1 (strengths, weaknesses, risks)
    2. Summarize option 2 (strengths, weaknesses, risks)
    3. Define decision criteria
    4. Score each option against criteria
    5. Make recommendation with confidence level
    """,
    rubric="""
    - [ ] Both options fairly represented
    - [ ] Decision criteria explicit before scoring
    - [ ] Recommendation includes confidence level
    - [ ] Key risks acknowledged
    """,
)
```

---

## Parallel Research with Merge

Spawn subagents that research independently, then synthesize.

```python
# Orchestrator spawns 3 subagents in parallel, each researching different angles
# Then executes code to merge findings into structured output

result = harness.run_single(
    task="""
    Research the state of quantum computing in 2024.
    
    Spawn 3 parallel subagents:
    1. Technical progress (qubit counts, error rates, algorithms)
    2. Commercial landscape (companies, funding, products)
    3. Timeline predictions (expert opinions on milestones)
    
    After all complete, use execute_code to:
    - Parse each subagent's findings
    - Identify contradictions between sources
    - Generate a structured JSON summary
    - Save to quantum_report.json
    """,
    enable_search=True,
    enable_code=True,
)
```

The orchestrator coordinates parallel research and uses code to merge results—not possible with a single prompt.

---

## Data Pipeline: Scrape → Clean → Analyze → Visualize

End-to-end data workflow using orchestration.

```python
result = harness.run_single(
    task="""
    Analyze Y Combinator's latest batch.
    
    1. Search for YC W24 batch company list
    2. For each company (spawn subagents in batches of 5):
       - Find industry, funding, founders
    3. Use execute_code to:
       - Aggregate into pandas DataFrame
       - Calculate industry distribution
       - Generate matplotlib charts
       - Save to yc_analysis.png and yc_data.csv
    4. Write summary with embedded chart references
    """,
    enable_search=True,
    enable_code=True,
    mode="plan",
    plan="""
    Phase 1: Data Collection (parallel subagents)
    Phase 2: Data Processing (code execution)
    Phase 3: Visualization (code execution)
    Phase 4: Report Writing (synthesis)
    """,
)
```

Orchestrator manages the assembly line: subagents gather, code processes, final synthesis.

---

## Self-Healing Code Generation

Generate code, run it, fix errors automatically.

```python
result = harness.run_single(
    task="""
    Write a Python script that fetches Bitcoin price history 
    and calculates 30-day moving average.
    
    Process:
    1. Write initial script
    2. Execute it with execute_code
    3. If error: analyze traceback, fix code, retry
    4. Repeat until working (max 5 attempts)
    5. Save working script to btc_analysis.py
    
    The rubric only passes if the code actually runs.
    """,
    enable_code=True,
    rubric="""
    - [ ] Script executes without errors
    - [ ] Output contains actual price data
    - [ ] Moving average calculation is correct
    - [ ] Script saved to artifacts
    """,
)
```

The verification loop forces iteration until code works—not just looks right.

---

## Multi-Source Reconciliation

Cross-reference multiple sources to find truth.

```python
result = harness.run_single(
    task="""
    What is the actual market size for AI code assistants in 2024?
    
    1. Spawn 4 subagents, each searching different source types:
       - Analyst reports (Gartner, Forrester)
       - Press releases (company announcements)
       - Academic papers (market research)
       - News articles (tech journalism)
    
    2. Use execute_code to:
       - Extract all numeric estimates
       - Track source, date, methodology for each
       - Identify outliers and median
       - Calculate confidence interval
    
    3. Synthesize: what's the defensible range?
    """,
    enable_search=True,
    enable_code=True,
    rubric="""
    - [ ] At least 3 distinct source types consulted
    - [ ] All estimates include source attribution
    - [ ] Outliers explicitly discussed
    - [ ] Final range is justified, not just averaged
    """,
)
```

---

## Document Generation with Computed Sections

Generate documents where some sections require computation.

```python
FINANCIAL_DATA = Attachment(
    content="financials.csv",
    mime_type="text/csv",
    preview=Path("financials.csv").read_text()[:2000],
)

result = harness.run_single(
    prompt=[
        """
        Generate a quarterly investor update.
        
        1. Use execute_code to analyze the attached financials:
           - Calculate QoQ growth rates
           - Identify top/bottom performing segments
           - Project next quarter (simple linear)
        
        2. Spawn subagents for narrative sections:
           - Market conditions (with search)
           - Product updates (from attached data)
           - Competitive landscape (with search)
        
        3. Assemble final document with:
           - Computed metrics inline
           - Charts saved to artifacts/
           - Markdown formatted for export
        """,
        FINANCIAL_DATA,
    ],
    enable_search=True,
    enable_code=True,
)
```

Mixes computation (code) with research (subagents) into a coherent document.

---

## Iterative Refinement with External Feedback

Loop with external validation at each step.

```python
harness = RLHarness(
    provider="gemini",
    enable_ask_user=True,
    enable_code=True,
    on_event=lambda e: handle_user_questions(e, harness),
)

result = harness.run_single(
    task="""
    Design a database schema for an e-commerce platform.
    
    Process:
    1. Generate initial schema (entities, relationships)
    2. Use ask_user to present schema and get feedback
    3. Revise based on feedback
    4. Use execute_code to generate SQL CREATE statements
    5. Use ask_user to confirm SQL looks correct
    6. Save final schema to schema.sql
    
    Iterate until user approves.
    """,
)
```

Orchestrator manages the feedback loop—ask, revise, ask again.

---

## Competitive Teardown with Artifacts

Deep analysis producing multiple output files.

```python
result = harness.run_single(
    task="""
    Teardown analysis of Notion vs Coda vs Obsidian.
    
    For each product, spawn subagent to research:
    - Pricing and packaging
    - Core features (list top 10)
    - Integration ecosystem
    - User sentiment (from reviews)
    
    Then use execute_code to:
    1. Build feature comparison matrix (pandas)
    2. Generate radar chart of capabilities (matplotlib)
    3. Calculate value scores (features / price)
    4. Export to:
       - comparison_matrix.csv
       - radar_chart.png
       - teardown_report.md (full narrative)
    """,
    enable_search=True,
    enable_code=True,
)

# Result includes multiple artifacts
print(result.artifacts)  # ['comparison_matrix.csv', 'radar_chart.png', 'teardown_report.md']
```

---

## Knowledge Base Builder

Build a structured knowledge base from unstructured research.

```python
result = harness.run_single(
    task="""
    Build a knowledge base on CRISPR gene editing.
    
    1. Spawn subagents to research (parallel):
       - Core technology (how it works)
       - Key players (companies, researchers)
       - Applications (medicine, agriculture, etc.)
       - Controversies (ethics, regulation)
       - Recent breakthroughs (2023-2024)
    
    2. Use execute_code to structure into:
       - Entities (with unique IDs)
       - Relationships (entity A relates to B)
       - Claims (with source citations)
       - Export as knowledge_graph.json
    
    3. Generate summary.md linking to entities
    """,
    enable_search=True,
    enable_code=True,
)
```

Transforms freeform research into structured, queryable data.

---

## Monte Carlo Analysis

Run simulations to stress-test a decision.

```python
result = harness.run_single(
    task="""
    Should we launch in Q1 or Q2?
    
    1. Research key variables:
       - Competitor launch timelines
       - Market seasonality
       - Resource availability
       - Spawn subagents for each
    
    2. Use execute_code to run Monte Carlo:
       - Define probability distributions for each variable
       - Simulate 1000 scenarios for Q1 launch
       - Simulate 1000 scenarios for Q2 launch
       - Calculate expected value and variance for each
    
    3. Recommend based on risk tolerance:
       - If risk-averse: which has lower variance?
       - If risk-seeking: which has higher upside?
    
    Save simulation results to monte_carlo.csv
    """,
    enable_search=True,
    enable_code=True,
    rubric="""
    - [ ] At least 3 variables modeled with distributions
    - [ ] 1000+ simulations per scenario
    - [ ] Recommendation accounts for risk preference
    - [ ] Simulation code is reproducible
    """,
)
```

---

## Codebase Audit Pipeline

Analyze a codebase across multiple dimensions.

```python
result = harness.run_single(
    task="""
    Audit the codebase at ./src/
    
    1. Use search_files to inventory:
       - File count by language
       - Total lines of code
       - Directory structure
    
    2. Spawn parallel subagents for:
       - Security: search for common vulnerabilities
       - Complexity: find functions over 50 lines
       - Dependencies: check for outdated packages
       - Tests: calculate coverage estimate
    
    3. Use execute_code to:
       - Aggregate findings into scores
       - Generate audit_report.json with structured findings
       - Create summary dashboard in audit.html
    
    4. Synthesize recommendations prioritized by severity
    """,
    enable_bash=True,
    enable_code=True,
)

---

## Your Idea Here

The verification loop is general. If you can write a rubric for it, you can automate it.

Custom modes let you encode *any* workflow. Mode composition lets you chain them.

What would you build?
