"""Error metrics tracking and analysis.

This module provides detailed tracking and analysis of errors across the system,
including error rates, most common errors, and tool-specific statistics.
"""

import logging
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

from .error_recovery import ErrorContext

logger = logging.getLogger(__name__)


@dataclass
class ErrorStatistics:
    """Statistics for a specific error type or tool.
    
    Attributes:
        total_errors: Total number of errors
        first_seen: When this error was first seen
        last_seen: When this error was last seen
        error_rate: Errors per minute (calculated)
        avg_attempts_to_success: Average retry attempts before success
    """
    total_errors: int = 0
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    error_rate: float = 0.0
    avg_attempts_to_success: float = 0.0
    
    def update(self, error_time: datetime, attempt_number: int) -> None:
        """Update statistics with new error.
        
        Args:
            error_time: When the error occurred
            attempt_number: Which attempt this was
        """
        self.total_errors += 1
        
        if self.first_seen is None:
            self.first_seen = error_time
        self.last_seen = error_time
        
        # Update average attempts
        if attempt_number > 1:
            # This is a retry, so track it
            if self.avg_attempts_to_success == 0.0:
                self.avg_attempts_to_success = float(attempt_number)
            else:
                # Running average
                self.avg_attempts_to_success = (
                    (self.avg_attempts_to_success + attempt_number) / 2
                )


@dataclass
class ToolMetrics:
    """Metrics for a specific tool.
    
    Attributes:
        tool_name: Name of the tool
        total_errors: Total number of errors
        error_types: Counter of error types
        last_24h_errors: Errors in last 24 hours
        success_after_retry: Number of times retry led to success
        permanent_failures: Number of permanent failures
    """
    tool_name: str
    total_errors: int = 0
    error_types: Counter = field(default_factory=Counter)
    last_24h_errors: int = 0
    success_after_retry: int = 0
    permanent_failures: int = 0
    
    @property
    def retry_success_rate(self) -> float:
        """Calculate success rate of retries."""
        total_retries = self.success_after_retry + self.permanent_failures
        if total_retries == 0:
            return 0.0
        return self.success_after_retry / total_retries


