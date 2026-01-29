"""Quick test: plan mode WITHOUT providing a rubric - with detailed trace."""
import os
import traceback
from dotenv import load_dotenv
load_dotenv()

from verif import RLHarness, ProviderConfig

TASK = "Write a haiku about debugging code."
PLAN = """
1. Think of programming frustration
2. Write first line (5 syllables)
3. Write second line (7 syllables)  
4. Write third line (5 syllables)
5. Verify it's a proper haiku
"""

def main():
    config = ProviderConfig(name="gemini")
    harness = RLHarness(provider=config, enable_search=False)

    print("Testing plan mode WITHOUT rubric...")
    print("-" * 40)

    try:
        # Note: NO rubric passed!
        result = harness.run_single(task=TASK, mode="plan", plan=PLAN)
        print(f"SUCCESS!\nAnswer: {result.answer}")
        print(f"\nRubric used: {result.rubric[:200] if result.rubric else 'NONE'}")
        
        # Print execution trace to see what tools were called
        print("\n" + "="*50)
        print("TOOL CALLS:")
        print("="*50)
        for entry in result.history:
            if entry.entry_type in ("tool_call", "tool_response"):
                print(f"  {entry.entry_type}: {entry.content[:150]}...")
        
        return True
    except Exception as e:
        print(f"FAILED: {e}")
        print(traceback.format_exc())
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
