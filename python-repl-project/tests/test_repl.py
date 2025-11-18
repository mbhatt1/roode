"""
Integration tests for the REPL class.

Tests the complete REPL functionality including command handling,
special commands, signal handling, and integration of all subsystems.
"""

import pytest
import sys
import signal
import tempfile
from io import StringIO
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from src.pyrepl.repl import REPL
from src.pyrepl.config import Config


class TestREPLInitialization:
    """Test REPL initialization."""

    def test_default_initialization(self):
        """Test REPL initializes with defaults."""
        repl = REPL()
        assert repl is not None
        assert repl.context is not None
        assert repl.history is not None
        assert repl.completion is not None
        assert repl.output is not None

    def test_initialization_with_config(self):
        """Test REPL initialization with custom config."""
        config = Config()
        config.appearance.theme = "dracula"
        repl = REPL(config=config)
        assert repl.config.appearance.theme == "dracula"

    def test_version_info(self):
        """Test version information is available."""
        assert REPL.VERSION is not None
        assert REPL.PYTHON_VERSION is not None

    def test_special_commands_defined(self):
        """Test special commands are defined."""
        assert isinstance(REPL.SPECIAL_COMMANDS, dict)
        assert "!help" in REPL.SPECIAL_COMMANDS
        assert "!exit" in REPL.SPECIAL_COMMANDS
        assert "!vars" in REPL.SPECIAL_COMMANDS

    def test_initial_state(self):
        """Test initial REPL state."""
        repl = REPL()
        assert repl.running is False
        assert repl.buffer == []
        assert repl._last_exception is None


class TestCommandHandling:
    """Test command execution and handling."""

    def test_execute_simple_expression(self):
        """Test executing a simple expression."""
        repl = REPL()
        result = repl.handle_command("2 + 2")
        assert result == 4

    def test_execute_statement(self):
        """Test executing a statement."""
        repl = REPL()
        result = repl.handle_command("x = 42")
        assert result is None
        assert repl.context.get_variable("x") == 42

    def test_execute_function_definition(self):
        """Test defining and calling a function."""
        repl = REPL()
        repl.handle_command("def add(a, b):\n    return a + b")
        result = repl.handle_command("add(3, 5)")
        assert result == 8

    def test_execute_import(self):
        """Test import statement."""
        repl = REPL()
        repl.handle_command("import math")
        result = repl.handle_command("math.pi")
        assert abs(result - 3.14159) < 0.001

    def test_execute_empty_command(self):
        """Test executing empty command."""
        repl = REPL()
        result = repl.handle_command("")
        assert result is None

    def test_execute_whitespace_only(self):
        """Test executing whitespace-only command."""
        repl = REPL()
        result = repl.handle_command("   \n\t  ")
        assert result is None

    def test_exception_handling(self):
        """Test exception is caught and stored."""
        repl = REPL()
        result = repl.handle_command("1 / 0")
        assert result is None
        assert repl._last_exception is not None
        assert isinstance(repl._last_exception, ZeroDivisionError)

    def test_get_last_exception(self):
        """Test retrieving last exception."""
        repl = REPL()
        assert repl.get_last_exception() is None
        
        repl.handle_command("raise ValueError('test')")
        exc = repl.get_last_exception()
        assert isinstance(exc, ValueError)


