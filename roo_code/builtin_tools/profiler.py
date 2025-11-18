"""
Profiling utilities for performance analysis.

This module provides tools for profiling code execution including:
- Execution time tracking
- Memory usage monitoring
- Context managers for easy profiling
"""

import time
import asyncio
import tracemalloc
from contextlib import contextmanager, asynccontextmanager
from typing import Dict, Any, Optional, Callable
from functools import wraps
import json
from pathlib import Path
from datetime import datetime


class PerformanceMetrics:
    """Track performance metrics for operations."""
    
    def __init__(self):
        """Initialize metrics tracker."""
        self._metrics: Dict[str, Dict[str, Any]] = {}
    
    def record(
        self,
        operation: str,
        duration: float,
        memory_delta: Optional[int] = None,
        **kwargs
    ) -> None:
        """
        Record performance metrics for an operation.
        
        Args:
            operation: Name of the operation
            duration: Execution time in seconds
            memory_delta: Change in memory usage in bytes
            **kwargs: Additional metrics to record
        """
        if operation not in self._metrics:
            self._metrics[operation] = {
                "count": 0,
                "total_time": 0.0,
                "min_time": float('inf'),
                "max_time": 0.0,
                "avg_time": 0.0,
                "total_memory": 0,
                "min_memory": float('inf') if memory_delta else None,
                "max_memory": 0 if memory_delta else None,
                "avg_memory": 0.0 if memory_delta else None,
            }
        
        metrics = self._metrics[operation]
        metrics["count"] += 1
        metrics["total_time"] += duration
        metrics["min_time"] = min(metrics["min_time"], duration)
        metrics["max_time"] = max(metrics["max_time"], duration)
        metrics["avg_time"] = metrics["total_time"] / metrics["count"]
        
        if memory_delta is not None:
            metrics["total_memory"] += memory_delta
            metrics["min_memory"] = min(metrics["min_memory"], memory_delta)
            metrics["max_memory"] = max(metrics["max_memory"], memory_delta)
            metrics["avg_memory"] = metrics["total_memory"] / metrics["count"]
        
        # Store additional metrics
        for key, value in kwargs.items():
            if key not in metrics:
                metrics[key] = []
            metrics[key].append(value)
    
    def get_metrics(self, operation: Optional[str] = None) -> Dict[str, Any]:
        """
        Get recorded metrics.
        
        Args:
            operation: Specific operation to get metrics for, or None for all
            
        Returns:
            Metrics dictionary
        """
        if operation:
            return self._metrics.get(operation, {})
        return self._metrics.copy()
    
    def clear(self) -> None:
        """Clear all recorded metrics."""
        self._metrics.clear()
    
    def to_json(self, filepath: str) -> None:
        """
        Save metrics to JSON file.
        
        Args:
            filepath: Path to save JSON file
        """
        with open(filepath, 'w') as f:
            json.dump(self._metrics, f, indent=2)
    
    def summary(self) -> str:
        """
        Generate human-readable summary of metrics.
        
        Returns:
            Summary string
        """
        lines = ["Performance Metrics Summary", "=" * 50]
        
        for operation, metrics in sorted(self._metrics.items()):
            lines.append(f"\n{operation}:")
            lines.append(f"  Count: {metrics['count']}")
            lines.append(f"  Total Time: {metrics['total_time']:.3f}s")
            lines.append(f"  Avg Time: {metrics['avg_time']:.3f}s")
            lines.append(f"  Min Time: {metrics['min_time']:.3f}s")
            lines.append(f"  Max Time: {metrics['max_time']:.3f}s")
            
            if metrics.get("avg_memory") is not None:
                lines.append(f"  Avg Memory: {metrics['avg_memory'] / 1024 / 1024:.2f} MB")
                lines.append(f"  Max Memory: {metrics['max_memory'] / 1024 / 1024:.2f} MB")
        
        return "\n".join(lines)


# Global metrics instance
_global_metrics = PerformanceMetrics()


def get_global_metrics() -> PerformanceMetrics:
    """Get the global metrics instance."""
    return _global_metrics


@contextmanager
def profile_sync(operation: str, track_memory: bool = False):
    """
    Context manager for profiling synchronous code.
    
    Args:
        operation: Name of the operation being profiled
        track_memory: Whether to track memory usage
        
    Yields:
        Metrics dict that can be updated with additional data
    """
    start_time = time.perf_counter()
    start_memory = None
    
    if track_memory:
        tracemalloc.start()
        start_memory = tracemalloc.get_traced_memory()[0]
    
    additional_metrics = {}
    
    try:
        yield additional_metrics
    finally:
        duration = time.perf_counter() - start_time
        
        memory_delta = None
        if track_memory and start_memory is not None:
            current_memory = tracemalloc.get_traced_memory()[0]
            memory_delta = current_memory - start_memory
            tracemalloc.stop()
        
        _global_metrics.record(
            operation,
            duration,
            memory_delta,
            **additional_metrics
        )


@asynccontextmanager
async def profile_async(operation: str, track_memory: bool = False):
    """
    Async context manager for profiling async code.
    
    Args:
        operation: Name of the operation being profiled
        track_memory: Whether to track memory usage
        
    Yields:
        Metrics dict that can be updated with additional data
    """
    start_time = time.perf_counter()
    start_memory = None
    
    if track_memory:
        tracemalloc.start()
        start_memory = tracemalloc.get_traced_memory()[0]
    
    additional_metrics = {}
    
    try:
        yield additional_metrics
    finally:
        duration = time.perf_counter() - start_time
        
        memory_delta = None
        if track_memory and start_memory is not None:
            current_memory = tracemalloc.get_traced_memory()[0]
            memory_delta = current_memory - start_memory
            tracemalloc.stop()
        
        _global_metrics.record(
            operation,
            duration,
            memory_delta,
            **additional_metrics
        )


