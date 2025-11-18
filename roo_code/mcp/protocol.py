"""
JSON-RPC 2.0 protocol message handling for MCP server.

This module provides classes and utilities for handling JSON-RPC 2.0 messages,
including request/response formatting and error code definitions.
"""

import json
import logging
from enum import IntEnum
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class McpErrorCode(IntEnum):
    """Standard JSON-RPC and MCP-specific error codes."""
    
    # JSON-RPC standard errors
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603
    
    # MCP-specific errors
    MODE_NOT_FOUND = -32001
    TASK_NOT_FOUND = -32002
    SESSION_EXPIRED = -32003
    VALIDATION_ERROR = -32004
    TOOL_RESTRICTION_ERROR = -32005
    FILE_RESTRICTION_ERROR = -32006


class McpProtocolError(Exception):
    """Base exception for MCP protocol errors."""
    
    def __init__(
        self,
        code: int,
        message: str,
        data: Any = None
    ):
        """
        Initialize protocol error.
        
        Args:
            code: Error code (from McpErrorCode)
            message: Error message
            data: Additional error data
        """
        self.code = code
        self.message = message
        self.data = data
        super().__init__(message)


class JsonRpcMessage:
    """Represents a JSON-RPC 2.0 message."""
    
    @staticmethod
    def create_request(
        method: str,
        params: Optional[Dict[str, Any]] = None,
        request_id: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Create a JSON-RPC request message.
        
        Args:
            method: Method name to call
            params: Method parameters
            request_id: Request ID (None for notifications)
            
        Returns:
            JSON-RPC request dict
        """
        message = {
            "jsonrpc": "2.0",
            "method": method
        }
        
        if params is not None:
            message["params"] = params
            
        if request_id is not None:
            message["id"] = request_id
            
        return message
    
    @staticmethod
    def create_response(
        request_id: Any,
        result: Any
    ) -> Dict[str, Any]:
        """
        Create a successful JSON-RPC response.
        
        Args:
            request_id: ID from the request
            result: Result data
            
        Returns:
            JSON-RPC response dict
        """
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": result
        }
    
    @staticmethod
    def create_error(
        request_id: Any,
        code: int,
        message: str,
        data: Any = None
    ) -> Dict[str, Any]:
        """
        Create an error JSON-RPC response.
        
        Args:
            request_id: ID from the request (None for parse errors)
            code: Error code
            message: Error message
            data: Additional error data
            
        Returns:
            JSON-RPC error response dict
        """
        error = {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": code,
                "message": message
            }
        }
        
        if data is not None:
            error["error"]["data"] = data
            
        return error
    
    @staticmethod
    def validate_request(message: Dict[str, Any]) -> None:
        """
        Validate a JSON-RPC request message.
        
        Args:
            message: Message to validate
            
        Raises:
            McpProtocolError: If message is invalid
        """
        # Check jsonrpc version
        if message.get("jsonrpc") != "2.0":
            raise McpProtocolError(
                code=McpErrorCode.INVALID_REQUEST,
                message="Invalid JSON-RPC version, must be '2.0'"
            )
        
        # Check method exists
        if "method" not in message:
            raise McpProtocolError(
                code=McpErrorCode.INVALID_REQUEST,
                message="Missing 'method' field"
            )
        
        # Method must be a string
        if not isinstance(message["method"], str):
            raise McpProtocolError(
                code=McpErrorCode.INVALID_REQUEST,
                message="Method must be a string"
            )
    
    @staticmethod
    def is_notification(message: Dict[str, Any]) -> bool:
        """
        Check if message is a notification (no ID).
        
        Args:
            message: Message to check
            
        Returns:
            True if notification, False otherwise
        """
        return "id" not in message


class MessageParser:
    """Parses JSON-RPC messages from byte streams."""
    
    @staticmethod
    def parse_message(data: bytes) -> Dict[str, Any]:
        """
        Parse a JSON-RPC message from bytes.
        
        Args:
            data: Raw message bytes
            
        Returns:
            Parsed message dict
            
        Raises:
            McpProtocolError: If parsing fails
        """
        try:
            decoded = data.decode('utf-8').strip()
            if not decoded:
                raise McpProtocolError(
                    code=McpErrorCode.PARSE_ERROR,
                    message="Empty message"
                )
            
            message = json.loads(decoded)
            
            if not isinstance(message, dict):
                raise McpProtocolError(
                    code=McpErrorCode.INVALID_REQUEST,
                    message="Message must be a JSON object"
                )
            
            return message
            
        except json.JSONDecodeError as e:
            raise McpProtocolError(
                code=McpErrorCode.PARSE_ERROR,
                message="Invalid JSON",
                data=str(e)
            )
        except UnicodeDecodeError as e:
            raise McpProtocolError(
                code=McpErrorCode.PARSE_ERROR,
                message="Invalid UTF-8 encoding",
                data=str(e)
            )
    
    @staticmethod
    def serialize_message(message: Dict[str, Any]) -> bytes:
        """
        Serialize a message to bytes for transmission.
        
        Args:
            message: Message dict to serialize
            
        Returns:
            Message as UTF-8 encoded bytes with newline
        """
        json_str = json.dumps(message, ensure_ascii=False)
        return (json_str + '\n').encode('utf-8')


class MessageWriter:
    """Handles writing messages to output stream."""
    
    def __init__(self, stream):
        """
        Initialize message writer.
        
        Args:
            stream: Output stream (e.g., sys.stdout.buffer)
        """
        self.stream = stream
    
    def write_message(self, message: Dict[str, Any]) -> None:
        """
        Write a message to the output stream.
        
        Args:
            message: Message to write
        """
        data = MessageParser.serialize_message(message)
        self.stream.write(data)
        self.stream.flush()
    
    def write_response(self, request_id: Any, result: Any) -> None:
        """
        Write a successful response.
        
        Args:
            request_id: Request ID
            result: Result data
        """
        response = JsonRpcMessage.create_response(request_id, result)
        self.write_message(response)
    
    def write_error(
        self,
        request_id: Any,
        code: int,
        message: str,
        data: Any = None
    ) -> None:
        """
        Write an error response.
        
        Args:
            request_id: Request ID (None for parse errors)
            code: Error code
            message: Error message
            data: Additional error data
        """
        error = JsonRpcMessage.create_error(request_id, code, message, data)
        self.write_message(error)
    
    def write_notification(
        self,
        method: str,
        params: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Write a notification message.
        
        Args:
            method: Method name
            params: Method parameters
        """
        notification = JsonRpcMessage.create_request(method, params)
        self.write_message(notification)