"""
Task and conversation management for mode-based agent execution.

This module provides the Task class which maintains conversation history,
manages parent-child task relationships, and supports mode switching within tasks.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from uuid import uuid4


class TaskState(str, Enum):
    """State of a task in its lifecycle."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Message:
    """A message in a conversation."""

    role: str  # "user", "assistant", "system"
    content: Union[str, List[Dict[str, Any]]]
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Task:
    """
    Represents a task with conversation history and mode context.

    A task maintains its own conversation history and can have parent-child
    relationships with other tasks. Tasks are mode-aware and can switch modes
    during execution.

    Attributes:
        task_id: Unique identifier for this task
        mode_slug: Current mode for this task
        messages: Conversation history for this task
        parent_task_id: ID of parent task if this is a subtask
        child_task_ids: IDs of child tasks created from this task
        state: Current state of the task
        created_at: When the task was created
        completed_at: When the task completed (if completed)
        metadata: Additional task metadata
    """

    task_id: str = field(default_factory=lambda: str(uuid4()))
    mode_slug: str = "code"
    messages: List[Message] = field(default_factory=list)
    parent_task_id: Optional[str] = None
    child_task_ids: List[str] = field(default_factory=list)
    state: TaskState = TaskState.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_message(
        self,
        role: str,
        content: Union[str, List[Dict[str, Any]]],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Message:
        """
        Add a message to the conversation history.

        Args:
            role: Message role (user, assistant, system)
            content: Message content
            metadata: Optional metadata for the message

        Returns:
            The created Message object
        """
        message = Message(
            role=role,
            content=content,
            metadata=metadata or {},
        )
        self.messages.append(message)
        return message

    def add_user_message(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> Message:
        """Add a user message to the conversation."""
        return self.add_message("user", content, metadata)

    def add_assistant_message(
        self, content: Union[str, List[Dict[str, Any]]], metadata: Optional[Dict[str, Any]] = None
    ) -> Message:
        """Add an assistant message to the conversation."""
        return self.add_message("assistant", content, metadata)

    def add_system_message(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> Message:
        """Add a system message to the conversation."""
        return self.add_message("system", content, metadata)

    def switch_mode(self, new_mode_slug: str) -> None:
        """
        Switch this task to a different mode.

        Args:
            new_mode_slug: Slug of the new mode to switch to

        Note:
            Mode switching typically involves updating the system prompt
            and may affect which tools are available.
        """
        old_mode = self.mode_slug
        self.mode_slug = new_mode_slug

        # Add a system message to track the mode change
        self.add_system_message(
            f"Mode switched from {old_mode} to {new_mode_slug}",
            metadata={"mode_change": {"from": old_mode, "to": new_mode_slug}},
        )

    def create_child_task(self, mode_slug: str, initial_message: str) -> "Task":
        """
        Create a child task in a different mode.

        Args:
            mode_slug: Mode for the child task
            initial_message: Initial user message for the child task

        Returns:
            The newly created child Task
        """
        child_task = Task(
            mode_slug=mode_slug,
            parent_task_id=self.task_id,
        )
        child_task.add_user_message(initial_message)

        # Track child in parent
        self.child_task_ids.append(child_task.task_id)

        return child_task

    def mark_running(self) -> None:
        """Mark the task as running."""
        self.state = TaskState.RUNNING

    def mark_completed(self, result: Optional[str] = None) -> None:
        """
        Mark the task as completed.

        Args:
            result: Optional completion result/summary
        """
        self.state = TaskState.COMPLETED
        self.completed_at = datetime.now()

        if result:
            self.metadata["completion_result"] = result

    def mark_failed(self, error: Optional[str] = None) -> None:
        """
        Mark the task as failed.

        Args:
            error: Optional error message
        """
        self.state = TaskState.FAILED
        self.completed_at = datetime.now()

        if error:
            self.metadata["error"] = error

    def mark_cancelled(self) -> None:
        """Mark the task as cancelled."""
        self.state = TaskState.CANCELLED
        self.completed_at = datetime.now()

    def get_conversation_context(self, max_messages: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get the conversation context for API calls.

        Args:
            max_messages: Maximum number of messages to return (None = all)

        Returns:
            List of message dictionaries suitable for API calls
        """
        messages = self.messages
        if max_messages is not None and len(messages) > max_messages:
            messages = messages[-max_messages:]

        return [{"role": msg.role, "content": msg.content} for msg in messages]

    def to_dict(self) -> Dict[str, Any]:
        """Convert task to dictionary for serialization."""
        return {
            "task_id": self.task_id,
            "mode_slug": self.mode_slug,
            "messages": [
                {
                    "role": msg.role,
                    "content": msg.content,
                    "timestamp": msg.timestamp.isoformat(),
                    "metadata": msg.metadata,
                }
                for msg in self.messages
            ],
            "parent_task_id": self.parent_task_id,
            "child_task_ids": self.child_task_ids,
            "state": self.state.value,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Task":
        """Create a task from a dictionary."""
        task = cls(
            task_id=data["task_id"],
            mode_slug=data["mode_slug"],
            parent_task_id=data.get("parent_task_id"),
            child_task_ids=data.get("child_task_ids", []),
            state=TaskState(data["state"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            completed_at=(
                datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None
            ),
            metadata=data.get("metadata", {}),
        )

        # Restore messages
        for msg_data in data.get("messages", []):
            task.messages.append(
                Message(
                    role=msg_data["role"],
                    content=msg_data["content"],
                    timestamp=datetime.fromisoformat(msg_data["timestamp"]),
                    metadata=msg_data.get("metadata", {}),
                )
            )

        return task

    def __repr__(self) -> str:
        return (
            f"Task(task_id={self.task_id!r}, mode={self.mode_slug!r}, "
            f"state={self.state.value}, messages={len(self.messages)})"
        )