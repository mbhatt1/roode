"""Context for tool execution with rich integration capabilities."""

from typing import Any, Awaitable, Callable, Dict, List, Optional
from pydantic import BaseModel, Field
from .modes import ModeConfig
from .file_watcher import AsyncFileWatcher


class ToolContext(BaseModel):
    """Rich execution context for tools with callbacks and state management.
    
    This class provides tools with access to:
    - Current working directory
    - User interaction callbacks (approval, error handling)
    - Result streaming for real-time updates
    - Workspace configuration
    - Mode-based file restrictions
    - File change tracking
    - State checkpointing
    
    The context enables tools to operate with the same rich integration
    as the TypeScript implementation, including approval flows, real-time
    feedback, and state management.
    
    Example:
        >>> async def ask_approval(changes: Dict[str, Any]) -> bool:
        ...     print(f"Approve changes? {changes}")
        ...     return True
        >>> 
        >>> async def push_result(message: str) -> None:
        ...     print(f"Result: {message}")
        >>> 
        >>> context = ToolContext(
        ...     cwd="/workspace",
        ...     ask_approval=ask_approval,
        ...     push_result=push_result
        ... )
        >>> 
        >>> # Use in tool execution
        >>> approved = await context.ask_approval({"action": "write_file"})
        >>> if approved:
        ...     await context.push_result("File written successfully")
    """
    
    # Core settings
    cwd: str = Field(
        description="Current working directory for tool operations"
    )
    
    # Callbacks for user interaction
    ask_approval: Optional[Callable[[Dict[str, Any]], Awaitable[bool]]] = Field(
        default=None,
        description="Callback to request user approval for operations"
    )
    
    handle_error: Optional[Callable[[Exception], Awaitable[None]]] = Field(
        default=None,
        description="Callback to handle and report errors"
    )
    
    push_result: Optional[Callable[[str], Awaitable[None]]] = Field(
        default=None,
        description="Callback to stream results/progress to the user"
    )
    
    # Configuration and state
    workspace_config: Dict[str, Any] = Field(
        default_factory=dict,
        description="Workspace-specific configuration"
    )
    
    mode: Optional[ModeConfig] = Field(
        default=None,
        description="Current mode with file editing restrictions"
    )
    
    file_watcher: Optional[AsyncFileWatcher] = Field(
        default=None,
        description="File watcher for tracking changes"
    )
    
    # State management
    checkpoint_data: Dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary checkpoint data for state management"
    )
    
    # Additional metadata
    task_id: Optional[str] = Field(
        default=None,
        description="ID of the current task for tracking"
    )
    
    user_id: Optional[str] = Field(
        default=None,
        description="ID of the user executing the task"
    )
    
    class Config:
        arbitrary_types_allowed = True
    
    async def request_approval(
        self,
        action: str,
        details: Optional[Dict[str, Any]] = None,
        default_approved: bool = True
    ) -> bool:
        """Request user approval for an action.
        
        If no approval callback is configured, returns the default value.
        
        Args:
            action: Description of the action requiring approval
            details: Additional details about the action
            default_approved: Value to return if no callback is configured (default True)
            
        Returns:
            True if approved, False otherwise
        """
        if self.ask_approval is None:
            return default_approved
        
        approval_data = {
            "action": action,
            "details": details or {},
            "task_id": self.task_id
        }
        
        try:
            return await self.ask_approval(approval_data)
        except Exception as e:
            # If approval callback fails, handle the error and deny by default
            if self.handle_error:
                await self.handle_error(e)
            return False
    
    async def report_error(self, error: Exception) -> None:
        """Report an error through the error handler callback.
        
        Args:
            error: The exception to report
        """
        if self.handle_error:
            try:
                await self.handle_error(error)
            except Exception as e:
                # If error handler itself fails, print to stderr
                print(f"Error in error handler: {e}", file=__import__('sys').stderr)
    
    async def stream_result(self, message: str) -> None:
        """Stream a result message to the user.
        
        Args:
            message: Message to stream
        """
        if self.push_result:
            try:
                await self.push_result(message)
            except Exception as e:
                # If streaming fails, print to stdout as fallback
                print(f"Stream error: {e} | Message: {message}")
    
    def check_file_edit_allowed(self, file_path: str) -> None:
        """Check if editing a file is allowed in the current mode.
        
        Args:
            file_path: Path to the file to check
            
        Raises:
            FileRestrictionError: If the file cannot be edited in the current mode
        """
        if self.mode:
            self.mode.check_file_edit(file_path)
    
    def is_file_edit_allowed(self, file_path: str) -> bool:
        """Check if editing a file is allowed in the current mode.
        
        Args:
            file_path: Path to the file to check
            
        Returns:
            True if the file can be edited, False otherwise
        """
        if self.mode:
            return self.mode.allows_file_edit(file_path)
        return True
    
    async def track_file_change(
        self,
        file_path: str,
        change_type: str,
        tool_name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Track a file change through the file watcher.
        
        Args:
            file_path: Path to the file that changed
            change_type: Type of change ("created", "modified", "deleted")
            tool_name: Name of the tool that made the change
            metadata: Additional metadata about the change
        """
        if self.file_watcher:
            from .file_watcher import FileChangeType
            change_type_enum = FileChangeType(change_type)
            await self.file_watcher.record_change_async(
                file_path,
                change_type_enum,
                tool_name=tool_name,
                metadata=metadata
            )
    
    def create_checkpoint(self, key: str, data: Any) -> None:
        """Create a checkpoint with arbitrary data.
        
        Args:
            key: Key to identify the checkpoint
            data: Data to store in the checkpoint
        """
        self.checkpoint_data[key] = data
    
    def restore_checkpoint(self, key: str) -> Optional[Any]:
        """Restore data from a checkpoint.
        
        Args:
            key: Key identifying the checkpoint
            
        Returns:
            The checkpoint data if found, None otherwise
        """
        return self.checkpoint_data.get(key)
    
    def clear_checkpoints(self) -> None:
        """Clear all checkpoint data."""
        self.checkpoint_data.clear()
    
    def get_config_value(self, key: str, default: Any = None) -> Any:
        """Get a value from workspace configuration.
        
        Args:
            key: Configuration key (supports dot notation, e.g., "editor.fontSize")
            default: Default value if key is not found
            
        Returns:
            The configuration value or default
        """
        keys = key.split('.')
        value = self.workspace_config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def set_config_value(self, key: str, value: Any) -> None:
        """Set a value in workspace configuration.
        
        Args:
            key: Configuration key (supports dot notation, e.g., "editor.fontSize")
            value: Value to set
        """
        keys = key.split('.')
        config = self.workspace_config
        
        # Navigate to the parent of the target key
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        # Set the final key
        config[keys[-1]] = value
    
    @classmethod
    def create_minimal(cls, cwd: str = ".") -> "ToolContext":
        """Create a minimal context with no callbacks.
        
        Useful for testing or simple use cases where user interaction
        is not needed.
        
        Args:
            cwd: Current working directory
            
        Returns:
            A minimal ToolContext instance
        """
        return cls(cwd=cwd)
    
    @classmethod
    def create_with_mode(cls, cwd: str, mode: ModeConfig) -> "ToolContext":
        """Create a context with a specific mode.
        
        Args:
            cwd: Current working directory
            mode: Mode configuration
            
        Returns:
            A ToolContext with the specified mode
        """
        return cls(cwd=cwd, mode=mode)
    
    @classmethod
    def create_full(
        cls,
        cwd: str,
        ask_approval: Callable[[Dict[str, Any]], Awaitable[bool]],
        push_result: Callable[[str], Awaitable[None]],
        handle_error: Optional[Callable[[Exception], Awaitable[None]]] = None,
        mode: Optional[ModeConfig] = None,
        workspace_config: Optional[Dict[str, Any]] = None,
        task_id: Optional[str] = None
    ) -> "ToolContext":
        """Create a fully configured context.
        
        Args:
            cwd: Current working directory
            ask_approval: Approval callback
            push_result: Result streaming callback
            handle_error: Error handling callback (optional)
            mode: Mode configuration (optional)
            workspace_config: Workspace configuration (optional)
            task_id: Task ID (optional)
            
        Returns:
            A fully configured ToolContext
        """
        return cls(
            cwd=cwd,
            ask_approval=ask_approval,
            push_result=push_result,
            handle_error=handle_error,
            mode=mode,
            workspace_config=workspace_config or {},
            file_watcher=AsyncFileWatcher(workspace_root=cwd),
            task_id=task_id
        )