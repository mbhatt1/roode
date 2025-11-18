"""Unit tests for MCP manager."""

import asyncio
import json
import pytest
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from roo_code.builtin_tools.mcp_manager import McpManager
from roo_code.builtin_tools.mcp_client import (
    McpClient,
    McpServer,
    McpTool,
    McpResource,
    ServerStatus,
    McpConnectionError
)


@pytest.fixture
def test_config_path(tmp_path):
    """Create a temporary config file."""
    config = {
        "mcpServers": {
            "test-server-1": {
                "command": "python",
                "args": ["-m", "test_mcp"],
                "env": {"VAR": "value1"},
                "timeout": 30
            },
            "test-server-2": {
                "command": "node",
                "args": ["server.js"],
                "env": {"VAR": "value2"},
                "timeout": 60
            },
            "disabled-server": {
                "command": "echo",
                "args": ["test"],
                "disabled": True
            }
        }
    }
    
    config_path = tmp_path / "mcp_config.json"
    with open(config_path, 'w') as f:
        json.dump(config, f)
    
    return str(config_path)


@pytest.fixture
def manager():
    """Create a test MCP manager."""
    return McpManager()


class TestMcpManager:
    """Test cases for McpManager."""
    
    @pytest.mark.asyncio
    async def test_load_config(self, manager, test_config_path):
        """Test loading configuration from file."""
        await manager.load_config(test_config_path)
        
        # Verify servers were loaded
        assert len(manager.servers) == 3
        assert "test-server-1" in manager.servers
        assert "test-server-2" in manager.servers
        assert "disabled-server" in manager.servers
        
        # Verify server configuration
        server1 = manager.servers["test-server-1"]
        assert server1.name == "test-server-1"
        assert server1.command == "python"
        assert server1.args == ["-m", "test_mcp"]
        assert server1.env == {"VAR": "value1"}
        assert server1.timeout == 30
        assert not server1.disabled
        
        # Verify disabled server
        disabled = manager.servers["disabled-server"]
        assert disabled.disabled
    
    @pytest.mark.asyncio
    async def test_load_config_missing_file(self, manager):
        """Test loading config with missing file."""
        with pytest.raises(FileNotFoundError):
            await manager.load_config("/nonexistent/config.json")
    
    @pytest.mark.asyncio
    async def test_load_config_invalid_json(self, manager, tmp_path):
        """Test loading config with invalid JSON."""
        config_path = tmp_path / "invalid.json"
        with open(config_path, 'w') as f:
            f.write("{ invalid json }")
        
        with pytest.raises(json.JSONDecodeError):
            await manager.load_config(str(config_path))
    
    @pytest.mark.asyncio
    async def test_load_config_missing_mcp_servers(self, manager, tmp_path):
        """Test loading config without mcpServers key."""
        config_path = tmp_path / "config.json"
        with open(config_path, 'w') as f:
            json.dump({"other": "data"}, f)
        
        with pytest.raises(ValueError, match="'mcpServers'"):
            await manager.load_config(str(config_path))
    
    @pytest.mark.asyncio
    async def test_load_config_missing_command(self, manager, tmp_path):
        """Test loading config with missing command field."""
        config = {
            "mcpServers": {
                "invalid-server": {
                    "args": ["test"]
                }
            }
        }
        config_path = tmp_path / "config.json"
        with open(config_path, 'w') as f:
            json.dump(config, f)
        
        with pytest.raises(ValueError, match="missing required 'command'"):
            await manager.load_config(str(config_path))
    
    @pytest.mark.asyncio
    async def test_connect_server(self, manager, test_config_path):
        """Test connecting to a server."""
        await manager.load_config(test_config_path)
        
        # Mock the client connection
        mock_client = AsyncMock(spec=McpClient)
        mock_client.connect = AsyncMock()
        mock_client.list_tools = AsyncMock(return_value=[])
        mock_client.list_resources = AsyncMock(return_value=[])
        mock_client.is_connected = Mock(return_value=True)
        mock_client.server = manager.servers["test-server-1"]
        
        with patch('roo_code.builtin_tools.mcp_manager.McpClient', return_value=mock_client):
            client = await manager.connect_server("test-server-1")
        
        assert client == mock_client
        mock_client.connect.assert_called_once()
        mock_client.list_tools.assert_called_once()
        mock_client.list_resources.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_connect_disabled_server(self, manager, test_config_path):
        """Test connecting to a disabled server."""
        await manager.load_config(test_config_path)
        
        with pytest.raises(ValueError, match="is disabled"):
            await manager.connect_server("disabled-server")
    
    @pytest.mark.asyncio
    async def test_connect_nonexistent_server(self, manager):
        """Test connecting to a server that doesn't exist."""
        with pytest.raises(ValueError, match="not found"):
            await manager.connect_server("nonexistent")
    
    @pytest.mark.asyncio
    async def test_connect_server_already_connected(self, manager, test_config_path):
        """Test connecting to an already connected server."""
        await manager.load_config(test_config_path)
        
        # Create mock client
        mock_client = AsyncMock(spec=McpClient)
        mock_client.is_connected = Mock(return_value=True)
        mock_client.connect = AsyncMock()
        
        # Add to clients
        manager.clients["test-server-1"] = mock_client
        
        # Try to connect again
        client = await manager.connect_server("test-server-1")
        
        # Should return existing client without reconnecting
        assert client == mock_client
        mock_client.connect.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_disconnect_server(self, manager, test_config_path):
        """Test disconnecting from a server."""
        await manager.load_config(test_config_path)
        
        # Create mock client
        mock_client = AsyncMock(spec=McpClient)
        mock_client.close = AsyncMock()
        
        # Add to clients
        manager.clients["test-server-1"] = mock_client
        
        await manager.disconnect_server("test-server-1")
        
        # Verify cleanup
        assert "test-server-1" not in manager.clients
        mock_client.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_restart_server(self, manager, test_config_path):
        """Test restarting a server."""
        await manager.load_config(test_config_path)
        
        # Create mock clients
        old_client = AsyncMock(spec=McpClient)
        old_client.close = AsyncMock()
        manager.clients["test-server-1"] = old_client
        
        new_client = AsyncMock(spec=McpClient)
        new_client.connect = AsyncMock()
        new_client.list_tools = AsyncMock(return_value=[])
        new_client.list_resources = AsyncMock(return_value=[])
        new_client.is_connected = Mock(return_value=True)
        new_client.server = manager.servers["test-server-1"]
        
        with patch('roo_code.builtin_tools.mcp_manager.McpClient', return_value=new_client):
            client = await manager.restart_server("test-server-1")
        
        # Verify old client was closed
        old_client.close.assert_called_once()
        
        # Verify new client was connected
        assert client == new_client
        new_client.connect.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_connect_all(self, manager, test_config_path):
        """Test connecting to all enabled servers."""
        await manager.load_config(test_config_path)
        
        # Mock the client connection
        mock_client = AsyncMock(spec=McpClient)
        mock_client.connect = AsyncMock()
        mock_client.list_tools = AsyncMock(return_value=[])
        mock_client.list_resources = AsyncMock(return_value=[])
        mock_client.is_connected = Mock(return_value=True)
        
        def create_mock_client(server):
            client = AsyncMock(spec=McpClient)
            client.connect = AsyncMock()
            client.list_tools = AsyncMock(return_value=[])
            client.list_resources = AsyncMock(return_value=[])
            client.is_connected = Mock(return_value=True)
            client.server = server
            return client
        
        with patch('roo_code.builtin_tools.mcp_manager.McpClient', side_effect=create_mock_client):
            await manager.connect_all()
        
        # Verify only enabled servers were connected
        assert len(manager.clients) == 2
        assert "test-server-1" in manager.clients
        assert "test-server-2" in manager.clients
        assert "disabled-server" not in manager.clients
    
    @pytest.mark.asyncio
    async def test_disconnect_all(self, manager):
        """Test disconnecting from all servers."""
        # Create mock clients
        client1 = AsyncMock(spec=McpClient)
        client1.close = AsyncMock()
        client2 = AsyncMock(spec=McpClient)
        client2.close = AsyncMock()
        
        manager.clients["server-1"] = client1
        manager.clients["server-2"] = client2
        
        await manager.disconnect_all()
        
        # Verify all were closed
        assert len(manager.clients) == 0
        client1.close.assert_called_once()
        client2.close.assert_called_once()
    
    def test_get_client(self, manager):
        """Test getting a client."""
        mock_client = Mock(spec=McpClient)
        manager.clients["test-server"] = mock_client
        
        client = manager.get_client("test-server")
        assert client == mock_client
        
        # Non-existent server
        assert manager.get_client("nonexistent") is None
    
    def test_get_server(self, manager):
        """Test getting server configuration."""
        server = McpServer(name="test", command="python", args=[])
        manager.servers["test"] = server
        
        result = manager.get_server("test")
        assert result == server
        
        # Non-existent server
        assert manager.get_server("nonexistent") is None
    
    def test_list_servers(self, manager):
        """Test listing all servers."""
        server1 = McpServer(name="test-1", command="python", args=[])
        server2 = McpServer(name="test-2", command="node", args=[])
        manager.servers["test-1"] = server1
        manager.servers["test-2"] = server2
        
        servers = manager.list_servers()
        assert len(servers) == 2
        assert "test-1" in servers
        assert "test-2" in servers
    
    def test_list_connected_servers(self, manager):
        """Test listing connected servers."""
        # Create mock clients
        connected_client = Mock(spec=McpClient)
        connected_client.is_connected = Mock(return_value=True)
        
        disconnected_client = Mock(spec=McpClient)
        disconnected_client.is_connected = Mock(return_value=False)
        
        manager.clients["connected"] = connected_client
        manager.clients["disconnected"] = disconnected_client
        
        connected = manager.list_connected_servers()
        assert len(connected) == 1
        assert "connected" in connected
    
    @pytest.mark.asyncio
    async def test_get_all_tools(self, manager):
        """Test getting tools from all servers."""
        # Create mock clients with tools
        client1 = Mock(spec=McpClient)
        client1.is_connected = Mock(return_value=True)
        client1.server = Mock()
        client1.server.tools = [
            McpTool(name="tool1", description="Tool 1", input_schema={}, server_name="server1")
        ]
        
        client2 = Mock(spec=McpClient)
        client2.is_connected = Mock(return_value=True)
        client2.server = Mock()
        client2.server.tools = [
            McpTool(name="tool2", description="Tool 2", input_schema={}, server_name="server2")
        ]
        
        manager.clients["server1"] = client1
        manager.clients["server2"] = client2
        
        tools = await manager.get_all_tools()
        assert len(tools) == 2
        assert tools[0].name == "tool1"
        assert tools[1].name == "tool2"
    
    @pytest.mark.asyncio
    async def test_call_tool(self, manager):
        """Test calling a tool."""
        mock_client = AsyncMock(spec=McpClient)
        mock_client.is_connected = Mock(return_value=True)
        mock_client.call_tool = AsyncMock(return_value={"result": "success"})
        
        manager.clients["test-server"] = mock_client
        
        result = await manager.call_tool("test-server", "test_tool", {"arg": "value"})
        
        assert result == {"result": "success"}
        mock_client.call_tool.assert_called_once_with("test_tool", {"arg": "value"})
    
    @pytest.mark.asyncio
    async def test_call_tool_not_connected(self, manager):
        """Test calling a tool on a non-connected server."""
        with pytest.raises(ValueError, match="not connected"):
            await manager.call_tool("nonexistent", "test_tool", {})
    
    @pytest.mark.asyncio
    async def test_read_resource(self, manager):
        """Test reading a resource."""
        mock_client = AsyncMock(spec=McpClient)
        mock_client.is_connected = Mock(return_value=True)
        mock_client.read_resource = AsyncMock(return_value={"contents": [{"text": "data"}]})
        
        manager.clients["test-server"] = mock_client
        
        result = await manager.read_resource("test-server", "file:///test.txt")
        
        assert result == {"contents": [{"text": "data"}]}
        mock_client.read_resource.assert_called_once_with("file:///test.txt")
    
    @pytest.mark.asyncio
    async def test_health_check(self, manager):
        """Test health check."""
        # Connected client
        connected_client = Mock(spec=McpClient)
        connected_client.is_connected = Mock(return_value=True)
        manager.clients["connected"] = connected_client
        
        assert await manager.health_check("connected") is True
        assert await manager.health_check("nonexistent") is False
    
    @pytest.mark.asyncio
    async def test_health_check_all(self, manager):
        """Test health check for all servers."""
        # Setup servers
        server1 = McpServer(name="server-1", command="python", args=[])
        server2 = McpServer(name="server-2", command="python", args=[])
        manager.servers["server-1"] = server1
        manager.servers["server-2"] = server2
        
        # Setup clients
        connected_client = Mock(spec=McpClient)
        connected_client.is_connected = Mock(return_value=True)
        manager.clients["server-1"] = connected_client
        
        results = await manager.health_check_all()
        
        assert results["server-1"] is True
        assert results["server-2"] is False
    
    def test_get_server_status(self, manager):
        """Test getting server status."""
        server = McpServer(name="test", command="python", args=[])
        server.status = ServerStatus.CONNECTED
        manager.servers["test"] = server
        
        status = manager.get_server_status("test")
        assert status == ServerStatus.CONNECTED
        
        # Non-existent server
        assert manager.get_server_status("nonexistent") is None
    
    def test_get_all_statuses(self, manager):
        """Test getting all server statuses."""
        server1 = McpServer(name="server-1", command="python", args=[])
        server1.status = ServerStatus.CONNECTED
        server2 = McpServer(name="server-2", command="python", args=[])
        server2.status = ServerStatus.DISCONNECTED
        
        manager.servers["server-1"] = server1
        manager.servers["server-2"] = server2
        
        statuses = manager.get_all_statuses()
        assert statuses["server-1"] == ServerStatus.CONNECTED
        assert statuses["server-2"] == ServerStatus.DISCONNECTED
    
    @pytest.mark.asyncio
    async def test_context_manager(self, manager):
        """Test using manager as context manager."""
        mock_client = AsyncMock(spec=McpClient)
        mock_client.close = AsyncMock()
        manager.clients["test"] = mock_client
        
        async with manager:
            pass
        
        # Verify cleanup
        assert len(manager.clients) == 0
        mock_client.close.assert_called_once()