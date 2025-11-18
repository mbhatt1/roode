"""
Unit tests for Anthropic tool parsing fix.

Tests that verify tool use blocks are properly parsed and stored in the streaming API.
"""

import pytest
from typing import AsyncIterator
from roo_code.types import (
    ContentBlockStart,
    TextContent,
    ToolUseContent,
    StreamChunk,
)
from roo_code.stream import ApiStream


class TestContentBlockStartValidation:
    """Test ContentBlockStart can accept both TextContent and ToolUseContent"""

    def test_content_block_start_accepts_text_content(self):
        """Test that ContentBlockStart accepts TextContent"""
        # Create a TextContent block
        text_content = TextContent(type="text", text="Hello, world!")
        
        # Create a ContentBlockStart with TextContent
        content_block_start = ContentBlockStart(
            type="content_block_start",
            index=0,
            content_block=text_content
        )
        
        # Assert it validates successfully
        assert content_block_start.type == "content_block_start"
        assert content_block_start.index == 0
        assert isinstance(content_block_start.content_block, TextContent)
        assert content_block_start.content_block.text == "Hello, world!"

    def test_content_block_start_accepts_tool_use_content(self):
        """Test that ContentBlockStart accepts ToolUseContent"""
        # Create a ToolUseContent block
        tool_use_content = ToolUseContent(
            type="tool_use",
            id="toolu_123456",
            name="read_file",
            input={"path": "test.py"}
        )
        
        # Create a ContentBlockStart with ToolUseContent
        content_block_start = ContentBlockStart(
            type="content_block_start",
            index=1,
            content_block=tool_use_content
        )
        
        # Assert it validates successfully
        assert content_block_start.type == "content_block_start"
        assert content_block_start.index == 1
        assert isinstance(content_block_start.content_block, ToolUseContent)
        assert content_block_start.content_block.id == "toolu_123456"
        assert content_block_start.content_block.name == "read_file"
        assert content_block_start.content_block.input == {"path": "test.py"}


class TestToolUseContentStructure:
    """Test ToolUseContent has the correct structure and validates properly"""

    def test_tool_use_content_structure(self):
        """Test that ToolUseContent has the correct structure"""
        # Create a ToolUseContent with all required fields
        tool_use = ToolUseContent(
            type="tool_use",
            id="toolu_abc123",
            name="execute_command",
            input={"command": "ls -la", "cwd": "/tmp"}
        )
        
        # Assert all fields are accessible and correct
        assert tool_use.type == "tool_use"
        assert tool_use.id == "toolu_abc123"
        assert tool_use.name == "execute_command"
        assert tool_use.input == {"command": "ls -la", "cwd": "/tmp"}

    def test_tool_use_content_with_complex_input(self):
        """Test that ToolUseContent handles complex input structures"""
        # Create a ToolUseContent with nested input
        tool_use = ToolUseContent(
            type="tool_use",
            id="toolu_xyz789",
            name="apply_diff",
            input={
                "path": "src/main.py",
                "diff": "<<<<<<< SEARCH\n...\n=======\n...\n>>>>>>> REPLACE",
                "metadata": {
                    "line_start": 10,
                    "line_end": 20
                }
            }
        )
        
        # Assert nested structures are preserved
        assert tool_use.input["path"] == "src/main.py"
        assert "metadata" in tool_use.input
        assert tool_use.input["metadata"]["line_start"] == 10


