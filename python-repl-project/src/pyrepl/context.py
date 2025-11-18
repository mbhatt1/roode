"""
Execution context management for Python REPL.

This module provides the ExecutionContext class which manages the execution
environment including namespaces, variables, and module tracking.
"""

import pickle
import sys
from typing import Any, Dict, Optional, Set, List, Tuple
from types import ModuleType
import builtins
import json
import traceback


class ExecutionContext:
    """
    Manages the execution context for Python REPL.
    
    This class handles:
    - Global and local namespaces
    - Variable storage and retrieval
    - Module tracking
    - Introspection capabilities
    - Context save/restore operations
    """
    
    def __init__(self, initial_globals: Optional[Dict[str, Any]] = None):
        """
        Initialize the execution context.
        
        Args:
            initial_globals: Optional dictionary of initial global variables
        """
        self._globals: Dict[str, Any] = {}
        self._locals: Dict[str, Any] = {}
        self._imported_modules: Set[str] = set()
        self._execution_history: List[str] = []
        
        # Initialize with built-in functions
        self._globals.update({
            '__builtins__': builtins,
            '__name__': '__console__',
            '__doc__': None,
        })
        
        # Add any initial globals
        if initial_globals:
            self._globals.update(initial_globals)
        
        # Track initial modules
        self._track_modules()
    
    def execute_code(self, code: str) -> Any:
        """
        Execute Python code in the current context.
        
        Args:
            code: Python code string to execute
            
        Returns:
            The result of the last expression, or None
            
        Raises:
            Exception: Any exception raised during code execution
        """
        if not code or not code.strip():
            return None
        
        # Store code in history
        self._execution_history.append(code)
        
        try:
            # Try to compile as eval first (for expressions)
            try:
                compiled = compile(code, '<console>', 'eval')
                result = eval(compiled, self._globals, self._locals)
                # Merge locals back into globals for persistence
                self._globals.update(self._locals)
                self._track_modules()
                return result
            except SyntaxError:
                # If eval fails, try exec (for statements)
                compiled = compile(code, '<console>', 'exec')
                exec(compiled, self._globals, self._locals)
                # Merge locals back into globals for persistence
                self._globals.update(self._locals)
                self._track_modules()
                return None
                
        except Exception as e:
            # Re-raise the exception to be handled by the caller
            raise
    
    def get_variable(self, name: str) -> Any:
        """
        Get a variable from the context.
        
        Args:
            name: Variable name
            
        Returns:
            The variable value
            
        Raises:
            NameError: If the variable doesn't exist
        """
        # Check locals first, then globals
        if name in self._locals:
            return self._locals[name]
        elif name in self._globals:
            return self._globals[name]
        else:
            raise NameError(f"name '{name}' is not defined")
    
    def set_variable(self, name: str, value: Any) -> None:
        """
        Set a variable in the context.
        
        Args:
            name: Variable name
            value: Variable value
        """
        self._globals[name] = value
    
    def has_variable(self, name: str) -> bool:
        """
        Check if a variable exists in the context.
        
        Args:
            name: Variable name
            
        Returns:
            True if the variable exists, False otherwise
        """
        return name in self._locals or name in self._globals
    
    def list_variables(self) -> Dict[str, Any]:
        """
        List all user-defined variables in the context.
        
        Returns:
            Dictionary of variable names and their values
        """
        # Filter out built-ins and private variables
        excluded_names = {
            '__builtins__', '__name__', '__doc__', '__package__',
            '__loader__', '__spec__', '__annotations__', '__cached__'
        }
        
        variables = {}
        
        # Collect from globals
        for name, value in self._globals.items():
            if (not name.startswith('_') or name.startswith('__')) and name not in excluded_names:
                if not isinstance(value, ModuleType):
                    variables[name] = value
        
        # Collect from locals (override globals if present)
        for name, value in self._locals.items():
            if (not name.startswith('_') or name.startswith('__')) and name not in excluded_names:
                if not isinstance(value, ModuleType):
                    variables[name] = value
        
        return variables
    
    def list_modules(self) -> List[str]:
        """
        List all imported modules.
        
        Returns:
            List of module names
        """
        return sorted(self._imported_modules)
    
    def get_variable_info(self, name: str) -> Dict[str, Any]:
        """
        Get detailed information about a variable.
        
        Args:
            name: Variable name
            
        Returns:
            Dictionary containing variable information
            
        Raises:
            NameError: If the variable doesn't exist
        """
        value = self.get_variable(name)
        
        info = {
            'name': name,
            'type': type(value).__name__,
            'value': repr(value),
            'module': type(value).__module__,
            'doc': getattr(value, '__doc__', None),
        }
        
        # Add size information for collections
        if hasattr(value, '__len__'):
            try:
                info['length'] = len(value)
            except:
                pass
        
        # Add callable information
        if callable(value):
            info['callable'] = True
            if hasattr(value, '__code__'):
                code = value.__code__
                info['args'] = code.co_varnames[:code.co_argcount]
        else:
            info['callable'] = False
        
        return info
    
    def clear_namespace(self, keep_builtins: bool = True) -> None:
        """
        Clear the execution namespace.
        
        Args:
            keep_builtins: If True, preserve built-in functions
        """
        if keep_builtins:
            # Reset to initial state
            builtins_ref = self._globals.get('__builtins__')
            self._globals.clear()
            self._locals.clear()
            self._globals.update({
                '__builtins__': builtins_ref,
                '__name__': '__console__',
                '__doc__': None,
            })
        else:
            self._globals.clear()
            self._locals.clear()
        
        self._imported_modules.clear()
        self._execution_history.clear()
    
    def save_state(self, filename: str) -> None:
        """
        Save the current execution state to a file.
        
        Args:
            filename: Path to the output file
            
        Raises:
            IOError: If the file cannot be written
            pickle.PicklingError: If objects cannot be serialized
        """
        # Prepare state for serialization
        state = {
            'variables': {},
            'modules': list(self._imported_modules),
            'history': self._execution_history.copy(),
        }
        
        # Only save picklable variables
        for name, value in self.list_variables().items():
            try:
                # Test if the value is picklable
                pickle.dumps(value)
                state['variables'][name] = value
            except (pickle.PicklingError, TypeError, AttributeError) as e:
                # Skip non-picklable objects
                print(f"Warning: Cannot save variable '{name}': {e}", file=sys.stderr)
        
        # Save to file
        try:
            with open(filename, 'wb') as f:
                pickle.dump(state, f, protocol=pickle.HIGHEST_PROTOCOL)
        except Exception as e:
            raise IOError(f"Failed to save state to '{filename}': {e}")
    
    def load_state(self, filename: str) -> None:
        """
        Load execution state from a file.
        
        Args:
            filename: Path to the input file
            
        Raises:
            IOError: If the file cannot be read
            pickle.UnpicklingError: If the file is corrupted
        """
        try:
            with open(filename, 'rb') as f:
                state = pickle.load(f)
        except FileNotFoundError:
            raise IOError(f"State file '{filename}' not found")
        except Exception as e:
            raise IOError(f"Failed to load state from '{filename}': {e}")
        
        # Validate state structure
        if not isinstance(state, dict):
            raise ValueError("Invalid state file format")
        
        # Restore variables
        if 'variables' in state:
            for name, value in state['variables'].items():
                self._globals[name] = value
        
        # Restore module tracking
        if 'modules' in state:
            self._imported_modules = set(state['modules'])
        
        # Restore history
        if 'history' in state:
            self._execution_history = state['history']
    
    def export_state(self) -> Dict[str, Any]:
        """
        Export the current state as a dictionary.
        
        Returns:
            Dictionary containing the current state
        """
        return {
            'variables': self.list_variables(),
            'modules': self.list_modules(),
            'history': self._execution_history.copy(),
        }
    
    def import_state(self, state: Dict[str, Any]) -> None:
        """
        Import state from a dictionary.
        
        Args:
            state: Dictionary containing state information
        """
        if 'variables' in state:
            for name, value in state['variables'].items():
                self._globals[name] = value
        
        if 'modules' in state:
            self._imported_modules = set(state['modules'])
        
        if 'history' in state:
            self._execution_history = list(state['history'])
    
    def get_history(self) -> List[str]:
        """
        Get the execution history.
        
        Returns:
            List of executed code strings
        """
        return self._execution_history.copy()
    
    def clear_history(self) -> None:
        """Clear the execution history."""
        self._execution_history.clear()
    
    def get_namespace(self) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Get the current global and local namespaces.
        
        Returns:
            Tuple of (globals, locals) dictionaries
        """
        return (self._globals.copy(), self._locals.copy())
    
    def _track_modules(self) -> None:
        """Track imported modules in the namespace."""
        for name, value in self._globals.items():
            if isinstance(value, ModuleType):
                self._imported_modules.add(name)
    
    def introspect(self, obj_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Perform introspection on an object or the entire namespace.
        
        Args:
            obj_name: Optional name of object to introspect. If None, introspect all.
            
        Returns:
            Dictionary containing introspection information
        """
        if obj_name:
            # Introspect specific object
            try:
                obj = self.get_variable(obj_name)
                return self._introspect_object(obj, obj_name)
            except NameError:
                return {'error': f"Object '{obj_name}' not found"}
        else:
            # Introspect entire namespace
            result = {
                'variables': {},
                'functions': {},
                'classes': {},
                'modules': {},
            }
            
            for name, value in self._globals.items():
                if name.startswith('_'):
                    continue
                
                if isinstance(value, ModuleType):
                    result['modules'][name] = {
                        'type': 'module',
                        'doc': getattr(value, '__doc__', None),
                    }
                elif isinstance(value, type):
                    result['classes'][name] = {
                        'type': 'class',
                        'bases': [b.__name__ for b in value.__bases__],
                        'doc': getattr(value, '__doc__', None),
                    }
                elif callable(value):
                    result['functions'][name] = {
                        'type': 'function',
                        'doc': getattr(value, '__doc__', None),
                    }
                else:
                    result['variables'][name] = {
                        'type': type(value).__name__,
                        'value': repr(value)[:100],  # Limit length
                    }
            
            return result
    
    def _introspect_object(self, obj: Any, name: str) -> Dict[str, Any]:
        """
        Introspect a single object.
        
        Args:
            obj: Object to introspect
            name: Name of the object
            
        Returns:
            Dictionary containing object information
        """
        info = {
            'name': name,
            'type': type(obj).__name__,
            'module': type(obj).__module__,
            'doc': getattr(obj, '__doc__', None),
            'attributes': [],
            'methods': [],
        }
        
        # Get attributes and methods
        for attr_name in dir(obj):
            if attr_name.startswith('_'):
                continue
            
            try:
                attr_value = getattr(obj, attr_name)
                if callable(attr_value):
                    info['methods'].append(attr_name)
                else:
                    info['attributes'].append(attr_name)
            except:
                pass
        
        # Add type-specific information
        if isinstance(obj, (list, tuple, set, dict)):
            info['length'] = len(obj)
        
        if isinstance(obj, type):
            info['bases'] = [b.__name__ for b in obj.__bases__]
        
        if callable(obj) and hasattr(obj, '__code__'):
            code = obj.__code__
            info['signature'] = {
                'args': code.co_varnames[:code.co_argcount],
                'filename': code.co_filename,
                'line': code.co_firstlineno,
            }
        
        return info
    
    def __repr__(self) -> str:
        """String representation of the execution context."""
        var_count = len(self.list_variables())
        mod_count = len(self._imported_modules)
        return f"<ExecutionContext: {var_count} variables, {mod_count} modules>"
