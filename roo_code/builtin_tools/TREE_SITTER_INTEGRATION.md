# Tree-sitter Integration for Code Parsing

This document describes the tree-sitter integration implemented for the Python SDK of Roo Code.

## Overview

The tree-sitter integration provides accurate code parsing for the `list_code_definition_names` tool, enabling extraction of code definitions (functions, classes, methods, etc.) from source files across multiple programming languages.

## Architecture

### Components

1. **TreeSitterParser** (`tree_sitter_parser.py`)
   - Main parser class that handles tree-sitter operations
   - Supports multiple programming languages
   - Provides graceful fallback when tree-sitter is unavailable

2. **ListCodeDefinitionNamesTool** (`search.py`)
   - Updated to use TreeSitterParser when available
   - Falls back to regex-based parsing when tree-sitter is not installed

3. **Test Suite** (`tests/test_tree_sitter_parser.py`)
   - Comprehensive tests for all supported languages
   - Tests both tree-sitter and fallback behavior

## Supported Languages

The following languages are supported with tree-sitter parsing:

- **Python** (.py) - Classes, functions, methods, async functions
- **JavaScript** (.js, .jsx) - Classes, functions, methods, arrow functions
- **TypeScript** (.ts, .tsx) - Classes, functions, interfaces, types, methods
- **Java** (.java) - Classes, interfaces, methods, constructors
- **Go** (.go) - Functions, methods, types, interfaces
- **Rust** (.rs) - Functions, structs, impl blocks, traits, enums
- **C++** (.cpp, .hpp) - Functions, classes, structs, methods
- **C** (.c, .h) - Functions, structs
- **Ruby** (.rb) - Classes, modules, methods
- **PHP** (.php) - Classes, functions, methods, interfaces, traits

## Installation

### Basic Installation

Install the base package with tree-sitter support:

```bash
pip install roo-code
```

### With Tree-sitter Language Grammars

To enable tree-sitter parsing, install the optional tree-sitter dependencies:

```bash
pip install roo-code[treesitter]
```

This will install:
- `tree-sitter` - Core tree-sitter library
- `tree-sitter-python` - Python grammar
- `tree-sitter-javascript` - JavaScript grammar
- `tree-sitter-typescript` - TypeScript grammar
- `tree-sitter-java` - Java grammar
- `tree-sitter-cpp` - C++ grammar
- `tree-sitter-c` - C grammar
- `tree-sitter-go` - Go grammar
- `tree-sitter-rust` - Rust grammar
- `tree-sitter-ruby` - Ruby grammar
- `tree-sitter-php` - PHP grammar

### Minimal Installation

The package works without tree-sitter language grammars, falling back to regex-based parsing:

```bash
pip install roo-code
```

## Usage

### Programmatic Usage

```python
from pathlib import Path
from roo_code.builtin_tools.tree_sitter_parser import TreeSitterParser

# Create parser instance
parser = TreeSitterParser()

# Check if tree-sitter is available
if parser.is_available():
    print("Tree-sitter parsing enabled")
else:
    print("Using regex fallback")

# Parse a single file
file_path = Path("example.py")
definitions = parser.parse_file(file_path)
print(definitions)

# Parse a directory
dir_path = Path("src")
all_definitions = parser.parse_directory(dir_path)
print(all_definitions)
```

### Tool Usage

The `list_code_definition_names` tool automatically uses tree-sitter when available:

```python
from roo_code.builtin_tools.search import ListCodeDefinitionNamesTool

tool = ListCodeDefinitionNamesTool(cwd=".")
result = await tool.execute({"path": "src/example.py"})
print(result.content)
```

## Output Format

The parser outputs definitions in the following format:

```
# filename.py
5--10 | class MyClass:
15--20 | def my_function():
25--30 | async def async_function():
```

Each line shows:
- Start line number (1-based)
- End line number (1-based)
- The first line of the definition

## Configuration

### Minimum Component Lines

By default, only code components spanning 4 or more lines are included. This filters out trivial definitions and keeps output concise.

This is configured by the `MIN_COMPONENT_LINES` constant in `tree_sitter_parser.py`.

## Fallback Behavior

When tree-sitter or language grammars are not available, the system automatically falls back to regex-based parsing. This ensures the tool works in all environments, though with potentially less accuracy.

### Regex Fallback Features

