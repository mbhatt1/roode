#!/usr/bin/env python3
"""
Basic PyREPL Usage Examples

This script demonstrates basic usage patterns for PyREPL.
You can run this interactively in PyREPL or study it to learn the basics.

To use in PyREPL:
    >>> exec(open('examples/basic_usage.py').read())

Or run individual examples:
    >>> from examples.basic_usage import *
    >>> example_1_simple_expressions()
"""


def example_1_simple_expressions():
    """Example 1: Simple expressions and basic arithmetic"""
    print("=" * 60)
    print("Example 1: Simple Expressions")
    print("=" * 60)
    
    # Basic arithmetic
    print(f"2 + 2 = {2 + 2}")
    print(f"10 * 5 = {10 * 5}")
    print(f"2 ** 8 = {2 ** 8}")
    print(f"17 // 5 = {17 // 5}")  # Floor division
    print(f"17 % 5 = {17 % 5}")    # Modulo
    
    # String operations
    name = "PyREPL"
    print(f"\nString: '{name}'")
    print(f"Length: {len(name)}")
    print(f"Uppercase: {name.upper()}")
    print(f"Reversed: {name[::-1]}")
    
    print()


def example_2_variables():
    """Example 2: Working with variables"""
    print("=" * 60)
    print("Example 2: Variables")
    print("=" * 60)
    
    # Different variable types
    integer_var = 42
    float_var = 3.14159
    string_var = "Hello, World!"
    list_var = [1, 2, 3, 4, 5]
    dict_var = {"name": "Alice", "age": 30}
    
    print(f"Integer: {integer_var} (type: {type(integer_var).__name__})")
    print(f"Float: {float_var} (type: {type(float_var).__name__})")
    print(f"String: {string_var} (type: {type(string_var).__name__})")
    print(f"List: {list_var} (type: {type(list_var).__name__})")
    print(f"Dict: {dict_var} (type: {type(dict_var).__name__})")
    
    # Variable reassignment
    x = 10
    print(f"\nx = {x}")
    x = x * 2
    print(f"x = x * 2 → x = {x}")
    x += 5
    print(f"x += 5 → x = {x}")
    
    print()


def example_3_functions():
    """Example 3: Defining and using functions"""
    print("=" * 60)
    print("Example 3: Functions")
    print("=" * 60)
    
    # Simple function
    def greet(name):
        return f"Hello, {name}!"
    
    print(f"greet('Python'): {greet('Python')}")
    
    # Function with default arguments
    def power(base, exponent=2):
        return base ** exponent
    
    print(f"\npower(5): {power(5)}")
    print(f"power(5, 3): {power(5, 3)}")
    
    # Function with multiple return values
    def min_max(numbers):
        return min(numbers), max(numbers)
    
    nums = [3, 1, 4, 1, 5, 9, 2, 6]
    minimum, maximum = min_max(nums)
    print(f"\nmin_max({nums}):")
    print(f"  Minimum: {minimum}")
    print(f"  Maximum: {maximum}")
    
    # Lambda functions
    square = lambda x: x ** 2
    print(f"\nlambda x: x ** 2")
    print(f"  square(7): {square(7)}")
    
    print()


def example_4_list_comprehensions():
    """Example 4: List comprehensions and generators"""
    print("=" * 60)
    print("Example 4: List Comprehensions")
    print("=" * 60)
    
    # Basic list comprehension
    squares = [x**2 for x in range(10)]
    print(f"Squares: {squares}")
    
    # With condition
    even_squares = [x**2 for x in range(10) if x % 2 == 0]
    print(f"Even squares: {even_squares}")
    
    # Nested comprehension
    matrix = [[i * j for j in range(1, 4)] for i in range(1, 4)]
    print(f"\nMultiplication table (3x3):")
    for row in matrix:
        print(f"  {row}")
    
    # Dictionary comprehension
    square_dict = {x: x**2 for x in range(5)}
    print(f"\nSquare dictionary: {square_dict}")
    
    # Set comprehension
    unique_lengths = {len(word) for word in ["hello", "world", "python", "code"]}
    print(f"Unique word lengths: {unique_lengths}")
    
    print()