class TestApiStreamToolUseParsing:
    """Test that ApiStream properly stores and retrieves tool use blocks"""

    @pytest.mark.asyncio
    async def test_api_stream_stores_tool_use_blocks(self):
        """Test that ApiStream stores tool use blocks correctly"""
        
        # Create mock stream chunks
        async def mock_stream() -> AsyncIterator[StreamChunk]:
            # Yield a tool use content block start
            tool_use = ToolUseContent(
                type="tool_use",
                id="toolu_test123",
                name="write_to_file",
                input={"path": "output.txt", "content": "test"}
            )
            
            content_block_start = ContentBlockStart(
                type="content_block_start",
                index=0,
                content_block=tool_use
            )
            
            yield content_block_start
        
        # Create ApiStream with mock
        stream = ApiStream(mock_stream())
        
        # Consume the stream
        async for _ in stream.stream():
            pass
        
        # Assert get_tool_uses() returns the tool use block
        tool_uses = stream.get_tool_uses()
        assert len(tool_uses) == 1
        assert isinstance(tool_uses[0], ToolUseContent)
        assert tool_uses[0].id == "toolu_test123"
        assert tool_uses[0].name == "write_to_file"
        assert tool_uses[0].input == {"path": "output.txt", "content": "test"}

    @pytest.mark.asyncio
    async def test_api_stream_stores_multiple_tool_uses(self):
        """Test that ApiStream stores multiple tool use blocks"""
        
        async def mock_stream() -> AsyncIterator[StreamChunk]:
            # First tool use
            tool_use_1 = ToolUseContent(
                type="tool_use",
                id="toolu_1",
                name="read_file",
                input={"path": "input.txt"}
            )
            yield ContentBlockStart(
                type="content_block_start",
                index=0,
                content_block=tool_use_1
            )
            
            # Second tool use
            tool_use_2 = ToolUseContent(
                type="tool_use",
                id="toolu_2",
                name="write_to_file",
                input={"path": "output.txt", "content": "data"}
            )
            yield ContentBlockStart(
                type="content_block_start",
                index=1,
                content_block=tool_use_2
            )
        
        stream = ApiStream(mock_stream())
        async for _ in stream.stream():
            pass
        
        tool_uses = stream.get_tool_uses()
        assert len(tool_uses) == 2
        assert tool_uses[0].id == "toolu_1"
        assert tool_uses[0].name == "read_file"
        assert tool_uses[1].id == "toolu_2"
        assert tool_uses[1].name == "write_to_file"

    @pytest.mark.asyncio
    async def test_api_stream_mixed_content_blocks(self):
        """Test that ApiStream handles mixed text and tool use content blocks"""
        
        async def mock_stream() -> AsyncIterator[StreamChunk]:
            # Text content block
            text_content = TextContent(type="text", text="Processing...")
            yield ContentBlockStart(
                type="content_block_start",
                index=0,
                content_block=text_content
            )
            
            # Tool use content block
            tool_use = ToolUseContent(
                type="tool_use",
                id="toolu_mix",
                name="execute_command",
                input={"command": "echo test"}
            )
            yield ContentBlockStart(
                type="content_block_start",
                index=1,
                content_block=tool_use
            )
        
        stream = ApiStream(mock_stream())
        async for _ in stream.stream():
            pass
        
        # Check content blocks
        assert len(stream.content_blocks) == 2
        assert isinstance(stream.content_blocks[0], TextContent)
        assert isinstance(stream.content_blocks[1], ToolUseContent)
        
        # Check get_tool_uses only returns tool use blocks
        tool_uses = stream.get_tool_uses()
        assert len(tool_uses) == 1
        assert tool_uses[0].id == "toolu_mix"
        assert tool_uses[0].name == "execute_command"

    @pytest.mark.asyncio
    async def test_api_stream_empty_tool_uses(self):
        """Test that ApiStream returns empty list when no tool uses present"""
        
        async def mock_stream() -> AsyncIterator[StreamChunk]:
            # Only text content, no tool uses
            text_content = TextContent(type="text", text="Just text")
            yield ContentBlockStart(
                type="content_block_start",
                index=0,
                content_block=text_content
            )
        
        stream = ApiStream(mock_stream())
        async for _ in stream.stream():
            pass
        
        # Should return empty list
        tool_uses = stream.get_tool_uses()
        assert len(tool_uses) == 0
        assert tool_uses == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
