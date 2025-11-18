"""
Input validation for MCP server.

This module provides validation utilities for tool arguments and other inputs
according to JSON schemas.
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Raised when validation fails."""
    pass


class SchemaValidator:
    """Validates inputs against JSON schemas."""
    
    @staticmethod
    def validate_type(
        value: Any,
        expected_type: str,
        param_name: str
    ) -> None:
        """
        Validate that a value matches the expected type.
        
        Args:
            value: Value to validate
            expected_type: Expected JSON schema type
            param_name: Parameter name for error messages
            
        Raises:
            ValidationError: If type doesn't match
        """
        type_checks = {
            "string": lambda v: isinstance(v, str),
            "number": lambda v: isinstance(v, (int, float)),
            "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
            "boolean": lambda v: isinstance(v, bool),
            "object": lambda v: isinstance(v, dict),
            "array": lambda v: isinstance(v, list),
            "null": lambda v: v is None
        }
        
        check = type_checks.get(expected_type)
        if not check:
            raise ValidationError(f"Unknown type: {expected_type}")
        
        if not check(value):
            raise ValidationError(
                f"Parameter '{param_name}' must be of type {expected_type}, "
                f"got {type(value).__name__}"
            )
    
    @staticmethod
    def validate_enum(
        value: Any,
        enum_values: List[Any],
        param_name: str
    ) -> None:
        """
        Validate that a value is in the allowed enum values.
        
        Args:
            value: Value to validate
            enum_values: List of allowed values
            param_name: Parameter name for error messages
            
        Raises:
            ValidationError: If value not in enum
        """
        if value not in enum_values:
            raise ValidationError(
                f"Parameter '{param_name}' must be one of: "
                f"{', '.join(str(v) for v in enum_values)}, got '{value}'"
            )
    
    @staticmethod
    def validate_required(
        args: Dict[str, Any],
        required: List[str],
        context: str = "parameters"
    ) -> None:
        """
        Validate that all required parameters are present.
        
        Args:
            args: Arguments dict
            required: List of required parameter names
            context: Context description for error messages
            
        Raises:
            ValidationError: If required parameter is missing
        """
        for param in required:
            if param not in args:
                raise ValidationError(
                    f"Missing required {context}: {param}"
                )
    
    @staticmethod
    def validate_tool_args(
        tool_name: str,
        args: Dict[str, Any],
        schema: Dict[str, Any]
    ) -> None:
        """
        Validate tool arguments against schema.
        
        Args:
            tool_name: Name of the tool
            args: Arguments to validate
            schema: JSON schema to validate against
            
        Raises:
            ValidationError: If validation fails
        """
        # Validate required parameters
        required = schema.get("required", [])
        SchemaValidator.validate_required(
            args,
            required,
            f"parameter for {tool_name}"
        )
        
        # Validate each parameter
        properties = schema.get("properties", {})
        for param_name, value in args.items():
            # Skip parameters not in schema (extra params allowed)
            if param_name not in properties:
                continue
            
            param_schema = properties[param_name]
            
            # Validate type
            if "type" in param_schema:
                SchemaValidator.validate_type(
                    value,
                    param_schema["type"],
                    param_name
                )
            
            # Validate enum
            if "enum" in param_schema:
                SchemaValidator.validate_enum(
                    value,
                    param_schema["enum"],
                    param_name
                )
            
            # Validate array items
            if param_schema.get("type") == "array" and "items" in param_schema:
                if not isinstance(value, list):
                    raise ValidationError(
                        f"Parameter '{param_name}' must be an array"
                    )
                
                items_schema = param_schema["items"]
                if "type" in items_schema:
                    for i, item in enumerate(value):
                        try:
                            SchemaValidator.validate_type(
                                item,
                                items_schema["type"],
                                f"{param_name}[{i}]"
                            )
                        except ValidationError as e:
                            raise ValidationError(
                                f"Invalid array item in '{param_name}': {e}"
                            )
            
            # Validate object properties
            if param_schema.get("type") == "object":
                if not isinstance(value, dict):
                    raise ValidationError(
                        f"Parameter '{param_name}' must be an object"
                    )
                
                # Validate nested required properties
                if "required" in param_schema:
                    SchemaValidator.validate_required(
                        value,
                        param_schema["required"],
                        f"property in '{param_name}'"
                    )
                
                # Validate nested properties
                if "properties" in param_schema:
                    for nested_name, nested_value in value.items():
                        if nested_name in param_schema["properties"]:
                            nested_schema = param_schema["properties"][nested_name]
                            if "type" in nested_schema:
                                SchemaValidator.validate_type(
                                    nested_value,
                                    nested_schema["type"],
                                    f"{param_name}.{nested_name}"
                                )
    
    @staticmethod
    def validate_uri(uri: str, expected_scheme: Optional[str] = None) -> None:
        """
        Validate a URI format.
        
        Args:
            uri: URI to validate
            expected_scheme: Expected URI scheme (e.g., "mode")
            
        Raises:
            ValidationError: If URI is invalid
        """
        if not uri or not isinstance(uri, str):
            raise ValidationError("URI must be a non-empty string")
        
        if "://" not in uri:
            raise ValidationError("URI must contain '://' separator")
        
        scheme = uri.split("://")[0]
        if expected_scheme and scheme != expected_scheme:
            raise ValidationError(
                f"URI scheme must be '{expected_scheme}', got '{scheme}'"
            )
    
    @staticmethod
    def validate_session_id(session_id: str) -> None:
        """
        Validate a session ID format.
        
        Args:
            session_id: Session ID to validate
            
        Raises:
            ValidationError: If session ID is invalid
        """
        if not session_id or not isinstance(session_id, str):
            raise ValidationError("Session ID must be a non-empty string")
        
        if not session_id.startswith("ses_"):
            raise ValidationError("Session ID must start with 'ses_'")
        
        if len(session_id) < 5:
            raise ValidationError("Session ID is too short")
    
    @staticmethod
    def validate_mode_slug(slug: str) -> None:
        """
        Validate a mode slug format.
        
        Args:
            slug: Mode slug to validate
            
        Raises:
            ValidationError: If slug is invalid
        """
        if not slug or not isinstance(slug, str):
            raise ValidationError("Mode slug must be a non-empty string")
        
        # Mode slugs should be lowercase alphanumeric with optional hyphens/underscores
        if not all(c.isalnum() or c in '-_' for c in slug):
            raise ValidationError(
                "Mode slug must contain only alphanumeric characters, "
                "hyphens, and underscores"
            )
        
        if len(slug) > 50:
            raise ValidationError("Mode slug is too long (max 50 characters)")


