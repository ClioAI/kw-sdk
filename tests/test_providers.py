"""Test file to verify both providers and tool definitions are working."""

import os
import time
from dotenv import load_dotenv

load_dotenv()

from verif import RLHarness, PlanResult
from verif.providers.base import TOOL_DEFINITIONS

# =============================================================================
# TEST CONFIGURATION - Modify these as needed
# =============================================================================

# Providers to test: "gemini", "openai", or "both"
TEST_PROVIDERS = "openai"

# Task for plan creation and execution tests
TEST_TASK = """
Analyze the key factors that contributed to the success of the Apollo 11 mission.
Provide a structured analysis covering: technical innovations, team coordination,
and risk management strategies. Keep the response concise (under 300 words).
"""

# Simple task for full run test
TEST_TASK_SIMPLE = """
Explain the difference between supervised and unsupervised learning in machine learning.
Provide 2-3 key differences with brief examples. Keep response under 200 words.
"""

# Wait time between API calls (seconds) to avoid rate limits
RATE_LIMIT_DELAY = 10

# =============================================================================


def test_tool_definitions():
    """Verify tool definitions are correctly structured."""
    print("=" * 50)
    print("Testing Tool Definitions")
    print("=" * 50)

    required_tools = ["create_brief", "create_rubric", "spawn_subagent", "search_web", "verify_answer", "submit_answer"]

    for tool_name in required_tools:
        assert tool_name in TOOL_DEFINITIONS, f"Missing tool: {tool_name}"
        tool = TOOL_DEFINITIONS[tool_name]
        assert "name" in tool, f"Tool {tool_name} missing 'name'"
        assert "description" in tool, f"Tool {tool_name} missing 'description'"
        assert "parameters" in tool, f"Tool {tool_name} missing 'parameters'"
        assert tool["parameters"]["type"] == "object", f"Tool {tool_name} parameters not object type"
        print(f"  [OK] {tool_name}")

    print(f"\nAll {len(required_tools)} tool definitions valid.\n")


def test_gemini_provider():
    """Test Gemini provider basic functionality."""
    print("=" * 50)
    print("Testing Gemini Provider")
    print("=" * 50)

    if not os.environ.get("GEMINI_API_KEY"):
        print("  [SKIP] GEMINI_API_KEY not set\n")
        return False

    try:
        from verif.providers.gemini import GeminiProvider
        provider = GeminiProvider()
        print("  [OK] Provider initialized")

        # Test simple generation
        response = provider.generate("Say 'hello' and nothing else.", _log=False)
        assert len(response) > 0, "Empty response"
        print(f"  [OK] Generation works: {response[:50]}...")

        # Test context initialization
        context = provider._init_context("test task", "test system", ["spawn_subagent", "submit_answer"])
        assert "config" in context, "Missing config in context"
        assert "contents" in context, "Missing contents in context"
        print("  [OK] Context initialization works")

        print("\nGemini provider tests passed.\n")
        return True

    except Exception as e:
        print(f"  [FAIL] {e}\n")
        return False


def test_openai_provider():
    """Test OpenAI provider basic functionality."""
    print("=" * 50)
    print("Testing OpenAI Provider")
    print("=" * 50)

    if not os.environ.get("OPENAI_API_KEY"):
        print("  [SKIP] OPENAI_API_KEY not set\n")
        return False

    try:
        from verif.providers.openai import OpenAIProvider, _to_openai_tool
        provider = OpenAIProvider()
        print("  [OK] Provider initialized")

        # Test tool conversion
        converted = _to_openai_tool(TOOL_DEFINITIONS["spawn_subagent"])
        assert converted["type"] == "function", "Wrong tool type"
        assert "additionalProperties" in converted["parameters"], "Missing additionalProperties"
        print("  [OK] Tool conversion works")

        # Test simple generation
        response = provider.generate("Say 'hello' and nothing else.", _log=False)
        assert len(response) > 0, "Empty response"
        print(f"  [OK] Generation works: {response[:50]}...")

        # Test context initialization
        context = provider._init_context("test task", "test system", ["spawn_subagent", "submit_answer"])
        assert "tools" in context, "Missing tools in context"
        assert "messages" in context, "Missing messages in context"
        print("  [OK] Context initialization works")

        print("\nOpenAI provider tests passed.\n")
        return True

    except Exception as e:
        print(f"  [FAIL] {e}\n")
        return False


def test_harness_init():
    """Test harness initialization with both providers."""
    print("=" * 50)
    print("Testing Harness Initialization")
    print("=" * 50)

    # Test Gemini harness
    if os.environ.get("GEMINI_API_KEY"):
        try:
            RLHarness(provider="gemini", plan_mode=False)
            print("  [OK] Gemini harness (plan_mode=False)")

            RLHarness(provider="gemini", plan_mode=True)
            print("  [OK] Gemini harness (plan_mode=True)")
        except Exception as e:
            print(f"  [FAIL] Gemini harness: {e}")
    else:
        print("  [SKIP] Gemini harness (no API key)")

    # Test OpenAI harness
    if os.environ.get("OPENAI_API_KEY"):
        try:
            RLHarness(provider="openai", plan_mode=False)
            print("  [OK] OpenAI harness (plan_mode=False)")

            RLHarness(provider="openai", plan_mode=True)
            print("  [OK] OpenAI harness (plan_mode=True)")
        except Exception as e:
            print(f"  [FAIL] OpenAI harness: {e}")
    else:
        print("  [SKIP] OpenAI harness (no API key)")

    print()


