"""
MCP Modes Server package.

This package provides an MCP (Model Context Protocol) server that exposes
Roo-Code's mode system through a standardized JSON-RPC 2.0 interface.
"""

__version__ = "1.0.0"

from .server import McpModesServer

__all__ = ["McpModesServer"]