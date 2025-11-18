"""File watching for tracking changes during tool execution."""

import asyncio
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional, Set
from pydantic import BaseModel, Field


class FileChangeType(str, Enum):
    """Types of file changes that can be tracked."""
    CREATED = "created"
    MODIFIED = "modified"
    DELETED = "deleted"


class FileChange(BaseModel):
    """Represents a single file change event.
    
    Attributes:
        path: Path to the file that changed (relative to workspace)
        change_type: Type of change (created, modified, deleted)
        timestamp: When the change occurred
        tool_name: Name of the tool that made the change
        metadata: Additional metadata about the change
    """
    
    path: str = Field(description="Path to the changed file")
    change_type: FileChangeType = Field(description="Type of file change")
    timestamp: datetime = Field(default_factory=datetime.now, description="When the change occurred")
    tool_name: Optional[str] = Field(default=None, description="Tool that made the change")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class FileWatcher:
    """Tracks file changes during tool execution.
    
    This class monitors file system changes made by tools, providing:
    - Change history for rollback/checkpoint support
    - Callbacks for real-time change notifications
    - Statistics on file operations
    
    Note: This is a lightweight tracker that records changes explicitly reported
    by tools, rather than using OS-level file system watching (like watchdog).
    For production use, consider integrating with watchdog for automatic detection.
    
    Example:
        >>> watcher = FileWatcher(workspace_root="/workspace")
        >>> watcher.on_change(lambda change: print(f"File changed: {change.path}"))
        >>> watcher.record_change("src/main.py", FileChangeType.MODIFIED, tool_name="write_to_file")
        >>> changes = watcher.get_changes()
        >>> len(changes)
        1
    """
    
    def __init__(self, workspace_root: str = "."):
        """Initialize the file watcher.
        
        Args:
            workspace_root: Root directory to watch (for path resolution)
        """
        self.workspace_root = Path(workspace_root).resolve()
        self._changes: List[FileChange] = []
        self._callbacks: List[Callable[[FileChange], None]] = []
        self._watching = False
    
    def record_change(
        self,
        file_path: str,
        change_type: FileChangeType,
        tool_name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> FileChange:
        """Record a file change.
        
        Args:
            file_path: Path to the file (relative to workspace)
            change_type: Type of change that occurred
            tool_name: Name of the tool that made the change
            metadata: Additional metadata about the change
            
        Returns:
            The created FileChange object
        """
        change = FileChange(
            path=file_path,
            change_type=change_type,
            tool_name=tool_name,
            metadata=metadata or {}
        )
        self._changes.append(change)
        
        # Notify callbacks
        for callback in self._callbacks:
            try:
                callback(change)
            except Exception as e:
                # Don't let callback errors break the watcher
                print(f"Error in file watcher callback: {e}")
        
        return change
    
    def on_change(self, callback: Callable[[FileChange], None]) -> None:
        """Register a callback to be called when files change.
        
        Args:
            callback: Function to call with FileChange when a change occurs
        """
        self._callbacks.append(callback)
    
    def get_changes(
        self,
        tool_name: Optional[str] = None,
        change_type: Optional[FileChangeType] = None
    ) -> List[FileChange]:
        """Get recorded file changes, optionally filtered.
        
        Args:
            tool_name: Filter by tool name (optional)
            change_type: Filter by change type (optional)
            
        Returns:
            List of FileChange objects matching the filters
        """
        changes = self._changes
        
        if tool_name is not None:
            changes = [c for c in changes if c.tool_name == tool_name]
        
        if change_type is not None:
            changes = [c for c in changes if c.change_type == change_type]
        
        return changes
    
    def get_modified_files(self) -> Set[str]:
        """Get set of all files that have been modified.
        
        Returns:
            Set of file paths that have been created or modified
        """
        modified = set()
        for change in self._changes:
            if change.change_type in (FileChangeType.CREATED, FileChangeType.MODIFIED):
                modified.add(change.path)
        return modified
    
    def get_deleted_files(self) -> Set[str]:
        """Get set of all files that have been deleted.
        
        Returns:
            Set of file paths that have been deleted
        """
        return {c.path for c in self._changes if c.change_type == FileChangeType.DELETED}
    
    def clear(self) -> None:
        """Clear all recorded changes."""
        self._changes.clear()
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about file changes.
        
        Returns:
            Dictionary with statistics:
            - total_changes: Total number of changes
            - files_created: Number of files created
            - files_modified: Number of files modified
            - files_deleted: Number of files deleted
            - unique_files: Number of unique files affected
            - by_tool: Changes grouped by tool name
        """
        stats = {
            "total_changes": len(self._changes),
            "files_created": len([c for c in self._changes if c.change_type == FileChangeType.CREATED]),
            "files_modified": len([c for c in self._changes if c.change_type == FileChangeType.MODIFIED]),
            "files_deleted": len([c for c in self._changes if c.change_type == FileChangeType.DELETED]),
            "unique_files": len(set(c.path for c in self._changes)),
            "by_tool": {}
        }
        
        # Group by tool
        for change in self._changes:
            tool = change.tool_name or "unknown"
            if tool not in stats["by_tool"]:
                stats["by_tool"][tool] = 0
            stats["by_tool"][tool] += 1
        
        return stats
    
    def checkpoint(self) -> List[FileChange]:
        """Create a checkpoint by returning current changes and clearing them.
        
        This is useful for tracking changes per tool execution or task phase.
        
        Returns:
            List of all changes since the last checkpoint
        """
        changes = self._changes.copy()
        self._changes.clear()
        return changes
    
    def restore_checkpoint(self, changes: List[FileChange]) -> None:
        """Restore changes from a checkpoint.
        
        Args:
            changes: List of FileChange objects to restore
        """
        self._changes.extend(changes)


class AsyncFileWatcher(FileWatcher):
    """Async version of FileWatcher with async callback support.
    
    Extends FileWatcher to support async callbacks and operations.
    
    Example:
        >>> async def on_change(change):
        ...     await async_process_change(change)
        >>> watcher = AsyncFileWatcher()
        >>> watcher.on_change_async(on_change)
    """
    
    def __init__(self, workspace_root: str = "."):
        super().__init__(workspace_root)
        self._async_callbacks: List[Callable[[FileChange], asyncio.Coroutine]] = []
    
    def on_change_async(self, callback: Callable[[FileChange], Awaitable[None]]) -> None:
        """Register an async callback for file changes.
        
        Args:
            callback: Async function to call with FileChange when a change occurs
        """
        self._async_callbacks.append(callback)
    
    async def record_change_async(
        self,
        file_path: str,
        change_type: FileChangeType,
        tool_name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> FileChange:
        """Record a file change and await async callbacks.
        
        Args:
            file_path: Path to the file (relative to workspace)
            change_type: Type of change that occurred
            tool_name: Name of the tool that made the change
            metadata: Additional metadata about the change
            
        Returns:
            The created FileChange object
        """
        change = super().record_change(file_path, change_type, tool_name, metadata)
        
        # Notify async callbacks
        for callback in self._async_callbacks:
            try:
                await callback(change)
            except Exception as e:
                # Don't let callback errors break the watcher
                print(f"Error in async file watcher callback: {e}")
        
        return change