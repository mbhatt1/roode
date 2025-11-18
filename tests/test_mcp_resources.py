"""
Unit tests for MCP resource handlers.

Tests resource operations for exposing modes as MCP resources.
"""

import pytest
from unittest.mock import Mock, AsyncMock
from roo_code.mcp.resources import ResourceHandler
from roo_code.mcp.validation import ValidationError
from roo_code.modes.config import ModeConfig, ModeSource, ToolGroupOptions
from roo_code.modes.orchestrator import ModeOrchestrator


@pytest.fixture
def mock_orchestrator():
    """Create a mock mode orchestrator with sample modes."""
    orchestrator = Mock(spec=ModeOrchestrator)
    
    # Create sample modes
    code_mode = ModeConfig(
        slug="code",
        name="Code Mode",
        source=ModeSource.BUILTIN,
        description="Write and modify code",
        when_to_use="Use when writing or editing code",
        role_definition="You are a code assistant",
        custom_instructions="Follow best practices",
        groups=["read", "edit", "command"]
    )
    
    ask_mode = ModeConfig(
        slug="ask",
        name="Ask Mode",
        source=ModeSource.BUILTIN,
        description="Answer questions",
        groups=["read"]
    )
    
    architect_mode = ModeConfig(
        slug="architect",
        name="Architect Mode",
        source=ModeSource.GLOBAL,
        description="Design systems",
        groups=[
            ("read", ToolGroupOptions()),
            ("edit", ToolGroupOptions(file_regex=r"\.md$"))
        ]
    )
    
    orchestrator.get_all_modes = Mock(return_value=[code_mode, ask_mode, architect_mode])
    orchestrator.get_mode = Mock(side_effect=lambda slug: {
        "code": code_mode,
        "ask": ask_mode,
        "architect": architect_mode
    }.get(slug))
    orchestrator.get_mode_names = Mock(return_value=["code", "ask", "architect"])
    orchestrator.get_system_prompt = Mock(return_value="System prompt for mode")
    
    return orchestrator


@pytest.fixture
def resource_handler(mock_orchestrator):
    """Create a resource handler."""
    return ResourceHandler(mock_orchestrator)


class TestResourceHandler:
    """Test ResourceHandler class."""
    
    def test_init(self, mock_orchestrator):
        """Test handler initialization."""
        handler = ResourceHandler(mock_orchestrator)
        
        assert handler.orchestrator == mock_orchestrator
    
    @pytest.mark.asyncio
    async def test_list_resources(self, resource_handler):
        """Test listing all mode resources."""
        resources = await resource_handler.list_resources()
        
        # Should have 3 resources per mode (full, config, system_prompt)
        assert len(resources) == 9
        
        # Check resource format
        for resource in resources:
            assert "uri" in resource
            assert "name" in resource
            assert "mimeType" in resource
            assert "description" in resource
            assert resource["uri"].startswith("mode://")
    
    @pytest.mark.asyncio
    async def test_list_resources_structure(self, resource_handler):
        """Test resource list structure for each mode."""
        resources = await resource_handler.list_resources()
        
        # Group by mode
        mode_resources = {}
        for res in resources:
            mode_slug = res["uri"].split("//")[1].split("/")[0]
            if mode_slug not in mode_resources:
                mode_resources[mode_slug] = []
            mode_resources[mode_slug].append(res)
        
        # Each mode should have 3 resources
        for mode_slug, mode_res in mode_resources.items():
            assert len(mode_res) == 3
            
            uris = [r["uri"] for r in mode_res]
            assert f"mode://{mode_slug}" in uris
            assert f"mode://{mode_slug}/config" in uris
            assert f"mode://{mode_slug}/system_prompt" in uris
    
    @pytest.mark.asyncio
    async def test_read_resource_full_mode(self, resource_handler):
        """Test reading full mode resource."""
        result = await resource_handler.read_resource("mode://code")
        
        assert "contents" in result
        assert len(result["contents"]) == 1
        
        content = result["contents"][0]
        assert content["uri"] == "mode://code"
        assert content["mimeType"] == "application/json"
        assert "text" in content
        
        # Parse JSON content
        import json
        data = json.loads(content["text"])
        
        assert data["slug"] == "code"
        assert data["name"] == "Code Mode"
        assert data["source"] == "builtin"
        assert "tool_groups" in data
    
    @pytest.mark.asyncio
    async def test_read_resource_config(self, resource_handler):
        """Test reading mode config resource."""
        result = await resource_handler.read_resource("mode://code/config")
        
        content = result["contents"][0]
        assert content["uri"] == "mode://code/config"
        assert content["mimeType"] == "application/json"
        
        # Parse JSON content
        import json
        data = json.loads(content["text"])
        
        assert data["slug"] == "code"
        assert data["name"] == "Code Mode"
        assert data["source"] == "builtin"
        assert "groups" in data
    
    @pytest.mark.asyncio
    async def test_read_resource_system_prompt(self, resource_handler, mock_orchestrator):
        """Test reading system prompt resource."""
        result = await resource_handler.read_resource("mode://code/system_prompt")
        
        content = result["contents"][0]
        assert content["uri"] == "mode://code/system_prompt"
        assert content["mimeType"] == "text/plain"
        assert content["text"] == "System prompt for mode"
        
        # Verify get_system_prompt was called
        mock_orchestrator.get_system_prompt.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_read_resource_invalid_uri_no_scheme(self, resource_handler):
        """Test reading resource with invalid URI (no scheme)."""
        with pytest.raises(ValidationError) as exc_info:
            await resource_handler.read_resource("code")
        
        assert "://" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_read_resource_wrong_scheme(self, resource_handler):
        """Test reading resource with wrong scheme."""
        with pytest.raises(ValidationError) as exc_info:
            await resource_handler.read_resource("http://code")
        
        assert "mode" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_read_resource_empty_mode_slug(self, resource_handler):
        """Test reading resource with empty mode slug."""
        with pytest.raises(ValidationError) as exc_info:
            await resource_handler.read_resource("mode://")
        
        assert "slug" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_read_resource_nonexistent_mode(self, resource_handler):
        """Test reading resource for non-existent mode."""
        with pytest.raises(ValidationError) as exc_info:
            await resource_handler.read_resource("mode://nonexistent")
        
        assert "not found" in str(exc_info.value).lower()
        assert "nonexistent" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_read_resource_invalid_subresource(self, resource_handler):
        """Test reading invalid subresource."""
        with pytest.raises(ValidationError) as exc_info:
            await resource_handler.read_resource("mode://code/invalid")
        
        assert "unknown" in str(exc_info.value).lower()
        assert "subresource" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_read_resource_multiple_paths(self, resource_handler):
        """Test reading resource with multiple path segments."""
        with pytest.raises(ValidationError) as exc_info:
            await resource_handler.read_resource("mode://code/config/extra")
        
        # Should treat as unknown subresource
        assert "unknown" in str(exc_info.value).lower()
    
    def test_get_resource_count(self, resource_handler, mock_orchestrator):
        """Test getting resource count."""
        # 3 modes × 3 resources per mode
        count = resource_handler.get_resource_count()
        
        assert count == 9
    
    def test_get_mode_uris(self, resource_handler):
        """Test getting all mode URIs."""
        uris = resource_handler.get_mode_uris()
        
        assert len(uris) == 9
        
        # Check specific URIs
        assert "mode://code" in uris
        assert "mode://code/config" in uris
        assert "mode://code/system_prompt" in uris
        assert "mode://ask" in uris
        assert "mode://architect/config" in uris


