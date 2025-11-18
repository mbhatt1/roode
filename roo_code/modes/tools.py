"""
Mode-specific tools for mode switching and task delegation.

This module provides the SwitchModeTool and NewTaskTool that enable
mode switching and subtask creation.
"""

from typing import Any, Callable, Dict, Optional

from ..tools import Tool, ToolInputSchema, ToolResult


class SwitchModeTool(Tool):
    """
    Tool for switching the current task to a different mode.

    This changes the mode of the current task, updating its system prompt
    and available tools accordingly.
    """

    def __init__(self, orchestrator: "ModeOrchestrator"):  # type: ignore
        """
        Initialize the switch mode tool.

        Args:
            orchestrator: ModeOrchestrator instance for mode management
        """
        self.orchestrator = orchestrator
        super().__init__(
            name="switch_mode",
            description=(
                "Request to switch to a different mode. This tool allows modes to request switching "
                "to another mode when needed, such as switching to Code mode to make code changes. "
                "The user must approve the mode switch."
            ),
            input_schema=ToolInputSchema(
                type="object",
                properties={
                    "mode_slug": {
                        "type": "string",
                        "description": (
                            f"The slug of the mode to switch to (e.g., 'code', 'ask', 'architect'). "
                            f"Available modes: {', '.join(orchestrator.get_mode_names())}"
                        ),
                    },
                    "reason": {
                        "type": "string",
                        "description": "The reason for switching modes",
                    },
                },
                required=["mode_slug"],
            ),
        )

    async def execute(self, input_data: Dict[str, Any]) -> ToolResult:
        """
        Execute the mode switch.

        Args:
            input_data: Dictionary containing:
                - mode_slug: Slug of the mode to switch to
                - reason: Optional reason for the switch

        Returns:
            ToolResult with switch status
        """
        mode_slug = input_data.get("mode_slug")
        reason = input_data.get("reason", "")

        if not mode_slug:
            return ToolResult(
                tool_use_id=self.current_use_id or "unknown",
                content="mode_slug parameter is required",
                is_error=True
            )

        # Validate mode exists
        if not self.orchestrator.validate_mode_exists(mode_slug):
            available_modes = ", ".join(self.orchestrator.get_mode_names())
            return ToolResult(
                tool_use_id=self.current_use_id or "unknown",
                content=f"Invalid mode '{mode_slug}'. Available modes: {available_modes}",
                is_error=True
            )

        # Get current task
        current_task = self.orchestrator.current_task
        if not current_task:
            return ToolResult(
                tool_use_id=self.current_use_id or "unknown",
                content="No active task to switch mode for",
                is_error=True
            )

        # Get mode info
        old_mode = self.orchestrator.get_mode(current_task.mode_slug)
        new_mode = self.orchestrator.get_mode(mode_slug)

        # Perform the switch
        success = self.orchestrator.switch_mode(current_task, mode_slug)

        if success:
            message = f"Mode switched from {old_mode.name if old_mode else current_task.mode_slug} to {new_mode.name if new_mode else mode_slug}"
            if reason:
                message += f"\nReason: {reason}"
            
            return ToolResult(
                tool_use_id=self.current_use_id or "unknown",
                content=message,
                is_error=False
            )
        else:
            return ToolResult(
                tool_use_id=self.current_use_id or "unknown",
                content=f"Failed to switch to mode '{mode_slug}'",
                is_error=True
            )


class NewTaskTool(Tool):
    """
    Tool for creating a new subtask in a different mode.

    This allows the orchestrator mode (or other modes) to delegate work
    to specialized modes by creating child tasks.
    """

    def __init__(self, orchestrator: "ModeOrchestrator"):  # type: ignore
        """
        Initialize the new task tool.

        Args:
            orchestrator: ModeOrchestrator instance for task management
        """
        self.orchestrator = orchestrator
        super().__init__(
            name="new_task",
            description=(
                "This will let you create a new task instance in the chosen mode using your provided message. "
                "This is useful for delegating work to specialized modes."
            ),
            input_schema=ToolInputSchema(
                type="object",
                properties={
                    "mode": {
                        "type": "string",
                        "description": (
                            f"The slug of the mode to start the new task in (e.g., 'code', 'debug', 'architect'). "
                            f"Available modes: {', '.join(orchestrator.get_mode_names())}"
                        ),
                    },
                    "message": {
                        "type": "string",
                        "description": "The initial user message or instructions for this new task",
                    },
                },
                required=["mode", "message"],
            ),
        )

    async def execute(self, input_data: Dict[str, Any]) -> ToolResult:
        """
        Execute the new task creation.

        Args:
            input_data: Dictionary containing:
                - mode: Slug of the mode for the new task
                - message: Initial message for the task

        Returns:
            ToolResult with task info
        """
        mode_slug = input_data.get("mode")
        message = input_data.get("message")

        if not mode_slug:
            return ToolResult(
                tool_use_id=self.current_use_id or "unknown",
                content="mode parameter is required",
                is_error=True
            )

        if not message:
            return ToolResult(
                tool_use_id=self.current_use_id or "unknown",
                content="message parameter is required",
                is_error=True
            )

        # Validate mode exists
        if not self.orchestrator.validate_mode_exists(mode_slug):
            available_modes = ", ".join(self.orchestrator.get_mode_names())
            return ToolResult(
                tool_use_id=self.current_use_id or "unknown",
                content=f"Invalid mode '{mode_slug}'. Available modes: {available_modes}",
                is_error=True
            )

        # Get current task as parent
        parent_task = self.orchestrator.current_task

        try:
            # Create the new task
            new_task = self.orchestrator.create_task(
                mode_slug=mode_slug,
                initial_message=message,
                parent_task=parent_task,
            )

            mode = self.orchestrator.get_mode(mode_slug)
            result_message = f"Task created successfully in {mode.name if mode else mode_slug} mode (ID: {new_task.task_id}). The subtask will now begin execution."

            return ToolResult(
                tool_use_id=self.current_use_id or "unknown",
                content=result_message,
                is_error=False
            )

        except Exception as e:
            return ToolResult(
                tool_use_id=self.current_use_id or "unknown",
                content=f"Failed to create task: {str(e)}",
                is_error=True
            )


def create_mode_tools(orchestrator: "ModeOrchestrator") -> Dict[str, Tool]:  # type: ignore
    """
    Create mode tools for an orchestrator.

    Args:
        orchestrator: ModeOrchestrator instance

    Returns:
        Dictionary of tool name to tool instance
    """
    return {
        "switch_mode": SwitchModeTool(orchestrator),
        "new_task": NewTaskTool(orchestrator),
    }