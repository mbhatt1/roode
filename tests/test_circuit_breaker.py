"""Tests for circuit breaker pattern."""

import asyncio
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock

from roo_code.builtin_tools.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerError,
    CircuitBreakerRegistry,
    CircuitState,
    get_circuit_breaker_registry
)


class UnreliableService:
    """Mock service that can fail or succeed on demand."""
    
    def __init__(self):
        self.call_count = 0
        self.should_fail = True
    
    async def call(self) -> str:
        """Call service, failing if should_fail is True."""
        self.call_count += 1
        if self.should_fail:
            raise Exception(f"Service failure #{self.call_count}")
        return f"Success #{self.call_count}"


@pytest.mark.asyncio
class TestCircuitBreaker:
    """Test circuit breaker functionality."""
    
    async def test_closed_state_allows_requests(self):
        """Test that CLOSED state allows all requests through."""
        breaker = CircuitBreaker(name="test", failure_threshold=3)
        service = UnreliableService()
        service.should_fail = False
        
        assert breaker.state == CircuitState.CLOSED
        
        result = await breaker.call(service.call)
        assert result == "Success #1"
        assert service.call_count == 1
    
    async def test_open_after_threshold_failures(self):
        """Test circuit opens after failure threshold is reached."""
        breaker = CircuitBreaker(name="test", failure_threshold=3)
        service = UnreliableService()
        service.should_fail = True
        
        # Cause failures up to threshold
        for i in range(3):
            with pytest.raises(Exception):
                await breaker.call(service.call)
        
        assert breaker.state == CircuitState.OPEN
        assert service.call_count == 3
    
    async def test_open_state_rejects_requests(self):
        """Test that OPEN state rejects requests immediately."""
        breaker = CircuitBreaker(
            name="test",
            failure_threshold=2,
            recovery_timeout=60
        )
        service = UnreliableService()
        service.should_fail = True
        
        # Open the circuit
        for i in range(2):
            with pytest.raises(Exception):
                await breaker.call(service.call)
        
        assert breaker.state == CircuitState.OPEN
        
        # Next call should be rejected without calling service
        call_count_before = service.call_count
        with pytest.raises(CircuitBreakerError) as exc_info:
            await breaker.call(service.call)
        
        assert service.call_count == call_count_before  # No new call
        assert "Circuit breaker 'test' is OPEN" in str(exc_info.value)
    
    async def test_half_open_after_timeout(self):
        """Test circuit transitions to HALF_OPEN after recovery timeout."""
        breaker = CircuitBreaker(
            name="test",
            failure_threshold=2,
            recovery_timeout=0.1  # Short timeout for testing
        )
        service = UnreliableService()
        service.should_fail = True
        
        # Open the circuit
        for i in range(2):
            with pytest.raises(Exception):
                await breaker.call(service.call)
        
        assert breaker.state == CircuitState.OPEN
        
        # Wait for recovery timeout
        await asyncio.sleep(0.15)
        
        # Next call should transition to HALF_OPEN and execute
        service.should_fail = False
        result = await breaker.call(service.call)
        
        # After successful call, should transition to CLOSED
        assert breaker.state == CircuitState.CLOSED
        assert result.startswith("Success")
    
    async def test_half_open_success_closes_circuit(self):
        """Test that successes in HALF_OPEN state close the circuit."""
        breaker = CircuitBreaker(
            name="test",
            failure_threshold=2,
            recovery_timeout=0.1,
            success_threshold=2  # Need 2 successes
        )
        service = UnreliableService()
        service.should_fail = True
        
        # Open the circuit
        for i in range(2):
            with pytest.raises(Exception):
                await breaker.call(service.call)
        
        assert breaker.state == CircuitState.OPEN
        
        # Wait and recover
        await asyncio.sleep(0.15)
        service.should_fail = False
        
        # First success
        await breaker.call(service.call)
        assert breaker.state == CircuitState.HALF_OPEN
        
        # Second success should close circuit
        await breaker.call(service.call)
        assert breaker.state == CircuitState.CLOSED
    
    async def test_half_open_failure_reopens_circuit(self):
        """Test that failure in HALF_OPEN reopens the circuit."""
        breaker = CircuitBreaker(
            name="test",
            failure_threshold=2,
            recovery_timeout=0.1
        )
        service = UnreliableService()
        service.should_fail = True
        
        # Open the circuit
        for i in range(2):
            with pytest.raises(Exception):
                await breaker.call(service.call)
        
        assert breaker.state == CircuitState.OPEN
        
        # Wait and try recovery but fail
        await asyncio.sleep(0.15)
        
        with pytest.raises(Exception):
            await breaker.call(service.call)
        
        # Should be back to OPEN
        assert breaker.state == CircuitState.OPEN
    
    async def test_half_open_max_calls_limit(self):
        """Test that HALF_OPEN limits concurrent calls."""
        breaker = CircuitBreaker(
            name="test",
            failure_threshold=1,
            recovery_timeout=0.1,
            half_open_max_calls=1
        )
        service = UnreliableService()
        service.should_fail = True
        
        # Open the circuit
        with pytest.raises(Exception):
            await breaker.call(service.call)
        
        # Wait for recovery
        await asyncio.sleep(0.15)
        
        # Start first call (will be slow)
        async def slow_call():
            await asyncio.sleep(0.2)
            return "slow"
        
        # First call should be allowed
        task1 = asyncio.create_task(breaker.call(slow_call))
        await asyncio.sleep(0.05)  # Let it start
        
        # Second call should be rejected (limit reached)
        with pytest.raises(CircuitBreakerError):
            await breaker.call(service.call)
        
        # Clean up
        task1.cancel()
        try:
            await task1
        except asyncio.CancelledError:
            pass
    
    async def test_success_resets_failure_count(self):
        """Test that successful calls reset failure count in CLOSED state."""
        breaker = CircuitBreaker(name="test", failure_threshold=3)
        service = UnreliableService()
        
        # Cause some failures (but not threshold)
        service.should_fail = True
        for i in range(2):
            with pytest.raises(Exception):
                await breaker.call(service.call)
        
        assert breaker.state == CircuitState.CLOSED
        
        # Successful call should reset failure count
        service.should_fail = False
        await breaker.call(service.call)
        
        # Now cause more failures - should need 3 more to open
        service.should_fail = True
        for i in range(2):
            with pytest.raises(Exception):
                await breaker.call(service.call)
        
        # Still closed (only 2 failures since last success)
        assert breaker.state == CircuitState.CLOSED
    
    async def test_manual_reset(self):
        """Test manual circuit reset."""
        breaker = CircuitBreaker(name="test", failure_threshold=1)
        service = UnreliableService()
        service.should_fail = True
        
        # Open the circuit
        with pytest.raises(Exception):
            await breaker.call(service.call)
        
        assert breaker.state == CircuitState.OPEN
        
        # Manual reset
        await breaker.reset()
        
        assert breaker.state == CircuitState.CLOSED
    
    async def test_statistics_tracking(self):
        """Test that statistics are properly tracked."""
        breaker = CircuitBreaker(name="test", failure_threshold=5)
        service = UnreliableService()
        
        # Make some successful calls
        service.should_fail = False
        for i in range(3):
            await breaker.call(service.call)
        
        # Make some failed calls
        service.should_fail = True
        for i in range(2):
            with pytest.raises(Exception):
                await breaker.call(service.call)
        
        stats = breaker.get_stats()
        
        assert stats.total_calls == 5
        assert stats.successful_calls == 3
        assert stats.failed_calls == 2
        assert stats.failure_rate == 0.4
        assert stats.success_rate == 0.6
    
    async def test_rejected_calls_tracked(self):
        """Test that rejected calls are tracked in statistics."""
        breaker = CircuitBreaker(
            name="test",
            failure_threshold=1,
            recovery_timeout=60
        )
        service = UnreliableService()
        service.should_fail = True
        
        # Open the circuit
        with pytest.raises(Exception):
            await breaker.call(service.call)
        
        # Try to call while open (will be rejected)
        for i in range(3):
            with pytest.raises(CircuitBreakerError):
                await breaker.call(service.call)
        
        stats = breaker.get_stats()
        assert stats.rejected_calls == 3
    
    async def test_expected_exception_type(self):
        """Test that only expected exception types count as failures."""
        breaker = CircuitBreaker(
            name="test",
            failure_threshold=2,
            expected_exception=ValueError
        )
        
        # ValueError should count as failure
        async def raises_value_error():
            raise ValueError("Expected")
        
        with pytest.raises(ValueError):
            await breaker.call(raises_value_error)
        
        assert breaker.state == CircuitState.CLOSED  # Only 1 failure
        
        with pytest.raises(ValueError):
            await breaker.call(raises_value_error)
        
        assert breaker.state == CircuitState.OPEN  # Now opened
        
        # Other exceptions should also count (fallback behavior)
        await breaker.reset()
        
        async def raises_runtime_error():
            raise RuntimeError("Unexpected")
        
        for i in range(2):
            with pytest.raises(RuntimeError):
                await breaker.call(raises_runtime_error)
        
        assert breaker.state == CircuitState.OPEN
    
    async def test_state_properties(self):
        """Test state checking properties."""
        breaker = CircuitBreaker(name="test", failure_threshold=1)
        
        assert breaker.is_closed
        assert not breaker.is_open
        assert not breaker.is_half_open
        
        # Open the circuit
        async def fails():
            raise Exception("Fail")
        
        with pytest.raises(Exception):
            await breaker.call(fails)
        
        assert not breaker.is_closed
        assert breaker.is_open
        assert not breaker.is_half_open


