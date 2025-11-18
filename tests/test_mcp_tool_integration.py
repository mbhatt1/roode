"""Test MCP dynamic tool discovery and integration with Agent."""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from roo_code.builtin_tools.mcp_manager import McpManager
from roo_code.builtin_tools.mcp_client import McpClient, McpServer, McpTool, ServerStatus
from roo_code.builtin_tools.mcp import set_mcp_manager, get_mcp_manager
from roo_code.agent import Agent
from roo_code.client import RooClient
from roo_code.tools import ToolRegistry
from roo_code.types import ProviderSettings


@pytest.fixture
def mock_mcp_server():
    """Create a mock MCP server with tools."""
    server = McpServer(
        name="test_server",
        command="test",
        args=[],
        status=ServerStatus.CONNECTED
    )
    
    # Add some test tools
    server.tools = [
        McpTool(
            name="weather",
            description="Get weather information",
            input_schema={
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "City name"},
                    "units": {"type": "string", "enum": ["celsius", "fahrenheit"]}
                },
                "required": ["city"]
            },
            server_name="test_server"
        ),
        McpTool(
            name="calculator",
            description="Perform calculations",
            input_schema={
                "type": "object",
                "properties": {
                    "operation": {"type": "string", "enum": ["add", "subtract", "multiply", "divide"]},
                    "a": {"type": "number"},
                    "b": {"type": "number"}
                },
                "required": ["operation", "a", "b"]
            },
            server_name="test_server"
        )
    ]
    
    return server


@pytest.fixture
def mock_mcp_client(mock_mcp_server):
    """Create a mock MCP client."""
    client = Mock(spec=McpClient)
    client.server = mock_mcp_server
    client.is_connected.return_value = True
    return client


@pytest.fixture
async def mcp_manager_with_server(mock_mcp_client, mock_mcp_server):
    """Create MCP manager with a connected server."""
    manager = McpManager()
    manager.servers["test_server"] = mock_mcp_server
    manager.clients["test_server"] = mock_mcp_client
    
    # Set as global MCP manager
    set_mcp_manager(manager)
    
    yield manager
    
    # Cleanup
    set_mcp_manager(McpManager())


class TestMcpToolDiscovery:
    """Test MCP tool discovery and conversion."""
    
    @pytest.mark.asyncio
    async def test_get_mcp_tool_definitions(self, mcp_manager_with_server):
        """Test that MCP tools are converted to API tool definitions."""
        tool_defs = await mcp_manager_with_server.get_mcp_tool_definitions()
        
        assert len(tool_defs) == 2
        
        # Check weather tool
        weather_tool = next((t for t in tool_defs if "weather" in t["name"]), None)
        assert weather_tool is not None
        assert weather_tool["name"] == "test_server__weather"
        assert "weather information" in weather_tool["description"].lower()
        assert "city" in weather_tool["input_schema"]["properties"]
        assert weather_tool["input_schema"]["required"] == ["city"]
        
        # Check calculator tool  
        calc_tool = next((t for t in tool_defs if "calculator" in t["name"]), None)
        assert calc_tool is not None
        assert calc_tool["name"] == "test_server__calculator"
        assert "calculation" in calc_tool["description"].lower()
        assert "operation" in calc_tool["input_schema"]["properties"]
    
    @pytest.mark.asyncio
    async def test_tool_name_prefixing(self, mcp_manager_with_server):
        """Test that tool names are prefixed with server name to avoid conflicts."""
        tool_defs = await mcp_manager_with_server.get_mcp_tool_definitions()
        
        # All tools should have server prefix
        for tool_def in tool_defs:
            assert tool_def["name"].startswith("test_server__")
    
    @pytest.mark.asyncio
    async def test_empty_manager(self):
        """Test that empty manager returns empty list."""
        manager = McpManager()
        tool_defs = await manager.get_mcp_tool_definitions()
        assert tool_defs == []
    
    @pytest.mark.asyncio
    async def test_disconnected_server_excluded(self, mock_mcp_server):
        """Test that disconnected servers are excluded from tool definitions."""
        manager = McpManager()
        mock_mcp_server.status = ServerStatus.DISCONNECTED
        
        client = Mock(spec=McpClient)
        client.server = mock_mcp_server
        client.is_connected.return_value = False
        
        manager.clients["test_server"] = client
        
        tool_defs = await manager.get_mcp_tool_definitions()
        assert tool_defs == []


