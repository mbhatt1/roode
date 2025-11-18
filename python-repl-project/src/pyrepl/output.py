"""
Output formatting module for PyREPL.

This module provides the OutputFormatter class which uses the rich library
to create beautiful, syntax-highlighted output for Python objects, exceptions,
tracebacks, and more.
"""

import sys
import traceback as tb_module
import inspect
from typing import Any, Optional, TextIO
from types import TracebackType

from rich.console import Console, Group
from rich.syntax import Syntax
from rich.traceback import Traceback
from rich.table import Table
from rich.tree import Tree
from rich.panel import Panel
from rich.text import Text
from rich.pretty import Pretty
from rich.pager import Pager
from rich.markdown import Markdown


class OutputFormatter:
    """
    Formatter for REPL output using the rich library.
    
    Provides beautiful, syntax-highlighted output for Python objects,
    exceptions, tracebacks, and more.
    """
    
    def __init__(
        self,
        file: Optional[TextIO] = None,
        force_terminal: Optional[bool] = None,
        width: Optional[int] = None,
        theme: str = "monokai"
    ):
        """
        Initialize the OutputFormatter.
        
        Args:
            file: Output file (defaults to sys.stdout)
            force_terminal: Force terminal mode even if not detected
            width: Console width (defaults to auto-detect)
            theme: Syntax highlighting theme
        """
        self.console = Console(
            file=file or sys.stdout,
            force_terminal=force_terminal,
            width=width,
            highlight=True,
            markup=True
        )
        self.theme = theme
        self._paging_enabled = True
        self._max_lines_before_paging = 50
    
    def format_result(self, obj: Any) -> str:
        """
        Format a Python object for display.
        
        Handles different types of objects with appropriate formatting:
        - Primitives: Simple repr
        - Collections: Pretty-printed with syntax highlighting
        - Complex objects: Tree or table representation
        - None: Special handling
        
        Args:
            obj: The object to format
            
        Returns:
            Formatted string representation
        """
        if obj is None:
            return ""
        
        # Check if it's a simple type
        if isinstance(obj, (int, float, bool, str)):
            return self._format_simple(obj)
        
        # Check for collections
        if isinstance(obj, (list, tuple, set, frozenset, dict)):
            return self._format_collection(obj)
        
        # Check for custom __repr__ or __str__
        if hasattr(obj, '__rich__') or hasattr(obj, '__rich_repr__'):
            return self._format_rich_object(obj)
        
        # Try pretty printing
        return self._format_pretty(obj)
    
    def _format_simple(self, obj: Any) -> str:
        """Format simple primitive types."""
        if isinstance(obj, str):
            # Show string with quotes and syntax highlighting
            syntax = Syntax(repr(obj), "python", theme=self.theme, line_numbers=False)
            with self.console.capture() as capture:
                self.console.print(syntax)
            return capture.get().rstrip()
        elif isinstance(obj, bool):
            color = "green" if obj else "red"
            return f"[bold {color}]{obj}[/bold {color}]"
        elif isinstance(obj, (int, float)):
            return f"[cyan]{obj}[/cyan]"
        return str(obj)
    
    def _format_collection(self, obj: Any) -> str:
        """Format collections with pretty printing."""
        # Use rich's Pretty for nice formatting
        with self.console.capture() as capture:
            self.console.print(Pretty(obj, expand_all=True, indent_guides=True))
        return capture.get().rstrip()
    
    def _format_rich_object(self, obj: Any) -> str:
        """Format objects that support rich rendering."""
        with self.console.capture() as capture:
            self.console.print(obj)
        return capture.get().rstrip()
    
    def _format_pretty(self, obj: Any) -> str:
        """Format objects using rich's Pretty renderer."""
        with self.console.capture() as capture:
            self.console.print(Pretty(obj, expand_all=False))
        return capture.get().rstrip()
    
    def format_exception(self, exc: Exception) -> str:
        """
        Format an exception with syntax-highlighted traceback.
        
        Args:
            exc: The exception to format
            
        Returns:
            Formatted exception string
        """
        # Get the traceback from the exception
        tb = exc.__traceback__
        
        # Create a rich Traceback
        traceback_obj = Traceback.from_exception(
            type(exc),
            exc,
            tb,
            show_locals=True,
            width=self.console.width,
            theme=self.theme,
            suppress=[sys.modules[__name__]]  # Suppress this module from traceback
        )
        
        with self.console.capture() as capture:
            self.console.print(traceback_obj)
        
        return capture.get().rstrip()
    
    def format_traceback(self, tb: Optional[TracebackType]) -> str:
        """
        Format a traceback object with syntax highlighting.
        
        Args:
            tb: The traceback object to format
            
        Returns:
            Formatted traceback string
        """
        if tb is None:
            return "[dim]No traceback available[/dim]"
        
        # Extract traceback information
        tb_lines = tb_module.format_tb(tb)
        tb_text = "".join(tb_lines)
        
        # Create syntax-highlighted version
        syntax = Syntax(
            tb_text,
            "pytb",
            theme=self.theme,
            line_numbers=True,
            word_wrap=True
        )
        
        with self.console.capture() as capture:
            self.console.print(Panel(syntax, title="[bold red]Traceback[/bold red]", border_style="red"))
        
        return capture.get().rstrip()
    
    def display_help(self, obj: Any) -> None:
        """
        Display help information for an object.
        
        Shows docstrings, signatures, and other helpful information
        in a formatted panel.
        
        Args:
            obj: The object to display help for
        """
        help_text = []
        
        # Object type and module
        obj_type = type(obj).__name__
        module = getattr(obj, "__module__", "unknown")
        help_text.append(f"[bold cyan]Type:[/bold cyan] {obj_type}")
        help_text.append(f"[bold cyan]Module:[/bold cyan] {module}")
        help_text.append("")
        
        # Signature for callables
        if callable(obj):
            try:
                sig = inspect.signature(obj)
                help_text.append(f"[bold green]Signature:[/bold green]")
                syntax = Syntax(f"{obj.__name__}{sig}", "python", theme=self.theme)
                with self.console.capture() as capture:
                    self.console.print(syntax)
                help_text.append(capture.get().rstrip())
                help_text.append("")
            except (ValueError, TypeError):
                pass
        
        # Docstring
        doc = inspect.getdoc(obj)
        if doc:
            help_text.append("[bold yellow]Documentation:[/bold yellow]")
            help_text.append("")
            # Try to render as markdown if it looks like markdown
            if any(marker in doc for marker in ["```", "**", "##", "* "]):
                with self.console.capture() as capture:
                    self.console.print(Markdown(doc))
                help_text.append(capture.get().rstrip())
            else:
                help_text.append(doc)
        else:
            help_text.append("[dim]No documentation available[/dim]")
        
        help_text.append("")
        
        # Attributes and methods (for objects)
        if not inspect.isbuiltin(obj) and not inspect.ismodule(obj):
            members = []
            for name, value in inspect.getmembers(obj):
                if not name.startswith("_"):
                    member_type = type(value).__name__
                    members.append((name, member_type))
            
            if members:
                help_text.append("[bold magenta]Public Members:[/bold magenta]")
                table = Table(show_header=True, header_style="bold", show_lines=False)
                table.add_column("Name", style="cyan")
                table.add_column("Type", style="green")
                
                for name, member_type in members[:20]:  # Limit to first 20
                    table.add_row(name, member_type)
                
                if len(members) > 20:
                    table.add_row("[dim]...[/dim]", f"[dim](+{len(members) - 20} more)[/dim]")
                
                with self.console.capture() as capture:
                    self.console.print(table)
                help_text.append(capture.get().rstrip())
        
        # Display in a panel
        content = "\n".join(help_text)
        title = f"[bold white]Help: {getattr(obj, '__name__', repr(obj)[:50])}[/bold white]"
        
        self.console.print(Panel(content, title=title, border_style="blue", padding=(1, 2)))
    
    def print_with_paging(self, text: str, title: Optional[str] = None) -> None:
        """
        Print text with automatic paging for long output.
        
        If the text exceeds the maximum lines threshold, it will be
        displayed in a pager (like 'less').
        
        Args:
            text: The text to display
            title: Optional title for the output
        """
        lines = text.split("\n")
        
        # Check if we need paging
        if self._paging_enabled and len(lines) > self._max_lines_before_paging:
            # Use rich's pager
            with self.console.pager(styles=True):
                if title:
                    self.console.print(f"[bold]{title}[/bold]")
                    self.console.print("─" * self.console.width)
                self.console.print(text)
        else:
            # Direct print
            if title:
                self.console.print(Panel(text, title=f"[bold]{title}[/bold]", border_style="blue"))
            else:
                self.console.print(text)
    
    def format_table(self, data: list[dict], title: Optional[str] = None) -> str:
        """
        Format data as a table.
        
        Args:
            data: List of dictionaries with consistent keys
            title: Optional table title
            
        Returns:
            Formatted table string
        """
        if not data:
            return "[dim]No data to display[/dim]"
        
        # Create table
        table = Table(title=title, show_header=True, header_style="bold cyan", show_lines=True)
        
        # Add columns from first row
        keys = list(data[0].keys())
        for key in keys:
            table.add_column(str(key), style="green")
        
        # Add rows
        for row in data:
            table.add_row(*[str(row.get(key, "")) for key in keys])
        
        with self.console.capture() as capture:
            self.console.print(table)
        
        return capture.get().rstrip()
    
    def format_tree(self, data: dict, label: str = "Root") -> str:
        """
        Format nested data as a tree structure.
        
        Args:
            data: Dictionary or nested structure to display as tree
            label: Root label for the tree
            
        Returns:
            Formatted tree string
        """
        tree = Tree(f"[bold cyan]{label}[/bold cyan]")
        self._build_tree(tree, data)
        
        with self.console.capture() as capture:
            self.console.print(tree)
        
        return capture.get().rstrip()
    
    def _build_tree(self, tree: Tree, data: Any, max_depth: int = 10, current_depth: int = 0) -> None:
        """Recursively build a tree structure."""
        if current_depth >= max_depth:
            tree.add("[dim]...[/dim]")
            return
        
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, (dict, list)):
                    branch = tree.add(f"[yellow]{key}[/yellow]")
                    self._build_tree(branch, value, max_depth, current_depth + 1)
                else:
                    tree.add(f"[yellow]{key}[/yellow]: [green]{repr(value)}[/green]")
        elif isinstance(data, list):
            for i, item in enumerate(data):
                if isinstance(item, (dict, list)):
                    branch = tree.add(f"[cyan]\\[{i}][/cyan]")
                    self._build_tree(branch, item, max_depth, current_depth + 1)
                else:
                    tree.add(f"[cyan]\\[{i}][/cyan]: [green]{repr(item)}[/green]")
        else:
            tree.add(f"[green]{repr(data)}[/green]")
    
    def print_status(self, message: str, style: str = "bold blue") -> None:
        """
        Print a status message.
        
        Args:
            message: The status message to display
            style: Rich style string
        """
        self.console.print(f"[{style}]{message}[/{style}]")
    
    def print_error(self, message: str) -> None:
        """
        Print an error message.
        
        Args:
            message: The error message to display
        """
        self.console.print(f"[bold red]Error:[/bold red] {message}")
    
    def print_warning(self, message: str) -> None:
        """
        Print a warning message.
        
        Args:
            message: The warning message to display
        """
        self.console.print(f"[bold yellow]Warning:[/bold yellow] {message}")
    
    def print_success(self, message: str) -> None:
        """
        Print a success message.
        
        Args:
            message: The success message to display
        """
        self.console.print(f"[bold green]✓[/bold green] {message}")
    
    def clear_screen(self) -> None:
        """Clear the console screen."""
        self.console.clear()
    
    def print_banner(self, text: str, style: str = "bold white on blue") -> None:
        """
        Print a banner with the given text.
        
        Args:
            text: Banner text
            style: Rich style string
        """
        self.console.print(f"\n[{style}] {text} [/{style}]\n")
    
    def set_paging_enabled(self, enabled: bool) -> None:
        """
        Enable or disable automatic paging.
        
        Args:
            enabled: Whether to enable paging
        """
        self._paging_enabled = enabled
    
    def set_max_lines_before_paging(self, lines: int) -> None:
        """
        Set the threshold for automatic paging.
        
        Args:
            lines: Number of lines before paging is triggered
        """
        self._max_lines_before_paging = max(1, lines)
    
    def print_code(self, code: str, language: str = "python", line_numbers: bool = True) -> None:
        """
        Print syntax-highlighted code.
        
        Args:
            code: The code to display
            language: Programming language for syntax highlighting
            line_numbers: Whether to show line numbers
        """
        syntax = Syntax(
            code,
            language,
            theme=self.theme,
            line_numbers=line_numbers,
            word_wrap=True
        )
        self.console.print(syntax)
    
    def create_progress_bar(self):
        """
        Create a rich Progress bar for long-running operations.
        
        Returns:
            Rich Progress object
        """
        from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
        
        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=self.console
        )


# Convenience function for quick formatting
def format_output(obj: Any, theme: str = "monokai") -> str:
    """
    Quick format function for Python objects.
    
    Args:
        obj: Object to format
        theme: Syntax highlighting theme
        
    Returns:
        Formatted string
    """
    formatter = OutputFormatter(theme=theme)
    return formatter.format_result(obj)
