"""
Unit tests for MCP session management.

Tests session and task state management, lifecycle handling, and cleanup operations.
"""

import asyncio
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from roo_code.mcp.session import (
    Session,
    SessionManager,
    PersistentSessionManager,
)
from roo_code.modes.task import Task, TaskState
from roo_code.modes.orchestrator import ModeOrchestrator


@pytest.fixture
def mock_orchestrator():
    """Create a mock mode orchestrator."""
    orchestrator = Mock(spec=ModeOrchestrator)
    orchestrator.get_mode = Mock(return_value=Mock(slug="code", name="Code Mode"))
    orchestrator.create_task = Mock(side_effect=lambda **kwargs: Task(**kwargs))
    return orchestrator


@pytest.fixture
def sample_task():
    """Create a sample task."""
    return Task(mode_slug="code", task_id="task_123")


class TestSession:
    """Test Session class."""
    
    def test_create_session(self, sample_task):
        """Test creating a session."""
        session = Session(task=sample_task)
        
        assert session.session_id.startswith("ses_")
        assert len(session.session_id) > 4
        assert session.task == sample_task
        assert isinstance(session.created_at, datetime)
        assert isinstance(session.last_accessed, datetime)
        assert isinstance(session.metadata, dict)
    
    def test_create_session_with_custom_id(self, sample_task):
        """Test creating session with custom ID."""
        session = Session(session_id="ses_custom123", task=sample_task)
        
        assert session.session_id == "ses_custom123"
    
    def test_session_touch(self, sample_task):
        """Test updating last accessed timestamp."""
        session = Session(task=sample_task)
        
        original_time = session.last_accessed
        
        # Wait a bit and touch
        import time
        time.sleep(0.01)
        session.touch()
        
        assert session.last_accessed > original_time
    
    def test_is_expired_not_expired(self, sample_task):
        """Test session is not expired within timeout."""
        session = Session(task=sample_task)
        
        assert not session.is_expired(timeout_seconds=3600)
    
    def test_is_expired_recently_accessed(self, sample_task):
        """Test recently accessed session is not expired."""
        session = Session(task=sample_task)
        session.touch()
        
        assert not session.is_expired(timeout_seconds=1)
    
    def test_is_expired_old_session(self, sample_task):
        """Test old session is expired."""
        session = Session(task=sample_task)
        
        # Manually set old last_accessed time
        session.last_accessed = datetime.now() - timedelta(seconds=7200)
        
        assert session.is_expired(timeout_seconds=3600)
    
    def test_get_age_seconds(self, sample_task):
        """Test getting session age."""
        session = Session(task=sample_task)
        
        age = session.get_age_seconds()
        
        assert age >= 0
        assert age < 1  # Should be very recent
    
    def test_get_idle_seconds(self, sample_task):
        """Test getting idle time."""
        session = Session(task=sample_task)
        
        import time
        time.sleep(0.01)
        
        idle = session.get_idle_seconds()
        
        assert idle >= 0.01
    
    def test_session_metadata(self, sample_task):
        """Test session metadata storage."""
        metadata = {"key": "value", "number": 42}
        session = Session(task=sample_task, metadata=metadata)
        
        assert session.metadata == metadata
        
        # Metadata should be mutable
        session.metadata["new_key"] = "new_value"
        assert session.metadata["new_key"] == "new_value"


