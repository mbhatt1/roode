"""Google Gemini provider implementation"""

from typing import Any, Dict, List, Optional, AsyncIterator
import httpx
from anthropic.types import ContentBlock

from ..types import (
    ModelInfo,
    ProviderSettings,
    MessageParam,
    ApiHandlerCreateMessageMetadata,
    StreamChunk,
    ContentBlockDelta,
    ContentBlockStart,
    ContentBlockStop,
    MessageStart,
    MessageDelta,
    MessageStop,
    TextDelta,
    TextContent,
    StreamError,
)
from ..stream import ApiStream
from .base import BaseProvider


class GeminiProvider(BaseProvider):
    """Provider for Google Gemini API"""

    MODEL_INFO = {
        "gemini-2.0-flash-exp": ModelInfo(
            max_tokens=8192,
            context_window=1048576,
            supports_images=True,
            supports_prompt_cache=False,
            input_price=0.00,
            output_price=0.00,
        ),
        "gemini-exp-1206": ModelInfo(
            max_tokens=8192,
            context_window=2097152,
            supports_images=True,
            supports_prompt_cache=False,
            input_price=0.00,
            output_price=0.00,
        ),
        "gemini-1.5-pro": ModelInfo(
            max_tokens=8192,
            context_window=2097152,
            supports_images=True,
            supports_prompt_cache=True,
            input_price=1.25,
            output_price=5.00,
            cache_writes_price=1.25,
            cache_reads_price=0.3125,
        ),
        "gemini-1.5-flash": ModelInfo(
            max_tokens=8192,
            context_window=1048576,
            supports_images=True,
            supports_prompt_cache=True,
            input_price=0.075,
            output_price=0.30,
            cache_writes_price=0.075,
            cache_reads_price=0.01875,
        ),
        "gemini-1.5-flash-8b": ModelInfo(
            max_tokens=8192,
            context_window=1048576,
            supports_images=True,
            supports_prompt_cache=True,
            input_price=0.0375,
            output_price=0.15,
            cache_writes_price=0.0375,
            cache_reads_price=0.009375,
        ),
    }

    def __init__(self, settings: ProviderSettings):
        """
        Initialize Gemini provider

        Args:
            settings: Provider configuration settings
        """
        super().__init__(settings)

        if not settings.api_key:
            raise ValueError("Gemini API key is required")

        self.base_url = settings.api_base_url or "https://generativelanguage.googleapis.com/v1beta"
        self.client = httpx.AsyncClient(timeout=60.0)

    def get_model(self) -> tuple[str, ModelInfo]:
        """
        Get model ID and information

        Returns:
            tuple: (model_id, ModelInfo)
        """
        model_id = self.settings.api_model_id
        model_info = self.MODEL_INFO.get(
            model_id,
            ModelInfo(
                context_window=1048576,
                supports_images=True,
                supports_prompt_cache=True,
            ),
        )
        return model_id, model_info

    async def create_message(
        self,
        system_prompt: str,
        messages: List[MessageParam],
        metadata: Optional[ApiHandlerCreateMessageMetadata] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> ApiStream:
        """
        Create a message with Gemini

        Args:
            system_prompt: System prompt for the conversation
            messages: List of messages in the conversation
            metadata: Optional metadata for tracking
            tools: Optional list of tool definitions (not yet implemented for Gemini)

        Returns:
            ApiStream: Streaming response
        """
        # Convert messages to Gemini format
        gemini_messages = []
        
        # Add system instruction separately
        system_instruction = {"parts": [{"text": system_prompt}]}

        for msg in messages:
            parts = []
            if isinstance(msg.content, str):
                parts.append({"text": msg.content})
            else:
                for block in msg.content:
                    if block.type == "text":
                        parts.append({"text": block.text})
                    elif block.type == "image":
                        parts.append({
                            "inline_data": {
                                "mime_type": block.source.media_type,
                                "data": block.source.data,
                            }
                        })
            
            gemini_messages.append({
                "role": "user" if msg.role == "user" else "model",
                "parts": parts,
            })

        _, model_info = self.get_model()

        # Prepare request
        url = f"{self.base_url}/models/{self.settings.api_model_id}:streamGenerateContent"
        
        request_body = {
            "contents": gemini_messages,
            "systemInstruction": system_instruction,
            "generationConfig": {
                "maxOutputTokens": model_info.max_tokens or 8192,
                "temperature": 0.7,
            },
        }

        return ApiStream(self._stream_response(url, request_body))

    async def _stream_response(self, url: str, body: dict) -> AsyncIterator[StreamChunk]:
        """
        Stream Gemini API response

        Args:
            url: API endpoint URL
            body: Request body

        Yields:
            StreamChunk: Converted stream chunks
        """
        try:
            headers = {
                "Content-Type": "application/json",
                "x-goog-api-key": self.settings.api_key,
            }

            # Emit message start
            yield MessageStart(
                type="message_start",
                message={"id": "gemini-msg", "model": self.settings.api_model_id, "role": "assistant"},
            )

            content_index = 0
            started = False

            async with self.client.stream("POST", url, json=body, headers=headers) as response:
                response.raise_for_status()

                async for line in response.aiter_lines():
                    if not line or line.startswith("data: [DONE]"):
                        continue

                    if line.startswith("data: "):
                        line = line[6:]

                    try:
                        import json
                        chunk_data = json.loads(line)

                        if "candidates" in chunk_data:
                            for candidate in chunk_data["candidates"]:
                                if "content" in candidate and "parts" in candidate["content"]:
                                    for part in candidate["content"]["parts"]:
                                        if "text" in part:
                                            if not started:
                                                yield ContentBlockStart(
                                                    type="content_block_start",
                                                    index=content_index,
                                                    content_block=TextContent(type="text", text=""),
                                                )
                                                started = True

                                            yield ContentBlockDelta(
                                                type="content_block_delta",
                                                index=content_index,
                                                delta=TextDelta(type="text_delta", text=part["text"]),
                                            )

                                if "finishReason" in candidate and candidate["finishReason"]:
                                    yield ContentBlockStop(type="content_block_stop", index=content_index)
                                    yield MessageDelta(
                                        type="message_delta",
                                        delta={"stop_reason": candidate["finishReason"].lower()},
                                        usage={"output_tokens": 0},
                                    )
                                    yield MessageStop(type="message_stop")

                    except json.JSONDecodeError:
                        continue

        except Exception as e:
            yield StreamError(
                type="error",
                error={"message": str(e), "type": type(e).__name__},
            )

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.client.aclose()