@pytest.mark.asyncio
class TestCircuitBreakerRegistry:
    """Test circuit breaker registry."""
    
    async def test_get_or_create_breaker(self):
        """Test creating and retrieving circuit breakers."""
        registry = CircuitBreakerRegistry()
        
        breaker1 = await registry.get_or_create(
            "service1",
            failure_threshold=5
        )
        
        assert breaker1.name == "service1"
        assert breaker1.failure_threshold == 5
        
        # Getting again should return same instance
        breaker2 = await registry.get_or_create("service1")
        assert breaker1 is breaker2
    
    async def test_get_existing_breaker(self):
        """Test retrieving existing breaker."""
        registry = CircuitBreakerRegistry()
        
        breaker1 = await registry.get_or_create("service1")
        breaker2 = registry.get("service1")
        
        assert breaker1 is breaker2
    
    async def test_get_nonexistent_breaker(self):
        """Test getting breaker that doesn't exist."""
        registry = CircuitBreakerRegistry()
        
        breaker = registry.get("nonexistent")
        assert breaker is None
    
    async def test_multiple_breakers(self):
        """Test managing multiple circuit breakers."""
        registry = CircuitBreakerRegistry()
        
        breaker1 = await registry.get_or_create("service1")
        breaker2 = await registry.get_or_create("service2")
        breaker3 = await registry.get_or_create("service3")
        
        assert breaker1 is not breaker2
        assert breaker2 is not breaker3
        assert breaker1.name == "service1"
        assert breaker2.name == "service2"
        assert breaker3.name == "service3"
    
    async def test_reset_all_breakers(self):
        """Test resetting all circuit breakers in registry."""
        registry = CircuitBreakerRegistry()
        
        # Create and open multiple breakers
        async def fails():
            raise Exception("Fail")
        
        for i in range(3):
            breaker = await registry.get_or_create(
                f"service{i}",
                failure_threshold=1
            )
            with pytest.raises(Exception):
                await breaker.call(fails)
            assert breaker.is_open
        
        # Reset all
        await registry.reset_all()
        
        # All should be closed now
        for i in range(3):
            breaker = registry.get(f"service{i}")
            assert breaker.is_closed
    
    async def test_get_all_stats(self):
        """Test getting statistics for all breakers."""
        registry = CircuitBreakerRegistry()
        
        # Create breakers and make some calls
        for i in range(2):
            breaker = await registry.get_or_create(f"service{i}")
            async def succeeds():
                return "ok"
            
            for _ in range(3):
                await breaker.call(succeeds)
        
        all_stats = registry.get_all_stats()
        
        assert len(all_stats) == 2
        assert "service0" in all_stats
        assert "service1" in all_stats
        assert all_stats["service0"].total_calls == 3
        assert all_stats["service1"].total_calls == 3


