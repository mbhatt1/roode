"""Integration tests for MCP client and manager."""

import asyncio
import json
import pytest
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch
from roo_code.builtin_tools.mcp_client import McpClient, McpServer, ServerStatus
from roo_code.builtin_tools.mcp_manager import McpManager
from roo_code.builtin_tools.mcp import (
    UseMcpToolTool,
    AccessMcpResourceTool,
    get_mcp_manager,
    set_mcp_manager
)


class MockMcpServer:
    """Mock MCP server for testing."""
    
    def __init__(self):
        self.tools = {
            "echo": {
                "name": "echo",
                "description": "Echo back the input",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "message": {"type": "string"}
                    },
                    "required": ["message"]
                }
            },
            "add": {
                "name": "add",
                "description": "Add two numbers",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "a": {"type": "number"},
                        "b": {"type": "number"}
                    },
                    "required": ["a", "b"]
                }
            }
        }
        
        self.resources = {
            "file:///test.txt": {
                "uri": "file:///test.txt",
                "name": "Test File",
                "mimeType": "text/plain",
                "description": "A test file"
            }
        }
        
        self.resource_contents = {
            "file:///test.txt": "Hello, World!"
        }
    
    async def handle_request(self, request: dict) -> dict:
        """Handle an MCP request."""
        method = request.get("method")
        params = request.get("params", {})
        request_id = request.get("id")
        
        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {},
                        "resources": {}
                    },
                    "serverInfo": {
                        "name": "mock-server",
                        "version": "1.0.0"
                    }
                }
            }
        
        elif method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "tools": list(self.tools.values())
                }
            }
        
        elif method == "tools/call":
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            
            if tool_name == "echo":
                message = arguments.get("message", "")
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": f"Echo: {message}"
                            }
                        ]
                    }
                }
            
            elif tool_name == "add":
                a = arguments.get("a", 0)
                b = arguments.get("b", 0)
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": f"Result: {a + b}"
                            }
                        ]
                    }
                }
            
            else:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32601,
                        "message": f"Tool not found: {tool_name}"
                    }
                }
        
        elif method == "resources/list":
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "resources": list(self.resources.values())
                }
            }
        
        elif method == "resources/read":
            uri = params.get("uri")
            if uri in self.resource_contents:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "contents": [
                            {
                                "mimeType": "text/plain",
                                "text": self.resource_contents[uri]
                            }
                        ]
                    }
                }
            else:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32602,
                        "message": f"Resource not found: {uri}"
                    }
                }
        
        else:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}"
                }
            }


@pytest.fixture
def mock_server():
    """Create a mock MCP server."""
    return MockMcpServer()


@pytest.fixture
def test_config(tmp_path):
    """Create a test configuration."""
    config = {
        "mcpServers": {
            "mock-server": {
                "command": "python",
                "args": ["-m", "mock_mcp_server"],
                "env": {},
                "timeout": 30
            }
        }
    }
    
    config_path = tmp_path / "mcp_config.json"
    with open(config_path, 'w') as f:
        json.dump(config, f)
    
    return str(config_path)


