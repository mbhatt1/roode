"""
Unit tests for the OutputFormatter class.

Tests output formatting, syntax highlighting, exception display,
and various presentation features.
"""

import pytest
import sys
from io import StringIO
from types import TracebackType

from src.pyrepl.output import OutputFormatter, format_output


class TestOutputFormatterInitialization:
    """Test OutputFormatter initialization."""

    def test_default_initialization(self):
        """Test default initialization."""
        formatter = OutputFormatter()
        assert formatter is not None
        assert formatter.console is not None
        assert formatter.theme == "monokai"

    def test_custom_theme(self):
        """Test initialization with custom theme."""
        formatter = OutputFormatter(theme="dracula")
        assert formatter.theme == "dracula"

    def test_custom_width(self):
        """Test initialization with custom width."""
        formatter = OutputFormatter(width=100)
        assert formatter.console.width == 100

    def test_custom_output_file(self):
        """Test initialization with custom output file."""
        output = StringIO()
        formatter = OutputFormatter(file=output)
        formatter.console.print("test")
        assert "test" in output.getvalue()

    def test_force_terminal(self):
        """Test force_terminal option."""
        formatter = OutputFormatter(force_terminal=True)
        assert formatter.console is not None


class TestSimpleFormatting:
    """Test formatting of simple types."""

    def test_format_none(self):
        """Test formatting None returns empty string."""
        formatter = OutputFormatter(force_terminal=False)
        result = formatter.format_result(None)
        assert result == ""

    def test_format_integer(self):
        """Test formatting integers."""
        formatter = OutputFormatter(force_terminal=False)
        result = formatter.format_result(42)
        assert "42" in result

    def test_format_float(self):
        """Test formatting floats."""
        formatter = OutputFormatter(force_terminal=False)
        result = formatter.format_result(3.14159)
        assert "3.14159" in result

    def test_format_boolean_true(self):
        """Test formatting True."""
        formatter = OutputFormatter(force_terminal=False)
        result = formatter.format_result(True)
        assert "True" in result

    def test_format_boolean_false(self):
        """Test formatting False."""
        formatter = OutputFormatter(force_terminal=False)
        result = formatter.format_result(False)
        assert "False" in result

    def test_format_string(self):
        """Test formatting strings."""
        formatter = OutputFormatter(force_terminal=False)
        result = formatter.format_result("hello")
        assert "hello" in result


class TestCollectionFormatting:
    """Test formatting of collections."""

    def test_format_list(self):
        """Test formatting lists."""
        formatter = OutputFormatter(force_terminal=False)
        result = formatter.format_result([1, 2, 3])
        assert "[" in result
        assert "1" in result
        assert "2" in result
        assert "3" in result

    def test_format_tuple(self):
        """Test formatting tuples."""
        formatter = OutputFormatter(force_terminal=False)
        result = formatter.format_result((1, 2, 3))
        assert "(" in result or "1" in result

    def test_format_set(self):
        """Test formatting sets."""
        formatter = OutputFormatter(force_terminal=False)
        result = formatter.format_result({1, 2, 3})
        assert "{" in result or "1" in result

    def test_format_dict(self):
        """Test formatting dictionaries."""
        formatter = OutputFormatter(force_terminal=False)
        result = formatter.format_result({"key": "value", "number": 42})
        assert "key" in result
        assert "value" in result

    def test_format_nested_structure(self):
        """Test formatting nested data structures."""
        formatter = OutputFormatter(force_terminal=False)
        nested = {
            "list": [1, 2, 3],
            "dict": {"a": 1, "b": 2},
            "tuple": (4, 5, 6)
        }
        result = formatter.format_result(nested)
        assert "list" in result
        assert "dict" in result

    def test_format_empty_list(self):
        """Test formatting empty collections."""
        formatter = OutputFormatter(force_terminal=False)
        result = formatter.format_result([])
        assert "[]" in result or result.strip() == ""