def example_5_data_structures():
    """Example 5: Working with data structures"""
    print("=" * 60)
    print("Example 5: Data Structures")
    print("=" * 60)
    
    # Lists
    fruits = ["apple", "banana", "cherry"]
    print(f"List: {fruits}")
    fruits.append("date")
    print(f"After append: {fruits}")
    print(f"First item: {fruits[0]}")
    print(f"Last item: {fruits[-1]}")
    print(f"Slice [1:3]: {fruits[1:3]}")
    
    # Tuples (immutable)
    point = (10, 20, 30)
    print(f"\nTuple: {point}")
    x, y, z = point
    print(f"Unpacked: x={x}, y={y}, z={z}")
    
    # Dictionaries
    person = {
        "name": "Alice",
        "age": 30,
        "city": "New York"
    }
    print(f"\nDictionary: {person}")
    print(f"Name: {person['name']}")
    print(f"Keys: {list(person.keys())}")
    print(f"Values: {list(person.values())}")
    
    # Sets (unique elements)
    numbers = {1, 2, 3, 3, 4, 4, 5}
    print(f"\nSet: {numbers}")  # Duplicates removed
    
    print()


def example_6_string_formatting():
    """Example 6: String formatting techniques"""
    print("=" * 60)
    print("Example 6: String Formatting")
    print("=" * 60)
    
    name = "Alice"
    age = 30
    pi = 3.14159265359
    
    # f-strings (recommended)
    print(f"f-string: {name} is {age} years old")
    print(f"f-string with expression: {name.upper()} is {age * 12} months old")
    print(f"f-string with formatting: π ≈ {pi:.2f}")
    
    # format() method
    print("\nformat(): {} is {} years old".format(name, age))
    print("format(): {1} is {0} years old".format(age, name))  # Positional
    print("format(): {name} is {age} years old".format(name=name, age=age))  # Named
    
    # %-formatting (old style)
    print("\n%%-formatting: %s is %d years old" % (name, age))
    
    # Alignment and padding
    print(f"\nLeft aligned:  |{name:<10}|")
    print(f"Right aligned: |{name:>10}|")
    print(f"Centered:      |{name:^10}|")
    
    print()


def example_7_control_flow():
    """Example 7: Control flow structures"""
    print("=" * 60)
    print("Example 7: Control Flow")
    print("=" * 60)
    
    # If-elif-else
    def describe_number(n):
        if n > 0:
            return "positive"
        elif n < 0:
            return "negative"
        else:
            return "zero"
    
    print("If-elif-else:")
    for num in [-5, 0, 5]:
        print(f"  {num} is {describe_number(num)}")
    
    # For loops
    print("\nFor loop:")
    for i in range(5):
        print(f"  Iteration {i}")
    
    # While loops
    print("\nWhile loop:")
    count = 0
    while count < 3:
        print(f"  Count: {count}")
        count += 1
    
    # List iteration with enumerate
    print("\nEnumerate:")
    colors = ["red", "green", "blue"]
    for index, color in enumerate(colors):
        print(f"  {index}: {color}")
    
    # Dictionary iteration
    print("\nDictionary iteration:")
    scores = {"Alice": 95, "Bob": 87, "Charlie": 92}
    for name, score in scores.items():
        print(f"  {name}: {score}")
    
    print()


def example_8_file_operations():
    """Example 8: File operations (read/write)"""
    print("=" * 60)
    print("Example 8: File Operations")
    print("=" * 60)
    
    # Note: This is a demonstration - actual file operations
    # would be run in a real REPL session
    
    # Writing to a file
    print("Writing to file:")
    print("  with open('example.txt', 'w') as f:")
    print("      f.write('Hello, World!\\n')")
    print("      f.write('PyREPL is awesome!')")
    
    # Reading from a file
    print("\nReading from file:")
    print("  with open('example.txt', 'r') as f:")
    print("      content = f.read()")
    print("      print(content)")
    
    # Reading line by line
    print("\nReading line by line:")
    print("  with open('example.txt', 'r') as f:")
    print("      for line in f:")
    print("          print(line.strip())")
    
    # Using pathlib (modern approach)
    print("\nUsing pathlib:")
    print("  from pathlib import Path")
    print("  path = Path('example.txt')")
    print("  path.write_text('Hello, PyREPL!')")
    print("  content = path.read_text()")
    
    print()


