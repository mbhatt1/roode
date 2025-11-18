# Project Structure

This document provides a detailed breakdown of the project directory structure with explanations for each component.

## Directory Tree

```
python-repl-project/
│
├── README.md                      # Project overview and quick start
├── ARCHITECTURE.md                # Comprehensive architecture documentation
├── PROJECT_STRUCTURE.md           # This file
├── LICENSE                        # MIT or Apache 2.0
├── setup.py                       # Package installation (setuptools)
├── pyproject.toml                 # Modern Python project metadata
├── requirements.txt               # Production dependencies
├── requirements-dev.txt           # Development dependencies
├── .gitignore                     # Git ignore patterns
├── .editorconfig                  # Editor configuration
├── Makefile                       # Common development tasks
│
├── repl/                          # Main package directory
│   ├── __init__.py               # Package initialization, version info
│   ├── __main__.py               # Entry point (python -m repl)
│   │
│   ├── core.py                    # REPLCore class - main event loop
│   │   └── Classes: REPLCore
│   │   └── Functions: main()
│   │
│   ├── input_handler.py           # Input handling with prompt_toolkit
│   │   └── Classes: InputHandler, MultilineValidator
│   │   └── Functions: create_key_bindings(), is_complete()
│   │
│   ├── parser.py                  # Code parsing and AST analysis
│   │   └── Classes: CodeParser, ParseResult
│   │   └── Functions: parse_code(), is_expression(), extract_assignments()
│   │
│   ├── executor.py                # Code execution engine
│   │   └── Classes: CodeExecutor, ExecutionResult, ExecutionContext
│   │   └── Functions: execute_sync(), execute_async(), capture_output()
│   │
│   ├── namespace.py               # Namespace and variable management
│   │   └── Classes: NamespaceManager, Variable
│   │   └── Functions: create_magic_variables(), filter_internal()
│   │
│   ├── completion.py              # Tab completion engine
│   │   └── Classes: TabCompleter, CompletionContext
│   │   └── Functions: get_completions(), complete_attribute(), complete_import()
│   │
│   ├── highlighter.py             # Syntax highlighting
│   │   └── Classes: SyntaxHighlighter, PygmentsStyleAdapter
│   │   └── Functions: highlight_code(), get_style()
│   │
│   ├── history.py                 # Command history with persistence
│   │   └── Classes: HistoryManager, HistoryEntry, HistoryDatabase
│   │   └── Functions: search_history(), filter_by_date()
│   │
│   ├── exception_handler.py       # Exception formatting and display
│   │   └── Classes: ExceptionHandler, FormattedException
│   │   └── Functions: format_exception(), get_error_context(), suggest_fix()
│   │
│   ├── inspector.py               # Variable introspection
│   │   └── Classes: VariableInspector, InspectionResult
│   │   └── Functions: inspect_object(), get_type_hierarchy(), get_memory_size()
│   │
│   ├── output_formatter.py        # Result formatting and display
│   │   └── Classes: OutputFormatter, FormatterRegistry
│   │   └── Functions: format_output(), register_formatter(), format_by_type()
│   │
│   ├── session.py                 # Session save/load functionality
│   │   └── Classes: SessionManager, Session, SessionMetadata
│   │   └── Functions: save_session(), load_session(), validate_session()
│   │
│   ├── config.py                  # Configuration management
│   │   └── Classes: Configuration, ConfigLoader, ConfigValidator
│   │   └── Functions: load_config(), merge_configs(), validate_config()
│   │
│   ├── plugins/                   # Plugin system implementation
│   │   ├── __init__.py
│   │   │
│   │   ├── base.py               # Plugin base classes and interfaces
│   │   │   └── Classes: Plugin (ABC), PluginMetadata
│   │   │   └── Functions: validate_plugin()
│   │   │
│   │   ├── manager.py            # Plugin lifecycle management
│   │   │   └── Classes: PluginManager, PluginState
│   │   │   └── Functions: load_plugin(), enable_plugin(), disable_plugin()
│   │   │
│   │   ├── hooks.py              # Hook system for plugin integration
│   │   │   └── Classes: HookSystem, Hook, HookRegistry
│   │   │   └── Functions: register_hook(), call_hook(), priority_sort()
│   │   │
│   │   └── discovery.py          # Plugin discovery mechanisms
│   │       └── Classes: PluginDiscovery, PluginInfo
│   │       └── Functions: scan_directory(), find_entry_points()
│   │
│   └── utils/                     # Utility modules
│       ├── __init__.py
│       │
│       ├── logger.py             # Logging configuration
│       │   └── Functions: setup_logger(), get_logger()
│       │
│       ├── colors.py             # Color and theme utilities
│       │   └── Classes: ColorScheme, Theme
│       │   └── Functions: apply_color(), get_ansi_code()
│       │
│       └── validators.py         # Input validation utilities
│           └── Functions: validate_python_identifier(), validate_path()
│
├── plugins/                       # Example and built-in plugins
│   │
│   ├── example_plugin.py         # Template plugin showing all features
│   │   └── Classes: ExamplePlugin(Plugin)
│   │
│   ├── timer_plugin.py           # Execution timing plugin
│   │   └── Classes: TimerPlugin(Plugin)
│   │   └── Features: Time code execution, show statistics
│   │
│   ├── export_plugin.py          # Session export plugin
│   │   └── Classes: ExportPlugin(Plugin)
│   │   └── Features: Export to .py, .ipynb, .md formats
│   │
│   ├── debug_plugin.py           # Enhanced debugging plugin
│   │   └── Classes: DebugPlugin(Plugin)
│   │   └── Features: Breakpoints, step execution, variable watch
│   │
│   ├── memory_plugin.py          # Memory profiling plugin
│   │   └── Classes: MemoryPlugin(Plugin)
│   │   └── Features: Track memory usage, detect leaks
│   │
│   └── ai_assistant_plugin.py    # AI code suggestions (future)
│       └── Classes: AIAssistantPlugin(Plugin)
│       └── Features: Code completion, explanations, bug fixes
│
├── tests/                         # Test suite
│   ├── __init__.py
│   ├── conftest.py               # Pytest configuration and fixtures
│   │
│   ├── test_core.py              # Test REPL core functionality
│   ├── test_input_handler.py    # Test input handling
│   ├── test_parser.py            # Test code parsing
│   ├── test_executor.py          # Test code execution
│   ├── test_namespace.py         # Test namespace management
│   ├── test_completion.py        # Test tab completion
│   ├── test_highlighter.py       # Test syntax highlighting
│   ├── test_history.py           # Test history management
│   ├── test_exception_handler.py # Test exception handling
│   ├── test_inspector.py         # Test variable inspection
│   ├── test_output_formatter.py  # Test output formatting
│   ├── test_session.py           # Test session save/load
│   ├── test_config.py            # Test configuration
│   ├── test_plugins.py           # Test plugin system
│   │
│   ├── integration/              # Integration tests
│   │   ├── __init__.py
│   │   ├── test_repl_integration.py    # End-to-end REPL tests
│   │   ├── test_plugin_integration.py  # Plugin integration tests
│   │   └── test_session_workflow.py    # Session workflow tests
│   │
│   ├── fixtures/                 # Test data and fixtures
│   │   ├── sample_code.py
│   │   ├── sample_session.json
│   │   └── test_plugin.py
│   │
│   └── performance/              # Performance benchmarks
│       ├── test_completion_perf.py
│       ├── test_history_perf.py
│       └── test_execution_perf.py
│
├── docs/                          # Documentation
│   │
│   ├── user_guide.md             # User documentation
│   │   └── Sections: Installation, Basic Usage, Features, Configuration
│   │
│   ├── plugin_development.md     # Plugin development guide
│   │   └── Sections: Plugin API, Hooks, Examples, Best Practices
│   │
│   ├── api_reference.md          # API documentation
│   │   └── Sections: All public classes and functions
│   │
│   ├── contributing.md           # Contribution guidelines
│   │   └── Sections: Setup, Testing, Code Style, PR Process
│   │
│   ├── changelog.md              # Version history and changes
│   │
│   └── examples/                 # Example documentation
│       ├── basic_usage.md        # Basic REPL usage
│       ├── advanced_features.md  # Advanced features
│       ├── plugin_examples.md    # Plugin usage examples
│       └── session_management.md # Session save/load examples
│
├── config/                        # Configuration files
│   │
│   ├── default_config.yaml       # Default configuration
│   │
│   └── themes/                   # Color scheme themes
│       ├── monokai.yaml          # Monokai theme
│       ├── solarized_dark.yaml   # Solarized Dark
│       ├── solarized_light.yaml  # Solarized Light
│       ├── dracula.yaml          # Dracula theme
│       └── default.yaml          # Default theme
│
└── examples/                      # Usage examples
    │
    ├── sample_session.json       # Example saved session
    ├── sample_session.pkl        # Pickle format session
    │
    ├── plugin_example.py         # Example plugin implementation
    │
    ├── custom_formatter.py       # Custom output formatter example
    │
    ├── basic_usage.py            # Basic REPL usage demo
    │
    └── scripts/                  # Utility scripts
        ├── generate_docs.py      # Generate API documentation
        └── benchmark.py          # Performance benchmarking
```