@pytest.mark.asyncio
class TestGlobalRegistry:
    """Test global circuit breaker registry."""
    
    async def test_global_registry_singleton(self):
        """Test that global registry is a singleton."""
        registry1 = get_circuit_breaker_registry()
        registry2 = get_circuit_breaker_registry()
        
        assert registry1 is registry2


@pytest.mark.asyncio
class TestCircuitBreakerError:
    """Test CircuitBreakerError exception."""
    
    async def test_error_message(self):
        """Test error message formatting."""
        next_retry = datetime.now() + timedelta(seconds=30)
        error = CircuitBreakerError("test_circuit", next_retry)
        
        assert "test_circuit" in str(error)
        assert "OPEN" in str(error)
        assert error.circuit_name == "test_circuit"
        assert error.next_retry_time == next_retry


@pytest.mark.asyncio
class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    async def test_zero_failure_threshold(self):
        """Test with failure_threshold=0 (should never open)."""
        breaker = CircuitBreaker(name="test", failure_threshold=0)
        
        async def fails():
            raise Exception("Fail")
        
        # Even many failures shouldn't open circuit
        for i in range(10):
            with pytest.raises(Exception):
                await breaker.call(fails)
        
        # Circuit should still be closed (threshold never reached)
        assert breaker.state == CircuitState.CLOSED
    
    async def test_very_short_recovery_timeout(self):
        """Test with very short recovery timeout."""
        breaker = CircuitBreaker(
            name="test",
            failure_threshold=1,
            recovery_timeout=0.01
        )
        
        async def fails():
            raise Exception("Fail")
        
        # Open circuit
        with pytest.raises(Exception):
            await breaker.call(fails)
        
        assert breaker.is_open
        
        # Wait for recovery
        await asyncio.sleep(0.02)
        
        # Should transition to HALF_OPEN on next call
        with pytest.raises(Exception):
            await breaker.call(fails)
        
        # Should be back to OPEN after failure in HALF_OPEN
        assert breaker.is_open
    
    async def test_concurrent_calls_in_closed_state(self):
        """Test multiple concurrent calls in CLOSED state."""
        breaker = CircuitBreaker(name="test", failure_threshold=5)
        
        async def slow_success():
            await asyncio.sleep(0.1)
            return "success"
        
        # Make multiple concurrent calls
        tasks = [breaker.call(slow_success) for _ in range(3)]
        results = await asyncio.gather(*tasks)
        
        assert all(r == "success" for r in results)
        assert breaker.get_stats().successful_calls == 3


