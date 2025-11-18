"""Search and discovery tools for finding files and code definitions."""

import os
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional
from ..tools import Tool, ToolInputSchema, ToolResult
from .tree_sitter_parser import TreeSitterParser, get_supported_extensions
from .ripgrep import (
    is_ripgrep_available,
    search_with_ripgrep_formatted,
)


class SearchFilesTool(Tool):
    """Tool for performing regex search across files."""
    
    def __init__(self, cwd: str = "."):
        self.cwd = cwd
        super().__init__(
            name="search_files",
            description=(
                "Request to perform a regex search across files in a specified directory, "
                "providing context-rich results. This tool searches for patterns or specific "
                "content across multiple files, displaying each match with encapsulating context."
            ),
            input_schema=ToolInputSchema(
                type="object",
                properties={
                    "path": {
                        "type": "string",
                        "description": "The path of the directory to search in (relative to workspace directory)"
                    },
                    "regex": {
                        "type": "string",
                        "description": "The regular expression pattern to search for"
                    },
                    "file_pattern": {
                        "type": "string",
                        "description": "Glob pattern to filter files (e.g., '*.py' for Python files). Optional."
                    }
                },
                required=["path", "regex"]
            )
        )
    
    async def execute(self, input_data: Dict[str, Any]) -> ToolResult:
        """Perform regex search across files."""
        try:
            search_path = input_data["path"]
            regex_pattern = input_data["regex"]
            file_pattern = input_data.get("file_pattern")
            
            # Resolve absolute path
            abs_path = Path(self.cwd) / search_path
            
            if not abs_path.exists():
                return ToolResult(
                    tool_use_id=self.current_use_id,
                    content=f"Error: Directory not found: {search_path}",
                    is_error=True
                )
            
            if not abs_path.is_dir():
                return ToolResult(
                    tool_use_id=self.current_use_id,
                    content=f"Error: Path is not a directory: {search_path}",
                    is_error=True
                )
            
            # Try to use ripgrep first if available
            if is_ripgrep_available():
                try:
                    content = search_with_ripgrep_formatted(
                        directory=abs_path,
                        regex=regex_pattern,
                        file_pattern=file_pattern,
                        cwd=Path(self.cwd)
                    )
                    return ToolResult(
                        tool_use_id=self.current_use_id,
                        content=content,
                        is_error=False
                    )
                except Exception as e:
                    # Fall back to Python regex if ripgrep fails
                    pass
            
            # Fallback to Python regex-based search
            return self._search_with_python_regex(abs_path, regex_pattern, file_pattern or "*")
            
        except Exception as e:
            return ToolResult(
                tool_use_id=self.current_use_id,
                content=f"Error searching files: {str(e)}",
                is_error=True
            )
    
    def _search_with_python_regex(
        self,
        abs_path: Path,
        regex_pattern: str,
        file_pattern: str
    ) -> ToolResult:
        """Fallback search implementation using Python's re module."""
        try:
            # Compile regex pattern
            try:
                pattern = re.compile(regex_pattern, re.MULTILINE)
            except re.error as e:
                return ToolResult(
                    tool_use_id=self.current_use_id,
                    content=f"Error: Invalid regex pattern: {str(e)}",
                    is_error=True
                )
            
            # Search files
            results = []
            matched_files = 0
            total_matches = 0
            
            # Use rglob to recursively find matching files
            for file_path in abs_path.rglob(file_pattern):
                if not file_path.is_file():
                    continue
                
                # Skip binary files and common ignore patterns
                if self._should_skip_file(file_path):
                    continue
                
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Find all matches
                    matches = list(pattern.finditer(content))
                    if matches:
                        matched_files += 1
                        total_matches += len(matches)
                        
                        # Get relative path for display
                        rel_path = file_path.relative_to(abs_path)
                        results.append(f"\n# {rel_path}")
                        
                        # Show each match with context (1 line before/after)
                        lines = content.split('\n')
                        for match in matches[:10]:  # Limit to 10 matches per file
                            line_num = content[:match.start()].count('\n') + 1
                            
                            # Get context lines (1 before, match, 1 after)
                            start_line = max(0, line_num - 2)
                            end_line = min(len(lines), line_num + 1)
                            
                            for i in range(start_line, end_line):
                                # Format similar to ripgrep output
                                line_num_str = str(i + 1).rjust(3)
                                marker = '>' if i == line_num - 1 else ' '
                                results.append(f"{line_num_str}{marker}| {lines[i]}")
                            
                            results.append("----")
                        
                        if len(matches) > 10:
                            results.append(f"... and {len(matches) - 10} more matches in this file\n")
                
                except (UnicodeDecodeError, PermissionError):
                    # Skip files that can't be read
                    continue
            
            if not results:
                content = f"No matches found for pattern '{regex_pattern}' in {search_path}"
            else:
                summary = f"Found {total_matches} matches in {matched_files} file(s)\n"
                content = summary + "\n".join(results)
            
            return ToolResult(
                tool_use_id=self.current_use_id,
                content=content,
                is_error=False
            )
            
        except Exception as e:
            return ToolResult(
                tool_use_id=self.current_use_id,
                content=f"Error searching files: {str(e)}",
                is_error=True
            )
    
    def _should_skip_file(self, file_path: Path) -> bool:
        """Check if file should be skipped."""
        skip_patterns = [
            '.git', '__pycache__', 'node_modules', '.venv', 'venv',
            '.pyc', '.pyo', '.so', '.dylib', '.dll', '.exe',
            '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.ico',
            '.pdf', '.zip', '.tar', '.gz', '.bz2'
        ]
        
        path_str = str(file_path)
        for pattern in skip_patterns:
            if pattern in path_str:
                return True
        
        return False


