#!/usr/bin/env python3
"""
Advanced PyREPL Features Examples

This script demonstrates advanced features of PyREPL including:
- Context management
- Session persistence
- Custom completion
- Advanced formatting
- Integration with external tools

To use in PyREPL:
    >>> exec(open('examples/advanced_features.py').read())

Or import specific examples:
    >>> from examples.advanced_features import *
    >>> example_session_management()
"""

import sys
import os
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def example_session_management():
    """Example: Save and load session state"""
    print("=" * 70)
    print("Example: Session Management")
    print("=" * 70)
    
    print("""
Session management allows you to save and restore your work:

# Create some variables
>>> x = 42
>>> y = [1, 2, 3, 4, 5]
>>> def my_function(n):
...     return n * 2
...

# Save the session
>>> !save my_work.pkl
Session saved to: my_work.pkl

# Later, in a new session...
>>> !load my_work.pkl
Session loaded from: my_work.pkl
Loaded 3 variable(s)

# Variables are restored
>>> x
42
>>> my_function(21)
42
""")
    
    print("Try it yourself in PyREPL!")
    print()


def example_context_inspection():
    """Example: Inspect execution context"""
    print("=" * 70)
    print("Example: Context Inspection")
    print("=" * 70)
    
    from pyrepl.context import ExecutionContext
    
    # Create a context
    ctx = ExecutionContext()
    
    # Execute some code
    print("Executing code in context:")
    print("  x = 10")
    print("  y = 20")
    print("  z = x + y")
    
    ctx.execute_code("x = 10")
    ctx.execute_code("y = 20")
    result = ctx.execute_code("x + y")
    
    print(f"\nResult: {result}")
    
    # List variables
    print("\nVariables in context:")
    variables = ctx.list_variables()
    for name, value in sorted(variables.items()):
        print(f"  {name} = {value} ({type(value).__name__})")
    
    # Get specific variable
    x_value = ctx.get_variable("x")
    print(f"\nGetting specific variable 'x': {x_value}")
    
    # Check if variable exists
    has_x = ctx.has_variable("x")
    has_w = ctx.has_variable("w")
    print(f"\nhas_variable('x'): {has_x}")
    print(f"has_variable('w'): {has_w}")
    
    # Get imported modules
    ctx.execute_code("import math")
    ctx.execute_code("import json")
    modules = ctx.get_imported_modules()
    print(f"\nImported modules: {modules}")
    
    print()


def example_completion_engine():
    """Example: Code completion capabilities"""
    print("=" * 70)
    print("Example: Code Completion")
    print("=" * 70)
    
    from pyrepl.context import ExecutionContext
    from pyrepl.completion import CompletionEngine
    
    # Create context and completion engine
    ctx = ExecutionContext()
    completion = CompletionEngine(context=ctx)
    
    # Set up some context
    ctx.execute_code("x = 42")
    ctx.execute_code("my_list = [1, 2, 3]")
    ctx.execute_code("import math")
    
    # Test completions
    print("Testing completions:\n")
    
    # Complete variable names
    completions = completion.get_completions("x")
    print(f"Completions for 'x': {completions}")
    
    # Complete on list methods
    completions = completion.get_completions("my_list.")
    print(f"\nCompletions for 'my_list.': {completions[:5]}...")  # Show first 5
    
    # Complete module attributes
    completions = completion.get_completions("math.")
    print(f"\nCompletions for 'math.': {completions[:5]}...")
    
    # Complete on partial text
    completions = completion.get_completions("my_")
    print(f"\nCompletions for 'my_': {completions}")
    
    print("\nIn PyREPL, press Tab to see completions!")
    print()


