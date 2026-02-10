from .base import BaseProvider, HistoryEntry

__all__ = ["BaseProvider", "HistoryEntry", "GeminiProvider", "OpenAIProvider", "AnthropicProvider"]


def __getattr__(name):
    if name == "GeminiProvider":
        from .gemini import GeminiProvider
        return GeminiProvider
    if name == "OpenAIProvider":
        from .openai import OpenAIProvider
        return OpenAIProvider
    if name == "AnthropicProvider":
        from .anthropic import AnthropicProvider
        return AnthropicProvider
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
