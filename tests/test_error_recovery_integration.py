"""Integration tests for error recovery with actual tools."""

import asyncio
import pytest
from unittest.mock import AsyncMock, Mock, patch

from roo_code.tools import Tool, ToolInputSchema, ToolResult, ToolRegistry
from roo_code.builtin_tools.error_recovery import (
    ErrorRecoveryManager,
    NetworkError,
    ValidationError,
    get_recovery_manager
)
from roo_code.builtin_tools.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerError,
    get_circuit_breaker_registry
)
from roo_code.builtin_tools.error_metrics import get_error_metrics


class MockUnreliableTool(Tool):
    """Mock tool that fails a specified number of times."""
    
    def __init__(self, fail_count: int = 2, enable_retry: bool = True):
        self.fail_count = fail_count
        self.attempts = 0
        super().__init__(
            name="mock_unreliable_tool",
            description="A tool that fails predictably",
            input_schema=ToolInputSchema(
                type="object",
                properties={
                    "value": {"type": "string", "description": "Test value"}
                },
                required=["value"]
            ),
            enable_retry=enable_retry,
            enable_circuit_breaker=False
        )
    
    async def execute(self, input_data: dict) -> ToolResult:
        """Execute with intentional failures."""
        self.attempts += 1
        
        if self.attempts <= self.fail_count:
            raise NetworkError(f"Attempt {self.attempts} failed")
        
        return ToolResult(
            tool_use_id=self.current_use_id or "test",
            content=f"Success after {self.attempts} attempts: {input_data['value']}",
            is_error=False
        )


class MockNonRecoverableTool(Tool):
    """Mock tool that always raises non-recoverable errors."""
    
    def __init__(self):
        super().__init__(
            name="mock_non_recoverable_tool",
            description="A tool that always fails with non-recoverable errors",
            input_schema=ToolInputSchema(
                type="object",
                properties={
                    "value": {"type": "string"}
                },
                required=["value"]
            ),
            enable_retry=True
        )
    
    async def execute(self, input_data: dict) -> ToolResult:
        """Always raise non-recoverable error."""
        raise ValidationError("Invalid input")


@pytest.mark.asyncio
class TestToolWithErrorRecovery:
    """Test tools with error recovery integration."""
    
    async def test_tool_executes_with_retry(self):
        """Test that tool execution includes retry logic."""
        tool = MockUnreliableTool(fail_count=2, enable_retry=True)
        tool.current_use_id = "test_001"
        
        # Execute via execute_with_recovery
        result = await tool.execute_with_recovery({"value": "test"})
        
        assert not result.is_error
        assert "Success after 3 attempts" in result.content
        assert tool.attempts == 3
    
    async def test_tool_without_retry_fails_immediately(self):
        """Test that tool with retry disabled fails on first error."""
        tool = MockUnreliableTool(fail_count=2, enable_retry=False)
        tool.current_use_id = "test_002"
        
        with pytest.raises(NetworkError):
            await tool.execute_with_recovery({"value": "test"})
        
        assert tool.attempts == 1  # No retries
    
    async def test_tool_non_recoverable_error_no_retry(self):
        """Test that non-recoverable errors are not retried."""
        tool = MockNonRecoverableTool()
        tool.current_use_id = "test_003"
        
        with pytest.raises(ValidationError):
            await tool.execute_with_recovery({"value": "test"})
        
        # Should only have attempted once
        recovery_manager = get_recovery_manager()
        history = recovery_manager.get_error_history(tool.name)
        assert len(history) == 1
    
    async def test_tool_timeout_enforcement(self):
        """Test that timeout is enforced during tool execution."""
        
        class SlowTool(Tool):
            def __init__(self):
                super().__init__(
                    name="slow_tool",
                    description="A slow tool",
                    input_schema=ToolInputSchema(
                        type="object",
                        properties={}
                    ),
                    enable_retry=True
                )
            
            async def execute(self, input_data: dict) -> ToolResult:
                await asyncio.sleep(2)
                return ToolResult(
                    tool_use_id=self.current_use_id or "test",
                    content="Done"
                )
        
        tool = SlowTool()
        tool.current_use_id = "test_004"
        
        # Should timeout
        from roo_code.builtin_tools.error_recovery import TimeoutError as RooTimeoutError
        with pytest.raises(RooTimeoutError):
            await tool.execute_with_recovery({}, timeout=0.1)
    
    async def test_metrics_tracking_on_recovery(self):
        """Test that metrics are tracked during recovery."""
        metrics = get_error_metrics()
        metrics.clear_all()
        
        tool = MockUnreliableTool(fail_count=1, enable_retry=True)
        tool.current_use_id = "test_005"
        
        result = await tool.execute_with_recovery({"value": "test"})
        
        # Check metrics
        tool_metrics = metrics.get_tool_metrics(tool.name)
        assert tool_metrics is not None
        assert tool_metrics.total_errors >= 1
        assert tool_metrics.success_after_retry >= 1


