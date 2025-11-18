"""Tests for Phase 2: Core Integration - Context, Modes, and File Watching."""

import pytest
from pathlib import Path
from typing import Dict, Any, List
from roo_code.builtin_tools.context import ToolContext
from roo_code.builtin_tools.modes import (
    ModeConfig,
    FileRestrictionError,
    get_mode_by_slug,
    get_all_modes,
    ARCHITECT_MODE,
    CODE_MODE,
    TEST_MODE,
)
from roo_code.builtin_tools.file_watcher import (
    FileWatcher,
    AsyncFileWatcher,
    FileChange,
    FileChangeType,
)
from roo_code.builtin_tools.file_operations import (
    WriteToFileTool,
    ApplyDiffTool,
    InsertContentTool,
)
from roo_code.tools import ToolResult


# Mode System Tests


def test_mode_config_creation():
    """Test creating a ModeConfig."""
    mode = ModeConfig(
        name="Test Mode",
        slug="test",
        file_patterns=[r"\.py$"],
        description="A test mode"
    )
    assert mode.name == "Test Mode"
    assert mode.slug == "test"
    assert mode.file_patterns == [r"\.py$"]
    assert mode.description == "A test mode"


def test_mode_allows_file_edit_with_patterns():
    """Test file edit permission checking with patterns."""
    mode = ModeConfig(
        name="Test Mode",
        slug="test",
        file_patterns=[r"\.py$", r"\.md$"]
    )
    
    # Should allow Python and Markdown files
    assert mode.allows_file_edit("test.py")
    assert mode.allows_file_edit("README.md")
    assert mode.allows_file_edit("src/main.py")
    
    # Should deny other files
    assert not mode.allows_file_edit("test.js")
    assert not mode.allows_file_edit("config.json")


def test_mode_allows_all_files_with_empty_patterns():
    """Test that empty patterns allow all files."""
    mode = ModeConfig(
        name="Code Mode",
        slug="code",
        file_patterns=[]
    )
    
    # Should allow any file
    assert mode.allows_file_edit("test.py")
    assert mode.allows_file_edit("test.js")
    assert mode.allows_file_edit("config.json")
    assert mode.allows_file_edit("README.md")


def test_mode_check_file_edit_raises_error():
    """Test that check_file_edit raises FileRestrictionError when denied."""
    mode = ModeConfig(
        name="Markdown Mode",
        slug="markdown",
        file_patterns=[r"\.md$"]
    )
    
    # Should not raise for allowed files
    mode.check_file_edit("README.md")
    
    # Should raise for denied files
    with pytest.raises(FileRestrictionError) as exc_info:
        mode.check_file_edit("test.py")
    
    assert "test.py" in str(exc_info.value)
    assert "Markdown Mode" in str(exc_info.value)


def test_predefined_modes():
    """Test predefined mode configurations."""
    # Architect mode - only markdown
    assert ARCHITECT_MODE.allows_file_edit("README.md")
    assert not ARCHITECT_MODE.allows_file_edit("src/main.py")
    
    # Code mode - all files
    assert CODE_MODE.allows_file_edit("README.md")
    assert CODE_MODE.allows_file_edit("src/main.py")
    
    # Test mode - only test files
    assert TEST_MODE.allows_file_edit("tests/test_main.py")
    assert TEST_MODE.allows_file_edit("src/main.test.py")
    assert not TEST_MODE.allows_file_edit("src/main.py")


def test_get_mode_by_slug():
    """Test retrieving modes by slug."""
    architect = get_mode_by_slug("architect")
    assert architect is not None
    assert architect.slug == "architect"
    
    code = get_mode_by_slug("code")
    assert code is not None
    assert code.slug == "code"
    
    unknown = get_mode_by_slug("unknown")
    assert unknown is None


def test_get_all_modes():
    """Test getting all predefined modes."""
    modes = get_all_modes()
    assert len(modes) >= 5
    assert any(m.slug == "architect" for m in modes)
    assert any(m.slug == "code" for m in modes)


# File Watcher Tests


def test_file_watcher_creation():
    """Test creating a FileWatcher."""
    watcher = FileWatcher(workspace_root="/workspace")
    assert watcher.workspace_root == Path("/workspace").resolve()
    assert len(watcher.get_changes()) == 0


def test_file_watcher_record_change():
    """Test recording file changes."""
    watcher = FileWatcher()
    
    change = watcher.record_change(
        "test.py",
        FileChangeType.CREATED,
        tool_name="write_to_file"
    )
    
    assert change.path == "test.py"
    assert change.change_type == FileChangeType.CREATED
    assert change.tool_name == "write_to_file"