def test_create_plan(provider_name: str):
    """Test plan creation for a provider."""
    print("=" * 50)
    print(f"Testing Plan Creation ({provider_name})")
    print("=" * 50)

    api_key_var = "GEMINI_API_KEY" if provider_name == "gemini" else "OPENAI_API_KEY"
    if not os.environ.get(api_key_var):
        print(f"  [SKIP] {api_key_var} not set\n")
        return None

    try:
        harness = RLHarness(provider=provider_name, plan_mode=True)

        plan_result = harness.create_plan(TEST_TASK)

        assert isinstance(plan_result, PlanResult), "Wrong return type"
        assert len(plan_result.brief) > 0, "Empty brief"
        assert len(plan_result.plan) > 0, "Empty plan"
        assert len(plan_result.rubric) > 0, "Empty rubric"

        print(f"  [OK] Plan created")
        print(f"\n  Brief ({len(plan_result.brief)} chars):")
        print(f"  {plan_result.brief[:300]}...")
        print(f"\n  Plan ({len(plan_result.plan)} chars):")
        print(f"  {plan_result.plan[:300]}...")
        print(f"\n  Rubric ({len(plan_result.rubric)} chars):")
        print(f"  {plan_result.rubric[:300]}...")

        print(f"\nPlan creation test passed.\n")
        return plan_result

    except Exception as e:
        print(f"  [FAIL] {e}\n")
        return None


def test_execute_plan(provider_name: str, plan_result: PlanResult):
    """Test plan execution for a provider."""
    print("=" * 50)
    print(f"Testing Plan Execution ({provider_name})")
    print("=" * 50)

    if plan_result is None:
        print("  [SKIP] No plan result provided\n")
        return

    print(f"  Waiting {RATE_LIMIT_DELAY}s for rate limit...")
    time.sleep(RATE_LIMIT_DELAY)

    try:
        harness = RLHarness(provider=provider_name, plan_mode=True)

        result = harness.execute_plan(
            task=plan_result.task,
            plan=plan_result.plan,
            rubric=plan_result.rubric
        )

        assert len(result.answer) > 0, "Empty answer"

        print(f"  [OK] Plan executed")
        print(f"\n  Answer ({len(result.answer)} chars):")
        print(f"  {result.answer[:500]}...")
        print(f"\n  History entries: {len(result.history)}")

        print(f"\nPlan execution test passed.\n")

    except Exception as e:
        print(f"  [FAIL] {e}\n")


def test_full_run(provider_name: str):
    """Test full run_single with plan_mode."""
    print("=" * 50)
    print(f"Testing Full Run ({provider_name})")
    print("=" * 50)

    api_key_var = "GEMINI_API_KEY" if provider_name == "gemini" else "OPENAI_API_KEY"
    if not os.environ.get(api_key_var):
        print(f"  [SKIP] {api_key_var} not set\n")
        return

    print(f"  Waiting {RATE_LIMIT_DELAY}s for rate limit...")
    time.sleep(RATE_LIMIT_DELAY)

    try:
        harness = RLHarness(provider=provider_name, plan_mode=True, enable_search=False)

        result = harness.run_single(TEST_TASK_SIMPLE)

        assert len(result.answer) > 0, "Empty answer"

        print(f"  [OK] Full run completed")
        print(f"\n  Answer: {result.answer[:500]}...")
        print(f"  Rubric: {result.rubric[:300]}..." if result.rubric else "  Rubric: (empty)")
        print(f"  History entries: {len(result.history)}")

        print(f"\nFull run test passed.\n")

    except Exception as e:
        print(f"  [FAIL] {e}\n")


if __name__ == "__main__":
    print("\n" + "=" * 50)
    print("PROVIDER TEST SUITE")
    print("=" * 50 + "\n")

    # Basic tests
    test_tool_definitions()
    test_gemini_provider()
    test_openai_provider()
    test_harness_init()

    # Plan mode tests - run for configured providers
    providers = []
    if TEST_PROVIDERS in ("gemini", "both") and os.environ.get("GEMINI_API_KEY"):
        providers.append("gemini")
    if TEST_PROVIDERS in ("openai", "both") and os.environ.get("OPENAI_API_KEY"):
        providers.append("openai")

    if providers:
        for provider in providers:
            print("\n" + "#" * 50)
            print(f"# INTEGRATION TESTS: {provider.upper()}")
            print("#" * 50 + "\n")

            plan_result = test_create_plan(provider)
            if plan_result:
                test_execute_plan(provider, plan_result)
            test_full_run(provider)
    else:
        print(f"No providers available for TEST_PROVIDERS='{TEST_PROVIDERS}'. Check API keys.\n")

    print("=" * 50)
    print("TEST SUITE COMPLETE")
    print("=" * 50)
