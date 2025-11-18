"""
Unit tests for MCP tool handlers.

Tests tool operations for task management, mode switching, and validation.
"""

import pytest
from unittest.mock import Mock, AsyncMock
from roo_code.mcp.tools import ToolHandler
from roo_code.mcp.session import SessionManager, Session
from roo_code.mcp.validation import ValidationError
from roo_code.modes.config import ModeConfig, ModeSource
from roo_code.modes.orchestrator import ModeOrchestrator
from roo_code.modes.task import Task, TaskState


@pytest.fixture
def mock_orchestrator():
    """Create a mock mode orchestrator."""
    orchestrator = Mock(spec=ModeOrchestrator)
    
    # Create sample modes
    code_mode = ModeConfig(
        slug="code",
        name="Code Mode",
        source=ModeSource.BUILTIN,
        description="Write and modify code",
        when_to_use="Use when writing or editing code",
        groups=["read", "edit", "command"]
    )
    
    ask_mode = ModeConfig(
        slug="ask",
        name="Ask Mode",
        source=ModeSource.BUILTIN,
        description="Answer questions",
        groups=["read"]
    )
    
    orchestrator.get_all_modes = Mock(return_value=[code_mode, ask_mode])
    orchestrator.get_mode = Mock(side_effect=lambda slug: {
        "code": code_mode,
        "ask": ask_mode
    }.get(slug))
    orchestrator.get_mode_names = Mock(return_value=["code", "ask"])
    orchestrator.validate_mode_exists = Mock(side_effect=lambda slug: slug in ["code", "ask"])
    orchestrator.create_task = Mock(side_effect=lambda **kwargs: Task(**kwargs))
    orchestrator.switch_mode = Mock(return_value=True)
    orchestrator.get_system_prompt = Mock(return_value="System prompt text")
    
    return orchestrator


@pytest.fixture
def session_manager(mock_orchestrator):
    """Create a session manager."""
    return SessionManager(orchestrator=mock_orchestrator)


@pytest.fixture
def tool_handler(session_manager, mock_orchestrator):
    """Create a tool handler."""
    return ToolHandler(session_manager, mock_orchestrator)


class TestToolHandler:
    """Test ToolHandler class."""
    
    def test_init(self, session_manager, mock_orchestrator):
        """Test handler initialization."""
        handler = ToolHandler(session_manager, mock_orchestrator)
        
        assert handler.session_manager == session_manager
        assert handler.orchestrator == mock_orchestrator
        assert len(handler.tools) > 0
    
    @pytest.mark.asyncio
    async def test_list_tools(self, tool_handler):
        """Test listing available tools."""
        tools = await tool_handler.list_tools()
        
        assert len(tools) > 0
        
        # Check tool names
        tool_names = [t["name"] for t in tools]
        assert "list_modes" in tool_names
        assert "get_mode_info" in tool_names
        assert "create_task" in tool_names
        assert "switch_mode" in tool_names
        assert "get_task_info" in tool_names
        assert "validate_tool_use" in tool_names
        assert "complete_task" in tool_names
    
    @pytest.mark.asyncio
    async def test_list_tools_format(self, tool_handler):
        """Test tool list format."""
        tools = await tool_handler.list_tools()
        
        for tool in tools:
            assert "name" in tool
            assert "description" in tool
            assert "inputSchema" in tool
            
            # Check schema structure
            schema = tool["inputSchema"]
            assert "type" in schema
            assert schema["type"] == "object"
            assert "properties" in schema


class TestListModesTool:
    """Test list_modes tool."""
    
    @pytest.mark.asyncio
    async def test_list_modes_all(self, tool_handler):
        """Test listing all modes."""
        result = await tool_handler.call_tool("list_modes", {})
        
        assert "content" in result
        assert len(result["content"]) > 0
        
        text = result["content"][0]["text"]
        assert "Available modes:" in text
        assert "code" in text.lower()
        assert "ask" in text.lower()
    
    @pytest.mark.asyncio
    async def test_list_modes_by_source(self, tool_handler):
        """Test listing modes filtered by source."""
        result = await tool_handler.call_tool("list_modes", {"source": "builtin"})
        
        assert "content" in result
        text = result["content"][0]["text"]
        assert "builtin" in text.lower()
    
    @pytest.mark.asyncio
    async def test_list_modes_shows_tool_groups(self, tool_handler):
        """Test that list_modes shows tool groups."""
        result = await tool_handler.call_tool("list_modes", {})
        
        text = result["content"][0]["text"]
        assert "Tool groups:" in text or "groups" in text.lower()