## Key Files Explained

### Root Level Files

#### `README.md`
- Project overview
- Features list
- Installation instructions
- Quick start guide
- Links to documentation
- Screenshots/GIFs of REPL in action
- Badge shields (build status, coverage, version)

#### `ARCHITECTURE.md`
- Comprehensive system design
- Component diagrams
- Data flow descriptions
- Design decisions and rationale
- Performance considerations
- Security considerations

#### `setup.py`
```python
# Package installation configuration
# - Package metadata
# - Dependencies
# - Entry points (console_scripts)
# - Package data inclusion
```

#### `pyproject.toml`
```toml
# Modern Python project configuration
# - Build system requirements
# - Tool configurations (black, mypy, pytest)
# - Project metadata
```

#### `requirements.txt`
```
# Production dependencies
prompt-toolkit>=3.0.0
pygments>=2.0.0
pyyaml>=6.0
```

#### `requirements-dev.txt`
```
# Development dependencies
-r requirements.txt
pytest>=7.0.0
pytest-cov>=4.0.0
pytest-asyncio>=0.21.0
black>=23.0.0
mypy>=1.0.0
ruff>=0.1.0
```

#### `Makefile`
```makefile
# Common development tasks
# - install: Install dependencies
# - test: Run tests
# - coverage: Generate coverage report
# - lint: Run linters
# - format: Format code
# - docs: Generate documentation
```

