"""
Unit tests for MCP input validation.

Tests validation utilities for tool arguments and other inputs according to JSON schemas.
"""

import pytest
from roo_code.mcp.validation import (
    ValidationError,
    SchemaValidator,
    InputSanitizer,
)


class TestSchemaValidator:
    """Test SchemaValidator class."""
    
    def test_validate_type_string(self):
        """Test validating string type."""
        # Valid
        SchemaValidator.validate_type("hello", "string", "param")
        
        # Invalid
        with pytest.raises(ValidationError) as exc_info:
            SchemaValidator.validate_type(123, "string", "param")
        
        assert "param" in str(exc_info.value)
        assert "string" in str(exc_info.value)
    
    def test_validate_type_number(self):
        """Test validating number type (int or float)."""
        # Valid
        SchemaValidator.validate_type(42, "number", "param")
        SchemaValidator.validate_type(3.14, "number", "param")
        
        # Invalid
        with pytest.raises(ValidationError):
            SchemaValidator.validate_type("42", "number", "param")
    
    def test_validate_type_integer(self):
        """Test validating integer type."""
        # Valid
        SchemaValidator.validate_type(42, "integer", "param")
        
        # Invalid - float
        with pytest.raises(ValidationError):
            SchemaValidator.validate_type(3.14, "integer", "param")
        
        # Invalid - boolean should not be treated as integer
        with pytest.raises(ValidationError):
            SchemaValidator.validate_type(True, "integer", "param")
    
    def test_validate_type_boolean(self):
        """Test validating boolean type."""
        # Valid
        SchemaValidator.validate_type(True, "boolean", "param")
        SchemaValidator.validate_type(False, "boolean", "param")
        
        # Invalid
        with pytest.raises(ValidationError):
            SchemaValidator.validate_type(1, "boolean", "param")
    
    def test_validate_type_object(self):
        """Test validating object type (dict)."""
        # Valid
        SchemaValidator.validate_type({"key": "value"}, "object", "param")
        SchemaValidator.validate_type({}, "object", "param")
        
        # Invalid
        with pytest.raises(ValidationError):
            SchemaValidator.validate_type(["list"], "object", "param")
    
    def test_validate_type_array(self):
        """Test validating array type (list)."""
        # Valid
        SchemaValidator.validate_type([1, 2, 3], "array", "param")
        SchemaValidator.validate_type([], "array", "param")
        
        # Invalid
        with pytest.raises(ValidationError):
            SchemaValidator.validate_type((1, 2), "array", "param")
    
    def test_validate_type_null(self):
        """Test validating null type."""
        # Valid
        SchemaValidator.validate_type(None, "null", "param")
        
        # Invalid
        with pytest.raises(ValidationError):
            SchemaValidator.validate_type("", "null", "param")
    
    def test_validate_type_unknown(self):
        """Test validation fails on unknown type."""
        with pytest.raises(ValidationError) as exc_info:
            SchemaValidator.validate_type("value", "unknown_type", "param")
        
        assert "unknown" in str(exc_info.value).lower()
    
    def test_validate_enum_valid(self):
        """Test validating enum with valid value."""
        enum_values = ["option1", "option2", "option3"]
        
        # Valid
        SchemaValidator.validate_enum("option1", enum_values, "param")
        SchemaValidator.validate_enum("option2", enum_values, "param")
    
    def test_validate_enum_invalid(self):
        """Test validating enum with invalid value."""
        enum_values = ["option1", "option2"]
        
        with pytest.raises(ValidationError) as exc_info:
            SchemaValidator.validate_enum("option3", enum_values, "param")
        
        assert "option1" in str(exc_info.value)
        assert "option2" in str(exc_info.value)
        assert "param" in str(exc_info.value)
    
    def test_validate_enum_different_types(self):
        """Test validating enum with mixed types."""
        enum_values = [1, "two", 3.0, None]
        
        SchemaValidator.validate_enum(1, enum_values, "param")
        SchemaValidator.validate_enum("two", enum_values, "param")
        SchemaValidator.validate_enum(None, enum_values, "param")
    
    def test_validate_required_all_present(self):
        """Test validation passes when all required params present."""
        args = {"param1": "value1", "param2": "value2", "param3": "value3"}
        required = ["param1", "param2"]
        
        # Should not raise
        SchemaValidator.validate_required(args, required)
    
    def test_validate_required_missing(self):
        """Test validation fails when required param missing."""
        args = {"param1": "value1"}
        required = ["param1", "param2"]
        
        with pytest.raises(ValidationError) as exc_info:
            SchemaValidator.validate_required(args, required)
        
        assert "param2" in str(exc_info.value)
        assert "required" in str(exc_info.value).lower()
    
    def test_validate_required_custom_context(self):
        """Test validation with custom context message."""
        args = {}
        required = ["field"]
        
        with pytest.raises(ValidationError) as exc_info:
            SchemaValidator.validate_required(args, required, context="field")
        
        assert "field" in str(exc_info.value)
    
    def test_validate_tool_args_minimal(self):
        """Test validating tool args with minimal schema."""
        schema = {
            "type": "object",
            "properties": {},
            "required": []
        }
        
        # Should not raise
        SchemaValidator.validate_tool_args("test_tool", {}, schema)
    
    def test_validate_tool_args_required(self):
        """Test validating required tool parameters."""
        schema = {
            "type": "object",
            "properties": {
                "arg1": {"type": "string"}
            },
            "required": ["arg1"]
        }
        
        # Valid
        SchemaValidator.validate_tool_args("test_tool", {"arg1": "value"}, schema)
        
        # Missing required
        with pytest.raises(ValidationError) as exc_info:
            SchemaValidator.validate_tool_args("test_tool", {}, schema)
        
        assert "arg1" in str(exc_info.value)
    
    def test_validate_tool_args_type_checking(self):
        """Test type checking in tool args validation."""
        schema = {
            "type": "object",
            "properties": {
                "count": {"type": "integer"},
                "name": {"type": "string"}
            },
            "required": []
        }
        
        # Valid
        SchemaValidator.validate_tool_args(
            "test_tool",
            {"count": 42, "name": "test"},
            schema
        )
        
        # Invalid type
        with pytest.raises(ValidationError):
            SchemaValidator.validate_tool_args(
                "test_tool",
                {"count": "42"},
                schema
            )
    
    def test_validate_tool_args_enum(self):
        """Test enum validation in tool args."""
        schema = {
            "type": "object",
            "properties": {
                "mode": {
                    "type": "string",
                    "enum": ["read", "write", "execute"]
                }
            },
            "required": ["mode"]
        }
        
        # Valid
        SchemaValidator.validate_tool_args("test_tool", {"mode": "read"}, schema)
        
        # Invalid enum value
        with pytest.raises(ValidationError) as exc_info:
            SchemaValidator.validate_tool_args("test_tool", {"mode": "invalid"}, schema)
        
        assert "read" in str(exc_info.value)
    
    def test_validate_tool_args_array_items(self):
        """Test array item validation in tool args."""
        schema = {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {"type": "string"}
                }
            },
            "required": []
        }
        
        # Valid
        SchemaValidator.validate_tool_args(
            "test_tool",
            {"items": ["a", "b", "c"]},
            schema
        )
        
        # Invalid item type
        with pytest.raises(ValidationError):
            SchemaValidator.validate_tool_args(
                "test_tool",
                {"items": ["a", 123, "c"]},
                schema
            )
    
    def test_validate_tool_args_nested_object(self):
        """Test nested object validation in tool args."""
        schema = {
            "type": "object",
            "properties": {
                "config": {
                    "type": "object",
                    "properties": {
                        "timeout": {"type": "integer"}
                    },
                    "required": ["timeout"]
                }
            },
            "required": ["config"]
        }
        
        # Valid
        SchemaValidator.validate_tool_args(
            "test_tool",
            {"config": {"timeout": 30}},
            schema
        )
        
        # Missing nested required
        with pytest.raises(ValidationError):
            SchemaValidator.validate_tool_args(
                "test_tool",
                {"config": {}},
                schema
            )
        
        # Invalid nested type
        with pytest.raises(ValidationError):
            SchemaValidator.validate_tool_args(
                "test_tool",
                {"config": {"timeout": "30"}},
                schema
            )
    
    def test_validate_tool_args_extra_params_allowed(self):
        """Test that extra parameters are allowed."""
        schema = {
            "type": "object",
            "properties": {
                "arg1": {"type": "string"}
            },
            "required": ["arg1"]
        }
        
        # Should not raise even with extra params
        SchemaValidator.validate_tool_args(
            "test_tool",
            {"arg1": "value", "extra_arg": "extra_value"},
            schema
        )
    
    def test_validate_uri_valid(self):
        """Test validating valid URIs."""
        SchemaValidator.validate_uri("mode://code")
        SchemaValidator.validate_uri("mode://code/config")
        SchemaValidator.validate_uri("http://example.com")
    
    def test_validate_uri_empty(self):
        """Test validation fails on empty URI."""
        with pytest.raises(ValidationError) as exc_info:
            SchemaValidator.validate_uri("")
        
        assert "non-empty" in str(exc_info.value).lower()
    
    def test_validate_uri_no_separator(self):
        """Test validation fails without :// separator."""
        with pytest.raises(ValidationError) as exc_info:
            SchemaValidator.validate_uri("mode:code")
        
        assert "://" in str(exc_info.value)
    
    def test_validate_uri_expected_scheme(self):
        """Test URI validation with expected scheme."""
        # Valid
        SchemaValidator.validate_uri("mode://code", expected_scheme="mode")
        
        # Invalid scheme
        with pytest.raises(ValidationError) as exc_info:
            SchemaValidator.validate_uri("http://code", expected_scheme="mode")
        
        assert "mode" in str(exc_info.value)
        assert "http" in str(exc_info.value)
    
    def test_validate_session_id_valid(self):
        """Test validating valid session IDs."""
        SchemaValidator.validate_session_id("ses_abc123")
        SchemaValidator.validate_session_id("ses_xyz789def456")
    
    def test_validate_session_id_empty(self):
        """Test validation fails on empty session ID."""
        with pytest.raises(ValidationError):
            SchemaValidator.validate_session_id("")
    
    def test_validate_session_id_no_prefix(self):
        """Test validation fails without ses_ prefix."""
        with pytest.raises(ValidationError) as exc_info:
            SchemaValidator.validate_session_id("abc123")
        
        assert "ses_" in str(exc_info.value)
    
    def test_validate_session_id_too_short(self):
        """Test validation fails on too short session ID."""
        with pytest.raises(ValidationError) as exc_info:
            SchemaValidator.validate_session_id("ses_")
        
        assert "short" in str(exc_info.value).lower()
    
    def test_validate_mode_slug_valid(self):
        """Test validating valid mode slugs."""
        SchemaValidator.validate_mode_slug("code")
        SchemaValidator.validate_mode_slug("ask")
        SchemaValidator.validate_mode_slug("my-custom-mode")
        SchemaValidator.validate_mode_slug("mode_123")
    
    def test_validate_mode_slug_empty(self):
        """Test validation fails on empty slug."""
        with pytest.raises(ValidationError):
            SchemaValidator.validate_mode_slug("")
    
    def test_validate_mode_slug_invalid_chars(self):
        """Test validation fails on invalid characters."""
        with pytest.raises(ValidationError) as exc_info:
            SchemaValidator.validate_mode_slug("my mode")
        
        assert "alphanumeric" in str(exc_info.value).lower()
        
        with pytest.raises(ValidationError):
            SchemaValidator.validate_mode_slug("mode@123")
    
    def test_validate_mode_slug_too_long(self):
        """Test validation fails on too long slug."""
        long_slug = "a" * 51
        
        with pytest.raises(ValidationError) as exc_info:
            SchemaValidator.validate_mode_slug(long_slug)
        
        assert "50" in str(exc_info.value)


