"""File operation tools for reading, writing, and modifying files."""

import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING
from ..tools import Tool, ToolInputSchema, ToolResult
from .cache import TTLCache

if TYPE_CHECKING:
    from .context import ToolContext


class ReadFileTool(Tool):
    """Tool for reading file contents with optional line ranges."""
    
    # Class-level cache shared across instances
    _file_cache: TTLCache[str] = TTLCache(ttl_seconds=5.0, max_size=100)
    
    def __init__(self, cwd: str = ".", context: Optional["ToolContext"] = None, enable_cache: bool = True):
        self.cwd = cwd
        self.enable_cache = enable_cache
        super().__init__(
            name="read_file",
            description=(
                "Request to read the contents of a file. The tool outputs line-numbered "
                "content (e.g. '1 | const x = 1') for easy reference when creating diffs "
                "or discussing code. Use line ranges to efficiently read specific portions "
                "of large files."
            ),
            input_schema=ToolInputSchema(
                type="object",
                properties={
                    "path": {
                        "type": "string",
                        "description": "Path to the file to read (relative to workspace directory)"
                    },
                    "start_line": {
                        "type": "integer",
                        "description": "Starting line number (1-based, inclusive). Optional."
                    },
                    "end_line": {
                        "type": "integer",
                        "description": "Ending line number (1-based, inclusive). Optional."
                    }
                },
                required=["path"]
            ),
            context=context
        )
    
    def _get_file_cache_key(self, file_path: str, abs_path: Path) -> str:
        """Generate cache key including file modification time."""
        try:
            mtime = abs_path.stat().st_mtime
            return f"{file_path}:{mtime}"
        except OSError:
            return file_path
    
    async def execute(self, input_data: Dict[str, Any]) -> ToolResult:
        """Read file contents with optional line range."""
        try:
            file_path = input_data["path"]
            start_line = input_data.get("start_line")
            end_line = input_data.get("end_line")
            
            # Resolve absolute path
            abs_path = Path(self.cwd) / file_path
            
            if not abs_path.exists():
                return ToolResult(
                    tool_use_id=self.current_use_id,
                    content=f"Error: File not found: {file_path}",
                    is_error=True
                )
            
            if not abs_path.is_file():
                return ToolResult(
                    tool_use_id=self.current_use_id,
                    content=f"Error: Path is not a file: {file_path}",
                    is_error=True
                )
            
            # Try to get from cache
            cache_key = self._get_file_cache_key(file_path, abs_path)
            cached_lines = None
            if self.enable_cache:
                cached_lines = self._file_cache.get(cache_key)
            
            if cached_lines is not None:
                lines = cached_lines
            else:
                # Read file content
                try:
                    with open(abs_path, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                except UnicodeDecodeError:
                    # Try with latin-1 encoding as fallback
                    with open(abs_path, 'r', encoding='latin-1') as f:
                        lines = f.readlines()
                
                # Cache the file content
                if self.enable_cache:
                    self._file_cache.set(cache_key, lines)
            
            # Apply line range if specified
            if start_line is not None or end_line is not None:
                start_idx = (start_line - 1) if start_line else 0
                end_idx = end_line if end_line else len(lines)
                lines = lines[start_idx:end_idx]
                line_offset = start_idx
            else:
                line_offset = 0
            
            # Add line numbers
            numbered_lines = [
                f"{i + line_offset + 1} | {line.rstrip()}"
                for i, line in enumerate(lines)
            ]
            
            content = "\n".join(numbered_lines)
            
            return ToolResult(
                tool_use_id=self.current_use_id,
                content=content,
                is_error=False
            )
            
        except Exception as e:
            return ToolResult(
                tool_use_id=self.current_use_id,
                content=f"Error reading file: {str(e)}",
                is_error=True
            )


class WriteToFileTool(Tool):
    """Tool for writing complete file contents."""
    
    def __init__(self, cwd: str = ".", context: Optional["ToolContext"] = None):
        self.cwd = cwd
        super().__init__(
            name="write_to_file",
            description=(
                "Request to write content to a file. This tool is primarily used for "
                "creating new files or for scenarios where a complete rewrite of an "
                "existing file is intentionally required. If the file exists, it will "
                "be overwritten. This tool will automatically create any directories "
                "needed to write the file."
            ),
            input_schema=ToolInputSchema(
                type="object",
                properties={
                    "path": {
                        "type": "string",
                        "description": "Path to the file to write (relative to workspace directory)"
                    },
                    "content": {
                        "type": "string",
                        "description": "Complete content to write to the file"
                    }
                },
                required=["path", "content"]
            ),
            context=context
        )
    
    async def execute(self, input_data: Dict[str, Any]) -> ToolResult:
        """Write complete content to a file."""
        try:
            file_path = input_data["path"]
            content = input_data["content"]
            
            # Check file restrictions
            try:
                self._check_file_edit_allowed(file_path)
            except Exception as e:
                return ToolResult(
                    tool_use_id=self.current_use_id,
                    content=str(e),
                    is_error=True
                )
            
            # Resolve absolute path
            abs_path = Path(self.cwd) / file_path
            
            # Check if file exists to determine if it's a create or overwrite
            file_exists = abs_path.exists()
            action = "overwrite" if file_exists else "create"
            
            # Request approval if context is available
            line_count = content.count('\n') + (1 if content and not content.endswith('\n') else 0)
            approval_details = {
                "action": action,
                "file_path": file_path,
                "line_count": line_count,
                "file_exists": file_exists
            }
            
            approved = await self._request_approval(
                f"{action.capitalize()} file: {file_path}",
                approval_details
            )
            
            if not approved:
                return ToolResult(
                    tool_use_id=self.current_use_id,
                    content=f"Operation cancelled: User denied {action} of {file_path}",
                    is_error=True
                )
            
            # Create parent directories if they don't exist
            abs_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write content
            with open(abs_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # Track file change
            change_type = "created" if not file_exists else "modified"
            await self._track_file_change(file_path, change_type, {"line_count": line_count})
            
            # Stream result
            await self._stream_result(f"Successfully wrote {line_count} lines to {file_path}")
            
            return ToolResult(
                tool_use_id=self.current_use_id,
                content=f"Successfully wrote {line_count} lines to {file_path}",
                is_error=False
            )
            
        except Exception as e:
            return ToolResult(
                tool_use_id=self.current_use_id,
                content=f"Error writing file: {str(e)}",
                is_error=True
            )


class ApplyDiffTool(Tool):
    """Tool for applying precise, targeted modifications to existing files."""
    
    def __init__(self, cwd: str = "."):
        self.cwd = cwd
        super().__init__(
            name="apply_diff",
            description=(
                "Request to apply PRECISE, TARGETED modifications to an existing file by "
                "searching for specific sections of content and replacing them. This tool "
                "is for SURGICAL EDITS ONLY. The SEARCH section must exactly match existing "
                "content including whitespace and indentation. Use read_file first if you're "
                "not confident in the exact content."
            ),
            input_schema=ToolInputSchema(
                type="object",
                properties={
                    "path": {
                        "type": "string",
                        "description": "Path to the file to modify (relative to workspace directory)"
                    },
                    "diff": {
                        "type": "string",
                        "description": (
                            "The search/replace block in format:\n"
                            "<<<<<<< SEARCH\n"
                            ":start_line: <line_number>\n"
                            "-------\n"
                            "[exact content to find]\n"
                            "=======\n"
                            "[new content to replace with]\n"
                            ">>>>>>> REPLACE"
                        )
                    }
                },
                required=["path", "diff"]
            )
        )
    
    def _parse_diff_blocks(self, diff: str) -> List[Tuple[int, str, str]]:
        """Parse diff blocks into (start_line, search, replace) tuples."""
        blocks = []
        
        # Split by SEARCH/REPLACE blocks
        pattern = r'<<<<<<< SEARCH\s*:start_line:\s*(\d+)\s*-------\s*(.*?)\s*=======\s*(.*?)\s*>>>>>>> REPLACE'
        matches = re.finditer(pattern, diff, re.DOTALL)
        
        for match in matches:
            start_line = int(match.group(1))
            search_content = match.group(2)
            replace_content = match.group(3)
            blocks.append((start_line, search_content, replace_content))
        
        return blocks
    
    async def execute(self, input_data: Dict[str, Any]) -> ToolResult:
        """Apply diff to a file."""
        try:
            file_path = input_data["path"]
            diff_content = input_data["diff"]
            
            # Check file restrictions
            try:
                self._check_file_edit_allowed(file_path)
            except Exception as e:
                return ToolResult(
                    tool_use_id=self.current_use_id,
                    content=str(e),
                    is_error=True
                )
            
            # Resolve absolute path
            abs_path = Path(self.cwd) / file_path
            
            if not abs_path.exists():
                return ToolResult(
                    tool_use_id=self.current_use_id,
                    content=f"Error: File not found: {file_path}",
                    is_error=True
                )
            
            # Read current file content
            with open(abs_path, 'r', encoding='utf-8') as f:
                original_content = f.read()
            
            # Parse diff blocks
            diff_blocks = self._parse_diff_blocks(diff_content)
            
            if not diff_blocks:
                return ToolResult(
                    tool_use_id=self.current_use_id,
                    content="Error: No valid SEARCH/REPLACE blocks found in diff",
                    is_error=True
                )
            
            # Request approval for the diff
            approval_details = {
                "file_path": file_path,
                "num_blocks": len(diff_blocks),
                "diff_content": diff_content[:500]  # Show first 500 chars
            }
            
            approved = await self._request_approval(
                f"Apply {len(diff_blocks)} diff block(s) to {file_path}",
                approval_details
            )
            
            if not approved:
                return ToolResult(
                    tool_use_id=self.current_use_id,
                    content=f"Operation cancelled: User denied diff application to {file_path}",
                    is_error=True
                )
            
            # Apply each diff block
            modified_content = original_content
            blocks_applied = 0
            
            for start_line, search, replace in diff_blocks:
                # Try to find and replace the search content
                if search in modified_content:
                    modified_content = modified_content.replace(search, replace, 1)
                    blocks_applied += 1
                else:
                    # Try with normalized whitespace
                    search_normalized = re.sub(r'\s+', ' ', search.strip())
                    content_lines = modified_content.split('\n')
                    
                    # Search around the specified line
                    found = False
                    for i in range(max(0, start_line - 5), min(len(content_lines), start_line + 5)):
                        window = '\n'.join(content_lines[i:i+len(search.split('\n'))])
                        window_normalized = re.sub(r'\s+', ' ', window.strip())
                        
                        if search_normalized in window_normalized:
                            # Found it with fuzzy matching
                            modified_content = modified_content.replace(window, replace, 1)
                            blocks_applied += 1
                            found = True
                            break
                    
                    if not found:
                        return ToolResult(
                            tool_use_id=self.current_use_id,
                            content=(
                                f"Error: Could not find search content near line {start_line}.\n"
                                f"Searched for:\n{search[:200]}...\n\n"
                                "Tip: Use read_file to verify the current content"
                            ),
                            is_error=True
                        )
            
            # Write modified content back
            with open(abs_path, 'w', encoding='utf-8') as f:
                f.write(modified_content)
            
            # Track file change
            await self._track_file_change(
                file_path,
                "modified",
                {"blocks_applied": blocks_applied}
            )
            
            # Stream result
            await self._stream_result(
                f"Successfully applied {blocks_applied} diff block(s) to {file_path}"
            )
            
            return ToolResult(
                tool_use_id=self.current_use_id,
                content=f"Successfully applied {blocks_applied} diff block(s) to {file_path}",
                is_error=False
            )
            
        except Exception as e:
            return ToolResult(
                tool_use_id=self.current_use_id,
                content=f"Error applying diff: {str(e)}",
                is_error=True
            )


class InsertContentTool(Tool):
    """Tool for inserting lines at a specific position in a file."""
    
    def __init__(self, cwd: str = ".", context: Optional["ToolContext"] = None):
        self.cwd = cwd
        super().__init__(
            name="insert_content",
            description=(
                "Use this tool for adding new lines of content into a file without "
                "modifying existing content. Specify the line number to insert before, "
                "or use line 0 to append to the end."
            ),
            input_schema=ToolInputSchema(
                type="object",
                properties={
                    "path": {
                        "type": "string",
                        "description": "Path to the file (relative to workspace directory)"
                    },
                    "line": {
                        "type": "integer",
                        "description": (
                            "Line number where content will be inserted (1-based). "
                            "Use 0 to append at end of file"
                        )
                    },
                    "content": {
                        "type": "string",
                        "description": "The content to insert at the specified line"
                    }
                },
                required=["path", "line", "content"]
            ),
            context=context
        )
    
    async def execute(self, input_data: Dict[str, Any]) -> ToolResult:
        """Insert content at specified line."""
        try:
            file_path = input_data["path"]
            line_num = input_data["line"]
            content = input_data["content"]
            
            # Check file restrictions
            try:
                self._check_file_edit_allowed(file_path)
            except Exception as e:
                return ToolResult(
                    tool_use_id=self.current_use_id,
                    content=str(e),
                    is_error=True
                )
            
            # Resolve absolute path
            abs_path = Path(self.cwd) / file_path
            
            if not abs_path.exists():
                return ToolResult(
                    tool_use_id=self.current_use_id,
                    content=f"Error: File not found: {file_path}",
                    is_error=True
                )
            
            # Read current file content
            with open(abs_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # Ensure content ends with newline if it doesn't already
            if content and not content.endswith('\n'):
                content += '\n'
            
            # Request approval
            insert_line_count = content.count('\n')
            position = "end" if line_num == 0 else f"line {line_num}"
            approval_details = {
                "file_path": file_path,
                "line_num": line_num,
                "insert_line_count": insert_line_count,
                "position": position
            }
            
            approved = await self._request_approval(
                f"Insert {insert_line_count} line(s) at {position} of {file_path}",
                approval_details
            )
            
            if not approved:
                return ToolResult(
                    tool_use_id=self.current_use_id,
                    content=f"Operation cancelled: User denied insertion to {file_path}",
                    is_error=True
                )
            
            # Insert content
            if line_num == 0:
                # Append to end
                lines.append(content)
            else:
                # Insert at specified line (convert to 0-based index)
                insert_idx = line_num - 1
                if insert_idx < 0 or insert_idx > len(lines):
                    return ToolResult(
                        tool_use_id=self.current_use_id,
                        content=f"Error: Line number {line_num} is out of range (file has {len(lines)} lines)",
                        is_error=True
                    )
                lines.insert(insert_idx, content)
            
            # Write modified content back
            with open(abs_path, 'w', encoding='utf-8') as f:
                f.writelines(lines)
            
            # Track file change
            await self._track_file_change(
                file_path,
                "modified",
                {"insert_line_count": insert_line_count, "position": position}
            )
            
            # Stream result
            await self._stream_result(
                f"Successfully inserted {insert_line_count} line(s) at {position} of {file_path}"
            )
            
            return ToolResult(
                tool_use_id=self.current_use_id,
                content=f"Successfully inserted {insert_line_count} line(s) at {position} of {file_path}",
                is_error=False
            )
            
        except Exception as e:
            return ToolResult(
                tool_use_id=self.current_use_id,
                content=f"Error inserting content: {str(e)}",
                is_error=True
            )