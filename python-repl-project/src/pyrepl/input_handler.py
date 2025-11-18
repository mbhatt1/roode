"""
Input handler module for Python REPL.

Provides sophisticated input handling with multi-line support, syntax highlighting,
auto-completion, and customizable key bindings using prompt_toolkit.
"""

import ast
import sys
from typing import Optional, Callable

from prompt_toolkit import PromptSession
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.document import Document
from prompt_toolkit.formatted_text import PygmentsTokens
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.key_binding import KeyBindings, KeyPressEvent
from prompt_toolkit.lexers import PygmentsLexer
from prompt_toolkit.styles import Style
from prompt_toolkit.validation import Validator, ValidationError
from pygments.lexers.python import PythonLexer
from pygments.token import Token


class PythonValidator(Validator):
    """Validator for Python code input."""
    
    def __init__(self, allow_incomplete: bool = True):
        """
        Initialize the validator.
        
        Args:
            allow_incomplete: If True, allows incomplete code (for multi-line input)
        """
        self.allow_incomplete = allow_incomplete
    
    def validate(self, document: Document) -> None:
        """
        Validate Python code.
        
        Args:
            document: The document to validate
            
        Raises:
            ValidationError: If the code has syntax errors
        """
        text = document.text
        
        if not text.strip():
            return
        
        # Check for syntax errors
        try:
            compile(text, '<input>', 'exec')
        except SyntaxError as e:
            # If incomplete code is allowed, check if it's just incomplete
            if self.allow_incomplete and self._is_incomplete(text):
                return
            
            # Get the error position
            if e.lineno is not None:
                # Calculate the index in the document
                lines = text.split('\n')
                index = sum(len(line) + 1 for line in lines[:e.lineno - 1])
                if e.offset:
                    index += e.offset - 1
            else:
                index = len(text)
            
            raise ValidationError(
                message=f'Syntax error: {e.msg}',
                cursor_position=index
            )
    
    def _is_incomplete(self, text: str) -> bool:
        """
        Check if the code is incomplete but potentially valid.
        
        Args:
            text: The text to check
            
        Returns:
            True if the code appears to be incomplete
        """
        # Check for unclosed brackets, quotes, or indentation
        lines = text.split('\n')
        
        # Check if last line is indented or ends with colon
        if lines and (lines[-1].startswith((' ', '\t')) or lines[-1].rstrip().endswith(':')):
            return True
        
        # Check for unclosed brackets
        brackets = {'(': ')', '[': ']', '{': '}'}
        stack = []
        in_string = None
        escape = False
        
        for char in text:
            if escape:
                escape = False
                continue
            
            if char == '\\':
                escape = True
                continue
            
            if in_string:
                if char == in_string:
                    in_string = None
            elif char in ('"', "'"):
                in_string = char
            elif char in brackets:
                stack.append(brackets[char])
            elif char in brackets.values():
                if stack and stack[-1] == char:
                    stack.pop()
        
        # If there are unclosed brackets or strings, it's incomplete
        return bool(stack or in_string)


