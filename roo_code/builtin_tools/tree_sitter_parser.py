"""Tree-sitter based code parser for extracting code definitions.

This module provides tree-sitter integration for parsing source code and extracting
definitions (functions, classes, methods, etc.) across multiple programming languages.
"""

import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass

# Tree-sitter queries for different languages
# These queries are based on the TypeScript implementation

PYTHON_QUERY = """
; Class definitions (including decorated)
(class_definition
  name: (identifier) @name.definition.class) @definition.class

(decorated_definition
  definition: (class_definition
    name: (identifier) @name.definition.class)) @definition.class

; Function and method definitions (including async and decorated)
(function_definition
  name: (identifier) @name.definition.function) @definition.function

(decorated_definition
  definition: (function_definition
    name: (identifier) @name.definition.function)) @definition.function
"""

JAVASCRIPT_QUERY = """
(
  (comment)* @doc
  .
  (method_definition
    name: (property_identifier) @name) @definition.method
  (#not-eq? @name "constructor")
)

(
  (comment)* @doc
  .
  [
    (class
      name: (_) @name)
    (class_declaration
      name: (_) @name)
  ] @definition.class
)

(
  (comment)* @doc
  .
  [
    (function_declaration
      name: (identifier) @name)
    (generator_function_declaration
      name: (identifier) @name)
  ] @definition.function
)

(
  (comment)* @doc
  .
  (lexical_declaration
    (variable_declarator
      name: (identifier) @name
      value: [(arrow_function) (function_expression)]) @definition.function)
)

(
  (comment)* @doc
  .
  (variable_declaration
    (variable_declarator
      name: (identifier) @name
      value: [(arrow_function) (function_expression)]) @definition.function)
)
"""

TYPESCRIPT_QUERY = JAVASCRIPT_QUERY + """
; TypeScript-specific constructs
(
  (comment)* @doc
  .
  (interface_declaration
    name: (type_identifier) @name) @definition.interface
)

(
  (comment)* @doc
  .
  (type_alias_declaration
    name: (type_identifier) @name) @definition.type
)
"""

JAVA_QUERY = """
(class_declaration
  name: (identifier) @name.definition.class) @definition.class

(interface_declaration
  name: (identifier) @name.definition.interface) @definition.interface

(method_declaration
  name: (identifier) @name.definition.method) @definition.method

(constructor_declaration
  name: (identifier) @name.definition.constructor) @definition.constructor
"""

GO_QUERY = """
(function_declaration
  name: (identifier) @name.definition.function) @definition.function

(method_declaration
  name: (field_identifier) @name.definition.method) @definition.method

(type_declaration
  (type_spec
    name: (type_identifier) @name.definition.type)) @definition.type

(type_declaration
  (type_spec
    type: (interface_type) @definition.interface))
"""

RUST_QUERY = """
(function_item
  name: (identifier) @name.definition.function) @definition.function

(struct_item
  name: (type_identifier) @name.definition.struct) @definition.struct

(impl_item
  type: (type_identifier) @name.definition.impl) @definition.impl

(trait_item
  name: (type_identifier) @name.definition.trait) @definition.trait

(enum_item
  name: (type_identifier) @name.definition.enum) @definition.enum
"""

CPP_QUERY = """
(function_definition
  declarator: (function_declarator
    declarator: (identifier) @name.definition.function)) @definition.function

(class_specifier
  name: (type_identifier) @name.definition.class) @definition.class

(struct_specifier
  name: (type_identifier) @name.definition.struct) @definition.struct

(declaration
  declarator: (function_declarator
    declarator: (identifier) @name.definition.function)) @definition.function
"""

C_QUERY = """
(function_definition
  declarator: (function_declarator
    declarator: (identifier) @name.definition.function)) @definition.function

(struct_specifier
  name: (type_identifier) @name.definition.struct) @definition.struct

(declaration
  declarator: (function_declarator
    declarator: (identifier) @name.definition.function)) @definition.function
"""

RUBY_QUERY = """
(class
  name: (constant) @name.definition.class) @definition.class

(module
  name: (constant) @name.definition.module) @definition.module

(method
  name: (identifier) @name.definition.method) @definition.method

(singleton_method
  name: (identifier) @name.definition.method) @definition.method
"""

PHP_QUERY = """
(class_declaration
  name: (name) @name.definition.class) @definition.class

(function_definition
  name: (name) @name.definition.function) @definition.function

(method_declaration
  name: (name) @name.definition.method) @definition.method

(interface_declaration
  name: (name) @name.definition.interface) @definition.interface

(trait_declaration
  name: (name) @name.definition.trait) @definition.trait
"""

