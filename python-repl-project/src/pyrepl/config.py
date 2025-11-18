"""
Configuration management for PyREPL.

This module handles loading and managing configuration from multiple sources:
- Default settings
- Configuration files (~/.pyrepl/config.toml)
- Environment variables (prefixed with PYREPL_)
- Command-line arguments

The configuration is merged in the following order (later sources override earlier ones):
1. Default settings
2. Configuration file
3. Environment variables
4. Command-line arguments
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

try:
    import tomllib  # Python 3.11+
except ImportError:
    try:
        import tomli as tomllib  # type: ignore
    except ImportError:
        tomllib = None  # type: ignore


@dataclass
class AppearanceConfig:
    """Configuration for appearance and UI settings."""

    theme: str = "monokai"
    show_line_numbers: bool = True
    prompt_style: str = ">>> "
    continuation_prompt: str = "... "
    enable_syntax_highlighting: bool = True
    color_depth: int = 24  # 1, 4, 8, or 24 bit color


@dataclass
class BehaviorConfig:
    """Configuration for REPL behavior."""

    auto_indent: bool = True
    confirm_exit: bool = True
    enable_pager: bool = True
    auto_suggest: bool = True
    vi_mode: bool = False
    multiline_mode: bool = True
    auto_parentheses: bool = True


@dataclass
class HistoryConfig:
    """Configuration for command history."""

    history_size: int = 10000
    history_file: Optional[Path] = None
    save_history: bool = True
    search_history: bool = True


@dataclass
class Config:
    """
    Main configuration class for PyREPL.

    This class holds all configuration settings and provides methods to load
    and merge configuration from various sources.

    Attributes:
        appearance: Appearance and UI configuration
        behavior: REPL behavior configuration
        history: Command history configuration
    """

    appearance: AppearanceConfig = field(default_factory=AppearanceConfig)
    behavior: BehaviorConfig = field(default_factory=BehaviorConfig)
    history: HistoryConfig = field(default_factory=HistoryConfig)

    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> "Config":
        """
        Load configuration from all available sources.

        Args:
            config_path: Optional path to configuration file. If None, uses default location.

        Returns:
            Config: A fully configured Config instance

        Example:
            >>> config = Config.load()
            >>> print(config.appearance.theme)
            monokai
        """
        config = cls()

        # Set default history file if not set
        if config.history.history_file is None:
            config.history.history_file = config._get_default_history_path()

        # Load from config file
        if config_path is None:
            config_path = config._get_default_config_path()

        if config_path and config_path.exists():
            config._load_from_file(config_path)

        # Load from environment variables
        config._load_from_env()

        return config

    @staticmethod
    def _get_default_config_path() -> Path:
        """
        Get the default configuration file path.

        Returns:
            Path: Path to the default config file (~/.pyrepl/config.toml)
        """
        config_dir = Path.home() / ".pyrepl"
        return config_dir / "config.toml"

    @staticmethod
    def _get_default_history_path() -> Path:
        """
        Get the default history file path.

        Returns:
            Path: Path to the default history file (~/.pyrepl/history)
        """
        config_dir = Path.home() / ".pyrepl"
        config_dir.mkdir(exist_ok=True)
        return config_dir / "history"

    def _load_from_file(self, config_path: Path) -> None:
        """
        Load configuration from a TOML file.

        Args:
            config_path: Path to the configuration file

        Raises:
            ImportError: If tomllib/tomli is not available
            ValueError: If the configuration file is invalid
        """
        if tomllib is None:
            raise ImportError(
                "tomllib/tomli is required to load config files. "
                "Install tomli for Python < 3.11: pip install tomli"
            )

        try:
            with open(config_path, "rb") as f:
                data = tomllib.load(f)

            # Load appearance settings
            if "appearance" in data:
                self._update_dataclass(self.appearance, data["appearance"])

            # Load behavior settings
            if "behavior" in data:
                self._update_dataclass(self.behavior, data["behavior"])

            # Load history settings
            if "history" in data:
                hist_data = data["history"]
                if "history_file" in hist_data:
                    hist_data["history_file"] = Path(hist_data["history_file"]).expanduser()
                self._update_dataclass(self.history, hist_data)

        except Exception as e:
            raise ValueError(f"Failed to load config from {config_path}: {e}") from e

    def _load_from_env(self) -> None:
        """
        Load configuration from environment variables.

        Environment variables should be prefixed with PYREPL_ and use uppercase.
        For nested settings, use double underscores, e.g., PYREPL_APPEARANCE__THEME
        """
        env_prefix = "PYREPL_"

        for key, value in os.environ.items():
            if not key.startswith(env_prefix):
                continue

            # Remove prefix and split into parts
            config_key = key[len(env_prefix) :].lower()
            parts = config_key.split("__")

            if len(parts) == 2:
                section, setting = parts
                self._set_env_value(section, setting, value)
            elif len(parts) == 1:
                # Handle top-level settings if any
                pass

    def _set_env_value(self, section: str, setting: str, value: str) -> None:
        """
        Set a configuration value from an environment variable.

        Args:
            section: Configuration section (appearance, behavior, history)
            setting: Setting name within the section
            value: String value from environment variable
        """
        section_obj = getattr(self, section, None)
        if section_obj is None:
            return

        # Convert string value to appropriate type
        if hasattr(section_obj, setting):
            current_value = getattr(section_obj, setting)
            converted_value = self._convert_env_value(value, type(current_value))
            setattr(section_obj, setting, converted_value)

    @staticmethod
    def _convert_env_value(value: str, target_type: type) -> Any:
        """
        Convert a string environment variable value to the target type.

        Args:
            value: String value from environment variable
            target_type: Target type to convert to

        Returns:
            Any: Converted value
        """
        if target_type == bool:
            return value.lower() in ("true", "1", "yes", "on")
        elif target_type == int:
            return int(value)
        elif target_type == Path:
            return Path(value).expanduser()
        else:
            return value

    @staticmethod
    def _update_dataclass(obj: Any, data: Dict[str, Any]) -> None:
        """
        Update a dataclass instance with values from a dictionary.

        Args:
            obj: Dataclass instance to update
            data: Dictionary with new values
        """
        for key, value in data.items():
            if hasattr(obj, key):
                setattr(obj, key, value)

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert configuration to a dictionary.

        Returns:
            Dict[str, Any]: Dictionary representation of the configuration

        Example:
            >>> config = Config.load()
            >>> config_dict = config.to_dict()
            >>> print(config_dict['appearance']['theme'])
            monokai
        """
        return {
            "appearance": {
                "theme": self.appearance.theme,
                "show_line_numbers": self.appearance.show_line_numbers,
                "prompt_style": self.appearance.prompt_style,
                "continuation_prompt": self.appearance.continuation_prompt,
                "enable_syntax_highlighting": self.appearance.enable_syntax_highlighting,
                "color_depth": self.appearance.color_depth,
            },
            "behavior": {
                "auto_indent": self.behavior.auto_indent,
                "confirm_exit": self.behavior.confirm_exit,
                "enable_pager": self.behavior.enable_pager,
                "auto_suggest": self.behavior.auto_suggest,
                "vi_mode": self.behavior.vi_mode,
                "multiline_mode": self.behavior.multiline_mode,
                "auto_parentheses": self.behavior.auto_parentheses,
            },
            "history": {
                "history_size": self.history.history_size,
                "history_file": str(self.history.history_file) if self.history.history_file else None,
                "save_history": self.history.save_history,
                "search_history": self.history.search_history,
            },
        }


def get_config(config_path: Optional[Path] = None) -> Config:
    """
    Convenience function to get a configured Config instance.

    Args:
        config_path: Optional path to configuration file

    Returns:
        Config: Configured Config instance

    Example:
        >>> from pyrepl.config import get_config
        >>> config = get_config()
        >>> print(config.appearance.theme)
        monokai
    """
    return Config.load(config_path)
