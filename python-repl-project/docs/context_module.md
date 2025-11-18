# ExecutionContext Module Documentation

## Overview

The `ExecutionContext` class provides a robust execution environment for Python code in a REPL setting. It manages namespaces, variables, module imports, execution history, and provides powerful introspection capabilities.

## Features

- **Code Execution**: Execute Python expressions and statements
- **Variable Management**: Store, retrieve, and inspect variables
- **Module Tracking**: Track and list imported modules
- **State Persistence**: Save and restore execution state
- **Introspection**: Examine variables, functions, and classes
- **Execution History**: Track all executed code
- **Error Handling**: Robust exception handling that preserves context state
- **Type Safety**: Full type hints for better IDE support

## Installation

The module is part of the `pyrepl` package:

```python
from src.pyrepl.context import ExecutionContext
```

## Quick Start

```python
# Create a new execution context
context = ExecutionContext()

# Execute code
result = context.execute_code("2 + 2")  # Returns: 4

# Define variables
context.execute_code("x = 10")
value = context.get_variable('x')  # Returns: 10

# List all variables
variables = context.list_variables()  # Returns: {'x': 10}
```

## API Reference

### Class: ExecutionContext

#### Constructor

```python
ExecutionContext(initial_globals: Optional[Dict[str, Any]] = None)
```

Creates a new execution context.

**Parameters:**
- `initial_globals` (optional): Dictionary of initial global variables

**Example:**
```python
context = ExecutionContext(initial_globals={'VERSION': '1.0.0'})
```

---

#### execute_code()

```python
execute_code(code: str) -> Any
```

Execute Python code in the current context.

**Parameters:**
- `code`: Python code string to execute

**Returns:**
- Result of the last expression, or `None` for statements

**Raises:**
- Any exception raised during code execution

**Examples:**
```python
# Execute expression
result = context.execute_code("2 + 2")  # Returns: 4

# Execute statement
context.execute_code("x = 10")  # Returns: None

# Execute multiline code
context.execute_code("""
def greet(name):
    return f"Hello, {name}!"
""")
```

---

#### get_variable()

```python
get_variable(name: str) -> Any
```

Get a variable from the context.

**Parameters:**
- `name`: Variable name

**Returns:**
- The variable value

**Raises:**
- `NameError`: If the variable doesn't exist

**Example:**
```python
context.execute_code("x = 42")
value = context.get_variable('x')  # Returns: 42
```

---

#### set_variable()

```python
set_variable(name: str, value: Any) -> None
```

Set a variable in the context.

**Parameters:**
- `name`: Variable name
- `value`: Variable value

**Example:**
```python
context.set_variable('my_var', 100)
```

---

#### has_variable()

```python
has_variable(name: str) -> bool
```

Check if a variable exists in the context.

**Parameters:**
- `name`: Variable name

**Returns:**
- `True` if the variable exists, `False` otherwise

**Example:**
```python
if context.has_variable('x'):
    print(context.get_variable('x'))
```

---

#### list_variables()

```python
list_variables() -> Dict[str, Any]
```

List all user-defined variables in the context.

**Returns:**
- Dictionary of variable names and their values

**Example:**
```python
context.execute_code("x = 1")
context.execute_code("y = 2")
variables = context.list_variables()  # Returns: {'x': 1, 'y': 2}
```

---

#### list_modules()

```python
list_modules() -> List[str]
```

List all imported modules.

**Returns:**
- List of module names

**Example:**
```python
context.execute_code("import os")
context.execute_code("import sys")
modules = context.list_modules()  # Returns: ['os', 'sys', ...]
```

---

#### get_variable_info()

```python
get_variable_info(name: str) -> Dict[str, Any]
```

Get detailed information about a variable.

**Parameters:**
- `name`: Variable name

**Returns:**
- Dictionary containing variable information

**Raises:**
- `NameError`: If the variable doesn't exist

**Example:**
```python
context.execute_code("my_list = [1, 2, 3]")
info = context.get_variable_info('my_list')
# Returns: {
#     'name': 'my_list',
#     'type': 'list',
#     'value': '[1, 2, 3]',
#     'module': 'builtins',
#     'doc': '...',
#     'length': 3,
#     'callable': False
# }
```

---

#### clear_namespace()