@pytest.mark.asyncio
class TestToolRegistryWithRetry:
    """Test tool registry with retry integration."""
    
    async def test_registry_execute_with_retry(self):
        """Test that registry uses execute_with_recovery for tools with retry enabled."""
        from roo_code.tools import ToolUse
        
        registry = ToolRegistry()
        tool = MockUnreliableTool(fail_count=1, enable_retry=True)
        registry.register(tool)
        
        tool_use = ToolUse(
            id="test_001",
            name="mock_unreliable_tool",
            input={"value": "test"}
        )
        
        result = await registry.execute(tool_use)
        
        assert not result.is_error
        assert "Success after 2 attempts" in result.content
    
    async def test_registry_execute_without_retry(self):
        """Test that registry respects retry disabled."""
        from roo_code.tools import ToolUse
        
        registry = ToolRegistry()
        tool = MockUnreliableTool(fail_count=1, enable_retry=False)
        registry.register(tool)
        
        tool_use = ToolUse(
            id="test_002",
            name="mock_unreliable_tool",
            input={"value": "test"}
        )
        
        result = await registry.execute(tool_use)
        
        # Should fail on first attempt
        assert result.is_error
        assert tool.attempts == 1


@pytest.mark.asyncio
class TestCircuitBreakerIntegration:
    """Test circuit breaker integration with tools."""
    
    async def test_tool_with_circuit_breaker(self):
        """Test tool execution with circuit breaker."""
        
        class CircuitBreakerTool(Tool):
            def __init__(self, should_fail: bool = False):
                self.should_fail = should_fail
                self.call_count = 0
                super().__init__(
                    name="circuit_breaker_tool",
                    description="Tool with circuit breaker",
                    input_schema=ToolInputSchema(
                        type="object",
                        properties={}
                    ),
                    enable_retry=True,
                    enable_circuit_breaker=True
                )
            
            async def execute(self, input_data: dict) -> ToolResult:
                self.call_count += 1
                if self.should_fail:
                    raise NetworkError("Service unavailable")
                return ToolResult(
                    tool_use_id=self.current_use_id or "test",
                    content=f"Success #{self.call_count}"
                )
        
        tool = CircuitBreakerTool(should_fail=True)
        tool.current_use_id = "test_001"
        
        # Get circuit breaker
        breaker = tool.get_circuit_breaker()
        assert breaker is not None
        assert breaker.name == tool.name
        
        # Cause failures to open circuit
        failure_threshold = breaker.failure_threshold
        for i in range(failure_threshold):
            try:
                await tool.execute_with_recovery({})
            except:
                pass
        
        # Circuit should be open now
        assert breaker.is_open
        
        # Next call should be rejected by circuit breaker
        with pytest.raises(CircuitBreakerError):
            await tool.execute_with_recovery({})
    
    async def test_circuit_breaker_recovery(self):
        """Test that circuit breaker recovers when service returns."""
        
        class RecoverableTool(Tool):
            def __init__(self):
                self.should_fail = True
                self.call_count = 0
                super().__init__(
                    name="recoverable_tool",
                    description="Tool that recovers",
                    input_schema=ToolInputSchema(
                        type="object",
                        properties={}
                    ),
                    enable_retry=False,  # Disable retry to test circuit breaker alone
                    enable_circuit_breaker=True
                )
            
            async def execute(self, input_data: dict) -> ToolResult:
                self.call_count += 1
                if self.should_fail:
                    raise NetworkError("Failing")
                return ToolResult(
                    tool_use_id=self.current_use_id or "test",
                    content="Success"
                )
        
        tool = RecoverableTool()
        tool.current_use_id = "test_002"
        
        breaker = tool.get_circuit_breaker()
        # Use a short recovery timeout for testing
        breaker.recovery_timeout = 0.1
        
        # Open the circuit
        for i in range(breaker.failure_threshold):
            try:
                await tool.execute_with_recovery({})
            except:
                pass
        
        assert breaker.is_open
        
        # Service recovers
        tool.should_fail = False
        
        # Wait for recovery timeout
        await asyncio.sleep(0.15)
        
        # Should succeed now (circuit transitions to HALF_OPEN then CLOSED)
        result = await tool.execute_with_recovery({})
        assert not result.is_error