@pytest.mark.asyncio
class TestIntegrationScenarios:
    """Test realistic integration scenarios."""
    
    async def test_flaky_service_recovery(self):
        """Test handling a flaky service that eventually recovers."""
        breaker = CircuitBreaker(
            name="flaky_service",
            failure_threshold=3,
            recovery_timeout=0.1,
            success_threshold=2
        )
        
        service = UnreliableService()
        service.should_fail = True
        
        # Cause failures to open circuit
        for i in range(3):
            with pytest.raises(Exception):
                await breaker.call(service.call)
        
        assert breaker.is_open
        
        # Service recovers
        service.should_fail = False
        
        # Wait for recovery timeout
        await asyncio.sleep(0.15)
        
        # Make successful calls to close circuit
        result1 = await breaker.call(service.call)
        assert breaker.is_half_open
        
        result2 = await breaker.call(service.call)
        assert breaker.is_closed
        
        # Circuit is now fully operational again
        result3 = await breaker.call(service.call)
        assert result3.startswith("Success")
    
    async def test_persistent_failure(self):
        """Test handling service that never recovers."""
        breaker = CircuitBreaker(
            name="dead_service",
            failure_threshold=2,
            recovery_timeout=0.05
        )
        
        service = UnreliableService()
        service.should_fail = True
        
        # Initial failures
        for i in range(2):
            with pytest.raises(Exception):
                await breaker.call(service.call)
        
        assert breaker.is_open
        
        # Try recovery multiple times, service still fails
        for attempt in range(3):
            await asyncio.sleep(0.06)
            
            with pytest.raises(Exception):
                await breaker.call(service.call)
            
            # Should be back to OPEN each time
            assert breaker.is_open
        
        # Service is effectively isolated
        stats = breaker.get_stats()
        assert stats.failed_calls > 0
        assert stats.rejected_calls > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])