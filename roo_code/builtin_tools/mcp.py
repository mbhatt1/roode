"""MCP (Model Context Protocol) tools for server integration."""

import logging
from typing import Any, Dict, Optional
from ..tools import Tool, ToolInputSchema, ToolResult
from .mcp_manager import McpManager
from .mcp_client import McpError, McpConnectionError, McpTimeoutError

logger = logging.getLogger(__name__)

# Global MCP manager instance
_mcp_manager: Optional[McpManager] = None


def get_mcp_manager() -> McpManager:
    """
    Get or create the global MCP manager instance.
    
    Returns:
        Global MCP manager
    """
    global _mcp_manager
    if _mcp_manager is None:
        _mcp_manager = McpManager()
    return _mcp_manager


def set_mcp_manager(manager: McpManager) -> None:
    """
    Set the global MCP manager instance.
    
    Args:
        manager: MCP manager to use
    """
    global _mcp_manager
    _mcp_manager = manager


class UseMcpToolTool(Tool):
    """Tool for executing MCP server tools with automatic retry on connection failures."""
    
    def __init__(self, enable_retry: bool = True, enable_circuit_breaker: bool = True):
        super().__init__(
            name="use_mcp_tool",
            description=(
                "Request to execute a tool from an MCP server. MCP servers provide additional "
                "capabilities like API integrations, database access, or specialized functions."
            ),
            input_schema=ToolInputSchema(
                type="object",
                properties={
                    "server_name": {
                        "type": "string",
                        "description": "Name of the MCP server"
                    },
                    "tool_name": {
                        "type": "string",
                        "description": "Name of the tool to execute"
                    },
                    "arguments": {
                        "type": "object",
                        "description": "Arguments to pass to the tool"
                    }
                },
                required=["server_name", "tool_name"]
            ),
            enable_retry=enable_retry,
            enable_circuit_breaker=enable_circuit_breaker  # MCP connections can fail repeatedly
        )
    
    async def execute(self, input_data: Dict[str, Any]) -> ToolResult:
        """Execute an MCP tool with proper error classification for retry."""
        from .error_recovery import (
            NetworkError, TimeoutError as RooTimeoutError,
            ValidationError
        )
        
        try:
            server_name = input_data["server_name"]
            tool_name = input_data["tool_name"]
            arguments = input_data.get("arguments", {})
            
            logger.info(f"Executing MCP tool: {server_name}.{tool_name}")
            
            # Get MCP manager
            manager = get_mcp_manager()
            
            # Check if server is connected
            client = manager.get_client(server_name)
            if client is None:
                # Try to connect
                try:
                    logger.info(f"Server {server_name} not connected, attempting to connect...")
                    await manager.connect_server(server_name)
                except McpConnectionError as e:
                    # Recoverable: connection might succeed on retry
                    raise NetworkError(
                        f"Failed to connect to MCP server '{server_name}': {str(e)}"
                    )
                except Exception as e:
                    # Unexpected connection error - might be recoverable
                    raise NetworkError(
                        f"Unexpected error connecting to server '{server_name}': {str(e)}"
                    )
            
            # Call the tool
            try:
                result = await manager.call_tool(server_name, tool_name, arguments)
                
                # Format the result
                if "content" in result:
                    content_items = result["content"]
                    if isinstance(content_items, list):
                        # Combine multiple content items
                        parts = []
                        for item in content_items:
                            if isinstance(item, dict):
                                if item.get("type") == "text":
                                    parts.append(item.get("text", ""))
                                elif item.get("type") == "resource":
                                    parts.append(f"Resource: {item.get('resource', {}).get('uri', 'unknown')}")
                                else:
                                    parts.append(str(item))
                            else:
                                parts.append(str(item))
                        content = "\n".join(parts)
                    else:
                        content = str(content_items)
                else:
                    content = str(result)
                
                return ToolResult(
                    tool_use_id=self.current_use_id,
                    content=content,
                    is_error=False
                )
                
            except McpTimeoutError as e:
                # Recoverable: timeout might not happen on retry
                raise RooTimeoutError(
                    f"Tool execution timed out: {tool_name} on server {server_name}: {str(e)}"
                )
            except McpConnectionError as e:
                # Recoverable: connection might be restored
                raise NetworkError(
                    f"Connection error calling tool '{tool_name}' on server '{server_name}': {str(e)}"
                )
            except McpError as e:
                # MCP protocol errors are usually not recoverable
                raise ValidationError(
                    f"MCP error calling tool '{tool_name}' on server '{server_name}': {str(e)}"
                )
            
        except KeyError as e:
            # Missing parameters are not recoverable
            raise ValidationError(f"Missing required parameter: {str(e)}")
        except (NetworkError, RooTimeoutError, ValidationError):
            # Re-raise our custom errors
            raise
        except Exception as e:
            logger.exception(f"Unexpected error executing MCP tool")
            # Unknown errors - don't retry by default
            raise ValidationError(f"Unexpected error executing MCP tool: {str(e)}")