class PythonCompleter(Completer):
    """Smart completer for Python code."""
    
    def __init__(self, namespace: Optional[dict] = None):
        """
        Initialize the completer.
        
        Args:
            namespace: The namespace to use for completion suggestions
        """
        self.namespace = namespace or {}
    
    def get_completions(self, document: Document, complete_event):
        """
        Generate completion suggestions.
        
        Args:
            document: The current document
            complete_event: The completion event
            
        Yields:
            Completion objects
        """
        text = document.text_before_cursor
        
        # Get the word to complete
        word = self._get_current_word(text)
        
        if not word:
            return
        
        # Get completions from namespace
        completions = self._get_namespace_completions(word)
        
        # Get attribute completions if there's a dot
        if '.' in word:
            completions.extend(self._get_attribute_completions(word))
        
        # Yield unique completions
        seen = set()
        for completion in completions:
            if completion not in seen:
                seen.add(completion)
                yield Completion(
                    completion,
                    start_position=-len(word.split('.')[-1])
                )
    
    def _get_current_word(self, text: str) -> str:
        """
        Extract the current word being typed.
        
        Args:
            text: The text before cursor
            
        Returns:
            The current word
        """
        # Find the start of the current identifier
        i = len(text) - 1
        while i >= 0 and (text[i].isalnum() or text[i] in ('_', '.')):
            i -= 1
        return text[i + 1:]
    
    def _get_namespace_completions(self, word: str) -> list:
        """
        Get completions from the namespace.
        
        Args:
            word: The word to complete
            
        Returns:
            List of matching completions
        """
        prefix = word.split('.')[0]
        return [name for name in self.namespace if name.startswith(prefix)]
    
    def _get_attribute_completions(self, word: str) -> list:
        """
        Get attribute completions for objects.
        
        Args:
            word: The word to complete (e.g., 'obj.attr')
            
        Returns:
            List of matching attribute names
        """
        parts = word.split('.')
        if len(parts) < 2:
            return []
        
        obj_name = parts[0]
        attr_prefix = parts[-1]
        
        # Get the object from namespace
        obj = self.namespace.get(obj_name)
        if obj is None:
            return []
        
        # Get all attributes
        try:
            attrs = dir(obj)
            return [
                f"{'.'.join(parts[:-1])}.{attr}"
                for attr in attrs
                if attr.startswith(attr_prefix) and not attr.startswith('_')
            ]
        except Exception:
            return []
    
    def update_namespace(self, namespace: dict):
        """
        Update the namespace used for completions.
        
        Args:
            namespace: The new namespace
        """
        self.namespace = namespace


