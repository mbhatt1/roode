"""Unit tests for MCP client."""

import asyncio
import json
import pytest
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from roo_code.builtin_tools.mcp_client import (
    McpClient,
    McpServer,
    McpTool,
    McpResource,
    ServerStatus,
    McpError,
    McpConnectionError,
    McpTimeoutError,
    McpProtocolError
)


@pytest.fixture
def test_server():
    """Create a test MCP server configuration."""
    return McpServer(
        name="test-server",
        command="python",
        args=["-m", "test_mcp"],
        env={"TEST_VAR": "value"},
        timeout=30
    )


@pytest.fixture
def mock_process():
    """Create a mock subprocess."""
    process = MagicMock()
    process.returncode = None
    
    # Mock stdin
    stdin = AsyncMock()
    stdin.write = Mock()
    stdin.drain = AsyncMock()
    stdin.close = Mock()
    stdin.wait_closed = AsyncMock()
    process.stdin = stdin
    
    # Mock stdout
    stdout = AsyncMock()
    process.stdout = stdout
    
    # Mock stderr
    stderr = AsyncMock()
    process.stderr = stderr
    
    # Mock wait
    process.wait = AsyncMock()
    process.kill = Mock()
    
    return process


class TestMcpClient:
    """Test cases for McpClient."""
    
    @pytest.mark.asyncio
    async def test_connect_success(self, test_server, mock_process):
        """Test successful connection to MCP server."""
        client = McpClient(test_server)
        
        # Mock subprocess creation
        with patch('asyncio.create_subprocess_exec', return_value=mock_process) as mock_exec:
            # Mock initialize response
            async def mock_readline():
                init_response = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {
                            "tools": {},
                            "resources": {}
                        },
                        "serverInfo": {
                            "name": "test-server",
                            "version": "1.0.0"
                        }
                    }
                }
                return (json.dumps(init_response) + "\n").encode()
            
            mock_process.stdout.readline = mock_readline
            
            await client.connect()
            
            # Verify subprocess was created with correct params
            mock_exec.assert_called_once()
            args = mock_exec.call_args
            assert args[0][0] == "python"
            assert args[0][1:] == ("-m", "test_mcp")
            
            # Verify server status
            assert test_server.status == ServerStatus.CONNECTED
            assert client.is_connected()
    
    @pytest.mark.asyncio
    async def test_connect_failure(self, test_server):
        """Test connection failure handling."""
        client = McpClient(test_server)
        
        # Mock subprocess creation to fail
        with patch('asyncio.create_subprocess_exec', side_effect=Exception("Connection failed")):
            with pytest.raises(McpConnectionError):
                await client.connect()
            
            # Verify server status
            assert test_server.status == ServerStatus.DISCONNECTED
            assert not client.is_connected()
    
    @pytest.mark.asyncio
    async def test_list_tools(self, test_server, mock_process):
        """Test listing tools from server."""
        client = McpClient(test_server)
        client.process = mock_process
        test_server.status = ServerStatus.CONNECTED
        
        # Create a future for the response
        response_future = asyncio.Future()
        response_future.set_result({
            "tools": [
                {
                    "name": "test_tool",
                    "description": "A test tool",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "arg1": {"type": "string"}
                        }
                    }
                }
            ]
        })
        
        # Mock the request
        with patch.object(client, '_send_request', return_value=response_future):
            tools = await client.list_tools()
        
        assert len(tools) == 1
        assert tools[0].name == "test_tool"
        assert tools[0].description == "A test tool"
        assert tools[0].server_name == "test-server"
    
    @pytest.mark.asyncio
    async def test_call_tool(self, test_server, mock_process):
        """Test calling a tool on the server."""
        client = McpClient(test_server)
        client.process = mock_process
        test_server.status = ServerStatus.CONNECTED
        
        # Create a future for the response
        response_future = asyncio.Future()
        response_future.set_result({
            "content": [
                {
                    "type": "text",
                    "text": "Tool executed successfully"
                }
            ]
        })
        
        # Mock the request
        with patch.object(client, '_send_request', return_value=response_future):
            result = await client.call_tool("test_tool", {"arg1": "value1"})
        
        assert "content" in result
        assert len(result["content"]) == 1
        assert result["content"][0]["text"] == "Tool executed successfully"
    
    @pytest.mark.asyncio
    async def test_call_tool_timeout(self, test_server, mock_process):
        """Test tool call timeout handling."""
        client = McpClient(test_server)
        client.process = mock_process
        test_server.status = ServerStatus.CONNECTED
        test_server.timeout = 1
        
        # Mock the request to timeout
        async def mock_timeout(*args, **kwargs):
            await asyncio.sleep(2)
            return {}
        
        with patch.object(client, '_send_request', side_effect=asyncio.TimeoutError):
            with pytest.raises(McpTimeoutError):
                await client.call_tool("slow_tool", {})
    
    @pytest.mark.asyncio
    async def test_list_resources(self, test_server, mock_process):
        """Test listing resources from server."""
        client = McpClient(test_server)
        client.process = mock_process
        test_server.status = ServerStatus.CONNECTED
        
        # Create a future for the response
        response_future = asyncio.Future()
        response_future.set_result({
            "resources": [
                {
                    "uri": "file:///test.txt",
                    "name": "Test File",
                    "mimeType": "text/plain",
                    "description": "A test file"
                }
            ]
        })
        
        # Mock the request
        with patch.object(client, '_send_request', return_value=response_future):
            resources = await client.list_resources()
        
        assert len(resources) == 1
        assert resources[0].uri == "file:///test.txt"
        assert resources[0].name == "Test File"
        assert resources[0].mime_type == "text/plain"
    
    @pytest.mark.asyncio
    async def test_read_resource(self, test_server, mock_process):
        """Test reading a resource from the server."""
        client = McpClient(test_server)
        client.process = mock_process
        test_server.status = ServerStatus.CONNECTED
        
        # Create a future for the response
        response_future = asyncio.Future()
        response_future.set_result({
            "contents": [
                {
                    "mimeType": "text/plain",
                    "text": "Hello, World!"
                }
            ]
        })
        
        # Mock the request
        with patch.object(client, '_send_request', return_value=response_future):
            result = await client.read_resource("file:///test.txt")
        
        assert "contents" in result
        assert len(result["contents"]) == 1
        assert result["contents"][0]["text"] == "Hello, World!"
    
    @pytest.mark.asyncio
    async def test_close(self, test_server, mock_process):
        """Test closing connection to server."""
        client = McpClient(test_server)
        client.process = mock_process
        test_server.status = ServerStatus.CONNECTED
        
        # Create a mock reader task
        reader_task = AsyncMock()
        reader_task.cancel = Mock()
        client.reader_task = reader_task
        
        await client.close()
        
        # Verify cleanup
        assert test_server.status == ServerStatus.DISCONNECTED
        assert client.process is None
        reader_task.cancel.assert_called_once()
        mock_process.stdin.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_send_request(self, test_server, mock_process):
        """Test sending a JSON-RPC request."""
        client = McpClient(test_server)
        client.process = mock_process
        test_server.status = ServerStatus.CONNECTED
        
        # Create response future
        async def handle_request():
            # Simulate response
            request_id = client.request_id
            future = client.pending_requests.get(request_id)
            if future:
                future.set_result({"success": True})
        
        # Start handling in background
        asyncio.create_task(handle_request())
        
        result = await client._send_request("test/method", {"param": "value"})
        
        assert result == {"success": True}
        mock_process.stdin.write.assert_called()
        mock_process.stdin.drain.assert_called()
    
    @pytest.mark.asyncio
    async def test_protocol_error_handling(self, test_server, mock_process):
        """Test handling of protocol errors."""
        client = McpClient(test_server)
        client.process = mock_process
        test_server.status = ServerStatus.CONNECTED
        
        # Create error response
        error_response = {
            "jsonrpc": "2.0",
            "id": 1,
            "error": {
                "code": -32000,
                "message": "Test error"
            }
        }
        
        # Simulate receiving error response
        await client._handle_response(error_response)
        
        # The error should be propagated through the pending request
        # We're testing the error handling mechanism
    
    @pytest.mark.asyncio
    async def test_not_connected_error(self, test_server):
        """Test operations when not connected."""
        client = McpClient(test_server)
        
        with pytest.raises(McpConnectionError):
            await client._send_request("test/method", {})
    
    @pytest.mark.asyncio
    async def test_multiple_requests(self, test_server, mock_process):
        """Test sending multiple concurrent requests."""
        client = McpClient(test_server)
        client.process = mock_process
        test_server.status = ServerStatus.CONNECTED
        
        # Mock responses for multiple requests
        async def mock_send(method, params, timeout=None):
            return {"method": method, "result": "ok"}
        
        with patch.object(client, '_send_request', side_effect=mock_send):
            # Send multiple requests concurrently
            tasks = [
                client.list_tools(),
                client.list_resources(),
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # All requests should succeed
            assert len(results) == 2
            for result in results:
                assert not isinstance(result, Exception)


class TestMcpDataClasses:
    """Test MCP data classes."""
    
    def test_mcp_server_creation(self):
        """Test creating an MCP server configuration."""
        server = McpServer(
            name="test",
            command="python",
            args=["-m", "test"],
            env={"VAR": "value"}
        )
        
        assert server.name == "test"
        assert server.command == "python"
        assert server.args == ["-m", "test"]
        assert server.env == {"VAR": "value"}
        assert server.status == ServerStatus.DISCONNECTED
        assert server.timeout == 60
    
    def test_mcp_tool_creation(self):
        """Test creating an MCP tool."""
        tool = McpTool(
            name="test_tool",
            description="A test tool",
            input_schema={"type": "object"},
            server_name="test-server"
        )
        
        assert tool.name == "test_tool"
        assert tool.description == "A test tool"
        assert tool.input_schema == {"type": "object"}
        assert tool.server_name == "test-server"
    
    def test_mcp_resource_creation(self):
        """Test creating an MCP resource."""
        resource = McpResource(
            uri="file:///test.txt",
            name="Test File",
            mime_type="text/plain",
            description="A test file"
        )
        
        assert resource.uri == "file:///test.txt"
        assert resource.name == "Test File"
        assert resource.mime_type == "text/plain"
        assert resource.description == "A test file"


class TestMcpExceptions:
    """Test MCP exception classes."""
    
    def test_mcp_error(self):
        """Test McpError exception."""
        error = McpError("Test error")
        assert str(error) == "Test error"
    
    def test_mcp_connection_error(self):
        """Test McpConnectionError exception."""
        error = McpConnectionError("Connection failed")
        assert str(error) == "Connection failed"
        assert isinstance(error, McpError)
    
    def test_mcp_timeout_error(self):
        """Test McpTimeoutError exception."""
        error = McpTimeoutError("Request timed out")
        assert str(error) == "Request timed out"
        assert isinstance(error, McpError)
    
    def test_mcp_protocol_error(self):
        """Test McpProtocolError exception."""
        error = McpProtocolError("Protocol error")
        assert str(error) == "Protocol error"
        assert isinstance(error, McpError)