```python
clear_namespace(keep_builtins: bool = True) -> None
```

Clear the execution namespace.

**Parameters:**
- `keep_builtins`: If `True`, preserve built-in functions (default: `True`)

**Example:**
```python
context.clear_namespace()  # Clear variables but keep builtins
context.clear_namespace(keep_builtins=False)  # Clear everything
```

---

#### save_state()

```python
save_state(filename: str) -> None
```

Save the current execution state to a file.

**Parameters:**
- `filename`: Path to the output file

**Raises:**
- `IOError`: If the file cannot be written
- `pickle.PicklingError`: If objects cannot be serialized

**Example:**
```python
context.save_state('session.pkl')
```

**Note:** Only picklable objects are saved. Non-picklable objects (like functions defined in the console) are skipped with a warning.

---

#### load_state()

```python
load_state(filename: str) -> None
```

Load execution state from a file.

**Parameters:**
- `filename`: Path to the input file

**Raises:**
- `IOError`: If the file cannot be read
- `pickle.UnpicklingError`: If the file is corrupted

**Example:**
```python
context.load_state('session.pkl')
```

---

#### export_state()

```python
export_state() -> Dict[str, Any]
```

Export the current state as a dictionary.

**Returns:**
- Dictionary containing the current state

**Example:**
```python
state = context.export_state()
# Returns: {
#     'variables': {...},
#     'modules': [...],
#     'history': [...]
# }
```

---

#### import_state()

```python
import_state(state: Dict[str, Any]) -> None
```

Import state from a dictionary.

**Parameters:**
- `state`: Dictionary containing state information

**Example:**
```python
state = context1.export_state()
context2.import_state(state)
```

---

#### get_history()

```python
get_history() -> List[str]
```

Get the execution history.

**Returns:**
- List of executed code strings

**Example:**
```python
context.execute_code("x = 1")
context.execute_code("y = 2")
history = context.get_history()  # Returns: ['x = 1', 'y = 2']
```

---

#### clear_history()

```python
clear_history() -> None
```

Clear the execution history.

**Example:**
```python
context.clear_history()
```

---

#### get_namespace()

```python
get_namespace() -> Tuple[Dict[str, Any], Dict[str, Any]]
```

Get the current global and local namespaces.

**Returns:**
- Tuple of (globals, locals) dictionaries

**Example:**
```python
globals_dict, locals_dict = context.get_namespace()
```

---

#### introspect()

```python
introspect(obj_name: Optional[str] = None) -> Dict[str, Any]
```

Perform introspection on an object or the entire namespace.

**Parameters:**
- `obj_name`: Optional name of object to introspect. If `None`, introspect all.

**Returns:**
- Dictionary containing introspection information

**Examples:**
```python
# Introspect specific variable
info = context.introspect('my_list')

# Introspect entire namespace
info = context.introspect()
# Returns: {
#     'variables': {...},
#     'functions': {...},
#     'classes': {...},
#     'modules': {...}
# }
```

---

## Usage Examples

### Basic Code Execution

```python
from src.pyrepl.context import ExecutionContext

context = ExecutionContext()

# Execute expressions
result = context.execute_code("2 + 2")
print(result)  # Output: 4

# Execute statements
context.execute_code("message = 'Hello, World!'")
print(context.get_variable('message'))  # Output: Hello, World!
```

### Function Definition and Calling

```python
context = ExecutionContext()

# Define a function
context.execute_code("""
def factorial(n):
    if n <= 1:
        return 1
    return n * factorial(n - 1)
""")

# Call the function
result = context.execute_code("factorial(5)")
print(result)  # Output: 120
```

### Class Definition and Instantiation

```python
context = ExecutionContext()

# Define a class
context.execute_code("""
class Counter:
    def __init__(self):
        self.count = 0
    
    def increment(self):
        self.count += 1
        return self.count
""")

# Create instance and use it
context.execute_code("counter = Counter()")
context.execute_code("counter.increment()")
result = context.execute_code("counter.increment()")
print(result)  # Output: 2
```

### Working with Modules

```python
context = ExecutionContext()

# Import modules
context.execute_code("import math")
context.execute_code("import random")

# Use imported modules
result = context.execute_code("math.sqrt(16)")
print(result)  # Output: 4.0

# List imported modules
modules = context.list_modules()
print(modules)  # Output: ['math', 'random', ...]
```