def example_output_formatting():
    """Example: Rich output formatting"""
    print("=" * 70)
    print("Example: Output Formatting")
    print("=" * 70)
    
    from pyrepl.output import OutputFormatter
    
    # Create formatter
    formatter = OutputFormatter(theme="monokai")
    
    print("PyREPL uses Rich for beautiful output:\n")
    
    # Format different types of results
    examples = [
        ("Integer", 42),
        ("Float", 3.14159),
        ("String", "Hello, PyREPL!"),
        ("List", [1, 2, 3, 4, 5]),
        ("Dict", {"name": "Alice", "age": 30, "city": "NYC"}),
        ("Tuple", (1, 2, 3)),
        ("Set", {1, 2, 3, 4, 5}),
    ]
    
    for name, value in examples:
        print(f"{name}:")
        formatted = formatter.format_result(value)
        formatter.console.print(formatted)
        print()
    
    # Format exception
    try:
        1 / 0
    except Exception as e:
        print("Exception formatting:")
        formatted = formatter.format_exception(e)
        formatter.console.print(formatted)
    
    print()


def example_history_features():
    """Example: History management"""
    print("=" * 70)
    print("Example: History Management")
    print("=" * 70)
    
    from pyrepl.history import HistoryManager
    import tempfile
    
    # Create history manager with temporary database
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    
    history = HistoryManager(db_path=db_path, max_history=100)
    
    print("Adding commands to history:")
    commands = [
        "x = 42",
        "y = x * 2",
        "print(y)",
        "import math",
        "math.sqrt(16)",
    ]
    
    for cmd in commands:
        print(f"  {cmd}")
        history.add_command(cmd)
    
    # Get history
    print("\nRetrieving history:")
    hist = history.get_history(limit=10)
    for i, cmd in enumerate(hist, 1):
        print(f"  {i}. {cmd}")
    
    # Search history
    print("\nSearching for 'math':")
    results = history.search_history("math")
    for cmd in results:
        print(f"  {cmd}")
    
    # Get statistics
    stats = history.get_statistics()
    print("\nHistory statistics:")
    print(f"  Total commands: {stats['total_commands']}")
    print(f"  Unique commands: {stats['unique_commands']}")
    print(f"  Most recent: {stats['most_recent_command']}")
    
    # Cleanup
    history.close()
    os.unlink(db_path)
    
    print("\nIn PyREPL, use !history to see your command history")
    print()


def example_custom_configuration():
    """Example: Configuration management"""
    print("=" * 70)
    print("Example: Configuration")
    print("=" * 70)
    
    from pyrepl.config import Config, AppearanceConfig, BehaviorConfig
    
    print("Creating custom configuration:\n")
    
    # Create config with custom settings
    config = Config()
    
    # Customize appearance
    config.appearance.theme = "dracula"
    config.appearance.prompt_style = "🐍 >>> "
    config.appearance.continuation_prompt = "...    "
    config.appearance.enable_syntax_highlighting = True
    
    # Customize behavior
    config.behavior.auto_suggest = True
    config.behavior.vi_mode = False
    config.behavior.confirm_exit = True
    
    # Print configuration
    print("Current configuration:")
    config_dict = config.to_dict()
    
    import json
    print(json.dumps(config_dict, indent=2))
    
    print("\nSave this to ~/.pyrepl/config.toml to make it permanent!")
    print()


def example_multi_line_editing():
    """Example: Multi-line code editing"""
    print("=" * 70)
    print("Example: Multi-line Editing")
    print("=" * 70)
    
    print("""
PyREPL automatically detects when you need multi-line input:

# Function definition
>>> def fibonacci(n):
...     if n <= 1:
...         return n
...     return fibonacci(n-1) + fibonacci(n-2)
...
>>> fibonacci(10)
55

# Class definition
>>> class Person:
...     def __init__(self, name, age):
...         self.name = name
...         self.age = age
...     
...     def greet(self):
...         return f"Hello, I'm {self.name} and I'm {self.age} years old"
...
>>> p = Person("Alice", 30)
>>> p.greet()
"Hello, I'm Alice and I'm 30 years old"

# List comprehension spanning multiple lines
>>> result = [
...     x**2
...     for x in range(10)
...     if x % 2 == 0
... ]
>>> result
[0, 4, 16, 36, 64]

# Multi-line strings
>>> text = '''
... This is a
... multi-line
... string
... '''
>>> print(text)

The continuation prompt (...) appears automatically!
""")
    print()


