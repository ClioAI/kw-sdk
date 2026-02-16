import os
import json
import base64
import logging
import mimetypes
import anthropic

from .base import BaseProvider, FunctionCall, TOOL_DEFINITIONS, retry_on_error
from ..prompts import SEARCH_AGENT
from ..config import Prompt, Attachment
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
MODEL_ID = "claude-opus-4-6"

# Debug logger
debug_logger = logging.getLogger("anthropic_debug")
debug_logger.setLevel(logging.DEBUG)
if not debug_logger.handlers:
    fh = logging.FileHandler("anthropic_debug.log", mode="w")
    fh.setFormatter(logging.Formatter("%(asctime)s | %(message)s"))
    debug_logger.addHandler(fh)


def _to_anthropic_tool(tool_def: dict) -> dict:
    """Convert base tool definition to Anthropic format."""
    return {
        "name": tool_def["name"],
        "description": tool_def["description"],
        "input_schema": tool_def["parameters"],
    }


WEB_SEARCH_TOOL = {"type": "web_search_20250305", "name": "web_search", "max_uses": 5}


class AnthropicProvider(BaseProvider):
    provider_name = "anthropic"

    def __init__(self, thinking_budget: int = 10000):
        super().__init__()
        self.client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        self.thinking_budget = thinking_budget
        self._verification_called = False

    def _debug_log(self, message: str):
        debug_logger.error(message)

    # === Core streaming method ===
    def _stream_generate(
        self,
        messages: list,
        system: str = "",
        tools: list = None,
        tool_choice: dict = None,
        event_type: str = "model_chunk",
        meta: dict = None,
        extract_function_calls: bool = False,
    ) -> tuple[str, list[FunctionCall], list]:
        """
        Core streaming logic. Returns (text, func_calls, content_blocks).
        content_blocks = full assistant message content for context assembly.
        """
        func_calls = []
        text_parts = []
        content_blocks = []
        meta = meta or {}

        # Track current block being streamed
        current_block = None
        current_tool_input_json = ""
        current_thinking_signature = ""

        kwargs = {
            "model": MODEL_ID,
            "max_tokens": 128000,
            "messages": messages,
            "thinking": {"type": "adaptive"},
            "output_config": {"effort": "medium"},
        }
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = tools
        if tool_choice:
            kwargs["tool_choice"] = tool_choice

        with self.client.messages.stream(**kwargs) as stream:
            for event in stream:
                if event.type == "content_block_start":
                    current_block = event.content_block
                    current_tool_input_json = ""
                    current_thinking_signature = ""

                elif event.type == "content_block_delta":
                    delta = event.delta
                    if delta.type == "text_delta":
                        text_parts.append(delta.text)
                        self.emit(event_type, delta.text, meta if meta else None)
                    elif extract_function_calls and delta.type == "thinking_delta":
                        self.emit("thinking", delta.thinking)
                    elif delta.type == "input_json_delta":
                        current_tool_input_json += delta.partial_json

                elif event.type == "signature":
                    current_thinking_signature = event.signature

                elif event.type == "content_block_stop":
                    if current_block is not None:
                        if current_block.type == "text":
                            # Use accumulated text from stop event's content_block
                            final_text = getattr(event.content_block, "text", "") if hasattr(event, "content_block") else ""
                            content_blocks.append({"type": "text", "text": final_text})
                        elif current_block.type == "thinking":
                            cb = event.content_block if hasattr(event, "content_block") else current_block
                            content_blocks.append({
                                "type": "thinking",
                                "thinking": getattr(cb, "thinking", ""),
                                "signature": getattr(cb, "signature", "") or current_thinking_signature,
                            })
                        elif current_block.type == "tool_use":
                            args = json.loads(current_tool_input_json) if current_tool_input_json else {}
                            block = {
                                "type": "tool_use",
                                "id": current_block.id,
                                "name": current_block.name,
                                "input": args,
                            }
                            content_blocks.append(block)
                            if extract_function_calls:
                                func_calls.append(FunctionCall(
                                    name=current_block.name,
                                    args=args,
                                    raw=block,
                                ))
                                self.log("tool_call", f"{current_block.name}({args})")
                        elif current_block.type == "server_tool_use":
                            # Server-side web search - pass through for context
                            self.emit("tool_call", f"web_search({getattr(current_block, 'input', {})})")
                        elif current_block.type == "web_search_tool_result":
                            # Search results - pass through
                            n = len(current_block.content) if hasattr(current_block, "content") and current_block.content else 0
                            self.emit("tool_response", f"web_search -> {n} results")
                    current_block = None

        return "".join(text_parts), func_calls, content_blocks

    # === LLM calls ===
    def generate(self, prompt: str, system: str = None, _log: bool = True, enable_search: bool = False,
                 stream: bool = False, subagent_id: str = None, stream_event_type: str = None,
                 stream_meta: dict = None) -> str:
        if _log:
            self.log("user", prompt)
            if system:
                self.log("system", system)

        messages = [{"role": "user", "content": prompt}]
        tools = [WEB_SEARCH_TOOL] if enable_search else None

        # Streaming path - emit events without storing in history
        if stream:
            event_type = stream_event_type or "subagent_chunk"
            is_subagent = not stream_event_type
            meta = stream_meta or ({"subagent_id": subagent_id} if subagent_id else {})
            if is_subagent:
                self.emit("subagent_start", prompt, meta)
            text, _, _ = self._stream_generate(
                messages=messages,
                system=system or "",
                tools=tools,
                event_type=event_type,
                meta=meta,
            )
            if is_subagent:
                self.emit("subagent_end", text, meta)
            return text

        # Blocking path
        kwargs = {
            "model": MODEL_ID,
            "max_tokens": 128000,
            "messages": messages,
            "thinking": {"type": "adaptive"},
            "output_config": {"effort": "medium"},
        }
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = tools

        try:
            response = retry_on_error(
                lambda: self._generate_with_pause(kwargs),
                logger=debug_logger,
            )
        except Exception as e:
            debug_logger.error(f"generate() failed | prompt: {prompt[:200]}... | error: {e}")
            if _log:
                self.log("tool_error", f"generate: {e}")
            raise

        if _log:
            self._log_response(response)

        return self._extract_text_with_citations(response)

    def search(self, query: str, stream: bool = False, subagent_id: str = None) -> str:
        """Search using Anthropic's native web search tool."""
        return self.generate(
            query,
            system=SEARCH_AGENT,
            _log=False,
            enable_search=True,
            stream=stream,
            subagent_id=subagent_id,
        )

    def _create(self, **kwargs):
        """Stream-backed blocking call (required for large max_tokens)."""
        with self.client.messages.stream(**kwargs) as s:
            return s.get_final_message()

    def _generate_with_pause(self, kwargs: dict):
        """Handle pause_turn stop reason by continuing the conversation."""
        response = self._create(**kwargs)
        while response.stop_reason == "pause_turn":
            kwargs["messages"] = kwargs["messages"] + [
                {"role": "assistant", "content": response.content},
                {"role": "user", "content": "Continue."},
            ]
            response = self._create(**kwargs)
        return response

    def read_file_with_vision(self, file_path: str, prompt: str) -> str:
        """Read a file using Anthropic's vision/document capabilities."""
        if not os.path.exists(file_path):
            return f"Error: File not found: {file_path}"

        mime_type, _ = mimetypes.guess_type(file_path)
        ext = os.path.splitext(file_path)[1].lower()

        image_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.webp'}

        try:
            if ext in image_extensions:
                with open(file_path, 'rb') as f:
                    data = base64.standard_b64encode(f.read()).decode('utf-8')
                media_type = mime_type or f"image/{ext[1:]}"
                content = [
                    {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": data}},
                    {"type": "text", "text": prompt},
                ]
            elif ext == '.pdf':
                with open(file_path, 'rb') as f:
                    data = base64.standard_b64encode(f.read()).decode('utf-8')
                content = [
                    {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": data}},
                    {"type": "text", "text": prompt},
                ]
            else:
                # Text files
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        file_content = f.read()[:50000]
                    content = f"{prompt}\n\n---\nFile Content:\n{file_content}"
                except UnicodeDecodeError:
                    return f"Error: Cannot read binary file {file_path}. Supported: images, PDFs, text files."

            response = retry_on_error(
                lambda: self._create(
                    model=MODEL_ID,
                    max_tokens=128000,
                    messages=[{"role": "user", "content": content}],
                    thinking={"type": "adaptive"},
                    output_config={"effort": "medium"},
                ),
                logger=debug_logger,
            )
            return self._extract_text(response)

        except Exception as e:
            debug_logger.error(f"read_file_with_vision() failed | file: {file_path} | error: {e}")
            return f"Error reading file: {e}"

    def _extract_text(self, response) -> str:
        """Extract text from Anthropic response."""
        parts = []
        for block in response.content:
            if block.type == "text":
                parts.append(block.text)
        return "".join(parts) or ""

    def _extract_text_with_citations(self, response) -> str:
        """Extract text with source URLs from web search citations."""
        text = self._extract_text(response)
        # Collect unique source URLs from citations
        sources = set()
        for block in response.content:
            if block.type == "text" and hasattr(block, "citations") and block.citations:
                for cite in block.citations:
                    if hasattr(cite, "url") and cite.url:
                        sources.add(cite.url)
        if sources:
            text += "\n\nSources:\n" + "\n".join(sorted(sources))
        return text

    def _log_response(self, response):
        for block in response.content:
            if block.type == "thinking":
                self.log("thinking", block.thinking)
            elif block.type == "text":
                self.log("model", block.text)
            elif block.type == "tool_use":
                self.log("tool_call", f"{block.name}({block.input})")
            elif block.type == "server_tool_use":
                self.log("tool_call", f"web_search({getattr(block, 'input', {})})")
            elif block.type == "web_search_tool_result":
                n = len(block.content) if hasattr(block, "content") and block.content else 0
                self.log("tool_response", f"web_search -> {n} results")

    # === Orchestrator context management ===
    def _init_context(self, task: Prompt, system: str, tool_names: list[str]) -> dict:
        self._verification_called = False
        tools = [_to_anthropic_tool(self.get_tool_definition(t)) for t in tool_names]
        user_content = self._prompt_to_content(task)
        messages = [{"role": "user", "content": user_content}]
        # Anthropic: thinking + tool_choice "any" is not allowed, always use "auto"
        return {
            "system": system,
            "tools": tools,
            "messages": messages,
            "tool_choice": {"type": "auto"},
        }

    def _prompt_to_content(self, task: Prompt):
        """Convert Prompt to Anthropic content format."""
        if isinstance(task, str):
            return task

        parts = []
        for item in task:
            if isinstance(item, str):
                parts.append({"type": "text", "text": item})
            elif isinstance(item, Attachment):
                parts.append(self._attachment_to_content(item))
        return parts

    def _attachment_to_content(self, attachment: Attachment) -> dict:
        """Convert Attachment to Anthropic content block."""
        # Images
        if attachment.mime_type.startswith("image/"):
            if isinstance(attachment.content, bytes):
                b64 = base64.standard_b64encode(attachment.content).decode("utf-8")
                return {"type": "image", "source": {"type": "base64", "media_type": attachment.mime_type, "data": b64}}
            elif isinstance(attachment.content, str):
                if os.path.exists(attachment.content):
                    with open(attachment.content, "rb") as f:
                        b64 = base64.standard_b64encode(f.read()).decode("utf-8")
                    return {"type": "image", "source": {"type": "base64", "media_type": attachment.mime_type, "data": b64}}
                return {"type": "image", "source": {"type": "url", "url": attachment.content}}

        # PDFs
        if attachment.mime_type == "application/pdf":
            if isinstance(attachment.content, bytes):
                b64 = base64.standard_b64encode(attachment.content).decode("utf-8")
                return {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": b64}}
            elif isinstance(attachment.content, str) and os.path.exists(attachment.content):
                with open(attachment.content, "rb") as f:
                    b64 = base64.standard_b64encode(f.read()).decode("utf-8")
                return {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": b64}}

        # Non-image/PDF files: text metadata + preview
        file_name = attachment.name or "attachment"
        if isinstance(attachment.content, str):
            if attachment.preview:
                return {
                    "type": "text",
                    "text": f"[Attached file: {file_name}, path: {attachment.content}, type: {attachment.mime_type}]\nPreview:\n{attachment.preview}",
                }
            return {
                "type": "text",
                "text": f"[Attached file: {file_name}, path: {attachment.content}, type: {attachment.mime_type}] - No preview available. Use search_files to read this file first.",
            }
        return {"type": "text", "text": f"[Attached file: {file_name}, type: {attachment.mime_type}] - Use search_files to read this file."}

    def _call_model(self, context: dict, step_desc: str, stream: bool = False) -> tuple[list[FunctionCall], str]:
        # Switch to auto after verification
        if self._verification_called:
            context["tool_choice"] = {"type": "auto"}

        # Streaming path
        if stream:
            text, func_calls, content_blocks = self._stream_generate(
                messages=context["messages"],
                system=context["system"],
                tools=context["tools"],
                tool_choice=context["tool_choice"],
                event_type="model_chunk",
                extract_function_calls=True,
            )
            if content_blocks:
                context["messages"].append({"role": "assistant", "content": content_blocks})
            return func_calls, text

        # Blocking path
        kwargs = {
            "model": MODEL_ID,
            "max_tokens": 128000,
            "system": context["system"],
            "messages": context["messages"],
            "tools": context["tools"],
            "tool_choice": context["tool_choice"],
            "thinking": {"type": "adaptive"},
            "output_config": {"effort": "medium"},
        }

        response = retry_on_error(
            lambda: self._create(**kwargs),
            logger=debug_logger,
        )
        self._log_response(response)

        # Extract function calls
        func_calls = []
        for block in response.content:
            if block.type == "tool_use":
                func_calls.append(FunctionCall(
                    name=block.name,
                    args=block.input or {},
                    raw=block,
                ))

        if not func_calls:
            return [], self._extract_text(response)

        # Append full assistant message to context
        # Convert response.content to serializable dicts
        assistant_content = []
        for block in response.content:
            if block.type == "thinking":
                assistant_content.append({
                    "type": "thinking",
                    "thinking": block.thinking,
                    "signature": block.signature,
                })
            elif block.type == "text":
                assistant_content.append({"type": "text", "text": block.text})
            elif block.type == "tool_use":
                assistant_content.append({
                    "type": "tool_use",
                    "id": block.id,
                    "name": block.name,
                    "input": block.input,
                })
        context["messages"].append({"role": "assistant", "content": assistant_content})

        return func_calls, self._extract_text(response)

    def _append_tool_results(self, context: dict, func_calls: list[FunctionCall], results: list[str]):
        # Track verification
        if any(fc.name == "verify_answer" for fc in func_calls):
            self._verification_called = True

        tool_results = []
        for i, fc in enumerate(func_calls):
            tool_use_id = fc.raw.get("id") if isinstance(fc.raw, dict) else getattr(fc.raw, "id", "")
            content = results[i]
            if not isinstance(content, (str, list)):
                content = str(content)
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tool_use_id,
                "content": content,
            })
        context["messages"].append({"role": "user", "content": tool_results})

    # === Context compaction methods ===
    def _estimate_context_tokens(self, context: dict) -> int:
        """Estimate tokens: chars / 4."""
        total_chars = 0
        for msg in context["messages"]:
            content = msg.get("content", "")
            if isinstance(content, str):
                total_chars += len(content)
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict):
                        total_chars += len(block.get("text", "") or block.get("thinking", "") or "")
                        if block.get("type") == "tool_use":
                            total_chars += len(json.dumps(block.get("input", {})))
                        if block.get("type") == "tool_result":
                            c = block.get("content", "")
                            total_chars += len(c) if isinstance(c, str) else 0
        total_chars += len(context.get("system", ""))
        return total_chars // 4

    def _get_context_length(self, context: dict) -> int:
        return len(context["messages"])

    def _extract_context_section(self, context: dict, start_idx: int, end_idx: int) -> list:
        return context["messages"][start_idx:end_idx]

    def _item_to_xml(self, item) -> str:
        """Convert Anthropic message dict to XML for compaction."""
        if not isinstance(item, dict):
            return ""
        role = item.get("role", "unknown")
        content = item.get("content", "")

        if isinstance(content, str):
            return f'  <{role}>{content[:1000]}</{role}>\n'

        xml = ""
        if isinstance(content, list):
            for block in content:
                if not isinstance(block, dict):
                    continue
                btype = block.get("type", "")
                if btype == "tool_use":
                    args_str = json.dumps(block.get("input", {}))[:500]
                    xml += f'  <tool-call name="{block.get("name", "")}">{args_str}</tool-call>\n'
                elif btype == "tool_result":
                    c = block.get("content", "")
                    result = c[:1000] if isinstance(c, str) else ""
                    xml += f'  <tool-result name="">{result}</tool-result>\n'
                elif btype == "text":
                    xml += f'  <{role}>{block.get("text", "")[:1000]}</{role}>\n'
        return xml

    def _inject_feedback(self, context: dict, text: str) -> None:
        context["messages"].append({"role": "user", "content": text})

    def _rebuild_context_with_summary(self, context: dict, summary: str, keep_recent: int) -> dict:
        """Rebuild context with summary replacing middle section."""
        messages = context["messages"]

        head = messages[:1]  # Initial task
        rest = messages[1:]

        # Find pair boundaries
        pair_starts = self._find_pair_boundaries(rest)

        if len(pair_starts) <= keep_recent:
            return context

        tail_start_idx = pair_starts[-keep_recent] if keep_recent > 0 else len(rest)
        tail = rest[tail_start_idx:]

        summary_msg = {
            "role": "user",
            "content": f'<compacted-history note="You already executed these tools. This is a summary of what happened.">\n{summary}\n</compacted-history>\n\nContinue from where you left off.',
        }

        new_context = context.copy()
        new_context["messages"] = head + [summary_msg] + tail
        return new_context

    def _find_pair_boundaries(self, messages: list) -> list[int]:
        """Find indices where tool call+response pairs start.

        A pair = assistant message with tool_use blocks + user message with tool_result blocks.
        """
        boundaries = []
        i = 0
        while i < len(messages):
            msg = messages[i]
            if not isinstance(msg, dict):
                i += 1
                continue
            # Check if assistant with tool_use
            if msg.get("role") == "assistant":
                content = msg.get("content", [])
                has_tool_use = isinstance(content, list) and any(
                    isinstance(b, dict) and b.get("type") == "tool_use" for b in content
                )
                if has_tool_use:
                    boundaries.append(i)
                    i += 1
                    # Skip corresponding user tool_result message
                    if i < len(messages):
                        next_msg = messages[i]
                        if isinstance(next_msg, dict) and next_msg.get("role") == "user":
                            next_content = next_msg.get("content", [])
                            has_tool_result = isinstance(next_content, list) and any(
                                isinstance(b, dict) and b.get("type") == "tool_result" for b in next_content
                            )
                            if has_tool_result:
                                i += 1
                    continue
            i += 1
        return boundaries
