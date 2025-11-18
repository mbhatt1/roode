"""
Unit tests for the ExecutionContext class.
"""

import pytest
import tempfile
import os
from pathlib import Path
from src.pyrepl.context import ExecutionContext


class TestExecutionContext:
    """Test suite for ExecutionContext class."""
    
    def test_initialization(self):
        """Test context initialization."""
        context = ExecutionContext()
        assert context is not None
        assert '__builtins__' in context._globals
        assert '__name__' in context._globals
    
    def test_initialization_with_globals(self):
        """Test context initialization with custom globals."""
        initial = {'custom_var': 42}
        context = ExecutionContext(initial_globals=initial)
        assert context.get_variable('custom_var') == 42
    
    def test_execute_expression(self):
        """Test executing a simple expression."""
        context = ExecutionContext()
        result = context.execute_code("2 + 2")
        assert result == 4
    
    def test_execute_statement(self):
        """Test executing a statement."""
        context = ExecutionContext()
        result = context.execute_code("x = 10")
        assert result is None
        assert context.get_variable('x') == 10
    
    def test_execute_multiline(self):
        """Test executing multiline code."""
        context = ExecutionContext()
        code = """
def greet(name):
    return f"Hello, {name}!"
"""
        context.execute_code(code)
        assert callable(context.get_variable('greet'))
        
        result = context.execute_code("greet('World')")
        assert result == "Hello, World!"
    
    def test_execute_with_exception(self):
        """Test that exceptions are properly raised."""
        context = ExecutionContext()
        with pytest.raises(ZeroDivisionError):
            context.execute_code("1 / 0")
    
    def test_execute_empty_code(self):
        """Test executing empty code."""
        context = ExecutionContext()
        result = context.execute_code("")
        assert result is None
        result = context.execute_code("   ")
        assert result is None
    
    def test_get_variable(self):
        """Test getting a variable."""
        context = ExecutionContext()
        context.execute_code("my_var = 'test'")
        assert context.get_variable('my_var') == 'test'
    
    def test_get_nonexistent_variable(self):
        """Test getting a non-existent variable."""
        context = ExecutionContext()
        with pytest.raises(NameError):
            context.get_variable('nonexistent')
    
    def test_set_variable(self):
        """Test setting a variable."""
        context = ExecutionContext()
        context.set_variable('test_var', 100)
        assert context.get_variable('test_var') == 100
    
    def test_has_variable(self):
        """Test checking if a variable exists."""
        context = ExecutionContext()
        context.set_variable('exists', True)
        assert context.has_variable('exists')
        assert not context.has_variable('does_not_exist')
    
    def test_list_variables(self):
        """Test listing variables."""
        context = ExecutionContext()
        context.execute_code("a = 1")
        context.execute_code("b = 2")
        context.execute_code("c = 3")
        
        variables = context.list_variables()
        assert 'a' in variables
        assert 'b' in variables
        assert 'c' in variables
        assert variables['a'] == 1
        assert variables['b'] == 2
        assert variables['c'] == 3
    
    def test_list_variables_excludes_modules(self):
        """Test that list_variables excludes modules."""
        context = ExecutionContext()
        context.execute_code("import os")
        context.execute_code("x = 42")
        
        variables = context.list_variables()
        assert 'os' not in variables
        assert 'x' in variables
    
    def test_list_modules(self):
        """Test listing imported modules."""
        context = ExecutionContext()
        context.execute_code("import os")
        context.execute_code("import sys")
        
        modules = context.list_modules()
        assert 'os' in modules
        assert 'sys' in modules
    
    def test_get_variable_info(self):
        """Test getting variable information."""
        context = ExecutionContext()
        context.execute_code("test_list = [1, 2, 3]")
        
        info = context.get_variable_info('test_list')
        assert info['name'] == 'test_list'
        assert info['type'] == 'list'
        assert info['length'] == 3
        assert info['callable'] is False
    
    def test_get_variable_info_function(self):
        """Test getting information about a function."""
        context = ExecutionContext()
        context.execute_code("def my_func(x, y): return x + y")
        
        info = context.get_variable_info('my_func')
        assert info['name'] == 'my_func'
        assert info['type'] == 'function'
        assert info['callable'] is True
        assert 'args' in info
    
    def test_clear_namespace(self):
        """Test clearing the namespace."""
        context = ExecutionContext()
        context.execute_code("x = 1")
        context.execute_code("y = 2")
        
        context.clear_namespace()
        
        assert not context.has_variable('x')
        assert not context.has_variable('y')
        assert '__builtins__' in context._globals  # Builtins preserved
    
    def test_clear_namespace_without_builtins(self):
        """Test clearing namespace including builtins."""
        context = ExecutionContext()
        context.execute_code("x = 1")
        
        context.clear_namespace(keep_builtins=False)
        
        assert not context.has_variable('x')
        assert len(context._globals) == 0
    
    def test_save_and_load_state(self):
        """Test saving and loading state."""
        context1 = ExecutionContext()
        context1.execute_code("x = 42")
        context1.execute_code("y = 'hello'")
        context1.execute_code("z = [1, 2, 3]")
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pkl') as f:
            temp_file = f.name
        
        try:
            context1.save_state(temp_file)
            
            context2 = ExecutionContext()
            context2.load_state(temp_file)
            
            assert context2.get_variable('x') == 42
            assert context2.get_variable('y') == 'hello'
            assert context2.get_variable('z') == [1, 2, 3]
        finally:
            os.unlink(temp_file)
    
    def test_load_nonexistent_file(self):
        """Test loading from a non-existent file."""
        context = ExecutionContext()
        with pytest.raises(IOError):
            context.load_state('nonexistent_file.pkl')
    
    def test_export_import_state(self):
        """Test exporting and importing state."""
        context1 = ExecutionContext()
        context1.execute_code("a = 10")
        context1.execute_code("b = 20")
        
        state = context1.export_state()
        
        context2 = ExecutionContext()
        context2.import_state(state)
        
        assert context2.get_variable('a') == 10
        assert context2.get_variable('b') == 20
    
    def test_execution_history(self):
        """Test execution history tracking."""
        context = ExecutionContext()
        context.execute_code("x = 1")
        context.execute_code("y = 2")
        context.execute_code("x + y")
        
        history = context.get_history()
        assert len(history) == 3
        assert history[0] == "x = 1"
        assert history[1] == "y = 2"
        assert history[2] == "x + y"
    
    def test_clear_history(self):
        """Test clearing execution history."""
        context = ExecutionContext()
        context.execute_code("x = 1")
        context.execute_code("y = 2")
        
        context.clear_history()
        
        history = context.get_history()
        assert len(history) == 0
    
    def test_get_namespace(self):
        """Test getting the namespace."""
        context = ExecutionContext()
        context.execute_code("x = 100")
        
        globals_dict, locals_dict = context.get_namespace()
        assert 'x' in globals_dict
        assert globals_dict['x'] == 100
    
    def test_introspect_variable(self):
        """Test introspecting a specific variable."""
        context = ExecutionContext()
        context.execute_code("my_list = [1, 2, 3, 4, 5]")
        
        info = context.introspect('my_list')
        assert info['name'] == 'my_list'
        assert info['type'] == 'list'
        assert info['length'] == 5
    
    def test_introspect_nonexistent(self):
        """Test introspecting a non-existent object."""
        context = ExecutionContext()
        info = context.introspect('nonexistent')
        assert 'error' in info
    
    def test_introspect_all(self):
        """Test introspecting entire namespace."""
        context = ExecutionContext()
        context.execute_code("x = 42")
        context.execute_code("def my_func(): pass")
        context.execute_code("class MyClass: pass")
        context.execute_code("import os")
        
        info = context.introspect()
        assert 'x' in info['variables']
        assert 'my_func' in info['functions']
        assert 'MyClass' in info['classes']
        assert 'os' in info['modules']
    
    def test_introspect_class(self):
        """Test introspecting a class."""
        context = ExecutionContext()
        context.execute_code("""
class TestClass:
    def __init__(self):
        self.value = 0
    
    def increment(self):
        self.value += 1
""")
        
        info = context.introspect('TestClass')
        assert info['type'] == 'type'
        assert 'object' in [b for b in info['bases']]
    
    def test_variable_persistence(self):
        """Test that variables persist across multiple executions."""
        context = ExecutionContext()
        context.execute_code("counter = 0")
        context.execute_code("counter += 1")
        context.execute_code("counter += 1")
        
        assert context.get_variable('counter') == 2
    
    def test_import_persistence(self):
        """Test that imports persist in the context."""
        context = ExecutionContext()
        context.execute_code("import math")
        result = context.execute_code("math.pi")
        
        assert abs(result - 3.14159) < 0.001
    
    def test_function_definition_and_call(self):
        """Test defining and calling functions."""
        context = ExecutionContext()
        context.execute_code("""
def factorial(n):
    if n <= 1:
        return 1
    return n * factorial(n - 1)
""")
        
        result = context.execute_code("factorial(5)")
        assert result == 120
    
    def test_class_instantiation(self):
        """Test class definition and instantiation."""
        context = ExecutionContext()
        context.execute_code("""
class Counter:
    def __init__(self):
        self.count = 0
    
    def increment(self):
        self.count += 1
        return self.count
""")
        
        context.execute_code("c = Counter()")
        context.execute_code("c.increment()")
        result = context.execute_code("c.increment()")
        
        assert result == 2
    
    def test_repr(self):
        """Test string representation."""
        context = ExecutionContext()
        context.execute_code("x = 1")
        context.execute_code("y = 2")
        context.execute_code("import os")
        
        repr_str = repr(context)
        assert 'ExecutionContext' in repr_str
        assert 'variables' in repr_str
        assert 'modules' in repr_str