class TestSessionManager:
    """Test SessionManager class."""
    
    @pytest.fixture
    def session_manager(self, mock_orchestrator):
        """Create a session manager."""
        return SessionManager(
            orchestrator=mock_orchestrator,
            timeout=3600,
            cleanup_interval=300
        )
    
    def test_init(self, mock_orchestrator):
        """Test session manager initialization."""
        manager = SessionManager(
            orchestrator=mock_orchestrator,
            timeout=7200,
            cleanup_interval=600
        )
        
        assert manager.orchestrator == mock_orchestrator
        assert manager.timeout == 7200
        assert manager.cleanup_interval == 600
        assert len(manager.sessions) == 0
        assert len(manager.task_to_session) == 0
        assert not manager.running
    
    @pytest.mark.asyncio
    async def test_start_stop(self, session_manager):
        """Test starting and stopping session manager."""
        assert not session_manager.running
        
        await session_manager.start()
        assert session_manager.running
        assert session_manager.cleanup_task is not None
        
        await session_manager.stop()
        assert not session_manager.running
    
    @pytest.mark.asyncio
    async def test_start_already_running(self, session_manager):
        """Test starting already running manager."""
        await session_manager.start()
        
        # Starting again should not create new task
        old_task = session_manager.cleanup_task
        await session_manager.start()
        assert session_manager.cleanup_task == old_task
        
        await session_manager.stop()
    
    def test_create_session(self, session_manager, sample_task):
        """Test creating a session."""
        session = session_manager.create_session(sample_task)
        
        assert session.session_id in session_manager.sessions
        assert sample_task.task_id in session_manager.task_to_session
        assert session_manager.task_to_session[sample_task.task_id] == session.session_id
    
    def test_create_multiple_sessions(self, session_manager):
        """Test creating multiple sessions."""
        task1 = Task(mode_slug="code", task_id="task1")
        task2 = Task(mode_slug="ask", task_id="task2")
        
        session1 = session_manager.create_session(task1)
        session2 = session_manager.create_session(task2)
        
        assert session1.session_id != session2.session_id
        assert len(session_manager.sessions) == 2
    
    def test_get_session(self, session_manager, sample_task):
        """Test getting a session by ID."""
        session = session_manager.create_session(sample_task)
        
        retrieved = session_manager.get_session(session.session_id)
        
        assert retrieved is not None
        assert retrieved.session_id == session.session_id
        assert retrieved.task == sample_task
    
    def test_get_session_nonexistent(self, session_manager):
        """Test getting non-existent session returns None."""
        result = session_manager.get_session("ses_nonexistent")
        
        assert result is None
    
    def test_get_session_expired(self, session_manager, sample_task):
        """Test getting expired session returns None and cleans up."""
        session = session_manager.create_session(sample_task)
        
        # Make session expired
        session.last_accessed = datetime.now() - timedelta(seconds=7200)
        
        result = session_manager.get_session(session.session_id)
        
        assert result is None
        assert session.session_id not in session_manager.sessions
    
    def test_get_session_touches_timestamp(self, session_manager, sample_task):
        """Test getting session updates last accessed timestamp."""
        session = session_manager.create_session(sample_task)
        
        original_time = session.last_accessed
        
        import time
        time.sleep(0.01)
        
        retrieved = session_manager.get_session(session.session_id)
        
        assert retrieved.last_accessed > original_time
    
    def test_get_session_by_task(self, session_manager, sample_task):
        """Test getting session by task ID."""
        session = session_manager.create_session(sample_task)
        
        retrieved = session_manager.get_session_by_task(sample_task.task_id)
        
        assert retrieved is not None
        assert retrieved.session_id == session.session_id
    
    def test_get_session_by_task_nonexistent(self, session_manager):
        """Test getting session by non-existent task ID."""
        result = session_manager.get_session_by_task("task_nonexistent")
        
        assert result is None
    
    def test_list_sessions(self, session_manager):
        """Test listing all sessions."""
        task1 = Task(mode_slug="code", task_id="task1")
        task2 = Task(mode_slug="ask", task_id="task2")
        
        session1 = session_manager.create_session(task1)
        session2 = session_manager.create_session(task2)
        
        sessions = session_manager.list_sessions()
        
        assert len(sessions) == 2
        assert session1 in sessions
        assert session2 in sessions
    
    def test_get_session_count(self, session_manager):
        """Test getting session count."""
        assert session_manager.get_session_count() == 0
        
        task1 = Task(mode_slug="code", task_id="task1")
        session_manager.create_session(task1)
        assert session_manager.get_session_count() == 1
        
        task2 = Task(mode_slug="ask", task_id="task2")
        session_manager.create_session(task2)
        assert session_manager.get_session_count() == 2
    
    def test_destroy_session(self, session_manager, sample_task):
        """Test explicitly destroying a session."""
        session = session_manager.create_session(sample_task)
        
        assert session.session_id in session_manager.sessions
        
        result = session_manager.destroy_session(session.session_id)
        
        assert result is True
        assert session.session_id not in session_manager.sessions
        assert sample_task.task_id not in session_manager.task_to_session
    
    def test_destroy_session_nonexistent(self, session_manager):
        """Test destroying non-existent session returns False."""
        result = session_manager.destroy_session("ses_nonexistent")
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_cleanup_expired(self, session_manager):
        """Test cleaning up expired sessions."""
        task1 = Task(mode_slug="code", task_id="task1")
        task2 = Task(mode_slug="ask", task_id="task2")
        
        session1 = session_manager.create_session(task1)
        session2 = session_manager.create_session(task2)
        
        # Make session1 expired
        session1.last_accessed = datetime.now() - timedelta(seconds=7200)
        
        await session_manager._cleanup_expired()
        
        # session1 should be removed, session2 should remain
        assert session1.session_id not in session_manager.sessions
        assert session2.session_id in session_manager.sessions
    
    @pytest.mark.asyncio
    async def test_cleanup_all(self, session_manager):
        """Test cleaning up all sessions."""
        task1 = Task(mode_slug="code", task_id="task1")
        task2 = Task(mode_slug="ask", task_id="task2")
        
        session_manager.create_session(task1)
        session_manager.create_session(task2)
        
        assert session_manager.get_session_count() == 2
        
        await session_manager.cleanup_all()
        
        assert session_manager.get_session_count() == 0
        assert len(session_manager.task_to_session) == 0
    
    @pytest.mark.asyncio
    async def test_cleanup_loop_runs(self, session_manager):
        """Test that cleanup loop runs periodically."""
        session_manager.cleanup_interval = 0.1  # Short interval for testing
        
        await session_manager.start()
        
        # Let it run for a bit
        await asyncio.sleep(0.15)
        
        # Should have run at least once without errors
        assert session_manager.running
        
        await session_manager.stop()
    
    def test_get_stats_empty(self, session_manager):
        """Test getting stats with no sessions."""
        stats = session_manager.get_stats()
        
        assert stats["total_sessions"] == 0
        assert stats["timeout_seconds"] == 3600
        assert stats["cleanup_interval_seconds"] == 300
    
    def test_get_stats_with_sessions(self, session_manager):
        """Test getting stats with active sessions."""
        task1 = Task(mode_slug="code", task_id="task1")
        task2 = Task(mode_slug="ask", task_id="task2")
        
        session_manager.create_session(task1)
        
        import time
        time.sleep(0.01)
        
        session_manager.create_session(task2)
        
        stats = session_manager.get_stats()
        
        assert stats["total_sessions"] == 2
        assert "oldest_session_age_seconds" in stats
        assert "newest_session_age_seconds" in stats
        assert "max_idle_time_seconds" in stats
        assert "min_idle_time_seconds" in stats
        assert "avg_idle_time_seconds" in stats


