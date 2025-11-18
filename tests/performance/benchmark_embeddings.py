"""
Benchmark suite for embedding generation performance.

Tests embedding generation speed, batching efficiency, and caching.
"""

import asyncio
import tempfile
import shutil
from pathlib import Path
from typing import List

from roo_code.builtin_tools.profiler import BenchmarkRunner
from roo_code.builtin_tools.ollama_embedder import OllamaEmbedder


async def benchmark_single_embeddings():
    """Benchmark single embedding generation."""
    runner = BenchmarkRunner("Single Embeddings")
    
    # Initialize embedder (mock mode for testing)
    embedder = OllamaEmbedder(
        model="nomic-embed-text",
        base_url="http://localhost:11434",
        timeout=30.0
    )
    
    test_texts = [
        "Hello, world!",
        "This is a short sentence.",
        "This is a medium length sentence with more words to process.",
        "This is a much longer sentence that contains significantly more text content and should take longer to process and generate embeddings for.",
        "def function():\n    pass\n\nclass MyClass:\n    def method(self):\n        return True"
    ]
    
    # Note: These benchmarks will only work if Ollama is running
    # Otherwise they'll measure timeout/error handling
    
    async def embed_short():
        try:
            await embedder.embed_text(test_texts[0])
        except Exception:
            pass  # Expected if Ollama not running
    
    async def embed_medium():
        try:
            await embedder.embed_text(test_texts[2])
        except Exception:
            pass
    
    async def embed_long():
        try:
            await embedder.embed_text(test_texts[3])
        except Exception:
            pass
    
    async def embed_code():
        try:
            await embedder.embed_text(test_texts[4])
        except Exception:
            pass
    
    print("Note: Embeddings benchmarks require Ollama to be running")
    print("If Ollama is not running, benchmarks will measure error handling speed")
    
    await runner.run_async_benchmark("embed_short_text", embed_short, iterations=10, warmup=2)
    await runner.run_async_benchmark("embed_medium_text", embed_medium, iterations=10, warmup=2)
    await runner.run_async_benchmark("embed_long_text", embed_long, iterations=10, warmup=2)
    await runner.run_async_benchmark("embed_code_text", embed_code, iterations=10, warmup=2)
    
    runner.print_summary()
    return runner.results


async def benchmark_batch_embeddings():
    """Benchmark batch embedding generation."""
    runner = BenchmarkRunner("Batch Embeddings")
    
    embedder = OllamaEmbedder(
        model="nomic-embed-text",
        base_url="http://localhost:11434",
        timeout=30.0
    )
    
    # Generate test data
    texts_5 = [f"This is test sentence number {i}." for i in range(5)]
    texts_10 = [f"This is test sentence number {i}." for i in range(10)]
    texts_50 = [f"This is test sentence number {i}." for i in range(50)]
    texts_100 = [f"This is test sentence number {i}." for i in range(100)]
    
    async def embed_batch_5():
        try:
            await embedder.embed_texts(texts_5)
        except Exception:
            pass
    
    async def embed_batch_10():
        try:
            await embedder.embed_texts(texts_10)
        except Exception:
            pass
    
    async def embed_batch_50():
        try:
            await embedder.embed_texts(texts_50)
        except Exception:
            pass
    
    async def embed_batch_100():
        try:
            await embedder.embed_texts(texts_100)
        except Exception:
            pass
    
    await runner.run_async_benchmark("batch_5_texts", embed_batch_5, iterations=5, warmup=1)
    await runner.run_async_benchmark("batch_10_texts", embed_batch_10, iterations=5, warmup=1)
    await runner.run_async_benchmark("batch_50_texts", embed_batch_50, iterations=3, warmup=1)
    await runner.run_async_benchmark("batch_100_texts", embed_batch_100, iterations=2, warmup=1)
    
    runner.print_summary()
    return runner.results


async def benchmark_cache_effectiveness():
    """Benchmark cache hit rates for embeddings."""
    runner = BenchmarkRunner("Embedding Cache")
    
    # Create embedder with cache
    cache_dir = tempfile.mkdtemp()
    try:
        embedder = OllamaEmbedder(
            model="nomic-embed-text",
            base_url="http://localhost:11434",
            cache_dir=cache_dir
        )
        
        test_text = "This is a test sentence for caching."
        
        # First call (cache miss)
        async def first_call():
            try:
                await embedder.embed_text(test_text)
            except Exception:
                pass
        
        # Second call (should be cache hit)
        async def cached_call():
            try:
                await embedder.embed_text(test_text)
            except Exception:
                pass
        
        await runner.run_async_benchmark("embedding_cache_miss", first_call, iterations=5, warmup=0)
        await runner.run_async_benchmark("embedding_cache_hit", cached_call, iterations=20, warmup=0)
        
        # Compare cache hit vs miss
        if "embedding_cache_miss" in runner.results and "embedding_cache_hit" in runner.results:
            comparison = runner.compare("embedding_cache_miss", "embedding_cache_hit")
            print(f"\nCache Speedup: {comparison['speedup']:.2f}x")
            print(f"Cache Improvement: {comparison['improvement_percent']:.1f}%")
        
        runner.print_summary()
        
    finally:
        shutil.rmtree(cache_dir, ignore_errors=True)
    
    return runner.results


async def run_all_benchmarks():
    """Run all embedding benchmarks."""
    print("\n" + "=" * 60)
    print("EMBEDDING PERFORMANCE BENCHMARKS")
    print("=" * 60)
    
    results = {}
    
    print("\n[1/3] Running single embedding benchmarks...")
    results["single_embeddings"] = await benchmark_single_embeddings()
    
    print("\n[2/3] Running batch embedding benchmarks...")
    results["batch_embeddings"] = await benchmark_batch_embeddings()
    
    print("\n[3/3] Running cache effectiveness benchmarks...")
    results["cache_effectiveness"] = await benchmark_cache_effectiveness()
    
    return results


if __name__ == "__main__":
    asyncio.run(run_all_benchmarks())