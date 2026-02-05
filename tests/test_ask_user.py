import os
import traceback
import threading
from dotenv import load_dotenv
load_dotenv()

from google import genai
from google.genai import types

from verif import RLHarness, ProviderConfig

# Task that should force clarification
task = """Create a detailed project plan for my upcoming product launch.
Include timeline, budget allocation, and team responsibilities."""

# Gemini client for answering questions
gemini_client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))


def answer_question(questions: list[dict], context: str) -> dict:
    """Use LLM to generate answers to the clarification questions."""
    questions_text = "\n".join(
        f"{i+1}. {q['question']}" + (f" (options: {', '.join(q['options'])})" if q.get('options') else "")
        for i, q in enumerate(questions)
    )

    prompt = f"""You are a user being asked clarification questions by an AI assistant working on a task.
Answer each question concisely as if you're giving real requirements.

Context from assistant: {context or 'None provided'}

Questions:
{questions_text}

Respond with answers in this format:
Q1: [your answer]
Q2: [your answer]
...

Be specific and realistic. For example:
- If asked about product type: "A B2B SaaS platform for HR management"
- If asked about budget: "$50,000 total budget"
- If asked about timeline: "3 months, launching June 15th"
"""

    response = gemini_client.models.generate_content(
        model="gemini-3-flash-preview",
        contents=prompt,
        config=types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(thinking_level="LOW"),
        ),
    )

    # Parse response into dict
    answers = {}
    lines = response.text.strip().split("\n")
    for i, line in enumerate(lines):
        line = line.strip()
        if line.startswith("Q") and ":" in line:
            try:
                q_num = int(line[1:line.index(":")]) - 1
                answer = line[line.index(":") + 1:].strip()
                answers[q_num] = answer
            except (ValueError, IndexError):
                continue

    return answers


def on_event(entry, harness):
    """Handle events, respond to user questions."""
    print(f"[{entry.entry_type}] {entry.content[:100]}...")

    if entry.entry_type == "user_question":
        question_id = entry.metadata["question_id"]
        questions = entry.metadata["questions"]
        context = entry.metadata.get("context", "")

        print(f"\n>>> USER QUESTION RECEIVED: {question_id}")
        print(f">>> Questions: {questions}")

        # Use LLM to generate answers
        answers = answer_question(questions, context)
        print(f">>> Generated answers: {answers}")

        # Send response back (in a thread to not block)
        def respond():
            harness.provider.receive_user_response(question_id, answers)
        threading.Thread(target=respond).start()


# Configure harness
config = ProviderConfig(name="gemini", thinking_level="MEDIUM")
harness = RLHarness(
    provider=config,
    enable_search=False,
    enable_bash=False,
    enable_code=False,
    enable_ask_user=True,
    on_event=lambda e: on_event(e, harness),
)

print(f"Running task: {task[:50]}...")
print("-" * 50)

try:
    result = harness.run_single(task)
    error = None
except Exception as e:
    result = None
    error = f"**FATAL ERROR**\n```\n{traceback.format_exc()}\n```"

# Save results
with open("test_ask_user_output.md", "w") as f:
    f.write(f"# ask_user Tool Test\n\n")
    f.write(f"## Task\n{task}\n\n")

    if error:
        f.write(f"## Error\n{error}\n\n---\n\n")

    if result:
        f.write(f"## Answer\n{result.answer}\n\n")
        f.write(f"## Rubric\n{result.rubric}\n\n")

    # User clarifications
    if harness.provider._user_clarifications:
        f.write("## User Clarifications\n")
        for c in harness.provider._user_clarifications:
            f.write(f"- **Q:** {c['questions']}\n")
            f.write(f"  **A:** {c['response']}\n\n")

    f.write("---\n\n")
    f.write(harness.get_history_markdown())

print("\nResults saved to test_ask_user_output.md")
if error:
    print("RUN FAILED - see output for details")
else:
    print(f"\nAnswer preview:\n{result.answer[:500]}...")
    print(f"\nClarifications received: {len(harness.provider._user_clarifications)}")