class TestGetModeInfoTool:
    """Test get_mode_info tool."""
    
    @pytest.mark.asyncio
    async def test_get_mode_info_basic(self, tool_handler):
        """Test getting basic mode info."""
        result = await tool_handler.call_tool("get_mode_info", {"mode_slug": "code"})
        
        assert "content" in result
        text = result["content"][0]["text"]
        
        assert "Code Mode" in text
        assert "code" in text.lower()
        assert "Source:" in text
    
    @pytest.mark.asyncio
    async def test_get_mode_info_with_system_prompt(self, tool_handler):
        """Test getting mode info with system prompt."""
        result = await tool_handler.call_tool(
            "get_mode_info",
            {"mode_slug": "code", "include_system_prompt": True}
        )
        
        text = result["content"][0]["text"]
        assert "System Prompt:" in text
        assert "System prompt text" in text
    
    @pytest.mark.asyncio
    async def test_get_mode_info_invalid_slug(self, tool_handler):
        """Test getting info for invalid mode slug."""
        with pytest.raises(ValidationError) as exc_info:
            await tool_handler.call_tool("get_mode_info", {"mode_slug": "invalid@mode"})
        
        assert "alphanumeric" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_get_mode_info_nonexistent_mode(self, tool_handler):
        """Test getting info for non-existent mode."""
        with pytest.raises(ValidationError) as exc_info:
            await tool_handler.call_tool("get_mode_info", {"mode_slug": "nonexistent"})
        
        assert "not found" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_get_mode_info_shows_tool_groups(self, tool_handler):
        """Test that mode info shows tool group status."""
        result = await tool_handler.call_tool("get_mode_info", {"mode_slug": "code"})
        
        text = result["content"][0]["text"]
        assert "Tool Groups:" in text
        # Check for enabled/disabled indicators
        assert "✓" in text or "✗" in text


class TestCreateTaskTool:
    """Test create_task tool."""
    
    @pytest.mark.asyncio
    async def test_create_task_minimal(self, tool_handler):
        """Test creating task with minimal parameters."""
        result = await tool_handler.call_tool("create_task", {"mode_slug": "code"})
        
        assert "content" in result
        assert "metadata" in result
        
        metadata = result["metadata"]
        assert "session_id" in metadata
        assert "task_id" in metadata
        assert "mode_slug" in metadata
        assert metadata["mode_slug"] == "code"
    
    @pytest.mark.asyncio
    async def test_create_task_with_message(self, tool_handler):
        """Test creating task with initial message."""
        result = await tool_handler.call_tool(
            "create_task",
            {"mode_slug": "code", "initial_message": "Write a function"}
        )
        
        assert "content" in result
        text = result["content"][0]["text"]
        assert "Task created successfully" in text
    
    @pytest.mark.asyncio
    async def test_create_task_invalid_mode(self, tool_handler):
        """Test creating task with invalid mode."""
        with pytest.raises(ValidationError) as exc_info:
            await tool_handler.call_tool("create_task", {"mode_slug": "nonexistent"})
        
        assert "invalid" in str(exc_info.value).lower() or "not found" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_create_task_with_parent(self, tool_handler, session_manager):
        """Test creating subtask with parent session."""
        # Create parent task
        parent_task = Task(mode_slug="code", task_id="parent_123")
        parent_session = session_manager.create_session(parent_task)
        
        # Create child task
        result = await tool_handler.call_tool(
            "create_task",
            {
                "mode_slug": "ask",
                "parent_session_id": parent_session.session_id
            }
        )
        
        assert "content" in result
        assert "metadata" in result
    
    @pytest.mark.asyncio
    async def test_create_task_invalid_parent_session(self, tool_handler):
        """Test creating task with invalid parent session."""
        with pytest.raises(ValidationError) as exc_info:
            await tool_handler.call_tool(
                "create_task",
                {
                    "mode_slug": "code",
                    "parent_session_id": "ses_nonexistent"
                }
            )
        
        assert "not found" in str(exc_info.value).lower()


