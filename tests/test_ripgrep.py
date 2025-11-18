"""Comprehensive tests for ripgrep integration."""

import pytest
import subprocess
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from roo_code.builtin_tools.ripgrep import (
    is_ripgrep_available,
    truncate_line,
    execute_ripgrep,
    parse_ripgrep_json,
    format_results,
    search_with_ripgrep,
    search_with_ripgrep_formatted,
    RipgrepMatch,
    SearchResult,
    FileResult,
    RipgrepResult,
    MAX_LINE_LENGTH,
)


class TestRipgrepAvailability:
    """Tests for ripgrep availability detection."""
    
    def test_is_ripgrep_available_when_installed(self):
        """Test detection when ripgrep is installed."""
        with patch('shutil.which', return_value='/usr/bin/rg'):
            assert is_ripgrep_available() is True
    
    def test_is_ripgrep_available_when_not_installed(self):
        """Test detection when ripgrep is not installed."""
        with patch('shutil.which', return_value=None):
            assert is_ripgrep_available() is False


class TestLineTruncation:
    """Tests for line truncation functionality."""
    
    def test_truncate_short_line(self):
        """Test that short lines are not truncated."""
        line = "Short line"
        result = truncate_line(line)
        assert result == line
    
    def test_truncate_long_line(self):
        """Test that long lines are truncated."""
        line = "x" * (MAX_LINE_LENGTH + 100)
        result = truncate_line(line)
        assert len(result) <= MAX_LINE_LENGTH + 20  # Including truncation marker
        assert result.endswith("[truncated...]")
    
    def test_truncate_exact_max_length(self):
        """Test line at exactly max length."""
        line = "x" * MAX_LINE_LENGTH
        result = truncate_line(line)
        assert result == line
    
    def test_truncate_custom_max_length(self):
        """Test truncation with custom max length."""
        line = "x" * 100
        result = truncate_line(line, max_length=50)
        assert len(result) <= 70  # 50 + truncation marker
        assert result.endswith("[truncated...]")


class TestRipgrepExecution:
    """Tests for ripgrep command execution."""
    
    @pytest.fixture
    def test_dir(self):
        """Fixture providing test directory path."""
        return Path(__file__).parent / "fixtures" / "search_test"
    
    def test_execute_ripgrep_not_available(self, test_dir):
        """Test execution when ripgrep is not available."""
        with patch('shutil.which', return_value=None):
            with pytest.raises(FileNotFoundError, match="ripgrep.*not installed"):
                execute_ripgrep(test_dir, "TODO")
    
    @pytest.mark.skipif(not is_ripgrep_available(), reason="ripgrep not installed")
    def test_execute_ripgrep_basic_search(self, test_dir):
        """Test basic ripgrep execution."""
        output, exec_time = execute_ripgrep(test_dir, "TODO")
        
        assert isinstance(output, str)
        assert exec_time >= 0
        assert len(output) > 0  # Should find TODO comments
    
    @pytest.mark.skipif(not is_ripgrep_available(), reason="ripgrep not installed")
    def test_execute_ripgrep_with_file_pattern(self, test_dir):
        """Test ripgrep with file pattern filter."""
        output, exec_time = execute_ripgrep(test_dir, "TODO", file_pattern="*.py")
        
        assert isinstance(output, str)
        # Should only search Python files
        if output:
            assert ".js" not in output or ".md" not in output
    
    @pytest.mark.skipif(not is_ripgrep_available(), reason="ripgrep not installed")
    def test_execute_ripgrep_no_matches(self, test_dir):
        """Test ripgrep when no matches are found."""
        output, exec_time = execute_ripgrep(test_dir, "NONEXISTENT_PATTERN_XYZ123")
        
        # ripgrep may output summary JSON even with no matches
        assert isinstance(output, str)
        assert exec_time >= 0
    
    def test_execute_ripgrep_timeout(self, test_dir):
        """Test ripgrep timeout handling."""
        with patch('shutil.which', return_value='/usr/bin/rg'):
            with patch('subprocess.run', side_effect=subprocess.TimeoutExpired(['rg'], 1)):
                with pytest.raises(subprocess.TimeoutExpired):
                    execute_ripgrep(test_dir, ".*", timeout=1)


