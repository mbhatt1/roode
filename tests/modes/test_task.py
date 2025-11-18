"""Tests for Task class and conversation management."""

import json
from datetime import datetime

import pytest

from roo_code.modes.task import Message, Task, TaskState


class TestMessage:
    """Test Message class."""

    def test_create_message(self):
        """Test creating a message."""
        msg = Message(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"
        assert isinstance(msg.timestamp, datetime)
        assert msg.metadata == {}

    def test_message_with_metadata(self):
        """Test message with metadata."""
        metadata = {"source": "test", "priority": "high"}
        msg = Message(role="assistant", content="Response", metadata=metadata)
        assert msg.metadata == metadata


class TestTask:
    """Test Task class."""

    def test_create_task(self):
        """Test creating a new task."""
        task = Task(mode_slug="code")
        assert task.mode_slug == "code"
        assert task.state == TaskState.PENDING
        assert len(task.messages) == 0
        assert task.parent_task_id is None
        assert len(task.child_task_ids) == 0
        assert isinstance(task.created_at, datetime)
        assert task.completed_at is None

    def test_task_with_parent(self):
        """Test creating a task with a parent."""
        parent_id = "parent-123"
        task = Task(mode_slug="debug", parent_task_id=parent_id)
        assert task.parent_task_id == parent_id

    def test_add_user_message(self):
        """Test adding a user message."""
        task = Task()
        msg = task.add_user_message("Test message")
        
        assert len(task.messages) == 1
        assert msg.role == "user"
        assert msg.content == "Test message"

    def test_add_assistant_message(self):
        """Test adding an assistant message."""
        task = Task()
        msg = task.add_assistant_message("AI response")
        
        assert len(task.messages) == 1
        assert msg.role == "assistant"
        assert msg.content == "AI response"

    def test_add_system_message(self):
        """Test adding a system message."""
        task = Task()
        msg = task.add_system_message("System info")
        
        assert len(task.messages) == 1
        assert msg.role == "system"
        assert msg.content == "System info"

    def test_add_message_with_metadata(self):
        """Test adding a message with metadata."""
        task = Task()
        metadata = {"type": "important"}
        msg = task.add_user_message("Test", metadata=metadata)
        
        assert msg.metadata == metadata

    def test_switch_mode(self):
        """Test switching task mode."""
        task = Task(mode_slug="code")
        task.switch_mode("debug")
        
        assert task.mode_slug == "debug"
        
        # Should have added a system message
        assert len(task.messages) == 1
        assert task.messages[0].role == "system"
        assert "code" in task.messages[0].content
        assert "debug" in task.messages[0].content

    def test_create_child_task(self):
        """Test creating a child task."""
        parent = Task(mode_slug="orchestrator")
        child = parent.create_child_task("code", "Write a function")
        
        assert child.parent_task_id == parent.task_id
        assert child.mode_slug == "code"
        assert child.task_id in parent.child_task_ids
        
        # Child should have initial message
        assert len(child.messages) == 1
        assert child.messages[0].content == "Write a function"

    def test_mark_running(self):
        """Test marking task as running."""
        task = Task()
        assert task.state == TaskState.PENDING
        
        task.mark_running()
        assert task.state == TaskState.RUNNING

    def test_mark_completed(self):
        """Test marking task as completed."""
        task = Task()
        task.mark_running()
        task.mark_completed("Task done")
        
        assert task.state == TaskState.COMPLETED
        assert task.completed_at is not None
        assert task.metadata["completion_result"] == "Task done"

    def test_mark_failed(self):
        """Test marking task as failed."""
        task = Task()
        task.mark_running()
        task.mark_failed("Something went wrong")
        
        assert task.state == TaskState.FAILED
        assert task.completed_at is not None
        assert task.metadata["error"] == "Something went wrong"

    def test_mark_cancelled(self):
        """Test marking task as cancelled."""
        task = Task()
        task.mark_running()
        task.mark_cancelled()
        
        assert task.state == TaskState.CANCELLED
        assert task.completed_at is not None

    def test_get_conversation_context(self):
        """Test getting conversation context."""
        task = Task()
        task.add_user_message("Message 1")
        task.add_assistant_message("Response 1")
        task.add_user_message("Message 2")
        
        context = task.get_conversation_context()
        
        assert len(context) == 3
        assert context[0]["role"] == "user"
        assert context[0]["content"] == "Message 1"
        assert context[1]["role"] == "assistant"
        assert context[2]["role"] == "user"

    def test_get_conversation_context_with_limit(self):
        """Test getting limited conversation context."""
        task = Task()
        for i in range(5):
            task.add_user_message(f"Message {i}")
        
        context = task.get_conversation_context(max_messages=2)
        
        assert len(context) == 2
        assert context[0]["content"] == "Message 3"
        assert context[1]["content"] == "Message 4"

    def test_to_dict(self):
        """Test serializing task to dictionary."""
        task = Task(mode_slug="code")
        task.add_user_message("Test")
        task.mark_running()
        
        data = task.to_dict()
        
        assert data["task_id"] == task.task_id
        assert data["mode_slug"] == "code"
        assert data["state"] == "running"
        assert len(data["messages"]) == 1
        assert data["parent_task_id"] is None
        assert isinstance(data["created_at"], str)

    def test_from_dict(self):
        """Test deserializing task from dictionary."""
        original = Task(mode_slug="debug")
        original.add_user_message("Original message")
        original.mark_completed("Done")
        
        data = original.to_dict()
        restored = Task.from_dict(data)
        
        assert restored.task_id == original.task_id
        assert restored.mode_slug == original.mode_slug
        assert restored.state == TaskState.COMPLETED
        assert len(restored.messages) == 1
        assert restored.messages[0].content == "Original message"

    def test_repr(self):
        """Test task string representation."""
        task = Task(mode_slug="architect")
        task.add_user_message("Test")
        
        repr_str = repr(task)
        assert "architect" in repr_str
        assert "PENDING" in repr_str
        assert "messages=1" in repr_str