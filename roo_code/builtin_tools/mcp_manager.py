"""MCP server manager for handling multiple MCP server connections.

This module provides centralized management of MCP servers including:
- Server configuration loading from JSON files
- Server lifecycle management (start, stop, restart)
- Connection pooling and health checks
- Server capability caching
"""

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import asdict

from .mcp_client import (
    McpClient,
    McpServer,
    McpTool,
    McpResource,
    ServerStatus,
    McpError,
    McpConnectionError
)

logger = logging.getLogger(__name__)


class McpManager:
    """
    Manages multiple MCP server connections.
    
    Provides centralized management of server lifecycle, configuration,
    and connection pooling.
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the MCP manager.
        
        Args:
            config_path: Optional path to configuration file
        """
        self.clients: Dict[str, McpClient] = {}
        self.servers: Dict[str, McpServer] = {}
        self.config_path = config_path
        self._lock = asyncio.Lock()
        
    async def load_config(self, config_path: Optional[str] = None) -> None:
        """
        Load MCP server configuration from a JSON file.
        
        Args:
            config_path: Path to configuration file. If None, uses instance config_path.
            
        Raises:
            FileNotFoundError: If config file doesn't exist
            json.JSONDecodeError: If config file is invalid JSON
            ValueError: If config structure is invalid
        """
        path = config_path or self.config_path
        if path is None:
            raise ValueError("No configuration path provided")
        
        logger.info(f"Loading MCP configuration from: {path}")
        
        # Read and parse config file
        config_file = Path(path)
        if not config_file.exists():
            raise FileNotFoundError(f"Configuration file not found: {path}")
        
        with open(config_file, 'r') as f:
            config_data = json.load(f)
        
        # Validate config structure
        if not isinstance(config_data, dict):
            raise ValueError("Configuration must be a JSON object")
        
        if "mcpServers" not in config_data:
            raise ValueError("Configuration must contain 'mcpServers' key")
        
        mcp_servers = config_data["mcpServers"]
        if not isinstance(mcp_servers, dict):
            raise ValueError("'mcpServers' must be a JSON object")
        
        # Parse server configurations
        for server_name, server_config in mcp_servers.items():
            await self._add_server_from_config(server_name, server_config)
        
        logger.info(f"Loaded {len(self.servers)} MCP server configurations")
    
    async def _add_server_from_config(self, name: str, config: Dict[str, Any]) -> None:
        """
        Add a server from configuration data.
        
        Args:
            name: Server name
            config: Server configuration dictionary
            
        Raises:
            ValueError: If configuration is invalid
        """
        # Validate required fields
        if "command" not in config:
            raise ValueError(f"Server '{name}' missing required 'command' field")
        
        # Extract configuration
        command = config["command"]
        args = config.get("args", [])
        env = config.get("env", {})
        cwd = config.get("cwd")
        disabled = config.get("disabled", False)
        timeout = config.get("timeout", 60)
        
        # Validate types
        if not isinstance(command, str):
            raise ValueError(f"Server '{name}' command must be a string")
        if not isinstance(args, list):
            raise ValueError(f"Server '{name}' args must be a list")
        if not isinstance(env, dict):
            raise ValueError(f"Server '{name}' env must be a dictionary")
        if cwd is not None and not isinstance(cwd, str):
            raise ValueError(f"Server '{name}' cwd must be a string or null")
        if not isinstance(disabled, bool):
            raise ValueError(f"Server '{name}' disabled must be a boolean")
        if not isinstance(timeout, (int, float)) or timeout <= 0:
            raise ValueError(f"Server '{name}' timeout must be a positive number")
        
        # Create server object
        server = McpServer(
            name=name,
            command=command,
            args=args,
            env=env,
            cwd=cwd,
            disabled=disabled,
            timeout=int(timeout)
        )
        
        async with self._lock:
            self.servers[name] = server
            
        logger.debug(f"Added server configuration: {name}")
    
    async def connect_server(self, server_name: str) -> McpClient:
        """
        Connect to an MCP server.
        
        Args:
            server_name: Name of the server to connect to
            
        Returns:
            Connected MCP client
            
        Raises:
            ValueError: If server not found
            McpConnectionError: If connection fails
        """
        async with self._lock:
            server = self.servers.get(server_name)
            if server is None:
                raise ValueError(f"Server '{server_name}' not found in configuration")
            
            if server.disabled:
                raise ValueError(f"Server '{server_name}' is disabled")
            
            # Check if already connected
            if server_name in self.clients:
                client = self.clients[server_name]
                if client.is_connected():
                    logger.debug(f"Server '{server_name}' already connected")
                    return client
                else:
                    # Clean up stale client
                    await client.close()
                    del self.clients[server_name]
        
        # Create and connect client
        logger.info(f"Connecting to server: {server_name}")
        client = McpClient(server)
        
        try:
            await client.connect()
            
            # Fetch tools and resources
            await client.list_tools()
            await client.list_resources()
            
            async with self._lock:
                self.clients[server_name] = client
            
            logger.info(f"Successfully connected to server: {server_name}")
            return client
            
        except Exception as e:
            logger.error(f"Failed to connect to server '{server_name}': {e}")
            await client.close()
            raise McpConnectionError(f"Failed to connect to '{server_name}': {e}")
    
    async def disconnect_server(self, server_name: str) -> None:
        """
        Disconnect from an MCP server.
        
        Args:
            server_name: Name of the server to disconnect from
        """
        async with self._lock:
            client = self.clients.pop(server_name, None)
        
        if client is not None:
            logger.info(f"Disconnecting from server: {server_name}")
            await client.close()
            logger.info(f"Disconnected from server: {server_name}")
    
    async def restart_server(self, server_name: str) -> McpClient:
        """
        Restart an MCP server connection.
        
        Args:
            server_name: Name of the server to restart
            
        Returns:
            Reconnected MCP client
            
        Raises:
            ValueError: If server not found
            McpConnectionError: If reconnection fails
        """
        logger.info(f"Restarting server: {server_name}")
        
        await self.disconnect_server(server_name)
        
        # Small delay before reconnecting
        await asyncio.sleep(0.5)
        
        return await self.connect_server(server_name)
    
    async def connect_all(self) -> None:
        """
        Connect to all configured and enabled servers.
        """
        logger.info("Connecting to all enabled MCP servers")
        
        enabled_servers = [
            name for name, server in self.servers.items()
            if not server.disabled
        ]
        
        # Connect to servers concurrently
        tasks = [self.connect_server(name) for name in enabled_servers]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Log results
        for name, result in zip(enabled_servers, results):
            if isinstance(result, Exception):
                logger.error(f"Failed to connect to server '{name}': {result}")
            else:
                logger.info(f"Successfully connected to server '{name}'")
    
    async def disconnect_all(self) -> None:
        """
        Disconnect from all servers.
        """
        logger.info("Disconnecting from all MCP servers")
        
        server_names = list(self.clients.keys())
        tasks = [self.disconnect_server(name) for name in server_names]
        await asyncio.gather(*tasks, return_exceptions=True)
        
        logger.info("Disconnected from all MCP servers")
    
    def get_client(self, server_name: str) -> Optional[McpClient]:
        """
        Get a connected client for a server.
        
        Args:
            server_name: Name of the server
            
        Returns:
            MCP client if connected, None otherwise
        """
        return self.clients.get(server_name)
    
    def get_server(self, server_name: str) -> Optional[McpServer]:
        """
        Get server configuration.
        
        Args:
            server_name: Name of the server
            
        Returns:
            Server configuration if found, None otherwise
        """
        return self.servers.get(server_name)
    
    def list_servers(self) -> List[str]:
        """
        List all configured server names.
        
        Returns:
            List of server names
        """
        return list(self.servers.keys())
    
    def list_connected_servers(self) -> List[str]:
        """
        List all currently connected server names.
        
        Returns:
            List of connected server names
        """
        return [
            name for name, client in self.clients.items()
            if client.is_connected()
        ]
    
    async def get_all_tools(self) -> List[McpTool]:
        """
        Get all tools from all connected servers.
        
        Returns:
            List of all available tools
        """
        tools = []
        for client in self.clients.values():
            if client.is_connected():
                tools.extend(client.server.tools)
        return tools
    
    async def get_server_tools(self, server_name: str) -> List[McpTool]:
        """
        Get tools from a specific server.
        
        Args:
            server_name: Name of the server
            
        Returns:
            List of tools from the server
            
        Raises:
            ValueError: If server not found or not connected
        """
        client = self.get_client(server_name)
        if client is None:
            raise ValueError(f"Server '{server_name}' not connected")
        
        if not client.is_connected():
            raise ValueError(f"Server '{server_name}' not connected")
        
        return client.server.tools
    
    async def get_mcp_tool_definitions(self) -> List[Dict[str, Any]]:
        """
        Get all MCP tools as API tool definitions.
        
        Converts MCP tool schemas to the format expected by the API
        (Anthropic/OpenAI compatible tool definitions).
        
        Returns:
            List of tool definitions ready to send to API
        """
        tool_definitions = []
        
        for client in self.clients.values():
            if not client.is_connected():
                continue
            
            for mcp_tool in client.server.tools:
                # Convert MCP tool to API tool definition
                tool_def = {
                    "name": f"{mcp_tool.server_name}__{mcp_tool.name}",  # Prefix with server name to avoid conflicts
                    "description": mcp_tool.description or f"Tool from MCP server {mcp_tool.server_name}",
                    "input_schema": mcp_tool.input_schema
                }
                tool_definitions.append(tool_def)
        
        logger.debug(f"Generated {len(tool_definitions)} MCP tool definitions")
        return tool_definitions
    
    async def get_all_resources(self) -> List[McpResource]:
        """
        Get all resources from all connected servers.
        
        Returns:
            List of all available resources
        """
        resources = []
        for client in self.clients.values():
            if client.is_connected():
                resources.extend(client.server.resources)
        return resources
    
    async def get_server_resources(self, server_name: str) -> List[McpResource]:
        """
        Get resources from a specific server.
        
        Args:
            server_name: Name of the server
            
        Returns:
            List of resources from the server
            
        Raises:
            ValueError: If server not found or not connected
        """
        client = self.get_client(server_name)
        if client is None:
            raise ValueError(f"Server '{server_name}' not connected")
        
        if not client.is_connected():
            raise ValueError(f"Server '{server_name}' not connected")
        
        return client.server.resources
    
    async def call_tool(
        self,
        server_name: str,
        tool_name: str,
        arguments: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Call a tool on a specific server.
        
        Args:
            server_name: Name of the server
            tool_name: Name of the tool
            arguments: Tool arguments
            
        Returns:
            Tool execution result
            
        Raises:
            ValueError: If server not found or not connected
            McpError: If tool call fails
        """
        client = self.get_client(server_name)
        if client is None:
            raise ValueError(f"Server '{server_name}' not connected")
        
        if not client.is_connected():
            raise ValueError(f"Server '{server_name}' not connected")
        
        return await client.call_tool(tool_name, arguments)
    
    async def read_resource(
        self,
        server_name: str,
        uri: str
    ) -> Dict[str, Any]:
        """
        Read a resource from a specific server.
        
        Args:
            server_name: Name of the server
            uri: Resource URI
            
        Returns:
            Resource contents
            
        Raises:
            ValueError: If server not found or not connected
            McpError: If resource read fails
        """
        client = self.get_client(server_name)
        if client is None:
            raise ValueError(f"Server '{server_name}' not connected")
        
        if not client.is_connected():
            raise ValueError(f"Server '{server_name}' not connected")
        
        return await client.read_resource(uri)
    
    async def health_check(self, server_name: str) -> bool:
        """
        Check if a server is healthy and connected.
        
        Args:
            server_name: Name of the server
            
        Returns:
            True if server is healthy, False otherwise
        """
        client = self.get_client(server_name)
        if client is None:
            return False
        
        return client.is_connected()
    
    async def health_check_all(self) -> Dict[str, bool]:
        """
        Check health of all servers.
        
        Returns:
            Dictionary mapping server names to health status
        """
        results = {}
        for server_name in self.servers.keys():
            results[server_name] = await self.health_check(server_name)
        return results
    
    def get_server_status(self, server_name: str) -> Optional[ServerStatus]:
        """
        Get the status of a server.
        
        Args:
            server_name: Name of the server
            
        Returns:
            Server status if found, None otherwise
        """
        server = self.get_server(server_name)
        if server is None:
            return None
        return server.status
    
    def get_all_statuses(self) -> Dict[str, ServerStatus]:
        """
        Get status of all servers.
        
        Returns:
            Dictionary mapping server names to their status
        """
        return {
            name: server.status
            for name, server in self.servers.items()
        }
    
    async def __aenter__(self):
        """Context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - cleanup all connections."""
        await self.disconnect_all()