class TestRipgrepJsonParsing:
    """Tests for parsing ripgrep JSON output."""
    
    def test_parse_empty_output(self):
        """Test parsing empty output."""
        results = parse_ripgrep_json("")
        assert results == []
    
    def test_parse_single_match(self):
        """Test parsing a single match."""
        json_output = '''{"type":"begin","data":{"path":{"text":"test.py"}}}
{"type":"match","data":{"line_number":5,"lines":{"text":"def search():\\n"},"absolute_offset":10}}
{"type":"end","data":{}}'''
        
        results = parse_ripgrep_json(json_output)
        
        assert len(results) == 1
        assert results[0].file_path == "test.py"
        assert len(results[0].search_results) == 1
        assert results[0].search_results[0].lines[0].line_number == 5
        assert results[0].search_results[0].lines[0].is_match is True
    
    def test_parse_match_with_context(self):
        """Test parsing matches with context lines."""
        json_output = '''{"type":"begin","data":{"path":{"text":"test.py"}}}
{"type":"context","data":{"line_number":4,"lines":{"text":"# Comment\\n"}}}
{"type":"match","data":{"line_number":5,"lines":{"text":"def search():\\n"},"absolute_offset":10}}
{"type":"context","data":{"line_number":6,"lines":{"text":"    pass\\n"}}}
{"type":"end","data":{}}'''
        
        results = parse_ripgrep_json(json_output)
        
        assert len(results) == 1
        search_result = results[0].search_results[0]
        assert len(search_result.lines) == 3
        
        # Check context before match
        assert search_result.lines[0].is_match is False
        assert search_result.lines[0].line_number == 4
        
        # Check match line
        assert search_result.lines[1].is_match is True
        assert search_result.lines[1].line_number == 5
        
        # Check context after match
        assert search_result.lines[2].is_match is False
        assert search_result.lines[2].line_number == 6
    
    def test_parse_multiple_files(self):
        """Test parsing results from multiple files."""
        json_output = '''{"type":"begin","data":{"path":{"text":"file1.py"}}}
{"type":"match","data":{"line_number":1,"lines":{"text":"match1\\n"},"absolute_offset":0}}
{"type":"end","data":{}}
{"type":"begin","data":{"path":{"text":"file2.py"}}}
{"type":"match","data":{"line_number":10,"lines":{"text":"match2\\n"},"absolute_offset":50}}
{"type":"end","data":{}}'''
        
        results = parse_ripgrep_json(json_output)
        
        assert len(results) == 2
        assert results[0].file_path == "file1.py"
        assert results[1].file_path == "file2.py"
    
    def test_parse_discontiguous_matches(self):
        """Test parsing non-contiguous matches (separated by >1 line)."""
        json_output = '''{"type":"begin","data":{"path":{"text":"test.py"}}}
{"type":"match","data":{"line_number":5,"lines":{"text":"match1\\n"},"absolute_offset":10}}
{"type":"match","data":{"line_number":15,"lines":{"text":"match2\\n"},"absolute_offset":100}}
{"type":"end","data":{}}'''
        
        results = parse_ripgrep_json(json_output)
        
        # Should create separate search results for non-contiguous matches
        assert len(results[0].search_results) == 2
    
    def test_parse_malformed_json(self):
        """Test handling of malformed JSON lines."""
        json_output = '''{"type":"begin","data":{"path":{"text":"test.py"}}}
this is not json
{"type":"match","data":{"line_number":5,"lines":{"text":"match\\n"},"absolute_offset":10}}
{"type":"end","data":{}}'''
        
        # Should skip malformed lines and continue
        results = parse_ripgrep_json(json_output)
        assert len(results) == 1


