"""Tests for mode configuration system."""

import re
import tempfile
from pathlib import Path

import pytest
import yaml

from roo_code.modes.config import (
    GroupOptions,
    ModeConfig,
    ModeConfigLoader,
    ModeSource,
)


class TestGroupOptions:
    """Test GroupOptions class."""

    def test_create_without_regex(self):
        """Test creating GroupOptions without regex."""
        options = GroupOptions(description="Test description")
        assert options.file_regex is None
        assert options.description == "Test description"

    def test_create_with_valid_regex(self):
        """Test creating GroupOptions with valid regex."""
        options = GroupOptions(file_regex=r"\.py$")
        assert options.file_regex == r"\.py$"

    def test_create_with_invalid_regex(self):
        """Test creating GroupOptions with invalid regex raises error."""
        with pytest.raises(ValueError, match="Invalid regex pattern"):
            GroupOptions(file_regex="[invalid")

    def test_matches_file_without_regex(self):
        """Test file matching when no regex is set."""
        options = GroupOptions()
        assert options.matches_file("any_file.txt")
        assert options.matches_file("test.py")

    def test_matches_file_with_regex(self):
        """Test file matching with regex."""
        options = GroupOptions(file_regex=r"\.py$")
        assert options.matches_file("test.py")
        assert options.matches_file("module/script.py")
        assert not options.matches_file("test.txt")
        assert not options.matches_file("test.py.bak")


class TestModeConfig:
    """Test ModeConfig class."""

    def test_create_minimal_mode(self):
        """Test creating a mode with minimal required fields."""
        mode = ModeConfig(
            slug="test-mode",
            name="Test Mode",
            role_definition="You are a test assistant.",
        )
        assert mode.slug == "test-mode"
        assert mode.name == "Test Mode"
        assert mode.role_definition == "You are a test assistant."
        assert mode.groups == []
        assert mode.source == ModeSource.BUILTIN

    def test_create_full_mode(self):
        """Test creating a mode with all fields."""
        mode = ModeConfig(
            slug="full-mode",
            name="Full Mode",
            role_definition="You are a full assistant.",
            groups=["read", "edit"],
            when_to_use="When you need everything",
            description="A complete mode",
            custom_instructions="Follow these rules",
            source=ModeSource.PROJECT,
        )
        assert mode.slug == "full-mode"
        assert mode.when_to_use == "When you need everything"
        assert mode.description == "A complete mode"
        assert mode.custom_instructions == "Follow these rules"
        assert mode.source == ModeSource.PROJECT

    def test_invalid_slug_format(self):
        """Test that invalid slug formats raise errors."""
        with pytest.raises(ValueError, match="Invalid slug"):
            ModeConfig(
                slug="test mode",  # Space not allowed
                name="Test",
                role_definition="Test",
            )

        with pytest.raises(ValueError, match="Invalid slug"):
            ModeConfig(
                slug="test_mode",  # Underscore not allowed
                name="Test",
                role_definition="Test",
            )

    def test_empty_required_fields(self):
        """Test that empty required fields raise errors."""
        with pytest.raises(ValueError, match="name is required"):
            ModeConfig(slug="test", name="", role_definition="Test")

        with pytest.raises(ValueError, match="role_definition is required"):
            ModeConfig(slug="test", name="Test", role_definition="")

    def test_duplicate_groups(self):
        """Test that duplicate groups raise errors."""
        with pytest.raises(ValueError, match="Duplicate group"):
            ModeConfig(
                slug="test",
                name="Test",
                role_definition="Test",
                groups=["read", "read"],
            )

    def test_invalid_tool_group(self):
        """Test that invalid tool groups raise errors."""
        with pytest.raises(ValueError, match="Invalid tool group"):
            ModeConfig(
                slug="test",
                name="Test",
                role_definition="Test",
                groups=["invalid_group"],
            )

    def test_groups_with_options(self):
        """Test mode with group options."""
        mode = ModeConfig(
            slug="test",
            name="Test",
            role_definition="Test",
            groups=[
                "read",
                ("edit", GroupOptions(file_regex=r"\.md$")),
            ],
        )
        assert mode.is_tool_group_enabled("read")
        assert mode.is_tool_group_enabled("edit")
        assert not mode.is_tool_group_enabled("command")

    def test_can_edit_file_no_restrictions(self):
        """Test file editing without restrictions."""
        mode = ModeConfig(
            slug="test",
            name="Test",
            role_definition="Test",
            groups=["edit"],
        )
        assert mode.can_edit_file("test.py")
        assert mode.can_edit_file("test.md")
        assert mode.can_edit_file("any_file.txt")

    def test_can_edit_file_with_restrictions(self):
        """Test file editing with regex restrictions."""
        mode = ModeConfig(
            slug="test",
            name="Test",
            role_definition="Test",
            groups=[("edit", GroupOptions(file_regex=r"\.md$"))],
        )
        assert mode.can_edit_file("README.md")
        assert mode.can_edit_file("docs/guide.md")
        assert not mode.can_edit_file("test.py")
        assert not mode.can_edit_file("config.json")

    def test_can_edit_file_no_edit_group(self):
        """Test file editing when edit group is not enabled."""
        mode = ModeConfig(
            slug="test",
            name="Test",
            role_definition="Test",
            groups=["read"],
        )
        assert not mode.can_edit_file("test.py")
        assert not mode.can_edit_file("test.md")


