"""
Unit tests for MCP protocol message handling.

Tests JSON-RPC 2.0 message creation, serialization, validation, and error handling.
"""

import json
import pytest
from roo_code.mcp.protocol import (
    McpErrorCode,
    McpProtocolError,
    JsonRpcMessage,
    MessageParser,
    MessageWriter,
)


class TestMcpErrorCode:
    """Test MCP error code enum."""
    
    def test_json_rpc_standard_codes(self):
        """Test standard JSON-RPC error codes."""
        assert McpErrorCode.PARSE_ERROR == -32700
        assert McpErrorCode.INVALID_REQUEST == -32600
        assert McpErrorCode.METHOD_NOT_FOUND == -32601
        assert McpErrorCode.INVALID_PARAMS == -32602
        assert McpErrorCode.INTERNAL_ERROR == -32603
    
    def test_mcp_specific_codes(self):
        """Test MCP-specific error codes."""
        assert McpErrorCode.MODE_NOT_FOUND == -32001
        assert McpErrorCode.TASK_NOT_FOUND == -32002
        assert McpErrorCode.SESSION_EXPIRED == -32003
        assert McpErrorCode.VALIDATION_ERROR == -32004
        assert McpErrorCode.TOOL_RESTRICTION_ERROR == -32005
        assert McpErrorCode.FILE_RESTRICTION_ERROR == -32006


class TestMcpProtocolError:
    """Test MCP protocol error exception."""
    
    def test_create_error(self):
        """Test creating a protocol error."""
        error = McpProtocolError(
            code=McpErrorCode.INVALID_REQUEST,
            message="Invalid request",
            data={"detail": "Missing field"}
        )
        
        assert error.code == McpErrorCode.INVALID_REQUEST
        assert error.message == "Invalid request"
        assert error.data == {"detail": "Missing field"}
        assert str(error) == "Invalid request"
    
    def test_error_without_data(self):
        """Test error without additional data."""
        error = McpProtocolError(
            code=McpErrorCode.METHOD_NOT_FOUND,
            message="Method not found"
        )
        
        assert error.code == McpErrorCode.METHOD_NOT_FOUND
        assert error.message == "Method not found"
        assert error.data is None