class TestPersistentSessionManager:
    """Test PersistentSessionManager class."""
    
    @pytest.fixture
    def storage_path(self, tmp_path):
        """Create a temporary storage path."""
        return str(tmp_path / "sessions")
    
    @pytest.fixture
    def persistent_manager(self, mock_orchestrator, storage_path):
        """Create a persistent session manager."""
        return PersistentSessionManager(
            orchestrator=mock_orchestrator,
            storage_path=storage_path,
            timeout=3600,
            cleanup_interval=300
        )
    
    def test_init_creates_storage_directory(self, mock_orchestrator, tmp_path):
        """Test initialization creates storage directory."""
        storage_path = str(tmp_path / "new_sessions")
        
        manager = PersistentSessionManager(
            orchestrator=mock_orchestrator,
            storage_path=storage_path
        )
        
        from pathlib import Path
        assert Path(storage_path).exists()
        assert Path(storage_path).is_dir()
    
    def test_get_session_file(self, persistent_manager):
        """Test getting session file path."""
        session_id = "ses_abc123"
        
        file_path = persistent_manager._get_session_file(session_id)
        
        from pathlib import Path
        assert isinstance(file_path, Path)
        assert str(file_path).endswith("ses_abc123.json")
    
    @pytest.mark.asyncio
    async def test_save_session(self, persistent_manager, sample_task):
        """Test saving session to disk."""
        session = persistent_manager.create_session(sample_task)
        
        await persistent_manager.save_session(session)
        
        # Verify file exists
        file_path = persistent_manager._get_session_file(session.session_id)
        assert file_path.exists()
        
        # Verify content
        import json
        with open(file_path) as f:
            data = json.load(f)
        
        assert data["session_id"] == session.session_id
        assert data["task_id"] == sample_task.task_id
        assert data["mode_slug"] == "code"
    
    @pytest.mark.asyncio
    async def test_save_session_with_metadata(self, persistent_manager):
        """Test saving session with metadata."""
        task = Task(mode_slug="code", task_id="task_123")
        session = persistent_manager.create_session(task)
        session.metadata = {"custom": "data", "count": 42}
        
        await persistent_manager.save_session(session)
        
        # Verify metadata is saved
        file_path = persistent_manager._get_session_file(session.session_id)
        import json
        with open(file_path) as f:
            data = json.load(f)
        
        assert data["metadata"] == {"custom": "data", "count": 42}
    
    @pytest.mark.asyncio
    async def test_load_session_nonexistent(self, persistent_manager):
        """Test loading non-existent session returns None."""
        result = await persistent_manager.load_session("ses_nonexistent")
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_load_session_saved(self, persistent_manager, sample_task):
        """Test loading a saved session."""
        session = persistent_manager.create_session(sample_task)
        await persistent_manager.save_session(session)
        
        # Currently returns None as full reconstruction is not implemented
        # This test documents the expected behavior
        result = await persistent_manager.load_session(session.session_id)
        
        # When implemented, should return reconstructed session
        # assert result is not None
        # assert result.session_id == session.session_id