def test_file_watcher_get_changes():
    """Test getting recorded changes."""
    watcher = FileWatcher()
    
    watcher.record_change("test1.py", FileChangeType.CREATED, tool_name="tool1")
    watcher.record_change("test2.py", FileChangeType.MODIFIED, tool_name="tool2")
    watcher.record_change("test3.py", FileChangeType.DELETED, tool_name="tool1")
    
    # Get all changes
    all_changes = watcher.get_changes()
    assert len(all_changes) == 3
    
    # Filter by tool name
    tool1_changes = watcher.get_changes(tool_name="tool1")
    assert len(tool1_changes) == 2
    
    # Filter by change type
    created = watcher.get_changes(change_type=FileChangeType.CREATED)
    assert len(created) == 1


def test_file_watcher_modified_files():
    """Test getting modified files."""
    watcher = FileWatcher()
    
    watcher.record_change("test1.py", FileChangeType.CREATED)
    watcher.record_change("test2.py", FileChangeType.MODIFIED)
    watcher.record_change("test3.py", FileChangeType.DELETED)
    
    modified = watcher.get_modified_files()
    assert "test1.py" in modified
    assert "test2.py" in modified
    assert "test3.py" not in modified


def test_file_watcher_deleted_files():
    """Test getting deleted files."""
    watcher = FileWatcher()
    
    watcher.record_change("test1.py", FileChangeType.CREATED)
    watcher.record_change("test2.py", FileChangeType.DELETED)
    
    deleted = watcher.get_deleted_files()
    assert "test2.py" in deleted
    assert "test1.py" not in deleted


def test_file_watcher_callbacks():
    """Test file watcher callbacks."""
    watcher = FileWatcher()
    called = []
    
    def callback(change: FileChange):
        called.append(change.path)
    
    watcher.on_change(callback)
    
    watcher.record_change("test1.py", FileChangeType.CREATED)
    watcher.record_change("test2.py", FileChangeType.MODIFIED)
    
    assert called == ["test1.py", "test2.py"]


def test_file_watcher_statistics():
    """Test file watcher statistics."""
    watcher = FileWatcher()
    
    watcher.record_change("test1.py", FileChangeType.CREATED, tool_name="tool1")
    watcher.record_change("test2.py", FileChangeType.MODIFIED, tool_name="tool1")
    watcher.record_change("test3.py", FileChangeType.DELETED, tool_name="tool2")
    
    stats = watcher.get_statistics()
    
    assert stats["total_changes"] == 3
    assert stats["files_created"] == 1
    assert stats["files_modified"] == 1
    assert stats["files_deleted"] == 1
    assert stats["unique_files"] == 3
    assert stats["by_tool"]["tool1"] == 2
    assert stats["by_tool"]["tool2"] == 1


def test_file_watcher_checkpoint():
    """Test file watcher checkpointing."""
    watcher = FileWatcher()
    
    watcher.record_change("test1.py", FileChangeType.CREATED)
    watcher.record_change("test2.py", FileChangeType.MODIFIED)
    
    # Create checkpoint (clears changes)
    checkpoint = watcher.checkpoint()
    assert len(checkpoint) == 2
    assert len(watcher.get_changes()) == 0
    
    # Add more changes
    watcher.record_change("test3.py", FileChangeType.DELETED)
    assert len(watcher.get_changes()) == 1
    
    # Restore checkpoint
    watcher.restore_checkpoint(checkpoint)
    assert len(watcher.get_changes()) == 3


@pytest.mark.asyncio
async def test_async_file_watcher_callbacks():
    """Test async file watcher callbacks."""
    watcher = AsyncFileWatcher()
    called = []
    
    async def async_callback(change: FileChange):
        called.append(change.path)
    
    watcher.on_change_async(async_callback)
    
    await watcher.record_change_async("test1.py", FileChangeType.CREATED)
    await watcher.record_change_async("test2.py", FileChangeType.MODIFIED)
    
    assert called == ["test1.py", "test2.py"]


# Tool Context Tests


def test_tool_context_creation():
    """Test creating a ToolContext."""
    context = ToolContext(cwd="/workspace")
    assert context.cwd == "/workspace"
    assert context.mode is None
    assert context.file_watcher is None