class TestResourceSerialization:
    """Test resource serialization methods."""
    
    @pytest.fixture
    def handler(self, mock_orchestrator):
        """Create handler for serialization tests."""
        return ResourceHandler(mock_orchestrator)
    
    def test_serialize_mode_config_basic(self, handler, mock_orchestrator):
        """Test serializing basic mode config."""
        mode = mock_orchestrator.get_mode("code")
        
        json_str = handler._serialize_mode_config(mode)
        
        import json
        data = json.loads(json_str)
        
        assert data["slug"] == "code"
        assert data["name"] == "Code Mode"
        assert data["source"] == "builtin"
        assert isinstance(data["groups"], list)
    
    def test_serialize_mode_config_with_options(self, handler, mock_orchestrator):
        """Test serializing mode with tool group options."""
        mode = mock_orchestrator.get_mode("architect")
        
        json_str = handler._serialize_mode_config(mode)
        
        import json
        data = json.loads(json_str)
        
        assert data["slug"] == "architect"
        assert isinstance(data["groups"], list)
        
        # Check for group with options
        edit_group = None
        for group in data["groups"]:
            if isinstance(group, list) and group[0] == "edit":
                edit_group = group
                break
        
        assert edit_group is not None
        assert "fileRegex" in edit_group[1]
    
    def test_serialize_mode_config_optional_fields(self, handler):
        """Test serializing mode with optional fields."""
        mode = ModeConfig(
            slug="test",
            name="Test Mode",
            source=ModeSource.BUILTIN,
            description="Test description",
            when_to_use="Use for testing",
            groups=["read"]
        )
        
        json_str = handler._serialize_mode_config(mode)
        
        import json
        data = json.loads(json_str)
        
        assert data["description"] == "Test description"
        assert data["when_to_use"] == "Use for testing"
    
    def test_serialize_mode_full(self, handler, mock_orchestrator):
        """Test serializing full mode information."""
        mode = mock_orchestrator.get_mode("code")
        
        json_str = handler._serialize_mode_full(mode)
        
        import json
        data = json.loads(json_str)
        
        assert data["slug"] == "code"
        assert data["name"] == "Code Mode"
        assert data["source"] == "builtin"
        assert data["description"] == "Write and modify code"
        assert data["when_to_use"] == "Use when writing or editing code"
        assert data["role_definition"] == "You are a code assistant"
        assert data["custom_instructions"] == "Follow best practices"
        assert "tool_groups" in data
    
    def test_serialize_mode_full_tool_groups(self, handler, mock_orchestrator):
        """Test tool groups in full serialization."""
        mode = mock_orchestrator.get_mode("code")
        
        json_str = handler._serialize_mode_full(mode)
        
        import json
        data = json.loads(json_str)
        
        tool_groups = data["tool_groups"]
        
        # Check all standard groups
        assert "read" in tool_groups
        assert "edit" in tool_groups
        assert "browser" in tool_groups
        assert "command" in tool_groups
        assert "mcp" in tool_groups
        assert "modes" in tool_groups
        
        # Each should have enabled status
        for group_name, group_data in tool_groups.items():
            assert "enabled" in group_data
            assert isinstance(group_data["enabled"], bool)
    
    def test_serialize_mode_full_disabled_groups(self, handler):
        """Test serialization of disabled tool groups."""
        mode = ModeConfig(
            slug="minimal",
            name="Minimal Mode",
            source=ModeSource.BUILTIN,
            groups=["read"]  # Only read enabled
        )
        
        # Need to mock orchestrator for this mode
        handler.orchestrator.get_mode = Mock(return_value=mode)
        
        json_str = handler._serialize_mode_full(mode)
        
        import json
        data = json.loads(json_str)
        
        # Read should be enabled, others disabled
        assert data["tool_groups"]["read"]["enabled"] is True
        assert data["tool_groups"]["edit"]["enabled"] is False
        assert data["tool_groups"]["command"]["enabled"] is False
    
    def test_serialize_unicode(self, handler):
        """Test serialization handles Unicode correctly."""
        mode = ModeConfig(
            slug="unicode",
            name="Unicode 世界 🌍",
            source=ModeSource.BUILTIN,
            description="Test with 中文 and emoji 🎉",
            groups=["read"]
        )
        
        json_str = handler._serialize_mode_config(mode)
        
        import json
        data = json.loads(json_str)
        
        assert data["name"] == "Unicode 世界 🌍"
        assert data["description"] == "Test with 中文 and emoji 🎉"