class InputSanitizer:
    """Sanitizes user inputs."""
    
    @staticmethod
    def sanitize_string(
        value: str,
        max_length: Optional[int] = None,
        strip: bool = True
    ) -> str:
        """
        Sanitize a string input.
        
        Args:
            value: String to sanitize
            max_length: Maximum allowed length
            strip: Whether to strip whitespace
            
        Returns:
            Sanitized string
            
        Raises:
            ValidationError: If string exceeds max length
        """
        if not isinstance(value, str):
            raise ValidationError("Value must be a string")
        
        if strip:
            value = value.strip()
        
        if max_length and len(value) > max_length:
            raise ValidationError(
                f"String exceeds maximum length of {max_length} characters"
            )
        
        return value
    
    @staticmethod
    def sanitize_path(path: str) -> str:
        """
        Sanitize a file path input.
        
        Args:
            path: Path to sanitize
            
        Returns:
            Sanitized path
            
        Raises:
            ValidationError: If path is invalid
        """
        if not isinstance(path, str):
            raise ValidationError("Path must be a string")
        
        path = path.strip()
        
        if not path:
            raise ValidationError("Path cannot be empty")
        
        # Prevent path traversal attacks
        if ".." in path:
            raise ValidationError("Path cannot contain '..' (path traversal)")
        
        # Prevent absolute paths (should be relative to project root)
        if path.startswith("/") or (len(path) > 1 and path[1] == ":"):
            raise ValidationError("Path must be relative, not absolute")
        
        return path