"""Tests for error recovery mechanisms."""

import asyncio
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, Mock

from roo_code.builtin_tools.error_recovery import (
    ErrorContext,
    ErrorRecoveryManager,
    RetryStrategy,
    RecoverableError,
    NonRecoverableError,
    NetworkError,
    RateLimitError,
    TimeoutError,
    ValidationError,
    FileNotFoundError,
    PermissionError,
    get_recovery_manager,
    set_recovery_manager
)


class UnreliableOperation:
    """Mock operation that fails a specified number of times."""
    
    def __init__(self, fail_count: int = 2, error_type: type = NetworkError):
        self.attempts = 0
        self.fail_count = fail_count
        self.error_type = error_type
    
    async def execute(self, value: str = "test") -> str:
        """Execute operation, failing fail_count times."""
        self.attempts += 1
        if self.attempts <= self.fail_count:
            raise self.error_type(f"Temporary failure (attempt {self.attempts})")
        return f"Success: {value}"


@pytest.mark.asyncio
class TestErrorRecoveryManager:
    """Test error recovery manager functionality."""
    
    async def test_successful_execution_no_retry(self):
        """Test successful execution without any failures."""
        manager = ErrorRecoveryManager(max_retries=3)
        
        async def always_succeeds():
            return "success"
        
        result = await manager.execute_with_recovery(
            always_succeeds,
            tool_name="test_tool",
            use_id="test_001"
        )
        
        assert result == "success"
        assert manager.get_error_count("test_tool") == 0
    
    async def test_retry_recoverable_error(self):
        """Test retry on recoverable error."""
        manager = ErrorRecoveryManager(
            max_retries=3,
            backoff_factor=1.0,  # No delay for testing
            initial_delay=0.01
        )
        
        operation = UnreliableOperation(fail_count=2)
        
        result = await manager.execute_with_recovery(
            operation.execute,
            "test_value",
            tool_name="test_tool",
            use_id="test_002"
        )
        
        assert result == "Success: test_value"
        assert operation.attempts == 3  # 2 failures + 1 success
        assert manager.get_error_count("test_tool") == 2
    
    async def test_non_recoverable_error_no_retry(self):
        """Test that non-recoverable errors are not retried."""
        manager = ErrorRecoveryManager(max_retries=3)
        
        async def raises_validation_error():
            raise ValidationError("Invalid input")
        
        with pytest.raises(ValidationError, match="Invalid input"):
            await manager.execute_with_recovery(
                raises_validation_error,
                tool_name="test_tool",
                use_id="test_003"
            )
        
        # Should only have one error (no retries)
        assert manager.get_error_count("test_tool") == 1
    
    async def test_max_retries_exhausted(self):
        """Test that max retries are respected."""
        manager = ErrorRecoveryManager(
            max_retries=2,
            initial_delay=0.01
        )
        
        operation = UnreliableOperation(fail_count=5)  # More failures than retries
        
        with pytest.raises(NetworkError):
            await manager.execute_with_recovery(
                operation.execute,
                tool_name="test_tool",
                use_id="test_004"
            )
        
        assert operation.attempts == 2  # max_retries
        assert manager.get_error_count("test_tool") == 2
    
    async def test_exponential_backoff(self):
        """Test exponential backoff delays."""
        manager = ErrorRecoveryManager(
            max_retries=3,
            backoff_factor=2.0,
            initial_delay=0.1,
            max_delay=1.0
        )
        
        # Test delay calculation
        delay1 = manager._calculate_delay(1)
        delay2 = manager._calculate_delay(2)
        delay3 = manager._calculate_delay(3)
        
        assert delay1 == 0.1
        assert delay2 == 0.2
        assert delay3 == 0.4
    
    async def test_linear_backoff(self):
        """Test linear backoff delays."""
        manager = ErrorRecoveryManager(
            max_retries=3,
            retry_strategy=RetryStrategy.LINEAR_BACKOFF,
            initial_delay=0.1
        )
        
        delay1 = manager._calculate_delay(1)
        delay2 = manager._calculate_delay(2)
        delay3 = manager._calculate_delay(3)
        
        assert delay1 == 0.1
        assert delay2 == 0.2
        assert delay3 == 0.3
    
    async def test_fixed_delay(self):
        """Test fixed delay strategy."""
        manager = ErrorRecoveryManager(
            max_retries=3,
            retry_strategy=RetryStrategy.FIXED_DELAY,
            initial_delay=0.5
        )
        
        delay1 = manager._calculate_delay(1)
        delay2 = manager._calculate_delay(2)
        delay3 = manager._calculate_delay(3)
        
        assert delay1 == 0.5
        assert delay2 == 0.5
        assert delay3 == 0.5
    
    async def test_max_delay_cap(self):
        """Test that delays are capped at max_delay."""
        manager = ErrorRecoveryManager(
            max_retries=10,
            backoff_factor=2.0,
            initial_delay=1.0,
            max_delay=5.0
        )
        
        # With exponential backoff, attempt 5 would be 16s without cap
        delay5 = manager._calculate_delay(5)
        assert delay5 == 5.0  # Capped at max_delay
    
    async def test_rate_limit_error_retry_after(self):
        """Test that rate limit errors respect retry_after."""
        manager = ErrorRecoveryManager(max_retries=2, initial_delay=1.0)
        
        error = RateLimitError("Rate limit exceeded", retry_after=3)
        delay = manager._calculate_delay(1, error)
        
        assert delay == 3.0  # Should use retry_after
    
    async def test_custom_recovery_strategy(self):
        """Test custom recovery strategy registration and execution."""
        manager = ErrorRecoveryManager(max_retries=2, initial_delay=0.01)
        
        # Register a fallback strategy
        fallback_value = "fallback_result"
        
        async def fallback_strategy(context: ErrorContext):
            return fallback_value
        
        manager.register_recovery_strategy(NetworkError, fallback_strategy)
        
        # Operation that always fails
        async def always_fails():
            raise NetworkError("Always fails")
        
        result = await manager.execute_with_recovery(
            always_fails,
            tool_name="test_tool",
            use_id="test_005"
        )
        
        assert result == fallback_value
    
    async def test_timeout_handling(self):
        """Test timeout enforcement."""
        manager = ErrorRecoveryManager(max_retries=1)
        
        async def slow_operation():
            await asyncio.sleep(2)
            return "success"
        
        with pytest.raises(TimeoutError):
            await manager.execute_with_recovery(
                slow_operation,
                tool_name="test_tool",
                use_id="test_006",
                timeout=0.1
            )
    
    async def test_error_context_tracking(self):
        """Test that error contexts are properly tracked."""
        manager = ErrorRecoveryManager(max_retries=2, initial_delay=0.01)
        
        operation = UnreliableOperation(fail_count=1)
        
        await manager.execute_with_recovery(
            operation.execute,
            "test_value",
            tool_name="test_tool",
            use_id="test_007"
        )
        
        history = manager.get_error_history("test_tool")
        assert len(history) == 1
        
        context = history[0]
        assert context.tool_name == "test_tool"
        assert context.use_id == "test_007"
        assert context.attempt_number == 1
        assert isinstance(context.error, NetworkError)
        assert context.stack_trace  # Should have stack trace
    
    async def test_error_history_filtering(self):
        """Test error history filtering by tool name."""
        manager = ErrorRecoveryManager(max_retries=1, initial_delay=0.01)
        
        # Create errors for different tools
        for tool_name in ["tool1", "tool2", "tool1"]:
            try:
                await manager.execute_with_recovery(
                    lambda: 1/0,  # Raises ZeroDivisionError
                    tool_name=tool_name,
                    use_id=f"test_{tool_name}"
                )
            except:
                pass
        
        tool1_history = manager.get_error_history("tool1")
        tool2_history = manager.get_error_history("tool2")
        
        assert len(tool1_history) == 2
        assert len(tool2_history) == 1
    
    async def test_clear_history(self):
        """Test clearing error history."""
        manager = ErrorRecoveryManager(max_retries=1, initial_delay=0.01)
        
        operation = UnreliableOperation(fail_count=1)
        
        await manager.execute_with_recovery(
            operation.execute,
            tool_name="test_tool",
            use_id="test_008"
        )
        
        assert manager.get_error_count() > 0
        
        manager.clear_history()
        
        assert manager.get_error_count() == 0
        assert len(manager.get_error_history()) == 0
    
    async def test_retry_on_specific_errors(self):
        """Test retry_on parameter to limit which errors trigger retry."""
        # Only retry on NetworkError
        manager = ErrorRecoveryManager(
            max_retries=2,
            retry_on=[NetworkError],
            initial_delay=0.01
        )
        
        # NetworkError should be retried
        operation1 = UnreliableOperation(fail_count=1, error_type=NetworkError)
        result1 = await manager.execute_with_recovery(
            operation1.execute,
            tool_name="test_tool",
            use_id="test_009"
        )
        assert result1.startswith("Success")
        assert operation1.attempts == 2  # 1 failure + 1 success
        
        # TimeoutError should not be retried (not in retry_on list)
        async def raises_timeout():
            raise TimeoutError("Timeout")
        
        with pytest.raises(TimeoutError):
            await manager.execute_with_recovery(
                raises_timeout,
                tool_name="test_tool",
                use_id="test_010"
            )


