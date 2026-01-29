# Performance Test: Compaction + Parallelization

**Total Time**: 174.61s
**Start**: 2026-01-14T15:19:05.678093
**End**: 2026-01-14T15:22:00.287901

## Result

### Task
What do the paternal genes contribute to the developing brain?

### Answer
Each parent contributes about **half of the embryo’s nuclear DNA**, and for **most genes both the maternal and paternal copies are used** during brain development. A notable exception is **genomic imprinting**, where a small set of genes is epigenetically “tagged” so that only the copy from one parent is switched on. Many **paternally expressed (imprinted) genes** are especially active in the **placenta** and tend to promote placental growth and nutrient transfer, increasing fetal resources that support overall growth, including the developing brain. Some paternally expressed imprinted genes are also active **in the brain itself**, influencing processes like neural proliferation, synapse formation, and behaviors such as feeding and arousal. By contrast, many maternally expressed imprinted genes often act as growth “brakes,” and genetic effects interact with the prenatal environment (maternal health, nutrition, hormones, stress).

### Rubric
1) **[must] Output length & structure**
   - Is the response a single paragraph **or** clearly written as **4–6 sentences** total?
   - Is the response approximately **120–200 words** (verifiable by word count)?
   - Does the response avoid headings, lists, or multiple paragraphs?

2) **[must] Equal genomic contribution baseline**
   - Does the response explicitly state that **both parents contribute ~half the DNA/genome**?
   - Does it clearly convey that **most genes are expressed from both parents** (i.e., biparental expression is the norm)?

3) **[must] One-sentence definition of imprinting**
   - Does the response include **exactly one sentence** that defines “imprinting” in plain language?
   - Does that definition state (in any wording) that imprinting is a **parent-of-origin effect** where **one parent’s copy is preferentially expressed/silenced**?

4) **[must] Imprinting framed as exception, limited subset**
   - Does the response explicitly state or clearly imply that imprinting affects **only a small subset** of genes (i.e., it is an exception)?
   - Does it avoid implying imprinting is the default for gene expression?

5) **[must] Paternal imprinted genes: placenta/resource allocation pathway**
   - Does the response state that **paternally expressed imprinted genes** often promote **fetal/placental growth or resource demand**?
   - Does it explicitly connect this to the **placenta** (e.g., nutrient transfer and/or endocrine/hormonal signaling)?
   - Does it clearly link this placental/resource allocation effect to **downstream brain growth/developmental timing** (a causal chain, not just a list)?

6) **[must] Paternal imprinted genes: direct brain/behavior roles**
   - Does the response state that **some** paternally expressed imprinted genes act **directly in the developing brain** (not only via placenta)?
   - Does it mention at least **two** of the following outcome domains (high-level): **neural proliferation/brain size**, **synapse development**, **feeding/suckling**, **sleep/arousal**, **cognition**, **social behavior**?

7) **[must] Maternal contrast: imprinted genes + broader maternal influences**
   - Does the response include **one sentence** that contrasts maternal contributions (not necessarily starting with “maternal”)?
   - In that sentence, does it mention (a) **maternally expressed imprinted genes** often bias toward **growth restraint/energy conservation** (or equivalent wording) **and** (b) non-genetic maternal influences such as **uterine/gestational environment, placental physiology, maternal health, or caregiving**?

8) **[must] Non-misleading importance framing**
   - Does the response explicitly avoid claiming or implying that **paternal genes are more important** than maternal genes for brain development?
   - Does it avoid implying paternal genes **only** affect the placenta (i.e., acknowledges both indirect and direct routes)?

9) **[must] Non-deterministic, interaction-aware phrasing**
   - Does the response include a clear hedge that effects are **probabilistic/not deterministic** (e.g., “influences,” “can,” “tends to,” “on average”)?
   - Does it mention that outcomes **interact with environment** (gestational and/or postnatal), without presenting a single-cause explanation?

10) **[must] Plain-language accessibility**
   - Is jargon minimal and, where present (e.g., “placenta,” “endocrine”), is it explained in simple terms or used in an immediately understandable way?
   - Is the tone neutral and explanatory (no advocacy, blame, or sensational framing)?

11) **[must] Avoids “genes vs parenting” confusion**
   - Does the response avoid equating **genetic contributions** with **parenting quality** or social fatherhood (i.e., no implication that paternal behavior is genetically pre-set or that “dad matters more” socially)?
   - Does it keep “paternal” clearly about **genetic parent-of-origin** rather than interpersonal roles?

12) **[good_to_have] Expert reframing**
   - Does the response explicitly reframe the topic as **“parent-of-origin effects”** (or equivalent) to prevent “paternal vs maternal” misconceptions?

13) **[good_to_have] Clear causal chain in one pass**
   - Does the response present a coherent causal sequence resembling: **paternal imprinting → placental strategy/hormones → fetal energy supply → brain growth/developmental timing/behavior**, without deep molecular detail?

14) **[good_to_have] Balanced symmetry statement**
   - Does the response explicitly note that maternal imprinted genes can also **directly affect neurodevelopment**, not only via growth restraint?

15) **[good_to_have] Optional credibility anchor (minimal)**
   - If imprinting disorders are mentioned, is it limited to **one short line** and used only as evidence that imprinting matters (no deep clinical/disease focus)?