### Core Module Files

#### `repl/__init__.py`
```python
"""Python REPL - Feature-rich interactive Python interpreter."""

__version__ = "1.0.0"
__author__ = "Your Name"

from repl.core import REPLCore
from repl.config import Configuration

__all__ = ["REPLCore", "Configuration"]
```

#### `repl/__main__.py`
```python
"""Entry point for running REPL as a module: python -m repl"""

import sys
from repl.core import main

if __name__ == "__main__":
    sys.exit(main())
```

### Plugin Files

#### Structure of a Plugin
```python
# plugins/example_plugin.py
from repl.plugins.base import Plugin

class ExamplePlugin(Plugin):
    @property
    def name(self) -> str:
        return "example"
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    def initialize(self, repl_core):
        # Setup code
        pass
    
    def on_pre_execute(self, code: str) -> str:
        # Modify code before execution
        return code
    
    def register_commands(self):
        # Register custom commands
        return {"%example": self.example_command}
    
    def example_command(self, args):
        # Command implementation
        pass
```

### Test Files

#### Test Structure
```python
# tests/test_core.py
import pytest
from repl.core import REPLCore

class TestREPLCore:
    def test_initialization(self):
        # Test REPL initialization
        pass
    
    def test_execution_loop(self):
        # Test main loop
        pass
    
    @pytest.mark.asyncio
    async def test_async_execution(self):
        # Test async code execution
        pass
```

#### Fixtures (conftest.py)
```python
# tests/conftest.py
import pytest
from repl.core import REPLCore
from repl.config import Configuration

@pytest.fixture
def repl_core():
    """Create a REPL instance for testing."""
    config = Configuration()
    return REPLCore(config)

@pytest.fixture
def mock_namespace():
    """Create a mock namespace for testing."""
    return {"x": 1, "y": 2}
```

### Configuration Files

#### Default Configuration (config/default_config.yaml)
```yaml
repl:
  prompt: ">>> "
  continuation_prompt: "... "
  auto_save: true
  auto_save_interval: 300

display:
  syntax_highlighting: true
  color_scheme: "monokai"
  max_output_lines: 1000

history:
  enabled: true
  file: "~/.python_repl_history"
  max_entries: 10000

completion:
  enabled: true
  fuzzy_matching: true

plugins:
  enabled: true
  plugin_dir: "~/.python_repl/plugins"
  auto_load: []
```