class TestJsonRpcMessage:
    """Test JSON-RPC message creation and validation."""
    
    def test_create_request_minimal(self):
        """Test creating a minimal request."""
        msg = JsonRpcMessage.create_request("test_method")
        
        assert msg["jsonrpc"] == "2.0"
        assert msg["method"] == "test_method"
        assert "params" not in msg
        assert "id" not in msg
    
    def test_create_request_with_params(self):
        """Test creating request with parameters."""
        params = {"arg1": "value1", "arg2": 42}
        msg = JsonRpcMessage.create_request("test_method", params=params)
        
        assert msg["jsonrpc"] == "2.0"
        assert msg["method"] == "test_method"
        assert msg["params"] == params
        assert "id" not in msg
    
    def test_create_request_with_id(self):
        """Test creating request with ID."""
        msg = JsonRpcMessage.create_request("test_method", request_id=1)
        
        assert msg["jsonrpc"] == "2.0"
        assert msg["method"] == "test_method"
        assert msg["id"] == 1
    
    def test_create_request_with_string_id(self):
        """Test creating request with string ID."""
        msg = JsonRpcMessage.create_request("test_method", request_id="abc-123")
        
        assert msg["id"] == "abc-123"
    
    def test_create_response(self):
        """Test creating a successful response."""
        result = {"status": "success", "data": [1, 2, 3]}
        msg = JsonRpcMessage.create_response(request_id=1, result=result)
        
        assert msg["jsonrpc"] == "2.0"
        assert msg["id"] == 1
        assert msg["result"] == result
        assert "error" not in msg
    
    def test_create_response_null_result(self):
        """Test creating response with null result."""
        msg = JsonRpcMessage.create_response(request_id=1, result=None)
        
        assert msg["result"] is None
    
    def test_create_error_minimal(self):
        """Test creating minimal error response."""
        msg = JsonRpcMessage.create_error(
            request_id=1,
            code=-32600,
            message="Invalid Request"
        )
        
        assert msg["jsonrpc"] == "2.0"
        assert msg["id"] == 1
        assert msg["error"]["code"] == -32600
        assert msg["error"]["message"] == "Invalid Request"
        assert "data" not in msg["error"]
    
    def test_create_error_with_data(self):
        """Test creating error with additional data."""
        error_data = {"field": "name", "issue": "required"}
        msg = JsonRpcMessage.create_error(
            request_id=1,
            code=-32602,
            message="Invalid params",
            data=error_data
        )
        
        assert msg["error"]["data"] == error_data
    
    def test_create_error_for_parse_error(self):
        """Test creating error for parse errors (null ID)."""
        msg = JsonRpcMessage.create_error(
            request_id=None,
            code=-32700,
            message="Parse error"
        )
        
        assert msg["id"] is None
    
    def test_validate_request_valid(self):
        """Test validating a valid request."""
        msg = {
            "jsonrpc": "2.0",
            "method": "test_method",
            "params": {},
            "id": 1
        }
        
        # Should not raise
        JsonRpcMessage.validate_request(msg)
    
    def test_validate_request_notification(self):
        """Test validating a notification (no ID)."""
        msg = {
            "jsonrpc": "2.0",
            "method": "test_notification",
            "params": {}
        }
        
        # Should not raise
        JsonRpcMessage.validate_request(msg)
    
    def test_validate_request_invalid_version(self):
        """Test validation fails on wrong version."""
        msg = {
            "jsonrpc": "1.0",
            "method": "test_method"
        }
        
        with pytest.raises(McpProtocolError) as exc_info:
            JsonRpcMessage.validate_request(msg)
        
        assert exc_info.value.code == McpErrorCode.INVALID_REQUEST
        assert "version" in exc_info.value.message.lower()
    
    def test_validate_request_missing_version(self):
        """Test validation fails on missing version."""
        msg = {
            "method": "test_method"
        }
        
        with pytest.raises(McpProtocolError) as exc_info:
            JsonRpcMessage.validate_request(msg)
        
        assert exc_info.value.code == McpErrorCode.INVALID_REQUEST
    
    def test_validate_request_missing_method(self):
        """Test validation fails on missing method."""
        msg = {
            "jsonrpc": "2.0",
            "id": 1
        }
        
        with pytest.raises(McpProtocolError) as exc_info:
            JsonRpcMessage.validate_request(msg)
        
        assert exc_info.value.code == McpErrorCode.INVALID_REQUEST
        assert "method" in exc_info.value.message.lower()
    
    def test_validate_request_invalid_method_type(self):
        """Test validation fails on non-string method."""
        msg = {
            "jsonrpc": "2.0",
            "method": 123
        }
        
        with pytest.raises(McpProtocolError) as exc_info:
            JsonRpcMessage.validate_request(msg)
        
        assert exc_info.value.code == McpErrorCode.INVALID_REQUEST
        assert "string" in exc_info.value.message.lower()
    
    def test_is_notification(self):
        """Test checking if message is a notification."""
        notification = {"jsonrpc": "2.0", "method": "notify"}
        request = {"jsonrpc": "2.0", "method": "call", "id": 1}
        
        assert JsonRpcMessage.is_notification(notification)
        assert not JsonRpcMessage.is_notification(request)


