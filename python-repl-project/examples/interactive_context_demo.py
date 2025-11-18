#!/usr/bin/env python3
"""
Interactive demo of ExecutionContext.

This script provides a simple interactive REPL using the ExecutionContext class.
Type Python code to execute it, or use special commands:
  - .vars     : List all variables
  - .modules  : List imported modules
  - .history  : Show execution history
  - .clear    : Clear namespace
  - .info <var> : Show info about a variable
  - .introspect : Show namespace overview
  - .save <file> : Save state to file
  - .load <file> : Load state from file
  - .help     : Show this help
  - .exit     : Exit the REPL
"""

import sys
import os
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.pyrepl.context import ExecutionContext


class InteractiveREPL:
    """Simple interactive REPL using ExecutionContext."""
    
    def __init__(self):
        self.context = ExecutionContext()
        self.running = True
        self.command_count = 0
    
    def print_banner(self):
        """Print welcome banner."""
        print("=" * 70)
        print("  Interactive ExecutionContext Demo")
        print("  Type Python code to execute, or .help for commands")
        print("=" * 70)
        print()
    
    def print_help(self):
        """Print help message."""
        print("\nSpecial Commands:")
        print("  .vars          - List all variables")
        print("  .modules       - List imported modules")
        print("  .history       - Show execution history")
        print("  .clear         - Clear namespace")
        print("  .info <var>    - Show detailed info about a variable")
        print("  .introspect    - Show namespace overview")
        print("  .save <file>   - Save state to file")
        print("  .load <file>   - Load state from file")
        print("  .help          - Show this help")
        print("  .exit          - Exit the REPL")
        print()
    
    def handle_command(self, line: str) -> bool:
        """
        Handle special commands.
        
        Returns True if a command was handled, False otherwise.
        """
        if not line.startswith('.'):
            return False
        
        parts = line[1:].split(maxsplit=1)
        command = parts[0].lower()
        args = parts[1] if len(parts) > 1 else None
        
        if command == 'exit' or command == 'quit':
            self.running = False
            print("Goodbye!")
            return True
        
        elif command == 'help':
            self.print_help()
            return True
        
        elif command == 'vars':
            self.show_variables()
            return True
        
        elif command == 'modules':
            self.show_modules()
            return True
        
        elif command == 'history':
            self.show_history()
            return True
        
        elif command == 'clear':
            self.context.clear_namespace()
            print("Namespace cleared.")
            return True
        
        elif command == 'info':
            if args:
                self.show_variable_info(args)
            else:
                print("Usage: .info <variable_name>")
            return True
        
        elif command == 'introspect':
            self.show_introspection()
            return True
        
        elif command == 'save':
            if args:
                self.save_state(args)
            else:
                print("Usage: .save <filename>")
            return True
        
        elif command == 'load':
            if args:
                self.load_state(args)
            else:
                print("Usage: .load <filename>")
            return True
        
        else:
            print(f"Unknown command: .{command}")
            print("Type .help for available commands")
            return True
    
    def show_variables(self):
        """Show all variables."""
        variables = self.context.list_variables()
        if variables:
            print("\nVariables:")
            for name, value in variables.items():
                value_str = repr(value)
                if len(value_str) > 50:
                    value_str = value_str[:47] + "..."
                print(f"  {name:20} = {value_str}")
        else:
            print("No variables defined.")
    
    def show_modules(self):
        """Show imported modules."""
        modules = self.context.list_modules()
        if modules:
            print("\nImported Modules:")
            for module in modules:
                print(f"  - {module}")
        else:
            print("No modules imported.")
    
    def show_history(self):
        """Show execution history."""
        history = self.context.get_history()
        if history:
            print("\nExecution History:")
            for i, code in enumerate(history, 1):
                code_display = code.replace('\n', ' ')
                if len(code_display) > 60:
                    code_display = code_display[:57] + "..."
                print(f"  [{i:3}] {code_display}")
        else:
            print("No history available.")
    
    def show_variable_info(self, var_name: str):
        """Show detailed variable information."""
        try:
            info = self.context.get_variable_info(var_name)
            print(f"\nVariable Information: {var_name}")
            print(f"  Type:     {info['type']}")
            print(f"  Module:   {info['module']}")
            print(f"  Callable: {info['callable']}")
            if 'length' in info:
                print(f"  Length:   {info['length']}")
            if info['doc']:
                doc = info['doc'].strip().split('\n')[0]
                if len(doc) > 60:
                    doc = doc[:57] + "..."
                print(f"  Doc:      {doc}")
        except NameError:
            print(f"Variable '{var_name}' not found.")
    
    def show_introspection(self):
        """Show namespace introspection."""
        info = self.context.introspect()
        
        print("\nNamespace Overview:")
        print(f"  Variables: {len(info['variables'])}")
        if info['variables']:
            for name in list(info['variables'].keys())[:5]:
                print(f"    - {name}")
            if len(info['variables']) > 5:
                print(f"    ... and {len(info['variables']) - 5} more")
        
        print(f"\n  Functions: {len(info['functions'])}")
        if info['functions']:
            for name in list(info['functions'].keys())[:5]:
                print(f"    - {name}")
        
        print(f"\n  Classes: {len(info['classes'])}")
        if info['classes']:
            for name in list(info['classes'].keys())[:5]:
                print(f"    - {name}")
        
        print(f"\n  Modules: {len(info['modules'])}")
        if info['modules']:
            for name in list(info['modules'].keys())[:5]:
                print(f"    - {name}")
    
    def save_state(self, filename: str):
        """Save context state to file."""
        try:
            self.context.save_state(filename)
            print(f"State saved to: {filename}")
        except Exception as e:
            print(f"Error saving state: {e}")
    
    def load_state(self, filename: str):
        """Load context state from file."""
        try:
            self.context.load_state(filename)
            print(f"State loaded from: {filename}")
        except Exception as e:
            print(f"Error loading state: {e}")
    
    def execute_code(self, code: str):
        """Execute user code."""
        try:
            result = self.context.execute_code(code)
            if result is not None:
                print(f"=> {result!r}")
        except Exception as e:
            print(f"Error: {type(e).__name__}: {e}")
    
    def run(self):
        """Run the interactive REPL."""
        self.print_banner()
        
        while self.running:
            try:
                # Get input
                self.command_count += 1
                prompt = f"[{self.command_count}]>>> "
                line = input(prompt)
                
                # Skip empty lines
                if not line.strip():
                    continue
                
                # Handle special commands
                if self.handle_command(line):
                    continue
                
                # Handle multi-line input
                if line.rstrip().endswith(':') or line.rstrip().endswith('\\'):
                    lines = [line]
                    while True:
                        try:
                            continuation = input("    ... ")
                            if not continuation.strip():
                                break
                            lines.append(continuation)
                            if not continuation.rstrip().endswith('\\'):
                                break
                        except EOFError:
                            break
                    code = '\n'.join(lines)
                else:
                    code = line
                
                # Execute code
                self.execute_code(code)
                
            except EOFError:
                print("\nGoodbye!")
                break
            except KeyboardInterrupt:
                print("\nKeyboardInterrupt")
                continue


def main():
    """Main entry point."""
    repl = InteractiveREPL()
    repl.run()


if __name__ == '__main__':
    main()
