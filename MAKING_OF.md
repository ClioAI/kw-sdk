# How This Was Made

## It started as an RL harness

I am working on self-verification training models to check their own output. The idea is simple: if you can get a model to reliably verify its own work, you have a reward signal for tasks that don't naturally have one. Code has tests. Math has proofs. But "write a market analysis" has nothing.

So I built a harness: task → execute → verify against rubric → iterate if fail. The rubric was the synthetic reward function. Train on the orchestration decisions (tool calls, sequencing, when to verify), leave the subagent outputs out of the training signal. Kimi in their recent 2.5 release and agent swarms arrived at a similar setup. 

## Rubric creation turned out to be the hard problem

The first thing I learned: models are bad at writing rubrics.

They either write rubrics so vague they always pass ("answer should be comprehensive and well-structured") or so specific they encode the answer ("must mention that the Chicxulub crater was discovered in 1978" . wrong year, but the rubric said it, so the verifier checked for it). The rubric is supposed to define quality criteria, not be a lookup table.

Training models to create good rubrics - specific enough to catch real failures, general enough not to leak answers - became the primary task of my RL runs. The brief→rubric→execute→verify loop *became* the training curriculum. Getting the rubric right mattered more than getting the answer quality right, because a good rubric makes every subsequent answer better.

## From training harness to product SDK

Then Claude Cowork launched, and I realized the same loop that works for RL training works for production knowledge work. The verification loop is genuinely useful. I think claude code and llm workflows greatly benefit from a feedback loop, and this is a good method to add a feedback loop for subjective tasks. Users want to see what criteria the agent is evaluating against. They want to override the rubric. They want to iterate with feedback.

The gap between "RL harness for training" and "SDK for building knowledge work" was smaller than I expected. The core loop is identical. The difference is who consumes the output: a training pipeline or a human.

## How Opus built most of this

The original architecture was mine: the verification loop, the mode system, the provider abstraction. It was full of pytorch, tapping local inference and batching, not useful for engineering consumption directly. But this SDK as it exists today was largely built by Claude Opus 4.5. I look at the quality and thought this would be a good way to test the model capabilities. The fact that it came up with abstractions that are not there in original cowork or claude code - yet - makes me feel really impressed by the prowess of the model. 

**Modularization.** I had a working monolith. I described the target architecture — providers as a protocol, modes as config, tools as a registry, execution as a pluggable interface — and Opus refactored it. The provider abstraction where Gemini, OpenAI, and Anthropic all implement the same base class, the mode system where you register custom modes at runtime, the executor protocol — that's Opus working from my spec.

**Examples.** Every example in `examples/` was written by Opus. Yes, the sdk exist, but it's still a task to come up with representative examples. I would describe the pattern I wanted to demonstrate ("show explore → select → execute as a three-stage pipeline", "show how a plan mode can be a repeatable writing playbook"), Opus would write the example, I'd run it, and we'd iterate on the output. Some examples took 3-4 rounds — the first version would run but produce mediocre output, so Opus in claude code would suggest changes. I like that loop more than the solo development I have been doing over the weeks. 

**The Anthropic provider.** This was almost entirely Opus. I had Gemini and OpenAI working. I said "add Anthropic with streaming, extended thinking, and native web search" and described the constraints (thinking + tool_choice "any" isn't allowed, need to handle `pause_turn` stop reason, citations need to be extracted from web search results). Opus wrote the full provider, ran the streaming test, it fixed edge cases from the trace.

## Test-driven development, but different

The development loop wasn't traditional TDD. It was closer to:

1. I describe what I want (a spec, a feature, a behavior)
2. Opus writes it
3. I say "run a full-scale test". not a unit test, an actual end-to-end execution with a real task and real API calls
4. Opus looks at the execution trace. the full tool-call-by-tool-call history, the model's reasoning, the verification results, the final output
5. Opus identifies failure modes from the trace and fixes them

The output markdown files in `examples/outputs/` are the test artifacts. Each one represents a run that passed end-to-end, including the verification step. If you open `file_artifact_output.md`, you can see the model's first answer get rejected, watch it self-correct, and see it pass on retry. That trace is the test.

## What I actually did vs what Opus did

**Me:**
- Original RL harness design
- Verification loop architecture
- Mode system concept (standard, plan, explore, iterate)
- Product direction (from training harness → SDK)
- Running examples and evaluating output quality
- Deciding when output was "good enough" vs needed another round

**Opus:**
- Provider abstraction and all three implementations
- Mode registry and custom mode system
- Executor protocol and SubprocessExecutor/RemoteExecutor
- Context compaction
- Checkpointing and resume
- Streaming implementation
- Every example file
- Every test file
- EXTENSIONS.md, SDK_GUIDE.md, TOOL_CALLING_GUIDE.md
- Bug fixes from execution traces

The ratio is probably 15% me, 85% Opus by lines of code. But the 15% is the architecture, the verification insight, and the quality bar ie which lines to keep and which to rewrite. Opus is fast and thorough. My job was knowing what to build and when it was done.

## The meta-irony

An SDK for AI knowledge work, built primarily by an AI doing knowledge work, using a verification loop to check its own output. The examples were written by the same kind of system they demonstrate. The traces that prove the system works were generated by the system working.

I don't think this makes it less valid. If anything, it's evidence that the pattern works. The SDK exists because the loop — spec → execute → verify → iterate — actually produces good output when the rubric is right. Getting the rubric right is still the hard part.