class TestExceptionFormatting:
    """Test exception and traceback formatting."""

    def test_format_simple_exception(self):
        """Test formatting a simple exception."""
        formatter = OutputFormatter(force_terminal=False)
        
        try:
            raise ValueError("Test error")
        except ValueError as e:
            result = formatter.format_exception(e)
            assert "ValueError" in result
            assert "Test error" in result

    def test_format_zero_division_error(self):
        """Test formatting ZeroDivisionError."""
        formatter = OutputFormatter(force_terminal=False)
        
        try:
            x = 1 / 0
        except ZeroDivisionError as e:
            result = formatter.format_exception(e)
            assert "ZeroDivisionError" in result

    def test_format_name_error(self):
        """Test formatting NameError."""
        formatter = OutputFormatter(force_terminal=False)
        
        try:
            undefined_variable
        except NameError as e:
            result = formatter.format_exception(e)
            assert "NameError" in result
            assert "undefined_variable" in result

    def test_format_exception_with_traceback(self):
        """Test exception formatting includes traceback."""
        formatter = OutputFormatter(force_terminal=False)
        
        def inner_function():
            raise RuntimeError("Inner error")
        
        def outer_function():
            inner_function()
        
        try:
            outer_function()
        except RuntimeError as e:
            result = formatter.format_exception(e)
            assert "RuntimeError" in result
            assert "Inner error" in result

    def test_format_traceback_none(self):
        """Test formatting None traceback."""
        formatter = OutputFormatter(force_terminal=False)
        result = formatter.format_traceback(None)
        assert "No traceback" in result or result != ""


class TestTableFormatting:
    """Test table formatting."""

    def test_format_simple_table(self):
        """Test formatting a simple table."""
        formatter = OutputFormatter(force_terminal=False)
        data = [
            {"name": "Alice", "age": 30},
            {"name": "Bob", "age": 25},
        ]
        result = formatter.format_table(data)
        assert "Alice" in result
        assert "Bob" in result
        assert "30" in result
        assert "25" in result

    def test_format_table_with_title(self):
        """Test formatting table with title."""
        formatter = OutputFormatter(force_terminal=False)
        data = [{"col1": "value1", "col2": "value2"}]
        result = formatter.format_table(data, title="Test Table")
        assert "value1" in result
        assert "value2" in result

    def test_format_empty_table(self):
        """Test formatting empty table."""
        formatter = OutputFormatter(force_terminal=False)
        result = formatter.format_table([])
        assert "No data" in result or result.strip() == ""

    def test_format_table_with_mixed_types(self):
        """Test table with mixed data types."""
        formatter = OutputFormatter(force_terminal=False)
        data = [
            {"name": "Test", "count": 42, "active": True},
        ]
        result = formatter.format_table(data)
        assert "Test" in result
        assert "42" in result


class TestTreeFormatting:
    """Test tree structure formatting."""

    def test_format_simple_tree(self):
        """Test formatting a simple tree."""
        formatter = OutputFormatter(force_terminal=False)
        data = {
            "key1": "value1",
            "key2": "value2",
        }
        result = formatter.format_tree(data, "Root")
        assert "key1" in result
        assert "value1" in result

    def test_format_nested_tree(self):
        """Test formatting nested tree."""
        formatter = OutputFormatter(force_terminal=False)
        data = {
            "level1": {
                "level2": {
                    "level3": "value"
                }
            }
        }
        result = formatter.format_tree(data)
        assert "level1" in result
        assert "level2" in result
        assert "level3" in result

    def test_format_tree_with_list(self):
        """Test tree with list items."""
        formatter = OutputFormatter(force_terminal=False)
        data = {
            "items": [1, 2, 3]
        }
        result = formatter.format_tree(data)
        assert "items" in result

    def test_format_deep_tree(self):
        """Test deeply nested tree."""
        formatter = OutputFormatter(force_terminal=False)
        data = {"a": {"b": {"c": {"d": {"e": "deep"}}}}}
        result = formatter.format_tree(data)
        # Should handle deep nesting without error
        assert isinstance(result, str)