def example_working_with_external_data():
    """Example: Working with external data formats"""
    print("=" * 70)
    print("Example: External Data Formats")
    print("=" * 70)
    
    import json
    import csv
    from io import StringIO
    
    print("Working with JSON:\n")
    
    # JSON parsing and formatting
    json_data = '{"users": [{"name": "Alice", "age": 30}, {"name": "Bob", "age": 25}]}'
    parsed = json.loads(json_data)
    print(f"Parsed JSON: {parsed}")
    
    # Pretty print JSON
    print("\nPretty printed:")
    print(json.dumps(parsed, indent=2))
    
    print("\n" + "-" * 70)
    print("\nWorking with CSV:\n")
    
    # CSV data
    csv_data = StringIO("""name,age,city
Alice,30,New York
Bob,25,San Francisco
Charlie,35,Boston""")
    
    reader = csv.DictReader(csv_data)
    rows = list(reader)
    
    print("CSV data as dictionaries:")
    for row in rows:
        print(f"  {row}")
    
    print("\n" + "-" * 70)
    print("\nData transformation:\n")
    
    # Transform data
    ages = [int(row['age']) for row in rows]
    print(f"Ages: {ages}")
    print(f"Average age: {sum(ages) / len(ages):.1f}")
    print(f"Oldest: {max(ages)}")
    print(f"Youngest: {min(ages)}")
    
    print()


def example_itertools_recipes():
    """Example: Advanced iteration patterns with itertools"""
    print("=" * 70)
    print("Example: Itertools Recipes")
    print("=" * 70)
    
    from itertools import islice, cycle, chain, combinations, permutations
    
    print("Common itertools patterns:\n")
    
    # Take first n items
    print("Take first 5 items from infinite sequence:")
    result = list(islice(cycle([1, 2, 3]), 5))
    print(f"  islice(cycle([1, 2, 3]), 5) = {result}")
    
    # Chain iterables
    print("\nChain multiple iterables:")
    result = list(chain([1, 2], [3, 4], [5, 6]))
    print(f"  chain([1, 2], [3, 4], [5, 6]) = {result}")
    
    # Combinations
    print("\nCombinations (choose 2 from list):")
    result = list(combinations([1, 2, 3, 4], 2))
    print(f"  combinations([1, 2, 3, 4], 2) = {result}")
    
    # Permutations
    print("\nPermutations (arrange 2 from list):")
    result = list(permutations([1, 2, 3], 2))
    print(f"  permutations([1, 2, 3], 2) = {result}")
    
    # Sliding window
    print("\nSliding window (window size 3):")
    def sliding_window(iterable, n):
        iterators = [iter(iterable)] * n
        return zip(*iterators)
    
    result = list(sliding_window(range(10), 3))
    print(f"  sliding_window(range(10), 3) = {result}")
    
    print()


