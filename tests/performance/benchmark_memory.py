"""
Benchmark suite for memory usage and leak detection.

Tests memory consumption patterns and identifies potential leaks.
"""

import asyncio
import gc
import tracemalloc
import tempfile
import shutil
from pathlib import Path
from typing import Dict, Any, List

from roo_code.builtin_tools.profiler import BenchmarkRunner
from roo_code.builtin_tools.file_operations import ReadFileTool
from roo_code.builtin_tools.ollama_embedder import OllamaEmbedder
from roo_code.builtin_tools.vector_store import VectorStore
from roo_code.builtin_tools.error_metrics import ErrorMetrics
from roo_code.builtin_tools.file_watcher import FileWatcher


def get_memory_usage() -> Dict[str, int]:
    """Get current memory usage statistics."""
    gc.collect()
    current, peak = tracemalloc.get_traced_memory()
    return {
        "current": current,
        "peak": peak,
        "current_mb": current / 1024 / 1024,
        "peak_mb": peak / 1024 / 1024
    }


async def benchmark_file_operations_memory():
    """Benchmark memory usage of file operations."""
    print("\n[File Operations Memory Test]")
    tracemalloc.start()
    
    temp_dir = tempfile.mkdtemp()
    try:
        # Create large file
        large_file = Path(temp_dir) / "large.txt"
        large_file.write_text("Hello, World!\n" * 100000)  # ~1.4MB
        
        before = get_memory_usage()
        print(f"Before: {before['current_mb']:.2f} MB")
        
        # Read file multiple times
        read_tool = ReadFileTool(cwd=temp_dir)
        for _ in range(10):
            await read_tool.execute({"path": "large.txt"})
        
        during = get_memory_usage()
        print(f"During: {during['current_mb']:.2f} MB (delta: {during['current_mb'] - before['current_mb']:.2f} MB)")
        
        # Clear references
        del read_tool
        gc.collect()
        
        after = get_memory_usage()
        print(f"After GC: {after['current_mb']:.2f} MB (delta: {after['current_mb'] - before['current_mb']:.2f} MB)")
        
        # Check for leak
        leak_mb = after['current_mb'] - before['current_mb']
        if leak_mb > 1.0:
            print(f"⚠️  Potential memory leak detected: {leak_mb:.2f} MB")
        else:
            print(f"✓ No significant memory leak detected")
        
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
        tracemalloc.stop()


async def benchmark_vector_store_memory():
    """Benchmark memory usage of vector store operations."""
    print("\n[Vector Store Memory Test]")
    tracemalloc.start()
    
    temp_dir = tempfile.mkdtemp()
    try:
        before = get_memory_usage()
        print(f"Before: {before['current_mb']:.2f} MB")
        
        # Create vector store and add embeddings
        store = VectorStore(db_path=f"{temp_dir}/vectors.db")
        
        # Generate fake embeddings
        embeddings = []
        for i in range(1000):
            embedding = [float(j) for j in range(768)]  # Typical embedding size
            embeddings.append({
                "file_path": f"file_{i}.py",
                "chunk_text": f"This is chunk {i}",
                "start_line": i * 10,
                "end_line": i * 10 + 10,
                "embedding": embedding
            })
        
        # Add embeddings in batches
        for i in range(0, len(embeddings), 100):
            batch = embeddings[i:i+100]
            for item in batch:
                store.add_embedding(
                    item["file_path"],
                    item["chunk_text"],
                    item["start_line"],
                    item["end_line"],
                    item["embedding"]
                )
        
        during = get_memory_usage()
        print(f"During: {during['current_mb']:.2f} MB (delta: {during['current_mb'] - before['current_mb']:.2f} MB)")
        
        # Query multiple times
        query_embedding = [0.1] * 768
        for _ in range(100):
            store.search(query_embedding, top_k=10)
        
        after_queries = get_memory_usage()
        print(f"After queries: {after_queries['current_mb']:.2f} MB")
        
        # Clear
        store.close()
        del store
        del embeddings
        gc.collect()
        
        after = get_memory_usage()
        print(f"After GC: {after['current_mb']:.2f} MB (delta: {after['current_mb'] - before['current_mb']:.2f} MB)")
        
        leak_mb = after['current_mb'] - before['current_mb']
        if leak_mb > 5.0:
            print(f"⚠️  Potential memory leak detected: {leak_mb:.2f} MB")
        else:
            print(f"✓ No significant memory leak detected")
        
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
        tracemalloc.stop()


