"""
Completion engine for Python REPL.

Provides intelligent, context-aware code completion including:
- Variables, functions, and modules
- Attribute completion via introspection
- File path completion
- Keywords and built-ins
- Import statement completion
- Smart ranking of suggestions
"""

import ast
import builtins
import glob
import inspect
import keyword
import os
import sys
from pathlib import Path
from typing import Any, List, Optional, Set, Tuple

try:
    import jedi
    JEDI_AVAILABLE = True
except ImportError:
    JEDI_AVAILABLE = False


class CompletionResult:
    """Represents a single completion suggestion."""
    
    def __init__(
        self,
        text: str,
        display: Optional[str] = None,
        type_: str = "unknown",
        priority: int = 0,
        description: Optional[str] = None
    ):
        self.text = text
        self.display = display or text
        self.type = type_
        self.priority = priority
        self.description = description
    
    def __repr__(self) -> str:
        return f"CompletionResult({self.text!r}, type={self.type})"
    
    def __eq__(self, other) -> bool:
        if isinstance(other, CompletionResult):
            return self.text == other.text
        return False
    
    def __hash__(self) -> int:
        return hash(self.text)


class CompletionEngine:
    """
    Intelligent completion engine for Python REPL.
    
    Features:
    - Context-aware completions using execution context
    - Jedi integration for advanced static analysis
    - Attribute completion via introspection
    - File path completion in strings
    - Import statement completion
    - Smart ranking based on relevance and usage
    """
    
    # Completion type priorities (higher = more relevant)
    PRIORITIES = {
        "local": 100,      # Local variables in current scope
        "parameter": 95,   # Function parameters
        "global": 90,      # Global variables
        "builtin": 80,     # Built-in functions/types
        "module": 75,      # Imported modules
        "keyword": 70,     # Python keywords
        "attribute": 85,   # Object attributes/methods
        "function": 80,    # Functions
        "class": 75,       # Classes
        "instance": 85,    # Instance variables
        "path": 60,        # File paths
        "import": 70,      # Module names for import
    }
    
    def __init__(self, use_jedi: bool = JEDI_AVAILABLE):
        """
        Initialize completion engine.
        
        Args:
            use_jedi: Whether to use Jedi for advanced completions
        """
        self.use_jedi = use_jedi and JEDI_AVAILABLE
        self._import_cache: Optional[Set[str]] = None
    
    def get_completions(
        self,
        text: str,
        context: Any = None,
        cursor_pos: Optional[int] = None
    ) -> List[str]:
        """
        Get completions for the given text.
        
        Args:
            text: Text to complete
            context: ExecutionContext with locals/globals
            cursor_pos: Cursor position in text (defaults to end)
        
        Returns:
            List of completion strings sorted by relevance
        """
        if cursor_pos is None:
            cursor_pos = len(text)
        
        # Extract the part up to cursor
        text_before_cursor = text[:cursor_pos]
        
        # Get completion results
        results = self._get_completion_results(text_before_cursor, context)
        
        # Sort by priority and alphabetically
        results.sort(key=lambda r: (-r.priority, r.text.lower()))
        
        # Return just the text
        return [r.text for r in results]
    
    def get_completion_results(
        self,
        text: str,
        context: Any = None,
        cursor_pos: Optional[int] = None
    ) -> List[CompletionResult]:
        """
        Get detailed completion results with metadata.
        
        Args:
            text: Text to complete
            context: ExecutionContext with locals/globals
            cursor_pos: Cursor position in text
        
        Returns:
            List of CompletionResult objects sorted by relevance
        """
        if cursor_pos is None:
            cursor_pos = len(text)
        
        text_before_cursor = text[:cursor_pos]
        results = self._get_completion_results(text_before_cursor, context)
        results.sort(key=lambda r: (-r.priority, r.text.lower()))
        
        return results
    
    def _get_completion_results(
        self,
        text: str,
        context: Any = None
    ) -> List[CompletionResult]:
        """Internal method to get completion results."""
        results: Set[CompletionResult] = set()
        
        # Try Jedi first for best results
        if self.use_jedi and context:
            try:
                jedi_results = self._get_jedi_completions(text, context)
                results.update(jedi_results)
            except Exception:
                # Fall back to manual completion if Jedi fails
                pass
        
        # Determine what kind of completion we need
        prefix, completion_type = self._analyze_completion_context(text)
        
        if completion_type == "attribute":
            # Completing object.attr
            results.update(self._complete_attribute_chain(text, context))
        elif completion_type == "import":
            # Completing import statement
            results.update(self._get_import_completions(prefix))
        elif completion_type == "path":
            # Completing file path
            results.update(self._get_path_completions(prefix))
        else:
            # General completion: keywords, builtins, context variables
            results.update(self._get_general_completions(prefix, context))
        
        return list(results)
    
    def _analyze_completion_context(self, text: str) -> Tuple[str, str]:
        """
        Analyze what kind of completion is needed.
        
        Returns:
            Tuple of (prefix, completion_type)
        """
        text = text.lstrip()
        
        # Check for import statement
        if text.startswith(("import ", "from ")):
            if text.startswith("from "):
                # from module import ...
                if " import " in text:
                    prefix = text.split(" import ")[-1].strip()
                else:
                    prefix = text[5:].strip()
            else:
                # import module
                prefix = text[7:].strip()
            return prefix, "import"
        
        # Check for file path (in string)
        if self._is_in_string(text):
            # Extract the string content
            quote_char = None
            for char in ['"', "'"]:
                if char in text:
                    quote_char = char
                    break
            
            if quote_char:
                parts = text.rsplit(quote_char, 1)
                if len(parts) > 1:
                    prefix = parts[-1]
                    if "/" in prefix or "\\" in prefix or prefix.startswith((".", "~")):
                        return prefix, "path"
        
        # Check for attribute access
        if "." in text:
            return text.split()[-1], "attribute"
        
        # General completion
        if " " in text or "\t" in text:
            prefix = text.split()[-1]
        else:
            prefix = text
        
        return prefix, "general"
    
    def _is_in_string(self, text: str) -> bool:
        """Check if we're currently inside a string literal."""
        single_quotes = text.count("'") - text.count("\\'")
        double_quotes = text.count('"') - text.count('\\"')
        
        return (single_quotes % 2 == 1) or (double_quotes % 2 == 1)
    
    def _get_jedi_completions(
        self,
        text: str,
        context: Any
    ) -> List[CompletionResult]:
        """Get completions using Jedi library."""
        if not JEDI_AVAILABLE:
            return []
        
        results = []
        
        try:
            # Create a Jedi script with context
            namespaces = []
            if context:
                if hasattr(context, 'globals'):
                    namespaces.append(context.globals)
                if hasattr(context, 'locals'):
                    namespaces.append(context.locals)
            
            # Use Jedi's Interpreter for REPL-style completion
            if namespaces:
                script = jedi.Interpreter(text, namespaces)
            else:
                script = jedi.Script(text)
            
            completions = script.complete()
            
            for completion in completions:
                type_map = {
                    "module": "module",
                    "class": "class",
                    "function": "function",
                    "param": "parameter",
                    "statement": "local",
                    "instance": "instance",
                    "keyword": "keyword",
                }
                
                comp_type = type_map.get(completion.type, "unknown")
                priority = self.PRIORITIES.get(comp_type, 50)
                
                # Boost priority for exact prefix matches
                if completion.name_with_symbols.startswith(completion.name):
                    priority += 5
                
                results.append(CompletionResult(
                    text=completion.name_with_symbols,
                    display=completion.name,
                    type_=comp_type,
                    priority=priority,
                    description=completion.docstring(raw=True).split("\n")[0] if completion.docstring() else None
                ))
        
        except Exception as e:
            # Jedi can fail on incomplete or invalid syntax
            pass
        
        return results
    
    def _get_general_completions(
        self,
        prefix: str,
        context: Any
    ) -> List[CompletionResult]:
        """Get general completions for variables, keywords, builtins."""
        results = []
        
        # Keywords
        for kw in keyword.kwlist:
            if kw.startswith(prefix):
                results.append(CompletionResult(
                    text=kw,
                    type_="keyword",
                    priority=self.PRIORITIES["keyword"]
                ))
        
        # Builtins
        for name in dir(builtins):
            if not name.startswith("_") and name.startswith(prefix):
                obj = getattr(builtins, name)
                type_ = "class" if isinstance(obj, type) else "builtin"
                results.append(CompletionResult(
                    text=name,
                    type_=type_,
                    priority=self.PRIORITIES["builtin"]
                ))
        
        # Context variables
        if context:
            # Local variables
            if hasattr(context, 'locals'):
                for name in context.locals:
                    if not name.startswith("_") and name.startswith(prefix):
                        results.append(CompletionResult(
                            text=name,
                            type_="local",
                            priority=self.PRIORITIES["local"]
                        ))
            
            # Global variables
            if hasattr(context, 'globals'):
                for name in context.globals:
                    if not name.startswith("_") and name.startswith(prefix):
                        # Skip if already in locals
                        if hasattr(context, 'locals') and name in context.locals:
                            continue
                        
                        obj = context.globals[name]
                        if inspect.ismodule(obj):
                            type_ = "module"
                        elif inspect.isclass(obj):
                            type_ = "class"
                        elif inspect.isfunction(obj):
                            type_ = "function"
                        else:
                            type_ = "global"
                        
                        results.append(CompletionResult(
                            text=name,
                            type_=type_,
                            priority=self.PRIORITIES.get(type_, 90)
                        ))
        
        return results
    
    def _complete_attribute_chain(
        self,
        text: str,
        context: Any
    ) -> List[CompletionResult]:
        """Complete attribute access like obj.attr or obj.method()."""
        # Split into object path and prefix
        parts = text.rsplit(".", 1)
        if len(parts) != 2:
            return []
        
        obj_expr, prefix = parts
        obj_expr = obj_expr.strip()
        
        # Try to evaluate the object
        obj = self._safe_eval(obj_expr, context)
        if obj is None:
            return []
        
        # Get attributes
        return self.complete_attribute(obj, prefix)
    
    def complete_attribute(
        self,
        obj: Any,
        prefix: str = ""
    ) -> List[CompletionResult]:
        """
        Get attribute completions for an object.
        
        Args:
            obj: Object to get attributes from
            prefix: Prefix to filter attributes
        
        Returns:
            List of CompletionResult objects
        """
        results = []
        
        try:
            # Get all attributes
            attrs = dir(obj)
            
            for attr in attrs:
                # Filter by prefix and skip private unless explicitly requested
                if not attr.startswith(prefix):
                    continue
                if attr.startswith("_") and not prefix.startswith("_"):
                    continue
                
                try:
                    attr_obj = getattr(obj, attr)
                    
                    # Determine type
                    if inspect.ismethod(attr_obj) or inspect.isfunction(attr_obj) or callable(attr_obj):
                        type_ = "function"
                        display = f"{attr}()"
                    elif inspect.isdatadescriptor(attr_obj):
                        type_ = "attribute"
                        display = attr
                    else:
                        type_ = "attribute"
                        display = attr
                    
                    # Get docstring for description
                    description = None
                    if hasattr(attr_obj, "__doc__") and attr_obj.__doc__:
                        description = attr_obj.__doc__.split("\n")[0]
                    
                    results.append(CompletionResult(
                        text=attr,
                        display=display,
                        type_=type_,
                        priority=self.PRIORITIES["attribute"],
                        description=description
                    ))
                
                except (AttributeError, Exception):
                    # Some attributes might raise on access
                    continue
        
        except Exception:
            pass
        
        return results
    
    def complete_import(self, prefix: str) -> List[str]:
        """
        Get completions for import statements.
        
        Args:
            prefix: Module name prefix
        
        Returns:
            List of module names
        """
        results = self._get_import_completions(prefix)
        return sorted([r.text for r in results])
    
    def _get_import_completions(self, prefix: str) -> List[CompletionResult]:
        """Get import completions as CompletionResult objects."""
        results = []
        
        # Handle submodule imports (e.g., os.path)
        if "." in prefix:
            parts = prefix.split(".")
            parent = ".".join(parts[:-1])
            sub_prefix = parts[-1]
            
            try:
                module = __import__(parent, fromlist=[""])
                for name in dir(module):
                    if not name.startswith("_") and name.startswith(sub_prefix):
                        attr = getattr(module, name)
                        if inspect.ismodule(attr):
                            results.append(CompletionResult(
                                text=f"{parent}.{name}",
                                type_="module",
                                priority=self.PRIORITIES["import"]
                            ))
            except ImportError:
                pass
        
        else:
            # Top-level modules
            if self._import_cache is None:
                self._build_import_cache()
            
            for module_name in self._import_cache:
                if module_name.startswith(prefix):
                    results.append(CompletionResult(
                        text=module_name,
                        type_="module",
                        priority=self.PRIORITIES["import"]
                    ))
        
        return results
    
    def _build_import_cache(self):
        """Build cache of importable module names."""
        self._import_cache = set()
        
        # Standard library and installed packages
        for path in sys.path:
            if not path or not os.path.isdir(path):
                continue
            
            try:
                for item in os.listdir(path):
                    # Python files
                    if item.endswith(".py") and not item.startswith("_"):
                        self._import_cache.add(item[:-3])
                    
                    # Packages
                    elif os.path.isdir(os.path.join(path, item)):
                        if not item.startswith("_") and not item.startswith("."):
                            # Check if it's a package
                            init_file = os.path.join(path, item, "__init__.py")
                            if os.path.exists(init_file):
                                self._import_cache.add(item)
            
            except (OSError, PermissionError):
                continue
        
        # Add commonly known modules
        common_modules = [
            "sys", "os", "re", "json", "math", "random", "datetime",
            "collections", "itertools", "functools", "pathlib", "typing",
            "asyncio", "threading", "multiprocessing", "subprocess",
            "urllib", "http", "socket", "email", "html", "xml",
        ]
        self._import_cache.update(common_modules)
    
    def complete_path(self, prefix: str) -> List[str]:
        """
        Get file path completions.
        
        Args:
            prefix: Path prefix to complete
        
        Returns:
            List of path strings
        """
        results = self._get_path_completions(prefix)
        return sorted([r.text for r in results])
    
    def _get_path_completions(self, prefix: str) -> List[CompletionResult]:
        """Get path completions as CompletionResult objects."""
        results = []
        
        try:
            # Expand user home directory
            if prefix.startswith("~"):
                prefix = os.path.expanduser(prefix)
            
            # Get directory and filename parts
            if os.path.sep in prefix or (os.altsep and os.altsep in prefix):
                dirname = os.path.dirname(prefix)
                basename = os.path.basename(prefix)
            else:
                dirname = "."
                basename = prefix
            
            # List directory contents
            if not dirname:
                dirname = "."
            
            if os.path.isdir(dirname):
                for item in os.listdir(dirname):
                    if item.startswith(basename) or not basename:
                        full_path = os.path.join(dirname, item)
                        
                        # Add trailing slash for directories
                        if os.path.isdir(full_path):
                            display = f"{item}/"
                        else:
                            display = item
                        
                        results.append(CompletionResult(
                            text=os.path.join(dirname, item) if dirname != "." else item,
                            display=display,
                            type_="path",
                            priority=self.PRIORITIES["path"]
                        ))
        
        except (OSError, PermissionError):
            pass
        
        return results
    
    def _safe_eval(self, expr: str, context: Any) -> Optional[Any]:
        """
        Safely evaluate an expression to get the object.
        
        Args:
            expr: Expression to evaluate
            context: Execution context
        
        Returns:
            Evaluated object or None if evaluation fails
        """
        if not context:
            return None
        
        try:
            # Get namespaces
            local_ns = context.locals if hasattr(context, 'locals') else {}
            global_ns = context.globals if hasattr(context, 'globals') else {}
            
            # Try to evaluate
            return eval(expr, global_ns, local_ns)
        
        except Exception:
            return None
    
    def rank_completions(
        self,
        completions: List[CompletionResult],
        prefix: str,
        history: Optional[List[str]] = None
    ) -> List[CompletionResult]:
        """
        Rank completions by relevance.
        
        Args:
            completions: List of completion results
            prefix: The prefix being completed
            history: Optional command history for frequency analysis
        
        Returns:
            Sorted list of completions
        """
        # Calculate frequency from history
        frequency = {}
        if history:
            for line in history:
                for comp in completions:
                    if comp.text in line:
                        frequency[comp.text] = frequency.get(comp.text, 0) + 1
        
        # Sort with custom scoring
        def score(comp: CompletionResult) -> Tuple[int, int, int, str]:
            # Priority (higher is better)
            priority = comp.priority
            
            # Frequency boost (higher is better)
            freq = frequency.get(comp.text, 0) * 10
            
            # Prefix match quality (exact start match is better)
            match_quality = 0
            if comp.text.startswith(prefix):
                match_quality = 100
                # Boost for exact match length
                if len(comp.text) == len(prefix):
                    match_quality = 150
            
            # Alphabetical (case-insensitive)
            alpha = comp.text.lower()
            
            return (-priority - freq - match_quality, -len(comp.text), 0, alpha)
        
        return sorted(completions, key=score)


# Convenience function for quick completions
def get_completions(
    text: str,
    context: Any = None,
    cursor_pos: Optional[int] = None
) -> List[str]:
    """
    Quick completion function.
    
    Args:
        text: Text to complete
        context: Execution context
        cursor_pos: Cursor position
    
    Returns:
        List of completion strings
    """
    engine = CompletionEngine()
    return engine.get_completions(text, context, cursor_pos)
