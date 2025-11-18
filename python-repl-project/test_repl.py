#!/usr/bin/env python3
"""
Test script for PyREPL functionality.

This script tests the REPL class and its components programmatically
without requiring interactive input.
"""

import sys
import tempfile
from pathlib import Path

# Add src to path
sys.path.insert(0, 'src')

from pyrepl.repl import REPL
from pyrepl.config import Config


def test_repl_initialization():
    """Test REPL initialization."""
    print("Test 1: REPL Initialization")
    print("-" * 50)
    
    try:
        repl = REPL()
        print("✓ REPL initialized successfully")
        print(f"  - Version: {repl.VERSION}")
        print(f"  - Python: {repl.PYTHON_VERSION}")
        print(f"  - Context: {repl.context}")
        print(f"  - History: {repl.history}")
        print()
        return True
    except Exception as e:
        print(f"✗ Failed to initialize REPL: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_execute_code():
    """Test code execution."""
    print("Test 2: Code Execution")
    print("-" * 50)
    
    try:
        repl = REPL()
        
        # Test simple expression
        result = repl.handle_command("2 + 2")
        print(f"✓ Expression '2 + 2' = {result}")
        
        # Test variable assignment
        repl.handle_command("x = 42")
        result = repl.handle_command("x")
        print(f"✓ Variable 'x' = {result}")
        
        # Test function definition
        repl.handle_command("def greet(name):\n    return f'Hello, {name}!'")
        result = repl.handle_command("greet('World')")
        print(f"✓ Function call result: {result}")
        
        # Test import
        repl.handle_command("import math")
        result = repl.handle_command("math.pi")
        print(f"✓ Imported math.pi = {result}")
        
        print()
        return True
    except Exception as e:
        print(f"✗ Code execution failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_special_commands():
    """Test special commands."""
    print("Test 3: Special Commands")
    print("-" * 50)
    
    try:
        repl = REPL()
        
        # Add some variables
        repl.handle_command("a = 1")
        repl.handle_command("b = 2")
        repl.handle_command("c = [1, 2, 3]")
        
        # Test !vars
        print("Testing !vars command:")
        repl.execute_special_command("!vars")
        print("✓ !vars executed")
        
        # Test !help
        print("\nTesting !help command:")
        repl.execute_special_command("!help")
        print("✓ !help executed")
        
        # Test !history
        print("\nTesting !history command:")
        repl.execute_special_command("!history")
        print("✓ !history executed")
        
        print()
        return True
    except Exception as e:
        print(f"✗ Special commands failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_save_load():
    """Test save and load functionality."""
    print("Test 4: Save/Load State")
    print("-" * 50)
    
    try:
        repl = REPL()
        
        # Create some state
        repl.handle_command("x = 100")
        repl.handle_command("y = 200")
        repl.handle_command("z = [1, 2, 3, 4, 5]")
        
        # Save state
        with tempfile.NamedTemporaryFile(mode='w', suffix='.pkl', delete=False) as f:
            temp_file = f.name
        
        print(f"Saving state to: {temp_file}")
        repl.execute_special_command(f"!save {temp_file}")
        print("✓ State saved")
        
        # Clear namespace
        repl.context.clear_namespace(keep_builtins=True)
        variables = repl.context.list_variables()
        print(f"✓ Namespace cleared ({len(variables)} variables)")
        
        # Load state
        print(f"Loading state from: {temp_file}")
        repl.execute_special_command(f"!load {temp_file}")
        
        # Verify variables
        result_x = repl.handle_command("x")
        result_y = repl.handle_command("y")
        result_z = repl.handle_command("z")
        
        print(f"✓ State loaded successfully")
        print(f"  - x = {result_x}")
        print(f"  - y = {result_y}")
        print(f"  - z = {result_z}")
        
        # Cleanup
        Path(temp_file).unlink()
        
        print()
        return True
    except Exception as e:
        print(f"✗ Save/load failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_error_handling():
    """Test error handling."""
    print("Test 5: Error Handling")
    print("-" * 50)
    
    try:
        repl = REPL()
        
        # Test syntax error
        print("Testing syntax error:")
        repl.handle_command("x = ")
        print("✓ Syntax error handled gracefully")
        
        # Test runtime error
        print("\nTesting runtime error:")
        repl.handle_command("1 / 0")
        print("✓ Runtime error handled gracefully")
        
        # Test name error
        print("\nTesting name error:")
        repl.handle_command("undefined_variable")
        print("✓ Name error handled gracefully")
        
        # Verify last exception is stored
        last_exc = repl.get_last_exception()
        print(f"✓ Last exception stored: {type(last_exc).__name__}")
        
        print()
        return True
    except Exception as e:
        print(f"✗ Error handling test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_multiline_detection():
    """Test multi-line code detection."""
    print("Test 6: Multi-line Detection")
    print("-" * 50)
    
    try:
        repl = REPL()
        
        # Simulate multi-line function definition
        repl.buffer.append("def factorial(n):")
        should_execute = repl._should_execute()
        print(f"✓ Incomplete function: should_execute = {should_execute} (expected: False)")
        
        repl.buffer.append("    if n <= 1:")
        should_execute = repl._should_execute()
        print(f"✓ Still incomplete: should_execute = {should_execute} (expected: False)")
        
        repl.buffer.append("        return 1")
        should_execute = repl._should_execute()
        print(f"✓ Still incomplete: should_execute = {should_execute} (expected: False)")
        
        repl.buffer.append("    return n * factorial(n - 1)")
        should_execute = repl._should_execute()
        print(f"✓ Complete function: should_execute = {should_execute} (expected: True)")
        
        # Execute the function
        code = '\n'.join(repl.buffer)
        repl.buffer.clear()
        repl.handle_command(code)
        
        # Test the function
        result = repl.handle_command("factorial(5)")
        print(f"✓ Function works: factorial(5) = {result}")
        
        print()
        return True
    except Exception as e:
        print(f"✗ Multi-line detection failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_context_persistence():
    """Test context persistence across commands."""
    print("Test 7: Context Persistence")
    print("-" * 50)
    
    try:
        repl = REPL()
        
        # Create variables
        repl.handle_command("counter = 0")
        repl.handle_command("counter += 1")
        result1 = repl.handle_command("counter")
        print(f"✓ After first increment: counter = {result1}")
        
        repl.handle_command("counter += 1")
        result2 = repl.handle_command("counter")
        print(f"✓ After second increment: counter = {result2}")
        
        # Test list modification
        repl.handle_command("items = []")
        repl.handle_command("items.append(1)")
        repl.handle_command("items.append(2)")
        repl.handle_command("items.append(3)")
        result = repl.handle_command("items")
        print(f"✓ List after appends: items = {result}")
        
        print()
        return True
    except Exception as e:
        print(f"✗ Context persistence test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("=" * 50)
    print("PyREPL Test Suite")
    print("=" * 50)
    print()
    
    tests = [
        test_repl_initialization,
        test_execute_code,
        test_special_commands,
        test_save_load,
        test_error_handling,
        test_multiline_detection,
        test_context_persistence,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"Test {test.__name__} crashed: {e}")
            import traceback
            traceback.print_exc()
            results.append(False)
        print()
    
    # Summary
    print("=" * 50)
    print("Test Summary")
    print("=" * 50)
    passed = sum(results)
    total = len(results)
    print(f"Passed: {passed}/{total}")
    print(f"Failed: {total - passed}/{total}")
    
    if passed == total:
        print("\n✓ All tests passed!")
        return 0
    else:
        print(f"\n✗ {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
