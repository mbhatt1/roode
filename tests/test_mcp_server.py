"""
Unit tests for MCP Modes Server.

Tests server lifecycle, request routing, and integration scenarios.
"""

import asyncio
import json
import pytest
from io import BytesIO
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from roo_code.mcp.server import McpModesServer
from roo_code.mcp.protocol import McpErrorCode, JsonRpcMessage
from roo_code.modes.orchestrator import ModeOrchestrator


@pytest.fixture
def mock_orchestrator():
    """Create a mock mode orchestrator."""
    from roo_code.modes.config import ModeConfig, ModeSource
    
    orchestrator = Mock(spec=ModeOrchestrator)
    
    code_mode = ModeConfig(
        slug="code",
        name="Code Mode",
        source=ModeSource.BUILTIN,
        groups=["read", "edit"]
    )
    
    orchestrator.get_all_modes = Mock(return_value=[code_mode])
    orchestrator.get_mode = Mock(return_value=code_mode)
    orchestrator.get_mode_names = Mock(return_value=["code"])
    
    return orchestrator


@pytest.fixture
def server():
    """Create a test server instance."""
    return McpModesServer(
        project_root=None,
        session_timeout=3600,
        cleanup_interval=300
    )


class TestMcpModesServer:
    """Test McpModesServer class."""
    
    def test_init(self, server):
        """Test server initialization."""
        assert server.orchestrator is not None
        assert server.session_manager is not None
        assert server.resource_handler is not None
        assert server.tool_handler is not None
        assert not server.running
        assert not server.initialized
        assert server.capabilities is not None
    
    def test_init_with_custom_paths(self, tmp_path):
        """Test initialization with custom paths."""
        project_root = tmp_path / "project"
        config_dir = tmp_path / "config"
        
        server = McpModesServer(
            project_root=project_root,
            global_config_dir=config_dir,
            session_timeout=7200,
            cleanup_interval=600
        )
        
        assert server.project_root == project_root
        assert server.session_manager.timeout == 7200
        assert server.session_manager.cleanup_interval == 600
    
    def test_build_capabilities(self, server):
        """Test capabilities structure."""
        caps = server.capabilities
        
        assert "resources" in caps
        assert "tools" in caps
        assert "listChanged" in caps["resources"]
        assert "listChanged" in caps["tools"]
    
    def test_register_request_handlers(self, server):
        """Test request handlers are registered."""
        handlers = server.request_handlers
        
        assert "initialize" in handlers
        assert "resources/list" in handlers
        assert "resources/read" in handlers
        assert "tools/list" in handlers
        assert "tools/call" in handlers
    
    def test_register_notification_handlers(self, server):
        """Test notification handlers are registered."""
        handlers = server.notification_handlers
        
        assert "notifications/initialized" in handlers
        assert "cancelled" in handlers


class TestServerLifecycle:
    """Test server lifecycle management."""
    
    @pytest.mark.asyncio
    async def test_start_and_shutdown(self, server):
        """Test starting and shutting down server."""
        # Mock stdin to prevent actual reading
        with patch.object(server, 'stdin'):
            # Start session manager only
            await server.session_manager.start()
            assert server.session_manager.running
            
            # Shutdown
            await server.shutdown()
            assert not server.session_manager.running
            assert not server.running
    
    @pytest.mark.asyncio
    async def test_shutdown_cleanup(self, server):
        """Test shutdown cleans up sessions."""
        from roo_code.modes.task import Task
        
        # Start session manager
        await server.session_manager.start()
        
        # Create some sessions
        task1 = Task(mode_slug="code", task_id="task1")
        task2 = Task(mode_slug="code", task_id="task2")
        server.session_manager.create_session(task1)
        server.session_manager.create_session(task2)
        
        assert server.session_manager.get_session_count() == 2
        
        # Shutdown should cleanup all sessions
        await server.shutdown()
        assert server.session_manager.get_session_count() == 0
    
    def test_get_server_info(self, server):
        """Test getting server information."""
        info = server.get_server_info()
        
        assert info["name"] == "roo-modes-server"
        assert info["version"] == "1.0.0"
        assert info["running"] == server.running
        assert info["initialized"] == server.initialized
        assert "modes_available" in info
        assert "active_sessions" in info
        assert "session_stats" in info


