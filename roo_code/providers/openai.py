"""OpenAI provider implementation"""

from typing import Any, Dict, List, Optional, AsyncIterator
from openai import AsyncOpenAI
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


class OpenAIProvider(BaseProvider):
    """Provider for OpenAI API"""

    MODEL_INFO = {
        "gpt-4": ModelInfo(
            max_tokens=8192,
            context_window=8192,
            supports_images=False,
            supports_prompt_cache=False,
            input_price=30.00,
            output_price=60.00,
        ),
        "gpt-4-turbo": ModelInfo(
            max_tokens=4096,
            context_window=128000,
            supports_images=True,
            supports_prompt_cache=False,
            input_price=10.00,
            output_price=30.00,
        ),
        "gpt-4o": ModelInfo(
            max_tokens=4096,
            context_window=128000,
            supports_images=True,
            supports_prompt_cache=False,
            input_price=5.00,
            output_price=15.00,
        ),
        "gpt-4o-mini": ModelInfo(
            max_tokens=16384,
            context_window=128000,
            supports_images=True,
            supports_prompt_cache=False,
            input_price=0.15,
            output_price=0.60,
        ),
        "gpt-3.5-turbo": ModelInfo(
            max_tokens=4096,
            context_window=16385,
            supports_images=False,
            supports_prompt_cache=False,
            input_price=0.50,
            output_price=1.50,
        ),
    }

    def __init__(self, settings: ProviderSettings):
        """
        Initialize OpenAI provider

        Args:
            settings: Provider configuration settings
        """
        super().__init__(settings)

        if not settings.api_key:
            raise ValueError("OpenAI API key is required")

        self.client = AsyncOpenAI(
            api_key=settings.api_key,
            base_url=settings.api_base_url,
        )

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
                context_window=8192,
                supports_images=False,
                supports_prompt_cache=False,
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
        Create a message with OpenAI

        Args:
            system_prompt: System prompt for the conversation
            messages: List of messages in the conversation
            metadata: Optional metadata for tracking
            tools: Optional list of tool definitions (not yet implemented for OpenAI)

        Returns:
            ApiStream: Streaming response
        """
        # Convert messages to OpenAI format
        openai_messages = [{"role": "system", "content": system_prompt}]

        for msg in messages:
            if isinstance(msg.content, str):
                openai_messages.append({"role": msg.role, "content": msg.content})
            else:
                # Handle content blocks
                content_blocks = []
                for block in msg.content:
                    if block.type == "text":
                        content_blocks.append({"type": "text", "text": block.text})
                    elif block.type == "image":
                        content_blocks.append(
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{block.source.media_type};base64,{block.source.data}"
                                },
                            }
                        )
                openai_messages.append({"role": msg.role, "content": content_blocks})

        # Create streaming request
        _, model_info = self.get_model()

        stream = await self.client.chat.completions.create(
            model=self.settings.api_model_id,
            messages=openai_messages,
            max_tokens=model_info.max_tokens or 4096,
            stream=True,
        )

        return ApiStream(self._convert_stream(stream))

    async def _convert_stream(self, stream) -> AsyncIterator[StreamChunk]:
        """
        Convert OpenAI stream to our StreamChunk format

        Args:
            stream: OpenAI chat completion stream

        Yields:
            StreamChunk: Converted stream chunks
        """
        try:
            content_index = 0
            started = False

            async for chunk in stream:
                if not started:
                    # Emit message start
                    yield MessageStart(
                        type="message_start",
                        message={
                            "id": chunk.id,
                            "model": chunk.model,
                            "role": "assistant",
                        },
                    )
                    # Emit content block start
                    yield ContentBlockStart(
                        type="content_block_start",
                        index=content_index,
                        content_block=TextContent(type="text", text=""),
                    )
                    started = True

                # Process deltas
                if chunk.choices and len(chunk.choices) > 0:
                    choice = chunk.choices[0]

                    if choice.delta and choice.delta.content:
                        yield ContentBlockDelta(
                            type="content_block_delta",
                            index=content_index,
                            delta=TextDelta(
                                type="text_delta",
                                text=choice.delta.content,
                            ),
                        )

                    # Check for finish
                    if choice.finish_reason:
                        yield ContentBlockStop(
                            type="content_block_stop",
                            index=content_index,
                        )
                        yield MessageDelta(
                            type="message_delta",
                            delta={"stop_reason": choice.finish_reason},
                            usage={"output_tokens": 0},  # OpenAI doesn't provide this in stream
                        )
                        yield MessageStop(type="message_stop")

        except Exception as e:
            yield StreamError(
                type="error",
                error={"message": str(e), "type": type(e).__name__},
            )