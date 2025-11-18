"""Tests for built-in tools."""

import pytest
import tempfile
import os
from pathlib import Path
from roo_code.builtin_tools import (
    ReadFileTool,
    WriteToFileTool,
    ApplyDiffTool,
    InsertContentTool,
    SearchFilesTool,
    ListFilesTool,
    ExecuteCommandTool,
)
from roo_code.builtin_tools.registry import (
    get_all_builtin_tools,
    get_tools_by_group,
    get_tool_by_name,
    list_available_tools,
)


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def sample_file(temp_dir):
    """Create a sample file for testing."""
    file_path = Path(temp_dir) / "test.py"
    content = """def hello():
    print("Hello, World!")

class TestClass:
    def method(self):
        pass
"""
    file_path.write_text(content)
    return file_path


class TestReadFileTool:
    """Tests for ReadFileTool."""
    
    @pytest.mark.asyncio
    async def test_read_entire_file(self, temp_dir, sample_file):
        """Test reading an entire file."""
        tool = ReadFileTool(cwd=temp_dir)
        tool.current_use_id = "test-1"
        
        result = await tool.execute({"path": "test.py"})
        
        assert not result.is_error
        assert "1 | def hello():" in result.content
        assert "2 |     print(\"Hello, World!\")" in result.content
    
    @pytest.mark.asyncio
    async def test_read_with_line_range(self, temp_dir, sample_file):
        """Test reading a file with line range."""
        tool = ReadFileTool(cwd=temp_dir)
        tool.current_use_id = "test-2"
        
        result = await tool.execute({
            "path": "test.py",
            "start_line": 1,
            "end_line": 2
        })
        
        assert not result.is_error
        assert "1 | def hello():" in result.content
        assert "2 |     print(\"Hello, World!\")" in result.content
        assert "class TestClass" not in result.content
    
    @pytest.mark.asyncio
    async def test_read_nonexistent_file(self, temp_dir):
        """Test reading a non-existent file."""
        tool = ReadFileTool(cwd=temp_dir)
        tool.current_use_id = "test-3"
        
        result = await tool.execute({"path": "nonexistent.py"})
        
        assert result.is_error
        assert "not found" in result.content.lower()


class TestWriteToFileTool:
    """Tests for WriteToFileTool."""
    
    @pytest.mark.asyncio
    async def test_write_new_file(self, temp_dir):
        """Test writing a new file."""
        tool = WriteToFileTool(cwd=temp_dir)
        tool.current_use_id = "test-4"
        
        content = "print('Hello')\n"
        result = await tool.execute({
            "path": "new_file.py",
            "content": content
        })
        
        assert not result.is_error
        assert "Successfully wrote" in result.content
        
        # Verify file was created
        file_path = Path(temp_dir) / "new_file.py"
        assert file_path.exists()
        assert file_path.read_text() == content
    
    @pytest.mark.asyncio
    async def test_write_creates_directories(self, temp_dir):
        """Test that writing creates necessary directories."""
        tool = WriteToFileTool(cwd=temp_dir)
        tool.current_use_id = "test-5"
        
        result = await tool.execute({
            "path": "subdir/nested/file.txt",
            "content": "test content"
        })
        
        assert not result.is_error
        
        # Verify nested file was created
        file_path = Path(temp_dir) / "subdir" / "nested" / "file.txt"
        assert file_path.exists()
        assert file_path.read_text() == "test content"


class TestApplyDiffTool:
    """Tests for ApplyDiffTool."""
    
    @pytest.mark.asyncio
    async def test_apply_simple_diff(self, temp_dir, sample_file):
        """Test applying a simple diff."""
        tool = ApplyDiffTool(cwd=temp_dir)
        tool.current_use_id = "test-6"
        
        diff = """<<<<<<< SEARCH
:start_line:1
-------
def hello():
    print("Hello, World!")
=======
def hello():
    print("Hello, Python!")
>>>>>>> REPLACE
"""
        
        result = await tool.execute({
            "path": "test.py",
            "diff": diff
        })
        
        assert not result.is_error
        assert "Successfully applied" in result.content
        
        # Verify change was made
        content = sample_file.read_text()
        assert "Hello, Python!" in content
        assert "Hello, World!" not in content
    
    @pytest.mark.asyncio
    async def test_apply_diff_nonexistent_file(self, temp_dir):
        """Test applying diff to non-existent file."""
        tool = ApplyDiffTool(cwd=temp_dir)
        tool.current_use_id = "test-7"
        
        diff = """<<<<<<< SEARCH
:start_line:1
-------
test
=======
changed
>>>>>>> REPLACE
"""
        
        result = await tool.execute({
            "path": "nonexistent.py",
            "diff": diff
        })
        
        assert result.is_error
        assert "not found" in result.content.lower()