class ListFilesTool(Tool):
    """Tool for listing files and directories."""
    
    def __init__(self, cwd: str = "."):
        self.cwd = cwd
        super().__init__(
            name="list_files",
            description=(
                "Request to list files and directories within the specified directory. "
                "If recursive is true, it will list all files and directories recursively. "
                "If recursive is false or not provided, it will only list the top-level contents."
            ),
            input_schema=ToolInputSchema(
                type="object",
                properties={
                    "path": {
                        "type": "string",
                        "description": "The path of the directory to list contents for (relative to workspace directory)"
                    },
                    "recursive": {
                        "type": "boolean",
                        "description": "Whether to list files recursively. Optional, defaults to false."
                    }
                },
                required=["path"]
            )
        )
    
    async def execute(self, input_data: Dict[str, Any]) -> ToolResult:
        """List files and directories."""
        try:
            dir_path = input_data["path"]
            recursive = input_data.get("recursive", False)
            
            # Resolve absolute path
            abs_path = Path(self.cwd) / dir_path
            
            if not abs_path.exists():
                return ToolResult(
                    tool_use_id=self.current_use_id,
                    content=f"Error: Directory not found: {dir_path}",
                    is_error=True
                )
            
            if not abs_path.is_dir():
                return ToolResult(
                    tool_use_id=self.current_use_id,
                    content=f"Error: Path is not a directory: {dir_path}",
                    is_error=True
                )
            
            # List files
            results = []
            
            if recursive:
                # Recursive listing
                for root, dirs, files in os.walk(abs_path):
                    # Skip common ignore directories
                    dirs[:] = [d for d in dirs if not self._should_skip_dir(d)]
                    
                    rel_root = Path(root).relative_to(abs_path)
                    
                    # Add directories
                    for dir_name in sorted(dirs):
                        rel_path = rel_root / dir_name
                        results.append(f"{rel_path}/")
                    
                    # Add files
                    for file_name in sorted(files):
                        rel_path = rel_root / file_name
                        results.append(str(rel_path))
            else:
                # Top-level listing only
                entries = sorted(abs_path.iterdir(), key=lambda p: (not p.is_dir(), p.name))
                
                for entry in entries:
                    if entry.is_dir():
                        results.append(f"{entry.name}/")
                    else:
                        results.append(entry.name)
            
            if not results:
                content = f"Directory is empty: {dir_path}"
            else:
                content = f"Contents of {dir_path}:\n" + "\n".join(results)
            
            return ToolResult(
                tool_use_id=self.current_use_id,
                content=content,
                is_error=False
            )
            
        except Exception as e:
            return ToolResult(
                tool_use_id=self.current_use_id,
                content=f"Error listing files: {str(e)}",
                is_error=True
            )
    
    def _should_skip_dir(self, dir_name: str) -> bool:
        """Check if directory should be skipped."""
        skip_dirs = {'.git', '__pycache__', 'node_modules', '.venv', 'venv', '.pytest_cache'}
        return dir_name in skip_dirs