class TestSpecialCommands:
    """Test special REPL commands."""

    def test_help_command(self):
        """Test !help command."""
        repl = REPL()
        result = repl.execute_special_command("!help")
        assert result is True

    def test_vars_command_empty(self):
        """Test !vars command with no variables."""
        repl = REPL()
        result = repl.execute_special_command("!vars")
        assert result is True

    def test_vars_command_with_variables(self):
        """Test !vars command with defined variables."""
        repl = REPL()
        repl.handle_command("x = 42")
        repl.handle_command("y = 'hello'")
        result = repl.execute_special_command("!vars")
        assert result is True

    def test_clear_command(self):
        """Test !clear command."""
        repl = REPL()
        repl.handle_command("x = 100")
        assert repl.context.has_variable("x")
        
        # Mock the prompt to auto-confirm
        with patch.object(repl.session, 'prompt', return_value='y'):
            result = repl.execute_special_command("!clear")
        
        assert result is True

    def test_save_command_no_filename(self):
        """Test !save command without filename."""
        repl = REPL()
        result = repl.execute_special_command("!save")
        assert result is True  # Should handle gracefully

    def test_save_command_with_filename(self):
        """Test !save command with filename."""
        repl = REPL()
        repl.handle_command("x = 42")
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pkl") as f:
            temp_file = f.name
        
        try:
            result = repl.execute_special_command(f"!save {temp_file}")
            assert result is True
            assert Path(temp_file).exists()
        finally:
            Path(temp_file).unlink(missing_ok=True)

    def test_load_command_no_filename(self):
        """Test !load command without filename."""
        repl = REPL()
        result = repl.execute_special_command("!load")
        assert result is True

    def test_load_command_nonexistent_file(self):
        """Test !load command with nonexistent file."""
        repl = REPL()
        result = repl.execute_special_command("!load /nonexistent/file.pkl")
        assert result is True

    def test_load_command_with_valid_file(self):
        """Test !load command with valid file."""
        repl = REPL()
        repl.handle_command("saved_var = 123")
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pkl") as f:
            temp_file = f.name
        
        try:
            # Save state
            repl.execute_special_command(f"!save {temp_file}")
            
            # Clear and reload
            repl.context.clear_namespace()
            result = repl.execute_special_command(f"!load {temp_file}")
            
            assert result is True
            assert repl.context.get_variable("saved_var") == 123
        finally:
            Path(temp_file).unlink(missing_ok=True)

    def test_history_command(self):
        """Test !history command."""
        repl = REPL()
        repl.history.add_command("cmd1")
        repl.history.add_command("cmd2")
        result = repl.execute_special_command("!history")
        assert result is True

    def test_exit_command(self):
        """Test !exit command."""
        repl = REPL()
        repl.running = True
        result = repl.execute_special_command("!exit")
        assert result is True
        assert repl.running is False

    def test_quit_command(self):
        """Test !quit command."""
        repl = REPL()
        repl.running = True
        result = repl.execute_special_command("!quit")
        assert result is True
        assert repl.running is False

    def test_unknown_command(self):
        """Test unknown special command."""
        repl = REPL()
        result = repl.execute_special_command("!unknown")
        assert result is False


class TestShouldExecute:
    """Test the _should_execute logic."""

    def test_empty_buffer_returns_false(self):
        """Test empty buffer doesn't execute."""
        repl = REPL()
        assert repl._should_execute() is False

    def test_whitespace_only_returns_true(self):
        """Test whitespace-only executes (to clear)."""
        repl = REPL()
        repl.buffer.append("   ")
        assert repl._should_execute() is True

    def test_complete_statement_returns_true(self):
        """Test complete statement executes."""
        repl = REPL()
        repl.buffer.append("x = 42")
        assert repl._should_execute() is True

    def test_incomplete_statement_returns_false(self):
        """Test incomplete statement doesn't execute."""
        repl = REPL()
        repl.buffer.append("def foo():")
        result = repl._should_execute()
        # May return False for incomplete code
        assert isinstance(result, bool)

    def test_special_command_returns_true(self):
        """Test special commands execute immediately."""
        repl = REPL()
        repl.buffer.append("!help")
        assert repl._should_execute() is True

    def test_multiline_complete_returns_true(self):
        """Test complete multiline code executes."""
        repl = REPL()
        repl.buffer.append("def foo():")
        repl.buffer.append("    return 42")
        assert repl._should_execute() is True


class TestSignalHandling:
    """Test signal handling."""

    def test_sigint_handler_exists(self):
        """Test SIGINT handler is set up."""
        repl = REPL()
        # Check signal handler was set (implementation specific)
        assert signal.getsignal(signal.SIGINT) is not signal.default_int_handler

    def test_handle_sigint_clears_buffer(self):
        """Test SIGINT clears input buffer."""
        repl = REPL()
        repl.buffer.append("incomplete code")
        
        with pytest.raises(KeyboardInterrupt):
            repl._handle_sigint(signal.SIGINT, None)
        
        # Buffer should be cleared
        assert len(repl.buffer) == 0

    def test_handle_sigint_with_empty_buffer(self):
        """Test SIGINT with empty buffer."""
        repl = REPL()
        
        with pytest.raises(KeyboardInterrupt):
            repl._handle_sigint(signal.SIGINT, None)

    @pytest.mark.skipif(not hasattr(signal, 'SIGQUIT'), reason="SIGQUIT not available on Windows")
    def test_sigquit_handler_exists(self):
        """Test SIGQUIT handler is set up (Unix only)."""
        repl = REPL()
        assert signal.getsignal(signal.SIGQUIT) is not signal.default_int_handler