@pytest.mark.asyncio
class TestErrorClassification:
    """Test error type hierarchy and classification."""
    
    async def test_recoverable_errors(self):
        """Test that RecoverableError subclasses are identified correctly."""
        assert issubclass(NetworkError, RecoverableError)
        assert issubclass(RateLimitError, RecoverableError)
        assert issubclass(TimeoutError, RecoverableError)
    
    async def test_non_recoverable_errors(self):
        """Test that NonRecoverableError subclasses are identified correctly."""
        assert issubclass(ValidationError, NonRecoverableError)
        assert issubclass(FileNotFoundError, NonRecoverableError)
        assert issubclass(PermissionError, NonRecoverableError)
    
    async def test_error_hierarchy(self):
        """Test that error types don't overlap."""
        # RecoverableError and NonRecoverableError should be distinct
        assert not issubclass(RecoverableError, NonRecoverableError)
        assert not issubclass(NonRecoverableError, RecoverableError)


@pytest.mark.asyncio
class TestGlobalRecoveryManager:
    """Test global recovery manager functions."""
    
    async def test_get_global_manager(self):
        """Test getting global manager instance."""
        manager1 = get_recovery_manager()
        manager2 = get_recovery_manager()
        
        assert manager1 is manager2  # Should be same instance
    
    async def test_set_global_manager(self):
        """Test setting custom global manager."""
        custom_manager = ErrorRecoveryManager(max_retries=5)
        set_recovery_manager(custom_manager)
        
        manager = get_recovery_manager()
        assert manager is custom_manager
        assert manager.max_retries == 5
        
        # Reset to default
        set_recovery_manager(ErrorRecoveryManager())


