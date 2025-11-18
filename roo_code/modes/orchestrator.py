"""
Mode orchestration and coordination.

This module provides the ModeOrchestrator class which manages mode execution,
task coordination, and mode switching.
"""

from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .builtin_modes import BUILTIN_MODES
from .config import ModeConfig, ModeConfigLoader
from .task import Task, TaskState


class ModeOrchestrator:
    """
    Orchestrates mode-based task execution.

    The ModeOrchestrator manages:
    - Loading and caching mode configurations
    - Task lifecycle management
    - Mode switching and validation
    - Tool restriction enforcement
    - Parent-child task relationships
    """

    def __init__(
        self,
        project_root: Optional[Path] = None,
        global_config_dir: Optional[Path] = None,
    ):
        """
        Initialize the orchestrator.

        Args:
            project_root: Root directory of the current project
            global_config_dir: Global configuration directory (defaults to ~/.roo-code)
        """
        self.project_root = project_root
        self.loader = ModeConfigLoader(global_config_dir)

        # Load all modes (builtin + global + project)
        self.modes: Dict[str, ModeConfig] = {}
        self._load_all_modes()

        # Task management
        self.tasks: Dict[str, Task] = {}
        self.current_task: Optional[Task] = None

    def _load_all_modes(self) -> None:
        """Load all modes from all sources and cache them."""
        all_modes = self.loader.load_all_modes(
            project_root=self.project_root,
            builtin_modes=BUILTIN_MODES,
        )
        self.modes = {mode.slug: mode for mode in all_modes}

    def reload_modes(self) -> None:
        """Reload modes from configuration files."""
        self._load_all_modes()

    def get_mode(self, slug: str) -> Optional[ModeConfig]:
        """
        Get a mode configuration by slug.

        Args:
            slug: Mode slug to look up

        Returns:
            ModeConfig if found, None otherwise
        """
        return self.modes.get(slug)

    def get_all_modes(self) -> List[ModeConfig]:
        """Get all available modes."""
        return list(self.modes.values())

    def get_mode_names(self) -> List[str]:
        """Get slugs of all available modes."""
        return list(self.modes.keys())

    def validate_mode_exists(self, slug: str) -> bool:
        """Check if a mode exists."""
        return slug in self.modes

    def create_task(
        self,
        mode_slug: str,
        initial_message: Optional[str] = None,
        parent_task: Optional[Task] = None,
    ) -> Task:
        """
        Create a new task in the specified mode.

        Args:
            mode_slug: Slug of the mode for this task
            initial_message: Optional initial user message
            parent_task: Optional parent task if this is a subtask

        Returns:
            The created Task object

        Raises:
            ValueError: If mode_slug doesn't exist
        """
        if not self.validate_mode_exists(mode_slug):
            raise ValueError(
                f"Invalid mode '{mode_slug}'. Available modes: {', '.join(self.get_mode_names())}"
            )

        task = Task(
            mode_slug=mode_slug,
            parent_task_id=parent_task.task_id if parent_task else None,
        )

        if initial_message:
            task.add_user_message(initial_message)

        # Register task
        self.tasks[task.task_id] = task

        # Update parent if provided
        if parent_task:
            parent_task.child_task_ids.append(task.task_id)

        return task

    def get_task(self, task_id: str) -> Optional[Task]:
        """Get a task by ID."""
        return self.tasks.get(task_id)

    def set_current_task(self, task: Task) -> None:
        """Set the current active task."""
        self.current_task = task

    def switch_mode(self, task: Task, new_mode_slug: str) -> bool:
        """
        Switch a task to a different mode.

        Args:
            task: Task to switch
            new_mode_slug: Slug of the mode to switch to

        Returns:
            True if successful, False if mode doesn't exist

        This updates the task's mode and adds a system message documenting the switch.
        """
        if not self.validate_mode_exists(new_mode_slug):
            return False

        task.switch_mode(new_mode_slug)
        return True

    def can_use_tool(self, task: Task, tool_name: str) -> bool:
        """
        Check if a tool can be used in the current mode.

        Args:
            task: The task to check
            tool_name: Name of the tool

        Returns:
            True if the tool is allowed in the current mode

        This enforces tool group restrictions based on the mode configuration.
        """
        mode = self.get_mode(task.mode_slug)
        if not mode:
            return True  # If mode not found, allow by default

        # Map tools to their groups
        tool_to_group = {
            # Read group
            "read_file": "read",
            "list_files": "read",
            "list_code_definition_names": "read",
            "search_files": "read",
            # Edit group
            "write_to_file": "edit",
            "apply_diff": "edit",
            "insert_content": "edit",
            # Browser group
            "browser_action": "browser",
            # Command group
            "execute_command": "command",
            # MCP group
            "use_mcp_tool": "mcp",
            "access_mcp_resource": "mcp",
            # Mode group (always allowed for mode switching)
            "switch_mode": "modes",
            "new_task": "modes",
            # Always allowed
            "ask_followup_question": None,
            "attempt_completion": None,
            "update_todo_list": None,
        }

        tool_group = tool_to_group.get(tool_name)

        # Tools without a group are always allowed
        if tool_group is None:
            return True

        # Check if the mode enables this tool group
        return mode.is_tool_group_enabled(tool_group)

    def can_edit_file(self, task: Task, file_path: str) -> bool:
        """
        Check if a file can be edited based on mode restrictions.

        Args:
            task: The task to check
            file_path: Path to the file

        Returns:
            True if the file can be edited in the current mode
        """
        mode = self.get_mode(task.mode_slug)
        if not mode:
            return True  # If mode not found, allow by default

        return mode.can_edit_file(file_path)

    def validate_tool_use(
        self,
        task: Task,
        tool_name: str,
        tool_args: Optional[Dict[str, Any]] = None,
    ) -> tuple[bool, Optional[str]]:
        """
        Validate if a tool can be used with the given arguments.

        Args:
            task: The task attempting to use the tool
            tool_name: Name of the tool
            tool_args: Arguments for the tool

        Returns:
            Tuple of (is_valid, error_message)
            is_valid is True if tool use is allowed, False otherwise
            error_message is None if valid, or a string describing the restriction
        """
        # Check if tool is allowed in current mode
        if not self.can_use_tool(task, tool_name):
            mode = self.get_mode(task.mode_slug)
            return (
                False,
                f"Tool '{tool_name}' is not available in mode '{mode.name if mode else task.mode_slug}'",
            )

        # For edit operations, check file restrictions
        if tool_name in ["write_to_file", "apply_diff", "insert_content"]:
            if tool_args and "path" in tool_args:
                file_path = tool_args["path"]
                if not self.can_edit_file(task, file_path):
                    mode = self.get_mode(task.mode_slug)
                    edit_options = mode.get_group_options("edit") if mode else None
                    restriction = (
                        edit_options.file_regex if edit_options and edit_options.file_regex else "unknown"
                    )
                    return (
                        False,
                        f"Cannot edit file '{file_path}' in mode '{mode.name if mode else task.mode_slug}'. "
                        f"File must match pattern: {restriction}",
                    )

        return (True, None)

    def get_system_prompt(self, task: Task) -> str:
        """
        Generate the system prompt for a task based on its mode.

        Args:
            task: The task to generate prompt for

        Returns:
            System prompt string
        """
        mode = self.get_mode(task.mode_slug)
        if not mode:
            return "You are a helpful AI assistant."

        parts = [mode.role_definition]

        if mode.custom_instructions:
            parts.append("\n\n## Mode Instructions\n\n" + mode.custom_instructions)

        if mode.when_to_use:
            parts.append("\n\n## When to Use This Mode\n\n" + mode.when_to_use)

        # Add available tool groups info
        if mode.groups:
            group_names = []
            for entry in mode.groups:
                if isinstance(entry, tuple):
                    group_name, options = entry
                    if options.file_regex:
                        group_names.append(f"{group_name} (restricted to: {options.file_regex})")
                    else:
                        group_names.append(group_name)
                else:
                    group_names.append(entry)

            parts.append("\n\n## Available Tool Groups\n\n" + ", ".join(group_names))

        return "".join(parts)

    def complete_task(
        self,
        task: Task,
        result: Optional[str] = None,
        error: Optional[str] = None,
    ) -> None:
        """
        Mark a task as completed or failed.

        Args:
            task: Task to complete
            result: Optional completion result
            error: Optional error message (if failed)
        """
        if error:
            task.mark_failed(error)
        else:
            task.mark_completed(result)

        # If this was the current task, clear it
        if self.current_task and self.current_task.task_id == task.task_id:
            self.current_task = None

    def get_task_hierarchy(self, task: Task) -> Dict[str, Any]:
        """
        Get the full hierarchy for a task (parent and children).

        Args:
            task: Task to get hierarchy for

        Returns:
            Dictionary with parent and children information
        """
        hierarchy = {
            "task": task,
            "parent": None,
            "children": [],
        }

        # Get parent
        if task.parent_task_id:
            hierarchy["parent"] = self.get_task(task.parent_task_id)

        # Get children
        for child_id in task.child_task_ids:
            child = self.get_task(child_id)
            if child:
                hierarchy["children"].append(child)

        return hierarchy