class TestSwitchModeTool:
    """Test switch_mode tool."""
    
    @pytest.mark.asyncio
    async def test_switch_mode_basic(self, tool_handler, session_manager):
        """Test basic mode switching."""
        # Create initial task
        task = Task(mode_slug="code", task_id="task_123")
        session = session_manager.create_session(task)
        
        # Switch mode
        result = await tool_handler.call_tool(
            "switch_mode",
            {
                "session_id": session.session_id,
                "new_mode_slug": "ask"
            }
        )
        
        assert "content" in result
        assert "metadata" in result
        
        text = result["content"][0]["text"]
        assert "Mode switched successfully" in text
        assert "code" in text.lower()
        assert "ask" in text.lower()
    
    @pytest.mark.asyncio
    async def test_switch_mode_with_reason(self, tool_handler, session_manager):
        """Test mode switching with reason."""
        task = Task(mode_slug="code", task_id="task_123")
        session = session_manager.create_session(task)
        
        result = await tool_handler.call_tool(
            "switch_mode",
            {
                "session_id": session.session_id,
                "new_mode_slug": "ask",
                "reason": "Need to ask a question"
            }
        )
        
        text = result["content"][0]["text"]
        assert "Reason:" in text
        assert "Need to ask a question" in text
    
    @pytest.mark.asyncio
    async def test_switch_mode_invalid_session(self, tool_handler):
        """Test switching mode with invalid session."""
        with pytest.raises(ValidationError) as exc_info:
            await tool_handler.call_tool(
                "switch_mode",
                {
                    "session_id": "ses_nonexistent",
                    "new_mode_slug": "ask"
                }
            )
        
        assert "not found" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_switch_mode_invalid_new_mode(self, tool_handler, session_manager):
        """Test switching to invalid mode."""
        task = Task(mode_slug="code", task_id="task_123")
        session = session_manager.create_session(task)
        
        with pytest.raises(ValidationError) as exc_info:
            await tool_handler.call_tool(
                "switch_mode",
                {
                    "session_id": session.session_id,
                    "new_mode_slug": "nonexistent"
                }
            )
        
        assert "invalid" in str(exc_info.value).lower()


class TestGetTaskInfoTool:
    """Test get_task_info tool."""
    
    @pytest.mark.asyncio
    async def test_get_task_info_basic(self, tool_handler, session_manager):
        """Test getting basic task info."""
        task = Task(mode_slug="code", task_id="task_123")
        session = session_manager.create_session(task)
        
        result = await tool_handler.call_tool(
            "get_task_info",
            {"session_id": session.session_id}
        )
        
        assert "content" in result
        text = result["content"][0]["text"]
        
        assert "Task Information" in text
        assert session.session_id in text
        assert task.task_id in text
        assert "code" in text.lower()
    
    @pytest.mark.asyncio
    async def test_get_task_info_with_messages(self, tool_handler, session_manager):
        """Test getting task info with messages."""
        task = Task(mode_slug="code", task_id="task_123")
        session = session_manager.create_session(task)
        
        result = await tool_handler.call_tool(
            "get_task_info",
            {
                "session_id": session.session_id,
                "include_messages": True
            }
        )
        
        text = result["content"][0]["text"]
        assert "Conversation History" in text or "messages" in text.lower()
    
    @pytest.mark.asyncio
    async def test_get_task_info_with_hierarchy(self, tool_handler, session_manager):
        """Test getting task info with hierarchy."""
        parent_task = Task(mode_slug="code", task_id="parent_123")
        parent_session = session_manager.create_session(parent_task)
        
        child_task = Task(mode_slug="ask", task_id="child_456", parent_task_id="parent_123")
        child_session = session_manager.create_session(child_task)
        
        result = await tool_handler.call_tool(
            "get_task_info",
            {
                "session_id": child_session.session_id,
                "include_hierarchy": True
            }
        )
        
        text = result["content"][0]["text"]
        assert "Hierarchy:" in text
        assert "Parent Task:" in text or "parent" in text.lower()
    
    @pytest.mark.asyncio
    async def test_get_task_info_invalid_session(self, tool_handler):
        """Test getting info for invalid session."""
        with pytest.raises(ValidationError) as exc_info:
            await tool_handler.call_tool(
                "get_task_info",
                {"session_id": "ses_nonexistent"}
            )
        
        assert "not found" in str(exc_info.value).lower()


class TestValidateToolUseTool:
    """Test validate_tool_use tool."""
    
    @pytest.mark.asyncio
    async def test_validate_tool_use_basic(self, tool_handler, session_manager):
        """Test basic tool validation."""
        task = Task(mode_slug="code", task_id="task_123")
        session = session_manager.create_session(task)
        
        result = await tool_handler.call_tool(
            "validate_tool_use",
            {
                "session_id": session.session_id,
                "tool_name": "read_file"
            }
        )
        
        assert "content" in result
    
    @pytest.mark.asyncio
    async def test_validate_tool_use_with_file_path(self, tool_handler, session_manager):
        """Test tool validation with file path."""
        task = Task(mode_slug="code", task_id="task_123")
        session = session_manager.create_session(task)
        
        result = await tool_handler.call_tool(
            "validate_tool_use",
            {
                "session_id": session.session_id,
                "tool_name": "write_to_file",
                "file_path": "src/test.py"
            }
        )
        
        assert "content" in result
    
    @pytest.mark.asyncio
    async def test_validate_tool_use_invalid_session(self, tool_handler):
        """Test validation with invalid session."""
        with pytest.raises(ValidationError) as exc_info:
            await tool_handler.call_tool(
                "validate_tool_use",
                {
                    "session_id": "ses_nonexistent",
                    "tool_name": "read_file"
                }
            )
        
        assert "not found" in str(exc_info.value).lower()