@pytest.mark.asyncio
class TestErrorMetricsIntegration:
    """Test error metrics integration with tools."""
    
    async def test_metrics_recorded_on_error(self):
        """Test that errors are recorded in metrics."""
        metrics = get_error_metrics()
        metrics.clear_all()
        
        tool = MockUnreliableTool(fail_count=2, enable_retry=True)
        tool.current_use_id = "test_001"
        
        # Execute with errors
        await tool.execute_with_recovery({"value": "test"})
        
        # Check error history
        history = metrics.get_error_history(tool.name)
        assert len(history) >= 2  # At least 2 errors before success
        
        # Check tool metrics
        tool_metrics = metrics.get_tool_metrics(tool.name)
        assert tool_metrics is not None
        assert tool_metrics.total_errors >= 2
    
    async def test_metrics_permanent_failure(self):
        """Test that permanent failures are tracked."""
        metrics = get_error_metrics()
        metrics.clear_all()
        
        tool = MockUnreliableTool(fail_count=10, enable_retry=True)  # More failures than retries
        tool.current_use_id = "test_002"
        
        # This will exhaust retries
        try:
            await tool.execute_with_recovery({"value": "test"})
        except:
            pass
        
        # Should have recorded permanent failure
        stats = metrics.get_global_statistics()
        assert stats["total_permanent_failures"] >= 1
    
    async def test_metrics_error_rate(self):
        """Test error rate calculation."""
        metrics = get_error_metrics()
        metrics.clear_all()
        
        tool = MockUnreliableTool(fail_count=1, enable_retry=True)
        
        # Generate some errors
        for i in range(3):
            tool.current_use_id = f"test_{i}"
            tool.attempts = 0  # Reset attempts
            await tool.execute_with_recovery({"value": "test"})
        
        # Check error rate
        error_rate = metrics.get_error_rate(tool.name, time_window_minutes=60)
        assert error_rate > 0


