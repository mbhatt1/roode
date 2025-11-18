"""MCP (Model Context Protocol) client implementation.

This module provides a complete MCP client for communicating with MCP servers
via stdio, implementing the JSON-RPC 2.0 protocol.
"""

import asyncio
import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class ServerStatus(Enum):
    """Status of an MCP server connection."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"


@dataclass
class McpTool:
    """Represents a tool available from an MCP server."""
    name: str
    description: str
    input_schema: Dict[str, Any]
    server_name: str


@dataclass
class McpResource:
    """Represents a resource available from an MCP server."""
    uri: str
    name: str
    mime_type: Optional[str] = None
    description: Optional[str] = None
    server_name: Optional[str] = None


@dataclass
class McpServer:
    """Configuration and state for an MCP server."""
    name: str
    command: str
    args: List[str] = field(default_factory=list)
    env: Dict[str, str] = field(default_factory=dict)
    cwd: Optional[str] = None
    status: ServerStatus = ServerStatus.DISCONNECTED
    error: str = ""
    process: Optional[asyncio.subprocess.Process] = None
    capabilities: Dict[str, Any] = field(default_factory=dict)
    tools: List[McpTool] = field(default_factory=list)
    resources: List[McpResource] = field(default_factory=list)
    disabled: bool = False
    timeout: int = 60  # Default timeout in seconds


class McpError(Exception):
    """Base exception for MCP client errors."""
    pass


class McpConnectionError(McpError):
    """Error establishing or maintaining MCP connection."""
    pass


class McpTimeoutError(McpError):
    """Timeout during MCP operation."""
    pass


class McpProtocolError(McpError):
    """Error in MCP protocol communication."""
    pass


class McpClient:
    """
    MCP client for communicating with MCP servers via stdio.
    
    Implements JSON-RPC 2.0 protocol over stdin/stdout.
    """
    
    def __init__(self, server: McpServer):
        """
        Initialize MCP client.
        
        Args:
            server: MCP server configuration
        """
        self.server = server
        self.process: Optional[asyncio.subprocess.Process] = None
        self.request_id = 0
        self.pending_requests: Dict[int, asyncio.Future] = {}
        self.reader_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
        
    async def connect(self) -> None:
        """
        Connect to the MCP server by starting the subprocess.
        
        Raises:
            McpConnectionError: If connection fails
        """
        if self.process is not None:
            logger.warning(f"Server {self.server.name} already connected")
            return
            
        try:
            self.server.status = ServerStatus.CONNECTING
            logger.info(f"Connecting to MCP server: {self.server.name}")
            
            # Prepare environment variables
            env = os.environ.copy()
            env.update(self.server.env)
            
            # Start the subprocess
            self.process = await asyncio.create_subprocess_exec(
                self.server.command,
                *self.server.args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
                cwd=self.server.cwd
            )
            
            self.server.process = self.process
            
            # Start reading responses
            self.reader_task = asyncio.create_task(self._read_responses())
            
            # Initialize the connection
            await self._initialize()
            
            self.server.status = ServerStatus.CONNECTED
            self.server.error = ""
            logger.info(f"Successfully connected to MCP server: {self.server.name}")
            
        except Exception as e:
            self.server.status = ServerStatus.DISCONNECTED
            self.server.error = str(e)
            logger.error(f"Failed to connect to MCP server {self.server.name}: {e}")
            await self.close()
            raise McpConnectionError(f"Failed to connect to {self.server.name}: {e}")
    
    async def _initialize(self) -> Dict[str, Any]:
        """
        Send initialize request to server.
        
        Returns:
            Server capabilities
            
        Raises:
            McpProtocolError: If initialization fails
        """
        response = await self._send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "roots": {
                    "listChanged": True
                },
                "sampling": {}
            },
            "clientInfo": {
                "name": "roo-code-python",
                "version": "1.0.0"
            }
        })
        
        if "capabilities" in response:
            self.server.capabilities = response["capabilities"]
        
        # Send initialized notification
        await self._send_notification("notifications/initialized", {})
        
        return response
    
    async def list_tools(self) -> List[McpTool]:
        """
        List all tools available from the server.
        
        Returns:
            List of available tools
            
        Raises:
            McpError: If listing fails
        """
        try:
            response = await self._send_request("tools/list", {})
            tools = []
            
            for tool_data in response.get("tools", []):
                tools.append(McpTool(
                    name=tool_data["name"],
                    description=tool_data.get("description", ""),
                    input_schema=tool_data.get("inputSchema", {}),
                    server_name=self.server.name
                ))
            
            self.server.tools = tools
            return tools
            
        except Exception as e:
            logger.error(f"Failed to list tools from {self.server.name}: {e}")
            raise McpError(f"Failed to list tools: {e}")
    
    async def call_tool(self, tool_name: str, arguments: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Call a tool on the MCP server.
        
        Args:
            tool_name: Name of the tool to call
            arguments: Arguments to pass to the tool
            
        Returns:
            Tool execution result
            
        Raises:
            McpError: If tool call fails
        """
        try:
            params = {"name": tool_name}
            if arguments:
                params["arguments"] = arguments
            
            response = await self._send_request(
                "tools/call",
                params,
                timeout=self.server.timeout
            )
            
            return response
            
        except asyncio.TimeoutError:
            raise McpTimeoutError(f"Tool call timed out after {self.server.timeout}s")
        except Exception as e:
            logger.error(f"Failed to call tool {tool_name} on {self.server.name}: {e}")
            raise McpError(f"Failed to call tool: {e}")
    
    async def list_resources(self) -> List[McpResource]:
        """
        List all resources available from the server.
        
        Returns:
            List of available resources
            
        Raises:
            McpError: If listing fails
        """
        try:
            response = await self._send_request("resources/list", {})
            resources = []
            
            for resource_data in response.get("resources", []):
                resources.append(McpResource(
                    uri=resource_data["uri"],
                    name=resource_data.get("name", ""),
                    mime_type=resource_data.get("mimeType"),
                    description=resource_data.get("description"),
                    server_name=self.server.name
                ))
            
            self.server.resources = resources
            return resources
            
        except Exception as e:
            logger.error(f"Failed to list resources from {self.server.name}: {e}")
            raise McpError(f"Failed to list resources: {e}")
    
    async def read_resource(self, uri: str) -> Dict[str, Any]:
        """
        Read a resource from the MCP server.
        
        Args:
            uri: URI of the resource to read
            
        Returns:
            Resource contents
            
        Raises:
            McpError: If resource read fails
        """
        try:
            response = await self._send_request("resources/read", {"uri": uri})
            return response
            
        except Exception as e:
            logger.error(f"Failed to read resource {uri} from {self.server.name}: {e}")
            raise McpError(f"Failed to read resource: {e}")
    
    async def _send_request(
        self,
        method: str,
        params: Dict[str, Any],
        timeout: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Send a JSON-RPC request to the server.
        
        Args:
            method: RPC method name
            params: Method parameters
            timeout: Optional timeout in seconds
            
        Returns:
            Response result
            
        Raises:
            McpProtocolError: If request fails
            McpTimeoutError: If request times out
        """
        if self.process is None or self.process.stdin is None:
            raise McpConnectionError("Not connected to server")
        
        async with self._lock:
            self.request_id += 1
            request_id = self.request_id
        
        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params
        }
        
        # Create a future for this request
        future = asyncio.Future()
        self.pending_requests[request_id] = future
        
        try:
            # Send the request
            request_json = json.dumps(request) + "\n"
            self.process.stdin.write(request_json.encode())
            await self.process.stdin.drain()
            
            logger.debug(f"Sent request to {self.server.name}: {method}")
            
            # Wait for response with timeout
            timeout_value = timeout if timeout is not None else 30
            result = await asyncio.wait_for(future, timeout=timeout_value)
            
            return result
            
        except asyncio.TimeoutError:
            self.pending_requests.pop(request_id, None)
            raise McpTimeoutError(f"Request timed out after {timeout_value}s")
        except Exception as e:
            self.pending_requests.pop(request_id, None)
            raise McpProtocolError(f"Request failed: {e}")
    
    async def _send_notification(self, method: str, params: Dict[str, Any]) -> None:
        """
        Send a JSON-RPC notification (no response expected).
        
        Args:
            method: RPC method name
            params: Method parameters
        """
        if self.process is None or self.process.stdin is None:
            raise McpConnectionError("Not connected to server")
        
        notification = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params
        }
        
        notification_json = json.dumps(notification) + "\n"
        self.process.stdin.write(notification_json.encode())
        await self.process.stdin.drain()
        
        logger.debug(f"Sent notification to {self.server.name}: {method}")
    
    async def _read_responses(self) -> None:
        """
        Read responses from the server in a loop.
        
        Runs as a background task to handle incoming messages.
        """
        if self.process is None or self.process.stdout is None:
            return
        
        try:
            while True:
                line = await self.process.stdout.readline()
                if not line:
                    # EOF reached
                    break
                
                try:
                    response = json.loads(line.decode())
                    await self._handle_response(response)
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse response from {self.server.name}: {e}")
                except Exception as e:
                    logger.error(f"Error handling response from {self.server.name}: {e}")
                    
        except Exception as e:
            logger.error(f"Error reading from {self.server.name}: {e}")
        finally:
            # Clean up pending requests
            for future in self.pending_requests.values():
                if not future.done():
                    future.set_exception(McpConnectionError("Connection closed"))
            self.pending_requests.clear()
    
    async def _handle_response(self, response: Dict[str, Any]) -> None:
        """
        Handle a response from the server.
        
        Args:
            response: JSON-RPC response
        """
        # Check if it's a response to a request
        if "id" in response:
            request_id = response["id"]
            future = self.pending_requests.pop(request_id, None)
            
            if future is None:
                logger.warning(f"Received response for unknown request ID: {request_id}")
                return
            
            # Check for errors
            if "error" in response:
                error = response["error"]
                error_msg = error.get("message", "Unknown error")
                future.set_exception(McpProtocolError(f"Server error: {error_msg}"))
            elif "result" in response:
                future.set_result(response["result"])
            else:
                future.set_exception(McpProtocolError("Invalid response format"))
        
        # Handle notifications (method but no id)
        elif "method" in response:
            # Log notifications but don't process them for now
            logger.debug(f"Received notification from {self.server.name}: {response['method']}")
    
    async def close(self) -> None:
        """
        Close the connection to the MCP server.
        """
        logger.info(f"Closing connection to MCP server: {self.server.name}")
        
        # Cancel reader task
        if self.reader_task is not None:
            self.reader_task.cancel()
            try:
                await self.reader_task
            except asyncio.CancelledError:
                pass
            self.reader_task = None
        
        # Close the process
        if self.process is not None:
            try:
                # Try graceful shutdown first
                if self.process.stdin is not None:
                    self.process.stdin.close()
                    await self.process.stdin.wait_closed()
                
                # Wait for process to exit
                try:
                    await asyncio.wait_for(self.process.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    # Force kill if it doesn't exit
                    self.process.kill()
                    await self.process.wait()
                    
            except Exception as e:
                logger.error(f"Error closing process for {self.server.name}: {e}")
            finally:
                self.process = None
                self.server.process = None
        
        # Clean up pending requests
        for future in self.pending_requests.values():
            if not future.done():
                future.set_exception(McpConnectionError("Connection closed"))
        self.pending_requests.clear()
        
        self.server.status = ServerStatus.DISCONNECTED
        logger.info(f"Closed connection to MCP server: {self.server.name}")
    
    def is_connected(self) -> bool:
        """
        Check if the client is connected.
        
        Returns:
            True if connected, False otherwise
        """
        return (
            self.process is not None
            and self.process.returncode is None
            and self.server.status == ServerStatus.CONNECTED
        )