def test_tool_context_create_minimal():
    """Test creating a minimal context."""
    context = ToolContext.create_minimal(cwd="/workspace")
    assert context.cwd == "/workspace"
    assert context.ask_approval is None
    assert context.push_result is None


def test_tool_context_create_with_mode():
    """Test creating context with a mode."""
    context = ToolContext.create_with_mode(cwd="/workspace", mode=ARCHITECT_MODE)
    assert context.mode == ARCHITECT_MODE


@pytest.mark.asyncio
async def test_tool_context_create_full():
    """Test creating a fully configured context."""
    approved = []
    messages = []
    
    async def ask_approval(data: Dict[str, Any]) -> bool:
        approved.append(data["action"])
        return True
    
    async def push_result(msg: str) -> None:
        messages.append(msg)
    
    context = ToolContext.create_full(
        cwd="/workspace",
        ask_approval=ask_approval,
        push_result=push_result,
        mode=CODE_MODE,
        task_id="task-123"
    )
    
    assert context.cwd == "/workspace"
    assert context.mode == CODE_MODE
    assert context.task_id == "task-123"
    assert context.file_watcher is not None


@pytest.mark.asyncio
async def test_tool_context_request_approval():
    """Test requesting approval through context."""
    approval_count = 0
    
    async def ask_approval(data: Dict[str, Any]) -> bool:
        nonlocal approval_count
        approval_count += 1
        return data["action"] != "deny"
    
    context = ToolContext(cwd=".", ask_approval=ask_approval)
    
    # Should be approved
    assert await context.request_approval("allow", {"key": "value"})
    assert approval_count == 1
    
    # Should be denied
    assert not await context.request_approval("deny")
    assert approval_count == 2


@pytest.mark.asyncio
async def test_tool_context_request_approval_no_callback():
    """Test that approval defaults to True with no callback."""
    context = ToolContext(cwd=".")
    assert await context.request_approval("action")


@pytest.mark.asyncio
async def test_tool_context_stream_result():
    """Test streaming results through context."""
    messages = []
    
    async def push_result(msg: str) -> None:
        messages.append(msg)
    
    context = ToolContext(cwd=".", push_result=push_result)
    
    await context.stream_result("Message 1")
    await context.stream_result("Message 2")
    
    assert messages == ["Message 1", "Message 2"]


def test_tool_context_check_file_edit_allowed():
    """Test checking file edit permissions."""
    context = ToolContext(cwd=".", mode=ARCHITECT_MODE)
    
    # Should not raise for allowed files
    context.check_file_edit_allowed("README.md")
    
    # Should raise for denied files
    with pytest.raises(FileRestrictionError):
        context.check_file_edit_allowed("main.py")


def test_tool_context_is_file_edit_allowed():
    """Test checking if file edit is allowed."""
    context = ToolContext(cwd=".", mode=ARCHITECT_MODE)
    
    assert context.is_file_edit_allowed("README.md")
    assert not context.is_file_edit_allowed("main.py")


@pytest.mark.asyncio
async def test_tool_context_track_file_change():
    """Test tracking file changes through context."""
    watcher = AsyncFileWatcher()
    context = ToolContext(cwd=".", file_watcher=watcher)
    
    await context.track_file_change(
        "test.py",
        "created",
        tool_name="write_to_file",
        metadata={"lines": 10}
    )
    
    changes = watcher.get_changes()
    assert len(changes) == 1
    assert changes[0].path == "test.py"
    assert changes[0].tool_name == "write_to_file"


def test_tool_context_config_value():
    """Test getting and setting config values."""
    context = ToolContext(
        cwd=".",
        workspace_config={"editor": {"fontSize": 14}}
    )
    
    # Get value
    assert context.get_config_value("editor.fontSize") == 14
    assert context.get_config_value("editor.unknown", 12) == 12
    
    # Set value
    context.set_config_value("editor.tabSize", 4)
    assert context.get_config_value("editor.tabSize") == 4


def test_tool_context_checkpoints():
    """Test checkpoint functionality."""
    context = ToolContext(cwd=".")
    
    # Create checkpoint
    context.create_checkpoint("step1", {"data": "value1"})
    assert context.restore_checkpoint("step1") == {"data": "value1"}
    
    # Unknown checkpoint
    assert context.restore_checkpoint("unknown") is None
    
    # Clear checkpoints
    context.clear_checkpoints()
    assert context.restore_checkpoint("step1") is None


# Integration Tests with File Operations