16) **[ideal] Internal coherence & no contradictions**
   - Are there no internal contradictions (e.g., claiming both “most genes are imprinted” and “imprinting is rare”)?
   - Are paternal/maternal effects described with “often/tend to” language rather than absolute claims?

17) **[ideal] Tight, readable sentence-level clarity**
   - Can each sentence be read independently without ambiguous pronouns (e.g., “this/it” clearly refers to imprinting or placenta)?
   - Does the paragraph flow logically: baseline equality → imprinting definition → paternal imprinted roles (placenta then brain) → maternal contrast/environment?

18) **[ideal] Common failure modes explicitly avoided (negative checks)**
   - Does the response avoid any of the following: “paternal DNA builds the brain,” “maternal DNA only nurtures,” “genes determine behavior,” or “placenta is controlled only by the father” (or close paraphrases)?
   - Does it avoid heavy molecular pathway detail (e.g., methylation cascades, specific signaling pathways) beyond what a general audience needs?

---

## Tool Execution Timing (Granular)

| Start | End | Duration | Thread | Tool |
|-------|-----|----------|--------|------|
|   3.45s |  18.09s | 14.64s | ThreadPoolExecutor-0_0 | create_brief |
|  28.62s |  56.02s | 27.40s | ThreadPoolExecutor-1_0 | create_rubric |
|  28.62s |  67.06s | 38.44s | ThreadPoolExecutor-1_1 | spawn_subagent |
|  28.62s |  74.18s | 45.55s | ThreadPoolExecutor-1_2 | spawn_subagent |
|  28.63s | 126.48s | 97.86s | ThreadPoolExecutor-1_3 | search_web |
| 132.31s | 150.43s | 18.12s | ThreadPoolExecutor-2_0 | verify_answer |
| 155.44s | 172.64s | 17.20s | ThreadPoolExecutor-3_0 | verify_answer |
| 174.61s | 174.61s |  0.00s | ThreadPoolExecutor-4_0 | submit_answer |

## Event Timeline