class InputHandler:
    """
    Advanced input handler for Python REPL with multi-line support,
    syntax highlighting, and smart completion.
    """
    
    def __init__(
        self,
        namespace: Optional[dict] = None,
        vi_mode: bool = False,
        enable_history: bool = True,
        enable_auto_suggest: bool = True,
        validate_on_enter: bool = True
    ):
        """
        Initialize the input handler.
        
        Args:
            namespace: The namespace for completions
            vi_mode: Enable Vi key bindings (default: Emacs mode)
            enable_history: Enable input history
            enable_auto_suggest: Enable auto-suggestions from history
            validate_on_enter: Validate input before accepting
        """
        self.namespace = namespace or {}
        self.vi_mode = vi_mode
        self.validate_on_enter = validate_on_enter
        
        # Set up history
        self.history = InMemoryHistory() if enable_history else None
        
        # Set up components
        self.completer = PythonCompleter(self.namespace)
        self.validator = PythonValidator(allow_incomplete=True) if validate_on_enter else None
        self.lexer = PygmentsLexer(PythonLexer)
        
        # Set up auto-suggest
        self.auto_suggest = AutoSuggestFromHistory() if enable_auto_suggest else None
        
        # Set up style
        self.style = Style.from_dict({
            'completion-menu.completion': 'bg:#008888 #ffffff',
            'completion-menu.completion.current': 'bg:#00aaaa #000000',
            'scrollbar.background': 'bg:#88aaaa',
            'scrollbar.button': 'bg:#222222',
            'prompt': '#00aa00 bold',
            'continuation': '#00aa00',
        })
        
        # Set up key bindings
        self.key_bindings = self.setup_key_bindings()
        
        # Create prompt session
        self.session = PromptSession(
            lexer=self.lexer,
            completer=self.completer,
            validator=self.validator,
            history=self.history,
            auto_suggest=self.auto_suggest,
            style=self.style,
            key_bindings=self.key_bindings,
            vi_mode=self.vi_mode,
            enable_history_search=True,
            complete_while_typing=True,
            mouse_support=True,
            multiline=False,  # We'll handle multiline manually
            prompt_continuation=self._get_continuation_prompt,
        )
    
    def setup_key_bindings(self) -> KeyBindings:
        """
        Set up custom key bindings.
        
        Returns:
            KeyBindings object with custom bindings
        """
        kb = KeyBindings()
        
        @kb.add('enter')
        def handle_enter(event: KeyPressEvent):
            """Handle Enter key - accept input or insert newline."""
            buffer = event.current_buffer
            text = buffer.text
            
            # Check if we should continue to next line
            if self._should_continue(text):
                # Insert newline and auto-indent
                buffer.insert_text('\n')
                indent = self._get_indentation(text)
                buffer.insert_text(indent)
            else:
                # Accept the input
                buffer.validate_and_handle()
        
        @kb.add('escape', 'enter')
        def force_accept(event: KeyPressEvent):
            """Force accept input (even if incomplete)."""
            event.current_buffer.validate_and_handle()
        
        @kb.add('c-d')
        def handle_eof(event: KeyPressEvent):
            """Handle Ctrl-D - exit if buffer is empty."""
            buffer = event.current_buffer
            if not buffer.text:
                event.app.exit(exception=EOFError)
        
        @kb.add('c-c')
        def handle_interrupt(event: KeyPressEvent):
            """Handle Ctrl-C - clear buffer or raise KeyboardInterrupt."""
            buffer = event.current_buffer
            if buffer.text:
                buffer.reset()
            else:
                raise KeyboardInterrupt
        
        @kb.add('tab')
        def handle_tab(event: KeyPressEvent):
            """Handle Tab - insert spaces or trigger completion."""
            buffer = event.current_buffer
            
            # If at the start of a line or after whitespace, insert spaces
            before_cursor = buffer.document.current_line_before_cursor
            if not before_cursor or before_cursor.isspace():
                buffer.insert_text('    ')
            else:
                # Trigger completion
                buffer.start_completion()
        
        @kb.add('c-space')
        def force_completion(event: KeyPressEvent):
            """Force trigger completion menu."""
            event.current_buffer.start_completion()
        
        return kb
    
    def get_input(self, prompt: str = ">>> ") -> str:
        """
        Get input from the user with all features enabled.
        
        Args:
            prompt: The prompt string to display
            
        Returns:
            The input string
            
        Raises:
            EOFError: When user presses Ctrl-D on empty line
            KeyboardInterrupt: When user presses Ctrl-C on empty line
        """
        try:
            # Update the multiline setting based on context
            self.session.multiline = True
            
            text = self.session.prompt(prompt)
            return text
        except EOFError:
            raise
        except KeyboardInterrupt:
            raise
    
    def validate_input(self, text: str) -> bool:
        """
        Validate if the input is complete and syntactically correct.
        
        Args:
            text: The text to validate
            
        Returns:
            True if the input is valid and complete
        """
        if not text.strip():
            return True
        
        try:
            # Try to compile as 'exec' for statements
            compile(text, '<input>', 'exec')
            return True
        except SyntaxError:
            # Try to compile as 'eval' for expressions
            try:
                compile(text, '<input>', 'eval')
                return True
            except SyntaxError:
                return False
    
    def handle_multiline(self, initial_prompt: str = ">>> ") -> str:
        """
        Handle multi-line input with smart continuation detection.
        
        Args:
            initial_prompt: The initial prompt to display
            
        Returns:
            The complete multi-line input
            
        Raises:
            EOFError: When user presses Ctrl-D
            KeyboardInterrupt: When user interrupts input
        """
        lines = []
        continuation_prompt = "... "
        current_prompt = initial_prompt
        
        while True:
            try:
                line = self.session.prompt(current_prompt)
                
                if not line.strip() and lines:
                    # Empty line after content - check if we're done
                    full_text = '\n'.join(lines)
                    if self.validate_input(full_text):
                        return full_text
                
                lines.append(line)
                
                # Check if we need to continue
                full_text = '\n'.join(lines)
                if not self._should_continue(full_text):
                    if self.validate_input(full_text):
                        return full_text
                
                # Continue to next line
                current_prompt = continuation_prompt
                
            except EOFError:
                if lines:
                    # Return what we have so far
                    return '\n'.join(lines)
                raise
            except KeyboardInterrupt:
                # Clear and start over
                raise
    
    def _should_continue(self, text: str) -> bool:
        """
        Determine if input should continue to the next line.
        
        Args:
            text: The current input text
            
        Returns:
            True if input should continue
        """
        if not text.strip():
            return False
        
        lines = text.split('\n')
        last_line = lines[-1]
        
        # Continue if last line ends with colon
        if last_line.rstrip().endswith(':'):
            return True
        
        # Continue if last line is indented
        if last_line and (last_line[0] in (' ', '\t')):
            return True
        
        # Continue if there are unclosed brackets
        validator = PythonValidator(allow_incomplete=True)
        if validator._is_incomplete(text):
            return True
        
        # Check if the code is syntactically incomplete
        try:
            compile(text, '<input>', 'exec')
            return False
        except SyntaxError as e:
            # Some syntax errors mean incomplete code
            if 'unexpected EOF' in str(e).lower() or 'invalid syntax' in str(e).lower():
                return True
            return False
    
    def _get_indentation(self, text: str) -> str:
        """
        Calculate the indentation for the next line.
        
        Args:
            text: The current input text
            
        Returns:
            The indentation string for the next line
        """
        lines = text.split('\n')
        if not lines:
            return ''
        
        last_line = lines[-1]
        
        # Get current indentation
        current_indent = len(last_line) - len(last_line.lstrip())
        indent = last_line[:current_indent]
        
        # If line ends with colon, increase indentation
        if last_line.rstrip().endswith(':'):
            indent += '    '
        
        # If line starts with certain keywords, maintain or decrease indentation
        stripped = last_line.strip()
        if stripped.startswith(('return', 'break', 'continue', 'pass', 'raise')):
            # These often end a block, so might decrease indent on next line
            # But we'll maintain for now and let the user adjust
            pass
        
        return indent
    
    def _get_continuation_prompt(self, width: int, line_number: int, is_soft_wrap: bool) -> str:
        """
        Get the continuation prompt for multi-line input.
        
        Args:
            width: The width of the prompt
            line_number: The current line number
            is_soft_wrap: Whether this is a soft wrap
            
        Returns:
            The continuation prompt
        """
        if is_soft_wrap:
            return ' ' * width
        return '... '
    
    def update_namespace(self, namespace: dict):
        """
        Update the namespace used for completions.
        
        Args:
            namespace: The new namespace dictionary
        """
        self.namespace = namespace
        self.completer.update_namespace(namespace)
    
    def set_vi_mode(self, enabled: bool):
        """
        Enable or disable Vi mode.
        
        Args:
            enabled: True to enable Vi mode, False for Emacs mode
        """
        self.vi_mode = enabled
        # Note: Changing vi_mode requires creating a new session
        # This is a limitation of prompt_toolkit
    
    def clear_history(self):
        """Clear the input history."""
        if self.history:
            self.history.clear()
    
    def get_history(self) -> list:
        """
        Get the input history.
        
        Returns:
            List of history strings
        """
        if self.history:
            return list(self.history.load_history_strings())
        return []