### Documentation Files

#### User Guide (docs/user_guide.md)
- Installation instructions
- Basic usage
- Feature overview
- Configuration guide
- Troubleshooting

#### Plugin Development (docs/plugin_development.md)
- Plugin API reference
- Hook system explanation
- Example plugins
- Best practices
- Testing plugins

#### API Reference (docs/api_reference.md)
- Auto-generated from docstrings
- All public classes and functions
- Parameters and return types
- Usage examples

## Module Dependencies

### Dependency Graph

```
repl.core
├── repl.input_handler
│   ├── repl.highlighter
│   ├── repl.completion
│   └── repl.history
├── repl.parser
├── repl.executor
│   └── repl.namespace
├── repl.output_formatter
├── repl.exception_handler
├── repl.session
│   ├── repl.namespace
│   └── repl.history
├── repl.config
└── repl.plugins.manager
    ├── repl.plugins.base
    ├── repl.plugins.hooks
    └── repl.plugins.discovery
```

## File Size Estimates

```
repl/core.py               ~500 lines   Main REPL loop
repl/input_handler.py      ~300 lines   Input handling
repl/parser.py             ~200 lines   Code parsing
repl/executor.py           ~400 lines   Code execution
repl/namespace.py          ~300 lines   Namespace management
repl/completion.py         ~400 lines   Tab completion
repl/highlighter.py        ~150 lines   Syntax highlighting
repl/history.py            ~350 lines   History management
repl/exception_handler.py  ~300 lines   Exception handling
repl/inspector.py          ~250 lines   Variable inspection
repl/output_formatter.py   ~300 lines   Output formatting
repl/session.py            ~300 lines   Session management
repl/config.py             ~250 lines   Configuration

repl/plugins/base.py       ~150 lines   Plugin base
repl/plugins/manager.py    ~400 lines   Plugin manager
repl/plugins/hooks.py      ~200 lines   Hook system
repl/plugins/discovery.py  ~200 lines   Plugin discovery

Total Core:                ~4,450 lines
Tests:                     ~3,000 lines (approx. 2/3 of core)
Documentation:             ~2,000 lines
Example Plugins:           ~500 lines
```

## Build and Distribution

### Package Structure (after build)
```
dist/
├── python_repl-1.0.0-py3-none-any.whl    # Wheel distribution
└── python_repl-1.0.0.tar.gz              # Source distribution
```

### Installation Methods

```bash
# From PyPI (after publishing)
pip install python-repl

# From source
pip install -e .

# With development dependencies
pip install -e ".[dev]"

# As standalone binary (with PyInstaller)
pyinstaller --onefile repl/__main__.py
```

## Entry Points

### Console Scripts
```python
# In setup.py
entry_points={
    'console_scripts': [
        'pyrepl=repl.core:main',
        'python-repl=repl.core:main',
    ],
}
```

### Usage After Installation
```bash
# Run directly
pyrepl

# Or with python -m
python -m repl

# With config file
pyrepl --config my_config.yaml

# Load session
pyrepl --load session.json
```

## Development Workflow

1. **Setup**: `make install` or `pip install -e ".[dev]"`
2. **Code**: Write code with editor of choice
3. **Format**: `make format` or `black repl/`
4. **Lint**: `make lint` or `ruff check repl/`
5. **Type Check**: `mypy repl/`
6. **Test**: `make test` or `pytest`
7. **Coverage**: `make coverage` or `pytest --cov=repl`
8. **Build**: `python -m build`
9. **Publish**: `twine upload dist/*`

## Configuration Locations

### User Configuration
```
~/.python_repl/
├── config.yaml           # User configuration
├── plugins/              # User plugins
├── themes/               # Custom themes
└── sessions/             # Saved sessions
```

### System Configuration
```
/etc/python_repl/
└── config.yaml           # System-wide configuration
```

### Environment Variables
```
PYTHON_REPL_CONFIG        # Override config file location
PYTHON_REPL_PLUGIN_DIR    # Override plugin directory
PYTHON_REPL_NO_COLOR      # Disable colors
```

## Versioning Strategy

Following Semantic Versioning (SemVer):
- **MAJOR**: Breaking API changes
- **MINOR**: New features, backward compatible
- **PATCH**: Bug fixes, backward compatible

Example: `1.2.3` = Major 1, Minor 2, Patch 3