class TestMessageProcessing:
    """Test message processing."""
    
    @pytest.mark.asyncio
    async def test_process_valid_request(self, server):
        """Test processing valid JSON-RPC request."""
        message = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": "2024-11-05"}
        }
        
        # Mock writer
        server.writer.write_response = Mock()
        
        await server._process_message(message)
        
        # Should have written response
        server.writer.write_response.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_process_notification(self, server):
        """Test processing notification (no id)."""
        message = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {}
        }
        
        # Should not write response for notifications
        server.writer.write_response = Mock()
        
        await server._process_message(message)
        
        server.writer.write_response.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_process_invalid_message(self, server):
        """Test processing invalid message."""
        message = {
            "jsonrpc": "1.0",  # Wrong version
            "method": "test"
        }
        
        from roo_code.mcp.protocol import McpProtocolError
        
        with pytest.raises(McpProtocolError):
            await server._process_message(message)


class TestInitialize:
    """Test initialize handshake."""
    
    @pytest.mark.asyncio
    async def test_initialize_request(self, server):
        """Test initialize request handling."""
        server.writer.write_response = Mock()
        
        await server._handle_initialize(
            request_id=1,
            params={
                "protocolVersion": "2024-11-05",
                "clientInfo": {"name": "test-client", "version": "1.0.0"}
            }
        )
        
        # Should write response with server info and capabilities
        server.writer.write_response.assert_called_once()
        args = server.writer.write_response.call_args
        
        assert args[0][0] == 1  # request_id
        result = args[0][1]
        
        assert result["protocolVersion"] == "2024-11-05"
        assert result["serverInfo"]["name"] == "roo-modes-server"
        assert "capabilities" in result
        assert server.initialized
    
    @pytest.mark.asyncio
    async def test_initialized_notification(self, server):
        """Test initialized notification handling."""
        await server._handle_initialized({})
        
        # Should complete without error (just logs)
        assert True


class TestResourceMethods:
    """Test resource method handlers."""
    
    @pytest.mark.asyncio
    async def test_list_resources(self, server):
        """Test resources/list handler."""
        server.writer.write_response = Mock()
        
        await server._handle_list_resources(request_id=1, params={})
        
        server.writer.write_response.assert_called_once()
        args = server.writer.write_response.call_args
        
        assert args[0][0] == 1
        result = args[0][1]
        assert "resources" in result
        assert isinstance(result["resources"], list)
    
    @pytest.mark.asyncio
    async def test_read_resource(self, server):
        """Test resources/read handler."""
        server.writer.write_response = Mock()
        
        await server._handle_read_resource(
            request_id=1,
            params={"uri": "mode://code"}
        )
        
        server.writer.write_response.assert_called_once()
        result = server.writer.write_response.call_args[0][1]
        
        assert "contents" in result
    
    @pytest.mark.asyncio
    async def test_read_resource_missing_uri(self, server):
        """Test read resource without URI parameter."""
        from roo_code.mcp.validation import ValidationError
        
        with pytest.raises(ValidationError):
            await server._handle_read_resource(request_id=1, params={})


class TestToolMethods:
    """Test tool method handlers."""
    
    @pytest.mark.asyncio
    async def test_list_tools(self, server):
        """Test tools/list handler."""
        server.writer.write_response = Mock()
        
        await server._handle_list_tools(request_id=1, params={})
        
        server.writer.write_response.assert_called_once()
        result = server.writer.write_response.call_args[0][1]
        
        assert "tools" in result
        assert isinstance(result["tools"], list)
        assert len(result["tools"]) > 0
    
    @pytest.mark.asyncio
    async def test_call_tool(self, server):
        """Test tools/call handler."""
        server.writer.write_response = Mock()
        
        await server._handle_call_tool(
            request_id=1,
            params={
                "name": "list_modes",
                "arguments": {}
            }
        )
        
        server.writer.write_response.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_call_tool_missing_name(self, server):
        """Test call tool without name parameter."""
        from roo_code.mcp.validation import ValidationError
        
        with pytest.raises(ValidationError):
            await server._handle_call_tool(
                request_id=1,
                params={"arguments": {}}
            )


class TestErrorHandling:
    """Test error handling in server."""
    
    @pytest.mark.asyncio
    async def test_method_not_found(self, server):
        """Test handling unknown method."""
        server.writer.write_error = Mock()
        
        await server._handle_request(
            request_id=1,
            method="unknown/method",
            params={}
        )
        
        server.writer.write_error.assert_called_once()
        args = server.writer.write_error.call_args[0]
        
        assert args[0] == 1  # request_id
        assert args[1] == McpErrorCode.METHOD_NOT_FOUND
    
    @pytest.mark.asyncio
    async def test_validation_error_handling(self, server):
        """Test handling validation errors."""
        server.writer.write_error = Mock()
        
        # Call tool with missing required parameter
        await server._handle_request(
            request_id=1,
            method="tools/call",
            params={"arguments": {}}  # Missing 'name'
        )
        
        server.writer.write_error.assert_called_once()
        args = server.writer.write_error.call_args[0]
        
        assert args[1] == McpErrorCode.VALIDATION_ERROR
    
    @pytest.mark.asyncio
    async def test_internal_error_handling(self, server):
        """Test handling internal errors."""
        server.writer.write_error = Mock()
        
        # Mock tool handler to raise exception
        with patch.object(server.tool_handler, 'call_tool', side_effect=Exception("Test error")):
            await server._handle_request(
                request_id=1,
                method="tools/call",
                params={"name": "list_modes", "arguments": {}}
            )
        
        server.writer.write_error.assert_called_once()
        args = server.writer.write_error.call_args[0]
        
        assert args[1] == McpErrorCode.INTERNAL_ERROR