class TestModeConfigLoader:
    """Test ModeConfigLoader class."""

    def test_load_from_nonexistent_file(self):
        """Test loading from a file that doesn't exist."""
        loader = ModeConfigLoader()
        modes = loader.load_from_yaml(Path("/nonexistent/file.yaml"), ModeSource.GLOBAL)
        assert modes == []

    def test_load_from_valid_yaml(self):
        """Test loading modes from valid YAML."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml_content = """
customModes:
  - slug: test-mode
    name: Test Mode
    roleDefinition: You are a test assistant
    groups:
      - read
      - edit
    description: A test mode
"""
            f.write(yaml_content)
            yaml_path = Path(f.name)

        try:
            loader = ModeConfigLoader()
            modes = loader.load_from_yaml(yaml_path, ModeSource.GLOBAL)

            assert len(modes) == 1
            mode = modes[0]
            assert mode.slug == "test-mode"
            assert mode.name == "Test Mode"
            assert mode.source == ModeSource.GLOBAL
            assert "read" in [g if isinstance(g, str) else g[0] for g in mode.groups]
        finally:
            yaml_path.unlink()

    def test_load_with_group_options(self):
        """Test loading modes with group options."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml_content = """
customModes:
  - slug: test-mode
    name: Test Mode
    roleDefinition: You are a test assistant
    groups:
      - read
      - [edit, {fileRegex: '\\.md$', description: 'Markdown only'}]
"""
            f.write(yaml_content)
            yaml_path = Path(f.name)

        try:
            loader = ModeConfigLoader()
            modes = loader.load_from_yaml(yaml_path, ModeSource.GLOBAL)

            assert len(modes) == 1
            mode = modes[0]
            
            # Check group options
            edit_options = mode.get_group_options("edit")
            assert edit_options is not None
            assert edit_options.file_regex == r"\.md$"
            assert edit_options.description == "Markdown only"
        finally:
            yaml_path.unlink()

    def test_merge_modes_precedence(self):
        """Test that mode merging respects precedence."""
        loader = ModeConfigLoader()

        builtin = [
            ModeConfig(
                slug="test",
                name="Builtin Test",
                role_definition="Builtin",
                source=ModeSource.BUILTIN,
            )
        ]

        global_modes = [
            ModeConfig(
                slug="test",
                name="Global Test",
                role_definition="Global",
                source=ModeSource.GLOBAL,
            ),
            ModeConfig(
                slug="global-only",
                name="Global Only",
                role_definition="Global only",
                source=ModeSource.GLOBAL,
            ),
        ]

        project = [
            ModeConfig(
                slug="test",
                name="Project Test",
                role_definition="Project",
                source=ModeSource.PROJECT,
            )
        ]

        merged = loader._merge_modes(builtin, global_modes, project)

        # Project should override
        test_mode = next(m for m in merged if m.slug == "test")
        assert test_mode.name == "Project Test"

        # Global-only mode should be present
        assert any(m.slug == "global-only" for m in merged)

    def test_save_and_load_roundtrip(self):
        """Test saving and loading modes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yaml_path = Path(tmpdir) / "modes.yaml"

            original_modes = [
                ModeConfig(
                    slug="test-mode",
                    name="Test Mode",
                    role_definition="Test",
                    groups=["read", ("edit", GroupOptions(file_regex=r"\.py$"))],
                    description="A test mode",
                )
            ]

            loader = ModeConfigLoader()
            loader.save_to_yaml(original_modes, yaml_path)

            # Load back
            loaded_modes = loader.load_from_yaml(yaml_path, ModeSource.GLOBAL)

            assert len(loaded_modes) == 1
            loaded = loaded_modes[0]
            assert loaded.slug == "test-mode"
            assert loaded.name == "Test Mode"
            assert loaded.description == "A test mode"

            # Check group options preserved
            edit_options = loaded.get_group_options("edit")
            assert edit_options is not None
            assert edit_options.file_regex == r"\.py$"