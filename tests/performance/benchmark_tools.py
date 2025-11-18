"""
Benchmark suite for built-in tools performance.

Tests execution time and throughput for common tool operations.
"""

import asyncio
import tempfile
import shutil
from pathlib import Path
from typing import Dict, Any

from roo_code.builtin_tools.profiler import BenchmarkRunner, get_global_metrics
from roo_code.builtin_tools.file_operations import ReadFileTool, WriteToFileTool
from roo_code.builtin_tools.search import SearchFilesTool, ListFilesTool


async def benchmark_file_operations():
    """Benchmark file operation tools."""
    runner = BenchmarkRunner("File Operations")
    
    # Create temporary directory with test files
    temp_dir = tempfile.mkdtemp()
    try:
        # Create test files of various sizes
        small_file = Path(temp_dir) / "small.txt"
        medium_file = Path(temp_dir) / "medium.txt"
        large_file = Path(temp_dir) / "large.txt"
        
        small_file.write_text("Hello, World!\n" * 10)
        medium_file.write_text("Hello, World!\n" * 1000)
        large_file.write_text("Hello, World!\n" * 10000)
        
        # Create subdirectories
        for i in range(10):
            subdir = Path(temp_dir) / f"subdir_{i}"
            subdir.mkdir()
            for j in range(10):
                (subdir / f"file_{j}.txt").write_text(f"Content {i}-{j}\n" * 100)
        
        # Benchmark ReadFileTool
        read_tool = ReadFileTool(cwd=temp_dir)
        read_tool.current_use_id = "benchmark-read"
        
        async def read_small():
            await read_tool.execute({"path": str(small_file)})
        
        async def read_medium():
            await read_tool.execute({"path": str(medium_file)})
        
        async def read_large():
            await read_tool.execute({"path": str(large_file)})
        
        await runner.run_async_benchmark("read_small_file", read_small, iterations=100)
        await runner.run_async_benchmark("read_medium_file", read_medium, iterations=100)
        await runner.run_async_benchmark("read_large_file", read_large, iterations=50)
        
        # Benchmark WriteToFileTool
        write_tool = WriteToFileTool(cwd=temp_dir)
        write_tool.current_use_id = "benchmark-write"
        write_count = [0]
        
        async def write_file():
            write_count[0] += 1
            await write_tool.execute({
                "path": f"output_{write_count[0]}.txt",
                "content": "Test content\n" * 100
            })
        
        await runner.run_async_benchmark("write_file", write_file, iterations=50)
        
        # Benchmark ListFilesTool
        list_tool = ListFilesTool(cwd=temp_dir)
        list_tool.current_use_id = "benchmark-list"
        
        async def list_files():
            await list_tool.execute({"path": ".", "recursive": True})
        
        async def list_files_non_recursive():
            await list_tool.execute({"path": ".", "recursive": False})
        
        await runner.run_async_benchmark("list_files_recursive", list_files, iterations=50)
        await runner.run_async_benchmark("list_files_non_recursive", list_files_non_recursive, iterations=100)
        
        runner.print_summary()
        
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    return runner.results


async def benchmark_search_operations():
    """Benchmark search tool performance."""
    runner = BenchmarkRunner("Search Operations")
    
    # Create temporary directory with test files
    temp_dir = tempfile.mkdtemp()
    try:
        # Create files with searchable content
        for i in range(50):
            file_path = Path(temp_dir) / f"file_{i}.py"
            content = f"""
def function_{i}():
    \"\"\"Function {i} docstring.\"\"\"
    value = {i}
    return value * 2

class Class_{i}:
    \"\"\"Class {i} docstring.\"\"\"
    def method(self):
        return {i}
"""
            file_path.write_text(content)
        
        # Benchmark SearchFilesTool
        search_tool = SearchFilesTool(cwd=temp_dir)
        search_tool.current_use_id = "benchmark-search"
        
        async def search_simple():
            await search_tool.execute({
                "path": ".",
                "regex": "def function",
                "file_pattern": "*.py"
            })
        
        async def search_complex():
            await search_tool.execute({
                "path": ".",
                "regex": r"class \w+:",
                "file_pattern": "*.py"
            })
        
        async def search_rare():
            await search_tool.execute({
                "path": ".",
                "regex": "function_42",
                "file_pattern": "*.py"
            })
        
        await runner.run_async_benchmark("search_simple_pattern", search_simple, iterations=1000)
        await runner.run_async_benchmark("search_complex_pattern", search_complex, iterations=1000)
        await runner.run_async_benchmark("search_rare_match", search_rare, iterations=1000)
        
        runner.print_summary()
        
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    return runner.results


async def benchmark_concurrent_tools():
    """Benchmark concurrent tool execution."""
    runner = BenchmarkRunner("Concurrent Tools")
    
    temp_dir = tempfile.mkdtemp()
    try:
        # Create test files
        for i in range(1000):
            (Path(temp_dir) / f"file_{i}.txt").write_text(f"Content {i}\n" * 100)
        
        read_tool = ReadFileTool(cwd=temp_dir)
        read_tool.current_use_id = "benchmark-concurrent"
        
        async def concurrent_reads_5():
            tasks = [
                read_tool.execute({"path": f"file_{i}.txt"})
                for i in range(5)
            ]
            await asyncio.gather(*tasks)
        
        async def concurrent_reads_10():
            tasks = [
                read_tool.execute({"path": f"file_{i}.txt"})
                for i in range(10)
            ]
            await asyncio.gather(*tasks)
        
        async def concurrent_reads_20():
            tasks = [
                read_tool.execute({"path": f"file_{i}.txt"})
                for i in range(20)
            ]
            await asyncio.gather(*tasks)
        
        await runner.run_async_benchmark("concurrent_5_reads", concurrent_reads_5, iterations=20)
        await runner.run_async_benchmark("concurrent_10_reads", concurrent_reads_10, iterations=20)
        await runner.run_async_benchmark("concurrent_20_reads", concurrent_reads_20, iterations=10)
        
        runner.print_summary()
        
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    return runner.results


async def run_all_benchmarks():
    """Run all tool benchmarks."""
    print("\n" + "=" * 60)
    print("TOOL PERFORMANCE BENCHMARKS")
    print("=" * 60)
    
    results = {}
    
    print("\n[1/3] Running file operation benchmarks...")
    results["file_operations"] = await benchmark_file_operations()
    
    print("\n[2/3] Running search operation benchmarks...")
    results["search_operations"] = await benchmark_search_operations()
    
    print("\n[3/3] Running concurrent tool benchmarks...")
    results["concurrent_tools"] = await benchmark_concurrent_tools()
    
    # Print global metrics
    print("\n" + "=" * 60)
    print("GLOBAL METRICS")
    print("=" * 60)
    metrics = get_global_metrics()
    print(metrics.summary())
    
    return results


if __name__ == "__main__":
    asyncio.run(run_all_benchmarks())