class TestAgentMcpIntegration:
    """Test Agent integration with MCP tools."""
    
    @pytest.mark.asyncio
    async def test_agent_includes_mcp_tools(self, mcp_manager_with_server):
        """Test that Agent includes MCP tools in API requests."""
        # Create agent
        settings = ProviderSettings(
            api_provider="anthropic",
            api_key="test-key",
            api_model_id="claude-3-5-sonnet-20241022"
        )
        client = RooClient(settings)
        agent = Agent(client, tools=[])  # Empty tools list
        
        # Mock the client's create_message to capture tools parameter
        captured_tools = None
        
        async def mock_create_message(**kwargs):
            nonlocal captured_tools
            captured_tools = kwargs.get('tools', [])
            # Return a mock response
            mock_response = AsyncMock()
            mock_response.get_text = AsyncMock(return_value="Test response")
            mock_response.get_tool_uses = Mock(return_value=[])
            return mock_response
        
        client.create_message = mock_create_message
        
        # Run agent
        try:
            await agent.run("Test task", max_iterations=1)
        except:
            pass  # We just want to capture the tools
        
        # Verify MCP tools were included
        assert captured_tools is not None
        mcp_tool_names = [t["name"] for t in captured_tools if "test_server__" in t["name"]]
        assert len(mcp_tool_names) == 2
        assert "test_server__weather" in mcp_tool_names
        assert "test_server__calculator" in mcp_tool_names
    
    @pytest.mark.asyncio
    async def test_agent_handles_mcp_failure_gracefully(self):
        """Test that Agent continues with built-in tools if MCP fails."""
        # Create agent without MCP setup
        settings = ProviderSettings(
            api_provider="anthropic",
            api_key="test-key",
            api_model_id="claude-3-5-sonnet-20241022"
        )
        client = RooClient(settings)
        agent = Agent(client, tools=[])  # Empty tools list
        
        # Mock create_message to capture tools
        captured_tools = None
        
        async def mock_create_message(**kwargs):
            nonlocal captured_tools
            captured_tools = kwargs.get('tools', [])
            mock_response = AsyncMock()
            mock_response.get_text = AsyncMock(return_value="Test response")
            mock_response.get_tool_uses = Mock(return_value=[])
            return mock_response
        
        client.create_message = mock_create_message
        
        # Run agent - should not crash even if MCP fails
        try:
            await agent.run("Test task", max_iterations=1)
        except:
            pass
        
        # Should still have captured tools (just built-in ones)
        assert captured_tools is not None


class TestMcpToolFormat:
    """Test MCP tool format conversion."""
    
    @pytest.mark.asyncio
    async def test_tool_schema_preservation(self, mcp_manager_with_server):
        """Test that input schemas are preserved correctly."""
        tool_defs = await mcp_manager_with_server.get_mcp_tool_definitions()
        
        weather_tool = next(t for t in tool_defs if "weather" in t["name"])
        
        # Schema should be preserved exactly
        assert weather_tool["input_schema"]["type"] == "object"
        assert "city" in weather_tool["input_schema"]["properties"]
        assert "units" in weather_tool["input_schema"]["properties"]
        assert weather_tool["input_schema"]["properties"]["units"]["enum"] == ["celsius", "fahrenheit"]
    
    @pytest.mark.asyncio
    async def test_tool_description_fallback(self):
        """Test that tools without description get a default one."""
        manager = McpManager()
        server = McpServer(name="test", command="test", status=ServerStatus.CONNECTED)
        server.tools = [
            McpTool(
                name="no_desc_tool",
                description="",  # Empty description
                input_schema={},
                server_name="test"
            )
        ]
        
        client = Mock(spec=McpClient)
        client.server = server
        client.is_connected.return_value = True
        manager.clients["test"] = client
        
        tool_defs = await manager.get_mcp_tool_definitions()
        
        # Should have default description
        assert len(tool_defs) == 1
        assert "MCP server" in tool_defs[0]["description"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])