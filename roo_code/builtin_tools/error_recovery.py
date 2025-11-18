"""Error recovery mechanisms for tools.

This module provides comprehensive error recovery capabilities including:
- Automatic retry with exponential backoff
- Error classification (recoverable vs non-recoverable)
- Custom recovery strategies
- Error context tracking
"""

import asyncio
import logging
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar, Awaitable
from enum import Enum

logger = logging.getLogger(__name__)

T = TypeVar('T')


# Error Type Hierarchy
class RecoverableError(Exception):
    """Base class for errors that can be recovered through retry."""
    pass


class NonRecoverableError(Exception):
    """Base class for errors that should not be retried."""
    pass


class NetworkError(RecoverableError):
    """Network-related error that may be transient."""
    pass


class RateLimitError(RecoverableError):
    """API rate limit exceeded, should retry with longer backoff."""
    
    def __init__(self, message: str, retry_after: Optional[int] = None):
        super().__init__(message)
        self.retry_after = retry_after


class TimeoutError(RecoverableError):
    """Operation timed out."""
    pass


class ValidationError(NonRecoverableError):
    """Invalid input that cannot be fixed by retrying."""
    pass


class FileNotFoundError(NonRecoverableError):
    """File or resource not found."""
    pass


class PermissionError(NonRecoverableError):
    """Insufficient permissions."""
    pass


@dataclass
class ErrorContext:
    """Context information about an error occurrence.
    
    Attributes:
        tool_name: Name of the tool that encountered the error
        use_id: Unique identifier for this tool use
        error: The exception that occurred
        attempt_number: Which retry attempt this was (1-indexed)
        timestamp: When the error occurred
        parameters: Input parameters that caused the error
        stack_trace: Full stack trace of the error
    """
    tool_name: str
    use_id: str
    error: Exception
    attempt_number: int
    timestamp: datetime = field(default_factory=datetime.now)
    parameters: Dict[str, Any] = field(default_factory=dict)
    stack_trace: str = field(default_factory=str)
    
    def __post_init__(self):
        if not self.stack_trace:
            self.stack_trace = ''.join(traceback.format_exception(
                type(self.error), self.error, self.error.__traceback__
            ))


class RetryStrategy(Enum):
    """Available retry strategies."""
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    FIXED_DELAY = "fixed_delay"
    LINEAR_BACKOFF = "linear_backoff"