@pytest.mark.asyncio
class TestErrorContext:
    """Test ErrorContext dataclass."""
    
    async def test_error_context_creation(self):
        """Test creating error context."""
        error = NetworkError("Test error")
        
        context = ErrorContext(
            tool_name="test_tool",
            use_id="test_001",
            error=error,
            attempt_number=1,
            parameters={"key": "value"}
        )
        
        assert context.tool_name == "test_tool"
        assert context.use_id == "test_001"
        assert context.error is error
        assert context.attempt_number == 1
        assert context.parameters == {"key": "value"}
        assert isinstance(context.timestamp, datetime)
        assert context.stack_trace  # Auto-generated
    
    async def test_error_context_stack_trace(self):
        """Test that stack trace is properly captured."""
        try:
            raise NetworkError("Test error")
        except NetworkError as e:
            context = ErrorContext(
                tool_name="test_tool",
                use_id="test_001",
                error=e,
                attempt_number=1
            )
            
            assert "NetworkError" in context.stack_trace
            assert "Test error" in context.stack_trace


@pytest.mark.asyncio
class TestEdgeCases:
    """Test edge cases and error conditions."""
    
    async def test_zero_retries(self):
        """Test with max_retries=0 (no retries)."""
        manager = ErrorRecoveryManager(max_retries=0)
        
        async def fails_once():
            raise NetworkError("Fails")
        
        with pytest.raises(NetworkError):
            await manager.execute_with_recovery(
                fails_once,
                tool_name="test_tool",
                use_id="test_001"
            )
    
    async def test_negative_retries(self):
        """Test with negative max_retries (treated as 0)."""
        manager = ErrorRecoveryManager(max_retries=-1)
        
        async def fails_once():
            raise NetworkError("Fails")
        
        # Should fail immediately with no retries
        with pytest.raises(NetworkError):
            await manager.execute_with_recovery(
                fails_once,
                tool_name="test_tool",
                use_id="test_001"
            )
    
    async def test_async_and_sync_errors(self):
        """Test handling of both async exceptions and sync ones."""
        manager = ErrorRecoveryManager(max_retries=1, initial_delay=0.01)
        
        # Async error
        async def async_error():
            raise NetworkError("Async error")
        
        with pytest.raises(NetworkError):
            await manager.execute_with_recovery(
                async_error,
                tool_name="test_tool",
                use_id="test_001"
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])