def example_decorators_and_closures():
    """Example: Decorators and closures"""
    print("=" * 70)
    print("Example: Decorators and Closures")
    print("=" * 70)
    
    import time
    from functools import wraps
    
    print("Creating a timing decorator:\n")
    
    # Timing decorator
    def timer(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start = time.time()
            result = func(*args, **kwargs)
            end = time.time()
            print(f"{func.__name__} took {end - start:.4f} seconds")
            return result
        return wrapper
    
    # Use the decorator
    @timer
    def slow_function():
        time.sleep(0.1)
        return "Done!"
    
    print("Calling decorated function:")
    result = slow_function()
    print(f"Result: {result}\n")
    
    print("-" * 70)
    print("\nClosure example - counter factory:\n")
    
    def make_counter(start=0):
        count = start
        def increment():
            nonlocal count
            count += 1
            return count
        def decrement():
            nonlocal count
            count -= 1
            return count
        def get():
            return count
        return increment, decrement, get
    
    inc, dec, get = make_counter(10)
    print(f"Initial count: {get()}")
    print(f"After increment: {inc()}")
    print(f"After increment: {inc()}")
    print(f"After decrement: {dec()}")
    print(f"Final count: {get()}")
    
    print()


def example_context_managers():
    """Example: Custom context managers"""
    print("=" * 70)
    print("Example: Context Managers")
    print("=" * 70)
    
    from contextlib import contextmanager
    import tempfile
    
    print("Custom context manager for timing:\n")
    
    @contextmanager
    def timer_context(name):
        print(f"Starting {name}...")
        start = time.time()
        yield
        end = time.time()
        print(f"{name} completed in {end - start:.4f} seconds")
    
    # Use the context manager
    with timer_context("calculation"):
        result = sum(range(1000000))
        print(f"Result: {result}")
    
    print("\n" + "-" * 70)
    print("\nTemporary file context:\n")
    
    @contextmanager
    def temporary_file(content):
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write(content)
            temp_path = f.name
        try:
            yield temp_path
        finally:
            os.unlink(temp_path)
    
    # Use temporary file
    with temporary_file("Hello, PyREPL!") as filepath:
        print(f"Temporary file: {filepath}")
        with open(filepath, 'r') as f:
            print(f"Content: {f.read()}")
    print("File automatically cleaned up!")
    
    print()


def example_async_programming():
    """Example: Async/await patterns"""
    print("=" * 70)
    print("Example: Async Programming")
    print("=" * 70)
    
    print("""
PyREPL supports async/await syntax:

# Define async function
>>> import asyncio
>>> async def fetch_data(id):
...     await asyncio.sleep(0.1)  # Simulate network delay
...     return f"Data for ID {id}"
...

# Run async function
>>> asyncio.run(fetch_data(42))
'Data for ID 42'

# Multiple concurrent tasks
>>> async def fetch_multiple(ids):
...     tasks = [fetch_data(id) for id in ids]
...     return await asyncio.gather(*tasks)
...
>>> asyncio.run(fetch_multiple([1, 2, 3]))
['Data for ID 1', 'Data for ID 2', 'Data for ID 3']

# Async comprehension
>>> async def get_numbers():
...     for i in range(5):
...         await asyncio.sleep(0.01)
...         yield i
...
>>> async def main():
...     return [x async for x in get_numbers()]
...
>>> asyncio.run(main())
[0, 1, 2, 3, 4]

Try these patterns in PyREPL!
""")
    print()


def run_all_examples():
    """Run all advanced examples"""
    examples = [
        ("Session Management", example_session_management),
        ("Context Inspection", example_context_inspection),
        ("Code Completion", example_completion_engine),
        ("Output Formatting", example_output_formatting),
        ("History Features", example_history_features),
        ("Custom Configuration", example_custom_configuration),
        ("Multi-line Editing", example_multi_line_editing),
        ("External Data", example_working_with_external_data),
        ("Itertools Recipes", example_itertools_recipes),
        ("Decorators & Closures", example_decorators_and_closures),
        ("Context Managers", example_context_managers),
        ("Async Programming", example_async_programming),
    ]
    
    print("\n" + "=" * 70)
    print("PYREPL ADVANCED FEATURES EXAMPLES")
    print("=" * 70 + "\n")
    
    for name, example_func in examples:
        print(f"\n📚 Running: {name}\n")
        try:
            example_func()
        except Exception as e:
            print(f"Error running {name}: {e}")
        
        if example_func != examples[-1][1]:  # Not last example
            input("\nPress Enter to continue to next example...")
            print("\n")
    
    print("=" * 70)
    print("All advanced examples completed!")
    print("=" * 70)


if __name__ == "__main__":
    import time
    
    # When run as a script, execute all examples
    run_all_examples()
else:
    # When imported, provide instructions
    print("Advanced Features Examples loaded!")
    print("\nAvailable examples:")
    print("  - example_session_management()")
    print("  - example_context_inspection()")
    print("  - example_completion_engine()")
    print("  - example_output_formatting()")
    print("  - example_history_features()")
    print("  - example_custom_configuration()")
    print("  - example_multi_line_editing()")
    print("  - example_working_with_external_data()")
    print("  - example_itertools_recipes()")
    print("  - example_decorators_and_closures()")
    print("  - example_context_managers()")
    print("  - example_async_programming()")
    print("\nRun all: run_all_examples()")