class ErrorMetrics:
    """Track error statistics for analysis and monitoring.
    
    This class provides detailed metrics about errors occurring across
    the system, including error rates, common error types, and tool-specific
    statistics.
    
    Example:
        ```python
        metrics = ErrorMetrics()
        
        # Record error
        error_context = ErrorContext(
            tool_name="execute_command",
            use_id="123",
            error=NetworkError("Connection timeout"),
            attempt_number=1
        )
        metrics.record_error(error_context)
        
        # Get statistics
        rate = metrics.get_error_rate("execute_command")
        common = metrics.get_most_common_errors(limit=10)
        ```
    """
    
    def __init__(self, retention_days: int = 7):
        """Initialize error metrics tracker.
        
        Args:
            retention_days: Number of days to retain error history
        """
        self.retention_days = retention_days
        
        # Error history
        self._error_history: List[ErrorContext] = []
        
        # Statistics by error type
        self._error_stats: Dict[str, ErrorStatistics] = defaultdict(ErrorStatistics)
        
        # Statistics by tool
        self._tool_metrics: Dict[str, ToolMetrics] = {}
        
        # Global counters
        self._total_errors = 0
        self._total_recoveries = 0
        self._total_permanent_failures = 0
    
    def record_error(self, context: ErrorContext) -> None:
        """Record an error occurrence.
        
        Args:
            context: Error context to record
        """
        self._error_history.append(context)
        self._total_errors += 1
        
        # Update error type statistics
        error_type = type(context.error).__name__
        self._error_stats[error_type].update(
            context.timestamp,
            context.attempt_number
        )
        
        # Update tool metrics
        if context.tool_name not in self._tool_metrics:
            self._tool_metrics[context.tool_name] = ToolMetrics(
                tool_name=context.tool_name
            )
        
        tool_metrics = self._tool_metrics[context.tool_name]
        tool_metrics.total_errors += 1
        tool_metrics.error_types[error_type] += 1
        
        # Check if this is within last 24 hours
        if (datetime.now() - context.timestamp) < timedelta(days=1):
            tool_metrics.last_24h_errors += 1
        
        logger.debug(
            f"Recorded error: {error_type} in {context.tool_name} "
            f"(attempt {context.attempt_number})"
        )
        
        # Cleanup old records
        self._cleanup_old_records()
    
    def record_recovery(self, tool_name: str) -> None:
        """Record a successful recovery after retry.
        
        Args:
            tool_name: Name of tool that recovered
        """
        self._total_recoveries += 1
        
        if tool_name in self._tool_metrics:
            self._tool_metrics[tool_name].success_after_retry += 1
    
    def record_permanent_failure(self, tool_name: str) -> None:
        """Record a permanent failure (all retries exhausted).
        
        Args:
            tool_name: Name of tool that failed permanently
        """
        self._total_permanent_failures += 1
        
        if tool_name in self._tool_metrics:
            self._tool_metrics[tool_name].permanent_failures += 1
    
    def get_error_rate(
        self,
        tool_name: Optional[str] = None,
        time_window_minutes: int = 60
    ) -> float:
        """Calculate error rate (errors per minute).
        
        Args:
            tool_name: Optional tool name to filter by
            time_window_minutes: Time window for rate calculation
            
        Returns:
            Errors per minute in the time window
        """
        cutoff_time = datetime.now() - timedelta(minutes=time_window_minutes)
        
        # Filter errors by time and optionally by tool
        recent_errors = [
            ctx for ctx in self._error_history
            if ctx.timestamp >= cutoff_time
            and (tool_name is None or ctx.tool_name == tool_name)
        ]
        
        if not recent_errors:
            return 0.0
        
        return len(recent_errors) / time_window_minutes
    
    def get_most_common_errors(self, limit: int = 10) -> List[Tuple[str, int]]:
        """Get most common error types.
        
        Args:
            limit: Maximum number of error types to return
            
        Returns:
            List of (error_type, count) tuples sorted by count descending
        """
        error_counts = Counter(
            type(ctx.error).__name__ for ctx in self._error_history
        )
        return error_counts.most_common(limit)
    
    def get_tool_metrics(self, tool_name: str) -> Optional[ToolMetrics]:
        """Get metrics for a specific tool.
        
        Args:
            tool_name: Name of the tool
            
        Returns:
            ToolMetrics for the tool or None if not found
        """
        return self._tool_metrics.get(tool_name)
    
    def get_all_tool_metrics(self) -> Dict[str, ToolMetrics]:
        """Get metrics for all tools.
        
        Returns:
            Dictionary mapping tool names to their metrics
        """
        return self._tool_metrics.copy()
    
    def get_error_statistics(self, error_type: str) -> Optional[ErrorStatistics]:
        """Get statistics for a specific error type.
        
        Args:
            error_type: Name of the error type
            
        Returns:
            ErrorStatistics for the error type or None if not found
        """
        return self._error_stats.get(error_type)
    
    def get_error_history(
        self,
        tool_name: Optional[str] = None,
        error_type: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[ErrorContext]:
        """Get error history with optional filtering.
        
        Args:
            tool_name: Optional tool name to filter by
            error_type: Optional error type to filter by
            limit: Optional maximum number of errors to return (most recent)
            
        Returns:
            List of error contexts matching filters
        """
        filtered = self._error_history
        
        if tool_name:
            filtered = [ctx for ctx in filtered if ctx.tool_name == tool_name]
        
        if error_type:
            filtered = [
                ctx for ctx in filtered
                if type(ctx.error).__name__ == error_type
            ]
        
        # Sort by timestamp descending (most recent first)
        filtered = sorted(filtered, key=lambda ctx: ctx.timestamp, reverse=True)
        
        if limit:
            filtered = filtered[:limit]
        
        return filtered
    
    def get_global_statistics(self) -> Dict[str, any]:
        """Get global error statistics.
        
        Returns:
            Dictionary with global statistics
        """
        total_attempts = self._total_errors
        recovery_rate = 0.0
        if total_attempts > 0:
            recovery_rate = self._total_recoveries / total_attempts
        
        return {
            "total_errors": self._total_errors,
            "total_recoveries": self._total_recoveries,
            "total_permanent_failures": self._total_permanent_failures,
            "recovery_rate": recovery_rate,
            "unique_tools_with_errors": len(self._tool_metrics),
            "unique_error_types": len(self._error_stats),
            "current_error_rate_1h": self.get_error_rate(time_window_minutes=60),
            "current_error_rate_24h": self.get_error_rate(time_window_minutes=1440),
        }
    
    def get_tools_by_error_rate(self, limit: int = 10) -> List[Tuple[str, float]]:
        """Get tools sorted by error rate.
        
        Args:
            limit: Maximum number of tools to return
            
        Returns:
            List of (tool_name, error_rate) tuples sorted by rate descending
        """
        tool_rates = []
        
        for tool_name in self._tool_metrics:
            rate = self.get_error_rate(tool_name, time_window_minutes=60)
            tool_rates.append((tool_name, rate))
        
        tool_rates.sort(key=lambda x: x[1], reverse=True)
        return tool_rates[:limit]
    
    def _cleanup_old_records(self) -> None:
        """Remove error records older than retention period."""
        cutoff_time = datetime.now() - timedelta(days=self.retention_days)
        
        old_count = len(self._error_history)
        self._error_history = [
            ctx for ctx in self._error_history
            if ctx.timestamp >= cutoff_time
        ]
        
        removed = old_count - len(self._error_history)
        if removed > 0:
            logger.debug(f"Cleaned up {removed} old error records")
    
    def clear_all(self) -> None:
        """Clear all metrics and history."""
        self._error_history.clear()
        self._error_stats.clear()
        self._tool_metrics.clear()
        self._total_errors = 0
        self._total_recoveries = 0
        self._total_permanent_failures = 0
        logger.info("Cleared all error metrics")
    
    def export_report(self, format: str = "text") -> str:
        """Export metrics as a formatted report.
        
        Args:
            format: Output format ("text" or "json")
            
        Returns:
            Formatted report string
        """
        if format == "json":
            import json
            report = {
                "global_stats": self.get_global_statistics(),
                "most_common_errors": dict(self.get_most_common_errors()),
                "tools_by_error_rate": dict(self.get_tools_by_error_rate()),
                "tool_metrics": {
                    name: {
                        "total_errors": metrics.total_errors,
                        "error_types": dict(metrics.error_types),
                        "last_24h_errors": metrics.last_24h_errors,
                        "retry_success_rate": metrics.retry_success_rate,
                    }
                    for name, metrics in self._tool_metrics.items()
                }
            }
            return json.dumps(report, indent=2, default=str)
        
        # Text format
        lines = ["=" * 60, "ERROR METRICS REPORT", "=" * 60, ""]
        
        # Global stats
        lines.append("GLOBAL STATISTICS")
        lines.append("-" * 60)
        for key, value in self.get_global_statistics().items():
            lines.append(f"{key}: {value}")
        lines.append("")
        
        # Most common errors
        lines.append("MOST COMMON ERRORS")
        lines.append("-" * 60)
        for error_type, count in self.get_most_common_errors():
            lines.append(f"{error_type}: {count}")
        lines.append("")
        
        # Tools by error rate
        lines.append("TOOLS BY ERROR RATE (1 hour)")
        lines.append("-" * 60)
        for tool_name, rate in self.get_tools_by_error_rate():
            lines.append(f"{tool_name}: {rate:.2f} errors/min")
        lines.append("")
        
        return "\n".join(lines)


# Global instance
_global_metrics: Optional[ErrorMetrics] = None


def get_error_metrics() -> ErrorMetrics:
    """Get or create the global error metrics instance.
    
    Returns:
        Global ErrorMetrics instance
    """
    global _global_metrics
    if _global_metrics is None:
        _global_metrics = ErrorMetrics()
    return _global_metrics


def set_error_metrics(metrics: ErrorMetrics) -> None:
    """Set the global error metrics instance.
    
    Args:
        metrics: ErrorMetrics instance to use globally
    """
    global _global_metrics
    _global_metrics = metrics