def profile_function(operation: Optional[str] = None, track_memory: bool = False):
    """
    Decorator for profiling function execution.
    
    Args:
        operation: Name of the operation (defaults to function name)
        track_memory: Whether to track memory usage
        
    Returns:
        Decorated function
    """
    def decorator(func: Callable) -> Callable:
        op_name = operation or func.__name__
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            with profile_sync(op_name, track_memory):
                return func(*args, **kwargs)
        
        return wrapper
    return decorator


def profile_async_function(operation: Optional[str] = None, track_memory: bool = False):
    """
    Decorator for profiling async function execution.
    
    Args:
        operation: Name of the operation (defaults to function name)
        track_memory: Whether to track memory usage
        
    Returns:
        Decorated async function
    """
    def decorator(func: Callable) -> Callable:
        op_name = operation or func.__name__
        
        @wraps(func)
        async def wrapper(*args, **kwargs):
            async with profile_async(op_name, track_memory):
                return await func(*args, **kwargs)
        
        return wrapper
    return decorator


class BenchmarkRunner:
    """Run and compare benchmarks."""
    
    def __init__(self, name: str):
        """
        Initialize benchmark runner.
        
        Args:
            name: Name of the benchmark suite
        """
        self.name = name
        self.results: Dict[str, Dict[str, Any]] = {}
    
    def run_benchmark(
        self,
        name: str,
        func: Callable,
        iterations: int = 100,
        warmup: int = 10
    ) -> Dict[str, Any]:
        """
        Run a benchmark function multiple times.
        
        Args:
            name: Name of the benchmark
            func: Function to benchmark
            iterations: Number of iterations to run
            warmup: Number of warmup iterations
            
        Returns:
            Benchmark results
        """
        # Warmup
        for _ in range(warmup):
            func()
        
        # Actual benchmark
        times = []
        for _ in range(iterations):
            start = time.perf_counter()
            func()
            times.append(time.perf_counter() - start)
        
        # Calculate statistics
        times_sorted = sorted(times)
        result = {
            "iterations": iterations,
            "total_time": sum(times),
            "mean": sum(times) / len(times),
            "median": times_sorted[len(times) // 2],
            "min": min(times),
            "max": max(times),
            "p95": times_sorted[int(len(times) * 0.95)],
            "p99": times_sorted[int(len(times) * 0.99)],
        }
        
        self.results[name] = result
        return result
    
    async def run_async_benchmark(
        self,
        name: str,
        func: Callable,
        iterations: int = 100,
        warmup: int = 10
    ) -> Dict[str, Any]:
        """
        Run an async benchmark function multiple times.
        
        Args:
            name: Name of the benchmark
            func: Async function to benchmark
            iterations: Number of iterations to run
            warmup: Number of warmup iterations
            
        Returns:
            Benchmark results
        """
        # Warmup
        for _ in range(warmup):
            await func()
        
        # Actual benchmark
        times = []
        for _ in range(iterations):
            start = time.perf_counter()
            await func()
            times.append(time.perf_counter() - start)
        
        # Calculate statistics
        times_sorted = sorted(times)
        result = {
            "iterations": iterations,
            "total_time": sum(times),
            "mean": sum(times) / len(times),
            "median": times_sorted[len(times) // 2],
            "min": min(times),
            "max": max(times),
            "p95": times_sorted[int(len(times) * 0.95)],
            "p99": times_sorted[int(len(times) * 0.99)],
        }
        
        self.results[name] = result
        return result
    
    def compare(self, baseline: str, current: str) -> Dict[str, Any]:
        """
        Compare two benchmark results.
        
        Args:
            baseline: Name of baseline benchmark
            current: Name of current benchmark
            
        Returns:
            Comparison results
        """
        baseline_result = self.results.get(baseline)
        current_result = self.results.get(current)
        
        if not baseline_result or not current_result:
            raise ValueError("Both benchmarks must be run first")
        
        speedup = baseline_result["mean"] / current_result["mean"]
        improvement = (1 - current_result["mean"] / baseline_result["mean"]) * 100
        
        return {
            "speedup": speedup,
            "improvement_percent": improvement,
            "baseline_mean": baseline_result["mean"],
            "current_mean": current_result["mean"],
        }
    
    def save_results(self, filepath: str) -> None:
        """
        Save benchmark results to file.
        
        Args:
            filepath: Path to save results
        """
        output = {
            "name": self.name,
            "timestamp": datetime.now().isoformat(),
            "results": self.results,
        }
        
        with open(filepath, 'w') as f:
            json.dump(output, f, indent=2)
    
    def print_summary(self) -> None:
        """Print benchmark summary."""
        print(f"\n{self.name} Benchmark Results")
        print("=" * 60)
        
        for name, result in self.results.items():
            print(f"\n{name}:")
            print(f"  Iterations: {result['iterations']}")
            print(f"  Mean: {result['mean']*1000:.3f} ms")
            print(f"  Median: {result['median']*1000:.3f} ms")
            print(f"  Min: {result['min']*1000:.3f} ms")
            print(f"  Max: {result['max']*1000:.3f} ms")
            print(f"  P95: {result['p95']*1000:.3f} ms")
            print(f"  P99: {result['p99']*1000:.3f} ms")