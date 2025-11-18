"""
Mode configuration system with YAML loading and validation.

This module provides the core configuration classes for the mode system,
including ModeConfig, GroupOptions, and ModeConfigLoader for loading modes
from YAML files with proper precedence (builtin < global < project).
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Literal, Optional, Set, Tuple, Union

import yaml

# Tool groups that modes can enable
ToolGroup = Literal["read", "edit", "browser", "command", "mcp", "modes"]

VALID_TOOL_GROUPS: Set[str] = {"read", "edit", "browser", "command", "mcp", "modes"}


class ModeSource(str, Enum):
    """Source of a mode configuration."""

    BUILTIN = "builtin"
    GLOBAL = "global"
    PROJECT = "project"


@dataclass
class GroupOptions:
    """Options for a tool group, including file restrictions."""

    file_regex: Optional[str] = None
    description: Optional[str] = None

    def __post_init__(self):
        """Validate regex pattern if provided."""
        if self.file_regex:
            try:
                re.compile(self.file_regex)
            except re.error as e:
                raise ValueError(f"Invalid regex pattern: {self.file_regex}") from e

    def matches_file(self, file_path: str) -> bool:
        """Check if a file path matches this group's restrictions."""
        if not self.file_regex:
            return True
        try:
            return bool(re.search(self.file_regex, file_path))
        except re.error:
            return False


# GroupEntry can be either just a group name or a tuple of (group name, options)
GroupEntry = Union[ToolGroup, Tuple[ToolGroup, GroupOptions]]


@dataclass
class ModeConfig:
    """
    Configuration for a mode/persona.

    Attributes:
        slug: Unique identifier (lowercase, alphanumeric with dashes)
        name: Display name (can include emoji)
        role_definition: The system prompt defining the mode's role
        groups: List of enabled tool groups, optionally with restrictions
        when_to_use: Description of when this mode should be used
        description: Short description of the mode
        custom_instructions: Additional mode-specific instructions
        source: Where this mode was loaded from (builtin/global/project)
    """

    slug: str
    name: str
    role_definition: str
    groups: List[GroupEntry] = field(default_factory=list)
    when_to_use: Optional[str] = None
    description: Optional[str] = None
    custom_instructions: Optional[str] = None
    source: ModeSource = ModeSource.BUILTIN

    def __post_init__(self):
        """Validate the mode configuration."""
        # Validate slug format
        if not re.match(r"^[a-zA-Z0-9-]+$", self.slug):
            raise ValueError(
                f"Invalid slug '{self.slug}': must contain only letters, numbers, and dashes"
            )

        # Validate required fields
        if not self.name:
            raise ValueError("Mode name is required")
        if not self.role_definition:
            raise ValueError("Mode role_definition is required")

        # Validate and normalize groups
        self._validate_groups()

    def _validate_groups(self):
        """Validate that groups don't have duplicates and use valid tool groups."""
        seen_groups: Set[str] = set()

        for entry in self.groups:
            # Extract group name from entry
            if isinstance(entry, tuple):
                group_name = entry[0]
            else:
                group_name = entry

            # Check for duplicates
            if group_name in seen_groups:
                raise ValueError(f"Duplicate group '{group_name}' in mode '{self.slug}'")
            seen_groups.add(group_name)

            # Validate group name
            if group_name not in VALID_TOOL_GROUPS:
                raise ValueError(
                    f"Invalid tool group '{group_name}' in mode '{self.slug}'. "
                    f"Valid groups: {', '.join(sorted(VALID_TOOL_GROUPS))}"
                )

    def is_tool_group_enabled(self, group: str) -> bool:
        """Check if a tool group is enabled in this mode."""
        for entry in self.groups:
            entry_group = entry[0] if isinstance(entry, tuple) else entry
            if entry_group == group:
                return True
        return False

    def get_group_options(self, group: str) -> Optional[GroupOptions]:
        """Get options for a specific tool group, if any."""
        for entry in self.groups:
            if isinstance(entry, tuple):
                entry_group, options = entry
                if entry_group == group:
                    return options
            elif entry == group:
                return None
        return None

    def can_edit_file(self, file_path: str) -> bool:
        """
        Check if this mode can edit a specific file based on fileRegex restrictions.

        Args:
            file_path: Path to the file to check

        Returns:
            True if the mode can edit the file, False otherwise
        """
        if not self.is_tool_group_enabled("edit"):
            return False

        edit_options = self.get_group_options("edit")
        if edit_options is None:
            # No restrictions, all files allowed
            return True

        return edit_options.matches_file(file_path)