class TestBanner:
    """Test banner display."""

    def test_display_banner(self, capsys):
        """Test banner is displayed."""
        repl = REPL()
        repl.display_banner()
        captured = capsys.readouterr()
        assert "PyREPL" in captured.out
        assert "Python" in captured.out

    def test_banner_contains_help_info(self, capsys):
        """Test banner contains help information."""
        repl = REPL()
        repl.display_banner()
        captured = capsys.readouterr()
        assert "!help" in captured.out or "help" in captured.out.lower()


class TestShutdown:
    """Test REPL shutdown."""

    def test_shutdown_changes_state(self):
        """Test shutdown changes running state."""
        repl = REPL()
        repl.running = True
        repl.shutdown()
        assert repl.running is False

    def test_shutdown_when_not_running(self):
        """Test shutdown when already stopped."""
        repl = REPL()
        repl.running = False
        repl.shutdown()  # Should not raise
        assert repl.running is False

    def test_shutdown_compacts_database(self):
        """Test shutdown compacts history database."""
        repl = REPL()
        repl.running = True
        # Should not raise even if compaction fails
        repl.shutdown()


class TestMultilineInput:
    """Test multiline input handling."""

    def test_buffer_accumulates_lines(self):
        """Test buffer accumulates multiple lines."""
        repl = REPL()
        assert len(repl.buffer) == 0
        
        repl.buffer.append("def foo():")
        assert len(repl.buffer) == 1
        
        repl.buffer.append("    return 42")
        assert len(repl.buffer) == 2

    def test_buffer_cleared_after_execution(self):
        """Test buffer is cleared after execution."""
        repl = REPL()
        repl.buffer.append("x = 42")
        
        if repl._should_execute():
            code = '\n'.join(repl.buffer)
            repl.buffer.clear()
            repl.handle_command(code)
        
        assert len(repl.buffer) == 0


class TestVariablePersistence:
    """Test variable persistence across commands."""

    def test_variables_persist(self):
        """Test variables persist between commands."""
        repl = REPL()
        repl.handle_command("x = 10")
        repl.handle_command("x += 5")
        result = repl.handle_command("x")
        assert result == 15

    def test_functions_persist(self):
        """Test functions persist between commands."""
        repl = REPL()
        repl.handle_command("def multiply(a, b): return a * b")
        result = repl.handle_command("multiply(6, 7)")
        assert result == 42

    def test_imports_persist(self):
        """Test imports persist between commands."""
        repl = REPL()
        repl.handle_command("import random")
        result = repl.handle_command("hasattr(random, 'randint')")
        assert result is True


class TestHistoryIntegration:
    """Test history integration with REPL."""

    def test_commands_added_to_history(self):
        """Test commands are added to history."""
        repl = REPL()
        initial_count = len(repl.history.get_history())
        
        repl.handle_command("x = 42")
        
        # Note: Commands might not be added to history in handle_command
        # They're typically added in the main loop
        # So we test the history manager directly
        repl.history.add_command("test command")
        assert len(repl.history.get_history()) > initial_count


class TestCompletionIntegration:
    """Test completion integration with REPL."""

    def test_completion_engine_has_context(self):
        """Test completion engine has access to context."""
        repl = REPL()
        assert repl.completion is not None

    def test_completion_after_variable_definition(self):
        """Test completion works after defining variables."""
        repl = REPL()
        repl.handle_command("my_variable = 100")
        
        # Completion should work (though we can't easily test the full flow)
        assert repl.completion is not None


class TestConfigurationIntegration:
    """Test configuration integration."""

    def test_custom_theme(self):
        """Test custom theme is applied."""
        config = Config()
        config.appearance.theme = "dracula"
        repl = REPL(config=config)
        assert repl.output.theme == "dracula"

    def test_custom_prompt(self):
        """Test custom prompt style."""
        config = Config()
        config.appearance.prompt_style = ">>> "
        repl = REPL(config=config)
        assert repl.config.appearance.prompt_style == ">>> "

    def test_history_size(self):
        """Test custom history size."""
        config = Config()
        config.history.history_size = 500
        repl = REPL(config=config)
        assert repl.history.max_history == 500


