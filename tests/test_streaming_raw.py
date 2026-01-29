"""Test streaming with function call arguments directly from docs."""
import os
from dotenv import load_dotenv
load_dotenv()

from google import genai
from google.genai import types

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

# From gemini_streaming.md docs
get_weather_declaration = types.FunctionDeclaration(
    name="get_weather",
    description="Gets the current weather temperature for a given location.",
    parameters={
        "type": "object",
        "properties": {"location": {"type": "string"}},
        "required": ["location"],
    },
)
get_weather_tool = types.Tool(function_declarations=[get_weather_declaration])

print("Testing streaming with function call arguments...")
print("-" * 60)

try:
    for chunk in client.models.generate_content_stream(
        model="gemini-3-flash-preview",
        contents="What's the weather in London and New York?",
        config=types.GenerateContentConfig(
            tools=[get_weather_tool],
            tool_config=types.ToolConfig(
                function_calling_config=types.FunctionCallingConfig(
                    mode=types.FunctionCallingConfigMode.AUTO,
                    stream_function_call_arguments=True,
                )
            ),
        ),
    ):
        if chunk.function_calls:
            for fc in chunk.function_calls:
                print(f"Function call: {fc.name}")
                print(f"  args: {fc.args}")
                print(f"  will_continue: {getattr(fc, 'will_continue', 'N/A')}")
        if chunk.text:
            print(f"Text: {chunk.text[:100]}...")
        print("---")

    print("\nSUCCESS: Streaming with function call arguments works!")

except Exception as e:
    print(f"\nERROR: {e}")
    import traceback
    traceback.print_exc()