# Map file extensions to language names and queries
LANGUAGE_CONFIG = {
    'py': ('python', PYTHON_QUERY),
    'js': ('javascript', JAVASCRIPT_QUERY),
    'jsx': ('javascript', JAVASCRIPT_QUERY),
    'ts': ('typescript', TYPESCRIPT_QUERY),
    'tsx': ('tsx', TYPESCRIPT_QUERY),
    'java': ('java', JAVA_QUERY),
    'go': ('go', GO_QUERY),
    'rs': ('rust', RUST_QUERY),
    'cpp': ('cpp', CPP_QUERY),
    'hpp': ('cpp', CPP_QUERY),
    'c': ('c', C_QUERY),
    'h': ('c', C_QUERY),
    'rb': ('ruby', RUBY_QUERY),
    'php': ('php', PHP_QUERY),
}

# Minimum lines for a component to be included in the output
MIN_COMPONENT_LINES = 4


@dataclass
class CodeDefinition:
    """Represents a code definition found by the parser."""
    name: str
    type: str  # 'class', 'function', 'method', etc.
    start_line: int
    end_line: int
    line_content: str


class TreeSitterParser:
    """Parser for extracting code definitions using tree-sitter."""
    
    def __init__(self):
        """Initialize the parser with lazy loading."""
        self._parsers: Dict[str, any] = {}
        self._languages: Dict[str, any] = {}
        self._tree_sitter_available: Optional[bool] = None  # Lazy check
        self._parse_cache: Dict[str, Tuple[str, float]] = {}  # Cache parsed results
        self._cache_ttl = 5.0  # Cache TTL in seconds
    
    def _check_tree_sitter(self) -> bool:
        """Check if tree-sitter is available (lazy)."""
        if self._tree_sitter_available is None:
            try:
                import tree_sitter
                self._tree_sitter_available = True
            except ImportError:
                self._tree_sitter_available = False
        return self._tree_sitter_available
    
    def is_available(self) -> bool:
        """Check if tree-sitter parsing is available."""
        return self._check_tree_sitter()
    
    def _get_language(self, language_name: str) -> Optional[any]:
        """Load a tree-sitter language."""
        if not self._tree_sitter_available:
            return None
        
        if language_name in self._languages:
            return self._languages[language_name]
        
        try:
            import tree_sitter
            
            # Try to import the language-specific module
            lang_module_name = f'tree_sitter_{language_name}'
            try:
                lang_module = __import__(lang_module_name)
                language = tree_sitter.Language(lang_module.language())
                self._languages[language_name] = language
                return language
            except (ImportError, AttributeError):
                # Language grammar not installed
                return None
        except Exception:
            return None
    
    def _get_parser(self, language_name: str) -> Optional[Tuple[any, any]]:
        """Get or create a parser for the given language."""
        if not self._tree_sitter_available:
            return None
        
        if language_name in self._parsers:
            return self._parsers[language_name]
        
        try:
            import tree_sitter
            
            language = self._get_language(language_name)
            if language is None:
                return None
            
            parser = tree_sitter.Parser()
            parser.set_language(language)
            
            # Get the query for this language
            _, query_string = LANGUAGE_CONFIG.get(language_name, (None, None))
            if query_string is None:
                # Find the language config by matching the language name
                for ext, (lang, query) in LANGUAGE_CONFIG.items():
                    if lang == language_name:
                        query_string = query
                        break
            
            if query_string:
                query = language.query(query_string)
            else:
                query = None
            
            self._parsers[language_name] = (parser, query)
            return (parser, query)
        except Exception:
            return None
    
    def parse_file(self, file_path: Path) -> Optional[str]:
        """
        Parse a single file and extract code definitions with caching.
        
        Args:
            file_path: Path to the source file
            
        Returns:
            Formatted string with code definitions or None if parsing failed
        """
        # Check cache first
        import time
        cache_key = str(file_path)
        try:
            mtime = file_path.stat().st_mtime
            cache_key = f"{file_path}:{mtime}"
        except OSError:
            pass
        
        if cache_key in self._parse_cache:
            cached_result, cached_time = self._parse_cache[cache_key]
            if time.time() - cached_time < self._cache_ttl:
                return cached_result
        
        # Get file extension
        ext = file_path.suffix.lstrip('.')
        
        # Check if language is supported
        if ext not in LANGUAGE_CONFIG:
            return None
        
        language_name, _ = LANGUAGE_CONFIG[ext]
        
        # Get parser and query (lazy loaded)
        parser_info = self._get_parser(language_name)
        if parser_info is None:
            return None
        
        parser, query = parser_info
        if query is None:
            return None
        
        try:
            # Read file content
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Parse the content
            tree = parser.parse(bytes(content, 'utf8'))
            
            # Get captures from the query
            captures = query.captures(tree.root_node)
            
            if not captures:
                result = None
            else:
                # Process captures
                lines = content.split('\n')
                definitions = self._process_captures(captures, lines)
                
                if not definitions:
                    result = None
                else:
                    # Format output
                    result = self._format_definitions(definitions)
            
            # Cache the result
            self._parse_cache[cache_key] = (result, time.time())
            return result
        
        except Exception:
            return None
    
    def _process_captures(self, captures: List[Tuple], lines: List[str]) -> List[CodeDefinition]:
        """
        Process tree-sitter captures into CodeDefinition objects.
        
        Args:
            captures: List of (node, capture_name) tuples
            lines: Lines of the source file
            
        Returns:
            List of CodeDefinition objects
        """
        definitions = []
        processed_lines: Set[str] = set()
        
        # Sort captures by start position
        captures_sorted = sorted(captures, key=lambda c: c[0].start_point[0])
        
        for node, capture_name in captures_sorted:
            # Skip if not a definition capture
            if 'definition' not in capture_name and 'name' not in capture_name:
                continue
            
            # Get the definition node
            if 'name' in capture_name:
                # This is a name capture, use parent as definition node
                def_node = node.parent
            else:
                def_node = node
            
            if def_node is None:
                continue
            
            # Get line numbers
            start_line = def_node.start_point[0]
            end_line = def_node.end_point[0]
            line_count = end_line - start_line + 1
            
            # Skip small components
            if line_count < MIN_COMPONENT_LINES:
                continue
            
            # Create unique key for this line range
            line_key = f"{start_line}-{end_line}"
            
            # Skip if already processed
            if line_key in processed_lines:
                continue
            
            # Extract definition info
            line_content = lines[start_line].strip() if start_line < len(lines) else ""
            
            # Determine definition type
            def_type = 'unknown'
            if 'class' in capture_name:
                def_type = 'class'
            elif 'function' in capture_name or 'method' in capture_name:
                def_type = 'function'
            elif 'interface' in capture_name:
                def_type = 'interface'
            elif 'type' in capture_name:
                def_type = 'type'
            elif 'struct' in capture_name:
                def_type = 'struct'
            elif 'trait' in capture_name:
                def_type = 'trait'
            
            # Extract name if available
            name = node.text.decode('utf8') if 'name' in capture_name else ""
            
            definitions.append(CodeDefinition(
                name=name,
                type=def_type,
                start_line=start_line + 1,  # Convert to 1-based
                end_line=end_line + 1,  # Convert to 1-based
                line_content=line_content
            ))
            
            processed_lines.add(line_key)
        
        return definitions
    
    def _format_definitions(self, definitions: List[CodeDefinition]) -> str:
        """
        Format definitions into the output string.
        
        Args:
            definitions: List of CodeDefinition objects
            
        Returns:
            Formatted string
        """
        if not definitions:
            return ""
        
        output_lines = []
        for definition in definitions:
            output_lines.append(
                f"{definition.start_line}--{definition.end_line} | {definition.line_content}"
            )
        
        return '\n'.join(output_lines)
    
    def parse_directory(self, dir_path: Path, max_files: int = 50) -> str:
        """
        Parse all source files in a directory.
        
        Args:
            dir_path: Path to the directory
            max_files: Maximum number of files to parse
            
        Returns:
            Formatted string with all definitions
        """
        results = []
        file_count = 0
        
        # Get all source files in directory (not recursive)
        for file_path in sorted(dir_path.iterdir()):
            if not file_path.is_file():
                continue
            
            ext = file_path.suffix.lstrip('.')
            if ext not in LANGUAGE_CONFIG:
                continue
            
            if file_count >= max_files:
                break
            
            definitions = self.parse_file(file_path)
            if definitions:
                rel_path = file_path.relative_to(dir_path)
                results.append(f"# {rel_path}")
                results.append(definitions)
                file_count += 1
        
        return '\n'.join(results) if results else "No source code definitions found."


def get_supported_extensions() -> List[str]:
    """Get list of supported file extensions."""
    return [f".{ext}" for ext in LANGUAGE_CONFIG.keys()]