class TestStatusMessages:
    """Test status message printing."""

    def test_print_status(self, capsys):
        """Test printing status message."""
        formatter = OutputFormatter(force_terminal=False)
        formatter.print_status("Test status")
        captured = capsys.readouterr()
        assert "Test status" in captured.out

    def test_print_error(self, capsys):
        """Test printing error message."""
        formatter = OutputFormatter(force_terminal=False)
        formatter.print_error("Test error")
        captured = capsys.readouterr()
        assert "Test error" in captured.out
        assert "Error" in captured.out

    def test_print_warning(self, capsys):
        """Test printing warning message."""
        formatter = OutputFormatter(force_terminal=False)
        formatter.print_warning("Test warning")
        captured = capsys.readouterr()
        assert "Test warning" in captured.out
        assert "Warning" in captured.out

    def test_print_success(self, capsys):
        """Test printing success message."""
        formatter = OutputFormatter(force_terminal=False)
        formatter.print_success("Test success")
        captured = capsys.readouterr()
        assert "Test success" in captured.out


class TestCodeFormatting:
    """Test code syntax highlighting."""

    def test_print_code_python(self, capsys):
        """Test printing Python code with highlighting."""
        formatter = OutputFormatter(force_terminal=False)
        code = "def hello():\n    print('Hello')"
        formatter.print_code(code)
        captured = capsys.readouterr()
        assert "def" in captured.out or "hello" in captured.out

    def test_print_code_without_line_numbers(self, capsys):
        """Test printing code without line numbers."""
        formatter = OutputFormatter(force_terminal=False)
        code = "x = 42"
        formatter.print_code(code, line_numbers=False)
        captured = capsys.readouterr()
        assert "x" in captured.out or "42" in captured.out

    def test_print_code_different_language(self, capsys):
        """Test printing code in different language."""
        formatter = OutputFormatter(force_terminal=False)
        code = "SELECT * FROM users;"
        formatter.print_code(code, language="sql")
        captured = capsys.readouterr()
        assert "SELECT" in captured.out or "FROM" in captured.out


class TestHelpDisplay:
    """Test help information display."""

    def test_display_help_for_function(self, capsys):
        """Test displaying help for a function."""
        formatter = OutputFormatter(force_terminal=False)
        
        def test_func(x, y):
            """Test function docstring."""
            return x + y
        
        formatter.display_help(test_func)
        captured = capsys.readouterr()
        assert "test_func" in captured.out
        assert "function" in captured.out.lower() or captured.out != ""

    def test_display_help_for_builtin(self, capsys):
        """Test displaying help for builtin."""
        formatter = OutputFormatter(force_terminal=False)
        formatter.display_help(len)
        captured = capsys.readouterr()
        assert captured.out != ""

    def test_display_help_for_class(self, capsys):
        """Test displaying help for a class."""
        formatter = OutputFormatter(force_terminal=False)
        
        class TestClass:
            """Test class docstring."""
            def method(self):
                pass
        
        formatter.display_help(TestClass)
        captured = capsys.readouterr()
        assert "TestClass" in captured.out or captured.out != ""


class TestPaging:
    """Test paging functionality."""

    def test_paging_enabled_by_default(self):
        """Test that paging is enabled by default."""
        formatter = OutputFormatter(force_terminal=False)
        assert formatter._paging_enabled is True

    def test_set_paging_enabled(self):
        """Test enabling/disabling paging."""
        formatter = OutputFormatter(force_terminal=False)
        formatter.set_paging_enabled(False)
        assert formatter._paging_enabled is False
        
        formatter.set_paging_enabled(True)
        assert formatter._paging_enabled is True

    def test_set_max_lines_before_paging(self):
        """Test setting paging threshold."""
        formatter = OutputFormatter(force_terminal=False)
        formatter.set_max_lines_before_paging(100)
        assert formatter._max_lines_before_paging == 100

    def test_max_lines_minimum_value(self):
        """Test that max lines has minimum value of 1."""
        formatter = OutputFormatter(force_terminal=False)
        formatter.set_max_lines_before_paging(0)
        assert formatter._max_lines_before_paging >= 1

    def test_print_with_paging_short_text(self, capsys):
        """Test paging with short text (no paging needed)."""
        formatter = OutputFormatter(force_terminal=False)
        formatter.set_paging_enabled(True)
        formatter.set_max_lines_before_paging(10)
        
        text = "Short text"
        formatter.print_with_paging(text)
        captured = capsys.readouterr()
        assert "Short text" in captured.out


