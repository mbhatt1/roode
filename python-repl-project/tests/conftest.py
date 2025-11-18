"""
Pytest configuration and shared fixtures.

This module provides common fixtures and configuration for all tests
in the PyREPL test suite.
"""

import os
import sys
import tempfile
import pytest
from pathlib import Path
from unittest.mock import Mock

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from pyrepl.context import ExecutionContext
from pyrepl.history import HistoryManager
from pyrepl.completion import CompletionEngine
from pyrepl.output import OutputFormatter
from pyrepl.config import Config


# ============================================================================
# Context Fixtures
# ============================================================================

@pytest.fixture
def execution_context():
    """
    Provides a clean ExecutionContext for testing.
    
    Returns:
        ExecutionContext: Fresh execution context instance
    """
    return ExecutionContext()


@pytest.fixture
def context_with_variables():
    """
    Provides an ExecutionContext pre-populated with test variables.
    
    Returns:
        ExecutionContext: Context with test variables defined
    """
    context = ExecutionContext()
    context.execute_code("x = 42")
    context.execute_code("y = 'hello'")
    context.execute_code("z = [1, 2, 3]")
    context.execute_code("def test_func(a, b): return a + b")
    return context


@pytest.fixture
def context_with_imports():
    """
    Provides an ExecutionContext with common imports.
    
    Returns:
        ExecutionContext: Context with modules imported
    """
    context = ExecutionContext()
    context.execute_code("import os")
    context.execute_code("import sys")
    context.execute_code("import math")
    return context


# ============================================================================
# History Fixtures
# ============================================================================

@pytest.fixture
def temp_db_path():
    """
    Provides a temporary database path for testing.
    
    Yields:
        str: Path to temporary database file
    """
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
    temp_file.close()
    db_path = temp_file.name
    
    yield db_path
    
    # Cleanup
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture
def history_manager(temp_db_path):
    """
    Provides a HistoryManager with temporary database.
    
    Args:
        temp_db_path: Path to temporary database
        
    Returns:
        HistoryManager: Fresh history manager instance
    """
    return HistoryManager(db_path=temp_db_path, max_history=1000)


@pytest.fixture
def history_with_commands(temp_db_path):
    """
    Provides a HistoryManager pre-populated with test commands.
    
    Args:
        temp_db_path: Path to temporary database
        
    Returns:
        HistoryManager: History manager with test commands
    """
    history = HistoryManager(db_path=temp_db_path)
    commands = [
        "print('Hello, World!')",
        "x = 42",
        "import math",
        "math.sqrt(16)",
        "for i in range(5): print(i)",
        "def greet(name): return f'Hello, {name}!'",
        "greet('Python')",
    ]
    for cmd in commands:
        history.add_command(cmd)
    return history


# ============================================================================
# Completion Fixtures
# ============================================================================

@pytest.fixture
def completion_engine():
    """
    Provides a CompletionEngine for testing.
    
    Returns:
        CompletionEngine: Completion engine instance
    """
    return CompletionEngine(use_jedi=False)


@pytest.fixture
def completion_engine_with_jedi():
    """
    Provides a CompletionEngine with Jedi enabled (if available).
    
    Returns:
        CompletionEngine: Completion engine with Jedi
    """
    return CompletionEngine(use_jedi=True)


@pytest.fixture
def mock_context():
    """
    Provides a mock execution context for completion testing.
    
    Returns:
        Mock: Mock context with locals and globals
    """
    context = Mock()
    context.locals = {
        "my_var": 42,
        "my_string": "test",
        "my_list": [1, 2, 3],
        "my_func": lambda x: x * 2,
    }
    context.globals = {
        "global_var": "global",
        "os": __import__("os"),
        "sys": __import__("sys"),
    }
    return context


# ============================================================================
# Output Fixtures
# ============================================================================

@pytest.fixture
def output_formatter():
    """
    Provides an OutputFormatter for testing.
    
    Returns:
        OutputFormatter: Output formatter instance
    """
    return OutputFormatter(force_terminal=False)


@pytest.fixture
def output_formatter_with_theme():
    """
    Provides an OutputFormatter with a specific theme.
    
    Returns:
        OutputFormatter: Output formatter with custom theme
    """
    return OutputFormatter(theme="monokai", force_terminal=False)


