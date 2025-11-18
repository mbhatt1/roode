"""Circuit breaker pattern implementation for preventing cascading failures.

The circuit breaker monitors failures and prevents repeated attempts to operations
that are likely to fail, following the three-state pattern:
- CLOSED: Normal operation, requests pass through
- OPEN: Too many failures, requests fail immediately
- HALF_OPEN: Testing if service recovered, limited requests allowed
"""

import asyncio
import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Optional, TypeVar, Awaitable
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

T = TypeVar('T')


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class CircuitBreakerStats:
    """Statistics for circuit breaker monitoring.
    
    Attributes:
        total_calls: Total number of calls attempted
        successful_calls: Number of successful calls
        failed_calls: Number of failed calls
        rejected_calls: Number of calls rejected while circuit open
        last_failure_time: Timestamp of last failure
        last_success_time: Timestamp of last success
        state_changes: Number of times state changed
    """
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    rejected_calls: int = 0
    last_failure_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None
    state_changes: int = 0
    
    @property
    def failure_rate(self) -> float:
        """Calculate failure rate (0.0 to 1.0)."""
        if self.total_calls == 0:
            return 0.0
        return self.failed_calls / self.total_calls
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate (0.0 to 1.0)."""
        return 1.0 - self.failure_rate


class CircuitBreakerError(Exception):
    """Raised when circuit breaker is open and rejects a call."""
    
    def __init__(self, circuit_name: str, next_retry_time: datetime):
        self.circuit_name = circuit_name
        self.next_retry_time = next_retry_time
        super().__init__(
            f"Circuit breaker '{circuit_name}' is OPEN. "
            f"Will retry at {next_retry_time.isoformat()}"
        )


class CircuitBreaker:
    """Circuit breaker to prevent cascading failures.
    
    The circuit breaker monitors failures and stops attempting operations
    that are consistently failing, allowing the system to recover.
    
    States:
    - CLOSED: Normal operation, all requests pass through
    - OPEN: Too many failures detected, requests are rejected immediately
    - HALF_OPEN: Testing if service recovered, limited requests allowed
    
    Example:
        ```python
        breaker = CircuitBreaker(
            name="api_service",
            failure_threshold=5,
            recovery_timeout=60,
            expected_exception=NetworkError
        )
        
        async def call_api():
            return await breaker.call(make_api_request, arg1="value")
        ```
    """
    
    def __init__(
        self,
        name: str = "default",
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: type[Exception] = Exception,
        success_threshold: int = 2,
        half_open_max_calls: int = 1,
    ):
        """Initialize circuit breaker.
        
        Args:
            name: Name for this circuit breaker (for logging/monitoring)
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds before attempting recovery (OPEN -> HALF_OPEN)
            expected_exception: Exception type that counts as failure
            success_threshold: Consecutive successes needed to close circuit from HALF_OPEN
            half_open_max_calls: Max concurrent calls allowed in HALF_OPEN state
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.success_threshold = success_threshold
        self.half_open_max_calls = half_open_max_calls
        
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[datetime] = None
        self._opened_at: Optional[datetime] = None
        self._half_open_calls = 0
        self._lock = asyncio.Lock()
        
        self.stats = CircuitBreakerStats()
        
        logger.info(
            f"Circuit breaker '{name}' initialized: "
            f"failure_threshold={failure_threshold}, "
            f"recovery_timeout={recovery_timeout}s"
        )
    
    @property
    def state(self) -> CircuitState:
        """Get current circuit state."""
        return self._state
    
    @property
    def is_closed(self) -> bool:
        """Check if circuit is closed (normal operation)."""
        return self._state == CircuitState.CLOSED
    
    @property
    def is_open(self) -> bool:
        """Check if circuit is open (rejecting calls)."""
        return self._state == CircuitState.OPEN
    
    @property
    def is_half_open(self) -> bool:
        """Check if circuit is half-open (testing recovery)."""
        return self._state == CircuitState.HALF_OPEN
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset from OPEN to HALF_OPEN."""
        if self._state != CircuitState.OPEN or self._opened_at is None:
            return False
        
        elapsed = (datetime.now() - self._opened_at).total_seconds()
        return elapsed >= self.recovery_timeout
    
    async def _transition_to(self, new_state: CircuitState) -> None:
        """Transition to a new state.
        
        Args:
            new_state: State to transition to
        """
        old_state = self._state
        self._state = new_state
        self.stats.state_changes += 1
        
        if new_state == CircuitState.OPEN:
            self._opened_at = datetime.now()
            logger.warning(
                f"Circuit breaker '{self.name}' opened after {self._failure_count} failures"
            )
        elif new_state == CircuitState.HALF_OPEN:
            self._half_open_calls = 0
            logger.info(f"Circuit breaker '{self.name}' half-opened for testing")
        elif new_state == CircuitState.CLOSED:
            self._failure_count = 0
            self._success_count = 0
            self._opened_at = None
            logger.info(f"Circuit breaker '{self.name}' closed")
        
        if old_state != new_state:
            logger.debug(
                f"Circuit breaker '{self.name}' state: {old_state.value} -> {new_state.value}"
            )
    
    async def _on_success(self) -> None:
        """Handle successful call."""
        async with self._lock:
            self.stats.successful_calls += 1
            self.stats.last_success_time = datetime.now()
            
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                self._half_open_calls -= 1
                
                if self._success_count >= self.success_threshold:
                    await self._transition_to(CircuitState.CLOSED)
            
            elif self._state == CircuitState.CLOSED:
                # Reset failure count on success
                self._failure_count = 0
    
    async def _on_failure(self, error: Exception) -> None:
        """Handle failed call.
        
        Args:
            error: Exception that caused the failure
        """
        async with self._lock:
            self.stats.failed_calls += 1
            self.stats.last_failure_time = datetime.now()
            self._last_failure_time = datetime.now()
            
            if self._state == CircuitState.HALF_OPEN:
                # Any failure in HALF_OPEN reopens the circuit
                self._half_open_calls -= 1
                await self._transition_to(CircuitState.OPEN)
            
            elif self._state == CircuitState.CLOSED:
                self._failure_count += 1
                
                if self._failure_count >= self.failure_threshold:
                    await self._transition_to(CircuitState.OPEN)
    
    async def call(
        self,
        func: Callable[..., Awaitable[T]],
        *args,
        **kwargs
    ) -> T:
        """Execute function with circuit breaker protection.
        
        Args:
            func: Async function to execute
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func
            
        Returns:
            Result of successful function execution
            
        Raises:
            CircuitBreakerError: If circuit is open
            Exception: If function raises expected_exception or other error
        """
        async with self._lock:
            self.stats.total_calls += 1
            
            # Check if we should transition from OPEN to HALF_OPEN
            if self._state == CircuitState.OPEN and self._should_attempt_reset():
                await self._transition_to(CircuitState.HALF_OPEN)
            
            # Reject if circuit is open
            if self._state == CircuitState.OPEN:
                self.stats.rejected_calls += 1
                next_retry = self._opened_at + timedelta(seconds=self.recovery_timeout)
                raise CircuitBreakerError(self.name, next_retry)
            
            # Limit concurrent calls in HALF_OPEN state
            if self._state == CircuitState.HALF_OPEN:
                if self._half_open_calls >= self.half_open_max_calls:
                    self.stats.rejected_calls += 1
                    next_retry = datetime.now() + timedelta(seconds=1)
                    raise CircuitBreakerError(self.name, next_retry)
                self._half_open_calls += 1
        
        # Execute the function
        try:
            result = await func(*args, **kwargs)
            await self._on_success()
            return result
            
        except self.expected_exception as e:
            await self._on_failure(e)
            raise
        except Exception as e:
            # Unexpected errors also count as failures
            await self._on_failure(e)
            raise
    
    async def reset(self) -> None:
        """Manually reset the circuit breaker to CLOSED state."""
        async with self._lock:
            await self._transition_to(CircuitState.CLOSED)
            logger.info(f"Circuit breaker '{self.name}' manually reset")
    
    def get_stats(self) -> CircuitBreakerStats:
        """Get current statistics.
        
        Returns:
            Copy of current statistics
        """
        return CircuitBreakerStats(
            total_calls=self.stats.total_calls,
            successful_calls=self.stats.successful_calls,
            failed_calls=self.stats.failed_calls,
            rejected_calls=self.stats.rejected_calls,
            last_failure_time=self.stats.last_failure_time,
            last_success_time=self.stats.last_success_time,
            state_changes=self.stats.state_changes,
        )


class CircuitBreakerRegistry:
    """Registry for managing multiple circuit breakers.
    
    Example:
        ```python
        registry = CircuitBreakerRegistry()
        
        # Get or create circuit breaker
        breaker = registry.get_or_create(
            "api_service",
            failure_threshold=5,
            recovery_timeout=60
        )
        
        # Use circuit breaker
        result = await breaker.call(make_api_request)
        ```
    """
    
    def __init__(self):
        """Initialize circuit breaker registry."""
        self._breakers: dict[str, CircuitBreaker] = {}
        self._lock = asyncio.Lock()
    
    async def get_or_create(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: type[Exception] = Exception,
        **kwargs
    ) -> CircuitBreaker:
        """Get existing circuit breaker or create new one.
        
        Args:
            name: Name for the circuit breaker
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds before attempting recovery
            expected_exception: Exception type that counts as failure
            **kwargs: Additional CircuitBreaker parameters
            
        Returns:
            CircuitBreaker instance
        """
        async with self._lock:
            if name not in self._breakers:
                self._breakers[name] = CircuitBreaker(
                    name=name,
                    failure_threshold=failure_threshold,
                    recovery_timeout=recovery_timeout,
                    expected_exception=expected_exception,
                    **kwargs
                )
            return self._breakers[name]
    
    def get(self, name: str) -> Optional[CircuitBreaker]:
        """Get circuit breaker by name.
        
        Args:
            name: Name of the circuit breaker
            
        Returns:
            CircuitBreaker instance or None if not found
        """
        return self._breakers.get(name)
    
    async def reset_all(self) -> None:
        """Reset all circuit breakers to CLOSED state."""
        async with self._lock:
            for breaker in self._breakers.values():
                await breaker.reset()
    
    def get_all_stats(self) -> dict[str, CircuitBreakerStats]:
        """Get statistics for all circuit breakers.
        
        Returns:
            Dictionary mapping breaker names to their statistics
        """
        return {
            name: breaker.get_stats()
            for name, breaker in self._breakers.items()
        }


# Global registry instance
_global_registry: Optional[CircuitBreakerRegistry] = None


def get_circuit_breaker_registry() -> CircuitBreakerRegistry:
    """Get or create the global circuit breaker registry.
    
    Returns:
        Global CircuitBreakerRegistry instance
    """
    global _global_registry
    if _global_registry is None:
        _global_registry = CircuitBreakerRegistry()
    return _global_registry