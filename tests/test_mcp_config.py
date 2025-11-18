"""
Unit tests for MCP server configuration management.

Tests configuration loading from files, environment variables, and defaults.
"""

import json
import os
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch
from roo_code.mcp.config import ServerConfig, load_config


class TestServerConfig:
    """Test ServerConfig class."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = ServerConfig()
        
        assert config.server_name == "roo-modes-server"
        assert config.server_version == "1.0.0"
        assert config.session_timeout == 3600
        assert config.cleanup_interval == 300
        assert config.log_level == "INFO"
        assert config.persistence_enabled is False
        assert config.project_root is None
    
    def test_custom_config(self):
        """Test creating config with custom values."""
        custom_root = Path("/custom/path")
        
        config = ServerConfig(
            server_name="custom-server",
            server_version="2.0.0",
            project_root=custom_root,
            session_timeout=7200,
            log_level="DEBUG"
        )
        
        assert config.server_name == "custom-server"
        assert config.server_version == "2.0.0"
        assert config.project_root == custom_root
        assert config.session_timeout == 7200
        assert config.log_level == "DEBUG"
    
    def test_from_file_minimal(self):
        """Test loading minimal configuration from file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({}, f)
            config_path = Path(f.name)
        
        try:
            config = ServerConfig.from_file(config_path)
            
            # Should use defaults
            assert config.server_name == "roo-modes-server"
            assert config.session_timeout == 3600
        finally:
            config_path.unlink()
    
    def test_from_file_server_info(self):
        """Test loading server info from file."""
        config_data = {
            "server": {
                "name": "custom-server",
                "version": "3.0.0",
                "description": "Custom description"
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            config_path = Path(f.name)
        
        try:
            config = ServerConfig.from_file(config_path)
            
            assert config.server_name == "custom-server"
            assert config.server_version == "3.0.0"
            assert config.server_description == "Custom description"
        finally:
            config_path.unlink()
    
    def test_from_file_paths(self):
        """Test loading path configuration from file."""
        config_data = {
            "paths": {
                "project_root": "/tmp/project",
                "global_config_dir": "/tmp/config"
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            config_path = Path(f.name)
        
        try:
            config = ServerConfig.from_file(config_path)
            
            assert config.project_root == Path("/tmp/project")
            assert config.global_config_dir == Path("/tmp/config")
        finally:
            config_path.unlink()
    
    def test_from_file_paths_with_tilde(self):
        """Test loading paths with tilde expansion."""
        config_data = {
            "paths": {
                "project_root": "~/my_project"
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            config_path = Path(f.name)
        
        try:
            config = ServerConfig.from_file(config_path)
            
            # Should expand tilde
            assert config.project_root == Path.home() / "my_project"
        finally:
            config_path.unlink()
    
    def test_from_file_sessions(self):
        """Test loading session configuration from file."""
        config_data = {
            "sessions": {
                "timeout": 1800,
                "cleanup_interval": 600
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            config_path = Path(f.name)
        
        try:
            config = ServerConfig.from_file(config_path)
            
            assert config.session_timeout == 1800
            assert config.cleanup_interval == 600
        finally:
            config_path.unlink()
    
    def test_from_file_persistence(self):
        """Test loading persistence configuration from file."""
        config_data = {
            "sessions": {
                "persistence": {
                    "enabled": True,
                    "storage_path": "/tmp/sessions"
                }
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            config_path = Path(f.name)
        
        try:
            config = ServerConfig.from_file(config_path)
            
            assert config.persistence_enabled is True
            assert config.storage_path == Path("/tmp/sessions")
        finally:
            config_path.unlink()
    
    def test_from_file_logging(self):
        """Test loading logging configuration from file."""
        config_data = {
            "logging": {
                "level": "DEBUG",
                "file": "/tmp/server.log",
                "format": "%(levelname)s: %(message)s"
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            config_path = Path(f.name)
        
        try:
            config = ServerConfig.from_file(config_path)
            
            assert config.log_level == "DEBUG"
            assert config.log_file == Path("/tmp/server.log")
            assert config.log_format == "%(levelname)s: %(message)s"
        finally:
            config_path.unlink()
    
    def test_from_file_missing(self):
        """Test loading from non-existent file fails."""
        with pytest.raises(FileNotFoundError):
            ServerConfig.from_file(Path("/nonexistent/config.json"))
    
    def test_from_file_invalid_json(self):
        """Test loading invalid JSON fails."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("{invalid json}")
            config_path = Path(f.name)
        
        try:
            with pytest.raises(json.JSONDecodeError):
                ServerConfig.from_file(config_path)
        finally:
            config_path.unlink()
    
    def test_from_env_minimal(self):
        """Test loading from environment with no vars set."""
        config = ServerConfig.from_env()
        
        # Should use defaults
        assert config.server_name == "roo-modes-server"
        assert config.session_timeout == 3600
    
    def test_from_env_project_root(self):
        """Test loading project root from environment."""
        with patch.dict(os.environ, {"ROO_PROJECT_ROOT": "/tmp/project"}):
            config = ServerConfig.from_env()
            
            assert config.project_root == Path("/tmp/project")
    
    def test_from_env_config_dir(self):
        """Test loading config dir from environment."""
        with patch.dict(os.environ, {"ROO_CONFIG_DIR": "/tmp/config"}):
            config = ServerConfig.from_env()
            
            assert config.global_config_dir == Path("/tmp/config")
    
    def test_from_env_session_timeout(self):
        """Test loading session timeout from environment."""
        with patch.dict(os.environ, {"ROO_SESSION_TIMEOUT": "7200"}):
            config = ServerConfig.from_env()
            
            assert config.session_timeout == 7200
    
    def test_from_env_session_timeout_invalid(self):
        """Test invalid session timeout uses default."""
        with patch.dict(os.environ, {"ROO_SESSION_TIMEOUT": "invalid"}):
            config = ServerConfig.from_env()
            
            # Should use default
            assert config.session_timeout == 3600
    
    def test_from_env_log_level(self):
        """Test loading log level from environment."""
        with patch.dict(os.environ, {"ROO_LOG_LEVEL": "DEBUG"}):
            config = ServerConfig.from_env()
            
            assert config.log_level == "DEBUG"
    
    def test_from_env_log_file(self):
        """Test loading log file from environment."""
        with patch.dict(os.environ, {"ROO_LOG_FILE": "/tmp/custom.log"}):
            config = ServerConfig.from_env()
            
            assert config.log_file == Path("/tmp/custom.log")
    
    def test_from_env_multiple_vars(self):
        """Test loading multiple environment variables."""
        env_vars = {
            "ROO_PROJECT_ROOT": "/tmp/project",
            "ROO_SESSION_TIMEOUT": "1800",
            "ROO_LOG_LEVEL": "WARNING"
        }
        
        with patch.dict(os.environ, env_vars):
            config = ServerConfig.from_env()
            
            assert config.project_root == Path("/tmp/project")
            assert config.session_timeout == 1800
            assert config.log_level == "WARNING"
    
    def test_get_default(self):
        """Test getting default configuration."""
        config = ServerConfig.get_default()
        
        assert isinstance(config, ServerConfig)
        assert config.server_name == "roo-modes-server"
        assert config.session_timeout == 3600
    
    def test_to_dict(self):
        """Test converting config to dictionary."""
        config = ServerConfig(
            server_name="test-server",
            project_root=Path("/tmp/project"),
            session_timeout=1800
        )
        
        config_dict = config.to_dict()
        
        assert config_dict["server"]["name"] == "test-server"
        assert config_dict["paths"]["project_root"] == "/tmp/project"
        assert config_dict["sessions"]["timeout"] == 1800
    
    def test_to_dict_with_none_values(self):
        """Test to_dict with None values."""
        config = ServerConfig(project_root=None, storage_path=None)
        
        config_dict = config.to_dict()
        
        assert config_dict["paths"]["project_root"] is None
        assert config_dict["sessions"]["persistence"]["storage_path"] is None
    
    def test_save_to_file(self):
        """Test saving configuration to file."""
        config = ServerConfig(
            server_name="test-server",
            session_timeout=1800
        )
        
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            config.save_to_file(config_path)
            
            # Verify file exists and contains correct data
            assert config_path.exists()
            
            with open(config_path) as f:
                data = json.load(f)
            
            assert data["server"]["name"] == "test-server"
            assert data["sessions"]["timeout"] == 1800
    
    def test_save_to_file_creates_directory(self):
        """Test save creates parent directories."""
        config = ServerConfig()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "subdir" / "config.json"
            
            # Parent doesn't exist yet
            assert not config_path.parent.exists()
            
            config.save_to_file(config_path)
            
            # Should create parent and file
            assert config_path.exists()
            assert config_path.parent.exists()
    
    def test_validate_valid_config(self):
        """Test validating a valid configuration."""
        config = ServerConfig()
        
        # Should not raise
        config.validate()
    
    def test_validate_negative_timeout(self):
        """Test validation fails on negative timeout."""
        config = ServerConfig(session_timeout=-1)
        
        with pytest.raises(ValueError) as exc_info:
            config.validate()
        
        assert "positive" in str(exc_info.value).lower()
    
    def test_validate_zero_timeout(self):
        """Test validation fails on zero timeout."""
        config = ServerConfig(session_timeout=0)
        
        with pytest.raises(ValueError):
            config.validate()
    
    def test_validate_negative_cleanup_interval(self):
        """Test validation fails on negative cleanup interval."""
        config = ServerConfig(cleanup_interval=-1)
        
        with pytest.raises(ValueError):
            config.validate()
    
    def test_validate_invalid_log_level(self):
        """Test validation fails on invalid log level."""
        config = ServerConfig(log_level="INVALID")
        
        with pytest.raises(ValueError) as exc_info:
            config.validate()
        
        assert "log_level" in str(exc_info.value).lower()
    
    def test_validate_log_level_case_insensitive(self):
        """Test log level validation is case insensitive."""
        config = ServerConfig(log_level="debug")
        
        # Should not raise - uppercase check
        config.validate()
    
    def test_validate_creates_directories(self):
        """Test validation creates necessary directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "config"
            log_dir = Path(tmpdir) / "logs"
            
            config = ServerConfig(
                global_config_dir=config_dir,
                log_file=log_dir / "server.log"
            )
            
            # Directories don't exist yet
            assert not config_dir.exists()
            assert not log_dir.exists()
            
            config.validate()
            
            # Should create directories
            assert config_dir.exists()
            assert log_dir.exists()
    
    def test_validate_enables_persistence_storage(self):
        """Test validation sets storage path when persistence enabled."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "config"
            
            config = ServerConfig(
                global_config_dir=config_dir,
                persistence_enabled=True,
                storage_path=None
            )
            
            config.validate()
            
            # Should set storage path
            assert config.storage_path is not None
            assert config.storage_path == config_dir / "mcp_sessions"
            assert config.storage_path.exists()


class TestLoadConfig:
    """Test load_config function."""
    
    def test_load_config_from_file(self):
        """Test loading config from file."""
        config_data = {
            "server": {"name": "file-server"},
            "sessions": {"timeout": 1800}
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            config_path = Path(f.name)
        
        try:
            config = load_config(config_file=config_path, use_env=False)
            
            assert config.server_name == "file-server"
            assert config.session_timeout == 1800
        finally:
            config_path.unlink()
    
    def test_load_config_from_env(self):
        """Test loading config from environment."""
        env_vars = {
            "ROO_PROJECT_ROOT": "/tmp/project",
            "ROO_SESSION_TIMEOUT": "7200"
        }
        
        with patch.dict(os.environ, env_vars):
            config = load_config(config_file=None, use_env=True)
            
            assert config.project_root == Path("/tmp/project")
            assert config.session_timeout == 7200
    
    def test_load_config_defaults(self):
        """Test loading default config."""
        config = load_config(config_file=None, use_env=False)
        
        assert config.server_name == "roo-modes-server"
        assert config.session_timeout == 3600
    
    def test_load_config_file_takes_precedence(self):
        """Test config file takes precedence over environment."""
        config_data = {
            "sessions": {"timeout": 1800}
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            config_path = Path(f.name)
        
        try:
            env_vars = {"ROO_SESSION_TIMEOUT": "7200"}
            
            with patch.dict(os.environ, env_vars):
                config = load_config(config_file=config_path, use_env=True)
                
                # File value should win
                assert config.session_timeout == 1800
        finally:
            config_path.unlink()
    
    def test_load_config_nonexistent_file_uses_env(self):
        """Test nonexistent file falls back to environment."""
        env_vars = {"ROO_SESSION_TIMEOUT": "7200"}
        
        with patch.dict(os.environ, env_vars):
            config = load_config(
                config_file=Path("/nonexistent.json"),
                use_env=True
            )
            
            # Should use environment
            assert config.session_timeout == 7200
    
    def test_load_config_validates(self):
        """Test load_config validates the configuration."""
        config_data = {
            "sessions": {"timeout": -1}  # Invalid
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            config_path = Path(f.name)
        
        try:
            with pytest.raises(ValueError):
                load_config(config_file=config_path, use_env=False)
        finally:
            config_path.unlink()