def example_9_error_handling():
    """Example 9: Exception handling"""
    print("=" * 60)
    print("Example 9: Error Handling")
    print("=" * 60)
    
    # Basic try-except
    def divide(a, b):
        try:
            result = a / b
            return result
        except ZeroDivisionError:
            return "Cannot divide by zero!"
    
    print(f"divide(10, 2): {divide(10, 2)}")
    print(f"divide(10, 0): {divide(10, 0)}")
    
    # Multiple exceptions
    def safe_convert(value):
        try:
            return int(value)
        except ValueError:
            return f"'{value}' is not a valid integer"
        except TypeError:
            return f"Cannot convert type {type(value).__name__} to int"
    
    print(f"\nsafe_convert('42'): {safe_convert('42')}")
    print(f"safe_convert('hello'): {safe_convert('hello')}")
    print(f"safe_convert([1, 2, 3]): {safe_convert([1, 2, 3])}")
    
    # Try-except-else-finally
    def read_file_safe(filename):
        try:
            with open(filename, 'r') as f:
                return f.read()
        except FileNotFoundError:
            return f"File '{filename}' not found"
        except PermissionError:
            return f"Permission denied for '{filename}'"
        else:
            print("File read successfully")
        finally:
            print("Cleanup completed")
    
    print()


def example_10_imports():
    """Example 10: Importing and using modules"""
    print("=" * 60)
    print("Example 10: Imports")
    print("=" * 60)
    
    # Standard library imports
    import math
    import random
    import datetime
    from collections import Counter
    
    # Math operations
    print(f"math.pi: {math.pi}")
    print(f"math.sqrt(16): {math.sqrt(16)}")
    print(f"math.factorial(5): {math.factorial(5)}")
    
    # Random operations
    print(f"\nrandom.randint(1, 10): {random.randint(1, 10)}")
    print(f"random.choice(['a', 'b', 'c']): {random.choice(['a', 'b', 'c'])}")
    
    # Datetime operations
    now = datetime.datetime.now()
    print(f"\ndatetime.now(): {now}")
    print(f"Today's date: {now.date()}")
    print(f"Current time: {now.time()}")
    
    # Collections
    words = ["apple", "banana", "apple", "cherry", "banana", "apple"]
    counter = Counter(words)
    print(f"\nCounter example:")
    print(f"  Words: {words}")
    print(f"  Counts: {counter}")
    print(f"  Most common: {counter.most_common(2)}")
    
    print()


def run_all_examples():
    """Run all examples in sequence"""
    examples = [
        example_1_simple_expressions,
        example_2_variables,
        example_3_functions,
        example_4_list_comprehensions,
        example_5_data_structures,
        example_6_string_formatting,
        example_7_control_flow,
        example_8_file_operations,
        example_9_error_handling,
        example_10_imports,
    ]
    
    print("\n" + "=" * 60)
    print("PYREPL BASIC USAGE EXAMPLES")
    print("=" * 60 + "\n")
    
    for example in examples:
        example()
        input("Press Enter to continue to next example...")
        print("\n")
    
    print("=" * 60)
    print("All examples completed!")
    print("=" * 60)


if __name__ == "__main__":
    # When run as a script, execute all examples
    run_all_examples()
else:
    # When imported, provide instructions
    print("Basic Usage Examples loaded!")
    print("\nAvailable examples:")
    print("  - example_1_simple_expressions()")
    print("  - example_2_variables()")
    print("  - example_3_functions()")
    print("  - example_4_list_comprehensions()")
    print("  - example_5_data_structures()")
    print("  - example_6_string_formatting()")
    print("  - example_7_control_flow()")
    print("  - example_8_file_operations()")
    print("  - example_9_error_handling()")
    print("  - example_10_imports()")
    print("\nRun all: run_all_examples()")