class TestResourceHandlerIntegration:
    """Test resource handler integration scenarios."""
    
    @pytest.mark.asyncio
    async def test_list_and_read_all_resources(self, resource_handler):
        """Test listing and reading all resources."""
        # List all resources
        resources = await resource_handler.list_resources()
        
        # Try to read each resource
        for resource in resources:
            uri = resource["uri"]
            result = await resource_handler.read_resource(uri)
            
            assert "contents" in result
            assert len(result["contents"]) > 0
            
            content = result["contents"][0]
            assert content["uri"] == uri
            assert "text" in content
            assert len(content["text"]) > 0
    
    @pytest.mark.asyncio
    async def test_resource_discovery_flow(self, resource_handler):
        """Test typical resource discovery flow."""
        # 1. List all resources
        resources = await resource_handler.list_resources()
        
        # 2. Find code mode resources
        code_resources = [r for r in resources if r["uri"].startswith("mode://code")]
        assert len(code_resources) == 3
        
        # 3. Read each code resource
        for resource in code_resources:
            result = await resource_handler.read_resource(resource["uri"])
            assert result is not None
    
    @pytest.mark.asyncio
    async def test_read_all_mode_types(self, resource_handler):
        """Test reading all types of mode resources."""
        mode_slug = "code"
        
        # Read full mode
        full = await resource_handler.read_resource(f"mode://{mode_slug}")
        import json
        full_data = json.loads(full["contents"][0]["text"])
        assert "tool_groups" in full_data
        
        # Read config
        config = await resource_handler.read_resource(f"mode://{mode_slug}/config")
        config_data = json.loads(config["contents"][0]["text"])
        assert "groups" in config_data
        
        # Read system prompt
        prompt = await resource_handler.read_resource(f"mode://{mode_slug}/system_prompt")
        prompt_text = prompt["contents"][0]["text"]
        assert isinstance(prompt_text, str)
        assert len(prompt_text) > 0
    
    @pytest.mark.asyncio
    async def test_error_handling_flow(self, resource_handler):
        """Test error handling in resource operations."""
        # Invalid URI format
        try:
            await resource_handler.read_resource("invalid")
            assert False, "Should raise ValidationError"
        except ValidationError:
            pass
        
        # Wrong scheme
        try:
            await resource_handler.read_resource("http://code")
            assert False, "Should raise ValidationError"
        except ValidationError:
            pass
        
        # Non-existent mode
        try:
            await resource_handler.read_resource("mode://nonexistent")
            assert False, "Should raise ValidationError"
        except ValidationError:
            pass
        
        # Invalid subresource
        try:
            await resource_handler.read_resource("mode://code/invalid")
            assert False, "Should raise ValidationError"
        except ValidationError:
            pass