@pytest.mark.asyncio
class TestCompleteWorkflow:
    """Test complete error recovery workflow end-to-end."""
    
    async def test_full_recovery_workflow(self):
        """Test complete recovery workflow: retry -> metrics -> success."""
        # Set up clean environment
        recovery_manager = ErrorRecoveryManager(
            max_retries=3,
            backoff_factor=1.5,
            initial_delay=0.01
        )
        metrics = get_error_metrics()
        metrics.clear_all()
        
        # Create tool with retry enabled
        tool = MockUnreliableTool(fail_count=2, enable_retry=True)
        tool.current_use_id = "workflow_test"
        
        # Override recovery manager for this test
        tool._recovery_manager = recovery_manager
        
        # Execute
        result = await tool.execute_with_recovery({"value": "test"})
        
        # Verify success
        assert not result.is_error
        assert "Success after 3 attempts" in result.content
        
        # Verify metrics
        tool_metrics = metrics.get_tool_metrics(tool.name)
        assert tool_metrics is not None
        assert tool_metrics.total_errors == 2
        assert tool_metrics.success_after_retry >= 1
        
        # Verify error history
        history = recovery_manager.get_error_history(tool.name)
        assert len(history) == 2
        
        # Verify all errors were NetworkError (recoverable)
        assert all(isinstance(ctx.error, NetworkError) for ctx in history)
    
    async def test_workflow_with_circuit_breaker(self):
        """Test workflow with both retry and circuit breaker."""
        
        class FullyProtectedTool(Tool):
            def __init__(self):
                self.call_count = 0
                self.fail_until = 5
                super().__init__(
                    name="fully_protected",
                    description="Tool with all protections",
                    input_schema=ToolInputSchema(
                        type="object",
                        properties={}
                    ),
                    enable_retry=True,
                    enable_circuit_breaker=True
                )
            
            async def execute(self, input_data: dict) -> ToolResult:
                self.call_count += 1
                if self.call_count <= self.fail_until:
                    raise NetworkError(f"Fail #{self.call_count}")
                return ToolResult(
                    tool_use_id=self.current_use_id or "test",
                    content="Success"
                )
        
        tool = FullyProtectedTool()
        tool.current_use_id = "test_001"
        
        # Configure short timeouts for testing
        breaker = tool.get_circuit_breaker()
        breaker.failure_threshold = 3
        breaker.recovery_timeout = 0.1
        
        # This should open the circuit
        try:
            await tool.execute_with_recovery({})
        except:
            pass
        
        # Circuit should be open
        assert breaker.is_open
        
        # Service "recovers"
        tool.fail_until = 0
        
        # Wait for recovery
        await asyncio.sleep(0.15)
        
        # Should succeed now
        result = await tool.execute_with_recovery({})
        assert not result.is_error


@pytest.mark.asyncio
class TestRealWorldScenarios:
    """Test real-world error scenarios."""
    
    async def test_intermittent_network_errors(self):
        """Test handling intermittent network errors."""
        
        class NetworkFlakeyTool(Tool):
            def __init__(self):
                self.attempts = 0
                self.fail_pattern = [True, False, True, False]  # Intermittent failures
                super().__init__(
                    name="network_flakey",
                    description="Tool with intermittent failures",
                    input_schema=ToolInputSchema(
                        type="object",
                        properties={}
                    ),
                    enable_retry=True
                )
            
            async def execute(self, input_data: dict) -> ToolResult:
                should_fail = self.fail_pattern[
                    self.attempts % len(self.fail_pattern)
                ]
                self.attempts += 1
                
                if should_fail:
                    raise NetworkError("Intermittent network error")
                
                return ToolResult(
                    tool_use_id=self.current_use_id or "test",
                    content=f"Success on attempt {self.attempts}"
                )
        
        tool = NetworkFlakeyTool()
        tool.current_use_id = "test_001"
        
        # Should succeed on second attempt (first fails, second succeeds)
        result = await tool.execute_with_recovery({})
        assert not result.is_error
        assert "attempt 2" in result.content
    
    async def test_rate_limit_backoff(self):
        """Test handling rate limit errors with custom backoff."""
        from roo_code.builtin_tools.error_recovery import RateLimitError
        
        class RateLimitedTool(Tool):
            def __init__(self):
                self.attempts = 0
                super().__init__(
                    name="rate_limited",
                    description="Tool that hits rate limits",
                    input_schema=ToolInputSchema(
                        type="object",
                        properties={}
                    ),
                    enable_retry=True
                )
            
            async def execute(self, input_data: dict) -> ToolResult:
                self.attempts += 1
                if self.attempts == 1:
                    # First attempt hits rate limit with retry_after
                    raise RateLimitError("Rate limit exceeded", retry_after=0.05)
                
                return ToolResult(
                    tool_use_id=self.current_use_id or "test",
                    content="Success"
                )
        
        tool = RateLimitedTool()
        tool.current_use_id = "test_001"
        
        # Should respect retry_after and succeed on second attempt
        result = await tool.execute_with_recovery({})
        assert not result.is_error
        assert tool.attempts == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])