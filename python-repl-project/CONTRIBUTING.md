# Contributing to PyREPL

Thank you for your interest in contributing to PyREPL! This document provides guidelines and instructions for contributing to the project.

## Table of Contents

1. [Code of Conduct](#code-of-conduct)
2. [Getting Started](#getting-started)
3. [Development Setup](#development-setup)
4. [Project Structure](#project-structure)
5. [Development Workflow](#development-workflow)
6. [Coding Standards](#coding-standards)
7. [Testing](#testing)
8. [Documentation](#documentation)
9. [Submitting Changes](#submitting-changes)
10. [Release Process](#release-process)

## Code of Conduct

### Our Pledge

We are committed to providing a welcoming and inclusive environment for all contributors. We expect everyone to:

- Be respectful and considerate
- Use welcoming and inclusive language
- Accept constructive criticism gracefully
- Focus on what is best for the community
- Show empathy towards other community members

### Unacceptable Behavior

- Harassment, discrimination, or exclusionary behavior
- Trolling, insulting comments, or personal attacks
- Public or private harassment
- Publishing others' private information without permission
- Any conduct that could reasonably be considered inappropriate

## Getting Started

### Prerequisites

Before you begin, ensure you have:

- Python 3.9 or higher installed
- Git installed and configured
- A GitHub account
- Basic understanding of Python and terminal usage

### Find an Issue

1. **Browse existing issues**: Check the [issue tracker](https://github.com/yourusername/pyrepl/issues) for open issues
2. **Look for beginner-friendly issues**: Issues labeled `good first issue` or `help wanted` are great starting points
3. **Ask questions**: Don't hesitate to comment on issues to ask for clarification

### Propose New Features

If you have an idea for a new feature:

1. Check if a similar feature has been proposed
2. Open a new issue with the `enhancement` label
3. Describe the feature, its use case, and potential implementation
4. Wait for feedback from maintainers before starting work

## Development Setup

### 1. Fork and Clone

```bash
# Fork the repository on GitHub, then clone your fork
git clone https://github.com/YOUR_USERNAME/pyrepl.git
cd pyrepl

# Add the upstream repository
git remote add upstream https://github.com/yourusername/pyrepl.git
```

### 2. Create a Virtual Environment

```bash
# Create virtual environment
python -m venv venv

# Activate it
# On macOS/Linux:
source venv/bin/activate
# On Windows:
venv\Scripts\activate
```

### 3. Install Development Dependencies

```bash
# Install package in editable mode with dev dependencies
pip install -e ".[dev]"

# Verify installation
pyrepl --version
```

### 4. Install Development Tools

```bash
# Install additional tools
pip install pre-commit
pre-commit install
```

## Project Structure

```
python-repl-project/
├── src/
│   └── pyrepl/              # Main package
│       ├── __init__.py      # Package initialization
│       ├── __main__.py      # Entry point
│       ├── repl.py          # Main REPL class
│       ├── context.py       # Execution context
│       ├── completion.py    # Auto-completion
│       ├── history.py       # History management
│       ├── output.py        # Output formatting
│       ├── config.py        # Configuration
│       └── input_handler.py # Input handling
├── tests/                   # Test suite
│   ├── test_repl.py
│   ├── test_context.py
│   ├── test_completion.py
│   ├── test_history.py
│   └── test_output.py
├── examples/                # Example scripts
│   ├── basic_usage.py
│   └── advanced_features.py
├── docs/                    # Documentation
├── pyproject.toml          # Project metadata
├── README.md               # Project overview
├── USAGE.md                # Usage guide
└── CONTRIBUTING.md         # This file
```

### Key Components

#### REPL Engine (`repl.py`)
- Main REPL loop
- Command handling
- Signal management
- Special command processing

#### Execution Context (`context.py`)
- Namespace management
- Code execution
- Variable tracking
- Module import tracking

#### Completion Engine (`completion.py`)
- Context-aware completions
- Attribute completions
- Module completions
- Smart suggestions

#### History Manager (`history.py`)
- SQLite-based history storage
- History search
- Session management
- Statistics tracking

#### Output Formatter (`output.py`)
- Rich-based formatting
- Syntax highlighting
- Exception formatting
- Status messages

## Development Workflow

### 1. Create a Feature Branch

```bash
# Update your main branch
git checkout main
git pull upstream main

# Create a feature branch
git checkout -b feature/my-new-feature
```

### 2. Make Changes

- Write clean, readable code
- Follow the coding standards (see below)
- Add tests for new functionality
- Update documentation as needed

### 3. Test Your Changes

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=pyrepl --cov-report=html

# Run specific test file
pytest tests/test_repl.py

# Run specific test
pytest tests/test_repl.py::test_basic_execution
```

### 4. Lint and Format

```bash
# Format code with black
black src/ tests/

# Sort imports with isort
isort src/ tests/

# Lint with ruff
ruff check src/ tests/

# Type check with mypy
mypy src/
```

### 5. Commit Changes

```bash
# Stage changes
git add .

# Commit with descriptive message
git commit -m "Add feature: description of changes"
```

Follow commit message conventions:
- Use present tense ("Add feature" not "Added feature")
- Use imperative mood ("Move cursor to..." not "Moves cursor to...")
- Keep first line under 72 characters
- Add detailed description after blank line if needed

### 6. Push and Create Pull Request

```bash
# Push to your fork
git push origin feature/my-new-feature
```

Then create a Pull Request on GitHub.

## Coding Standards

### Python Style Guide

We follow [PEP 8](https://pep8.org/) with some modifications:

- **Line length**: 100 characters (not 79)
- **Indentation**: 4 spaces
- **Quotes**: Prefer double quotes for strings
- **Imports**: Grouped and sorted (use `isort`)

### Type Hints

Use type hints for all functions:

```python
from typing import Optional, List, Dict, Any

def process_items(items: List[str], limit: Optional[int] = None) -> Dict[str, Any]:
    """
    Process a list of items.
    
    Args:
        items: List of item names
        limit: Optional maximum number to process
        
    Returns:
        Dictionary with processing results
    """
    results: Dict[str, Any] = {}
    # Implementation...
    return results
```

### Documentation

#### Docstrings

Use Google-style docstrings:

```python
def my_function(arg1: str, arg2: int = 0) -> bool:
    """
    Brief description of the function.
    
    Longer description if needed. Can span multiple
    lines and include more details.
    
    Args:
        arg1: Description of arg1
        arg2: Description of arg2 (default: 0)
        
    Returns:
        Description of return value
        
    Raises:
        ValueError: When arg2 is negative
        
    Example:
        >>> my_function("hello", 5)
        True
    """
    if arg2 < 0:
        raise ValueError("arg2 must be non-negative")
    return len(arg1) > arg2
```

#### Comments

- Write clear, concise comments
- Explain *why*, not *what*
- Use comments sparingly - prefer self-documenting code
- Use `# TODO:` for temporary code or future improvements
- Use `# FIXME:` for known issues

### Code Organization

#### Imports

Group imports in this order:

```python
# Standard library imports
import os
import sys
from typing import Optional, List

# Third-party imports
from prompt_toolkit import PromptSession
from rich.console import Console

# Local application imports
from .context import ExecutionContext
from .config import Config
```

#### Class Structure

Organize class members in this order:

```python
class MyClass:
    """Class docstring."""
    
    # Class variables
    CLASS_CONSTANT = "value"
    
    def __init__(self, arg: str):
        """Initialize instance."""
        self.arg = arg
        self._private_var = None
    
    # Public methods
    def public_method(self) -> str:
        """Public method."""
        return self.arg
    
    # Private methods
    def _private_method(self) -> None:
        """Private method."""
        pass
    
    # Special methods
    def __str__(self) -> str:
        """String representation."""
        return f"MyClass({self.arg})"
```

### Error Handling

- Use specific exception types
- Provide helpful error messages
- Don't catch exceptions silently
- Clean up resources in `finally` blocks

```python
def read_config(path: str) -> Config:
    """Read configuration from file."""
    try:
        with open(path, 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        raise ConfigError(f"Config file not found: {path}")
    except json.JSONDecodeError as e:
        raise ConfigError(f"Invalid JSON in config file: {e}")
    except PermissionError:
        raise ConfigError(f"Permission denied reading config: {path}")
    
    return Config.from_dict(data)
```

## Testing

### Writing Tests

- Write tests for all new features
- Write tests for bug fixes
- Aim for high code coverage (>80%)
- Use descriptive test names

```python
import pytest
from pyrepl.context import ExecutionContext

class TestExecutionContext:
    """Tests for ExecutionContext class."""
    
    def test_basic_execution(self):
        """Test basic code execution."""
        ctx = ExecutionContext()
        result = ctx.execute_code("2 + 2")
        assert result == 4
    
    def test_variable_persistence(self):
        """Test that variables persist across executions."""
        ctx = ExecutionContext()
        ctx.execute_code("x = 42")
        result = ctx.execute_code("x * 2")
        assert result == 84
    
    def test_exception_handling(self):
        """Test that exceptions are properly raised."""
        ctx = ExecutionContext()
        with pytest.raises(ZeroDivisionError):
            ctx.execute_code("1 / 0")
```

### Test Structure

- Use fixtures for common setup
- Use parametrize for similar tests with different inputs
- Group related tests in classes

```python
@pytest.fixture
def context():
    """Create a fresh context for testing."""
    return ExecutionContext()

@pytest.mark.parametrize("code,expected", [
    ("2 + 2", 4),
    ("10 * 5", 50),
    ("2 ** 8", 256),
])
def test_arithmetic(context, code, expected):
    """Test arithmetic operations."""
    result = context.execute_code(code)
    assert result == expected
```

### Running Tests

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_context.py

# Run tests matching pattern
pytest -k "test_completion"

# Run with coverage
pytest --cov=pyrepl --cov-report=term-missing

# Run with pdb on failure
pytest --pdb

# Run only failed tests from last run
pytest --lf
```

## Documentation

### Updating Documentation

When adding features or making changes:

1. Update relevant docstrings
2. Update `USAGE.md` if user-facing
3. Update `README.md` if architecture changes
4. Add examples to `examples/` directory
5. Update `CHANGELOG.md`

### Building Documentation

If we add Sphinx documentation:

```bash
cd docs/
make html
open _build/html/index.html
```

## Submitting Changes

### Pull Request Guidelines

1. **Keep PRs focused**: One feature or fix per PR
2. **Write a clear title**: Describe what the PR does
3. **Provide description**: Explain why and how
4. **Reference issues**: Use "Fixes #123" or "Closes #123"
5. **Update changelog**: Add entry to `CHANGELOG.md`
6. **Ensure CI passes**: All tests and checks must pass

### PR Template

```markdown
## Description
Brief description of the changes

## Motivation and Context
Why is this change needed? What problem does it solve?

## Type of Change
- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to change)
- [ ] Documentation update

## How Has This Been Tested?
Describe the tests you ran to verify your changes

## Checklist
- [ ] My code follows the code style of this project
- [ ] I have added tests to cover my changes
- [ ] All new and existing tests passed
- [ ] I have updated the documentation accordingly
- [ ] I have added an entry to CHANGELOG.md
```

### Code Review Process

1. **Be responsive**: Respond to review comments promptly
2. **Be open**: Accept feedback constructively
3. **Explain**: Clarify your design decisions if questioned
4. **Iterate**: Make requested changes and push updates
5. **Resolve conversations**: Mark conversations as resolved when addressed

### After Merge

1. Delete your feature branch
2. Update your local repository
3. Celebrate! 🎉

```bash
# Delete local branch
git branch -d feature/my-new-feature

# Delete remote branch
git push origin --delete feature/my-new-feature

# Update main
git checkout main
git pull upstream main
```

## Release Process

### Versioning

We use [Semantic Versioning](https://semver.org/):

- **MAJOR**: Breaking changes
- **MINOR**: New features (backwards compatible)
- **PATCH**: Bug fixes (backwards compatible)

### Release Checklist

For maintainers:

1. Update version in `pyproject.toml`
2. Update `CHANGELOG.md`
3. Create and push tag: `git tag v1.0.0 && git push origin v1.0.0`
4. Build package: `python -m build`
5. Upload to PyPI: `python -m twine upload dist/*`
6. Create GitHub release with notes

## Getting Help

### Communication Channels

- **GitHub Issues**: Bug reports and feature requests
- **GitHub Discussions**: Questions and general discussion
- **Email**: maintainer@example.com (for security issues)

### Questions?

- Check existing issues and discussions
- Read the documentation
- Ask in GitHub Discussions
- Be specific about your question
- Provide context and examples

## Recognition

Contributors are recognized in:

- `CONTRIBUTORS.md` file
- GitHub contributors page
- Release notes

## License

By contributing to PyREPL, you agree that your contributions will be licensed under the MIT License.

---

Thank you for contributing to PyREPL! Your efforts help make this project better for everyone. 🚀