class ErrorRecoveryManager:
    """Manages error recovery strategies across all tools.
    
    This class provides automatic retry logic with configurable strategies,
    error classification, and custom recovery handlers.
    
    Example:
        ```python
        manager = ErrorRecoveryManager(max_retries=3, backoff_factor=2.0)
        
        # Execute with automatic retry
        result = await manager.execute_with_recovery(
            risky_operation,
            arg1="value",
            timeout=30
        )
        
        # Register custom recovery strategy
        async def fallback_to_cache(ctx: ErrorContext):
            return cache.get(ctx.parameters["key"])
        
        manager.register_recovery_strategy(
            NetworkError,
            fallback_to_cache
        )
        ```
    """
    
    def __init__(
        self,
        max_retries: int = 3,
        backoff_factor: float = 2.0,
        retry_on: Optional[List[Type[Exception]]] = None,
        retry_strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF,
        initial_delay: float = 1.0,
        max_delay: float = 60.0,
    ):
        """Initialize error recovery manager.
        
        Args:
            max_retries: Maximum number of retry attempts
            backoff_factor: Multiplier for exponential backoff
            retry_on: List of exception types to retry (default: all RecoverableError)
            retry_strategy: Strategy to use for retry delays
            initial_delay: Initial delay in seconds before first retry
            max_delay: Maximum delay in seconds between retries
        """
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.retry_on = retry_on or [RecoverableError]
        self.retry_strategy = retry_strategy
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        
        # Custom recovery strategies per error type
        self._recovery_strategies: Dict[Type[Exception], Callable[[ErrorContext], Awaitable[Any]]] = {}
        
        # Error history for analysis
        self._error_history: List[ErrorContext] = []
    
    def register_recovery_strategy(
        self,
        error_type: Type[Exception],
        strategy: Callable[[ErrorContext], Awaitable[Any]]
    ) -> None:
        """Register a custom recovery strategy for a specific error type.
        
        Args:
            error_type: Exception type to handle
            strategy: Async function that takes ErrorContext and returns recovery result
        """
        self._recovery_strategies[error_type] = strategy
        logger.info(f"Registered recovery strategy for {error_type.__name__}")
    
    def _should_retry(self, error: Exception) -> bool:
        """Determine if an error should be retried.
        
        Args:
            error: Exception that occurred
            
        Returns:
            True if error is recoverable and should be retried
        """
        # Never retry NonRecoverableError
        if isinstance(error, NonRecoverableError):
            return False
        
        # Check if error type is in retry list
        for error_type in self.retry_on:
            if isinstance(error, error_type):
                return True
        
        return False
    
    def _calculate_delay(self, attempt: int, error: Optional[Exception] = None) -> float:
        """Calculate delay before next retry attempt.
        
        Args:
            attempt: Current attempt number (1-indexed)
            error: Optional error that may influence delay (e.g., RateLimitError)
            
        Returns:
            Delay in seconds
        """
        # Handle rate limit errors with specific retry_after
        if isinstance(error, RateLimitError) and error.retry_after:
            return float(error.retry_after)
        
        if self.retry_strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
            delay = self.initial_delay * (self.backoff_factor ** (attempt - 1))
        elif self.retry_strategy == RetryStrategy.LINEAR_BACKOFF:
            delay = self.initial_delay * attempt
        else:  # FIXED_DELAY
            delay = self.initial_delay
        
        return min(delay, self.max_delay)
    
    async def execute_with_recovery(
        self,
        func: Callable[..., Awaitable[T]],
        *args,
        tool_name: str = "unknown",
        use_id: str = "unknown",
        timeout: Optional[float] = None,
        **kwargs
    ) -> T:
        """Execute a function with automatic retry logic.
        
        Args:
            func: Async function to execute
            *args: Positional arguments for func
            tool_name: Name of the tool executing this function
            use_id: Unique identifier for this execution
            timeout: Optional timeout in seconds
            **kwargs: Keyword arguments for func
            
        Returns:
            Result of successful function execution
            
        Raises:
            Exception: If all retries are exhausted or error is non-recoverable
        """
        last_error: Optional[Exception] = None
        
        for attempt in range(1, self.max_retries + 1):
            try:
                # Apply timeout if specified
                if timeout:
                    return await asyncio.wait_for(func(*args, **kwargs), timeout=timeout)
                else:
                    return await func(*args, **kwargs)
                    
            except asyncio.TimeoutError as e:
                # Convert to our TimeoutError for consistent handling
                last_error = TimeoutError(f"Operation timed out after {timeout}s")
                last_error.__cause__ = e
                
            except Exception as e:
                last_error = e
            
            # Create error context
            error_context = ErrorContext(
                tool_name=tool_name,
                use_id=use_id,
                error=last_error,
                attempt_number=attempt,
                parameters={"args": args, "kwargs": kwargs}
            )
            self._error_history.append(error_context)
            
            # Log the error
            logger.warning(
                f"Attempt {attempt}/{self.max_retries} failed for {tool_name}: "
                f"{type(last_error).__name__}: {str(last_error)}"
            )
            
            # Check if we should retry
            if not self._should_retry(last_error):
                logger.error(f"Non-recoverable error in {tool_name}, not retrying")
                raise last_error
            
            # Try custom recovery strategy if available
            for error_type, strategy in self._recovery_strategies.items():
                if isinstance(last_error, error_type):
                    logger.info(f"Trying custom recovery strategy for {error_type.__name__}")
                    try:
                        return await strategy(error_context)
                    except Exception as recovery_error:
                        logger.warning(
                            f"Recovery strategy failed: {type(recovery_error).__name__}: "
                            f"{str(recovery_error)}"
                        )
                        # Continue with normal retry logic
                        break
            
            # If this wasn't the last attempt, wait before retrying
            if attempt < self.max_retries:
                delay = self._calculate_delay(attempt, last_error)
                logger.info(f"Waiting {delay:.2f}s before retry {attempt + 1}")
                await asyncio.sleep(delay)
            else:
                logger.error(f"All {self.max_retries} retries exhausted for {tool_name}")
        
        # All retries exhausted
        raise last_error
    
    def get_error_history(self, tool_name: Optional[str] = None) -> List[ErrorContext]:
        """Get error history, optionally filtered by tool name.
        
        Args:
            tool_name: Optional tool name to filter by
            
        Returns:
            List of error contexts
        """
        if tool_name:
            return [ctx for ctx in self._error_history if ctx.tool_name == tool_name]
        return self._error_history.copy()
    
    def clear_history(self) -> None:
        """Clear error history."""
        self._error_history.clear()
    
    def get_error_count(self, tool_name: Optional[str] = None) -> int:
        """Get total error count.
        
        Args:
            tool_name: Optional tool name to filter by
            
        Returns:
            Number of errors
        """
        if tool_name:
            return len([ctx for ctx in self._error_history if ctx.tool_name == tool_name])
        return len(self._error_history)


# Global instance for convenience
_global_recovery_manager: Optional[ErrorRecoveryManager] = None


def get_recovery_manager() -> ErrorRecoveryManager:
    """Get or create the global error recovery manager.
    
    Returns:
        Global ErrorRecoveryManager instance
    """
    global _global_recovery_manager
    if _global_recovery_manager is None:
        _global_recovery_manager = ErrorRecoveryManager()
    return _global_recovery_manager


def set_recovery_manager(manager: ErrorRecoveryManager) -> None:
    """Set the global error recovery manager.
    
    Args:
        manager: ErrorRecoveryManager instance to use globally
    """
    global _global_recovery_manager
    _global_recovery_manager = manager