@pytest.mark.asyncio
async def test_write_to_file_with_context(tmp_path):
    """Test WriteToFileTool with context integration."""
    approved_actions = []
    
    async def ask_approval(data: Dict[str, Any]) -> bool:
        approved_actions.append(data["action"])
        return True
    
    watcher = AsyncFileWatcher()
    context = ToolContext(
        cwd=str(tmp_path),
        ask_approval=ask_approval,
        file_watcher=watcher
    )
    
    tool = WriteToFileTool(cwd=str(tmp_path), context=context)
    tool.current_use_id = "test-id"
    
    result = await tool.execute({
        "path": "test.py",
        "content": "print('hello')\n"
    })
    
    assert not result.is_error
    # Check that approval was requested with "create" in the action
    assert any("create" in action.lower() for action in approved_actions)
    assert len(watcher.get_changes()) == 1
    assert watcher.get_changes()[0].change_type == FileChangeType.CREATED


@pytest.mark.asyncio
async def test_write_to_file_with_mode_restriction(tmp_path):
    """Test WriteToFileTool respects mode restrictions."""
    context = ToolContext(cwd=str(tmp_path), mode=ARCHITECT_MODE)
    
    tool = WriteToFileTool(cwd=str(tmp_path), context=context)
    tool.current_use_id = "test-id"
    
    # Should be denied - Python file not allowed in Architect mode
    result = await tool.execute({
        "path": "test.py",
        "content": "print('hello')\n"
    })
    
    assert result.is_error
    assert "not allowed" in result.content


@pytest.mark.asyncio
async def test_write_to_file_approval_denied(tmp_path):
    """Test WriteToFileTool when approval is denied."""
    async def ask_approval(data: Dict[str, Any]) -> bool:
        return False
    
    context = ToolContext(cwd=str(tmp_path), ask_approval=ask_approval)
    
    tool = WriteToFileTool(cwd=str(tmp_path), context=context)
    tool.current_use_id = "test-id"
    
    result = await tool.execute({
        "path": "test.py",
        "content": "print('hello')\n"
    })
    
    assert result.is_error
    assert "cancelled" in result.content.lower()


@pytest.mark.asyncio
async def test_apply_diff_with_context(tmp_path):
    """Test ApplyDiffTool with context integration."""
    # Create initial file
    test_file = tmp_path / "test.py"
    test_file.write_text("def hello():\n    print('hello')\n")
    
    approved_actions = []
    
    async def ask_approval(data: Dict[str, Any]) -> bool:
        approved_actions.append(data)
        return True
    
    watcher = AsyncFileWatcher()
    context = ToolContext(
        cwd=str(tmp_path),
        ask_approval=ask_approval,
        file_watcher=watcher
    )
    
    tool = ApplyDiffTool(cwd=str(tmp_path))
    tool.set_context(context)
    tool.current_use_id = "test-id"
    
    result = await tool.execute({
        "path": "test.py",
        "diff": """<<<<<<< SEARCH
:start_line:1
-------
def hello():
    print('hello')
=======
def hello():
    print('Hello, World!')
>>>>>>> REPLACE
"""
    })
    
    assert not result.is_error
    assert len(approved_actions) == 1
    assert len(watcher.get_changes()) == 1


@pytest.mark.asyncio
async def test_insert_content_with_context(tmp_path):
    """Test InsertContentTool with context integration."""
    # Create initial file
    test_file = tmp_path / "test.py"
    test_file.write_text("line 1\nline 2\n")
    
    approved_actions = []
    
    async def ask_approval(data: Dict[str, Any]) -> bool:
        approved_actions.append(data)
        return True
    
    watcher = AsyncFileWatcher()
    context = ToolContext(
        cwd=str(tmp_path),
        ask_approval=ask_approval,
        file_watcher=watcher
    )
    
    tool = InsertContentTool(cwd=str(tmp_path), context=context)
    tool.current_use_id = "test-id"
    
    result = await tool.execute({
        "path": "test.py",
        "line": 2,
        "content": "inserted line\n"
    })
    
    assert not result.is_error
    assert len(approved_actions) == 1
    assert len(watcher.get_changes()) == 1


@pytest.mark.asyncio
async def test_tool_without_context_still_works(tmp_path):
    """Test that tools work without context (backward compatibility)."""
    tool = WriteToFileTool(cwd=str(tmp_path))
    tool.current_use_id = "test-id"
    
    result = await tool.execute({
        "path": "test.py",
        "content": "print('hello')\n"
    })
    
    assert not result.is_error
    assert (tmp_path / "test.py").exists()