class ListCodeDefinitionNamesTool(Tool):
    """Tool for extracting code definitions using tree-sitter or AST parsing."""
    
    def __init__(self, cwd: str = "."):
        self.cwd = cwd
        self.parser = TreeSitterParser()
        super().__init__(
            name="list_code_definition_names",
            description=(
                "Request to list definition names (classes, functions, methods, etc.) from "
                "source code. This tool can analyze either a single file or all files at the "
                "top level of a specified directory."
            ),
            input_schema=ToolInputSchema(
                type="object",
                properties={
                    "path": {
                        "type": "string",
                        "description": (
                            "The path of the file or directory (relative to workspace directory) "
                            "to analyze. When given a directory, it lists definitions from all "
                            "top-level source files."
                        )
                    }
                },
                required=["path"]
            )
        )
    
    async def execute(self, input_data: Dict[str, Any]) -> ToolResult:
        """Extract code definitions from files."""
        try:
            target_path = input_data["path"]
            
            # Resolve absolute path
            abs_path = Path(self.cwd) / target_path
            
            if not abs_path.exists():
                return ToolResult(
                    tool_use_id=self.current_use_id,
                    content=f"Error: Path not found: {target_path}",
                    is_error=True
                )
            
            results = []
            
            if abs_path.is_file():
                # Analyze single file
                definitions = self._extract_definitions(abs_path)
                if definitions:
                    results.append(f"# {abs_path.name}")
                    results.append(definitions)
            elif abs_path.is_dir():
                # Analyze all top-level files using tree-sitter if available
                if self.parser.is_available():
                    content = self.parser.parse_directory(abs_path)
                    return ToolResult(
                        tool_use_id=self.current_use_id,
                        content=content,
                        is_error=False
                    )
                else:
                    # Fallback to regex-based parsing
                    for file_path in sorted(abs_path.iterdir()):
                        if file_path.is_file() and self._is_source_file(file_path):
                            definitions = self._extract_definitions(file_path)
                            if definitions:
                                rel_path = file_path.relative_to(abs_path)
                                results.append(f"\n# {rel_path}")
                                results.append(definitions)
            else:
                return ToolResult(
                    tool_use_id=self.current_use_id,
                    content=f"Error: Path is neither a file nor directory: {target_path}",
                    is_error=True
                )
            
            if not results:
                content = f"No code definitions found in {target_path}"
            else:
                content = "\n".join(results)
            
            return ToolResult(
                tool_use_id=self.current_use_id,
                content=content,
                is_error=False
            )
            
        except Exception as e:
            return ToolResult(
                tool_use_id=self.current_use_id,
                content=f"Error extracting definitions: {str(e)}",
                is_error=True
            )
    
    def _is_source_file(self, file_path: Path) -> bool:
        """Check if file is a source code file."""
        source_extensions = {
            '.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.cpp', '.c', '.h',
            '.hpp', '.cs', '.go', '.rs', '.rb', '.php', '.swift', '.kt'
        }
        return file_path.suffix in source_extensions
    
    def _extract_definitions(self, file_path: Path) -> Optional[str]:
        """Extract definitions from a source file using tree-sitter or regex fallback."""
        # Try tree-sitter first
        if self.parser.is_available():
            definitions = self.parser.parse_file(file_path)
            if definitions:
                return definitions
        
        # Fallback to regex-based parsing
        return self._extract_definitions_regex(file_path)
    
    def _extract_definitions_regex(self, file_path: Path) -> Optional[str]:
        """Extract definitions from a source file using simple pattern matching."""
        definitions = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Python-style definitions
            if file_path.suffix == '.py':
                # Classes
                for match in re.finditer(r'^class\s+(\w+)', content, re.MULTILINE):
                    definitions.append(f"  class {match.group(1)}")
                
                # Functions
                for match in re.finditer(r'^def\s+(\w+)', content, re.MULTILINE):
                    definitions.append(f"  def {match.group(1)}()")
                
                # Async functions
                for match in re.finditer(r'^async\s+def\s+(\w+)', content, re.MULTILINE):
                    definitions.append(f"  async def {match.group(1)}()")
            
            # JavaScript/TypeScript definitions
            elif file_path.suffix in {'.js', '.ts', '.jsx', '.tsx'}:
                # Classes
                for match in re.finditer(r'^\s*(?:export\s+)?class\s+(\w+)', content, re.MULTILINE):
                    definitions.append(f"  class {match.group(1)}")
                
                # Functions
                for match in re.finditer(r'^\s*(?:export\s+)?(?:async\s+)?function\s+(\w+)', content, re.MULTILINE):
                    definitions.append(f"  function {match.group(1)}()")
                
                # Arrow functions
                for match in re.finditer(r'^\s*(?:export\s+)?const\s+(\w+)\s*=\s*(?:async\s*)?\(', content, re.MULTILINE):
                    definitions.append(f"  const {match.group(1)} = ()")
                
                # Interfaces (TypeScript)
                if file_path.suffix in {'.ts', '.tsx'}:
                    for match in re.finditer(r'^\s*(?:export\s+)?interface\s+(\w+)', content, re.MULTILINE):
                        definitions.append(f"  interface {match.group(1)}")
            
            # Java/C#/C++ style
            elif file_path.suffix in {'.java', '.cs', '.cpp', '.c', '.h', '.hpp'}:
                # Classes
                for match in re.finditer(r'^\s*(?:public\s+|private\s+)?class\s+(\w+)', content, re.MULTILINE):
                    definitions.append(f"  class {match.group(1)}")
                
                # Functions/Methods
                for match in re.finditer(r'^\s*(?:public\s+|private\s+|protected\s+)?(?:static\s+)?(?:\w+\s+)+(\w+)\s*\(', content, re.MULTILINE):
                    definitions.append(f"  {match.group(1)}()")
            
        except (UnicodeDecodeError, PermissionError):
            pass
        
        return '\n'.join(definitions) if definitions else None