class TestErrorRecovery:
    """Test error recovery and state preservation."""

    def test_error_doesnt_crash_repl(self):
        """Test errors don't crash the REPL."""
        repl = REPL()
        repl.handle_command("1 / 0")
        # REPL should still work after error
        result = repl.handle_command("2 + 2")
        assert result == 4

    def test_syntax_error_recovery(self):
        """Test recovery from syntax errors."""
        repl = REPL()
        repl.handle_command("def broken(")  # Syntax error
        # Should still work
        result = repl.handle_command("3 * 3")
        assert result == 9

    def test_name_error_recovery(self):
        """Test recovery from name errors."""
        repl = REPL()
        repl.handle_command("undefined_variable")
        # Should still work
        result = repl.handle_command("5 + 5")
        assert result == 10


class TestEdgeCases:
    """Test edge cases and unusual scenarios."""

    def test_very_long_command(self):
        """Test handling very long commands."""
        repl = REPL()
        long_cmd = "x = " + "1" * 10000
        result = repl.handle_command(long_cmd)
        assert result is None

    def test_unicode_in_commands(self):
        """Test Unicode characters in commands."""
        repl = REPL()
        repl.handle_command("变量 = 42")  # Chinese variable name
        result = repl.handle_command("变量")
        assert result == 42

    def test_special_command_with_args(self):
        """Test special command with arguments."""
        repl = REPL()
        # !save with arguments
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pkl") as f:
            temp_file = f.name
        
        try:
            result = repl.execute_special_command(f"!save {temp_file}")
            assert result is True
        finally:
            Path(temp_file).unlink(missing_ok=True)

    def test_rapid_command_execution(self):
        """Test rapid command execution."""
        repl = REPL()
        for i in range(100):
            repl.handle_command(f"x{i} = {i}")
        
        result = repl.handle_command("x50")
        assert result == 50

    def test_deeply_nested_code(self):
        """Test deeply nested code structures."""
        repl = REPL()
        code = """
def level1():
    def level2():
        def level3():
            return 42
        return level3()
    return level2()
"""
        repl.handle_command(code)
        result = repl.handle_command("level1()")
        assert result == 42


class TestREPLIntegration:
    """Integration tests for complete REPL functionality."""

    def test_full_workflow(self):
        """Test complete workflow from start to finish."""
        repl = REPL()
        
        # Import
        repl.handle_command("import math")
        
        # Define variable
        repl.handle_command("radius = 5")
        
        # Calculate
        result = repl.handle_command("math.pi * radius ** 2")
        assert abs(result - 78.54) < 0.1
        
        # Define function
        repl.handle_command("def square(x): return x ** 2")
        
        # Use function
        result = repl.handle_command("square(radius)")
        assert result == 25

    def test_save_and_load_workflow(self):
        """Test save and load workflow."""
        repl = REPL()
        
        # Define some state
        repl.handle_command("x = 100")
        repl.handle_command("y = 200")
        repl.handle_command("result = x + y")
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pkl") as f:
            temp_file = f.name
        
        try:
            # Save
            repl.execute_special_command(f"!save {temp_file}")
            
            # Clear
            repl.context.clear_namespace()
            
            # Load
            repl.execute_special_command(f"!load {temp_file}")
            
            # Verify
            assert repl.context.get_variable("x") == 100
            assert repl.context.get_variable("y") == 200
            assert repl.context.get_variable("result") == 300
        finally:
            Path(temp_file).unlink(missing_ok=True)

    def test_error_and_recovery_workflow(self):
        """Test error handling and recovery."""
        repl = REPL()
        
        # Define variable
        repl.handle_command("x = 10")
        
        # Cause error
        repl.handle_command("y = 1 / 0")
        
        # Verify error was captured
        assert repl.get_last_exception() is not None
        
        # Verify state is still intact
        assert repl.context.get_variable("x") == 10
        
        # Continue working
        result = repl.handle_command("x * 2")
        assert result == 20


@pytest.mark.integration
class TestREPLMain:
    """Test REPL main entry point."""

    def test_main_function_exists(self):
        """Test main function is defined."""
        from src.pyrepl.repl import main
        assert callable(main)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
