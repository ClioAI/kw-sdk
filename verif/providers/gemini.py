import os
import logging
from google import genai
from google.genai import types

from .base import BaseProvider, FunctionCall, TOOL_DEFINITIONS, retry_on_error
from ..prompts import SEARCH_AGENT
from ..config import Prompt, Attachment
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
MODEL_ID = "gemini-3-flash-preview"

# Debug logger
debug_logger = logging.getLogger("gemini_debug")
debug_logger.setLevel(logging.DEBUG)
if not debug_logger.handlers:
    fh = logging.FileHandler("gemini_debug.log", mode="w")
    fh.setFormatter(logging.Formatter("%(asctime)s | %(message)s"))
    debug_logger.addHandler(fh)


class GeminiProvider(BaseProvider):
    provider_name = "gemini"

    def __init__(self, thinking_level: str = "MEDIUM"):
        super().__init__()
        self.client = genai.Client(api_key=GEMINI_API_KEY)
        self.thinking_level = thinking_level
        self._verification_called = False

    def _thinking_config(self) -> types.ThinkingConfig:
        return types.ThinkingConfig(thinking_level=self.thinking_level)

    def _debug_log(self, message: str):
        debug_logger.error(message)

    # === Core streaming method ===
    def _stream_generate(
        self,
        contents,
        config: types.GenerateContentConfig,
        event_type: str = "model_chunk",
        meta: dict = None,
        extract_function_calls: bool = False,
    ) -> tuple[str, list[FunctionCall], types.Content | None]:
        """
        Core streaming logic. Returns (text, func_calls, accumulated_content).
        - event_type: which log type to emit for text chunks
        - meta: metadata dict for subagent events (contains subagent_id)
        - extract_function_calls: True for orchestrator, False for subagents
        """
        func_calls = []
        text_parts = []
        accumulated_parts = []
        meta = meta or {}

        for chunk in self.client.models.generate_content_stream(
            model=MODEL_ID,
            contents=contents,
            config=config,
        ):
            if not chunk.candidates:
                continue

            for part in chunk.candidates[0].content.parts:
                accumulated_parts.append(part)

                # Text chunk (non-thinking) - emit only, don't store in history
                if hasattr(part, "text") and part.text and not getattr(part, "thought", False):
                    text_parts.append(part.text)
                    self.emit(event_type, part.text, meta if meta else None)

                # Thinking chunk - emit only, don't store in history
                if hasattr(part, "thought") and part.thought and part.text:
                    self.emit("thinking", part.text)

                # Function call (only for orchestrator) - arrives complete without FC streaming
                if extract_function_calls and hasattr(part, "function_call") and part.function_call:
                    fc = part.function_call
                    if fc.name:
                        func_calls.append(FunctionCall(
                            name=fc.name,
                            args=dict(fc.args) if fc.args else {},
                            raw=fc
                        ))
                        self.log("tool_call", f"{fc.name}({dict(fc.args) if fc.args else {}})")

        accumulated_content = types.Content(role="model", parts=accumulated_parts) if accumulated_parts else None
        return "".join(text_parts), func_calls, accumulated_content

    def _make_streaming_config(self, base_config: types.GenerateContentConfig) -> types.GenerateContentConfig:
        """Clone config for streaming. FC args streaming not yet supported in SDK."""
        tool_config = None
        if base_config.tool_config and base_config.tool_config.function_calling_config:
            tool_config = types.ToolConfig(
                function_calling_config=types.FunctionCallingConfig(
                    mode=base_config.tool_config.function_calling_config.mode
                )
            )
        return types.GenerateContentConfig(
            system_instruction=base_config.system_instruction,
            tools=base_config.tools,
            thinking_config=base_config.thinking_config,
            automatic_function_calling=base_config.automatic_function_calling,
            tool_config=tool_config,
        )

    # === LLM calls ===
    def generate(self, prompt: str, system: str = None, _log: bool = True, enable_search: bool = False,
                 stream: bool = False, subagent_id: str = None) -> str:
        if _log:
            self.log("user", prompt)
            if system:
                self.log("system", system)

        config = types.GenerateContentConfig(thinking_config=self._thinking_config())
        if system:
            config.system_instruction = system
        if enable_search:
            config.tools = [
                types.Tool(google_search=types.GoogleSearch()),
                types.Tool(url_context=types.UrlContext()),
            ]

        # Streaming path for subagents - emit events without storing in history
        if stream:
            meta = {"subagent_id": subagent_id} if subagent_id else {}
            self.emit("subagent_start", prompt, meta)
            text, _, _ = self._stream_generate(
                contents=prompt,
                config=config,
                event_type="subagent_chunk",
                meta=meta,
            )
            self.emit("subagent_end", text, meta)
            return text

        # Blocking path (existing)
        try:
            response = retry_on_error(
                lambda: self.client.models.generate_content(model=MODEL_ID, contents=prompt, config=config),
                logger=debug_logger
            )
        except Exception as e:
            debug_logger.error(f"generate() failed | prompt: {prompt[:200]}... | error: {e}")
            if _log:
                self.log("tool_error", f"generate: {e}")
            raise

        if _log:
            self._log_response(response)

        result = response.text or ""
        if enable_search and response.candidates:
            # Grounding metadata (from google_search)
            if response.candidates[0].grounding_metadata:
                sources = [
                    chunk.web.uri
                    for chunk in response.candidates[0].grounding_metadata.grounding_chunks
                    if hasattr(chunk, "web") and chunk.web
                ]
                if sources:
                    result += "\n\nSources:\n" + "\n".join(sources)
            # URL context metadata (from url_context)
            if hasattr(response.candidates[0], "url_context_metadata"):
                url_meta = response.candidates[0].url_context_metadata
                if url_meta and hasattr(url_meta, "url_metadata"):
                    urls = [m.retrieved_url for m in url_meta.url_metadata if hasattr(m, "retrieved_url")]
                    if urls:
                        result += "\n\nURLs fetched:\n" + "\n".join(urls)
        return result

    def search(self, query: str, stream: bool = False, subagent_id: str = None) -> str:
        config = types.GenerateContentConfig(
            system_instruction=SEARCH_AGENT,
            tools=[
                types.Tool(google_search=types.GoogleSearch()),
                types.Tool(url_context=types.UrlContext()),
            ],
            thinking_config=self._thinking_config(),
        )

        # Streaming path - emit events without storing in history
        if stream:
            meta = {"subagent_id": subagent_id, "tool": "search_web"} if subagent_id else {}
            self.emit("subagent_start", query, meta)
            text, _, _ = self._stream_generate(
                contents=query,
                config=config,
                event_type="subagent_chunk",
                meta=meta,
            )
            self.emit("subagent_end", text, meta)
            return text

        # Blocking path (existing)
        try:
            response = retry_on_error(
                lambda: self.client.models.generate_content(
                    model=MODEL_ID,
                    contents=query,
                    config=config,
                ),
                logger=debug_logger
            )
        except Exception as e:
            debug_logger.error(f"search() failed | query: {query} | error: {e}")
            self.log("tool_error", f"search: {e}")
            raise

        result = response.text or ""
        # Grounding metadata (from google_search)
        if response.candidates and response.candidates[0].grounding_metadata:
            sources = [
                chunk.web.uri
                for chunk in response.candidates[0].grounding_metadata.grounding_chunks
                if hasattr(chunk, "web") and chunk.web
            ]
            if sources:
                result += "\n\nSources:\n" + "\n".join(sources)
        # URL context metadata (from url_context)
        if response.candidates and hasattr(response.candidates[0], "url_context_metadata"):
            url_meta = response.candidates[0].url_context_metadata
            if url_meta and hasattr(url_meta, "url_metadata"):
                urls = [m.retrieved_url for m in url_meta.url_metadata if hasattr(m, "retrieved_url")]
                if urls:
                    result += "\n\nURLs fetched:\n" + "\n".join(urls)
        return result

    def read_file_with_vision(self, file_path: str, prompt: str) -> str:
        """Read a file using Gemini's vision/multimodal capabilities."""
        import os
        import mimetypes
        
        if not os.path.exists(file_path):
            return f"Error: File not found: {file_path}"
        
        # Get mime type
        mime_type, _ = mimetypes.guess_type(file_path)
        if not mime_type:
            # Default based on extension
            ext = os.path.splitext(file_path)[1].lower()
            mime_map = {
                '.pdf': 'application/pdf',
                '.png': 'image/png',
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.gif': 'image/gif',
                '.webp': 'image/webp',
                '.mp4': 'video/mp4',
                '.mov': 'video/quicktime',
                '.avi': 'video/x-msvideo',
                '.txt': 'text/plain',
                '.md': 'text/markdown',
            }
            mime_type = mime_map.get(ext, 'application/octet-stream')
        
        try:
            # Upload file to Gemini
            uploaded_file = self.client.files.upload(file=file_path)
            
            # Generate content with the file
            response = retry_on_error(
                lambda: self.client.models.generate_content(
                    model=MODEL_ID,
                    contents=[
                        uploaded_file,
                        prompt,
                    ],
                    config=types.GenerateContentConfig(
                        thinking_config=self._thinking_config(),
                    ),
                ),
                logger=debug_logger
            )
            
            return response.text or "[No content extracted]"
            
        except Exception as e:
            debug_logger.error(f"read_file_with_vision() failed | file: {file_path} | error: {e}")
            return f"Error reading file: {e}"

    def _log_response(self, response):
        if not response.candidates:
            return
        for part in response.candidates[0].content.parts:
            if hasattr(part, "thought") and part.thought and hasattr(part, "text") and part.text:
                self.log("thinking", part.text)
            elif hasattr(part, "function_call") and part.function_call:
                fc = part.function_call
                self.log("tool_call", f"{fc.name}({dict(fc.args) if fc.args else {}})")
            elif hasattr(part, "text") and part.text:
                self.log("model", part.text)

    # === Orchestrator context management ===
    def _init_context(self, task: Prompt, system: str, tool_names: list[str]) -> dict:
        self._verification_called = False
        tool_declarations = [TOOL_DEFINITIONS[t] for t in tool_names]
        tools = types.Tool(function_declarations=tool_declarations)

        config = types.GenerateContentConfig(
            tools=[tools],
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            thinking_config=self._thinking_config(),
            system_instruction=system,
            # Force tool calls until verification
            tool_config=types.ToolConfig(
                function_calling_config=types.FunctionCallingConfig(mode="ANY")
            ),
        )

        parts = self._prompt_to_parts(task)
        contents = [types.Content(role="user", parts=parts)]
        return {"config": config, "contents": contents, "tools": tools}

    def _prompt_to_parts(self, task: Prompt) -> list:
        """Convert Prompt to Gemini parts."""
        if isinstance(task, str):
            return [types.Part.from_text(text=task)]

        parts = []
        for item in task:
            if isinstance(item, str):
                parts.append(types.Part.from_text(text=item))
            elif isinstance(item, Attachment):
                parts.append(self._attachment_to_part(item))
        return parts

    def _attachment_to_part(self, attachment: Attachment):
        """Convert Attachment to Gemini Part.

        For images: upload/embed directly (Gemini can see)
        For other files: include path metadata + preview if available
        """
        # Handle image types - Gemini can see these directly
        if attachment.mime_type.startswith("image/"):
            if isinstance(attachment.content, bytes):
                return types.Part.from_data(data=attachment.content, mime_type=attachment.mime_type)
            elif isinstance(attachment.content, str):
                if os.path.exists(attachment.content):
                    uploaded = self.client.files.upload(file=attachment.content)
                    return uploaded
                return types.Part.from_uri(file_uri=attachment.content, mime_type=attachment.mime_type)

        # Non-image files: include path metadata + preview if available
        file_name = attachment.name or "attachment"
        if isinstance(attachment.content, str):
            # Content is a file path
            if attachment.preview:
                return types.Part.from_text(
                    text=f"[Attached file: {file_name}, path: {attachment.content}, type: {attachment.mime_type}]\nPreview:\n{attachment.preview}"
                )
            else:
                # No preview (PDF, images, etc.) - orchestrator must call search_files first
                return types.Part.from_text(
                    text=f"[Attached file: {file_name}, path: {attachment.content}, type: {attachment.mime_type}] - No preview available. Use search_files to read this file first."
                )
        elif isinstance(attachment.content, bytes):
            return types.Part.from_text(text=f"[Attached file: {file_name}, type: {attachment.mime_type}] - Use search_files to read this file.")

        raise ValueError(f"Invalid attachment content type: {type(attachment.content)}")

    def _call_model(self, context: dict, step_desc: str, stream: bool = False) -> tuple[list[FunctionCall], str]:
        # Switch to AUTO mode after verification (allows text response for submit)
        if self._verification_called:
            context["config"] = types.GenerateContentConfig(
                tools=[context["tools"]],
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                thinking_config=self._thinking_config(),
                system_instruction=context["config"].system_instruction,
                tool_config=types.ToolConfig(
                    function_calling_config=types.FunctionCallingConfig(mode="AUTO")
                ),
            )

        # Streaming path
        if stream:
            config = self._make_streaming_config(context["config"])
            text, func_calls, content = self._stream_generate(
                contents=context["contents"],
                config=config,
                event_type="model_chunk",
                extract_function_calls=True,
            )
            if content:
                context["contents"].append(content)
            return func_calls, text

        # Blocking path (existing)
        response = retry_on_error(
            lambda: self.client.models.generate_content(
                model=MODEL_ID,
                contents=context["contents"],
                config=context["config"],
            ),
            logger=debug_logger
        )
        self._log_response(response)

        if not response.function_calls:
            return [], response.text or ""

        # Append model response to context
        context["contents"].append(response.candidates[0].content)

        # Debug log thought signatures
        for i, part in enumerate(response.candidates[0].content.parts):
            if hasattr(part, 'function_call') and part.function_call:
                has_sig = hasattr(part, 'thought_signature') and part.thought_signature
                debug_logger.debug(f"part[{i}] {part.function_call.name} sig={'YES' if has_sig else 'NO'}")

        # Convert to normalized FunctionCall
        func_calls = [
            FunctionCall(name=fc.name, args=dict(fc.args) if fc.args else {}, raw=fc)
            for fc in response.function_calls
        ]
        return func_calls, response.text or ""

    def _append_tool_results(self, context: dict, func_calls: list[FunctionCall], results: list[str]):
        # Track if verify_answer was called -> switch to AUTO mode next iteration
        if any(fc.name == "verify_answer" for fc in func_calls):
            self._verification_called = True

        parts = [
            types.Part.from_function_response(name=fc.name, response={"result": results[i]})
            for i, fc in enumerate(func_calls)
        ]
        context["contents"].append(types.Content(role="user", parts=parts))

    # === Context compaction methods ===
    def _estimate_context_tokens(self, context: dict) -> int:
        """Use Gemini count_tokens API for accurate estimation."""
        try:
            result = self.client.models.count_tokens(
                model=MODEL_ID,
                contents=context["contents"],
            )
            return result.total_tokens
        except Exception as e:
            debug_logger.warning(f"count_tokens failed, using fallback: {e}")
            # Fallback to char estimation
            total = 0
            for content in context["contents"]:
                for part in content.parts:
                    if hasattr(part, "text") and part.text:
                        total += len(part.text) // 4
            return total

    def _get_context_length(self, context: dict) -> int:
        """Get number of content items in Gemini context."""
        return len(context["contents"])

    def _extract_context_section(self, context: dict, start_idx: int, end_idx: int) -> list:
        """Extract raw content items from context."""
        return context["contents"][start_idx:end_idx]

    def _item_to_xml(self, item) -> str:
        """Convert Gemini Content to XML for compaction."""
        xml = ""
        role = item.role if hasattr(item, "role") else "unknown"

        for part in item.parts:
            if hasattr(part, "function_call") and part.function_call:
                fc = part.function_call
                args_str = str(dict(fc.args))[:500] if fc.args else ""
                xml += f'  <tool-call name="{fc.name}">{args_str}</tool-call>\n'
            elif hasattr(part, "function_response") and part.function_response:
                fr = part.function_response
                result = ""
                if hasattr(fr, "response") and fr.response:
                    result = str(fr.response.get("result", ""))[:1000]
                xml += f'  <tool-result name="{fr.name}">{result}</tool-result>\n'
            elif hasattr(part, "text") and part.text:
                text = part.text[:1000]
                xml += f'  <{role}>{text}</{role}>\n'
        return xml

    def _find_pair_boundaries(self, contents: list) -> list[int]:
        """Find indices where tool call+response pairs start.

        In Gemini, a pair = model Content with function_calls + user Content with function_responses.
        Returns list of start indices for each pair.
        """
        boundaries = []
        i = 0
        while i < len(contents):
            content = contents[i]
            # Check if this is a model response with function calls
            is_model_with_calls = (
                hasattr(content, "role") and content.role == "model" and
                hasattr(content, "parts") and
                any(hasattr(p, "function_call") and p.function_call for p in content.parts)
            )
            if is_model_with_calls:
                boundaries.append(i)
                i += 1
                # Skip the corresponding user Content with function_responses
                if i < len(contents):
                    next_content = contents[i]
                    if (hasattr(next_content, "role") and next_content.role == "user" and
                        hasattr(next_content, "parts") and
                        any(hasattr(p, "function_response") and p.function_response for p in next_content.parts)):
                        i += 1
            else:
                i += 1
        return boundaries

    def _rebuild_context_with_summary(self, context: dict, summary: str, keep_recent: int) -> dict:
        """Rebuild Gemini context with summary replacing middle section.

        Tool call + response = atomic pair, never split.
        keep_recent = number of pairs to keep in native format.
        """
        contents = context["contents"]

        head = contents[:1]  # Initial task
        rest = contents[1:]  # Everything after head

        # Find pair boundaries in rest
        pair_starts = self._find_pair_boundaries(rest)

        if len(pair_starts) <= keep_recent:
            # Not enough pairs to compact, keep as-is
            return context

        # Split into middle (to summarize) and tail (to keep native)
        tail_start_idx = pair_starts[-keep_recent] if keep_recent > 0 else len(rest)
        tail = rest[tail_start_idx:]  # Complete pairs, native format

        # Create compacted summary as user message
        summary_content = types.Content(
            role="user",
            parts=[types.Part.from_text(
                text=f'<compacted-history note="You already executed these tools. This is a summary of what happened.">\n{summary}\n</compacted-history>\n\nContinue from where you left off.'
            )]
        )

        new_context = context.copy()
        new_context["contents"] = head + [summary_content] + tail
        return new_context
