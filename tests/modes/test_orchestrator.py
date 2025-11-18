"""Tests for ModeOrchestrator."""

import tempfile
from pathlib import Path

import pytest

from roo_code.modes.builtin_modes import BUILTIN_MODES
from roo_code.modes.config import ModeConfig, ModeSource, GroupOptions
from roo_code.modes.orchestrator import ModeOrchestrator
from roo_code.modes.task import Task, TaskState


class TestModeOrchestrator:
    """Test ModeOrchestrator class."""

    def test_init_with_builtin_modes(self):
        """Test initializing orchestrator loads builtin modes."""
        orchestrator = ModeOrchestrator()
        
        # Should have loaded builtin modes
        assert len(orchestrator.modes) > 0
        assert "code" in orchestrator.modes
        assert "architect" in orchestrator.modes
        assert "debug" in orchestrator.modes
        assert "ask" in orchestrator.modes
        assert "orchestrator" in orchestrator.modes

    def test_get_mode(self):
        """Test getting a mode by slug."""
        orchestrator = ModeOrchestrator()
        
        code_mode = orchestrator.get_mode("code")
        assert code_mode is not None
        assert code_mode.slug == "code"
        assert code_mode.name == "💻 Code"

    def test_get_nonexistent_mode(self):
        """Test getting a mode that doesn't exist."""
        orchestrator = ModeOrchestrator()
        mode = orchestrator.get_mode("nonexistent")
        assert mode is None

    def test_get_all_modes(self):
        """Test getting all modes."""
        orchestrator = ModeOrchestrator()
        modes = orchestrator.get_all_modes()
        
        assert len(modes) >= 5  # At least 5 builtin modes
        slugs = [m.slug for m in modes]
        assert "code" in slugs
        assert "architect" in slugs

    def test_get_mode_names(self):
        """Test getting all mode slugs."""
        orchestrator = ModeOrchestrator()
        names = orchestrator.get_mode_names()
        
        assert "code" in names
        assert "debug" in names
        assert "ask" in names

    def test_validate_mode_exists(self):
        """Test validating mode existence."""
        orchestrator = ModeOrchestrator()
        
        assert orchestrator.validate_mode_exists("code")
        assert orchestrator.validate_mode_exists("architect")
        assert not orchestrator.validate_mode_exists("nonexistent")

    def test_create_task(self):
        """Test creating a task."""
        orchestrator = ModeOrchestrator()
        task = orchestrator.create_task("code", "Write a function")
        
        assert task.mode_slug == "code"
        assert len(task.messages) == 1
        assert task.messages[0].content == "Write a function"
        assert task.task_id in orchestrator.tasks

    def test_create_task_invalid_mode(self):
        """Test creating a task with invalid mode raises error."""
        orchestrator = ModeOrchestrator()
        
        with pytest.raises(ValueError, match="Invalid mode"):
            orchestrator.create_task("invalid-mode")

    def test_create_task_with_parent(self):
        """Test creating a child task."""
        orchestrator = ModeOrchestrator()
        
        parent = orchestrator.create_task("orchestrator")
        child = orchestrator.create_task("code", "Subtask", parent_task=parent)
        
        assert child.parent_task_id == parent.task_id
        assert child.task_id in parent.child_task_ids

    def test_get_task(self):
        """Test getting a task by ID."""
        orchestrator = ModeOrchestrator()
        task = orchestrator.create_task("code")
        
        retrieved = orchestrator.get_task(task.task_id)
        assert retrieved is task

    def test_set_current_task(self):
        """Test setting the current task."""
        orchestrator = ModeOrchestrator()
        task = orchestrator.create_task("code")
        
        orchestrator.set_current_task(task)
        assert orchestrator.current_task is task

    def test_switch_mode(self):
        """Test switching task mode."""
        orchestrator = ModeOrchestrator()
        task = orchestrator.create_task("code")
        
        success = orchestrator.switch_mode(task, "debug")
        assert success
        assert task.mode_slug == "debug"

    def test_switch_mode_invalid(self):
        """Test switching to invalid mode."""
        orchestrator = ModeOrchestrator()
        task = orchestrator.create_task("code")
        
        success = orchestrator.switch_mode(task, "invalid")
        assert not success
        assert task.mode_slug == "code"  # Unchanged

    def test_can_use_tool_read_group(self):
        """Test checking if read tools are allowed."""
        orchestrator = ModeOrchestrator()
        task = orchestrator.create_task("code")
        
        assert orchestrator.can_use_tool(task, "read_file")
        assert orchestrator.can_use_tool(task, "list_files")
        assert orchestrator.can_use_tool(task, "search_files")

    def test_can_use_tool_edit_group(self):
        """Test checking if edit tools are allowed."""
        orchestrator = ModeOrchestrator()
        
        code_task = orchestrator.create_task("code")
        assert orchestrator.can_use_tool(code_task, "write_to_file")
        assert orchestrator.can_use_tool(code_task, "apply_diff")
        
        # Ask mode doesn't have edit
        ask_task = orchestrator.create_task("ask")
        assert not orchestrator.can_use_tool(ask_task, "write_to_file")

    def test_can_use_tool_always_allowed(self):
        """Test that certain tools are always allowed."""
        orchestrator = ModeOrchestrator()
        task = orchestrator.create_task("ask")
        
        # These should always be allowed
        assert orchestrator.can_use_tool(task, "ask_followup_question")
        assert orchestrator.can_use_tool(task, "attempt_completion")

    def test_can_edit_file_no_restrictions(self):
        """Test file editing without restrictions."""
        orchestrator = ModeOrchestrator()
        task = orchestrator.create_task("code")
        
        assert orchestrator.can_edit_file(task, "test.py")
        assert orchestrator.can_edit_file(task, "test.md")
        assert orchestrator.can_edit_file(task, "config.json")

    def test_can_edit_file_with_restrictions(self):
        """Test file editing with restrictions."""
        orchestrator = ModeOrchestrator()
        task = orchestrator.create_task("architect")
        
        # Architect can only edit .md files
        assert orchestrator.can_edit_file(task, "README.md")
        assert orchestrator.can_edit_file(task, "docs/guide.md")
        assert not orchestrator.can_edit_file(task, "test.py")
        assert not orchestrator.can_edit_file(task, "config.json")

    def test_validate_tool_use_success(self):
        """Test validating allowed tool use."""
        orchestrator = ModeOrchestrator()
        task = orchestrator.create_task("code")
        
        is_valid, error = orchestrator.validate_tool_use(task, "read_file")
        assert is_valid
        assert error is None

    def test_validate_tool_use_not_allowed(self):
        """Test validating disallowed tool use."""
        orchestrator = ModeOrchestrator()
        task = orchestrator.create_task("ask")
        
        is_valid, error = orchestrator.validate_tool_use(task, "write_to_file")
        assert not is_valid
        assert "not available" in error

    def test_validate_tool_use_file_restriction(self):
        """Test validating tool use with file restrictions."""
        orchestrator = ModeOrchestrator()
        task = orchestrator.create_task("architect")
        
        # Valid: editing markdown
        is_valid, error = orchestrator.validate_tool_use(
            task, "write_to_file", {"path": "README.md"}
        )
        assert is_valid
        
        # Invalid: editing Python file
        is_valid, error = orchestrator.validate_tool_use(
            task, "write_to_file", {"path": "test.py"}
        )
        assert not is_valid
        assert "Cannot edit file" in error

    def test_get_system_prompt(self):
        """Test generating system prompt."""
        orchestrator = ModeOrchestrator()
        task = orchestrator.create_task("code")
        
        prompt = orchestrator.get_system_prompt(task)
        
        assert "software engineer" in prompt.lower()
        assert len(prompt) > 0

    def test_get_system_prompt_with_custom_instructions(self):
        """Test system prompt includes custom instructions."""
        orchestrator = ModeOrchestrator()
        task = orchestrator.create_task("architect")
        
        prompt = orchestrator.get_system_prompt(task)
        
        # Architect has custom instructions
        assert "Mode Instructions" in prompt

    def test_complete_task_success(self):
        """Test completing a task successfully."""
        orchestrator = ModeOrchestrator()
        task = orchestrator.create_task("code")
        task.mark_running()
        
        orchestrator.complete_task(task, result="Task completed")
        
        assert task.state == TaskState.COMPLETED
        assert task.metadata["completion_result"] == "Task completed"

    def test_complete_task_failure(self):
        """Test completing a task with error."""
        orchestrator = ModeOrchestrator()
        task = orchestrator.create_task("code")
        task.mark_running()
        
        orchestrator.complete_task(task, error="Something failed")
        
        assert task.state == TaskState.FAILED
        assert task.metadata["error"] == "Something failed"

    def test_get_task_hierarchy(self):
        """Test getting task hierarchy."""
        orchestrator = ModeOrchestrator()
        
        parent = orchestrator.create_task("orchestrator")
        child1 = orchestrator.create_task("code", parent_task=parent)
        child2 = orchestrator.create_task("debug", parent_task=parent)
        
        hierarchy = orchestrator.get_task_hierarchy(child1)
        
        assert hierarchy["task"] is child1
        assert hierarchy["parent"] is parent
        assert len(hierarchy["children"]) == 0
        
        parent_hierarchy = orchestrator.get_task_hierarchy(parent)
        assert len(parent_hierarchy["children"]) == 2

    def test_reload_modes(self):
        """Test reloading modes from configuration."""
        orchestrator = ModeOrchestrator()
        initial_count = len(orchestrator.modes)
        
        # Reload should work without error
        orchestrator.reload_modes()
        
        # Should still have the same modes
        assert len(orchestrator.modes) == initial_count