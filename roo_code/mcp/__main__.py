"""
CLI entry point for MCP Modes Server.

This module provides the command-line interface for running the MCP Modes Server.
It can be invoked as: python -m roo_code.mcp
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from .config import load_config
from .server import McpModesServer


def setup_logging(config) -> None:
    """
    Setup logging configuration.
    
    Args:
        config: Server configuration
    """
    # Ensure log directory exists
    config.log_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, config.log_level.upper()),
        format=config.log_format,
        handlers=[
            logging.FileHandler(config.log_file),
            logging.StreamHandler(sys.stderr)  # Log to stderr, not stdout (used for JSON-RPC)
        ]
    )
    
    # Set specific logger levels
    logger = logging.getLogger("roo_code.mcp")
    logger.setLevel(getattr(logging, config.log_level.upper()))


def parse_arguments() -> argparse.Namespace:
    """
    Parse command-line arguments.
    
    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description="MCP Modes Server - Expose Roo-Code mode system via MCP protocol",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with project root
  python -m roo_code.mcp --project-root /path/to/project

  # Run with custom configuration
  python -m roo_code.mcp --config /path/to/config.json

  # Run with increased logging
  python -m roo_code.mcp --log-level DEBUG

Environment Variables:
  ROO_PROJECT_ROOT     Project root directory
  ROO_CONFIG_DIR       Global config directory (default: ~/.roo-code)
  ROO_SESSION_TIMEOUT  Session timeout in seconds
  ROO_LOG_LEVEL        Logging level (DEBUG, INFO, WARNING, ERROR)
  ROO_LOG_FILE         Log file path
        """
    )
    
    parser.add_argument(
        "--config",
        type=Path,
        help="Path to configuration file (JSON)"
    )
    
    parser.add_argument(
        "--project-root",
        type=Path,
        help="Project root directory"
    )
    
    parser.add_argument(
        "--global-config-dir",
        type=Path,
        help="Global configuration directory (default: ~/.roo-code)"
    )
    
    parser.add_argument(
        "--session-timeout",
        type=int,
        help="Session timeout in seconds (default: 3600)"
    )
    
    parser.add_argument(
        "--cleanup-interval",
        type=int,
        help="Session cleanup interval in seconds (default: 300)"
    )
    
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging level (default: INFO)"
    )
    
    parser.add_argument(
        "--log-file",
        type=Path,
        help="Log file path (default: ~/.roo-code/mcp_modes_server.log)"
    )
    
    parser.add_argument(
        "--version",
        action="version",
        version="MCP Modes Server 1.0.0"
    )
    
    return parser.parse_args()


async def main() -> int:
    """
    Main entry point for MCP Modes Server.
    
    Returns:
        Exit code (0 for success, 1 for error)
    """
    # Parse arguments
    args = parse_arguments()
    
    # Load configuration
    try:
        if args.config and args.config.exists():
            config = load_config(config_file=args.config, use_env=True)
        else:
            config = load_config(use_env=True)
    except Exception as e:
        print(f"Error loading configuration: {e}", file=sys.stderr)
        return 1
    
    # Override with command line arguments
    if args.project_root:
        config.project_root = args.project_root.resolve()
    
    if args.global_config_dir:
        config.global_config_dir = args.global_config_dir.resolve()
    
    if args.session_timeout:
        config.session_timeout = args.session_timeout
    
    if args.cleanup_interval:
        config.cleanup_interval = args.cleanup_interval
    
    if args.log_level:
        config.log_level = args.log_level
    
    if args.log_file:
        config.log_file = args.log_file.resolve()
    
    # Validate configuration
    try:
        config.validate()
    except ValueError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        return 1
    
    # Setup logging
    setup_logging(config)
    logger = logging.getLogger(__name__)
    
    logger.info("=" * 60)
    logger.info("MCP Modes Server Starting")
    logger.info("=" * 60)
    logger.info(f"Version: 1.0.0")
    logger.info(f"Project Root: {config.project_root or 'None'}")
    logger.info(f"Global Config: {config.global_config_dir}")
    logger.info(f"Session Timeout: {config.session_timeout}s")
    logger.info(f"Cleanup Interval: {config.cleanup_interval}s")
    logger.info(f"Log Level: {config.log_level}")
    logger.info(f"Log File: {config.log_file}")
    logger.info("=" * 60)
    
    # Create and run server
    try:
        server = McpModesServer(
            project_root=config.project_root,
            global_config_dir=config.global_config_dir,
            session_timeout=config.session_timeout,
            cleanup_interval=config.cleanup_interval
        )
        
        logger.info("Server initialized successfully")
        
        # Run server
        await server.run()
        
        logger.info("Server exited normally")
        return 0
        
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
        return 0
        
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        return 1


def run() -> None:
    """
    Synchronous wrapper for main async function.
    
    This is the actual entry point called by Python.
    """
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as e:
        print(f"Fatal error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    run()