async def benchmark_error_metrics_memory():
    """Benchmark memory usage of error tracking."""
    print("\n[Error Metrics Memory Test]")
    tracemalloc.start()
    
    before = get_memory_usage()
    print(f"Before: {before['current_mb']:.2f} MB")
    
    # Create error metrics and log many errors
    metrics = ErrorMetrics()
    
    for i in range(10000):
        metrics.record_error(
            tool_name="test_tool",
            error_type="TestError",
            error_message=f"Error {i}",
            parameters={"param": f"value_{i}"}
        )
    
    during = get_memory_usage()
    print(f"During (10k errors): {during['current_mb']:.2f} MB (delta: {during['current_mb'] - before['current_mb']:.2f} MB)")
    
    # Clear metrics
    metrics.clear()
    gc.collect()
    
    after = get_memory_usage()
    print(f"After clear: {after['current_mb']:.2f} MB (delta: {after['current_mb'] - before['current_mb']:.2f} MB)")
    
    leak_mb = after['current_mb'] - before['current_mb']
    if leak_mb > 1.0:
        print(f"⚠️  Potential memory leak detected: {leak_mb:.2f} MB")
    else:
        print(f"✓ No significant memory leak detected")
    
    tracemalloc.stop()


async def benchmark_file_watcher_memory():
    """Benchmark memory usage of file watcher."""
    print("\n[File Watcher Memory Test]")
    tracemalloc.start()
    
    temp_dir = tempfile.mkdtemp()
    try:
        # Create many files
        for i in range(500):
            (Path(temp_dir) / f"file_{i}.py").write_text(f"# File {i}\n" * 10)
        
        before = get_memory_usage()
        print(f"Before: {before['current_mb']:.2f} MB")
        
        # Start file watcher
        watcher = FileWatcher(watch_dir=temp_dir)
        await watcher.start()
        
        # Wait a bit for initial scan
        await asyncio.sleep(1)
        
        during = get_memory_usage()
        print(f"During (watching 500 files): {during['current_mb']:.2f} MB (delta: {during['current_mb'] - before['current_mb']:.2f} MB)")
        
        # Modify files
        for i in range(100):
            (Path(temp_dir) / f"file_{i}.py").write_text(f"# Modified {i}\n" * 20)
        
        await asyncio.sleep(0.5)
        
        after_changes = get_memory_usage()
        print(f"After changes: {after_changes['current_mb']:.2f} MB")
        
        # Stop watcher
        await watcher.stop()
        del watcher
        gc.collect()
        
        after = get_memory_usage()
        print(f"After stop: {after['current_mb']:.2f} MB (delta: {after['current_mb'] - before['current_mb']:.2f} MB)")
        
        leak_mb = after['current_mb'] - before['current_mb']
        if leak_mb > 2.0:
            print(f"⚠️  Potential memory leak detected: {leak_mb:.2f} MB")
        else:
            print(f"✓ No significant memory leak detected")
        
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
        tracemalloc.stop()


async def benchmark_long_running_operations():
    """Test memory stability over long-running operations."""
    print("\n[Long Running Operations Test]")
    tracemalloc.start()
    
    temp_dir = tempfile.mkdtemp()
    try:
        # Create test file
        test_file = Path(temp_dir) / "test.txt"
        test_file.write_text("Test content\n" * 1000)
        
        measurements = []
        read_tool = ReadFileTool(cwd=temp_dir)
        
        # Perform 1000 iterations
        for i in range(1000):
            await read_tool.execute({"path": "test.txt"})
            
            if i % 100 == 0:
                gc.collect()
                usage = get_memory_usage()
                measurements.append(usage['current_mb'])
                print(f"Iteration {i}: {usage['current_mb']:.2f} MB")
        
        # Check for memory growth
        if len(measurements) >= 2:
            growth = measurements[-1] - measurements[0]
            growth_per_100 = growth / (len(measurements) - 1)
            
            print(f"\nMemory growth: {growth:.2f} MB over {len(measurements)} measurements")
            print(f"Growth per 100 iterations: {growth_per_100:.2f} MB")
            
            if growth_per_100 > 0.5:
                print(f"⚠️  Significant memory growth detected")
            else:
                print(f"✓ Memory usage stable")
        
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
        tracemalloc.stop()


async def run_all_benchmarks():
    """Run all memory benchmarks."""
    print("\n" + "=" * 60)
    print("MEMORY USAGE BENCHMARKS")
    print("=" * 60)
    
    await benchmark_file_operations_memory()
    await benchmark_vector_store_memory()
    await benchmark_error_metrics_memory()
    await benchmark_file_watcher_memory()
    await benchmark_long_running_operations()
    
    print("\n" + "=" * 60)
    print("Memory benchmarks complete!")


if __name__ == "__main__":
    asyncio.run(run_all_benchmarks())