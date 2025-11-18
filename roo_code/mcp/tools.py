"""
MCP tool handlers for mode operations.

This module handles MCP tool operations, providing tools for task management,
mode switching, and validation.
"""

import logging
from typing import Any, Dict, List

from ..modes.orchestrator import ModeOrchestrator
from ..modes.task import TaskState
from .session import SessionManager
from .validation import SchemaValidator, ValidationError

logger = logging.getLogger(__name__)


class ToolHandler:
    """Handles MCP tool operations for modes."""
    
    def __init__(
        self,
        session_manager: SessionManager,
        orchestrator: ModeOrchestrator
    ):
        """
        Initialize tool handler.
        
        Args:
            session_manager: Session manager for task tracking
            orchestrator: Mode orchestrator for mode operations
        """
        self.session_manager = session_manager
        self.orchestrator = orchestrator
        
        # Register tool implementations
        self.tools = {
            "list_modes": self._list_modes,
            "get_mode_info": self._get_mode_info,
            "create_task": self._create_task,
            "switch_mode": self._switch_mode,
            "get_task_info": self._get_task_info,
            "validate_tool_use": self._validate_tool_use,
            "complete_task": self._complete_task,
        }
    
    async def list_tools(self) -> List[Dict[str, Any]]:
        """
        Return list of available tools with their schemas.
        
        Returns:
            List of tool definitions in MCP format
        """
        return [
            {
                "name": "list_modes",
                "description": "List all available modes with their metadata",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "source": {
                            "type": "string",
                            "enum": ["builtin", "global", "project", "all"],
                            "description": "Filter modes by source (default: all)"
                        }
                    }
                }
            },
            {
                "name": "get_mode_info",
                "description": "Get detailed information about a specific mode",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "mode_slug": {
                            "type": "string",
                            "description": "Slug of the mode to get info for"
                        },
                        "include_system_prompt": {
                            "type": "boolean",
                            "description": "Include the full system prompt (default: false)"
                        }
                    },
                    "required": ["mode_slug"]
                }
            },
            {
                "name": "create_task",
                "description": "Create a new task in a specific mode",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "mode_slug": {
                            "type": "string",
                            "description": "Mode to use for this task"
                        },
                        "initial_message": {
                            "type": "string",
                            "description": "Initial user message for the task"
                        },
                        "parent_session_id": {
                            "type": "string",
                            "description": "Parent session ID if this is a subtask"
                        }
                    },
                    "required": ["mode_slug"]
                }
            },
            {
                "name": "switch_mode",
                "description": "Switch a task to a different mode",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "session_id": {
                            "type": "string",
                            "description": "Session ID of the task"
                        },
                        "new_mode_slug": {
                            "type": "string",
                            "description": "Slug of the mode to switch to"
                        },
                        "reason": {
                            "type": "string",
                            "description": "Reason for switching modes (optional)"
                        }
                    },
                    "required": ["session_id", "new_mode_slug"]
                }
            },
            {
                "name": "get_task_info",
                "description": "Get information about a task/session",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "session_id": {
                            "type": "string",
                            "description": "Session ID"
                        },
                        "include_messages": {
                            "type": "boolean",
                            "description": "Include conversation history (default: false)"
                        },
                        "include_hierarchy": {
                            "type": "boolean",
                            "description": "Include parent/child task info (default: false)"
                        }
                    },
                    "required": ["session_id"]
                }
            },
            {
                "name": "validate_tool_use",
                "description": "Check if a tool can be used in the current mode",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "session_id": {
                            "type": "string",
                            "description": "Session ID"
                        },
                        "tool_name": {
                            "type": "string",
                            "description": "Name of the tool to validate"
                        },
                        "file_path": {
                            "type": "string",
                            "description": "File path (for edit operations)"
                        }
                    },
                    "required": ["session_id", "tool_name"]
                }
            },
            {
                "name": "complete_task",
                "description": "Mark a task as completed or failed",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "session_id": {
                            "type": "string",
                            "description": "Session ID"
                        },
                        "status": {
                            "type": "string",
                            "enum": ["completed", "failed", "cancelled"],
                            "description": "Final status of the task"
                        },
                        "result": {
                            "type": "string",
                            "description": "Completion result or error message"
                        }
                    },
                    "required": ["session_id", "status"]
                }
            }
        ]
    
    async def call_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute a tool.
        
        Args:
            tool_name: Name of tool to execute
            arguments: Tool arguments
            
        Returns:
            Tool result in MCP format
            
        Raises:
            ValidationError: If tool not found or validation fails
        """
        if tool_name not in self.tools:
            available = ', '.join(self.tools.keys())
            raise ValidationError(
                f"Unknown tool: {tool_name}. Available tools: {available}"
            )
        
        tool_func = self.tools[tool_name]
        result = await tool_func(arguments)
        
        logger.debug(f"Tool '{tool_name}' executed successfully")
        return result
    
    async def _list_modes(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Implementation of list_modes tool."""
        source_filter = args.get("source", "all")
        modes = self.orchestrator.get_all_modes()
        
        # Filter by source if requested
        if source_filter != "all":
            modes = [m for m in modes if m.source.value == source_filter]
        
        # Format output
        lines = ["Available modes:\n"]
        for i, mode in enumerate(modes, 1):
            lines.append(f"{i}. {mode.slug} ({mode.name}) - {mode.source.value}")
            if mode.description:
                lines.append(f"   Description: {mode.description}")
            
            # Tool groups summary
            groups = []
            for entry in mode.groups:
                if isinstance(entry, tuple):
                    group_name, options = entry
                    if options.file_regex:
                        groups.append(f"{group_name} ({options.file_regex})")
                    else:
                        groups.append(group_name)
                else:
                    groups.append(entry)
            lines.append(f"   Tool groups: {', '.join(groups)}")
            lines.append("")
        
        return {
            "content": [
                {
                    "type": "text",
                    "text": "\n".join(lines)
                }
            ]
        }
    
    async def _get_mode_info(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Implementation of get_mode_info tool."""
        mode_slug = args["mode_slug"]
        include_system_prompt = args.get("include_system_prompt", False)
        
        # Validate and get mode
        SchemaValidator.validate_mode_slug(mode_slug)
        mode = self.orchestrator.get_mode(mode_slug)
        if not mode:
            available = ', '.join(self.orchestrator.get_mode_names())
            raise ValidationError(
                f"Mode not found: {mode_slug}. Available: {available}"
            )
        
        # Build info text
        lines = [
            f"Mode: {mode.name} ({mode.slug})",
            f"Source: {mode.source.value}",
        ]
        
        if mode.description:
            lines.append(f"Description: {mode.description}")
        
        if mode.when_to_use:
            lines.append(f"\nWhen to use:")
            lines.append(mode.when_to_use)
        
        # Tool groups
        lines.append("\nTool Groups:")
        for group in ["read", "edit", "browser", "command", "mcp", "modes"]:
            enabled = mode.is_tool_group_enabled(group)
            status = "✓" if enabled else "✗"
            line = f"{status} {group}"
            
            if enabled:
                options = mode.get_group_options(group)
                if options and options.file_regex:
                    line += f" (restricted to: {options.file_regex})"
                if options and options.description:
                    line += f" - {options.description}"
            
            lines.append(line)
        
        if mode.custom_instructions:
            lines.append(f"\nCustom Instructions:")
            lines.append(mode.custom_instructions)
        
        # Optionally include system prompt
        if include_system_prompt:
            from ..modes.task import Task
            temp_task = Task(mode_slug=mode_slug)
            system_prompt = self.orchestrator.get_system_prompt(temp_task)
            lines.append(f"\nSystem Prompt:")
            lines.append(system_prompt)
        
        return {
            "content": [
                {
                    "type": "text",
                    "text": "\n".join(lines)
                }
            ]
        }
    
    async def _create_task(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Implementation of create_task tool."""
        mode_slug = args["mode_slug"]
        initial_message = args.get("initial_message")
        parent_session_id = args.get("parent_session_id")
        
        # Validate mode exists
        SchemaValidator.validate_mode_slug(mode_slug)
        if not self.orchestrator.validate_mode_exists(mode_slug):
            available = ', '.join(self.orchestrator.get_mode_names())
            raise ValidationError(
                f"Invalid mode '{mode_slug}'. Available: {available}"
            )
        
        # Get parent task if specified
        parent_task = None
        if parent_session_id:
            SchemaValidator.validate_session_id(parent_session_id)
            parent_session = self.session_manager.get_session(parent_session_id)
            if not parent_session:
                raise ValidationError(f"Parent session not found: {parent_session_id}")
            parent_task = parent_session.task
        
        # Create task
        task = self.orchestrator.create_task(
            mode_slug=mode_slug,
            initial_message=initial_message,
            parent_task=parent_task
        )
        
        # Create session
        session = self.session_manager.create_session(task)
        
        # Format response
        mode = self.orchestrator.get_mode(mode_slug)
        text = (
            f"Task created successfully\n\n"
            f"Session ID: {session.session_id}\n"
            f"Task ID: {task.task_id}\n"
            f"Mode: {mode_slug} ({mode.name if mode else 'Unknown'})\n"
            f"State: {task.state.value}\n\n"
            f"Use this session_id for subsequent operations."
        )
        
        return {
            "content": [{"type": "text", "text": text}],
            "metadata": {
                "session_id": session.session_id,
                "task_id": task.task_id,
                "mode_slug": mode_slug
            }
        }
    
    async def _switch_mode(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Implementation of switch_mode tool."""
        session_id = args["session_id"]
        new_mode_slug = args["new_mode_slug"]
        reason = args.get("reason")
        
        # Validate inputs
        SchemaValidator.validate_session_id(session_id)
        SchemaValidator.validate_mode_slug(new_mode_slug)
        
        # Get session
        session = self.session_manager.get_session(session_id)
        if not session:
            raise ValidationError(f"Session not found: {session_id}")
        
        task = session.task
        old_mode_slug = task.mode_slug
        
        # Validate new mode
        if not self.orchestrator.validate_mode_exists(new_mode_slug):
            available = ', '.join(self.orchestrator.get_mode_names())
            raise ValidationError(
                f"Invalid mode: {new_mode_slug}. Available: {available}"
            )
        
        # Switch mode
        success = self.orchestrator.switch_mode(task, new_mode_slug)
        if not success:
            raise ValidationError(f"Failed to switch to mode: {new_mode_slug}")
        
        # Add reason to task metadata if provided
        if reason:
            task.metadata["mode_switch_reason"] = reason
        
        # Format response
        new_mode = self.orchestrator.get_mode(new_mode_slug)
        text = (
            f"Mode switched successfully\n\n"
            f"Session: {session_id}\n"
            f"Old mode: {old_mode_slug}\n"
            f"New mode: {new_mode_slug}\n"
        )
        
        if reason:
            text += f"Reason: {reason}\n"
        
        if new_mode:
            text += f"\nNew tool groups:\n"
            for group in ["read", "edit", "browser", "command", "mcp", "modes"]:
                enabled = new_mode.is_tool_group_enabled(group)
                status = "✓" if enabled else "✗"
                text += f"{status} {group}"
                
                if not enabled:
                    text += " (not available)"
                else:
                    options = new_mode.get_group_options(group)
                    if options and options.file_regex:
                        text += f" (restricted to: {options.file_regex})"
                
                text += "\n"
        
        return {
            "content": [{"type": "text", "text": text}],
            "metadata": {
                "old_mode": old_mode_slug,
                "new_mode": new_mode_slug
            }
        }
    
    async def _get_task_info(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Implementation of get_task_info tool."""
        session_id = args["session_id"]
        include_messages = args.get("include_messages", False)
        include_hierarchy = args.get("include_hierarchy", False)
        
        # Validate and get session
        SchemaValidator.validate_session_id(session_id)
        session = self.session_manager.get_session(session_id)
        if not session:
            raise ValidationError(f"Session not found: {session_id}")
        
        task = session.task
        mode = self.orchestrator.get_mode(task.mode_slug)
        
        # Build info
        lines = [
            f"Task Information\n",
            f"Session ID: {session.session_id}",
            f"Task ID: {task.task_id}",
            f"Mode: {task.mode_slug} ({mode.name if mode else 'Unknown'})",
            f"State: {task.state.value}",
            f"Created: {task.created_at.isoformat()}",
        ]
        
        if task.completed_at:
            lines.append(f"Completed: {task.completed_at.isoformat()}")
        
        lines.append(f"\nSession Age: {session.get_age_seconds():.0f}s")
        lines.append(f"Idle Time: {session.get_idle_seconds():.0f}s")
        
        # Hierarchy info
        if include_hierarchy:
            lines.append(f"\nHierarchy:")
            if task.parent_task_id:
                lines.append(f"  Parent Task: {task.parent_task_id}")
            if task.child_task_ids:
                lines.append(f"  Child Tasks: {', '.join(task.child_task_ids)}")
        
        # Messages
        if include_messages:
            lines.append(f"\nConversation History ({len(task.messages)} messages):")
            for i, msg in enumerate(task.messages, 1):
                lines.append(f"\n{i}. [{msg.role}] {msg.timestamp.isoformat()}")
                content_preview = str(msg.content)[:100]
                if len(str(msg.content)) > 100:
                    content_preview += "..."
                lines.append(f"   {content_preview}")
        
        return {
            "content": [{"type": "text", "text": "\n".join(lines)}],
            "metadata": {
                "session_id": session.session_id,
                "task_id": task.task_id,
                "mode": task.mode_slug,
                "state": task.state.value,
                "message_count": len(task.messages)
            }
        }
    
    async def _validate_tool_use(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Implementation of validate_tool_use tool."""
        session_id = args["session_id"]
        tool_name = args["tool_name"]
        file_path = args.get("file_path")
        
        # Validate and get session
        SchemaValidator.validate_session_id(session_id)
        session = self.session_manager.get_session(session_id)
        if not session:
            raise ValidationError(f"Session not found: {session_id}")
        
        task = session.task
        mode = self.orchestrator.get_mode(task.mode_slug)
        
        # Build tool args for validation
        tool_args = {}
        if file_path:
            tool_args["path"] = file_path
        
        # Validate
        is_valid, error_message = self.orchestrator.validate_tool_use(
            task,
            tool_name,
            tool_args
        )
        
        # Format response
        mode_name = mode.name if mode else task.mode_slug
        
        if is_valid:
            text = f"✓ Tool '{tool_name}' is allowed in mode '{mode_name}'"
            if file_path:
                text += f" for file '{file_path}'"
        else:
            text = f"✗ {error_message}"
        
        return {
            "content": [{"type": "text", "text": text}],
            "metadata": {
                "allowed": is_valid,
                "tool_name": tool_name,
                "mode": task.mode_slug,
                "error": error_message if not is_valid else None
            }
        }
    
    async def _complete_task(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Implementation of complete_task tool."""
        session_id = args["session_id"]
        status = args["status"]
        result = args.get("result")
        
        # Validate inputs
        SchemaValidator.validate_session_id(session_id)
        
        # Get session
        session = self.session_manager.get_session(session_id)
        if not session:
            raise ValidationError(f"Session not found: {session_id}")
        
        task = session.task
        
        # Update task state
        if status == "completed":
            task.mark_completed()
        elif status == "failed":
            task.mark_failed()
        elif status == "cancelled":
            task.mark_cancelled()
        
        # Store result if provided
        if result:
            task.metadata["completion_result"] = result
        
        # Format response
        text = (
            f"Task {status}\n\n"
            f"Session ID: {session_id}\n"
            f"Task ID: {task.task_id}\n"
            f"Final State: {task.state.value}\n"
        )
        
        if task.completed_at:
            text += f"Completed At: {task.completed_at.isoformat()}\n"
        
        if result:
            text += f"\nResult:\n{result}"
        
        return {
            "content": [{"type": "text", "text": text}],
            "metadata": {
                "session_id": session_id,
                "task_id": task.task_id,
                "status": task.state.value
            }
        }