class ModeConfigLoader:
    """
    Loads and manages mode configurations from multiple sources.

    Supports loading from:
    - Built-in modes (hardcoded defaults)
    - Global configuration (.roo-code/modes.yaml)
    - Project configuration (.roomodes in project root)

    Precedence: project > global > builtin
    """

    GLOBAL_MODES_FILENAME = "modes.yaml"
    PROJECT_MODES_FILENAME = ".roomodes"

    def __init__(self, global_config_dir: Optional[Path] = None):
        """
        Initialize the mode loader.

        Args:
            global_config_dir: Path to global config directory (defaults to ~/.roo-code)
        """
        if global_config_dir is None:
            global_config_dir = Path.home() / ".roo-code"
        self.global_config_dir = global_config_dir

    def load_from_yaml(self, file_path: Path, source: ModeSource) -> List[ModeConfig]:
        """
        Load modes from a YAML file.

        Args:
            file_path: Path to YAML file
            source: Source type for the loaded modes

        Returns:
            List of loaded mode configurations

        The YAML file should have format:
        ```yaml
        customModes:
          - slug: my-mode
            name: My Mode
            roleDefinition: You are...
            groups:
              - read
              - [edit, {fileRegex: "\\.py$"}]
        ```
        """
        if not file_path.exists():
            return []

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Strip BOM if present
            if content.startswith("\ufeff"):
                content = content[1:]

            data = yaml.safe_load(content)
            if not data or not isinstance(data, dict):
                return []

            custom_modes = data.get("customModes", [])
            if not isinstance(custom_modes, list):
                return []

            modes = []
            for mode_data in custom_modes:
                try:
                    mode = self._parse_mode_dict(mode_data, source)
                    modes.append(mode)
                except (ValueError, KeyError, TypeError) as e:
                    # Log error but continue loading other modes
                    print(f"Warning: Failed to load mode from {file_path}: {e}")
                    continue

            return modes

        except yaml.YAMLError as e:
            print(f"Error parsing YAML file {file_path}: {e}")
            return []
        except Exception as e:
            print(f"Error loading modes from {file_path}: {e}")
            return []

    def _parse_mode_dict(self, data: dict, source: ModeSource) -> ModeConfig:
        """Parse a mode configuration from a dictionary."""
        # Parse groups
        groups: List[GroupEntry] = []
        raw_groups = data.get("groups", [])

        for group_entry in raw_groups:
            if isinstance(group_entry, str):
                # Simple group name
                groups.append(group_entry)  # type: ignore
            elif isinstance(group_entry, list) and len(group_entry) == 2:
                # [group_name, options_dict]
                group_name = group_entry[0]
                options_dict = group_entry[1]

                if not isinstance(options_dict, dict):
                    raise ValueError(f"Group options must be a dict, got {type(options_dict)}")

                options = GroupOptions(
                    file_regex=options_dict.get("fileRegex"),
                    description=options_dict.get("description"),
                )
                groups.append((group_name, options))  # type: ignore
            else:
                raise ValueError(f"Invalid group entry format: {group_entry}")

        return ModeConfig(
            slug=data["slug"],
            name=data["name"],
            role_definition=data["roleDefinition"],
            groups=groups,
            when_to_use=data.get("whenToUse"),
            description=data.get("description"),
            custom_instructions=data.get("customInstructions"),
            source=source,
        )

    def load_all_modes(
        self,
        project_root: Optional[Path] = None,
        builtin_modes: Optional[List[ModeConfig]] = None,
    ) -> List[ModeConfig]:
        """
        Load and merge modes from all sources with proper precedence.

        Args:
            project_root: Root directory of the current project
            builtin_modes: List of builtin modes to use as base

        Returns:
            Merged list of modes with precedence: project > global > builtin
        """
        if builtin_modes is None:
            builtin_modes = []

        # Load from each source
        global_path = self.global_config_dir / self.GLOBAL_MODES_FILENAME
        global_modes = self.load_from_yaml(global_path, ModeSource.GLOBAL)

        project_modes: List[ModeConfig] = []
        if project_root:
            project_path = project_root / self.PROJECT_MODES_FILENAME
            project_modes = self.load_from_yaml(project_path, ModeSource.PROJECT)

        # Merge with precedence: project > global > builtin
        return self._merge_modes(builtin_modes, global_modes, project_modes)

    def _merge_modes(
        self,
        builtin_modes: List[ModeConfig],
        global_modes: List[ModeConfig],
        project_modes: List[ModeConfig],
    ) -> List[ModeConfig]:
        """
        Merge modes from different sources with proper precedence.

        Project modes override global modes, which override builtin modes.
        Modes are identified by their slug.
        """
        modes_by_slug: Dict[str, ModeConfig] = {}

        # Add builtin modes first
        for mode in builtin_modes:
            modes_by_slug[mode.slug] = mode

        # Add global modes (overriding builtin)
        for mode in global_modes:
            modes_by_slug[mode.slug] = mode

        # Add project modes (overriding everything)
        for mode in project_modes:
            modes_by_slug[mode.slug] = mode

        # Return in deterministic order (sorted by slug)
        return sorted(modes_by_slug.values(), key=lambda m: m.slug)

    def save_to_yaml(self, modes: List[ModeConfig], file_path: Path) -> None:
        """
        Save modes to a YAML file.

        Args:
            modes: List of modes to save
            file_path: Path to save to
        """
        # Create parent directories if needed
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Convert modes to dict format
        modes_data = []
        for mode in modes:
            mode_dict = {
                "slug": mode.slug,
                "name": mode.name,
                "roleDefinition": mode.role_definition,
                "groups": self._serialize_groups(mode.groups),
            }

            # Add optional fields if present
            if mode.when_to_use:
                mode_dict["whenToUse"] = mode.when_to_use
            if mode.description:
                mode_dict["description"] = mode.description
            if mode.custom_instructions:
                mode_dict["customInstructions"] = mode.custom_instructions

            modes_data.append(mode_dict)

        # Write to file
        data = {"customModes": modes_data}
        with open(file_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    def _serialize_groups(self, groups: List[GroupEntry]) -> List:
        """Convert groups to serializable format."""
        result = []
        for entry in groups:
            if isinstance(entry, tuple):
                group_name, options = entry
                options_dict = {}
                if options.file_regex:
                    options_dict["fileRegex"] = options.file_regex
                if options.description:
                    options_dict["description"] = options.description
                result.append([group_name, options_dict])
            else:
                result.append(entry)
        return result