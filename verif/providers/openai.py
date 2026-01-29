import os
import json
import logging
from openai import OpenAI

from .base import BaseProvider, FunctionCall, TOOL_DEFINITIONS, retry_on_error
from ..prompts import SEARCH_AGENT
from ..config import Prompt, Attachment

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
MODEL_ID = "gpt-5.2"

# Debug logger
debug_logger = logging.getLogger("openai_debug")
debug_logger.setLevel(logging.DEBUG)
if not debug_logger.handlers:
    fh = logging.FileHandler("openai_debug.log", mode="w")
    fh.setFormatter(logging.Formatter("%(asctime)s | %(message)s"))
    debug_logger.addHandler(fh)


def _to_openai_tool(tool_def: dict) -> dict:
    """Convert base tool definition to OpenAI format."""
    params = tool_def["parameters"].copy()
    params["additionalProperties"] = False
    return {
        "type": "function",
        "name": tool_def["name"],
        "description": tool_def["description"],
        "parameters": params,
    }


class OpenAIProvider(BaseProvider):
    provider_name = "openai"

    def __init__(self, reasoning_effort: str = "medium"):
        super().__init__()
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        self.reasoning_effort = reasoning_effort

    def _debug_log(self, message: str):
        debug_logger.error(message)

    # === Core streaming method ===
    def _stream_generate(
        self,
        input_messages: list,
        tools: list = None,
        event_type: str = "model_chunk",
        meta: dict = None,
        extract_function_calls: bool = False,
    ) -> tuple[str, list[FunctionCall], list]:
        """
        Core streaming logic. Returns (text, func_calls, response_output).
        - event_type: which log type to emit for text chunks
        - meta: metadata dict for subagent events (contains subagent_id)
        - extract_function_calls: True for orchestrator, False for subagents
        """
        func_calls_by_idx = {}
        text_parts = []
        response_output = []
        meta = meta or {}

        kwargs = {
            "model": MODEL_ID,
            "input": input_messages,
            "reasoning": {"effort": self.reasoning_effort},
            "stream": True,
        }
        if tools:
            kwargs["tools"] = tools

        for event in self.client.responses.create(**kwargs):
            if event.type == "response.output_text.delta":
                text_parts.append(event.delta)
                self.emit(event_type, event.delta, meta if meta else None)

            elif event.type == "response.reasoning_summary_part.delta":
                self.emit("thinking", event.delta)

            elif extract_function_calls and event.type == "response.output_item.added":
                if hasattr(event.item, "type") and event.item.type == "function_call":
                    func_calls_by_idx[event.output_index] = {
                        "item": event.item,
                        "arguments": ""
                    }

            elif extract_function_calls and event.type == "response.function_call_arguments.delta":
                idx = event.output_index
                if idx in func_calls_by_idx:
                    func_calls_by_idx[idx]["arguments"] += event.delta

            elif event.type == "response.output_item.done":
                response_output.append(event.item)
                # Log tool_call with full arguments when function call is complete
                if extract_function_calls and event.output_index in func_calls_by_idx:
                    fc_data = func_calls_by_idx[event.output_index]
                    self.log("tool_call", f"{fc_data['item'].name}({fc_data['arguments']})")

            elif event.type == "response.completed":
                break

        func_calls = [
            FunctionCall(
                name=fc_data["item"].name,
                args=json.loads(fc_data["arguments"]) if fc_data["arguments"] else {},
                raw=fc_data["item"]
            )
            for fc_data in func_calls_by_idx.values()
        ]

        return "".join(text_parts), func_calls, response_output

    # === LLM calls ===
    def generate(self, prompt: str, system: str = None, _log: bool = True, enable_search: bool = False,
                 stream: bool = False, subagent_id: str = None) -> str:
        if _log:
            self.log("user", prompt)
            if system:
                self.log("system", system)

        input_messages = []
        if system:
            input_messages.append({"role": "system", "content": system})
        input_messages.append({"role": "user", "content": prompt})

        tools = [{"type": "web_search"}] if enable_search else None

        # Streaming path for subagents - emit events without storing in history
        if stream:
            meta = {"subagent_id": subagent_id} if subagent_id else {}
            self.emit("subagent_start", prompt, meta)
            text, _, _ = self._stream_generate(
                input_messages=input_messages,
                tools=tools,
                event_type="subagent_chunk",
                meta=meta,
            )
            self.emit("subagent_end", text, meta)
            return text

        # Blocking path (existing)
        kwargs = {"model": MODEL_ID, "input": input_messages, "reasoning": {"effort": self.reasoning_effort}}
        if tools:
            kwargs["tools"] = tools

        try:
            response = retry_on_error(lambda: self.client.responses.create(**kwargs), logger=debug_logger)
        except Exception as e:
            debug_logger.error(f"generate() failed | prompt: {prompt[:200]}... | error: {e}")
            if _log:
                self.log("tool_error", f"generate: {e}")
            raise

        if _log:
            self._log_response(response)
        return response.output_text or ""

    def search(self, query: str, stream: bool = False, subagent_id: str = None) -> str:
        input_messages = [
            {"role": "system", "content": SEARCH_AGENT},
            {"role": "user", "content": query},
        ]
        tools = [{"type": "web_search"}]

        # Streaming path - emit events without storing in history
        if stream:
            meta = {"subagent_id": subagent_id, "tool": "search_web"} if subagent_id else {}
            self.emit("subagent_start", query, meta)
            text, _, _ = self._stream_generate(
                input_messages=input_messages,
                tools=tools,
                event_type="subagent_chunk",
                meta=meta,
            )
            self.emit("subagent_end", text, meta)
            return text

        # Blocking path (existing)
        try:
            response = retry_on_error(
                lambda: self.client.responses.create(
                    model=MODEL_ID,
                    input=input_messages,
                    tools=tools,
                    reasoning={"effort": self.reasoning_effort},
                ),
                logger=debug_logger
            )
        except Exception as e:
            debug_logger.error(f"search() failed | query: {query} | error: {e}")
            self.log("tool_error", f"search: {e}")
            raise
        return response.output_text or ""

    def read_file_with_vision(self, file_path: str, prompt: str) -> str:
        """Read a file using OpenAI's vision capabilities."""
        import os
        import base64
        import mimetypes
        
        if not os.path.exists(file_path):
            return f"Error: File not found: {file_path}"
        
        # Get mime type and extension
        mime_type, _ = mimetypes.guess_type(file_path)
        ext = os.path.splitext(file_path)[1].lower()
        
        # Determine how to handle the file
        image_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.webp'}
        
        try:
            if ext in image_extensions:
                # Handle images with vision API
                with open(file_path, 'rb') as f:
                    image_data = base64.standard_b64encode(f.read()).decode('utf-8')
                
                media_type = mime_type or f"image/{ext[1:]}"
                
                response = retry_on_error(
                    lambda: self.client.responses.create(
                        model=MODEL_ID,
                        input=[
                            {
                                "role": "user",
                                "content": [
                                    {
                                        "type": "input_image",
                                        "image_url": f"data:{media_type};base64,{image_data}",
                                    },
                                    {
                                        "type": "input_text",
                                        "text": prompt,
                                    },
                                ],
                            }
                        ],
                        reasoning={"effort": self.reasoning_effort},
                    ),
                    logger=debug_logger
                )
                return response.output_text or "[No content extracted]"
            
            elif ext == '.pdf':
                # For PDFs, try to extract text or use file upload if available
                # Fall back to describing what we can
                try:
                    # Try using pdftotext if available
                    import subprocess
                    result = subprocess.run(
                        ['pdftotext', file_path, '-'],
                        capture_output=True,
                        text=True,
                        timeout=30
                    )
                    if result.returncode == 0 and result.stdout.strip():
                        pdf_text = result.stdout[:50000]  # Truncate if too long
                        # Ask the model to summarize the extracted text
                        response = retry_on_error(
                            lambda: self.client.responses.create(
                                model=MODEL_ID,
                                input=[
                                    {"role": "user", "content": f"{prompt}\n\n---\nPDF Content:\n{pdf_text}"}
                                ],
                                reasoning={"effort": self.reasoning_effort},
                            ),
                            logger=debug_logger
                        )
                        return response.output_text or "[No content extracted]"
                except (FileNotFoundError, subprocess.SubprocessError):
                    pass
                
                return f"Error: PDF support requires pdftotext (brew install poppler). File: {file_path}"
            
            else:
                # For text files, read directly
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()[:50000]  # Truncate if too long
                    
                    response = retry_on_error(
                        lambda: self.client.responses.create(
                            model=MODEL_ID,
                            input=[
                                {"role": "user", "content": f"{prompt}\n\n---\nFile Content:\n{content}"}
                            ],
                            reasoning={"effort": self.reasoning_effort},
                        ),
                        logger=debug_logger
                    )
                    return response.output_text or "[No content extracted]"
                except UnicodeDecodeError:
                    return f"Error: Cannot read binary file {file_path}. Supported: images (png, jpg, gif, webp), PDFs, text files."
                    
        except Exception as e:
            debug_logger.error(f"read_file_with_vision() failed | file: {file_path} | error: {e}")
            return f"Error reading file: {e}"

    def _log_response(self, response):
        for item in response.output:
            if item.type == "reasoning":
                if item.summary:
                    for s in item.summary:
                        self.log("thinking", s.text if hasattr(s, "text") else str(s))
            elif item.type == "message":
                for content in item.content:
                    if content.type == "output_text":
                        self.log("model", content.text)
            elif item.type == "function_call":
                args = item.arguments if hasattr(item, "arguments") else "{}"
                self.log("tool_call", f"{item.name}({args})")
            elif item.type == "web_search_call":
                self.log("tool_call", "web_search()")

    # === Orchestrator context management ===
    def _init_context(self, task: Prompt, system: str, tool_names: list[str]) -> dict:
        tools = [_to_openai_tool(TOOL_DEFINITIONS[t]) for t in tool_names]
        user_content = self._prompt_to_content(task)
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ]
        return {"tools": tools, "messages": messages}

    def _prompt_to_content(self, task: Prompt):
        """Convert Prompt to OpenAI content format."""
        if isinstance(task, str):
            return task

        parts = []
        for item in task:
            if isinstance(item, str):
                parts.append({"type": "input_text", "text": item})
            elif isinstance(item, Attachment):
                parts.append(self._attachment_to_content(item))
        return parts

    def _attachment_to_content(self, attachment: Attachment) -> dict:
        """Convert Attachment to OpenAI content part.

        For images: base64 encode and embed (models can see directly)
        For other files: include path metadata + preview if available
        """
        import base64

        # Handle image types - embed directly for multimodal
        if attachment.mime_type.startswith("image/"):
            if isinstance(attachment.content, bytes):
                b64 = base64.standard_b64encode(attachment.content).decode("utf-8")
                return {"type": "input_image", "image_url": f"data:{attachment.mime_type};base64,{b64}"}
            elif isinstance(attachment.content, str):
                # File path
                if os.path.exists(attachment.content):
                    with open(attachment.content, "rb") as f:
                        b64 = base64.standard_b64encode(f.read()).decode("utf-8")
                    return {"type": "input_image", "image_url": f"data:{attachment.mime_type};base64,{b64}"}
                # URL
                return {"type": "input_image", "image_url": attachment.content}

        # Non-image files: include path metadata + preview if available
        file_name = attachment.name or "attachment"
        if isinstance(attachment.content, str):
            # Content is a file path
            if attachment.preview:
                return {
                    "type": "input_text",
                    "text": f"[Attached file: {file_name}, path: {attachment.content}, type: {attachment.mime_type}]\nPreview:\n{attachment.preview}"
                }
            else:
                # No preview (PDF, images, etc.) - orchestrator must call search_files first
                return {
                    "type": "input_text",
                    "text": f"[Attached file: {file_name}, path: {attachment.content}, type: {attachment.mime_type}] - No preview available. Use search_files to read this file first."
                }
        elif isinstance(attachment.content, bytes):
            # Content is bytes - note that file needs to be saved first
            return {"type": "input_text", "text": f"[Attached file: {file_name}, type: {attachment.mime_type}] - Use search_files to read this file."}

    def _call_model(self, context: dict, step_desc: str, stream: bool = False) -> tuple[list[FunctionCall], str]:
        # Streaming path
        if stream:
            text, func_calls, response_output = self._stream_generate(
                input_messages=context["messages"],
                tools=context["tools"],
                event_type="model_chunk",
                extract_function_calls=True,
            )
            context["messages"] += response_output
            return func_calls, text

        # Blocking path (existing)
        response = retry_on_error(
            lambda: self.client.responses.create(
                model=MODEL_ID,
                input=context["messages"],
                tools=context["tools"],
                reasoning={"effort": self.reasoning_effort},
            ),
            logger=debug_logger
        )
        self._log_response(response)

        # Extract function calls
        raw_func_calls = [item for item in response.output if item.type == "function_call"]

        if not raw_func_calls:
            return [], response.output_text or ""

        # Append response to context
        context["messages"] += response.output

        # Debug log
        for i, item in enumerate(response.output):
            if item.type == "function_call":
                debug_logger.debug(f"item[{i}] {item.name} call_id={item.call_id}")

        # Convert to normalized FunctionCall
        func_calls = [
            FunctionCall(
                name=fc.name,
                args=json.loads(fc.arguments) if fc.arguments else {},
                raw=fc
            )
            for fc in raw_func_calls
        ]
        return func_calls, response.output_text or ""

    def _append_tool_results(self, context: dict, func_calls: list[FunctionCall], results: list[str]):
        for i, fc in enumerate(func_calls):
            context["messages"].append({
                "type": "function_call_output",
                "call_id": fc.raw.call_id,
                "output": results[i],
            })

    # === Context compaction methods ===
    def _estimate_context_tokens(self, context: dict) -> int:
        """Estimate tokens: chars / 4 for OpenAI."""
        total_chars = 0
        for msg in context["messages"]:
            if isinstance(msg, dict):
                content = msg.get("content", "") or msg.get("output", "")
                if isinstance(content, str):
                    total_chars += len(content)
                elif isinstance(content, list):
                    for part in content:
                        if isinstance(part, dict):
                            total_chars += len(part.get("text", ""))
            else:
                # Response output items
                if hasattr(msg, "type"):
                    if msg.type == "function_call" and hasattr(msg, "arguments"):
                        total_chars += len(msg.arguments or "")
                    elif msg.type == "message" and hasattr(msg, "content"):
                        for c in msg.content:
                            if hasattr(c, "text"):
                                total_chars += len(c.text)
        return total_chars // 4

    def _get_context_length(self, context: dict) -> int:
        """Get number of messages in OpenAI context."""
        return len(context["messages"])

    def _extract_context_section(self, context: dict, start_idx: int, end_idx: int) -> list:
        """Extract raw messages from context."""
        return context["messages"][start_idx:end_idx]

    def _item_to_xml(self, item) -> str:
        """Convert OpenAI message to XML for compaction."""
        if isinstance(item, dict):
            role = item.get("role", item.get("type", "unknown"))
            content = item.get("content", "") or item.get("output", "")
            if isinstance(content, list):
                content = " ".join(p.get("text", "") for p in content if isinstance(p, dict))
            content = str(content)[:1000]
            return f'  <{role}>{content}</{role}>\n'
        else:
            # Response output items
            if hasattr(item, "type"):
                if item.type == "function_call":
                    args = (item.arguments if hasattr(item, "arguments") else "")[:500]
                    return f'  <tool-call name="{item.name}">{args}</tool-call>\n'
                elif item.type == "message" and hasattr(item, "content"):
                    text = " ".join(c.text for c in item.content if hasattr(c, "text"))[:1000]
                    return f'  <model>{text}</model>\n'
        return ""

    def _find_pair_boundaries(self, messages: list) -> list[int]:
        """Find indices where tool call+response pairs start.

        A pair = model's response.output (reasoning + function_calls) + function_call_outputs.
        OpenAI requires reasoning items to stay with their function_call items.
        Returns list of start indices for each pair.
        """
        boundaries = []
        i = 0
        while i < len(messages):
            msg = messages[i]
            # Check if this is a reasoning item (start of a model response batch)
            is_reasoning = hasattr(msg, "type") and msg.type == "reasoning"
            # Or a function_call without preceding reasoning
            is_func_call = hasattr(msg, "type") and msg.type == "function_call"

            if is_reasoning or is_func_call:
                boundaries.append(i)
                # Skip all response.output items (reasoning, function_call, message, etc.)
                while i < len(messages):
                    m = messages[i]
                    if hasattr(m, "type") and m.type in ("reasoning", "function_call", "message"):
                        i += 1
                    else:
                        break
                # Skip all function_call_outputs (responses to this batch)
                while i < len(messages):
                    m = messages[i]
                    if isinstance(m, dict) and m.get("type") == "function_call_output":
                        i += 1
                    else:
                        break
            else:
                i += 1
        return boundaries

    def _rebuild_context_with_summary(self, context: dict, summary: str, keep_recent: int) -> dict:
        """Rebuild OpenAI context with summary replacing middle section.

        Tool call + response = atomic pair, never split.
        keep_recent = number of pairs to keep in native format.
        Middle pairs become XML in a user message.
        """
        messages = context["messages"]

        head = messages[:2]  # System + initial task
        rest = messages[2:]  # Everything after head

        # Find pair boundaries in rest
        pair_starts = self._find_pair_boundaries(rest)

        if len(pair_starts) <= keep_recent:
            # Not enough pairs to compact, keep as-is
            return context

        # Split into middle (to summarize) and tail (to keep native)
        # Tail = last keep_recent pairs
        tail_start_idx = pair_starts[-keep_recent] if keep_recent > 0 else len(rest)

        tail = rest[tail_start_idx:]  # Complete pairs, native format

        # Create compacted summary as user message
        summary_msg = {
            "role": "user",
            "content": f'<compacted-history note="You already executed these tools. This is a summary of what happened.">\n{summary}\n</compacted-history>\n\nContinue from where you left off.'
        }

        new_context = context.copy()
        new_context["messages"] = head + [summary_msg] + tail
        return new_context