class TestInputSanitizer:
    """Test InputSanitizer class."""
    
    def test_sanitize_string_basic(self):
        """Test basic string sanitization."""
        result = InputSanitizer.sanitize_string("  hello  ")
        assert result == "hello"
    
    def test_sanitize_string_no_strip(self):
        """Test string sanitization without stripping."""
        result = InputSanitizer.sanitize_string("  hello  ", strip=False)
        assert result == "  hello  "
    
    def test_sanitize_string_max_length(self):
        """Test string sanitization with max length."""
        # Valid
        result = InputSanitizer.sanitize_string("hello", max_length=10)
        assert result == "hello"
        
        # Too long
        with pytest.raises(ValidationError) as exc_info:
            InputSanitizer.sanitize_string("hello world", max_length=5)
        
        assert "maximum length" in str(exc_info.value).lower()
        assert "5" in str(exc_info.value)
    
    def test_sanitize_string_non_string(self):
        """Test sanitization fails on non-string."""
        with pytest.raises(ValidationError):
            InputSanitizer.sanitize_string(123)
    
    def test_sanitize_string_empty_after_strip(self):
        """Test sanitizing string that becomes empty after strip."""
        result = InputSanitizer.sanitize_string("   ")
        assert result == ""
    
    def test_sanitize_path_basic(self):
        """Test basic path sanitization."""
        result = InputSanitizer.sanitize_path("  path/to/file.txt  ")
        assert result == "path/to/file.txt"
    
    def test_sanitize_path_empty(self):
        """Test sanitization fails on empty path."""
        with pytest.raises(ValidationError) as exc_info:
            InputSanitizer.sanitize_path("")
        
        assert "empty" in str(exc_info.value).lower()
    
    def test_sanitize_path_whitespace_only(self):
        """Test sanitization fails on whitespace-only path."""
        with pytest.raises(ValidationError):
            InputSanitizer.sanitize_path("   ")
    
    def test_sanitize_path_traversal(self):
        """Test sanitization prevents path traversal."""
        with pytest.raises(ValidationError) as exc_info:
            InputSanitizer.sanitize_path("../../../etc/passwd")
        
        assert ".." in str(exc_info.value)
        assert "traversal" in str(exc_info.value).lower()
    
    def test_sanitize_path_traversal_hidden(self):
        """Test sanitization prevents hidden path traversal."""
        with pytest.raises(ValidationError):
            InputSanitizer.sanitize_path("path/../other/file")
    
    def test_sanitize_path_absolute_unix(self):
        """Test sanitization prevents absolute Unix paths."""
        with pytest.raises(ValidationError) as exc_info:
            InputSanitizer.sanitize_path("/etc/passwd")
        
        assert "absolute" in str(exc_info.value).lower()
    
    def test_sanitize_path_absolute_windows(self):
        """Test sanitization prevents absolute Windows paths."""
        with pytest.raises(ValidationError) as exc_info:
            InputSanitizer.sanitize_path("C:\\Windows\\System32")
        
        assert "absolute" in str(exc_info.value).lower()
    
    def test_sanitize_path_valid_relative(self):
        """Test valid relative paths."""
        paths = [
            "file.txt",
            "path/to/file.txt",
            "src/components/MyComponent.tsx",
            "./local/file.txt"
        ]
        
        for path in paths:
            result = InputSanitizer.sanitize_path(path)
            assert isinstance(result, str)
    
    def test_sanitize_path_non_string(self):
        """Test sanitization fails on non-string path."""
        with pytest.raises(ValidationError):
            InputSanitizer.sanitize_path(["path", "to", "file"])