class AccessMcpResourceTool(Tool):
    """Tool for accessing MCP resources."""
    
    def __init__(self):
        super().__init__(
            name="access_mcp_resource",
            description=(
                "Request to access a resource from an MCP server. Resources can include "
                "files, database records, API responses, or other data provided by the server."
            ),
            input_schema=ToolInputSchema(
                type="object",
                properties={
                    "server_name": {
                        "type": "string",
                        "description": "Name of the MCP server"
                    },
                    "resource_uri": {
                        "type": "string",
                        "description": "URI of the resource to access"
                    }
                },
                required=["server_name", "resource_uri"]
            )
        )
    
    async def execute(self, input_data: Dict[str, Any]) -> ToolResult:
        """Access an MCP resource."""
        try:
            server_name = input_data["server_name"]
            resource_uri = input_data["resource_uri"]
            
            logger.info(f"Accessing MCP resource: {server_name}:{resource_uri}")
            
            # Get MCP manager
            manager = get_mcp_manager()
            
            # Check if server is connected
            client = manager.get_client(server_name)
            if client is None:
                # Try to connect
                try:
                    logger.info(f"Server {server_name} not connected, attempting to connect...")
                    await manager.connect_server(server_name)
                except McpConnectionError as e:
                    return ToolResult(
                        tool_use_id=self.current_use_id,
                        content=(
                            f"Failed to connect to MCP server '{server_name}'.\n"
                            f"Error: {str(e)}\n\n"
                            f"Please ensure:\n"
                            f"1. The server is configured in your MCP settings\n"
                            f"2. The server command and arguments are correct\n"
                            f"3. Required environment variables are set"
                        ),
                        is_error=True
                    )
                except Exception as e:
                    return ToolResult(
                        tool_use_id=self.current_use_id,
                        content=f"Unexpected error connecting to server '{server_name}': {str(e)}",
                        is_error=True
                    )
            
            # Read the resource
            try:
                result = await manager.read_resource(server_name, resource_uri)
                
                # Format the result
                if "contents" in result:
                    contents = result["contents"]
                    if isinstance(contents, list):
                        # Combine multiple content items
                        parts = []
                        for item in contents:
                            if isinstance(item, dict):
                                if item.get("mimeType"):
                                    parts.append(f"[{item['mimeType']}]")
                                if item.get("text"):
                                    parts.append(item["text"])
                                elif item.get("blob"):
                                    parts.append(f"<binary data: {len(item['blob'])} bytes>")
                            else:
                                parts.append(str(item))
                        content = "\n".join(parts)
                    else:
                        content = str(contents)
                else:
                    content = str(result)
                
                return ToolResult(
                    tool_use_id=self.current_use_id,
                    content=content,
                    is_error=False
                )
                
            except McpError as e:
                return ToolResult(
                    tool_use_id=self.current_use_id,
                    content=(
                        f"MCP error reading resource '{resource_uri}' from server '{server_name}':\n"
                        f"{str(e)}"
                    ),
                    is_error=True
                )
            
        except KeyError as e:
            return ToolResult(
                tool_use_id=self.current_use_id,
                content=f"Missing required parameter: {str(e)}",
                is_error=True
            )
        except Exception as e:
            logger.exception(f"Unexpected error accessing MCP resource")
            return ToolResult(
                tool_use_id=self.current_use_id,
                content=f"Unexpected error accessing MCP resource: {str(e)}",
                is_error=True
            )