class TestMessageParser:
    """Test message parsing and serialization."""
    
    def test_parse_message_valid(self):
        """Test parsing a valid JSON message."""
        data = b'{"jsonrpc": "2.0", "method": "test", "id": 1}\n'
        msg = MessageParser.parse_message(data)
        
        assert msg["jsonrpc"] == "2.0"
        assert msg["method"] == "test"
        assert msg["id"] == 1
    
    def test_parse_message_without_newline(self):
        """Test parsing message without trailing newline."""
        data = b'{"jsonrpc": "2.0", "method": "test"}'
        msg = MessageParser.parse_message(data)
        
        assert msg["method"] == "test"
    
    def test_parse_message_with_whitespace(self):
        """Test parsing message with surrounding whitespace."""
        data = b'  {"jsonrpc": "2.0", "method": "test"}  \n'
        msg = MessageParser.parse_message(data)
        
        assert msg["method"] == "test"
    
    def test_parse_message_empty(self):
        """Test parsing empty message fails."""
        with pytest.raises(McpProtocolError) as exc_info:
            MessageParser.parse_message(b'')
        
        assert exc_info.value.code == McpErrorCode.PARSE_ERROR
        assert "empty" in exc_info.value.message.lower()
    
    def test_parse_message_whitespace_only(self):
        """Test parsing whitespace-only message fails."""
        with pytest.raises(McpProtocolError) as exc_info:
            MessageParser.parse_message(b'   \n')
        
        assert exc_info.value.code == McpErrorCode.PARSE_ERROR
    
    def test_parse_message_invalid_json(self):
        """Test parsing invalid JSON fails."""
        data = b'{invalid json}'
        
        with pytest.raises(McpProtocolError) as exc_info:
            MessageParser.parse_message(data)
        
        assert exc_info.value.code == McpErrorCode.PARSE_ERROR
        assert "json" in exc_info.value.message.lower()
    
    def test_parse_message_not_object(self):
        """Test parsing non-object JSON fails."""
        data = b'["array", "not", "object"]'
        
        with pytest.raises(McpProtocolError) as exc_info:
            MessageParser.parse_message(data)
        
        assert exc_info.value.code == McpErrorCode.INVALID_REQUEST
        assert "object" in exc_info.value.message.lower()
    
    def test_parse_message_invalid_utf8(self):
        """Test parsing invalid UTF-8 fails."""
        data = b'\xff\xfe\x00\x00'
        
        with pytest.raises(McpProtocolError) as exc_info:
            MessageParser.parse_message(data)
        
        assert exc_info.value.code == McpErrorCode.PARSE_ERROR
        assert "utf-8" in exc_info.value.message.lower()
    
    def test_serialize_message(self):
        """Test serializing a message."""
        msg = {"jsonrpc": "2.0", "method": "test", "id": 1}
        data = MessageParser.serialize_message(msg)
        
        assert isinstance(data, bytes)
        assert data.endswith(b'\n')
        
        # Parse it back
        parsed = json.loads(data.decode('utf-8').strip())
        assert parsed == msg
    
    def test_serialize_message_unicode(self):
        """Test serializing message with Unicode characters."""
        msg = {"method": "test", "text": "Hello 世界 🌍"}
        data = MessageParser.serialize_message(msg)
        
        # Should preserve Unicode
        parsed = json.loads(data.decode('utf-8'))
        assert parsed["text"] == "Hello 世界 🌍"


class TestMessageWriter:
    """Test message writing."""
    
    def test_write_message(self):
        """Test writing a message to stream."""
        from io import BytesIO
        
        stream = BytesIO()
        writer = MessageWriter(stream)
        
        msg = {"jsonrpc": "2.0", "method": "test"}
        writer.write_message(msg)
        
        # Check output
        output = stream.getvalue()
        assert output.endswith(b'\n')
        
        parsed = json.loads(output.decode('utf-8'))
        assert parsed == msg
    
    def test_write_response(self):
        """Test writing a response."""
        from io import BytesIO
        
        stream = BytesIO()
        writer = MessageWriter(stream)
        
        result = {"status": "ok"}
        writer.write_response(request_id=1, result=result)
        
        # Parse output
        output = stream.getvalue()
        parsed = json.loads(output.decode('utf-8'))
        
        assert parsed["jsonrpc"] == "2.0"
        assert parsed["id"] == 1
        assert parsed["result"] == result
    
    def test_write_error(self):
        """Test writing an error."""
        from io import BytesIO
        
        stream = BytesIO()
        writer = MessageWriter(stream)
        
        writer.write_error(
            request_id=1,
            code=-32600,
            message="Invalid Request",
            data={"detail": "test"}
        )
        
        # Parse output
        output = stream.getvalue()
        parsed = json.loads(output.decode('utf-8'))
        
        assert parsed["jsonrpc"] == "2.0"
        assert parsed["id"] == 1
        assert parsed["error"]["code"] == -32600
        assert parsed["error"]["message"] == "Invalid Request"
        assert parsed["error"]["data"] == {"detail": "test"}
    
    def test_write_notification(self):
        """Test writing a notification."""
        from io import BytesIO
        
        stream = BytesIO()
        writer = MessageWriter(stream)
        
        params = {"key": "value"}
        writer.write_notification("test_method", params)
        
        # Parse output
        output = stream.getvalue()
        parsed = json.loads(output.decode('utf-8'))
        
        assert parsed["jsonrpc"] == "2.0"
        assert parsed["method"] == "test_method"
        assert parsed["params"] == params
        assert "id" not in parsed
    
    def test_write_multiple_messages(self):
        """Test writing multiple messages."""
        from io import BytesIO
        
        stream = BytesIO()
        writer = MessageWriter(stream)
        
        writer.write_response(1, {"result": "first"})
        writer.write_response(2, {"result": "second"})
        
        # Should have two newline-delimited messages
        output = stream.getvalue().decode('utf-8')
        lines = [line for line in output.split('\n') if line]
        
        assert len(lines) == 2
        assert json.loads(lines[0])["id"] == 1
        assert json.loads(lines[1])["id"] == 2