# ============================================================================
# Config Fixtures
# ============================================================================

@pytest.fixture
def default_config():
    """
    Provides a default configuration object.
    
    Returns:
        Config: Default configuration
    """
    return Config()


@pytest.fixture
def custom_config():
    """
    Provides a customized configuration object.
    
    Returns:
        Config: Custom configuration for testing
    """
    config = Config()
    config.appearance.theme = "monokai"
    config.appearance.prompt_style = ">>> "
    config.history.history_size = 500
    config.behavior.auto_suggest = True
    return config


# ============================================================================
# File System Fixtures
# ============================================================================

@pytest.fixture
def temp_directory():
    """
    Provides a temporary directory for file operations.
    
    Yields:
        Path: Path to temporary directory
    """
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    
    # Cleanup
    import shutil
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)


@pytest.fixture
def temp_file():
    """
    Provides a temporary file for testing.
    
    Yields:
        str: Path to temporary file
    """
    temp = tempfile.NamedTemporaryFile(delete=False, mode='w')
    temp.close()
    
    yield temp.name
    
    # Cleanup
    if os.path.exists(temp.name):
        os.unlink(temp.name)


# ============================================================================
# Mock Fixtures
# ============================================================================

@pytest.fixture
def mock_stdin():
    """
    Provides a mock stdin for testing input.
    
    Returns:
        Mock: Mock stdin object
    """
    mock = Mock()
    mock.readline = Mock(return_value="test input\n")
    return mock


@pytest.fixture
def mock_stdout():
    """
    Provides a mock stdout for capturing output.
    
    Returns:
        Mock: Mock stdout object
    """
    from io import StringIO
    return StringIO()


# ============================================================================
# Integration Test Fixtures
# ============================================================================

@pytest.fixture
def full_repl_setup(temp_db_path):
    """
    Provides a complete REPL setup with all components.
    
    Args:
        temp_db_path: Path to temporary database
        
    Returns:
        dict: Dictionary containing all REPL components
    """
    context = ExecutionContext()
    history = HistoryManager(db_path=temp_db_path)
    completion = CompletionEngine(use_jedi=False)
    output = OutputFormatter(force_terminal=False)
    
    return {
        "context": context,
        "history": history,
        "completion": completion,
        "output": output,
    }


# ============================================================================
# Pytest Configuration
# ============================================================================

def pytest_configure(config):
    """
    Pytest configuration hook.
    
    Args:
        config: Pytest config object
    """
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "unit: marks tests as unit tests"
    )
    config.addinivalue_line(
        "markers", "requires_jedi: marks tests that require Jedi library"
    )


def pytest_collection_modifyitems(config, items):
    """
    Modify test collection to add markers automatically.
    
    Args:
        config: Pytest config object
        items: List of test items
    """
    for item in items:
        # Add 'unit' marker to all tests by default
        if "integration" not in item.keywords:
            item.add_marker(pytest.mark.unit)
        
        # Add 'slow' marker to integration tests
        if "integration" in item.keywords:
            item.add_marker(pytest.mark.slow)


# ============================================================================
# Assertion Helpers
# ============================================================================

def assert_code_executes(context, code):
    """
    Helper to assert that code executes without error.
    
    Args:
        context: ExecutionContext instance
        code: Code string to execute
        
    Raises:
        AssertionError: If code execution fails
    """
    try:
        context.execute_code(code)
    except Exception as e:
        pytest.fail(f"Code execution failed: {e}")


def assert_variable_exists(context, var_name):
    """
    Helper to assert that a variable exists in context.
    
    Args:
        context: ExecutionContext instance
        var_name: Variable name to check
        
    Raises:
        AssertionError: If variable doesn't exist
    """
    assert context.has_variable(var_name), f"Variable '{var_name}' does not exist"


def assert_variable_equals(context, var_name, expected_value):
    """
    Helper to assert that a variable has a specific value.
    
    Args:
        context: ExecutionContext instance
        var_name: Variable name to check
        expected_value: Expected value
        
    Raises:
        AssertionError: If values don't match
    """
    actual_value = context.get_variable(var_name)
    assert actual_value == expected_value, \
        f"Variable '{var_name}' expected {expected_value}, got {actual_value}"
