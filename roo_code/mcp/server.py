"""
Main MCP Modes Server implementation.

This module provides the McpModesServer class which handles the JSON-RPC 2.0
protocol, routes requests to appropriate handlers, and manages server lifecycle.
"""

import asyncio
import logging
import sys
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from ..modes.orchestrator import ModeOrchestrator
from .config import ServerConfig
from .protocol import (
    JsonRpcMessage,
    McpErrorCode,
    McpProtocolError,
    MessageParser,
    MessageWriter,
)
from .resources import ResourceHandler
from .session import SessionManager
from .tools import ToolHandler
from .validation import ValidationError

logger = logging.getLogger(__name__)


class McpModesServer:
    """
    Main MCP server class handling protocol communication and routing.
    
    Responsibilities:
    - JSON-RPC 2.0 message handling
    - Request routing to appropriate handlers
    - Response formatting and error handling
    - Process lifecycle management
    """
    
    def __init__(
        self,
        project_root: Optional[Path] = None,
        global_config_dir: Optional[Path] = None,
        session_timeout: int = 3600,  # 1 hour default
        cleanup_interval: int = 300,  # 5 minutes default
    ):
        """
        Initialize MCP Modes Server.
        
        Args:
            project_root: Project directory for loading project modes
            global_config_dir: Global config directory (~/.roo-code)
            session_timeout: Session timeout in seconds
            cleanup_interval: Session cleanup interval in seconds
        """
        self.project_root = project_root
        self.global_config_dir = global_config_dir or (Path.home() / ".roo-code")
        
        # Initialize mode system
        self.orchestrator = ModeOrchestrator(
            project_root=project_root,
            global_config_dir=global_config_dir
        )
        
        # Initialize session management
        self.session_manager = SessionManager(
            orchestrator=self.orchestrator,
            timeout=session_timeout,
            cleanup_interval=cleanup_interval
        )
        
        # Initialize handlers
        self.resource_handler = ResourceHandler(self.orchestrator)
        self.tool_handler = ToolHandler(self.session_manager, self.orchestrator)
        
        # Server state
        self.running = False
        self.initialized = False
        self.capabilities = self._build_capabilities()
        
        # I/O streams
        self.stdin = sys.stdin.buffer
        self.stdout = sys.stdout.buffer
        self.writer = MessageWriter(self.stdout)
        
        # Message handling
        self.request_handlers = self._register_request_handlers()
        self.notification_handlers = self._register_notification_handlers()
        
        logger.info("MCP Modes Server initialized")
    
    def _build_capabilities(self) -> Dict[str, Any]:
        """
        Build server capabilities.
        
        Returns:
            Dictionary of server capabilities
        """
        return {
            "resources": {
                "listChanged": False  # We don't send resource list change notifications
            },
            "tools": {
                "listChanged": False  # We don't send tool list change notifications
            }
        }
    
    def _register_request_handlers(self) -> Dict[str, Callable]:
        """
        Register all JSON-RPC request handlers.
        
        Returns:
            Dictionary mapping method names to handler functions
        """
        return {
            # Protocol methods
            "initialize": self._handle_initialize,
            
            # Resource methods
            "resources/list": self._handle_list_resources,
            "resources/read": self._handle_read_resource,
            
            # Tool methods
            "tools/list": self._handle_list_tools,
            "tools/call": self._handle_call_tool,
        }
    
    def _register_notification_handlers(self) -> Dict[str, Callable]:
        """
        Register notification handlers.
        
        Returns:
            Dictionary mapping notification names to handler functions
        """
        return {
            "notifications/initialized": self._handle_initialized,
            "cancelled": self._handle_cancelled,
        }
    
    async def run(self) -> None:
        """
        Main server loop - reads from stdin, processes messages, writes to stdout.
        
        Message Format (newline-delimited JSON):
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "resources/list",
            "params": {}
        }
        """
        self.running = True
        
        # Start session manager
        await self.session_manager.start()
        
        logger.info("MCP Modes Server started, waiting for messages...")
        
        try:
            while self.running:
                # Read message (newline-delimited)
                line = await asyncio.get_event_loop().run_in_executor(
                    None, self.stdin.readline
                )
                
                if not line:
                    logger.info("EOF received, shutting down")
                    break  # EOF
                
                try:
                    message = MessageParser.parse_message(line)
                    await self._process_message(message)
                    
                except McpProtocolError as e:
                    logger.warning(f"Protocol error: {e.message}")
                    self.writer.write_error(None, e.code, e.message, e.data)
                    
                except Exception as e:
                    logger.exception("Error processing message")
                    self.writer.write_error(
                        None,
                        McpErrorCode.INTERNAL_ERROR,
                        "Internal error",
                        str(e)
                    )
                    
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
        except Exception as e:
            logger.exception(f"Fatal error in server loop: {e}")
        finally:
            await self.shutdown()
    
    async def _process_message(self, message: Dict[str, Any]) -> None:
        """
        Process a JSON-RPC message.
        
        Args:
            message: Parsed JSON-RPC message
        """
        # Validate message
        JsonRpcMessage.validate_request(message)
        
        method = message.get("method")
        params = message.get("params", {})
        request_id = message.get("id")
        
        # Check if it's a notification (no id)
        if JsonRpcMessage.is_notification(message):
            await self._handle_notification(method, params)
            return
        
        # Handle request
        await self._handle_request(request_id, method, params)
    
    async def _handle_request(
        self,
        request_id: Any,
        method: str,
        params: Dict[str, Any]
    ) -> None:
        """
        Handle a JSON-RPC request.
        
        Args:
            request_id: Request ID
            method: Method name
            params: Method parameters
        """
        logger.debug(f"Handling request: {method} (id={request_id})")
        
        handler = self.request_handlers.get(method)
        if not handler:
            logger.warning(f"Unknown method: {method}")
            self.writer.write_error(
                request_id,
                McpErrorCode.METHOD_NOT_FOUND,
                f"Method not found: {method}"
            )
            return
        
        try:
            await handler(request_id, params)
        except ValidationError as e:
            logger.warning(f"Validation error in {method}: {e}")
            self.writer.write_error(
                request_id,
                McpErrorCode.VALIDATION_ERROR,
                "Validation error",
                str(e)
            )
        except McpProtocolError as e:
            logger.warning(f"Protocol error in {method}: {e.message}")
            self.writer.write_error(request_id, e.code, e.message, e.data)
        except Exception as e:
            logger.exception(f"Error in {method}")
            self.writer.write_error(
                request_id,
                McpErrorCode.INTERNAL_ERROR,
                "Internal server error",
                str(e)
            )
    
    async def _handle_notification(
        self,
        method: str,
        params: Dict[str, Any]
    ) -> None:
        """
        Handle a JSON-RPC notification.
        
        Args:
            method: Notification method name
            params: Notification parameters
        """
        logger.debug(f"Handling notification: {method}")
        
        handler = self.notification_handlers.get(method)
        if handler:
            try:
                await handler(params)
            except Exception as e:
                logger.exception(f"Error in notification handler {method}")
        else:
            logger.debug(f"Unknown notification: {method}")
    
    async def _handle_initialize(
        self,
        request_id: Any,
        params: Dict[str, Any]
    ) -> None:
        """
        Handle initialize request.
        
        Args:
            request_id: Request ID
            params: Initialization parameters
        """
        protocol_version = params.get("protocolVersion", "unknown")
        client_info = params.get("clientInfo", {})
        
        logger.info(
            f"Initialize request from {client_info.get('name', 'unknown')} "
            f"(protocol: {protocol_version})"
        )
        
        result = {
            "protocolVersion": "2024-11-05",
            "serverInfo": {
                "name": "roo-modes-server",
                "version": "1.0.0"
            },
            "capabilities": self.capabilities
        }
        
        self.initialized = True
        self.writer.write_response(request_id, result)
    
    async def _handle_initialized(self, params: Dict[str, Any]) -> None:
        """
        Handle initialized notification.
        
        Args:
            params: Notification parameters
        """
        logger.info("Client initialization complete")
    
    async def _handle_cancelled(self, params: Dict[str, Any]) -> None:
        """
        Handle cancelled notification.
        
        Args:
            params: Cancellation parameters
        """
        request_id = params.get("requestId")
        reason = params.get("reason", "No reason provided")
        logger.info(f"Request {request_id} cancelled: {reason}")
    
    async def _handle_list_resources(
        self,
        request_id: Any,
        params: Dict[str, Any]
    ) -> None:
        """
        Handle resources/list request.
        
        Args:
            request_id: Request ID
            params: Request parameters
        """
        resources = await self.resource_handler.list_resources()
        result = {"resources": resources}
        self.writer.write_response(request_id, result)
    
    async def _handle_read_resource(
        self,
        request_id: Any,
        params: Dict[str, Any]
    ) -> None:
        """
        Handle resources/read request.
        
        Args:
            request_id: Request ID
            params: Request parameters (must include 'uri')
        """
        uri = params.get("uri")
        if not uri:
            raise ValidationError("Missing required parameter: uri")
        
        result = await self.resource_handler.read_resource(uri)
        self.writer.write_response(request_id, result)
    
    async def _handle_list_tools(
        self,
        request_id: Any,
        params: Dict[str, Any]
    ) -> None:
        """
        Handle tools/list request.
        
        Args:
            request_id: Request ID
            params: Request parameters
        """
        tools = await self.tool_handler.list_tools()
        result = {"tools": tools}
        self.writer.write_response(request_id, result)
    
    async def _handle_call_tool(
        self,
        request_id: Any,
        params: Dict[str, Any]
    ) -> None:
        """
        Handle tools/call request.
        
        Args:
            request_id: Request ID
            params: Request parameters (must include 'name' and 'arguments')
        """
        tool_name = params.get("name")
        if not tool_name:
            raise ValidationError("Missing required parameter: name")
        
        arguments = params.get("arguments", {})
        
        result = await self.tool_handler.call_tool(tool_name, arguments)
        self.writer.write_response(request_id, result)
    
    async def shutdown(self) -> None:
        """
        Graceful shutdown of the server.
        
        - Closes all active sessions
        - Stops session manager
        - Cleans up resources
        """
        logger.info("Shutting down MCP Modes Server")
        self.running = False
        
        # Stop session manager
        await self.session_manager.stop()
        
        # Clean up sessions
        await self.session_manager.cleanup_all()
        
        logger.info("Server shutdown complete")
    
    def get_server_info(self) -> Dict[str, Any]:
        """
        Get server information and statistics.
        
        Returns:
            Dictionary with server info
        """
        return {
            "name": "roo-modes-server",
            "version": "1.0.0",
            "running": self.running,
            "initialized": self.initialized,
            "project_root": str(self.project_root) if self.project_root else None,
            "modes_available": len(self.orchestrator.get_all_modes()),
            "active_sessions": self.session_manager.get_session_count(),
            "session_stats": self.session_manager.get_stats(),
        }