# Convenience function for quick usage
def get_input(prompt: str = ">>> ", namespace: Optional[dict] = None) -> str:
    """
    Convenience function to get input with default settings.
    
    Args:
        prompt: The prompt string
        namespace: Optional namespace for completions
        
    Returns:
        The input string
    """
    handler = InputHandler(namespace=namespace)
    return handler.get_input(prompt)


if __name__ == '__main__':
    """Demo of the InputHandler capabilities."""
    print("Python REPL Input Handler Demo")
    print("Features: Multi-line input, syntax highlighting, auto-completion")
    print("Press Ctrl-D to exit, Ctrl-C to cancel input")
    print("-" * 60)
    
    # Create a sample namespace for completions
    demo_namespace = {
        'print': print,
        'len': len,
        'str': str,
        'list': list,
        'dict': dict,
        'sample_var': 42,
        'sample_list': [1, 2, 3],
    }
    
    handler = InputHandler(namespace=demo_namespace, enable_auto_suggest=True)
    
    while True:
        try:
            code = handler.get_input(">>> ")
            
            if code.strip():
                print(f"You entered ({len(code)} chars):")
                print(repr(code))
                print()
                
                # Try to execute it
                try:
                    result = eval(code, demo_namespace)
                    if result is not None:
                        print(f"Result: {result}")
                        demo_namespace['_'] = result
                except SyntaxError:
                    # Try as statement
                    try:
                        exec(code, demo_namespace)
                    except Exception as e:
                        print(f"Error: {e}")
                except Exception as e:
                    print(f"Error: {e}")
                
                # Update namespace for completions
                handler.update_namespace(demo_namespace)
                print()
                
        except EOFError:
            print("\nGoodbye!")
            break
        except KeyboardInterrupt:
            print("\n^C")
            continue