### State Persistence

```python
# Create context and add some data
context1 = ExecutionContext()
context1.execute_code("x = 42")
context1.execute_code("y = [1, 2, 3]")

# Save state
context1.save_state('session.pkl')

# Create new context and load state
context2 = ExecutionContext()
context2.load_state('session.pkl')

# Variables are restored
print(context2.get_variable('x'))  # Output: 42
print(context2.get_variable('y'))  # Output: [1, 2, 3]
```

### Introspection

```python
context = ExecutionContext()

# Create various objects
context.execute_code("x = 42")
context.execute_code("def my_func(): pass")
context.execute_code("class MyClass: pass")
context.execute_code("import os")

# Introspect entire namespace
info = context.introspect()

print(f"Variables: {list(info['variables'].keys())}")
print(f"Functions: {list(info['functions'].keys())}")
print(f"Classes: {list(info['classes'].keys())}")
print(f"Modules: {list(info['modules'].keys())}")

# Introspect specific variable
context.execute_code("my_list = [1, 2, 3, 4, 5]")
list_info = context.introspect('my_list')
print(f"Type: {list_info['type']}")
print(f"Length: {list_info['length']}")
print(f"Methods: {list_info['methods']}")
```

### Error Handling

```python
context = ExecutionContext()
context.execute_code("x = 10")

try:
    context.execute_code("y = 1 / 0")
except ZeroDivisionError as e:
    print(f"Error: {e}")

# Context remains functional after error
print(context.get_variable('x'))  # Output: 10
context.execute_code("z = 20")
print(context.get_variable('z'))  # Output: 20
```

### Execution History

```python
context = ExecutionContext()

# Execute some code
context.execute_code("x = 1")
context.execute_code("y = 2")
context.execute_code("z = x + y")

# Get history
history = context.get_history()
for i, code in enumerate(history, 1):
    print(f"{i}. {code}")

# Output:
# 1. x = 1
# 2. y = 2
# 3. z = x + y
```

### Advanced Python Features

```python
context = ExecutionContext()

# List comprehension
result = context.execute_code("[x**2 for x in range(5)]")
print(result)  # Output: [0, 1, 4, 9, 16]

# Lambda functions
context.execute_code("square = lambda x: x**2")
result = context.execute_code("square(7)")
print(result)  # Output: 49

# Dictionary comprehension
result = context.execute_code("{k: v**2 for k, v in zip(['a', 'b'], [1, 2])}")
print(result)  # Output: {'a': 1, 'b': 4}

# Generator expression
context.execute_code("gen = (x*2 for x in range(5))")
result = context.execute_code("list(gen)")
print(result)  # Output: [0, 2, 4, 6, 8]
```

## Best Practices

1. **Error Handling**: Always wrap `execute_code()` calls in try-except blocks to handle runtime errors gracefully.

2. **State Persistence**: Be aware that not all objects can be pickled. Functions and classes defined in the console cannot be saved to files.

3. **Memory Management**: Clear the namespace periodically in long-running sessions using `clear_namespace()`.

4. **Variable Inspection**: Use `has_variable()` before `get_variable()` to avoid NameError exceptions.

5. **History Management**: Clear execution history periodically in long-running sessions to prevent memory buildup.

## Limitations

1. **Pickling**: User-defined functions and classes cannot be saved with `save_state()` due to pickle limitations. Use `export_state()` for in-memory state transfer.

2. **Namespace Isolation**: The context shares Python's module system, so module imports affect the global Python environment.

3. **Thread Safety**: The class is not thread-safe. Use separate instances for different threads.

4. **Resource Cleanup**: Objects created in the context are not automatically cleaned up. Use `clear_namespace()` to free memory.

## Testing

Comprehensive tests are available in `tests/test_context.py`. Run tests with:

```bash
python -m pytest tests/test_context.py -v
```

## Contributing

When extending the `ExecutionContext` class:

1. Add comprehensive type hints
2. Include docstrings for all public methods
3. Handle exceptions appropriately
4. Add corresponding unit tests
5. Update this documentation

## License

This module is part of the pyrepl project. See the project LICENSE file for details.
