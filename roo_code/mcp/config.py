"""
Server configuration management.

This module provides configuration loading and management for the MCP Modes Server.
"""

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class ServerConfig:
    """Configuration for MCP Modes Server."""
    
    # Server info
    server_name: str = "roo-modes-server"
    server_version: str = "1.0.0"
    server_description: str = "MCP server exposing Roo-Code mode system"
    
    # Paths
    project_root: Optional[Path] = None
    global_config_dir: Path = field(default_factory=lambda: Path.home() / ".roo-code")
    
    # Session management
    session_timeout: int = 3600  # 1 hour in seconds
    cleanup_interval: int = 300  # 5 minutes in seconds
    
    # Persistence (optional)
    persistence_enabled: bool = False
    storage_path: Optional[Path] = None
    
    # Logging
    log_level: str = "INFO"
    log_file: Path = field(default_factory=lambda: Path.home() / ".roo-code" / "mcp_modes_server.log")
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    @classmethod
    def from_file(cls, path: Path) -> "ServerConfig":
        """
        Load configuration from JSON file.
        
        Args:
            path: Path to configuration file
            
        Returns:
            Loaded ServerConfig instance
            
        Raises:
            FileNotFoundError: If config file doesn't exist
            json.JSONDecodeError: If config file is invalid JSON
        """
        with open(path) as f:
            data = json.load(f)
        
        config = cls()
        
        # Server info
        if "server" in data:
            server = data["server"]
            config.server_name = server.get("name", config.server_name)
            config.server_version = server.get("version", config.server_version)
            config.server_description = server.get("description", config.server_description)
        
        # Paths
        if "paths" in data:
            paths = data["paths"]
            if paths.get("project_root"):
                config.project_root = Path(paths["project_root"]).expanduser()
            if paths.get("global_config_dir"):
                config.global_config_dir = Path(paths["global_config_dir"]).expanduser()
        
        # Sessions
        if "sessions" in data:
            sessions = data["sessions"]
            config.session_timeout = sessions.get("timeout", config.session_timeout)
            config.cleanup_interval = sessions.get("cleanup_interval", config.cleanup_interval)
            
            # Persistence
            if "persistence" in sessions:
                persistence = sessions["persistence"]
                config.persistence_enabled = persistence.get("enabled", False)
                if persistence.get("storage_path"):
                    config.storage_path = Path(persistence["storage_path"]).expanduser()
        
        # Logging
        if "logging" in data:
            log_config = data["logging"]
            config.log_level = log_config.get("level", config.log_level)
            if log_config.get("file"):
                config.log_file = Path(log_config["file"]).expanduser()
            config.log_format = log_config.get("format", config.log_format)
        
        logger.info(f"Loaded configuration from {path}")
        return config
    
    @classmethod
    def from_env(cls) -> "ServerConfig":
        """
        Load configuration from environment variables.
        
        Environment variables:
        - ROO_PROJECT_ROOT: Project root directory
        - ROO_CONFIG_DIR: Global config directory (default: ~/.roo-code)
        - ROO_SESSION_TIMEOUT: Session timeout in seconds
        - ROO_LOG_LEVEL: Logging level (DEBUG, INFO, WARNING, ERROR)
        - ROO_LOG_FILE: Log file path
        
        Returns:
            ServerConfig loaded from environment
        """
        config = cls()
        
        # Paths
        if os.getenv("ROO_PROJECT_ROOT"):
            config.project_root = Path(os.getenv("ROO_PROJECT_ROOT")).expanduser()
        
        if os.getenv("ROO_CONFIG_DIR"):
            config.global_config_dir = Path(os.getenv("ROO_CONFIG_DIR")).expanduser()
        
        # Session management
        if os.getenv("ROO_SESSION_TIMEOUT"):
            try:
                config.session_timeout = int(os.getenv("ROO_SESSION_TIMEOUT"))
            except ValueError:
                logger.warning("Invalid ROO_SESSION_TIMEOUT value, using default")
        
        # Logging
        if os.getenv("ROO_LOG_LEVEL"):
            config.log_level = os.getenv("ROO_LOG_LEVEL")
        
        if os.getenv("ROO_LOG_FILE"):
            config.log_file = Path(os.getenv("ROO_LOG_FILE")).expanduser()
        
        logger.info("Loaded configuration from environment variables")
        return config
    
    @classmethod
    def get_default(cls) -> "ServerConfig":
        """
        Get default configuration.
        
        Returns:
            Default ServerConfig instance
        """
        return cls()
    
    def to_dict(self) -> dict:
        """
        Convert configuration to dictionary.
        
        Returns:
            Configuration as dict
        """
        return {
            "server": {
                "name": self.server_name,
                "version": self.server_version,
                "description": self.server_description
            },
            "paths": {
                "project_root": str(self.project_root) if self.project_root else None,
                "global_config_dir": str(self.global_config_dir)
            },
            "sessions": {
                "timeout": self.session_timeout,
                "cleanup_interval": self.cleanup_interval,
                "persistence": {
                    "enabled": self.persistence_enabled,
                    "storage_path": str(self.storage_path) if self.storage_path else None
                }
            },
            "logging": {
                "level": self.log_level,
                "file": str(self.log_file),
                "format": self.log_format
            }
        }
    
    def save_to_file(self, path: Path) -> None:
        """
        Save configuration to JSON file.
        
        Args:
            path: Path to save configuration to
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
        logger.info(f"Saved configuration to {path}")
    
    def validate(self) -> None:
        """
        Validate configuration values.
        
        Raises:
            ValueError: If configuration is invalid
        """
        # Validate timeout values
        if self.session_timeout <= 0:
            raise ValueError("session_timeout must be positive")
        
        if self.cleanup_interval <= 0:
            raise ValueError("cleanup_interval must be positive")
        
        # Validate log level
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if self.log_level.upper() not in valid_levels:
            raise ValueError(
                f"log_level must be one of: {', '.join(valid_levels)}"
            )
        
        # Ensure global config dir exists
        self.global_config_dir.mkdir(parents=True, exist_ok=True)
        
        # Ensure log file directory exists
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        
        # If persistence enabled, ensure storage path is set
        if self.persistence_enabled and not self.storage_path:
            self.storage_path = self.global_config_dir / "mcp_sessions"
        
        # Create storage directory if needed
        if self.storage_path:
            self.storage_path.mkdir(parents=True, exist_ok=True)
        
        logger.debug("Configuration validated successfully")


def load_config(
    config_file: Optional[Path] = None,
    use_env: bool = True
) -> ServerConfig:
    """
    Load configuration from file and/or environment.
    
    Priority order:
    1. Config file (if provided)
    2. Environment variables (if use_env=True)
    3. Defaults
    
    Args:
        config_file: Optional path to configuration file
        use_env: Whether to load from environment variables
        
    Returns:
        Loaded and validated ServerConfig
    """
    if config_file and config_file.exists():
        config = ServerConfig.from_file(config_file)
    elif use_env:
        config = ServerConfig.from_env()
    else:
        config = ServerConfig.get_default()
    
    config.validate()
    return config