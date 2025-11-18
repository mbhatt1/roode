"""
End-to-end integration test for tool execution flow.

This test verifies the complete tool execution flow from tool registration
through API call to tool execution, simulating realistic Anthropic API responses.
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from typing import Dict, Any, AsyncIterator, List
from roo_code.agent import Agent
from roo_code.tools import ToolRegistry, Tool, FunctionTool, ToolInputSchema
from roo_code.client import RooClient
from roo_code.types import (
    ProviderSettings,
    ApiProvider,
    ToolUseContent,
    ContentBlockStart,
    TextContent,
    ContentBlockDelta,
    TextDelta,
    MessageParam,
)
from roo_code.stream import ApiStream
from pydantic import BaseModel, Field


class CalculatorInput(BaseModel):
    """Input for calculator tool"""
    a: int = Field(..., description="First number")
    b: int = Field(..., description="Second number")


async def calculator_handler(a: int, b: int) -> str:
    """Add two numbers"""
    return str(a + b)


class MockUsage:
    """Mock usage object"""
    def __init__(self, output_tokens: int):
        self.output_tokens = output_tokens


class MockStreamChunk:
    """Mock streaming chunk for testing"""
    def __init__(self, chunk_type: str, **kwargs):
        self.type = chunk_type
        for key, value in kwargs.items():
            setattr(self, key, value)


async def create_mock_stream_with_tool_use(
    tool_id: str = "toolu_123",
    tool_name: str = "calculator",
    tool_input: Dict[str, Any] = None
) -> AsyncIterator[MockStreamChunk]:
    """
    Create a mock streaming response that includes a tool_use block.
    
    Simulates realistic Anthropic API streaming response with tool use.
    """
    if tool_input is None:
        tool_input = {"a": 5, "b": 3}
    
    # Message start
    yield MockStreamChunk(
        "message_start",
        message={
            "id": "msg_123",
            "type": "message",
            "role": "assistant",
            "content": [],
            "model": "claude-sonnet-4-5",
            "usage": {"input_tokens": 100, "output_tokens": 0}
        }
    )
    
    # Text content block start
    yield MockStreamChunk(
        "content_block_start",
        index=0,
        content_block=TextContent(type="text", text="")
    )
    
    # Text delta - thinking before tool use
    yield MockStreamChunk(
        "content_block_delta",
        index=0,
        delta=TextDelta(type="text_delta", text="Let me calculate that for you.")
    )
    
    # Text content block stop
    yield MockStreamChunk(
        "content_block_stop",
        index=0
    )
    
    # Tool use content block start
    yield MockStreamChunk(
        "content_block_start",
        index=1,
        content_block=ToolUseContent(
            type="tool_use",
            id=tool_id,
            name=tool_name,
            input=tool_input
        )
    )
    
    # Tool use content block stop
    yield MockStreamChunk(
        "content_block_stop",
        index=1
    )
    
    # Message delta with stop reason
    yield MockStreamChunk(
        "message_delta",
        delta={"stop_reason": "tool_use"},
        usage=MockUsage(output_tokens=50)
    )
    
    # Message stop
    yield MockStreamChunk(
        "message_stop"
    )


async def create_mock_stream_text_only(text: str = "Task completed!") -> AsyncIterator[MockStreamChunk]:
    """Create a mock streaming response with only text (no tool use)"""
    
    # Message start
    yield MockStreamChunk(
        "message_start",
        message={
            "id": "msg_456",
            "type": "message",
            "role": "assistant",
            "content": [],
            "model": "claude-sonnet-4-5",
            "usage": {"input_tokens": 50, "output_tokens": 0}
        }
    )
    
    # Text content block start
    yield MockStreamChunk(
        "content_block_start",
        index=0,
        content_block=TextContent(type="text", text="")
    )
    
    # Text delta
    yield MockStreamChunk(
        "content_block_delta",
        index=0,
        delta=TextDelta(type="text_delta", text=text)
    )
    
    # Text content block stop
    yield MockStreamChunk(
        "content_block_stop",
        index=0
    )
    
    # Message delta with stop reason
    yield MockStreamChunk(
        "message_delta",
        delta={"stop_reason": "end_turn"},
        usage=MockUsage(output_tokens=20)
    )
    
    # Message stop
    yield MockStreamChunk(
        "message_stop"
    )


@pytest.mark.asyncio
class TestToolExecutionIntegration:
    """Integration tests for complete tool execution flow"""
    
    async def test_complete_tool_execution_flow(self):
        """Test end-to-end tool execution from registration to execution"""
        
        # Track tool execution
        tool_executed = False
        execution_params = {}
        
        async def tracked_calculator(a: int, b: int) -> str:
            """Calculator that tracks execution"""
            nonlocal tool_executed, execution_params
            tool_executed = True
            execution_params = {"a": a, "b": b}
            return str(a + b)
        
        # 1. Set up agent with tool registry
        calculator_tool = FunctionTool(
            name="calculator",
            description="Add two numbers together",
            function=tracked_calculator,
            input_schema=ToolInputSchema(
                type="object",
                properties={
                    "a": {"type": "integer", "description": "First number"},
                    "b": {"type": "integer", "description": "Second number"}
                },
                required=["a", "b"]
            )
        )
        
        # Create client with mock settings
        client = RooClient(
            provider_settings=ProviderSettings(
                api_provider=ApiProvider.ANTHROPIC,
                api_key="test-key",
                api_model_id="claude-sonnet-4-5"
            )
        )
        
        # 2. Create agent with calculator tool
        agent = Agent(client=client, tools=[calculator_tool])
        
        # Verify tool is registered
        assert agent.tool_registry.get("calculator") is not None
        tool_defs = agent.tool_registry.get_tool_definitions()
        assert len(tool_defs) == 1
        assert tool_defs[0]["name"] == "calculator"
        
        # 3. Mock the client's create_message to capture API call and return tool_use
        captured_tools = None
        call_count = [0]
        
        async def mock_create_message(
            system_prompt: str,
            messages: List[MessageParam],
            metadata=None,
            tools=None,
            **kwargs
        ):
            """Mock create_message that captures tools parameter"""
            nonlocal captured_tools
            call_count[0] += 1
            
            # Capture the tools parameter
            if call_count[0] == 1:
                captured_tools = tools
                # First call: return tool_use response
                stream = create_mock_stream_with_tool_use(
                    tool_id="toolu_123",
                    tool_name="calculator",
                    tool_input={"a": 5, "b": 3}
                )
            else:
                # Second call after tool execution: return final text
                stream = create_mock_stream_text_only("The sum is 8!")
            
            return ApiStream(stream)
        
        # Patch the client's create_message method
        with patch.object(client, 'create_message', side_effect=mock_create_message):
            # 4. Run agent with a task
            result = await agent.run("What is 5 + 3?", on_iteration=None)
            
            # 5. Verify all stages of the flow
            
            # a) Tools were sent to API
            assert captured_tools is not None, "Tools were not passed to create_message"
            assert len(captured_tools) == 1, "Expected 1 tool definition"
            assert captured_tools[0]["name"] == "calculator"
            assert captured_tools[0]["description"] == "Add two numbers together"
            assert "input_schema" in captured_tools[0]
            print("✓ Tools sent to API")
            
            # b) Tool was executed
            assert tool_executed, "Tool was not executed"
            assert execution_params == {"a": 5, "b": 3}, f"Tool executed with wrong params: {execution_params}"
            print("✓ Tool executed with correct parameters")
            
            # c) Agent completed the task
            assert "8" in result or "sum" in result.lower()
            print("✓ Agent completed task successfully")
            print(f"  Final result: {result}")
    
    async def test_tool_definitions_sent_to_api(self):
        """Verify tool definitions are correctly formatted and included in API request"""
        
        # Create a tool with complex schema
        def complex_tool(
            operation: str,
            numbers: List[int],
            precision: int = 2
        ) -> str:
            """Perform operations on numbers"""
            return "result"
        
        tool = FunctionTool(
            name="math_operations",
            description="Perform various mathematical operations",
            function=complex_tool,
            input_schema=ToolInputSchema(
                type="object",
                properties={
                    "operation": {
                        "type": "string",
                        "enum": ["sum", "product", "average"],
                        "description": "The operation to perform"
                    },
                    "numbers": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "List of numbers"
                    },
                    "precision": {
                        "type": "integer",
                        "description": "Decimal precision",
                        "default": 2
                    }
                },
                required=["operation", "numbers"]
            )
        )
        
        # Create client and agent
        client = RooClient(
            provider_settings=ProviderSettings(
                api_provider=ApiProvider.ANTHROPIC,
                api_key="test-key",
                api_model_id="claude-sonnet-4-5"
            )
        )
        agent = Agent(client=client, tools=[tool])
        
        # Capture tools parameter
        captured_tools = None
        
        async def mock_create_message(
            system_prompt: str,
            messages: List[MessageParam],
            metadata=None,
            tools=None,
            **kwargs
        ):
            nonlocal captured_tools
            captured_tools = tools
            # Return simple text response (no tool use)
            return ApiStream(create_mock_stream_text_only("Done"))
        
        with patch.object(client, 'create_message', side_effect=mock_create_message):
            await agent.run("Test task")
            
            # Verify tool definitions structure
            assert captured_tools is not None
            assert len(captured_tools) == 1
            
            tool_def = captured_tools[0]
            assert tool_def["name"] == "math_operations"
            assert tool_def["description"] == "Perform various mathematical operations"
            assert "input_schema" in tool_def
            
            schema = tool_def["input_schema"]
            assert schema["type"] == "object"
            assert "properties" in schema
            assert "operation" in schema["properties"]
            assert "numbers" in schema["properties"]
            assert "required" in schema
            assert "operation" in schema["required"]
            assert "numbers" in schema["required"]
            
            print("✓ Tool definition correctly formatted")
            print(f"  Schema properties: {list(schema['properties'].keys())}")
            print(f"  Required fields: {schema['required']}")
    
    async def test_multiple_tools_registration(self):
        """Test registering and using multiple tools"""
        
        # Create multiple tools
        def add(a: int, b: int) -> str:
            return str(a + b)
        
        def multiply(a: int, b: int) -> str:
            return str(a * b)
        
        add_tool = FunctionTool(
            name="add",
            description="Add two numbers",
            function=add,
            input_schema=ToolInputSchema(
                type="object",
                properties={
                    "a": {"type": "integer"},
                    "b": {"type": "integer"}
                },
                required=["a", "b"]
            )
        )
        
        multiply_tool = FunctionTool(
            name="multiply",
            description="Multiply two numbers",
            function=multiply,
            input_schema=ToolInputSchema(
                type="object",
                properties={
                    "a": {"type": "integer"},
                    "b": {"type": "integer"}
                },
                required=["a", "b"]
            )
        )
        
        # Create agent with multiple tools
        client = RooClient(
            provider_settings=ProviderSettings(
                api_provider=ApiProvider.ANTHROPIC,
                api_key="test-key",
                api_model_id="claude-sonnet-4-5"
            )
        )
        agent = Agent(client=client, tools=[add_tool, multiply_tool])
        
        # Verify both tools are registered
        assert agent.tool_registry.get("add") is not None
        assert agent.tool_registry.get("multiply") is not None
        
        tool_defs = agent.tool_registry.get_tool_definitions()
        assert len(tool_defs) == 2
        
        tool_names = [t["name"] for t in tool_defs]
        assert "add" in tool_names
        assert "multiply" in tool_names
        
        print("✓ Multiple tools registered successfully")
        print(f"  Registered tools: {tool_names}")
    
    async def test_tool_use_parsing_from_stream(self):
        """Test that tool_use blocks are correctly parsed from streaming response"""
        
        # Create mock stream with tool use
        stream = create_mock_stream_with_tool_use(
            tool_id="toolu_xyz",
            tool_name="test_tool",
            tool_input={"param1": "value1", "param2": 42}
        )
        
        # Create ApiStream and consume it
        api_stream = ApiStream(stream)
        final_message = await api_stream.get_final_message()
        
        # Verify content blocks
        assert len(final_message["content"]) == 2
        
        # First block should be text
        assert isinstance(final_message["content"][0], TextContent)
        assert "calculate" in final_message["content"][0].text.lower()
        
        # Second block should be tool_use
        assert isinstance(final_message["content"][1], ToolUseContent)
        tool_use = final_message["content"][1]
        assert tool_use.id == "toolu_xyz"
        assert tool_use.name == "test_tool"
        assert tool_use.input == {"param1": "value1", "param2": 42}
        
        # Verify get_tool_uses method
        tool_uses = api_stream.get_tool_uses()
        assert len(tool_uses) == 1
        assert tool_uses[0].name == "test_tool"
        
        print("✓ Tool use correctly parsed from stream")
        print(f"  Tool ID: {tool_use.id}")
        print(f"  Tool name: {tool_use.name}")
        print(f"  Tool input: {tool_use.input}")
    
    async def test_tool_result_returned_correctly(self):
        """Test that tool results are properly formatted and returned"""
        
        # Create a tool that returns a specific result
        def get_weather(location: str) -> str:
            return f"Weather in {location}: 72°F, Sunny"
        
        weather_tool = FunctionTool(
            name="get_weather",
            description="Get weather for a location",
            function=get_weather,
            input_schema=ToolInputSchema(
                type="object",
                properties={
                    "location": {"type": "string"}
                },
                required=["location"]
            )
        )
        
        # Test tool registry execution
        registry = ToolRegistry()
        registry.register(weather_tool)
        
        # Create a ToolUse object
        from roo_code.tools import ToolUse
        tool_use = ToolUse(
            id="toolu_weather_123",
            name="get_weather",
            input={"location": "San Francisco"}
        )
        
        # Execute the tool
        result = await registry.execute(tool_use)
        
        # Verify result
        assert result.tool_use_id == "toolu_weather_123"
        assert not result.is_error
        assert "San Francisco" in result.content
        assert "72°F" in result.content
        assert "Sunny" in result.content
        
        print("✓ Tool result correctly formatted")
        print(f"  Result content: {result.content}")
        print(f"  Is error: {result.is_error}")


if __name__ == "__main__":
    """Run tests with detailed output"""
    import asyncio
    
    async def run_tests():
        test_suite = TestToolExecutionIntegration()
        
        print("=" * 70)
        print("INTEGRATION TEST: End-to-End Tool Execution")
        print("=" * 70)
        
        print("\n[Test 1/5] Complete tool execution flow...")
        try:
            await test_suite.test_complete_tool_execution_flow()
            print("✅ PASSED\n")
        except AssertionError as e:
            print(f"❌ FAILED: {e}\n")
        
        print("[Test 2/5] Tool definitions sent to API...")
        try:
            await test_suite.test_tool_definitions_sent_to_api()
            print("✅ PASSED\n")
        except AssertionError as e:
            print(f"❌ FAILED: {e}\n")
        
        print("[Test 3/5] Multiple tools registration...")
        try:
            await test_suite.test_multiple_tools_registration()
            print("✅ PASSED\n")
        except AssertionError as e:
            print(f"❌ FAILED: {e}\n")
        
        print("[Test 4/5] Tool use parsing from stream...")
        try:
            await test_suite.test_tool_use_parsing_from_stream()
            print("✅ PASSED\n")
        except AssertionError as e:
            print(f"❌ FAILED: {e}\n")
        
        print("[Test 5/5] Tool result returned correctly...")
        try:
            await test_suite.test_tool_result_returned_correctly()
            print("✅ PASSED\n")
        except AssertionError as e:
            print(f"❌ FAILED: {e}\n")
        
        print("=" * 70)
        print("INTEGRATION TEST COMPLETE")
        print("=" * 70)
    
    asyncio.run(run_tests())