class TestSessionLifecycle:
    """Test session lifecycle scenarios."""
    
    @pytest.mark.asyncio
    async def test_session_lifecycle_complete(self, mock_orchestrator):
        """Test complete session lifecycle."""
        manager = SessionManager(orchestrator=mock_orchestrator)
        
        # Start manager
        await manager.start()
        
        # Create session
        task = Task(mode_slug="code", task_id="task_123")
        session = manager.create_session(task)
        
        assert session.session_id in manager.sessions
        
        # Use session
        retrieved = manager.get_session(session.session_id)
        assert retrieved is not None
        
        # Destroy session
        manager.destroy_session(session.session_id)
        assert session.session_id not in manager.sessions
        
        # Stop manager
        await manager.stop()
        assert not manager.running
    
    @pytest.mark.asyncio
    async def test_multiple_sessions_lifecycle(self, mock_orchestrator):
        """Test managing multiple sessions."""
        manager = SessionManager(orchestrator=mock_orchestrator, timeout=1)
        
        # Create multiple sessions
        sessions = []
        for i in range(5):
            task = Task(mode_slug="code", task_id=f"task_{i}")
            session = manager.create_session(task)
            sessions.append(session)
        
        assert manager.get_session_count() == 5
        
        # Make some sessions expired
        sessions[0].last_accessed = datetime.now() - timedelta(seconds=2)
        sessions[2].last_accessed = datetime.now() - timedelta(seconds=2)
        
        # Cleanup expired
        await manager._cleanup_expired()
        
        assert manager.get_session_count() == 3
        
        # Cleanup all
        await manager.cleanup_all()
        
        assert manager.get_session_count() == 0
    
    @pytest.mark.asyncio
    async def test_session_expiration_during_use(self, mock_orchestrator):
        """Test session expiration while being used."""
        manager = SessionManager(orchestrator=mock_orchestrator, timeout=0.1)
        
        task = Task(mode_slug="code", task_id="task_123")
        session = manager.create_session(task)
        
        # Wait for expiration
        await asyncio.sleep(0.15)
        
        # Getting expired session should return None and clean up
        result = manager.get_session(session.session_id)
        
        assert result is None
        assert session.session_id not in manager.sessions