class TestResultFormatting:
    """Tests for result formatting."""
    
    def test_format_empty_results(self):
        """Test formatting empty results."""
        output = format_results([], Path.cwd(), 0)
        assert output == "No results found"
    
    def test_format_single_result(self):
        """Test formatting a single result."""
        match = RipgrepMatch(
            file_path="test.py",
            line_number=5,
            line_content="def search():",
            is_match=True,
            column=0
        )
        search_result = SearchResult(lines=[match])
        file_result = FileResult(file_path="test.py", search_results=[search_result])
        
        output = format_results([file_result], Path.cwd(), 1)
        
        assert "Found 1 result" in output
        assert "test.py" in output
        assert "def search():" in output
        assert "  5>|" in output or "5>|" in output  # Line number with marker
    
    def test_format_multiple_results(self):
        """Test formatting multiple results."""
        file_results = []
        for i in range(3):
            match = RipgrepMatch(
                file_path=f"file{i}.py",
                line_number=i+1,
                line_content=f"line {i}",
                is_match=True
            )
            search_result = SearchResult(lines=[match])
            file_results.append(
                FileResult(file_path=f"file{i}.py", search_results=[search_result])
            )
        
        output = format_results(file_results, Path.cwd(), 3)
        
        assert "Found 3 results" in output
        for i in range(3):
            assert f"file{i}.py" in output
    
    def test_format_with_context_lines(self):
        """Test formatting results with context lines."""
        lines = [
            RipgrepMatch("test.py", 4, "# comment", False),
            RipgrepMatch("test.py", 5, "def search():", True, 10),
            RipgrepMatch("test.py", 6, "    pass", False),
        ]
        search_result = SearchResult(lines=lines)
        file_result = FileResult(file_path="test.py", search_results=[search_result])
        
        output = format_results([file_result], Path.cwd(), 1)
        
        # Check all lines are present
        assert "# comment" in output
        assert "def search():" in output
        assert "pass" in output
        
        # Check match line has marker
        assert ">|" in output
    
    def test_format_truncated_results(self):
        """Test formatting when results are truncated."""
        # Create dummy results to trigger truncation message
        match = RipgrepMatch("test.py", 1, "line", True)
        search_result = SearchResult(lines=[match])
        file_result = FileResult(file_path="test.py", search_results=[search_result])
        
        output = format_results([file_result], Path.cwd(), 300, truncated=True)
        assert "Showing first 300" in output or "300+" in output


class TestSearchWithRipgrep:
    """Integration tests for search_with_ripgrep function."""
    
    @pytest.fixture
    def test_dir(self):
        """Fixture providing test directory path."""
        return Path(__file__).parent / "fixtures" / "search_test"
    
    @pytest.mark.skipif(not is_ripgrep_available(), reason="ripgrep not installed")
    def test_search_basic(self, test_dir):
        """Test basic search functionality."""
        result = search_with_ripgrep(test_dir, "TODO")
        
        assert isinstance(result, RipgrepResult)
        assert result.total_matches > 0
        assert result.total_files > 0
        assert result.execution_time >= 0
        assert len(result.file_results) > 0
    
    @pytest.mark.skipif(not is_ripgrep_available(), reason="ripgrep not installed")
    def test_search_with_file_pattern(self, test_dir):
        """Test search with file pattern filtering."""
        result = search_with_ripgrep(test_dir, "TODO", file_pattern="*.py")
        
        assert isinstance(result, RipgrepResult)
        # All results should be from .py files
        for file_result in result.file_results:
            assert file_result.file_path.endswith(".py")
    
    @pytest.mark.skipif(not is_ripgrep_available(), reason="ripgrep not installed")
    def test_search_no_matches(self, test_dir):
        """Test search with no matches."""
        result = search_with_ripgrep(test_dir, "NONEXISTENT_XYZ123")
        
        assert result.total_matches == 0
        assert result.total_files == 0
        assert len(result.file_results) == 0
    
    @pytest.mark.skipif(not is_ripgrep_available(), reason="ripgrep not installed")
    def test_search_formatted_output(self, test_dir):
        """Test formatted search output."""
        output = search_with_ripgrep_formatted(test_dir, "TODO")
        
        assert isinstance(output, str)
        assert len(output) > 0
        assert "Found" in output or "result" in output
        # Should have file paths
        assert ".py" in output or ".js" in output or ".md" in output


