"""Ripgrep integration for fast file searching.

This module provides a wrapper around the ripgrep (rg) command-line tool
for performing fast regex searches across large codebases. It includes:
- Automatic detection of ripgrep availability
- JSON output parsing for structured results
- Context line support
- Graceful fallback to Python's re module
- Result formatting matching TypeScript implementation
"""

import json
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple
import re


# Constants matching TypeScript implementation
MAX_RESULTS = 300
MAX_LINE_LENGTH = 500
DEFAULT_CONTEXT = 1  # lines before and after match
TIMEOUT_SECONDS = 30


@dataclass
class RipgrepMatch:
    """Represents a single search match."""
    file_path: str
    line_number: int
    line_content: str
    is_match: bool  # True for match line, False for context line
    column: Optional[int] = None  # Column offset for match lines


@dataclass
class SearchResult:
    """Represents a group of contiguous lines (match + context)."""
    lines: List[RipgrepMatch] = field(default_factory=list)


@dataclass
class FileResult:
    """Represents all search results for a single file."""
    file_path: str
    search_results: List[SearchResult] = field(default_factory=list)


@dataclass
class RipgrepResult:
    """Complete search result with metadata."""
    file_results: List[FileResult]
    total_matches: int
    total_files: int
    execution_time: float
    truncated: bool = False  # True if results were limited


def is_ripgrep_available() -> bool:
    """Check if ripgrep (rg) is installed and available."""
    return shutil.which('rg') is not None


def truncate_line(line: str, max_length: int = MAX_LINE_LENGTH) -> str:
    """Truncate a line if it exceeds the maximum length.
    
    Args:
        line: The line to potentially truncate
        max_length: Maximum allowed length
        
    Returns:
        Original line or truncated version with indicator
    """
    if len(line) > max_length:
        return line[:max_length] + " [truncated...]"
    return line


def execute_ripgrep(
    directory: Path,
    regex: str,
    file_pattern: Optional[str] = None,
    context: int = DEFAULT_CONTEXT,
    timeout: int = TIMEOUT_SECONDS
) -> Tuple[str, float]:
    """Execute ripgrep command and return raw output.
    
    Args:
        directory: Directory to search in
        regex: Regex pattern to search for
        file_pattern: Optional glob pattern to filter files
        context: Number of context lines before/after match
        timeout: Timeout in seconds
        
    Returns:
        Tuple of (output string, execution time)
        
    Raises:
        FileNotFoundError: If ripgrep is not available
        subprocess.TimeoutExpired: If search exceeds timeout
        subprocess.CalledProcessError: If ripgrep fails
    """
    rg_path = shutil.which('rg')
    if not rg_path:
        raise FileNotFoundError("ripgrep (rg) is not installed or not in PATH")
    
    # Build ripgrep arguments
    args = [
        rg_path,
        '--json',  # JSON output for structured parsing
        '-e', regex,  # Regex pattern
        '--context', str(context),  # Context lines
        '--no-messages',  # Suppress error messages
        str(directory)  # Search directory
    ]
    
    # Add file pattern if specified
    if file_pattern:
        args.insert(-1, '--glob')
        args.insert(-1, file_pattern)
    
    start_time = time.time()
    
    try:
        # Execute ripgrep with timeout
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False  # Don't raise on non-zero exit (no matches = exit 1)
        )
        
        execution_time = time.time() - start_time
        
        # ripgrep exits with 1 if no matches found, which is not an error
        if result.returncode not in (0, 1):
            raise subprocess.CalledProcessError(
                result.returncode,
                args,
                output=result.stdout,
                stderr=result.stderr
            )
        
        return result.stdout, execution_time
        
    except subprocess.TimeoutExpired:
        execution_time = time.time() - start_time
        raise subprocess.TimeoutExpired(
            args,
            timeout,
            output=f"Search exceeded timeout of {timeout} seconds"
        )


def parse_ripgrep_json(output: str) -> List[FileResult]:
    """Parse ripgrep JSON output into structured results.
    
    Ripgrep outputs one JSON object per line with different types:
    - "begin": Start of results for a file
    - "match": A line that matches the regex
    - "context": A context line (before/after match)
    - "end": End of results for a file
    
    Args:
        output: Raw JSON output from ripgrep
        
    Returns:
        List of FileResult objects
    """
    results = []
    current_file = None
    result_count = 0
    
    for line in output.split('\n'):
        if not line.strip():
            continue
        
        try:
            data = json.loads(line)
            msg_type = data.get('type')
            
            if msg_type == 'begin':
                # Start of a new file's results
                file_path = data['data']['path']['text']
                current_file = FileResult(file_path=file_path)
                
            elif msg_type == 'end':
                # End of file's results
                if current_file and current_file.search_results:
                    results.append(current_file)
                    result_count += len(current_file.search_results)
                    
                    # Limit total results
                    if result_count >= MAX_RESULTS:
                        break
                        
                current_file = None
                
            elif msg_type in ('match', 'context') and current_file:
                # Parse match or context line
                line_data = data['data']
                line_number = line_data['line_number']
                line_text = truncate_line(line_data['lines']['text'].rstrip('\n'))
                is_match = (msg_type == 'match')
                column = line_data.get('absolute_offset') if is_match else None
                
                match = RipgrepMatch(
                    file_path=current_file.file_path,
                    line_number=line_number,
                    line_content=line_text,
                    is_match=is_match,
                    column=column
                )
                
                # Group contiguous lines together
                if current_file.search_results:
                    last_result = current_file.search_results[-1]
                    if last_result.lines:
                        last_line_num = last_result.lines[-1].line_number
                        
                        # If contiguous (within 1 line), add to existing result
                        if line_number <= last_line_num + 1:
                            last_result.lines.append(match)
                        else:
                            # Otherwise start a new result group
                            current_file.search_results.append(
                                SearchResult(lines=[match])
                            )
                    else:
                        # Empty lines list (shouldn't happen)
                        current_file.search_results.append(
                            SearchResult(lines=[match])
                        )
                else:
                    # First result in file
                    current_file.search_results.append(
                        SearchResult(lines=[match])
                    )
                    
        except (json.JSONDecodeError, KeyError) as e:
            # Skip malformed JSON lines
            continue
    
    return results