class TestExecutionContextEdgeCases:
    """Test edge cases and error handling."""
    
    def test_circular_reference(self):
        """Test handling circular references."""
        context = ExecutionContext()
        context.execute_code("a = []")
        context.execute_code("a.append(a)")
        
        # Should not crash
        variables = context.list_variables()
        assert 'a' in variables
    
    def test_lambda_functions(self):
        """Test lambda functions."""
        context = ExecutionContext()
        context.execute_code("square = lambda x: x ** 2")
        result = context.execute_code("square(5)")
        
        assert result == 25
    
    def test_list_comprehension(self):
        """Test list comprehensions."""
        context = ExecutionContext()
        result = context.execute_code("[x**2 for x in range(5)]")
        
        assert result == [0, 1, 4, 9, 16]
    
    def test_dictionary_operations(self):
        """Test dictionary operations."""
        context = ExecutionContext()
        context.execute_code("d = {'a': 1, 'b': 2}")
        context.execute_code("d['c'] = 3")
        result = context.execute_code("d")
        
        assert result == {'a': 1, 'b': 2, 'c': 3}
    
    def test_exception_doesnt_corrupt_state(self):
        """Test that exceptions don't corrupt the context state."""
        context = ExecutionContext()
        context.execute_code("x = 10")
        
        try:
            context.execute_code("y = 1 / 0")
        except ZeroDivisionError:
            pass
        
        # Context should still work
        assert context.get_variable('x') == 10
        context.execute_code("z = 20")
        assert context.get_variable('z') == 20
    
    def test_large_data_structure(self):
        """Test handling large data structures."""
        context = ExecutionContext()
        context.execute_code("large_list = list(range(10000))")
        
        info = context.get_variable_info('large_list')
        assert info['length'] == 10000
    
    def test_nested_function_calls(self):
        """Test nested function calls."""
        context = ExecutionContext()
        context.execute_code("""
def outer(x):
    def inner(y):
        return y * 2
    return inner(x) + 1
""")
        
        result = context.execute_code("outer(5)")
        assert result == 11
    
    def test_generator_expression(self):
        """Test generator expressions."""
        context = ExecutionContext()
        context.execute_code("gen = (x**2 for x in range(5))")
        result = context.execute_code("list(gen)")
        
        assert result == [0, 1, 4, 9, 16]
    
    def test_multiple_assignments(self):
        """Test multiple assignments."""
        context = ExecutionContext()
        context.execute_code("a, b, c = 1, 2, 3")
        
        assert context.get_variable('a') == 1
        assert context.get_variable('b') == 2
        assert context.get_variable('c') == 3
    
    def test_unpacking(self):
        """Test sequence unpacking."""
        context = ExecutionContext()
        context.execute_code("data = [1, 2, 3, 4, 5]")
        context.execute_code("first, *middle, last = data")
        
        assert context.get_variable('first') == 1
        assert context.get_variable('middle') == [2, 3, 4]
        assert context.get_variable('last') == 5
