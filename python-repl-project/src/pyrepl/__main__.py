#!/usr/bin/env python3
"""
PyREPL CLI Entry Point

Command-line interface for the PyREPL application.
Provides multiple execution modes and configuration options.

Usage:
    python -m pyrepl                      # Interactive REPL mode
    python -m pyrepl script.py            # Execute a Python script
    python -m pyrepl -c "print('Hello')"  # Execute code and exit
    python -m pyrepl --config config.toml # Use custom config file
    python -m pyrepl --version            # Show version information
"""

import argparse
import sys
import os
import traceback
from pathlib import Path
from typing import Optional, NoReturn

from . import __version__, get_info
from .config import Config, get_config
from .repl import REPL
from .context import ExecutionContext
from .output import OutputFormatter


def create_parser() -> argparse.ArgumentParser:
    """
    Create and configure the argument parser.

    Returns:
        argparse.ArgumentParser: Configured argument parser
    """
    parser = argparse.ArgumentParser(
        prog="pyrepl",
        description="PyREPL - A Modern Python REPL with advanced features",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  pyrepl                          Start interactive REPL
  pyrepl script.py                Execute a Python script file
  pyrepl -c "print('Hello')"      Execute code and exit
  pyrepl --config myconfig.toml   Use custom configuration
  pyrepl --no-history             Disable command history
  pyrepl --version                Show version information

Special Commands (in interactive mode):
  !help      Show help information
  !vars      List all variables
  !save      Save session state
  !load      Load session state
  !clear     Clear namespace
  !history   Show command history
  !exit      Exit the REPL

For more information, visit: https://github.com/yourusername/pyrepl
        """,
    )

    # Version information
    parser.add_argument(
        "--version",
        action="version",
        version=f"PyREPL v{__version__}",
        help="Show version information and exit",
    )

    # Configuration options
    parser.add_argument(
        "--config",
        type=str,
        metavar="FILE",
        help="Path to configuration file (default: ~/.pyrepl/config.toml)",
    )

    # History options
    parser.add_argument(
        "--no-history",
        action="store_true",
        help="Disable command history for this session",
    )

    parser.add_argument(
        "--history-file",
        type=str,
        metavar="FILE",
        help="Use a specific history file",
    )

    # Execution modes
    parser.add_argument(
        "-c",
        "--execute",
        "--command",
        type=str,
        metavar="CODE",
        dest="execute",
        help="Execute Python code and exit",
    )

    parser.add_argument(
        "script",
        nargs="?",
        type=str,
        help="Python script file to execute",
    )

    parser.add_argument(
        "args",
        nargs="*",
        help="Arguments to pass to the script (available as sys.argv)",
    )

    # Display options
    parser.add_argument(
        "--no-banner",
        action="store_true",
        help="Don't display the startup banner",
    )

    parser.add_argument(
        "--theme",
        type=str,
        metavar="THEME",
        help="Syntax highlighting theme (e.g., monokai, solarized-dark)",
    )

    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable colored output",
    )

    # Behavior options
    parser.add_argument(
        "--vi-mode",
        action="store_true",
        help="Enable Vi-style key bindings",
    )

    parser.add_argument(
        "--no-auto-suggest",
        action="store_true",
        help="Disable automatic suggestions from history",
    )

    # Debug options
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode with verbose output",
    )

    parser.add_argument(
        "-i",
        "--interactive",
        action="store_true",
        help="Enter interactive mode after executing script or command",
    )

    return parser


def load_configuration(args: argparse.Namespace) -> Config:
    """
    Load and configure the Config object based on command-line arguments.

    Args:
        args: Parsed command-line arguments

    Returns:
        Config: Configured Config instance

    Raises:
        ValueError: If configuration file is invalid
        FileNotFoundError: If specified config file doesn't exist
    """
    # Load base configuration
    config_path = None
    if args.config:
        config_path = Path(args.config).expanduser()
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

    config = get_config(config_path)

    # Apply command-line overrides
    if args.no_history:
        config.history.save_history = False

    if args.history_file:
        config.history.history_file = Path(args.history_file).expanduser()

    if args.theme:
        config.appearance.theme = args.theme

    if args.no_color:
        config.appearance.enable_syntax_highlighting = False

    if args.vi_mode:
        config.behavior.vi_mode = True

    if args.no_auto_suggest:
        config.behavior.auto_suggest = False

    return config


def execute_code(code: str, config: Config, interactive: bool = False) -> int:
    """
    Execute Python code and optionally enter interactive mode.

    Args:
        code: Python code string to execute
        config: Configuration object
        interactive: Whether to enter interactive mode after execution

    Returns:
        int: Exit status code (0 for success, 1 for error)
    """
    # Create execution context
    context = ExecutionContext()
    output = OutputFormatter(theme=config.appearance.theme)

    exit_code = 0

    try:
        # Execute the code
        result = context.execute_code(code)

        # Print result if it's not None
        if result is not None:
            formatted = output.format_result(result)
            output.console.print(formatted)

    except Exception as e:
        # Display error
        formatted_exception = output.format_exception(e)
        output.console.print(formatted_exception)
        exit_code = 1

    # Enter interactive mode if requested
    if interactive and exit_code == 0:
        try:
            repl = REPL(config=config)
            # Update REPL context with executed code context
            repl.context._globals.update(context._globals)
            repl.context._locals.update(context._locals)
            repl.run()
        except Exception as e:
            print(f"Error starting interactive mode: {e}", file=sys.stderr)
            if config.behavior.auto_suggest:  # Using as proxy for debug mode
                traceback.print_exc()
            exit_code = 1

    return exit_code


def execute_script(script_path: str, script_args: list, config: Config, interactive: bool = False) -> int:
    """
    Execute a Python script file.

    Args:
        script_path: Path to the Python script file
        script_args: Arguments to pass to the script
        config: Configuration object
        interactive: Whether to enter interactive mode after execution

    Returns:
        int: Exit status code (0 for success, 1 for error)
    """
    # Resolve script path
    path = Path(script_path).expanduser().resolve()

    if not path.exists():
        print(f"Error: Script file not found: {script_path}", file=sys.stderr)
        return 1

    if not path.is_file():
        print(f"Error: Not a file: {script_path}", file=sys.stderr)
        return 1

    # Read script content
    try:
        with open(path, "r", encoding="utf-8") as f:
            code = f.read()
    except Exception as e:
        print(f"Error reading script file: {e}", file=sys.stderr)
        return 1

    # Setup sys.argv for the script
    old_argv = sys.argv
    sys.argv = [str(path)] + script_args

    # Add script directory to sys.path
    script_dir = str(path.parent)
    old_path = sys.path.copy()
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)

    try:
        # Create execution context
        context = ExecutionContext(initial_globals={
            "__file__": str(path),
            "__name__": "__main__",
        })
        
        output = OutputFormatter(theme=config.appearance.theme)
        exit_code = 0

        try:
            # Execute the script
            context.execute_code(code)

        except SystemExit as e:
            # Handle sys.exit() calls in the script
            exit_code = e.code if isinstance(e.code, int) else 1

        except Exception as e:
            # Display error
            formatted_exception = output.format_exception(e)
            output.console.print(formatted_exception)
            exit_code = 1

        # Enter interactive mode if requested and no error occurred
        if interactive and exit_code == 0:
            try:
                repl = REPL(config=config)
                # Update REPL context with script context
                repl.context._globals.update(context._globals)
                repl.context._locals.update(context._locals)
                repl.run()
            except Exception as e:
                print(f"Error starting interactive mode: {e}", file=sys.stderr)
                traceback.print_exc()
                exit_code = 1

        return exit_code

    finally:
        # Restore sys.argv and sys.path
        sys.argv = old_argv
        sys.path = old_path


def run_interactive(config: Config, show_banner: bool = True) -> int:
    """
    Run the interactive REPL.

    Args:
        config: Configuration object
        show_banner: Whether to display the startup banner

    Returns:
        int: Exit status code (0 for success, 1 for error)
    """
    try:
        repl = REPL(config=config)
        
        # Optionally suppress banner
        if not show_banner:
            original_display_banner = repl.display_banner
            repl.display_banner = lambda: None
        
        repl.run()
        return 0

    except KeyboardInterrupt:
        print("\nInterrupted by user", file=sys.stderr)
        return 130  # Standard exit code for SIGINT

    except Exception as e:
        print(f"Fatal error: {e}", file=sys.stderr)
        traceback.print_exc()
        return 1


def main(argv: Optional[list] = None) -> int:
    """
    Main entry point for the PyREPL CLI.

    Args:
        argv: Optional command-line arguments (uses sys.argv if None)

    Returns:
        int: Exit status code
    """
    # Parse command-line arguments
    parser = create_parser()
    args = parser.parse_args(argv)

    # Enable debug output if requested
    if args.debug:
        print(f"PyREPL v{__version__}", file=sys.stderr)
        print(f"Python {sys.version}", file=sys.stderr)
        print(f"Arguments: {args}", file=sys.stderr)
        print("", file=sys.stderr)

    try:
        # Load configuration
        config = load_configuration(args)

        # Determine execution mode and run
        if args.execute:
            # Execute code from command line
            return execute_code(args.execute, config, interactive=args.interactive)

        elif args.script:
            # Execute script file
            return execute_script(args.script, args.args, config, interactive=args.interactive)

        else:
            # Interactive REPL mode
            return run_interactive(config, show_banner=not args.no_banner)

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    except ValueError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        return 1

    except KeyboardInterrupt:
        print("\nInterrupted by user", file=sys.stderr)
        return 130

    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        if args.debug:
            traceback.print_exc()
        return 1


def cli_entry_point() -> NoReturn:
    """
    Entry point for console_scripts in setup.py/pyproject.toml.
    
    This function calls main() and exits with the returned status code.
    """
    sys.exit(main())


if __name__ == "__main__":
    sys.exit(main())
