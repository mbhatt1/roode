"""Streaming API response handling"""

import json
from typing import AsyncIterator, List, Optional
from .types import StreamChunk, ContentBlock, TextContent, ToolUseContent, InputJsonDelta


class ApiStream:
    """Handles streaming API responses"""

    def __init__(self, stream: AsyncIterator[StreamChunk]):
        """
        Initialize API stream

        Args:
            stream: Async iterator of stream chunks
        """
        self._stream = stream
        self._content_blocks: List[ContentBlock] = []
        self._stop_reason: Optional[str] = None
        self._usage = {"input_tokens": 0, "output_tokens": 0}

    async def stream(self) -> AsyncIterator[StreamChunk]:
        """
        Stream response chunks

        Yields:
            StreamChunk: Individual chunks from the API response
        """
        async for chunk in self._stream:
            # Track content blocks
            if chunk.type == "content_block_start":
                self._content_blocks.append(chunk.content_block)
            elif chunk.type == "content_block_delta":
                if chunk.index < len(self._content_blocks):
                    block = self._content_blocks[chunk.index]
                    if isinstance(block, TextContent) and hasattr(chunk.delta, 'text'):
                        # Accumulate text for TextContent blocks
                        block.text += chunk.delta.text
                    elif isinstance(block, ToolUseContent) and isinstance(chunk.delta, InputJsonDelta):
                        # Accumulate JSON input for ToolUseContent blocks
                        # The partial_json contains incremental JSON chunks that build up the full input
                        if not hasattr(block, '_input_json_buffer'):
                            block._input_json_buffer = ""
                        block._input_json_buffer += chunk.delta.partial_json
                        # Try to parse the accumulated JSON to update the input
                        try:
                            block.input = json.loads(block._input_json_buffer)
                        except json.JSONDecodeError:
                            # JSON is still incomplete, continue accumulating
                            pass

            # Track usage and stop reason
            elif chunk.type == "message_delta":
                if hasattr(chunk, "usage") and chunk.usage:
                    self._usage["output_tokens"] = chunk.usage.output_tokens
                if "stop_reason" in chunk.delta:
                    self._stop_reason = chunk.delta["stop_reason"]

            elif chunk.type == "message_start":
                if "usage" in chunk.message:
                    usage = chunk.message["usage"]
                    if "input_tokens" in usage:
                        self._usage["input_tokens"] = usage["input_tokens"]

            yield chunk

    async def get_final_message(self) -> dict:
        """
        Consume the entire stream and return the final message

        Returns:
            dict: Final message with content, stop_reason, and usage
        """
        async for _ in self.stream():
            pass

        return {
            "content": self._content_blocks,
            "stop_reason": self._stop_reason,
            "usage": self._usage,
        }

    async def get_text(self) -> str:
        """
        Consume the entire stream and return concatenated text

        Returns:
            str: Complete text response
        """
        result = await self.get_final_message()
        text_parts = []

        for block in result["content"]:
            if isinstance(block, TextContent):
                text_parts.append(block.text)

        return "".join(text_parts)

    @property
    def content_blocks(self) -> List[ContentBlock]:
        """Get accumulated content blocks"""
        return self._content_blocks

    @property
    def stop_reason(self) -> Optional[str]:
        """Get stop reason"""
        return self._stop_reason

    @property
    def usage(self) -> dict:
        """Get token usage statistics"""
        return self._usage

    def get_tool_uses(self) -> List[ToolUseContent]:
        """Get all tool use content blocks from the message."""
        return [block for block in self._content_blocks if isinstance(block, ToolUseContent)]