- **Python**: Detects classes, functions, async functions
- **JavaScript/TypeScript**: Detects classes, functions, arrow functions, interfaces
- **Java/C#/C++**: Detects classes, functions/methods

## Query Patterns

Each language has custom tree-sitter query patterns optimized for definition extraction. These queries are based on the TypeScript implementation and capture:

- Class declarations
- Function/method declarations
- Interface/type definitions
- Async functions
- Decorated functions/classes
- And more

Query patterns are defined in the `tree_sitter_parser.py` file as string constants (e.g., `PYTHON_QUERY`, `JAVASCRIPT_QUERY`).

## Error Handling

The parser includes robust error handling:

1. **Missing tree-sitter**: Gracefully falls back to regex
2. **Missing language grammar**: Returns None (falls back in tool)
3. **File not found**: Returns None
4. **Parse errors**: Catches exceptions and returns None
5. **Unsupported file types**: Returns None

## Performance Considerations

- Tree-sitter parsing is significantly more accurate than regex
- Parser instances cache language parsers for reuse
- Directory parsing limits to 50 files by default (configurable)
- Large files are handled efficiently through tree-sitter's streaming API

## Testing

Run the test suite:

```bash
# Run all tree-sitter tests
pytest tests/test_tree_sitter_parser.py -v

# Run specific test class
pytest tests/test_tree_sitter_parser.py::TestPythonParsing -v

# Run with coverage
pytest tests/test_tree_sitter_parser.py --cov=roo_code.builtin_tools.tree_sitter_parser
```

## Extending Language Support

To add support for a new language:

1. Add the file extension to `LANGUAGE_CONFIG` in `tree_sitter_parser.py`
2. Define a query pattern constant (e.g., `MYLANG_QUERY`)
3. Map the extension to the language name and query
4. Add the language grammar to `pyproject.toml` under `[project.optional-dependencies.treesitter]`
5. Create test fixtures in `tests/fixtures/`
6. Add tests to `test_tree_sitter_parser.py`

Example:

```python
# In tree_sitter_parser.py
SCALA_QUERY = """
(class_definition
  name: (identifier) @name.definition.class) @definition.class
(function_definition
  name: (identifier) @name.definition.function) @definition.function
"""

LANGUAGE_CONFIG = {
    # ... existing languages ...
    'scala': ('scala', SCALA_QUERY),
}
```

## Troubleshooting

### Tree-sitter not available

**Symptom**: `parser.is_available()` returns `False`

**Solution**: Install tree-sitter:
```bash
pip install tree-sitter
```

### Language grammar not installed

**Symptom**: Parsing returns `None` even with tree-sitter installed

**Solution**: Install language-specific grammars:
```bash
pip install tree-sitter-python tree-sitter-javascript
```

Or install all supported grammars:
```bash
pip install roo-code[treesitter]
```

### No definitions found

**Symptom**: Parser returns empty string or None

**Possible causes**:
1. File contains only small definitions (< 4 lines)
2. Query pattern doesn't match the code structure
3. File has syntax errors

**Solution**:
- Check file content
- Verify syntax is correct
- Try with a different file

## Comparison with TypeScript Implementation

The Python implementation mirrors the TypeScript implementation (`src/services/tree-sitter/`) with these differences:

1. **Language Loading**: Python uses language-specific packages instead of WASM binaries
2. **Parser Initialization**: Python's tree-sitter API differs slightly from web-tree-sitter
3. **Query Syntax**: Identical query patterns with minor adjustments for API differences
4. **Fallback**: Both implementations include regex fallbacks

## Future Improvements

Potential enhancements:

1. **Caching**: Cache parsed results for frequently accessed files
2. **Incremental Parsing**: Support for parsing only changed portions
3. **More Languages**: Add support for Swift, Kotlin, Scala, etc.
4. **Custom Queries**: Allow users to provide custom query patterns
5. **Grammar Auto-installation**: Automatically install missing grammars on demand

## References

- [tree-sitter Documentation](https://tree-sitter.github.io/tree-sitter/)
- [Python tree-sitter Bindings](https://github.com/tree-sitter/py-tree-sitter)
- [Tree-sitter Query Syntax](https://tree-sitter.github.io/tree-sitter/using-parsers#query-syntax)
- [Roo Code TypeScript Implementation](../../../src/services/tree-sitter/)