class TestMcpIntegration:
    """Integration tests for MCP functionality."""
    
    @pytest.mark.asyncio
    async def test_full_workflow(self, mock_server, test_config):
        """Test complete workflow: load config, connect, call tool."""
        manager = McpManager()
        await manager.load_config(test_config)
        
        # Create mock process for the client
        mock_process = AsyncMock()
        mock_process.returncode = None
        mock_process.stdin = AsyncMock()
        mock_process.stdout = AsyncMock()
        mock_process.stderr = AsyncMock()
        mock_process.wait = AsyncMock()
        mock_process.kill = Mock()
        
        # Mock stdin/stdout communication
        request_responses = []
        
        async def mock_write(data):
            request = json.loads(data.decode().strip())
            response = await mock_server.handle_request(request)
            request_responses.append(response)
        
        async def mock_readline():
            if request_responses:
                response = request_responses.pop(0)
                return (json.dumps(response) + "\n").encode()
            await asyncio.sleep(0.1)
            return b""
        
        mock_process.stdin.write = mock_write
        mock_process.stdin.drain = AsyncMock()
        mock_process.stdout.readline = mock_readline
        
        # Patch subprocess creation
        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            # Connect to server
            client = await manager.connect_server("mock-server")
            
            # List tools
            tools = await client.list_tools()
            assert len(tools) == 2
            assert any(t.name == "echo" for t in tools)
            
            # Call tool
            result = await client.call_tool("echo", {"message": "Hello"})
            assert "content" in result
            
            # Clean up
            await manager.disconnect_server("mock-server")
    
    @pytest.mark.asyncio
    async def test_use_mcp_tool_integration(self, mock_server):
        """Test UseMcpToolTool with mock server."""
        # Setup manager
        manager = McpManager()
        server = McpServer(
            name="mock-server",
            command="python",
            args=["-m", "mock"],
            timeout=30
        )
        await manager._add_server_from_config("mock-server", {
            "command": "python",
            "args": ["-m", "mock"],
            "timeout": 30
        })
        
        # Create mock client
        mock_client = AsyncMock()
        mock_client.is_connected = Mock(return_value=True)
        mock_client.call_tool = AsyncMock(return_value={
            "content": [
                {"type": "text", "text": "Echo: Test"}
            ]
        })
        
        manager.clients["mock-server"] = mock_client
        set_mcp_manager(manager)
        
        # Use the tool
        tool = UseMcpToolTool()
        tool.current_use_id = "test-use-id"
        
        result = await tool.execute({
            "server_name": "mock-server",
            "tool_name": "echo",
            "arguments": {"message": "Test"}
        })
        
        assert not result.is_error
        assert "Echo: Test" in result.content
        mock_client.call_tool.assert_called_once_with("echo", {"message": "Test"})
    
    @pytest.mark.asyncio
    async def test_access_mcp_resource_integration(self, mock_server):
        """Test AccessMcpResourceTool with mock server."""
        # Setup manager
        manager = McpManager()
        await manager._add_server_from_config("mock-server", {
            "command": "python",
            "args": ["-m", "mock"],
            "timeout": 30
        })
        
        # Create mock client
        mock_client = AsyncMock()
        mock_client.is_connected = Mock(return_value=True)
        mock_client.read_resource = AsyncMock(return_value={
            "contents": [
                {"mimeType": "text/plain", "text": "File contents"}
            ]
        })
        
        manager.clients["mock-server"] = mock_client
        set_mcp_manager(manager)
        
        # Use the tool
        tool = AccessMcpResourceTool()
        tool.current_use_id = "test-use-id"
        
        result = await tool.execute({
            "server_name": "mock-server",
            "resource_uri": "file:///test.txt"
        })
        
        assert not result.is_error
        assert "File contents" in result.content
        mock_client.read_resource.assert_called_once_with("file:///test.txt")
    
    @pytest.mark.asyncio
    async def test_auto_connect_on_tool_use(self):
        """Test automatic connection when using tool."""
        # Setup manager
        manager = McpManager()
        await manager._add_server_from_config("test-server", {
            "command": "python",
            "args": ["-m", "test"],
            "timeout": 30
        })
        
        set_mcp_manager(manager)
        
        # Mock the connect_server method
        mock_client = AsyncMock()
        mock_client.is_connected = Mock(return_value=True)
        mock_client.call_tool = AsyncMock(return_value={
            "content": [{"type": "text", "text": "Result"}]
        })
        
        async def mock_connect(server_name):
            manager.clients[server_name] = mock_client
            return mock_client
        
        manager.connect_server = AsyncMock(side_effect=mock_connect)
        
        # Use tool (server not connected initially)
        tool = UseMcpToolTool()
        tool.current_use_id = "test-use-id"
        
        result = await tool.execute({
            "server_name": "test-server",
            "tool_name": "test_tool",
            "arguments": {}
        })
        
        # Should auto-connect
        manager.connect_server.assert_called_once_with("test-server")
        assert not result.is_error
    
    @pytest.mark.asyncio
    async def test_multiple_servers(self, mock_server):
        """Test managing multiple servers simultaneously."""
        # Create config with multiple servers
        manager = McpManager()
        await manager._add_server_from_config("server-1", {
            "command": "python",
            "args": ["-m", "server1"],
            "timeout": 30
        })
        await manager._add_server_from_config("server-2", {
            "command": "python",
            "args": ["-m", "server2"],
            "timeout": 30
        })
        
        # Create mock clients
        client1 = AsyncMock()
        client1.is_connected = Mock(return_value=True)
        client1.server = Mock()
        client1.server.tools = []
        client1.server.resources = []
        
        client2 = AsyncMock()
        client2.is_connected = Mock(return_value=True)
        client2.server = Mock()
        client2.server.tools = []
        client2.server.resources = []
        
        manager.clients["server-1"] = client1
        manager.clients["server-2"] = client2
        
        # Verify both servers are connected
        connected = manager.list_connected_servers()
        assert len(connected) == 2
        assert "server-1" in connected
        assert "server-2" in connected
    
    @pytest.mark.asyncio
    async def test_error_handling(self):
        """Test error handling in tool execution."""
        manager = McpManager()
        await manager._add_server_from_config("test-server", {
            "command": "python",
            "args": ["-m", "test"],
            "timeout": 30
        })
        
        # Create mock client that raises errors
        mock_client = AsyncMock()
        mock_client.is_connected = Mock(return_value=True)
        mock_client.call_tool = AsyncMock(side_effect=Exception("Tool error"))
        
        manager.clients["test-server"] = mock_client
        set_mcp_manager(manager)
        
        # Use tool
        tool = UseMcpToolTool()
        tool.current_use_id = "test-use-id"
        
        result = await tool.execute({
            "server_name": "test-server",
            "tool_name": "failing_tool",
            "arguments": {}
        })
        
        assert result.is_error
        assert "error" in result.content.lower() or "unexpected" in result.content.lower()
    
    @pytest.mark.asyncio
    async def test_connection_error_handling(self):
        """Test connection error handling."""
        manager = McpManager()
        await manager._add_server_from_config("test-server", {
            "command": "nonexistent-command",
            "args": [],
            "timeout": 30
        })
        
        set_mcp_manager(manager)
        
        # Mock connection to fail
        from roo_code.builtin_tools.mcp_client import McpConnectionError
        manager.connect_server = AsyncMock(side_effect=McpConnectionError("Connection failed"))
        
        # Use tool
        tool = UseMcpToolTool()
        tool.current_use_id = "test-use-id"
        
        result = await tool.execute({
            "server_name": "test-server",
            "tool_name": "test_tool",
            "arguments": {}
        })
        
        assert result.is_error
        assert "Failed to connect" in result.content
    
    @pytest.mark.asyncio
    async def test_resource_binary_data(self):
        """Test handling binary resource data."""
        manager = McpManager()
        await manager._add_server_from_config("test-server", {
            "command": "python",
            "args": ["-m", "test"],
            "timeout": 30
        })
        
        # Create mock client with binary resource
        mock_client = AsyncMock()
        mock_client.is_connected = Mock(return_value=True)
        mock_client.read_resource = AsyncMock(return_value={
            "contents": [
                {"mimeType": "application/octet-stream", "blob": "SGVsbG8gV29ybGQ="}
            ]
        })
        
        manager.clients["test-server"] = mock_client
        set_mcp_manager(manager)
        
        # Use tool
        tool = AccessMcpResourceTool()
        tool.current_use_id = "test-use-id"
        
        result = await tool.execute({
            "server_name": "test-server",
            "resource_uri": "file:///binary.dat"
        })
        
        assert not result.is_error
        assert "binary data" in result.content.lower()


class TestMcpManagerContext:
    """Test MCP manager as context manager."""
    
    @pytest.mark.asyncio
    async def test_context_manager_cleanup(self):
        """Test that context manager properly cleans up."""
        manager = McpManager()
        await manager._add_server_from_config("test-server", {
            "command": "python",
            "args": ["-m", "test"],
            "timeout": 30
        })
        
        # Create mock client
        mock_client = AsyncMock()
        mock_client.close = AsyncMock()
        manager.clients["test-server"] = mock_client
        
        async with manager:
            # Manager is active
            assert "test-server" in manager.clients
        
        # After context, should be cleaned up
        assert len(manager.clients) == 0
        mock_client.close.assert_called_once()