class TestInsertContentTool:
    """Tests for InsertContentTool."""
    
    @pytest.mark.asyncio
    async def test_insert_at_beginning(self, temp_dir, sample_file):
        """Test inserting content at the beginning of a file."""
        tool = InsertContentTool(cwd=temp_dir)
        tool.current_use_id = "test-8"
        
        result = await tool.execute({
            "path": "test.py",
            "line": 1,
            "content": "# This is a comment\n"
        })
        
        assert not result.is_error
        
        # Verify insertion
        content = sample_file.read_text()
        assert content.startswith("# This is a comment\n")
    
    @pytest.mark.asyncio
    async def test_insert_at_end(self, temp_dir, sample_file):
        """Test inserting content at the end of a file."""
        tool = InsertContentTool(cwd=temp_dir)
        tool.current_use_id = "test-9"
        
        result = await tool.execute({
            "path": "test.py",
            "line": 0,
            "content": "\n# End of file\n"
        })
        
        assert not result.is_error
        
        # Verify insertion
        content = sample_file.read_text()
        assert content.endswith("# End of file\n")


class TestSearchFilesTool:
    """Tests for SearchFilesTool."""
    
    @pytest.mark.asyncio
    async def test_search_files(self, temp_dir, sample_file):
        """Test searching files with regex."""
        tool = SearchFilesTool(cwd=temp_dir)
        tool.current_use_id = "test-10"
        
        result = await tool.execute({
            "path": ".",
            "regex": "def hello"
        })
        
        assert not result.is_error
        assert "test.py" in result.content
        assert "def hello" in result.content
    
    @pytest.mark.asyncio
    async def test_search_with_file_pattern(self, temp_dir, sample_file):
        """Test searching files with file pattern."""
        tool = SearchFilesTool(cwd=temp_dir)
        tool.current_use_id = "test-11"
        
        result = await tool.execute({
            "path": ".",
            "regex": "class",
            "file_pattern": "*.py"
        })
        
        assert not result.is_error
        assert "TestClass" in result.content


class TestListFilesTool:
    """Tests for ListFilesTool."""
    
    @pytest.mark.asyncio
    async def test_list_files_non_recursive(self, temp_dir, sample_file):
        """Test listing files non-recursively."""
        tool = ListFilesTool(cwd=temp_dir)
        tool.current_use_id = "test-12"
        
        result = await tool.execute({
            "path": ".",
            "recursive": False
        })
        
        assert not result.is_error
        assert "test.py" in result.content
    
    @pytest.mark.asyncio
    async def test_list_files_recursive(self, temp_dir):
        """Test listing files recursively."""
        # Create nested structure
        (Path(temp_dir) / "subdir").mkdir()
        (Path(temp_dir) / "subdir" / "file.txt").write_text("test")
        
        tool = ListFilesTool(cwd=temp_dir)
        tool.current_use_id = "test-13"
        
        result = await tool.execute({
            "path": ".",
            "recursive": True
        })
        
        assert not result.is_error
        assert "subdir/" in result.content
        assert "subdir/file.txt" in result.content or "subdir\\file.txt" in result.content


class TestExecuteCommandTool:
    """Tests for ExecuteCommandTool."""
    
    @pytest.mark.asyncio
    async def test_execute_simple_command(self, temp_dir):
        """Test executing a simple command."""
        tool = ExecuteCommandTool(cwd=temp_dir)
        tool.current_use_id = "test-14"
        
        result = await tool.execute({
            "command": "echo 'Hello'"
        })
        
        assert not result.is_error
        assert "Hello" in result.content
    
    @pytest.mark.asyncio
    async def test_execute_command_with_cwd(self, temp_dir):
        """Test executing command with custom working directory."""
        tool = ExecuteCommandTool(cwd=temp_dir)
        tool.current_use_id = "test-15"
        
        result = await tool.execute({
            "command": "pwd",
            "cwd": temp_dir
        })
        
        assert not result.is_error


class TestRegistry:
    """Tests for tool registry functions."""
    
    def test_get_all_builtin_tools(self, temp_dir):
        """Test getting all built-in tools."""
        tools = get_all_builtin_tools(cwd=temp_dir)
        
        assert len(tools) > 0
        tool_names = [tool.name for tool in tools]
        assert "read_file" in tool_names
        assert "write_to_file" in tool_names
        assert "execute_command" in tool_names
    
    def test_get_tools_by_group(self, temp_dir):
        """Test getting tools by group."""
        read_tools = get_tools_by_group("read", cwd=temp_dir)
        
        assert len(read_tools) > 0
        tool_names = [tool.name for tool in read_tools]
        assert "read_file" in tool_names
        assert "search_files" in tool_names
    
    def test_get_tool_by_name(self, temp_dir):
        """Test getting a specific tool by name."""
        tool = get_tool_by_name("read_file", cwd=temp_dir)
        
        assert tool.name == "read_file"
        assert isinstance(tool, ReadFileTool)
    
    def test_get_tool_by_name_invalid(self, temp_dir):
        """Test getting an invalid tool name."""
        with pytest.raises(ValueError):
            get_tool_by_name("nonexistent_tool", cwd=temp_dir)
    
    def test_list_available_tools(self):
        """Test listing available tools."""
        tools_dict = list_available_tools()
        
        assert "read" in tools_dict
        assert "edit" in tools_dict
        assert "command" in tools_dict
        assert "read_file" in tools_dict["read"]
        assert "write_to_file" in tools_dict["edit"]