class TestCancellation:
    """Test request cancellation."""
    
    @pytest.mark.asyncio
    async def test_cancelled_notification(self, server):
        """Test handling cancelled notification."""
        await server._handle_cancelled({
            "requestId": 123,
            "reason": "User cancelled"
        })
        
        # Should complete without error (just logs)
        assert True


class TestIntegration:
    """Test end-to-end integration scenarios."""
    
    @pytest.mark.asyncio
    async def test_full_handshake(self, server):
        """Test complete initialize handshake."""
        server.writer.write_response = Mock()
        
        # 1. Initialize
        await server._handle_initialize(
            request_id=1,
            params={
                "protocolVersion": "2024-11-05",
                "clientInfo": {"name": "test"}
            }
        )
        
        assert server.initialized
        
        # 2. Initialized notification
        await server._handle_initialized({})
        
        # Server should be ready
        assert server.initialized
    
    @pytest.mark.asyncio
    async def test_resource_workflow(self, server):
        """Test complete resource workflow."""
        server.writer.write_response = Mock()
        
        # 1. List resources
        await server._handle_list_resources(1, {})
        resources = server.writer.write_response.call_args[0][1]["resources"]
        
        # 2. Read a resource
        uri = resources[0]["uri"]
        await server._handle_read_resource(2, {"uri": uri})
        
        assert server.writer.write_response.call_count == 2
    
    @pytest.mark.asyncio
    async def test_tool_workflow(self, server):
        """Test complete tool workflow."""
        server.writer.write_response = Mock()
        
        # 1. List tools
        await server._handle_list_tools(1, {})
        
        # 2. Call a tool
        await server._handle_call_tool(
            2,
            {"name": "list_modes", "arguments": {}}
        )
        
        # 3. Create a task
        await server._handle_call_tool(
            3,
            {"name": "create_task", "arguments": {"mode_slug": "code"}}
        )
        
        assert server.writer.write_response.call_count == 3
    
    @pytest.mark.asyncio
    async def test_task_lifecycle(self, server):
        """Test complete task lifecycle through server."""
        server.writer.write_response = Mock()
        
        # 1. Create task
        await server._handle_call_tool(
            1,
            {"name": "create_task", "arguments": {"mode_slug": "code"}}
        )
        
        # Get session_id from response
        result = server.writer.write_response.call_args[0][1]
        session_id = result["metadata"]["session_id"]
        
        # 2. Get task info
        await server._handle_call_tool(
            2,
            {"name": "get_task_info", "arguments": {"session_id": session_id}}
        )
        
        # 3. Switch mode
        await server._handle_call_tool(
            3,
            {
                "name": "switch_mode",
                "arguments": {
                    "session_id": session_id,
                    "new_mode_slug": "code"
                }
            }
        )
        
        # 4. Complete task
        await server._handle_call_tool(
            4,
            {
                "name": "complete_task",
                "arguments": {
                    "session_id": session_id,
                    "status": "completed"
                }
            }
        )
        
        assert server.writer.write_response.call_count == 4


class TestConcurrency:
    """Test concurrent request handling."""
    
    @pytest.mark.asyncio
    async def test_concurrent_requests(self, server):
        """Test handling multiple concurrent requests."""
        server.writer.write_response = Mock()
        
        # Create multiple concurrent requests
        tasks = [
            server._handle_list_resources(i, {})
            for i in range(10)
        ]
        
        await asyncio.gather(*tasks)
        
        # All requests should complete
        assert server.writer.write_response.call_count == 10
    
    @pytest.mark.asyncio
    async def test_concurrent_tool_calls(self, server):
        """Test concurrent tool calls."""
        server.writer.write_response = Mock()
        
        tasks = [
            server._handle_call_tool(
                i,
                {"name": "list_modes", "arguments": {}}
            )
            for i in range(5)
        ]
        
        await asyncio.gather(*tasks)
        
        assert server.writer.write_response.call_count == 5