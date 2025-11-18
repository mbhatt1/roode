"""
MCP resource handlers for mode system.

This module handles MCP resource operations, exposing modes as resources
that can be queried and read through the MCP protocol.
"""

import json
import logging
from typing import Any, Dict, List, Optional

from ..modes.config import ModeConfig
from ..modes.orchestrator import ModeOrchestrator
from ..modes.task import Task
from .validation import SchemaValidator, ValidationError

logger = logging.getLogger(__name__)


class ResourceHandler:
    """Handles MCP resource operations for modes."""
    
    def __init__(self, orchestrator: ModeOrchestrator):
        """
        Initialize resource handler.
        
        Args:
            orchestrator: Mode orchestrator for accessing mode configurations
        """
        self.orchestrator = orchestrator
    
    async def list_resources(self) -> List[Dict[str, Any]]:
        """
        List all available mode resources.
        
        Returns:
            List of resource descriptors in MCP format
        """
        resources = []
        
        for mode in self.orchestrator.get_all_modes():
            # Full mode resource
            resources.append({
                "uri": f"mode://{mode.slug}",
                "name": mode.name,
                "mimeType": "application/json",
                "description": mode.description or f"Full configuration for {mode.name}"
            })
            
            # Config resource (structured configuration)
            resources.append({
                "uri": f"mode://{mode.slug}/config",
                "name": f"{mode.name} - Configuration",
                "mimeType": "application/json",
                "description": f"Structured configuration for {mode.name}"
            })
            
            # System prompt resource
            resources.append({
                "uri": f"mode://{mode.slug}/system_prompt",
                "name": f"{mode.name} - System Prompt",
                "mimeType": "text/plain",
                "description": f"System prompt for {mode.name}"
            })
        
        logger.debug(f"Listed {len(resources)} mode resources")
        return resources
    
    async def read_resource(self, uri: str) -> Dict[str, Any]:
        """
        Read a specific mode resource.
        
        Args:
            uri: Resource URI (e.g., "mode://code" or "mode://code/config")
            
        Returns:
            Resource contents in MCP format
            
        Raises:
            ValidationError: If URI is invalid or mode not found
        """
        # Validate URI format
        SchemaValidator.validate_uri(uri, expected_scheme="mode")
        
        # Parse URI
        uri_parts = uri[7:].split("/")  # Remove "mode://"
        if not uri_parts or not uri_parts[0]:
            raise ValidationError("Mode slug is required in URI")
        
        mode_slug = uri_parts[0]
        subresource = uri_parts[1] if len(uri_parts) > 1 else None
        
        # Get mode
        mode = self.orchestrator.get_mode(mode_slug)
        if not mode:
            available = ', '.join(self.orchestrator.get_mode_names())
            raise ValidationError(
                f"Mode not found: {mode_slug}. Available modes: {available}"
            )
        
        # Generate content based on subresource
        if subresource == "config":
            content = self._serialize_mode_config(mode)
            mime_type = "application/json"
        elif subresource == "system_prompt":
            # Generate system prompt using orchestrator
            temp_task = Task(mode_slug=mode_slug)
            content = self.orchestrator.get_system_prompt(temp_task)
            mime_type = "text/plain"
        elif subresource is None:
            # Full mode resource
            content = self._serialize_mode_full(mode)
            mime_type = "application/json"
        else:
            raise ValidationError(
                f"Unknown subresource: {subresource}. "
                f"Valid subresources: config, system_prompt"
            )
        
        logger.debug(f"Read resource {uri} ({len(content)} chars)")
        
        return {
            "contents": [
                {
                    "uri": uri,
                    "mimeType": mime_type,
                    "text": content
                }
            ]
        }
    
    def _serialize_mode_config(self, mode: ModeConfig) -> str:
        """
        Serialize mode to config JSON.
        
        Args:
            mode: Mode configuration to serialize
            
        Returns:
            JSON string representation
        """
        config = {
            "slug": mode.slug,
            "name": mode.name,
            "source": mode.source.value,
            "groups": []
        }
        
        # Serialize groups
        for entry in mode.groups:
            if isinstance(entry, tuple):
                group_name, options = entry
                group_data = [group_name, {}]
                if options.file_regex:
                    group_data[1]["fileRegex"] = options.file_regex
                if options.description:
                    group_data[1]["description"] = options.description
                config["groups"].append(group_data)
            else:
                config["groups"].append(entry)
        
        # Add optional fields if present
        if mode.description:
            config["description"] = mode.description
        if mode.when_to_use:
            config["when_to_use"] = mode.when_to_use
        
        return json.dumps(config, indent=2, ensure_ascii=False)
    
    def _serialize_mode_full(self, mode: ModeConfig) -> str:
        """
        Serialize full mode information including all metadata.
        
        Args:
            mode: Mode configuration to serialize
            
        Returns:
            JSON string representation
        """
        data = {
            "slug": mode.slug,
            "name": mode.name,
            "source": mode.source.value,
            "description": mode.description,
            "when_to_use": mode.when_to_use,
            "role_definition": mode.role_definition,
            "custom_instructions": mode.custom_instructions,
            "tool_groups": {}
        }
        
        # Add tool group info
        for group in ["read", "edit", "browser", "command", "mcp", "modes"]:
            enabled = mode.is_tool_group_enabled(group)
            
            data["tool_groups"][group] = {
                "enabled": enabled
            }
            
            if enabled:
                options = mode.get_group_options(group)
                if options and options.file_regex:
                    data["tool_groups"][group]["file_regex"] = options.file_regex
                if options and options.description:
                    data["tool_groups"][group]["description"] = options.description
        
        return json.dumps(data, indent=2, ensure_ascii=False)
    
    def get_resource_count(self) -> int:
        """
        Get total count of available resources.
        
        Returns:
            Number of resources (3 per mode: full, config, system_prompt)
        """
        return len(self.orchestrator.get_all_modes()) * 3
    
    def get_mode_uris(self) -> List[str]:
        """
        Get list of all mode URIs.
        
        Returns:
            List of mode:// URIs
        """
        uris = []
        for mode in self.orchestrator.get_all_modes():
            uris.append(f"mode://{mode.slug}")
            uris.append(f"mode://{mode.slug}/config")
            uris.append(f"mode://{mode.slug}/system_prompt")
        return uris