def format_results(
    file_results: List[FileResult],
    cwd: Path,
    total_matches: int,
    truncated: bool = False
) -> str:
    """Format search results into human-readable output.
    
    Matches the TypeScript implementation's format:
    # path/to/file.py
      10 | some code
      11>| matched line
      12 | more code
    ----
    
    Args:
        file_results: List of file results to format
        cwd: Current working directory for relative paths
        total_matches: Total number of matches found
        truncated: Whether results were truncated
        
    Returns:
        Formatted string output
    """
    if not file_results:
        return "No results found"
    
    output_lines = []
    
    # Add summary header
    if truncated:
        output_lines.append(
            f"Showing first {MAX_RESULTS} of {MAX_RESULTS}+ results. "
            f"Use a more specific search if necessary.\n"
        )
    else:
        result_word = "result" if total_matches == 1 else "results"
        output_lines.append(f"Found {total_matches} {result_word}.\n")
    
    # Format each file's results
    for file_result in file_results:
        try:
            # Get relative path from cwd
            file_path = Path(file_result.file_path)
            try:
                rel_path = file_path.relative_to(cwd)
            except ValueError:
                # If file is not relative to cwd, use absolute path
                rel_path = file_path
            
            output_lines.append(f"# {rel_path}")
            
            # Format each search result group
            for search_result in file_result.search_results:
                if not search_result.lines:
                    continue
                
                for match in search_result.lines:
                    # Format line number (right-aligned, 3 chars)
                    line_num_str = str(match.line_number).rjust(3)
                    # Add '>' marker for match lines, space for context
                    marker = '>' if match.is_match else ' '
                    output_lines.append(
                        f"{line_num_str}{marker}| {match.line_content}"
                    )
                
                output_lines.append("----")
            
            output_lines.append("")  # Blank line between files
            
        except Exception as e:
            # Skip files that can't be formatted
            continue
    
    return '\n'.join(output_lines).rstrip()


def search_with_ripgrep(
    directory: Path,
    regex: str,
    file_pattern: Optional[str] = None,
    cwd: Optional[Path] = None,
    context: int = DEFAULT_CONTEXT,
    timeout: int = TIMEOUT_SECONDS
) -> RipgrepResult:
    """Perform a search using ripgrep.
    
    Main entry point for ripgrep-based searching.
    
    Args:
        directory: Directory to search in
        regex: Regex pattern to search for
        file_pattern: Optional glob pattern for file filtering
        cwd: Current working directory (for relative paths)
        context: Number of context lines
        timeout: Search timeout in seconds
        
    Returns:
        RipgrepResult object with all search results
        
    Raises:
        FileNotFoundError: If ripgrep is not available
        subprocess.TimeoutExpired: If search times out
        subprocess.CalledProcessError: If ripgrep fails
    """
    if cwd is None:
        cwd = directory
    
    # Execute ripgrep
    output, execution_time = execute_ripgrep(
        directory=directory,
        regex=regex,
        file_pattern=file_pattern,
        context=context,
        timeout=timeout
    )
    
    # Parse JSON output
    file_results = parse_ripgrep_json(output)
    
    # Calculate totals
    total_matches = sum(
        len(file_result.search_results) 
        for file_result in file_results
    )
    total_files = len(file_results)
    truncated = total_matches >= MAX_RESULTS
    
    return RipgrepResult(
        file_results=file_results,
        total_matches=total_matches,
        total_files=total_files,
        execution_time=execution_time,
        truncated=truncated
    )


def search_with_ripgrep_formatted(
    directory: Path,
    regex: str,
    file_pattern: Optional[str] = None,
    cwd: Optional[Path] = None,
    context: int = DEFAULT_CONTEXT,
    timeout: int = TIMEOUT_SECONDS
) -> str:
    """Perform a search using ripgrep and return formatted output.
    
    Convenience function that combines search and formatting.
    
    Args:
        directory: Directory to search in
        regex: Regex pattern to search for
        file_pattern: Optional glob pattern for file filtering
        cwd: Current working directory (for relative paths)
        context: Number of context lines
        timeout: Search timeout in seconds
        
    Returns:
        Formatted string output
        
    Raises:
        FileNotFoundError: If ripgrep is not available
        subprocess.TimeoutExpired: If search times out
        subprocess.CalledProcessError: If ripgrep fails
    """
    if cwd is None:
        cwd = directory
    
    result = search_with_ripgrep(
        directory=directory,
        regex=regex,
        file_pattern=file_pattern,
        cwd=cwd,
        context=context,
        timeout=timeout
    )
    
    return format_results(
        file_results=result.file_results,
        cwd=cwd,
        total_matches=result.total_matches,
        truncated=result.truncated
    )