"""
Main REPL class for PyREPL.

This module provides the REPL class which integrates all components
(context, history, completion, input handling, output formatting)
into a fully functional Python REPL with advanced features.
"""

import os
import sys
import signal
import traceback
from pathlib import Path
from typing import Any, Optional

from prompt_toolkit import PromptSession
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.history import FileHistory
from prompt_toolkit.lexers import PygmentsLexer
from prompt_toolkit.styles import Style
from pygments.lexers.python import PythonLexer

from .context import ExecutionContext
from .history import HistoryManager
from .completion import CompletionEngine
from .output import OutputFormatter
from .config import Config, get_config


class REPL:
    """
    Main Read-Eval-Print Loop class for PyREPL.
    
    Integrates all subsystems to provide a powerful, user-friendly
    Python REPL with advanced features like:
    - Intelligent code completion
    - Persistent history with search
    - Syntax highlighting
    - Multi-line editing
    - Special commands (!help, !vars, !save, etc.)
    - Graceful error handling
    - Signal handling (Ctrl+C, Ctrl+D)
    """
    
    # Version information
    VERSION = "1.0.0"
    PYTHON_VERSION = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    
    # Special commands that the REPL handles
    SPECIAL_COMMANDS = {
        '!help': 'Show help information',
        '!vars': 'List all variables in the current context',
        '!save': 'Save current session state (!save <filename>)',
        '!load': 'Load session state from file (!load <filename>)',
        '!clear': 'Clear the namespace (reset variables)',
        '!history': 'Show command history',
        '!exit': 'Exit the REPL',
        '!quit': 'Exit the REPL',
    }
    
    def __init__(self, config: Optional[Config] = None):
        """
        Initialize the REPL with all subsystems.
        
        Args:
            config: Optional configuration object. If None, loads default config.
        """
        # Load configuration
        self.config = config or get_config()
        
        # Initialize output formatter (used for all output)
        self.output = OutputFormatter(
            theme=self.config.appearance.theme,
            force_terminal=True
        )
        
        # Initialize execution context
        self.context = ExecutionContext()
        
        # Initialize history manager
        history_db = Path.home() / ".pyrepl" / "history.db"
        self.history = HistoryManager(
            db_path=str(history_db),
            max_history=self.config.history.history_size
        )
        
        # Initialize completion engine
        self.completion = CompletionEngine(context=self.context)
        
        # Initialize prompt session
        self._init_prompt_session()
        
        # REPL state
        self.running = False
        self.buffer = []  # For multi-line input
        self._last_exception: Optional[Exception] = None
        
        # Setup signal handlers
        self._setup_signal_handlers()
    
    def _init_prompt_session(self):
        """Initialize the prompt_toolkit session for input handling."""
        # Create style for prompt
        style = Style.from_dict({
            'prompt': '#00aa00 bold',
            'continuation': '#888888',
        })
        
        # Setup history file for prompt_toolkit (separate from our SQLite history)
        history_file = Path.home() / ".pyrepl" / "prompt_history"
        history_file.parent.mkdir(exist_ok=True)
        
        # Create prompt session
        self.session = PromptSession(
            lexer=PygmentsLexer(PythonLexer) if self.config.appearance.enable_syntax_highlighting else None,
            style=style,
            auto_suggest=AutoSuggestFromHistory() if self.config.behavior.auto_suggest else None,
            enable_history_search=self.config.history.search_history,
            vi_mode=self.config.behavior.vi_mode,
            multiline=False,  # We handle multiline manually
            complete_while_typing=True,
        )
    
    def _setup_signal_handlers(self):
        """Setup signal handlers for Ctrl+C and other signals."""
        # Handle Ctrl+C (SIGINT)
        signal.signal(signal.SIGINT, self._handle_sigint)
        
        # Handle Ctrl+\ (SIGQUIT) on Unix systems
        if hasattr(signal, 'SIGQUIT'):
            signal.signal(signal.SIGQUIT, self._handle_sigquit)
    
    def _handle_sigint(self, signum, frame):
        """Handle SIGINT (Ctrl+C)."""
        # If we're in the middle of input, clear the buffer
        if self.buffer:
            self.output.print_warning("\nKeyboardInterrupt - clearing input buffer")
            self.buffer.clear()
        else:
            self.output.print_warning("\nKeyboardInterrupt")
        
        # Raise KeyboardInterrupt to let the REPL loop handle it
        raise KeyboardInterrupt()
    
    def _handle_sigquit(self, signum, frame):
        """Handle SIGQUIT (Ctrl+\)."""
        self.output.print_warning("\nReceived quit signal")
        self.shutdown()
    
    def display_banner(self):
        """Display the startup banner."""
        banner_lines = [
            f"PyREPL v{self.VERSION}",
            f"Python {self.PYTHON_VERSION}",
            "",
            "Type !help for help, !exit to quit.",
            "Press Ctrl+D or Ctrl+C twice to exit.",
        ]
        
        banner_text = "\n".join(banner_lines)
        self.output.console.print(f"[bold cyan]{banner_text}[/bold cyan]")
        self.output.console.print()
    
    def run(self):
        """
        Main REPL loop.
        
        Continuously reads input, evaluates it, and prints results
        until the user exits or an unrecoverable error occurs.
        """
        self.running = True
        self.display_banner()
        
        consecutive_ctrl_c = 0
        
        while self.running:
            try:
                # Determine prompt based on whether we're in multi-line mode
                if self.buffer:
                    prompt = self.config.appearance.continuation_prompt
                else:
                    prompt = self.config.appearance.prompt_style
                
                # Get input from user
                try:
                    line = self.session.prompt(prompt)
                except KeyboardInterrupt:
                    # Ctrl+C pressed
                    consecutive_ctrl_c += 1
                    if consecutive_ctrl_c >= 2:
                        self.output.print_warning("Double Ctrl+C - exiting")
                        break
                    self.output.print_warning("Press Ctrl+C again to exit")
                    self.buffer.clear()
                    continue
                except EOFError:
                    # Ctrl+D pressed
                    self.output.print_status("\nExiting...")
                    break
                
                # Reset Ctrl+C counter on successful input
                consecutive_ctrl_c = 0
                
                # Add to buffer
                self.buffer.append(line)
                
                # Check if we should execute
                if self._should_execute():
                    # Join buffer and execute
                    code = '\n'.join(self.buffer)
                    self.buffer.clear()
                    
                    # Add to history
                    if code.strip():
                        self.history.add_command(code)
                    
                    # Handle the command
                    self.handle_command(code)
            
            except KeyboardInterrupt:
                # Already handled above, but catch any other occurrences
                self.buffer.clear()
                consecutive_ctrl_c += 1
                if consecutive_ctrl_c >= 2:
                    self.output.print_warning("\nDouble Ctrl+C - exiting")
                    break
                continue
            
            except EOFError:
                # Ctrl+D - exit gracefully
                self.output.print_status("\nExiting...")
                break
            
            except Exception as e:
                # Unexpected error in REPL loop itself
                self.output.print_error(f"REPL error: {e}")
                self.output.console.print(traceback.format_exc())
                self.buffer.clear()
        
        # Cleanup
        self.shutdown()
    
    def _should_execute(self) -> bool:
        """
        Determine if the current buffer should be executed.
        
        Returns:
            True if the code should be executed, False if more input is needed.
        """
        if not self.buffer:
            return False
        
        code = '\n'.join(self.buffer)
        
        # Empty or whitespace-only input
        if not code.strip():
            return True
        
        # Check if it's a special command
        if code.strip().startswith('!'):
            return True
        
        # Try to compile the code
        try:
            compile(code, '<stdin>', 'exec')
            return True
        except SyntaxError as e:
            # Check if it's incomplete (expecting more input)
            if 'unexpected EOF' in str(e) or 'incomplete' in str(e).lower():
                return False
            # Real syntax error - execute to show the error
            return True
        except:
            # Other compilation errors - execute to show them
            return True
    
    def handle_command(self, cmd: str) -> Optional[Any]:
        """
        Handle a command (either special command or Python code).
        
        Args:
            cmd: The command string to execute
            
        Returns:
            The result of execution, or None
        """
        cmd = cmd.strip()
        
        if not cmd:
            return None
        
        # Check if it's a special command
        if cmd.startswith('!'):
            return self.execute_special_command(cmd)
        
        # Execute Python code
        try:
            result = self.context.execute_code(cmd)
            
            # Display result if not None
            if result is not None:
                formatted = self.output.format_result(result)
                self.output.console.print(formatted)
            
            return result
        
        except Exception as e:
            # Store exception for potential inspection
            self._last_exception = e
            
            # Format and display the exception
            formatted_exception = self.output.format_exception(e)
            self.output.console.print(formatted_exception)
            
            return None
    
    def execute_special_command(self, cmd: str) -> bool:
        """
        Execute a special REPL command.
        
        Args:
            cmd: The special command (starts with !)
            
        Returns:
            True if command was handled, False otherwise
        """
        # Parse command and arguments
        parts = cmd.split(maxsplit=1)
        command = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""
        
        # Help command
        if command == '!help':
            self._cmd_help()
            return True
        
        # List variables
        elif command == '!vars':
            self._cmd_vars()
            return True
        
        # Save state
        elif command == '!save':
            self._cmd_save(args)
            return True
        
        # Load state
        elif command == '!load':
            self._cmd_load(args)
            return True
        
        # Clear namespace
        elif command == '!clear':
            self._cmd_clear()
            return True
        
        # Show history
        elif command == '!history':
            self._cmd_history()
            return True
        
        # Exit commands
        elif command in ('!exit', '!quit'):
            self.running = False
            return True
        
        # Unknown command
        else:
            self.output.print_error(f"Unknown command: {command}")
            self.output.print_status("Type !help for available commands")
            return False
    
    def _cmd_help(self):
        """Display help information."""
        from rich.table import Table
        
        table = Table(title="PyREPL Special Commands", show_header=True, header_style="bold cyan")
        table.add_column("Command", style="green", width=20)
        table.add_column("Description", style="white")
        
        for cmd, desc in self.SPECIAL_COMMANDS.items():
            table.add_row(cmd, desc)
        
        self.output.console.print()
        self.output.console.print(table)
        self.output.console.print()
        self.output.console.print("[bold]Tips:[/bold]")
        self.output.console.print("  • Use arrow keys to navigate history")
        self.output.console.print("  • Press Tab for code completion")
        self.output.console.print("  • Multi-line input: end with blank line or proper indentation")
        self.output.console.print("  • Ctrl+C clears input, Ctrl+D exits")
        self.output.console.print()
    
    def _cmd_vars(self):
        """List all variables in the current context."""
        variables = self.context.list_variables()
        
        if not variables:
            self.output.print_status("No variables defined")
            return
        
        from rich.table import Table
        
        table = Table(title="Variables", show_header=True, header_style="bold cyan")
        table.add_column("Name", style="green", width=20)
        table.add_column("Type", style="yellow", width=15)
        table.add_column("Value", style="white")
        
        for name, value in sorted(variables.items()):
            type_name = type(value).__name__
            value_repr = repr(value)
            # Truncate long values
            if len(value_repr) > 60:
                value_repr = value_repr[:57] + "..."
            
            table.add_row(name, type_name, value_repr)
        
        self.output.console.print()
        self.output.console.print(table)
        self.output.console.print()
        self.output.print_status(f"Total: {len(variables)} variable(s)")
    
    def _cmd_save(self, filename: str):
        """Save the current session state."""
        if not filename:
            self.output.print_error("Usage: !save <filename>")
            return
        
        try:
            # Expand user path
            filepath = Path(filename).expanduser()
            
            # Save context state
            self.context.save_state(str(filepath))
            
            self.output.print_success(f"Session saved to: {filepath}")
        
        except Exception as e:
            self.output.print_error(f"Failed to save session: {e}")
    
    def _cmd_load(self, filename: str):
        """Load session state from a file."""
        if not filename:
            self.output.print_error("Usage: !load <filename>")
            return
        
        try:
            # Expand user path
            filepath = Path(filename).expanduser()
            
            # Check if file exists
            if not filepath.exists():
                self.output.print_error(f"File not found: {filepath}")
                return
            
            # Load context state
            self.context.load_state(str(filepath))
            
            self.output.print_success(f"Session loaded from: {filepath}")
            
            # Show loaded variables
            variables = self.context.list_variables()
            self.output.print_status(f"Loaded {len(variables)} variable(s)")
        
        except Exception as e:
            self.output.print_error(f"Failed to load session: {e}")
    
    def _cmd_clear(self):
        """Clear the namespace (reset all variables)."""
        # Confirm if configured
        if self.config.behavior.confirm_exit:
            try:
                response = self.session.prompt("Clear all variables? [y/N]: ")
                if response.lower() not in ('y', 'yes'):
                    self.output.print_status("Clear cancelled")
                    return
            except (KeyboardInterrupt, EOFError):
                self.output.print_status("\nClear cancelled")
                return
        
        # Get variable count before clearing
        var_count = len(self.context.list_variables())
        
        # Clear namespace
        self.context.clear_namespace(keep_builtins=True)
        
        self.output.print_success(f"Namespace cleared ({var_count} variable(s) removed)")
    
    def _cmd_history(self):
        """Show command history."""
        history = self.history.get_history(limit=50, session_only=False)
        
        if not history:
            self.output.print_status("No history available")
            return
        
        from rich.syntax import Syntax
        from rich.panel import Panel
        
        # Format history with line numbers
        history_text = []
        for i, cmd in enumerate(history[-50:], 1):  # Show last 50
            history_text.append(f"{i:3d}  {cmd}")
        
        history_str = "\n".join(history_text)
        
        # Display with syntax highlighting
        syntax = Syntax(history_str, "python", theme=self.config.appearance.theme, line_numbers=False)
        self.output.console.print()
        self.output.console.print(Panel(syntax, title="[bold cyan]Command History (last 50)[/bold cyan]", border_style="cyan"))
        self.output.console.print()
    
    def shutdown(self):
        """
        Gracefully shutdown the REPL.
        
        Performs cleanup operations like saving history,
        closing connections, etc.
        """
        if not self.running:
            return
        
        self.running = False
        
        # Display goodbye message
        self.output.console.print()
        self.output.console.print("[bold cyan]Goodbye![/bold cyan]")
        
        # Compact history database
        try:
            self.history.compact_database()
        except:
            pass
    
    def get_last_exception(self) -> Optional[Exception]:
        """
        Get the last exception that occurred.
        
        Returns:
            The last exception, or None if no exception occurred.
        """
        return self._last_exception


def main():
    """
    Main entry point for the PyREPL application.
    
    Creates a REPL instance and starts the main loop.
    """
    try:
        repl = REPL()
        repl.run()
    except Exception as e:
        print(f"Fatal error: {e}", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