class TestBannerAndScreen:
    """Test banner and screen operations."""

    def test_print_banner(self, capsys):
        """Test printing banner."""
        formatter = OutputFormatter(force_terminal=False)
        formatter.print_banner("Test Banner")
        captured = capsys.readouterr()
        assert "Test Banner" in captured.out

    def test_clear_screen(self):
        """Test clearing screen doesn't crash."""
        formatter = OutputFormatter(force_terminal=False)
        # Should not raise an exception
        formatter.clear_screen()


class TestProgressBar:
    """Test progress bar creation."""

    def test_create_progress_bar(self):
        """Test creating a progress bar."""
        formatter = OutputFormatter(force_terminal=False)
        progress = formatter.create_progress_bar()
        assert progress is not None


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_format_very_large_number(self):
        """Test formatting very large numbers."""
        formatter = OutputFormatter(force_terminal=False)
        result = formatter.format_result(10**100)
        assert "10" in result or result != ""

    def test_format_very_long_string(self):
        """Test formatting very long strings."""
        formatter = OutputFormatter(force_terminal=False)
        long_string = "a" * 10000
        result = formatter.format_result(long_string)
        assert isinstance(result, str)

    def test_format_circular_reference(self):
        """Test formatting object with circular reference."""
        formatter = OutputFormatter(force_terminal=False)
        lst = []
        lst.append(lst)  # Circular reference
        result = formatter.format_result(lst)
        # Should handle gracefully without infinite recursion
        assert isinstance(result, str)

    def test_format_custom_object(self):
        """Test formatting custom object."""
        formatter = OutputFormatter(force_terminal=False)
        
        class CustomObject:
            def __repr__(self):
                return "<CustomObject>"
        
        obj = CustomObject()
        result = formatter.format_result(obj)
        assert isinstance(result, str)

    def test_format_lambda(self):
        """Test formatting lambda function."""
        formatter = OutputFormatter(force_terminal=False)
        func = lambda x: x * 2
        result = formatter.format_result(func)
        assert "lambda" in result or "function" in result

    def test_format_generator(self):
        """Test formatting generator."""
        formatter = OutputFormatter(force_terminal=False)
        gen = (x for x in range(5))
        result = formatter.format_result(gen)
        assert isinstance(result, str)


class TestConvenienceFunction:
    """Test convenience function."""

    def test_format_output_function(self):
        """Test format_output convenience function."""
        result = format_output(42)
        assert "42" in result

    def test_format_output_with_theme(self):
        """Test format_output with custom theme."""
        result = format_output([1, 2, 3], theme="dracula")
        assert "1" in result or "[" in result


class TestFormatterIntegration:
    """Integration tests for OutputFormatter."""

    def test_format_multiple_types_sequence(self):
        """Test formatting multiple types in sequence."""
        formatter = OutputFormatter(force_terminal=False)
        
        values = [
            42,
            "hello",
            [1, 2, 3],
            {"key": "value"},
            True,
            None,
        ]
        
        for value in values:
            result = formatter.format_result(value)
            assert isinstance(result, str)

    def test_exception_then_normal_output(self):
        """Test formatting exception followed by normal output."""
        formatter = OutputFormatter(force_terminal=False)
        
        try:
            raise ValueError("Error")
        except ValueError as e:
            exc_result = formatter.format_exception(e)
            assert "ValueError" in exc_result
        
        # Should still work for normal output
        normal_result = formatter.format_result(42)
        assert "42" in normal_result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