class TestSearchFilesTool:
    """Integration tests for SearchFilesTool with ripgrep."""
    
    @pytest.fixture
    def test_dir(self):
        """Fixture providing test directory path."""
        return Path(__file__).parent / "fixtures" / "search_test"
    
    @pytest.mark.asyncio
    async def test_search_tool_with_ripgrep(self, test_dir):
        """Test SearchFilesTool uses ripgrep when available."""
        from roo_code.builtin_tools.search import SearchFilesTool
        
        tool = SearchFilesTool(cwd=str(test_dir.parent))
        # Set tool_use_id before execution
        tool.current_use_id = "test-id-1"
        
        result = await tool.execute({
            "path": "search_test",
            "regex": "TODO"
        })
        
        assert not result.is_error
        assert "TODO" in result.content or "result" in result.content
    
    @pytest.mark.asyncio
    async def test_search_tool_with_file_pattern(self, test_dir):
        """Test SearchFilesTool with file pattern."""
        from roo_code.builtin_tools.search import SearchFilesTool
        
        tool = SearchFilesTool(cwd=str(test_dir.parent))
        # Set tool_use_id before execution
        tool.current_use_id = "test-id-2"
        
        result = await tool.execute({
            "path": "search_test",
            "regex": "search",
            "file_pattern": "*.py"
        })
        
        assert not result.is_error
    
    @pytest.mark.asyncio
    async def test_search_tool_fallback_to_regex(self, test_dir):
        """Test SearchFilesTool falls back to Python regex."""
        from roo_code.builtin_tools.search import SearchFilesTool
        
        # Force fallback by making ripgrep unavailable
        with patch('roo_code.builtin_tools.search.is_ripgrep_available', return_value=False):
            tool = SearchFilesTool(cwd=str(test_dir.parent))
            # Set tool_use_id before execution
            tool.current_use_id = "test-id-3"
            
            result = await tool.execute({
                "path": "search_test",
                "regex": "TODO"
            })
            
            assert not result.is_error
            # Should still get results via Python regex
            assert len(result.content) > 0


class TestPerformance:
    """Performance comparison tests."""
    
    @pytest.fixture
    def test_dir(self):
        """Fixture providing test directory path."""
        return Path(__file__).parent / "fixtures" / "search_test"
    
    @pytest.mark.skipif(not is_ripgrep_available(), reason="ripgrep not installed")
    def test_ripgrep_performance(self, test_dir):
        """Test that ripgrep completes search quickly."""
        start = time.time()
        result = search_with_ripgrep(test_dir, "search")
        duration = time.time() - start
        
        # Should complete very quickly on small test directory
        assert duration < 1.0  # Less than 1 second
        assert result.execution_time < 1.0


class TestEdgeCases:
    """Tests for edge cases and error handling."""
    
    @pytest.fixture
    def test_dir(self):
        """Fixture providing test directory path."""
        return Path(__file__).parent / "fixtures" / "search_test"
    
    def test_search_nonexistent_directory(self):
        """Test search in non-existent directory."""
        with pytest.raises(Exception):
            search_with_ripgrep(Path("/nonexistent/directory"), "pattern")
    
    @pytest.mark.skipif(not is_ripgrep_available(), reason="ripgrep not installed")
    def test_search_with_regex_special_chars(self, test_dir):
        """Test search with regex special characters."""
        # Should handle regex metacharacters properly
        result = search_with_ripgrep(test_dir, r"\bsearch\b")
        
        assert isinstance(result, RipgrepResult)
        # Should complete without error
    
    @pytest.mark.skipif(not is_ripgrep_available(), reason="ripgrep not installed")
    def test_search_case_insensitive(self, test_dir):
        """Test case-insensitive search (using regex flags)."""
        # Ripgrep uses Rust regex which supports (?i) for case-insensitive
        result = search_with_ripgrep(test_dir, "(?i)TODO")
        
        assert isinstance(result, RipgrepResult)
        # Should find TODO, todo, Todo, etc.


if __name__ == "__main__":
    pytest.main([__file__, "-v"])