class TestCompleteTaskTool:
    """Test complete_task tool."""
    
    @pytest.mark.asyncio
    async def test_complete_task_success(self, tool_handler, session_manager):
        """Test completing task successfully."""
        task = Task(mode_slug="code", task_id="task_123")
        session = session_manager.create_session(task)
        
        result = await tool_handler.call_tool(
            "complete_task",
            {
                "session_id": session.session_id,
                "status": "completed",
                "result": "Task completed successfully"
            }
        )
        
        assert "content" in result
        text = result["content"][0]["text"]
        assert "completed" in text.lower()
    
    @pytest.mark.asyncio
    async def test_complete_task_failed(self, tool_handler, session_manager):
        """Test marking task as failed."""
        task = Task(mode_slug="code", task_id="task_123")
        session = session_manager.create_session(task)
        
        result = await tool_handler.call_tool(
            "complete_task",
            {
                "session_id": session.session_id,
                "status": "failed",
                "result": "Error occurred"
            }
        )
        
        assert "content" in result
    
    @pytest.mark.asyncio
    async def test_complete_task_cancelled(self, tool_handler, session_manager):
        """Test cancelling task."""
        task = Task(mode_slug="code", task_id="task_123")
        session = session_manager.create_session(task)
        
        result = await tool_handler.call_tool(
            "complete_task",
            {
                "session_id": session.session_id,
                "status": "cancelled"
            }
        )
        
        assert "content" in result
    
    @pytest.mark.asyncio
    async def test_complete_task_invalid_session(self, tool_handler):
        """Test completing invalid session."""
        with pytest.raises(ValidationError) as exc_info:
            await tool_handler.call_tool(
                "complete_task",
                {
                    "session_id": "ses_nonexistent",
                    "status": "completed"
                }
            )
        
        assert "not found" in str(exc_info.value).lower()


class TestToolErrorHandling:
    """Test error handling in tools."""
    
    @pytest.mark.asyncio
    async def test_call_unknown_tool(self, tool_handler):
        """Test calling unknown tool."""
        with pytest.raises(ValidationError) as exc_info:
            await tool_handler.call_tool("nonexistent_tool", {})
        
        assert "unknown" in str(exc_info.value).lower()
        assert "available" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_validation_error_propagation(self, tool_handler):
        """Test that validation errors propagate correctly."""
        with pytest.raises(ValidationError) as exc_info:
            await tool_handler.call_tool("get_mode_info", {"mode_slug": ""})
        
        assert "empty" in str(exc_info.value).lower() or "slug" in str(exc_info.value).lower()


class TestToolIntegration:
    """Test tool integration scenarios."""
    
    @pytest.mark.asyncio
    async def test_create_and_get_task(self, tool_handler):
        """Test creating task then getting its info."""
        # Create task
        create_result = await tool_handler.call_tool(
            "create_task",
            {"mode_slug": "code", "initial_message": "Test task"}
        )
        
        session_id = create_result["metadata"]["session_id"]
        
        # Get task info
        info_result = await tool_handler.call_tool(
            "get_task_info",
            {"session_id": session_id}
        )
        
        text = info_result["content"][0]["text"]
        assert session_id in text
    
    @pytest.mark.asyncio
    async def test_create_switch_get_workflow(self, tool_handler):
        """Test complete workflow: create, switch, get info."""
        # 1. Create task
        create_result = await tool_handler.call_tool(
            "create_task",
            {"mode_slug": "code"}
        )
        session_id = create_result["metadata"]["session_id"]
        
        # 2. Switch mode
        switch_result = await tool_handler.call_tool(
            "switch_mode",
            {"session_id": session_id, "new_mode_slug": "ask"}
        )
        assert "metadata" in switch_result
        
        # 3. Get task info
        info_result = await tool_handler.call_tool(
            "get_task_info",
            {"session_id": session_id}
        )
        
        text = info_result["content"][0]["text"]
        assert "ask" in text.lower()
    
    @pytest.mark.asyncio
    async def test_list_modes_then_create_task(self, tool_handler):
        """Test listing modes then creating task in one."""
        # List modes
        list_result = await tool_handler.call_tool("list_modes", {})
        text = list_result["content"][0]["text"]
        assert "code" in text.lower()
        
        # Create task in code mode
        create_result = await tool_handler.call_tool(
            "create_task",
            {"mode_slug": "code"}
        )
        assert "session_id" in create_result["metadata"]