"""
Example usage of the ExecutionContext class.

This script demonstrates various features of the ExecutionContext including:
- Code execution
- Variable management
- Module tracking
- State save/load
- Introspection
"""

import sys
import os
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.pyrepl.context import ExecutionContext


def print_section(title):
    """Print a formatted section header."""
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}\n")


def main():
    """Demonstrate ExecutionContext features."""
    
    # Create a new execution context
    print_section("1. Creating ExecutionContext")
    context = ExecutionContext()
    print(f"Context created: {context}")
    
    # Execute simple expressions
    print_section("2. Executing Expressions")
    result = context.execute_code("2 + 2")
    print(f"2 + 2 = {result}")
    
    result = context.execute_code("'Hello' + ' ' + 'World'")
    print(f"'Hello' + ' ' + 'World' = {result}")
    
    # Execute statements and define variables
    print_section("3. Variable Management")
    context.execute_code("x = 10")
    context.execute_code("y = 20")
    context.execute_code("z = x + y")
    
    print(f"x = {context.get_variable('x')}")
    print(f"y = {context.get_variable('y')}")
    print(f"z = {context.get_variable('z')}")
    
    # List all variables
    print("\nAll variables:")
    for name, value in context.list_variables().items():
        print(f"  {name} = {value}")
    
    # Define and use functions
    print_section("4. Function Definition and Execution")
    context.execute_code("""
def fibonacci(n):
    '''Calculate the nth Fibonacci number.'''
    if n <= 1:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)
""")
    
    result = context.execute_code("fibonacci(10)")
    print(f"fibonacci(10) = {result}")
    
    # Get detailed variable info
    print("\nFunction information:")
    func_info = context.get_variable_info('fibonacci')
    for key, value in func_info.items():
        print(f"  {key}: {value}")
    
    # Define and use classes
    print_section("5. Class Definition and Instantiation")
    context.execute_code("""
class Calculator:
    '''Simple calculator class.'''
    
    def __init__(self):
        self.result = 0
    
    def add(self, x):
        self.result += x
        return self.result
    
    def multiply(self, x):
        self.result *= x
        return self.result
    
    def get_result(self):
        return self.result
""")
    
    context.execute_code("calc = Calculator()")
    context.execute_code("calc.add(5)")
    context.execute_code("calc.add(3)")
    result = context.execute_code("calc.get_result()")
    print(f"Calculator result: {result}")
    
    # Import and use modules
    print_section("6. Module Imports")
    context.execute_code("import math")
    context.execute_code("import random")
    
    result = context.execute_code("math.pi")
    print(f"math.pi = {result}")
    
    result = context.execute_code("math.sqrt(16)")
    print(f"math.sqrt(16) = {result}")
    
    print("\nImported modules:")
    for module_name in context.list_modules():
        print(f"  - {module_name}")
    
    # Introspection
    print_section("7. Introspection")
    
    # Introspect a specific variable
    context.execute_code("my_list = [1, 2, 3, 4, 5]")
    print("Introspecting 'my_list':")
    list_info = context.introspect('my_list')
    for key, value in list_info.items():
        print(f"  {key}: {value}")
    
    # Introspect entire namespace
    print("\nNamespace overview:")
    namespace_info = context.introspect()
    
    print(f"\n  Variables ({len(namespace_info['variables'])}):")
    for name in list(namespace_info['variables'].keys())[:5]:
        print(f"    - {name}")
    
    print(f"\n  Functions ({len(namespace_info['functions'])}):")
    for name in namespace_info['functions'].keys():
        print(f"    - {name}")
    
    print(f"\n  Classes ({len(namespace_info['classes'])}):")
    for name in namespace_info['classes'].keys():
        print(f"    - {name}")
    
    print(f"\n  Modules ({len(namespace_info['modules'])}):")
    for name in namespace_info['modules'].keys():
        print(f"    - {name}")
    
    # Execution history
    print_section("8. Execution History")
    history = context.get_history()
    print(f"Total executions: {len(history)}")
    print("\nLast 5 executions:")
    for i, code in enumerate(history[-5:], 1):
        print(f"  {i}. {code[:50]}{'...' if len(code) > 50 else ''}")
    
    # Save and load state
    print_section("9. State Persistence")
    
    # Save current state
    state_file = "/tmp/repl_state.pkl"
    context.save_state(state_file)
    print(f"State saved to: {state_file}")
    
    # Create a new context and load the state
    new_context = ExecutionContext()
    new_context.load_state(state_file)
    print(f"State loaded into new context")
    
    # Verify variables were restored
    print("\nVerifying restored variables:")
    print(f"  x = {new_context.get_variable('x')}")
    print(f"  y = {new_context.get_variable('y')}")
    print(f"  z = {new_context.get_variable('z')}")
    
    # Clean up
    if os.path.exists(state_file):
        os.remove(state_file)
    
    # Export/import state as dictionary
    print_section("10. State Export/Import")
    state_dict = context.export_state()
    
    print("Exported state contains:")
    print(f"  - {len(state_dict['variables'])} variables")
    print(f"  - {len(state_dict['modules'])} modules")
    print(f"  - {len(state_dict['history'])} history entries")
    
    another_context = ExecutionContext()
    another_context.import_state(state_dict)
    print("\nState imported into another context")
    
    # Error handling
    print_section("11. Error Handling")
    
    print("Attempting division by zero:")
    try:
        context.execute_code("1 / 0")
    except ZeroDivisionError as e:
        print(f"  Caught exception: {type(e).__name__}: {e}")
    
    print("\nContext remains functional after error:")
    result = context.execute_code("2 + 2")
    print(f"  2 + 2 = {result}")
    
    # Advanced features
    print_section("12. Advanced Features")
    
    # List comprehension
    result = context.execute_code("[x**2 for x in range(5)]")
    print(f"List comprehension: {result}")
    
    # Lambda functions
    context.execute_code("square = lambda x: x**2")
    result = context.execute_code("square(7)")
    print(f"Lambda function: square(7) = {result}")
    
    # Generator expression
    context.execute_code("gen = (x*2 for x in range(5))")
    result = context.execute_code("list(gen)")
    print(f"Generator expression: {result}")
    
    # Dictionary comprehension
    result = context.execute_code("{k: v**2 for k, v in zip(['a', 'b', 'c'], [1, 2, 3])}")
    print(f"Dictionary comprehension: {result}")
    
    # Clear namespace
    print_section("13. Namespace Management")
    
    print(f"Variables before clear: {len(context.list_variables())}")
    context.clear_namespace()
    print(f"Variables after clear: {len(context.list_variables())}")
    print("Namespace cleared successfully!")
    
    # Final summary
    print_section("Summary")
    print("ExecutionContext provides:")
    print("  ✓ Code execution (expressions and statements)")
    print("  ✓ Variable and function management")
    print("  ✓ Module import tracking")
    print("  ✓ State persistence (save/load)")
    print("  ✓ Introspection capabilities")
    print("  ✓ Execution history")
    print("  ✓ Robust error handling")
    print("  ✓ Support for advanced Python features")
    print()


if __name__ == '__main__':
    main()
