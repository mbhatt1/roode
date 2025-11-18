"""
Mode-aware agent implementation.

This module provides a ModeAgent class that extends the base Agent
with mode awareness, tool restriction enforcement, and task management.
"""

from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from ..agent import Agent
from ..client import RooClient
from ..tools import Tool, ToolUse
from ..types import ApiHandlerCreateMessageMetadata, MessageParam
from .orchestrator import ModeOrchestrator
from .task import Task, TaskState
from .tools import create_mode_tools


class ModeAgent(Agent):
    """
    Mode-aware agent that enforces tool restrictions and manages tasks.

    This agent extends the base Agent class with mode capabilities:
    - Mode-based system prompt generation
    - Tool restriction enforcement based on mode configuration
    - Task lifecycle management
    - Mode switching and subtask creation
    - File editing restrictions

    Example:
        ```python
        from roo_code import RooClient, ProviderSettings
        from roo_code.modes import ModeAgent

        client = RooClient(
            provider_settings=ProviderSettings(
                api_provider="anthropic",
                api_key="your-key",
                api_model_id="claude-sonnet-4-5"
            )
        )

        agent = ModeAgent(
            client=client,
            mode_slug="code",  # Start in code mode
            project_root=Path.cwd()
        )

        result = await agent.run("Create a new Python file")
        print(result)
        ```
    """

    def __init__(
        self,
        client: RooClient,
        mode_slug: str = "code",
        tools: Optional[List[Tool]] = None,
        project_root: Optional[Path] = None,
        global_config_dir: Optional[Path] = None,
        max_iterations: int = 10,
        metadata: Optional[ApiHandlerCreateMessageMetadata] = None,
        load_builtin_tools: bool = True,
    ):
        """
        Initialize the mode-aware agent.

        Args:
            client: RooClient instance
            mode_slug: Initial mode slug (default: "code")
            tools: Additional tools to register (beyond mode and builtin tools)
            project_root: Root directory of the current project
            global_config_dir: Global configuration directory
            max_iterations: Maximum number of iterations
            metadata: Optional metadata for tracking
            load_builtin_tools: Whether to automatically load all builtin tools (default: True)
        """
        # Initialize orchestrator
        self.orchestrator = ModeOrchestrator(
            project_root=project_root,
            global_config_dir=global_config_dir,
        )

        # Validate mode exists
        if not self.orchestrator.validate_mode_exists(mode_slug):
            raise ValueError(
                f"Invalid mode '{mode_slug}'. Available modes: {', '.join(self.orchestrator.get_mode_names())}"
            )

        # Create initial task
        self.current_task = self.orchestrator.create_task(mode_slug)
        self.orchestrator.set_current_task(self.current_task)

        # Generate system prompt from mode
        system_prompt = self.orchestrator.get_system_prompt(self.current_task)

        # Use project root as cwd if available
        cwd = str(project_root) if project_root else "."

        # Initialize base agent with builtin tools
        super().__init__(
            client=client,
            tools=tools or [],
            system_prompt=system_prompt,
            max_iterations=max_iterations,
            metadata=metadata,
            cwd=cwd,
            load_builtin_tools=load_builtin_tools,
        )

        # Register mode tools (switch_mode, new_task)
        mode_tools = create_mode_tools(self.orchestrator)
        for tool in mode_tools.values():
            self.tool_registry.register(tool)

    def get_current_mode_slug(self) -> str:
        """Get the slug of the current mode."""
        return self.current_task.mode_slug

    def get_current_mode_name(self) -> str:
        """Get the display name of the current mode."""
        mode = self.orchestrator.get_mode(self.current_task.mode_slug)
        return mode.name if mode else self.current_task.mode_slug

    def switch_mode(self, new_mode_slug: str, reason: Optional[str] = None) -> bool:
        """
        Switch to a different mode.

        Args:
            new_mode_slug: Slug of the mode to switch to
            reason: Optional reason for the switch

        Returns:
            True if successful, False otherwise
        """
        success = self.orchestrator.switch_mode(self.current_task, new_mode_slug)

        if success:
            # Update system prompt
            self.system_prompt = self.orchestrator.get_system_prompt(self.current_task)

            # Add system message to conversation
            mode = self.orchestrator.get_mode(new_mode_slug)
            mode_name = mode.name if mode else new_mode_slug
            message = f"Switched to {mode_name} mode"
            if reason:
                message += f": {reason}"

            self.messages.append(MessageParam(role="system", content=message))

        return success

    def create_subtask(self, mode_slug: str, initial_message: str) -> Task:
        """
        Create a subtask in a different mode.

        Args:
            mode_slug: Mode for the subtask
            initial_message: Initial message for the subtask

        Returns:
            The created Task object
        """
        return self.orchestrator.create_task(
            mode_slug=mode_slug,
            initial_message=initial_message,
            parent_task=self.current_task,
        )

    def _validate_tool_use(self, tool_use: ToolUse) -> tuple[bool, Optional[str]]:
        """
        Validate if a tool can be used based on mode restrictions.

        Args:
            tool_use: The tool use to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Extract tool arguments
        tool_args = tool_use.input if hasattr(tool_use, "input") else None

        return self.orchestrator.validate_tool_use(
            self.current_task, tool_use.name, tool_args
        )

    async def run(
        self,
        task: str,
        on_iteration: Optional[Callable[[int, str], None]] = None,
    ) -> str:
        """
        Run the agent on a task with mode awareness.

        This overrides the base run method to add:
        - Tool restriction enforcement
        - Task state management
        - Mode-aware error handling

        Args:
            task: The task to accomplish
            on_iteration: Optional callback called after each iteration

        Returns:
            Final response from the agent
        """
        # Mark task as running
        self.current_task.mark_running()

        # Add initial user message to task
        self.current_task.add_user_message(task)

        try:
            # Run the base agent
            result = await super().run(task, on_iteration)

            # Mark task as completed
            self.current_task.mark_completed(result)

            return result

        except Exception as e:
            # Mark task as failed
            self.current_task.mark_failed(str(e))
            raise

    async def _execute_tool(self, tool_use: ToolUse) -> Any:
        """
        Execute a tool with mode restriction validation.

        Args:
            tool_use: The tool use to execute

        Returns:
            Tool execution result

        Raises:
            PermissionError: If tool use is not allowed in current mode
        """
        # Validate tool use against mode restrictions
        is_valid, error_message = self._validate_tool_use(tool_use)

        if not is_valid:
            raise PermissionError(error_message or "Tool use not allowed in current mode")

        # Execute the tool
        return await self.tool_registry.execute(tool_use)

    def get_available_tools(self) -> List[str]:
        """
        Get list of tools available in the current mode.

        Returns:
            List of tool names that can be used
        """
        all_tools = self.tool_registry.get_definitions()
        available = []

        for tool_def in all_tools:
            if self.orchestrator.can_use_tool(self.current_task, tool_def.name):
                available.append(tool_def.name)

        return available

    def get_mode_info(self) -> Dict[str, Any]:
        """
        Get information about the current mode.

        Returns:
            Dictionary with mode information
        """
        mode = self.orchestrator.get_mode(self.current_task.mode_slug)

        if not mode:
            return {
                "slug": self.current_task.mode_slug,
                "name": self.current_task.mode_slug,
                "groups": [],
            }

        return {
            "slug": mode.slug,
            "name": mode.name,
            "description": mode.description,
            "when_to_use": mode.when_to_use,
            "groups": [
                entry[0] if isinstance(entry, tuple) else entry for entry in mode.groups
            ],
            "source": mode.source.value,
        }

    def get_all_modes(self) -> List[Dict[str, Any]]:
        """
        Get information about all available modes.

        Returns:
            List of mode information dictionaries
        """
        modes = self.orchestrator.get_all_modes()
        return [
            {
                "slug": mode.slug,
                "name": mode.name,
                "description": mode.description,
                "when_to_use": mode.when_to_use,
                "source": mode.source.value,
            }
            for mode in modes
        ]

    def get_task_info(self) -> Dict[str, Any]:
        """
        Get information about the current task.

        Returns:
            Dictionary with task information
        """
        return {
            "task_id": self.current_task.task_id,
            "mode_slug": self.current_task.mode_slug,
            "state": self.current_task.state.value,
            "message_count": len(self.current_task.messages),
            "parent_task_id": self.current_task.parent_task_id,
            "child_task_ids": self.current_task.child_task_ids,
        }

    def reload_modes(self) -> None:
        """
        Reload mode configurations from files.

        This is useful when mode configurations have been updated.
        """
        self.orchestrator.reload_modes()

        # Update system prompt if current mode was reloaded
        self.system_prompt = self.orchestrator.get_system_prompt(self.current_task)