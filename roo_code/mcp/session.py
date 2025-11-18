"""
Session and task state management for MCP server.

This module provides session management, task tracking, and lifecycle handling
for the MCP Modes Server.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional
from uuid import uuid4

from ..modes.orchestrator import ModeOrchestrator
from ..modes.task import Task

logger = logging.getLogger(__name__)


@dataclass
class Session:
    """
    Represents an active session with a task.
    
    A session wraps a task and adds session-specific metadata
    like creation time, last access, and session ID for client reference.
    """
    
    session_id: str = field(default_factory=lambda: f"ses_{uuid4().hex[:12]}")
    task: Task = field(default_factory=Task)
    created_at: datetime = field(default_factory=datetime.now)
    last_accessed: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, any] = field(default_factory=dict)
    
    def touch(self) -> None:
        """Update last accessed timestamp."""
        self.last_accessed = datetime.now()
    
    def is_expired(self, timeout_seconds: int) -> bool:
        """
        Check if session has expired.
        
        Args:
            timeout_seconds: Timeout threshold in seconds
            
        Returns:
            True if session has expired, False otherwise
        """
        elapsed = (datetime.now() - self.last_accessed).total_seconds()
        return elapsed > timeout_seconds
    
    def get_age_seconds(self) -> float:
        """
        Get the age of the session in seconds.
        
        Returns:
            Seconds since session creation
        """
        return (datetime.now() - self.created_at).total_seconds()
    
    def get_idle_seconds(self) -> float:
        """
        Get the idle time in seconds.
        
        Returns:
            Seconds since last access
        """
        return (datetime.now() - self.last_accessed).total_seconds()


class SessionManager:
    """
    Manages sessions and their lifecycle.
    
    Responsibilities:
    - Create and destroy sessions
    - Track task-session mappings
    - Handle session expiration
    - Maintain task hierarchies
    - Background cleanup of expired sessions
    """
    
    def __init__(
        self,
        orchestrator: ModeOrchestrator,
        timeout: int = 3600,  # 1 hour
        cleanup_interval: int = 300  # 5 minutes
    ):
        """
        Initialize session manager.
        
        Args:
            orchestrator: Mode orchestrator for task management
            timeout: Session timeout in seconds
            cleanup_interval: How often to run cleanup (seconds)
        """
        self.orchestrator = orchestrator
        self.timeout = timeout
        self.cleanup_interval = cleanup_interval
        
        # Session storage
        self.sessions: Dict[str, Session] = {}
        self.task_to_session: Dict[str, str] = {}  # task_id -> session_id
        
        # Cleanup task
        self.cleanup_task: Optional[asyncio.Task] = None
        self.running = False
    
    async def start(self) -> None:
        """Start the session manager and cleanup task."""
        if self.running:
            logger.warning("Session manager already running")
            return
        
        self.running = True
        self.cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("Session manager started")
    
    async def stop(self) -> None:
        """Stop the session manager."""
        if not self.running:
            return
        
        self.running = False
        
        if self.cleanup_task:
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Session manager stopped")
    
    def create_session(self, task: Task) -> Session:
        """
        Create a new session for a task.
        
        Args:
            task: Task to create session for
            
        Returns:
            Created session
        """
        session = Session(task=task)
        self.sessions[session.session_id] = session
        self.task_to_session[task.task_id] = session.session_id
        
        logger.info(
            f"Created session {session.session_id} for task {task.task_id} "
            f"in mode '{task.mode_slug}'"
        )
        return session
    
    def get_session(self, session_id: str) -> Optional[Session]:
        """
        Get a session by ID.
        
        Args:
            session_id: Session ID to retrieve
            
        Returns:
            Session if found and not expired, None otherwise
        """
        session = self.sessions.get(session_id)
        if not session:
            return None
        
        # Check expiration
        if session.is_expired(self.timeout):
            logger.info(f"Session {session_id} has expired")
            self._cleanup_session(session_id)
            return None
        
        # Update access time
        session.touch()
        return session
    
    def get_session_by_task(self, task_id: str) -> Optional[Session]:
        """
        Get session by task ID.
        
        Args:
            task_id: Task ID to look up
            
        Returns:
            Session if found, None otherwise
        """
        session_id = self.task_to_session.get(task_id)
        if session_id:
            return self.get_session(session_id)
        return None
    
    def list_sessions(self) -> list[Session]:
        """
        List all active sessions.
        
        Returns:
            List of active sessions
        """
        return list(self.sessions.values())
    
    def get_session_count(self) -> int:
        """
        Get count of active sessions.
        
        Returns:
            Number of active sessions
        """
        return len(self.sessions)
    
    def destroy_session(self, session_id: str) -> bool:
        """
        Explicitly destroy a session.
        
        Args:
            session_id: Session to destroy
            
        Returns:
            True if session was found and destroyed
        """
        return self._cleanup_session(session_id)
    
    def _cleanup_session(self, session_id: str) -> bool:
        """
        Internal cleanup of a session.
        
        Args:
            session_id: Session ID to clean up
            
        Returns:
            True if session was found and removed
        """
        session = self.sessions.pop(session_id, None)
        if session:
            self.task_to_session.pop(session.task.task_id, None)
            logger.info(f"Cleaned up session {session_id}")
            return True
        return False
    
    async def _cleanup_loop(self) -> None:
        """Background task to clean up expired sessions."""
        logger.info(
            f"Starting session cleanup loop (interval: {self.cleanup_interval}s, "
            f"timeout: {self.timeout}s)"
        )
        
        while self.running:
            try:
                await asyncio.sleep(self.cleanup_interval)
                await self._cleanup_expired()
            except asyncio.CancelledError:
                logger.info("Cleanup loop cancelled")
                break
            except Exception as e:
                logger.exception(f"Error in cleanup loop: {e}")
    
    async def _cleanup_expired(self) -> None:
        """Clean up all expired sessions."""
        expired = [
            sid for sid, session in self.sessions.items()
            if session.is_expired(self.timeout)
        ]
        
        for session_id in expired:
            self._cleanup_session(session_id)
        
        if expired:
            logger.info(f"Cleaned up {len(expired)} expired sessions")
    
    async def cleanup_all(self) -> None:
        """
        Clean up all sessions (for shutdown).
        
        This method is called during server shutdown to clean up
        all active sessions gracefully.
        """
        session_count = len(self.sessions)
        session_ids = list(self.sessions.keys())
        
        for session_id in session_ids:
            self._cleanup_session(session_id)
        
        logger.info(f"Cleaned up all {session_count} sessions")
    
    def get_stats(self) -> Dict[str, any]:
        """
        Get session manager statistics.
        
        Returns:
            Dictionary with statistics
        """
        sessions_list = list(self.sessions.values())
        
        stats = {
            "total_sessions": len(sessions_list),
            "timeout_seconds": self.timeout,
            "cleanup_interval_seconds": self.cleanup_interval,
        }
        
        if sessions_list:
            ages = [s.get_age_seconds() for s in sessions_list]
            idle_times = [s.get_idle_seconds() for s in sessions_list]
            
            stats["oldest_session_age_seconds"] = max(ages)
            stats["newest_session_age_seconds"] = min(ages)
            stats["max_idle_time_seconds"] = max(idle_times)
            stats["min_idle_time_seconds"] = min(idle_times)
            stats["avg_idle_time_seconds"] = sum(idle_times) / len(idle_times)
        
        return stats


class PersistentSessionManager(SessionManager):
    """
    Session manager with persistence support.
    
    This extends SessionManager to add the ability to save and restore
    sessions across server restarts.
    """
    
    def __init__(
        self,
        orchestrator: ModeOrchestrator,
        storage_path: str,
        timeout: int = 3600,
        cleanup_interval: int = 300
    ):
        """
        Initialize persistent session manager.
        
        Args:
            orchestrator: Mode orchestrator
            storage_path: Path to store session data
            timeout: Session timeout in seconds
            cleanup_interval: Cleanup interval in seconds
        """
        super().__init__(orchestrator, timeout, cleanup_interval)
        from pathlib import Path
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Persistent sessions enabled at {storage_path}")
    
    def _get_session_file(self, session_id: str) -> str:
        """Get file path for a session."""
        from pathlib import Path
        return Path(self.storage_path) / f"{session_id}.json"
    
    async def save_session(self, session: Session) -> None:
        """
        Save session to disk.
        
        Args:
            session: Session to save
        """
        import json
        
        file_path = self._get_session_file(session.session_id)
        
        data = {
            "session_id": session.session_id,
            "task_id": session.task.task_id,
            "mode_slug": session.task.mode_slug,
            "created_at": session.created_at.isoformat(),
            "last_accessed": session.last_accessed.isoformat(),
            "metadata": session.metadata,
            "task_state": session.task.state.value,
            "message_count": len(session.task.messages)
        }
        
        try:
            with open(file_path, 'w') as f:
                json.dump(data, f, indent=2)
            logger.debug(f"Saved session {session.session_id} to {file_path}")
        except Exception as e:
            logger.error(f"Failed to save session {session.session_id}: {e}")
    
    async def load_session(self, session_id: str) -> Optional[Session]:
        """
        Load session from disk.
        
        Args:
            session_id: Session ID to load
            
        Returns:
            Loaded session or None if not found
        """
        import json
        
        file_path = self._get_session_file(session_id)
        
        if not file_path.exists():
            return None
        
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            # Note: This is a simplified load - full implementation would
            # need to reconstruct the Task with all its messages
            logger.info(f"Loaded session metadata for {session_id}")
            return None  # Placeholder
            
        except Exception as e:
            logger.error(f"Failed to load session {session_id}: {e}")
            return None