| Elapsed | Type | Preview |
|---------|------|--------|
|   0.00s | SYSTEM | Task: What do the paternal genes contribute to the developin |
|   0.00s | USER | What do the paternal genes contribute to the developing brai |
|   0.00s | SYSTEM | You are a task orchestrator. You MUST use tools to complete  |
|   3.45s | TOOL_CALL | create_brief({"task":"Answer the question: 'What do the pate |
|  18.09s | TOOL_RESPONSE | create_brief -> ## Brief: Explain paternal gene contribution |
|  28.62s | TOOL_CALL | create_rubric({"brief":"## Brief: Explain paternal gene cont |
|  28.62s | TOOL_CALL | spawn_subagent({"prompt":"Draft a concise general-audience e |
|  28.62s | TOOL_CALL | spawn_subagent({"prompt":"Provide scientific accuracy check: |
|  28.62s | TOOL_CALL | search_web({"query":"paternally expressed imprinted genes pl |
| 126.48s | TOOL_RESPONSE | create_rubric -> Rubric created. |
| 126.48s | TOOL_RESPONSE | spawn_subagent -> Genomic imprinting is an unusual kind of g |
| 126.48s | TOOL_RESPONSE | spawn_subagent -> ## 1) Baseline reality: maternal and pater |
| 126.48s | TOOL_RESPONSE | search_web -> Paternally expressed imprinted genes (PEGs) ar |
| 132.31s | TOOL_CALL | verify_answer({"answer":"In humans, the father’s DNA provide |
| 150.43s | TOOL_RESPONSE | verify_answer -> 1) Output length & structure: **Satisfied.* |
| 155.44s | TOOL_CALL | verify_answer({"answer":"Each parent contributes about **hal |
| 172.64s | TOOL_RESPONSE | verify_answer -> 1) Output length & structure: **Satisfied.* |
| 174.61s | TOOL_CALL | submit_answer({"answer":"Each parent contributes about **hal |
| 174.61s | TOOL_RESPONSE | submit_answer -> SUBMITTED |

---

# Execution Trace

### 1. ⚙️ SYSTEM
```
Task: What do the paternal genes contribute to the developing brain?...
```

### 2. 📝 USER
```
What do the paternal genes contribute to the developing brain?
```

### 3. ⚙️ SYSTEM
```
You are a task orchestrator. You MUST use tools to complete tasks - never output text describing what you will do.

## CRITICAL RULES
- NEVER say "I will call X" - just call X immediately
- NEVER output your answer as text - use submit_answer(answer)
- ALWAYS use function calls, not text descriptions of actions

## PARALLEL EXECUTION
Tools execute in parallel when you call multiple in one turn. Maximize parallelism:
- BATCH independent tool calls together - don't call them one at a time
- spawn_subagent: Call 2-4 subagents simultaneously for different subtasks
- search_web: Call multiple searches at once for different queries
- search_files: Read multiple files in one turn
- execute_code: Call sequentially (shared state)

Example - GOOD (parallel):
  create_rubric(brief), spawn_subagent("research X"), spawn_subagent("research Y"), search_web("Z")
Example - BAD (sequential):
  create_rubric(brief) → wait → spawn_subagent("research X") → wait → spawn_subagent("research Y")

## Workflow
1. If files are attached without preview: call search_files FIRST to understand content
2. create_brief(task + file insights) - formalize requirements
3. create_rubric(brief) + work on task IN PARALLEL - rubric runs alongside spawn_subagent/search calls
4. verify_answer(answer) - check against rubric, get PASS/FAIL (rubric ready by now)
   - **CRITICAL**: Verify the CONTENT first, NOT the file creation. Pass the content to verify_answer(content) not "I have created the file".
   - If the task is to create a file, DO NOT create it until you get a PASS on the content.
5. If FAIL, improve and verify again
6. If PASS, and the task requires a file, create it now using execute_code.
7. submit_answer(answer) - submit final answer after PASS

## Tool Selection Guide

| Need | Tool | Parallel? |
|------|------|-----------|
| Set rubric | create_rubric(brief) | YES - with work below |
| Read attached file | search_files(query, path) | YES - batch multiple |
| Web research | search_web(query) | YES - batch multiple |
| Reasoning/synthesis | spawn_subagent(prompt) | YES - batch 2-4 |
| Calculations/charts/save files | execute_code(code) | NO - sequential |
| Check answer | verify_answer(content) | NO - needs rubric |
| Submit | submit_answer(answer) | NO - after PASS |

## Tools
- create_brief(task): Formalize task. Call first (after reading files if attached without preview).
- create_rubric(brief): Create rubric. Call after brief. CAN RUN IN PARALLEL with spawn_subagent/search calls.
- spawn_subagent(prompt): Delegate subtasks. Always have multiple subagents to increase your coverage and write a better article. DO NOT DELEGATE the entire task to one subagent. Create subtasks. ATLEAST TWO. CALL THEM IN PARALLEL. Subagents have web search if enabled. NO file access - for file tasks, YOU read with search_files first, then pass content to subagents.
- search_web(query): Search web and fetch URL content (if enabled). Returns summary + sources. CALL MULTIPLE IN PARALLEL for different queries.
- search_files(query, path): Read or search local files (if enabled). Returns summary. CALL MULTIPLE IN PARALLEL for different files/searches.
- execute_code(code): Run Python code for calculations, data processing, creating files (xlsx, csv, charts). Variables persist across calls - call sequentially. (if enabled).
- verify_answer(answer): Check answer. Returns PASS/FAIL. Pass the FULL CONTENT to be verified.
- submit_answer(answer): Submit final. Only after PASS.

Note: search_web and search_files are subagents that return summaries to keep context clean.

DO NOT output text about calling tools. CALL THE TOOLS DIRECTLY.
```

### 4. 🔧 TOOL_CALL
```
create_brief({"task":"Answer the question: 'What do the paternal genes contribute to the developing brain?' Provide a concise, accurate explanation appropriate for a general audience, touching on known roles of paternally expressed (imprinted) genes in neurodevelopment, e.g., placental growth, resource allocation, neural growth/behavior, and contrast with maternal gene contributions briefly."})
```

### 5. 📥 TOOL_RESPONSE
```
create_brief -> ## Brief: Explain paternal gene contributions to developing brain (general audience)

### 1) Core objective  
Deliver a clear, accurate, non-misleading explanation of what paternal genes contribute to brain development, emphasizing that paternal and maternal genomes both provide ~half the DNA, while a small subset of **imprinted, paternally expressed genes** have outsized effects on **placental function, fetal resource allocation, and downstream brain growth/behavior**.

### 2) Key requirements & constraints  
- **Audience:** General public; plain language; minimal jargon; define “imprinting” succinctly.  
- **Scientific accuracy:**  
  - State that **most genes are expressed from both parents**; imprinting is an **exception** involving parent-of-origin expression.  
  - Explain that paternally expressed imprinted genes often promote **growth/resource demand** via the **placenta** (nutrient transfer, endocrine signals), influencing fetal and brain development.  
  - Include known neurodevelopmental roles: **neural proliferation/brain size, synapse development, feeding/suckling, sleep/arousal, cognition/social behavior** (high-level, not exhaustive).  
  - Briefly contrast maternal contributions: maternal expressed imprinted genes often bias toward **growth restraint/energy conservation** and also directly affect neurodevelopment; additionally note **maternal environment** (uterus, placenta, caregiving) shapes outcomes.  
- **Avoid pitfalls:**  
  - Do not imply “paternal genes are more important” or that paternal genes only affect the placenta.  
  - Avoid deterministic claims; acknowledge effects are **probabilistic** and interact with environment.  
  - No deep molecular pathways; no heavy disease focus, but may mention **imprinting disorders** as evidence (optional, 1 line).  
- **Length:** Concise (≈120–200 words or 4–6 sentences).  
- **Tone:** Neutral, explanatory.

### 3) Expected output format  
- One short paragraph (or 4–6 sentences).  
- Include:  
  - A one-sentence definition of imprinting.  
  - 2–3 sentences on paternal (imprinted) roles (placenta/resource allocation → brain development; direct neural effects/behavior).  
  - 1 sentence contrasting maternal imprinted genes and broader maternal influences.

### 4) Success criteria  
- Reader comes away understanding:  
  - Both parents contribute equally to the genome; imprinting is a special case.  
  - Paternally expressed imprinted genes commonly increase fetal/placental growth and nutrient acquisition, indirectly shaping brain development.  
  - Some paternal imprinted genes act directly in the brain affecting neural development and behavior.  
  - Maternal genes and maternal physiology/environment also play key, sometimes growth-limiting, roles.  
- No overclaiming, no confusion between “genes” and “parenting,” and no implication of a single-cause explanation.

### Elevation: Expert reframing & second-order considerations  
- Frame the question as “**parent-of-origin effects**” rather than “paternal genes vs maternal genes,” to prevent the common misconception that paternal DNA uniquely “builds the brain.”  
- Add the causal chain experts expect: **paternal imprinting → placental strategy/hormones → fetal energy supply → brain growth and developmental timing**.  
- Hedge with nuance: imprinting effects are **important but limited to a small gene subset**; outcomes depend on **maternal health, gestational environment, and postnatal context**.  
- Optionally strengthen credibility with one example reference class (e.g., “imprinting disorders show these effects”), without diving into clinical detail.
```

### 6. 🔧 TOOL_CALL
```
create_rubric({"brief":"## Brief: Explain paternal gene contributions to developing brain (general audience)\n\n### 1) Core objective  \nDeliver a clear, accurate, non-misleading explanation of what paternal genes contribute to brain development, emphasizing that paternal and maternal genomes both provide ~half the DNA, while a small subset of **imprinted, paternally expressed genes** have outsized effects on **placental function, fetal resource allocation, and downstream brain growth/behavior**.\n\n### 2) Key requirements & constraints  \n- **Audience:** General public; plain language; minimal jargon; define “imprinting” succinctly.  \n- **Scientific accuracy:**  \n  - State that **most genes are expressed from both parents**; imprinting is an **exception** involving parent-of-origin expression.  \n  - Explain that paternally expressed imprinted genes often promote **growth/resource demand** via the **placenta** (nutrient transfer, endocrine signals), influencing fetal and brain development.  \n  - Include known neurodevelopmental roles: **neural proliferation/brain size, synapse development, feeding/suckling, sleep/arousal, cognition/social behavior** (high-level, not exhaustive).  \n  - Briefly contrast maternal contributions: maternal expressed imprinted genes often bias toward **growth restraint/energy conservation** and also directly affect neurodevelopment; additionally note **maternal environment** (uterus, placenta, caregiving) shapes outcomes.  \n- **Avoid pitfalls:**  \n  - Do not imply “paternal genes are more important” or that paternal genes only affect the placenta.  \n  - Avoid deterministic claims; acknowledge effects are **probabilistic** and interact with environment.  \n  - No deep molecular pathways; no heavy disease focus, but may mention **imprinting disorders** as evidence (optional, 1 line).  \n- **Length:** Concise (≈120–200 words or 4–6 sentences).  \n- **Tone:** Neutral, explanatory.\n\n### 3) Expected output format  \n- One short paragraph (or 4–6 sentences).  \n- Include:  \n  - A one-sentence definition of imprinting.  \n  - 2–3 sentences on paternal (imprinted) roles (placenta/resource allocation → brain development; direct neural effects/behavior).  \n  - 1 sentence contrasting maternal imprinted genes and broader maternal influences.\n\n### 4) Success criteria  \n- Reader comes away understanding:  \n  - Both parents contribute equally to the genome; imprinting is a special case.  \n  - Paternally expressed imprinted genes commonly increase fetal/placental growth and nutrient acquisition, indirectly shaping brain development.  \n  - Some paternal imprinted genes act directly in the brain affecting neural development and behavior.  \n  - Maternal genes and maternal physiology/environment also play key, sometimes growth-limiting, roles.  \n- No overclaiming, no confusion between “genes” and “parenting,” and no implication of a single-cause explanation.\n\n### Elevation: Expert reframing & second-order considerations  \n- Frame the question as “**parent-of-origin effects**” rather than “paternal genes vs maternal genes,” to prevent the common misconception that paternal DNA uniquely “builds the brain.”  \n- Add the causal chain experts expect: **paternal imprinting → placental strategy/hormones → fetal energy supply → brain growth and developmental timing**.  \n- Hedge with nuance: imprinting effects are **important but limited to a small gene subset**; outcomes depend on **maternal health, gestational environment, and postnatal context**.  \n- Optionally strengthen credibility with one example reference class (e.g., “imprinting disorders show these effects”), without diving into clinical detail."})
```

### 7. 🔧 TOOL_CALL
```
spawn_subagent({"prompt":"Draft a concise general-audience explanation focusing on genomic imprinting and paternally expressed genes' roles in placenta, fetal growth, and brain development; include contrast with maternal."})
```

### 8. 🔧 TOOL_CALL
```
spawn_subagent({"prompt":"Provide scientific accuracy check: key points about paternal gene contributions vs maternal, imprinting exception, typical functional themes, and avoid common misconceptions."})
```

### 9. 🔧 TOOL_CALL
```
search_web({"query":"paternally expressed imprinted genes placenta fetal growth brain development resource allocation review"})
```

### 10. 📥 TOOL_RESPONSE
```
create_rubric -> Rubric created.
```

### 11. 📥 TOOL_RESPONSE
```
spawn_subagent -> Genomic imprinting is an unusual kind of gene control in mammals where, for a small set of genes, only the copy from **one parent** is active while the other parent’s copy is **epigenetically silenced** (often via DNA methylation marks set in egg or sperm). The result is “parent-of-origin” gene expression: some genes are **paternally expressed** (dad’s copy on), others are **maternally expressed** (mom’s copy on). ([nature.com](https://www.nature.com/articles/35047554?utm_source=openai))

### Why imprinting matters so much in the placenta
The placenta is the fetus–mother interface that controls **nutrient/oxygen transfer** and produces hormones that reshape maternal physiology to support pregnancy. Many imprinted genes are highly active in placental tissues, and classic evolutionary thinking (“genetic conflict/kinship” models) proposes a tension: **paternally expressed genes tend to push for greater maternal investment in the current fetus**, while **maternally expressed genes tend to limit fetal demands to protect the mother and preserve resources for potential future offspring**. ([pubmed.ncbi.nlm.nih.gov](https://pubmed.ncbi.nlm.nih.gov/21648055/?utm_source=openai))

### Paternally expressed genes: often “pro-growth / pro-supply”
Many well-studied paternally expressed genes increase placental capacity and fetal growth—especially by influencing how effectively the placenta can acquire and deliver maternal nutrients.

- **IGF2** is a classic example: it is typically **paternally expressed** and promotes growth in both fetus and placenta; disrupting a placenta-specific Igf2 transcript in mice reduces placental growth first and then leads to fetal growth restriction, consistent with a role in controlling nutrient supply. ([pubmed.ncbi.nlm.nih.gov](https://pubmed.ncbi.nlm.nih.gov/12087403/?utm_source=openai))  
- **PEG10** is another paternally expressed gene with a major placental role; knockout studies in mice show severe placental defects and embryonic lethality, indicating PEG10 is crucial for normal placental formation and function. ([nature.com](https://www.nature.com/articles/ng1699?utm_source=openai))

### Maternally expressed genes: often “growth-restraining / demand-limiting”
In contrast, many maternally expressed imprinted genes act like “brakes,” limiting growth or placental demands.

- **GRB10** is largely **maternally expressed** in mice, and disrupting the maternal allele causes fetal and placental overgrowth—evidence that GRB10 normally restrains growth. ([pubmed.ncbi.nlm.nih.gov](https://pubmed.ncbi.nlm.nih.gov/12829789/?utm_source=openai))  
- Reviews of human and animal data commonly summarize the overall pattern as **paternally expressed genes promoting fetal growth**, while **maternally expressed genes suppress growth**, aligning with resource-allocation models. ([pubmed.ncbi.nlm.nih.gov](https://pubmed.ncbi.nlm.nih.gov/25602077/?utm_source=openai))

### Brain development: imprinting also shapes neural circuits and behavior
Imprinted genes are not “placenta-only.” Many are active in the developing brain, where they influence processes such as **neural patterning, differentiation, and pruning**, with long-lasting effects on behavior. ([nature.com](https://www.nature.com/articles/nrn2235?utm_source=openai))

Several paternally expressed genes are especially notable for brain-related roles:
- **PEG3** (paternally expressed) is linked in mouse studies to hypothalamic development and programmed cell death (apoptosis) during early postnatal brain development; loss of Peg3 alters apoptosis patterns and is associated with later behavioral deficits. ([pubmed.ncbi.nlm.nih.gov](https://pubmed.ncbi.nlm.nih.gov/19224563/?utm_source=openai))  
- **MAGEL2** is paternally expressed in the central nervous system; loss of paternally expressed genes in the same chromosomal region is central to **Prader–Willi syndrome**, a neurodevelopmental disorder. ([pubmed.ncbi.nlm.nih.gov](https://pubmed.ncbi.nlm.nih.gov/10915770/?utm_source=openai))  

Overall, genomic imprinting helps tune a three-way negotiation among **placenta (supply), fetus (growth and brain development), and mother (resource availability)**—with paternally expressed genes often biasing toward increased investment in growth and maternal provisioning, and maternally expressed genes often biasing toward restraint and balance. ([pubmed.ncbi.nlm.nih.gov](https://pubmed.ncbi.nlm.nih.gov/21648055/?utm_source=openai))
```

### 12. 📥 TOOL_RESPONSE
```
spawn_subagent -> ## 1) Baseline reality: maternal and paternal **nuclear** genes are (usually) equal contributors
- In typical human conception, the child’s **nuclear genome** comes as **23 chromosome pairs (46 total)**, with **one chromosome of each pair from the mother and the other from the father**—so, for almost all nuclear genes, you inherit **one maternal allele + one paternal allele**. ([medlineplus.gov](https://medlineplus.gov/ency/article/002327.htm?utm_source=openai))  
- For **most** genes, **both inherited copies are active** (biallelic expression); there is no general rule that “maternal genes run X” and “paternal genes run Y.” ([medlineplus.gov](https://medlineplus.gov/genetics/understanding/inheritance/updimprinting/?utm_source=openai))

**Accuracy check:** Any claim that fathers “contribute less genetic information” (in the nuclear genome) is incorrect; the paternal and maternal nuclear contributions are symmetric in count and genome-wide importance.

---

## 2) Legitimate exceptions people mix up (and what they really mean)

### A) **Mitochondrial DNA (mtDNA): usually maternal**
- mtDNA is classically **maternally inherited** in humans; paternal mtDNA is actively eliminated/does not persist in typical inheritance. Deep sequencing studies have found **no evidence of paternal mtDNA transmission in humans** (supporting that paternal transmission, if it occurs at all, is extraordinarily rare). ([pubmed.ncbi.nlm.nih.gov](https://pubmed.ncbi.nlm.nih.gov/25973765/?utm_source=openai))  

**Common misconception to avoid:** “You get *more* genes from your mother because mtDNA.”  
Reality: mtDNA is **tiny** compared with nuclear DNA; it matters biologically, but it does **not** make maternal inheritance “dominant” overall.

### B) **Sex chromosomes are not symmetric**
- Mothers always provide an **X**; fathers provide **X or Y**, which is why paternal contribution determines typical chromosomal sex (XX vs XY). ([medlineplus.gov](https://medlineplus.gov/ency/article/002327.htm?utm_source=openai))  
This is a chromosome-type exception, not a genome-wide “paternal genes are stronger/weaker” principle.

### C) **Genomic imprinting: parent-of-origin *expression* bias (not extra DNA)**
- **Genomic imprinting** is when **only one parental allele is normally active** (the other is silenced), and **which allele is active depends on whether it came from egg or sperm**. ([medlineplus.gov](https://medlineplus.gov/genetics/understanding/inheritance/updimprinting/?utm_source=openai))  
- Imprints are typically established via epigenetic marks (classically **DNA methylation**) laid down during gamete formation and then maintained after fertilization; they are also reset across generations. ([medlineplus.gov](https://medlineplus.gov/genetics/understanding/inheritance/updimprinting/?utm_source=openai))  
- Only a **small fraction** of human genes are imprinted, and imprinted genes often occur in **clusters** (e.g., well-known clusters include regions on chromosomes 11 and 15). ([medlineplus.gov](https://medlineplus.gov/genetics/understanding/inheritance/updimprinting/?utm_source=openai))

**Accuracy check:** Imprinting changes **which copy is expressed**, not the fact that the DNA was inherited from both parents.

---

## 3) Typical functional “themes” of imprinted genes (what’s broadly true vs overstated)

### Theme 1: **Placenta + fetal growth + resource allocation**
- A consistent theme across mammalian imprinting research is that many imprinted genes influence **feto-placental development**, including **placental growth, morphology, and nutrient transfer**, thereby shaping fetal growth. ([pubmed.ncbi.nlm.nih.gov](https://pubmed.ncbi.nlm.nih.gov/16612114/?utm_source=openai))  
- The **H19–IGF2** region is a canonical example often discussed in this context (with parent-of-origin expression differences playing into growth regulation). ([pubmed.ncbi.nlm.nih.gov](https://pubmed.ncbi.nlm.nih.gov/16612114/?utm_source=openai))  
- A frequently reported pattern (a generalization, not an absolute rule): **paternally expressed genes tend to promote fetal growth**, while **maternally expressed genes tend to restrain it**—often framed alongside the “parental conflict” idea. ([pmc.ncbi.nlm.nih.gov](https://pmc.ncbi.nlm.nih.gov/articles/PMC4305174/?utm_source=openai))  

**Guardrail:** This is a *tendency* observed in many cases, not a universal law across all imprinted genes or all traits.

### Theme 2: **Brain/behavior, especially feeding and motivated behaviors (seen strongly in mammals)**
- Genome-wide work in mouse brain has found many loci with parent-of-origin allelic biases and reported enrichment in neural systems linked to **feeding/motivated behaviors**, with parental biases affecting pathways including **metabolism and cell adhesion**. ([pubmed.ncbi.nlm.nih.gov](https://pubmed.ncbi.nlm.nih.gov/20616232/?utm_source=openai))  

**Guardrail:** Findings in mouse brain do not license simplistic statements like “materna...
```

### 13. 📥 TOOL_RESPONSE
```
search_web -> Paternally expressed imprinted genes (PEGs) are disproportionately important at the maternal–fetal interface because they (i) shape placental structure and transport capacity, (ii) alter placental endocrine signals that change maternal physiology, and (iii) influence fetal organ growth—including brain development—thereby affecting “resource allocation” phenotypes classically framed by kinship/parent–offspring conflict models. ([pubmed.ncbi.nlm.nih.gov](https://pubmed.ncbi.nlm.nih.gov/21108957/))

## How PEGs connect placenta → fetal growth → brain/behavior (resource allocation framework)
- **Resource allocation logic (kinship/conflict framing):** many PEGs tend to **increase fetal demand and/or placental capacity**, whereas many maternally expressed imprinted genes (MEGs) tend to **constrain** growth and demand—an antagonism often discussed as a regulatory “tug-of-war” over maternal investment. ([pubmed.ncbi.nlm.nih.gov](https://pubmed.ncbi.nlm.nih.gov/21108957/))  
- **Placenta as both “transporter” and “endocrine manipulator”:** beyond nutrient exchange, the placenta secretes hormones (e.g., prolactin/placental lactogen families in rodents) that tune **maternal metabolism, appetite, insulin resistance, and maternal brain priming** for caregiving—creating direct mechanistic routes for conceptus genotype (including imprinting) to affect maternal provisioning and offspring outcomes. ([pmc.ncbi.nlm.nih.gov](https://pmc.ncbi.nlm.nih.gov/articles/PMC6774950/))  
- **Placenta–brain axis:** imprinted genes are among the most enriched classes in both **placenta and brain**, and variation in placental imprinted-gene expression has been associated with **newborn neurobehavioral profiles**, supporting the idea that placental imprinting affects neurodevelopment not only indirectly via growth, but also via endocrine/inflammatory signaling. ([journals.plos.org](https://journals.plos.org/plosgenetics/article?id=10.1371%2Fjournal.pgen.1008709))

## High-yield PEG examples (with what they illustrate)
### 1) **IGF2 (paternally expressed)** — classic growth & placental supply control
- **Placenta-specific Igf2 (P0 transcript)**: deleting a placenta-specific Igf2 transcript in mice reduces placental growth first, then fetal growth restriction follows; nutrient transfer changes show partial compensation before failure—often cited as direct evidence that imprinting can tune placental nutrient supply (resource allocation). ([pubmed.ncbi.nlm.nih.gov](https://pubmed.ncbi.nlm.nih.gov/12087403/))  
- **Igf2–Igf2r axis / placental microvasculature**: fetal and endothelial IGF2 signaling helps match placental exchange surface area (labyrinth microvasculature expansion) to fetal growth demand. ([pmc.ncbi.nlm.nih.gov](https://pmc.ncbi.nlm.nih.gov/articles/PMC8751640/))  
- **Endocrine Igf2 and maternal metabolism (“fetal manipulation” mechanism)**: Igf2 expressed in placental endocrine lineages can be required to establish normal pregnancy insulin resistance and nutrient partitioning to the fetus via placental hormones (including prolactin family effects). ([pubmed.ncbi.nlm.nih.gov](https://pubmed.ncbi.nlm.nih.gov/37437545/?utm_source=openai))  

### 2) **PEG3 (paternally expressed)** — growth + maternal brain/behavior coupling
- Peg3 mutation in mice causes **offspring growth retardation** and strong **maternal-care deficits** (including impaired milk ejection linked to hypothalamic/oxytocin circuitry), illustrating a placenta/brain-relevant PEG that links growth with caregiving-related neurobiology. ([pubmed.ncbi.nlm.nih.gov](https://pubmed.ncbi.nlm.nih.gov/10195900/))  
- In a broader placenta→maternal behavior framing, reviews and experimental work emphasize PEG3 as a canonical example where conceptus/placental genotype can influence maternal priming and caregiving behaviors. ([pmc.ncbi.nlm.nih.gov](https://pmc.ncbi.nlm.nih.gov/articles/PMC6774950/))  

### 3) **PEG10 (paternally expressed; retrotransposon-derived)** — placental essentiality
- Peg10 knockout in mice leads to **early embryonic lethality due to placental defects**, making it one of the clearest “PEG is essential for placentation” demonstrations. ([pubmed.ncbi.nlm.nih.gov](https://pubmed.ncbi.nlm.nih.gov/16341224/))  

### 4) **DLK1 (paternally expressed)** — fetal growth associations in humans
- Human genetic/placental-expression work links DLK1 (and other imprinted loci) to birthweight and growth parameters, illustrating translational relevance of PEGs beyond mouse placentation. ([pubmed.ncbi.nlm.nih.gov](https://pubmed.ncbi.nlm.nih.gov/25602077/?utm_source=openai))  

## Placental imprinting as a *regulatory system* (why placenta is special)
Modern reviews emphasize that placental imprinting includes **placenta-specific imprinted expression**, **non-canonical mechanisms**, lineage differences (trophoblast vs embryonic epiblast), and technical pitfalls (cell-type mixture; maternal cell contamination), so “PEG effects” are often compartment- and stage-sp...
```

### 14. 🔧 TOOL_CALL
```
verify_answer({"answer":"In humans, the father’s DNA provides one copy of (almost) every gene in the embryo—so paternal genes are broadly just as essential as maternal genes for building the brain. The special twist is **genomic imprinting**, where a small set of genes is “tagged” so that only the copy from one parent is switched on. Many **paternally expressed imprinted genes** are most active in the **placenta** and tend to increase placental growth, nutrient transfer, and fetal growth, which indirectly affects how much energy and building material the developing brain receives. Some paternally expressed imprinted genes are also active **in the brain itself**, influencing neurogenesis, synapse development, and behaviors such as feeding, arousal, and social/cognitive traits. By contrast, many maternally expressed imprinted genes often act as growth “brakes,” and overall brain outcomes still depend strongly on the prenatal environment (maternal health, hormones, stress, nutrition) as well as genetics."})
```

### 15. 📥 TOOL_RESPONSE
```
verify_answer -> 1) Output length & structure: **Satisfied.** Single paragraph, **5 sentences**, no headings/lists. Word count is **~146 words** (within 120–200).

2) Equal genomic contribution baseline: **Not satisfied.** It implies equality (“paternal genes… as essential as maternal”), but it does **not explicitly state both parents contribute ~half the genome**, and it does **not explicitly state that most genes are expressed from both parents** (the biparental-expression norm).

3) One-sentence definition of imprinting: **Satisfied.** Exactly one sentence defines imprinting as a parent-of-origin silencing/activation effect.

4) Imprinting framed as exception: **Satisfied.** “Small set of genes” clearly signals it’s uncommon.

5) Paternal imprinted genes via placenta/resource allocation → brain: **Satisfied.** Placental growth/nutrient transfer → more fetal resources → brain building materials.

6) Paternal imprinted genes direct brain/behavior roles: **Satisfied.** Explicit brain activity + multiple domains (neurogenesis, synapses, feeding, arousal, social/cognitive).

7) Maternal contrast + broader maternal influences in one sentence: **Satisfied.** Growth “brakes” plus prenatal environment factors.

8) Non-misleading importance framing: **Satisfied.** Explicitly avoids “dad genes more important” and includes both placenta and brain routes.

9) Non-deterministic & interaction-aware: **Satisfied.** Uses “tend to,” “influencing,” and mentions environment.

10) Plain-language accessibility: **Satisfied.** Jargon is limited and readable.

11) Avoids genes vs parenting confusion: **Satisfied.**

12) Expert reframing: **Not present** (good-to-have).

13) Clear causal chain: **Satisfied** (good-to-have).

14) Maternal direct neurodevelopment note: **Not present** (good-to-have).

15) Credibility anchor: **SKIP** (not attempted; no disorders mentioned).

16) Internal coherence/no contradictions: **Satisfied.**

17) Tight clarity/flow: **Satisfied.**

18) Avoids common failure modes: **Satisfied.**

**FAIL** — Fix criterion (2) by adding an explicit clause like: “Each parent contributes about half the genome, and for most genes both copies are normally expressed,” while keeping the 4–6 sentence / 120–200 word constraint.
```

### 16. 🔧 TOOL_CALL
```
verify_answer({"answer":"Each parent contributes about **half of the embryo’s nuclear DNA**, and for **most genes both the maternal and paternal copies are used** during brain development. A notable exception is **genomic imprinting**, where a small set of genes is epigenetically “tagged” so that only the copy from one parent is switched on. Many **paternally expressed (imprinted) genes** are especially active in the **placenta** and tend to promote placental growth and nutrient transfer, increasing fetal resources that support overall growth, including the developing brain. Some paternally expressed imprinted genes are also active **in the brain itself**, influencing processes like neural proliferation, synapse formation, and behaviors such as feeding and arousal. By contrast, many maternally expressed imprinted genes often act as growth “brakes,” and genetic effects interact with the prenatal environment (maternal health, nutrition, hormones, stress)."})
```

### 17. 📥 TOOL_RESPONSE
```
verify_answer -> 1) Output length & structure: **Satisfied.** Single paragraph, **6 sentences**, no headings/lists. Word count appears ~**133 words** (within 120–200).

2) Equal genomic contribution baseline: **Satisfied.** Explicitly says each parent contributes about half the nuclear DNA and that most genes use both copies.

3) One-sentence definition of imprinting: **Satisfied.** Exactly one sentence defines imprinting as a parent-of-origin effect where only one parent’s copy is switched on.

4) Imprinting framed as exception, limited subset: **Satisfied.** Calls imprinting an “exception” affecting a “small set of genes.”

5) Paternal imprinted genes via placenta/resource allocation → brain: **Satisfied.** Connects paternally expressed imprinted genes to placental growth/nutrient transfer and links increased fetal resources to supporting developing brain growth.

6) Paternal imprinted genes direct brain/behavior roles: **Satisfied.** States some act in the brain and mentions multiple domains (neural proliferation/brain size proxy, synapse formation, feeding, arousal).

7) Maternal contrast + broader maternal influences (one sentence): **Satisfied.** One sentence contrasts maternally expressed imprinted genes as growth brakes and mentions non-genetic prenatal influences (maternal health, nutrition, hormones, stress).

8) Non-misleading importance framing: **Satisfied.** Does not imply paternal genes are more important and includes both placental and direct brain routes.

9) Non-deterministic, interaction-aware phrasing: **Satisfied.** Uses “tend,” “often,” “influencing,” and explicitly notes interaction with prenatal environment.

10) Plain-language accessibility: **Satisfied.** Minimal jargon; “epigenetically ‘tagged’” is explained in-line.

11) Avoids “genes vs parenting” confusion: **Satisfied.** Keeps discussion on genetic parent-of-origin effects, not social parenting roles.

12) Expert reframing (good-to-have): **Not satisfied.** Does not explicitly use the phrase “parent-of-origin effects.”

13) Clear causal chain (good-to-have): **Satisfied.** Presents a coherent placenta → resources → brain support sequence.

14) Balanced symmetry statement (good-to-have): **Not satisfied.** Does not note that maternally expressed imprinted genes can also directly affect neurodevelopment.

15) Optional credibility anchor (ideal/good-to-have): **Satisfied (by omission).** No disorder mention, so no over-focus.

16) Internal coherence & no contradictions: **Satisfied.** No conflicting claims; uses probabilistic language.

17) Tight, readable clarity: **Mostly satisfied.** Flow is logical and pronouns are clear.

18) Common failure modes avoided: **Satisfied.** Avoids paternal-dominance, determinism, and excessive molecular detail.

**PASS.** All verifiable must-have criteria are satisfied; optional improvements would be explicitly reframing as “parent-of-origin effects” and adding a brief note that maternal imprinted genes can also act directly in the brain.
```

### 18. 🔧 TOOL_CALL
```
submit_answer({"answer":"Each parent contributes about **half of the embryo’s nuclear DNA**, and for **most genes both the maternal and paternal copies are used** during brain development. A notable exception is **genomic imprinting**, where a small set of genes is epigenetically “tagged” so that only the copy from one parent is switched on. Many **paternally expressed (imprinted) genes** are especially active in the **placenta** and tend to promote placental growth and nutrient transfer, increasing fetal resources that support overall growth, including the developing brain. Some paternally expressed imprinted genes are also active **in the brain itself**, influencing processes like neural proliferation, synapse formation, and behaviors such as feeding and arousal. By contrast, many maternally expressed imprinted genes often act as growth “brakes,” and genetic effects interact with the prenatal environment (maternal health, nutrition, hormones, stress)."})
```

### 19. 📥 TOOL_RESPONSE
```
submit_answer -> SUBMITTED
```