class TestValidationErrorPropagation:
    """Test that ValidationError propagates correctly."""
    
    def test_error_message(self):
        """Test ValidationError message."""
        error = ValidationError("Test error message")
        assert str(error) == "Test error message"
    
    def test_error_in_nested_validation(self):
        """Test error propagation in nested validation."""
        schema = {
            "type": "object",
            "properties": {
                "nested": {
                    "type": "object",
                    "properties": {
                        "value": {"type": "integer"}
                    }
                }
            }
        }
        
        try:
            SchemaValidator.validate_tool_args(
                "test_tool",
                {"nested": {"value": "not_an_int"}},
                schema
            )
            assert False, "Should have raised ValidationError"
        except ValidationError as e:
            # Error should mention the nested field
            assert "value" in str(e) or "nested" in str(e)
    
    def test_multiple_validation_errors(self):
        """Test that first validation error is raised."""
        schema = {
            "type": "object",
            "properties": {
                "arg1": {"type": "string"},
                "arg2": {"type": "integer"}
            },
            "required": ["arg1", "arg2"]
        }
        
        # Missing both required args - should fail on first
        with pytest.raises(ValidationError) as exc_info:
            SchemaValidator.validate_tool_args("test_tool", {}, schema)
        
        # Should mention required parameter
        assert "required" in str(exc_info.value).lower()