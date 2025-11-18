"""Anthropic Claude provider implementation"""

from typing import Any, Dict, List, Optional, AsyncIterator
import logging
from anthropic import AsyncAnthropic
from anthropic.types import ContentBlock, Message, MessageStreamEvent

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
    ToolUseContent,
    ToolResultContent,
    StreamError,
)
from ..stream import ApiStream
from .base import BaseProvider


class AnthropicProvider(BaseProvider):
    """Provider for Anthropic Claude API"""

    # Model information for Claude models
    MODEL_INFO = {
        "claude-3-5-sonnet-20241022": ModelInfo(
            max_tokens=8192,
            context_window=200000,
            supports_images=True,
            supports_prompt_cache=True,
            input_price=3.00,
            output_price=15.00,
            cache_writes_price=3.75,
            cache_reads_price=0.30,
        ),
        "claude-sonnet-4-5": ModelInfo(
            max_tokens=8192,
            context_window=200000,
            supports_images=True,
            supports_prompt_cache=True,
            input_price=3.00,
            output_price=15.00,
            cache_writes_price=3.75,
            cache_reads_price=0.30,
        ),
        "claude-3-5-sonnet-20240620": ModelInfo(
            max_tokens=8192,
            context_window=200000,
            supports_images=True,
            supports_prompt_cache=True,
            input_price=3.00,
            output_price=15.00,
            cache_writes_price=3.75,
            cache_reads_price=0.30,
        ),
        "claude-3-opus-20240229": ModelInfo(
            max_tokens=4096,
            context_window=200000,
            supports_images=True,
            supports_prompt_cache=True,
            input_price=15.00,
            output_price=75.00,
            cache_writes_price=18.75,
            cache_reads_price=1.50,
        ),
        "claude-3-sonnet-20240229": ModelInfo(
            max_tokens=4096,
            context_window=200000,
            supports_images=True,
            supports_prompt_cache=True,
            input_price=3.00,
            output_price=15.00,
            cache_writes_price=3.75,
            cache_reads_price=0.30,
        ),
        "claude-3-haiku-20240307": ModelInfo(
            max_tokens=4096,
            context_window=200000,
            supports_images=True,
            supports_prompt_cache=True,
            input_price=0.25,
            output_price=1.25,
            cache_writes_price=0.30,
            cache_reads_price=0.03,
        ),
    }

    def __init__(self, settings: ProviderSettings):
        """
        Initialize Anthropic provider

        Args:
            settings: Provider configuration settings
        """
        super().__init__(settings)

        if not settings.api_key:
            raise ValueError("Anthropic API key is required")

        self.client = AsyncAnthropic(
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
                context_window=200000,
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
        Create a message with Claude

        Args:
            system_prompt: System prompt for the conversation
            messages: List of messages in the conversation
            metadata: Optional metadata for tracking
            tools: Optional list of tool definitions for the AI to use

        Returns:
            ApiStream: Streaming response
        """
        # Convert messages to Anthropic format
        logging.info(f"API_REQUEST: Converting {len(messages)} messages to Anthropic format")
        anthropic_messages = []
        for idx, msg in enumerate(messages):
            if isinstance(msg.content, str):
                logging.debug(f"API_REQUEST: Message {idx} ({msg.role}): text content ({len(msg.content)} chars)")
                anthropic_messages.append(
                    {"role": msg.role, "content": msg.content}
                )
            else:
                # Handle content blocks
                logging.debug(f"API_REQUEST: Message {idx} ({msg.role}): {len(msg.content)} content blocks")
                content_blocks = []
                for block_idx, block in enumerate(msg.content):
                    if block.type == "text":
                        content_blocks.append({"type": "text", "text": block.text})
                        logging.debug(f"API_REQUEST:   Message {idx}, Block {block_idx}: text ({len(block.text)} chars)")
                    elif block.type == "image":
                        content_blocks.append(
                            {
                                "type": "image",
                                "source": {
                                    "type": block.source.type,
                                    "media_type": block.source.media_type,
                                    "data": block.source.data,
                                },
                            }
                        )
                        logging.debug(f"API_REQUEST:   Message {idx}, Block {block_idx}: image")
                    elif block.type == "tool_use":
                        # Include tool_use blocks in assistant messages
                        content_blocks.append({
                            "type": "tool_use",
                            "id": block.id,
                            "name": block.name,
                            "input": block.input,
                        })
                        logging.info(f"API_REQUEST:   Message {idx}, Block {block_idx}: tool_use - {block.name} (id: {block.id})")
                        logging.debug(f"API_REQUEST:   Tool input: {block.input}")
                    elif block.type == "tool_result":
                        # Include tool_result blocks in user messages
                        result_preview = str(block.content)[:200] + ("..." if len(str(block.content)) > 200 else "")
                        content_blocks.append({
                            "type": "tool_result",
                            "tool_use_id": block.tool_use_id,
                            "content": block.content,
                            "is_error": block.is_error,
                        })
                        logging.info(f"API_REQUEST:   Message {idx}, Block {block_idx}: tool_result for tool_use_id: {block.tool_use_id}, is_error: {block.is_error}")
                        logging.debug(f"API_REQUEST:   Result preview: {result_preview}")
                
                # DIAGNOSTIC: Log if content_blocks is empty
                if not content_blocks:
                    logging.warning(
                        f"API_REQUEST: Message {idx} ({msg.role}): Empty content_blocks after conversion. "
                        f"Original block types: {[b.type for b in msg.content]}"
                    )
                
                # VALIDATION: Only add messages with non-empty content
                # According to Anthropic API: all messages must have non-empty content
                # except for the optional final assistant message
                if content_blocks:
                    anthropic_messages.append(
                        {"role": msg.role, "content": content_blocks}
                    )
                    logging.debug(f"API_REQUEST: Message {idx} added with {len(content_blocks)} blocks")
                else:
                    logging.warning(
                        f"API_REQUEST: Skipping message {idx} ({msg.role}) with empty content to prevent API error"
                    )

        # Create streaming request
        _, model_info = self.get_model()

        # Build API call parameters
        api_params = {
            "model": self.settings.api_model_id,
            "max_tokens": model_info.max_tokens or 4096,
            "system": system_prompt,
            "messages": anthropic_messages,
            "stream": True,
        }
        
        # Add tools if provided
        if tools:
            api_params["tools"] = tools
            logging.info(f"API_REQUEST: Sending request with {len(tools)} tools available")
            logging.debug(f"API_REQUEST: Tool names: {[t.get('name', 'unknown') for t in tools]}")
        else:
            logging.info(f"API_REQUEST: Sending request without tools")
        
        logging.info(f"API_REQUEST: Calling Anthropic API with model '{self.settings.api_model_id}'")
        logging.debug(f"API_REQUEST: Total messages to API: {len(anthropic_messages)}, max_tokens: {api_params['max_tokens']}")
        
        stream = await self.client.messages.create(**api_params)
        
        logging.info(f"API_RESPONSE: Stream created successfully")

        return ApiStream(self._convert_stream(stream))

    async def _convert_stream(
        self, stream: AsyncIterator[MessageStreamEvent]
    ) -> AsyncIterator[StreamChunk]:
        """
        Convert Anthropic stream events to our StreamChunk format

        Args:
            stream: Anthropic message stream

        Yields:
            StreamChunk: Converted stream chunks
        """
        try:
            async for event in stream:
                if event.type == "message_start":
                    logging.debug(f"API_STREAM: message_start received")
                    yield MessageStart(
                        type="message_start",
                        message=event.message.model_dump(),
                    )

                elif event.type == "content_block_start":
                    if event.content_block.type == "text":
                        logging.debug(f"API_STREAM: content_block_start - text at index {event.index}")
                        yield ContentBlockStart(
                            type="content_block_start",
                            index=event.index,
                            content_block=TextContent(
                                type="text",
                                text=event.content_block.text,
                            ),
                        )
                    elif event.content_block.type == "tool_use":
                        logging.info(f"API_STREAM: content_block_start - tool_use '{event.content_block.name}' at index {event.index} (id: {event.content_block.id})")
                        logging.debug(f"API_STREAM: Tool input: {event.content_block.input}")
                        yield ContentBlockStart(
                            type="content_block_start",
                            index=event.index,
                            content_block=ToolUseContent(
                                type="tool_use",
                                id=event.content_block.id,
                                name=event.content_block.name,
                                input=event.content_block.input,
                            ),
                        )

                elif event.type == "content_block_delta":
                    if event.delta.type == "text_delta":
                        logging.debug(f"API_STREAM: content_block_delta - text_delta at index {event.index} ({len(event.delta.text)} chars)")
                        yield ContentBlockDelta(
                            type="content_block_delta",
                            index=event.index,
                            delta=TextDelta(
                                type="text_delta",
                                text=event.delta.text,
                            ),
                        )
                    elif event.delta.type == "input_json_delta":
                        # Tool input is streamed as JSON chunks that need to be accumulated
                        from ..types import InputJsonDelta
                        logging.debug(f"API_STREAM: content_block_delta - input_json_delta at index {event.index} ({len(event.delta.partial_json)} chars)")
                        yield ContentBlockDelta(
                            type="content_block_delta",
                            index=event.index,
                            delta=InputJsonDelta(
                                type="input_json_delta",
                                partial_json=event.delta.partial_json,
                            ),
                        )

                elif event.type == "content_block_stop":
                    logging.debug(f"API_STREAM: content_block_stop at index {event.index}")
                    yield ContentBlockStop(
                        type="content_block_stop",
                        index=event.index,
                    )

                elif event.type == "message_delta":
                    logging.debug(f"API_STREAM: message_delta - usage: {event.usage.model_dump()}")
                    yield MessageDelta(
                        type="message_delta",
                        delta=event.delta.model_dump(),
                        usage=event.usage.model_dump(),
                    )

                elif event.type == "message_stop":
                    logging.info(f"API_STREAM: message_stop - stream completed")
                    yield MessageStop(type="message_stop")

        except Exception as e:
            logging.error(f"API_STREAM: Stream error - {type(e).__name__}: {str(e)}")
            yield StreamError(
                type="error",
                error={"message": str(e), "type": type(e).__name__},
            )

    async def count_tokens(self, content: List[ContentBlock]) -> int:
        """
        Count tokens using Anthropic's native token counting

        Args:
            content: List of content blocks

        Returns:
            int: Token count
        """
        try:
            # Use Anthropic's count_tokens method if available
            token_count = await self.client.messages.count_tokens(
                model=self.settings.api_model_id,
                messages=[{"role": "user", "content": content}],
            )
            return token_count.input_tokens
        except Exception:
            # Fall back to tiktoken-based counting
            return await super().count_tokens(content)