"""
Caching utilities for performance optimization.

This module provides various caching mechanisms including:
- In-memory TTL cache
- Persistent file-based cache
- LRU cache with size limits
"""

import time
import json
import hashlib
import pickle
from pathlib import Path
from typing import Any, Dict, Optional, TypeVar, Generic, Callable
from collections import OrderedDict
from datetime import datetime, timedelta

T = TypeVar('T')


class TTLCache(Generic[T]):
    """Time-To-Live cache with automatic expiration."""
    
    def __init__(self, ttl_seconds: float = 5.0, max_size: int = 1000):
        """
        Initialize TTL cache.
        
        Args:
            ttl_seconds: Time to live for cached items in seconds
            max_size: Maximum number of items to cache
        """
        self._cache: Dict[str, tuple[T, float]] = {}
        self._ttl = ttl_seconds
        self._max_size = max_size
        self._hits = 0
        self._misses = 0
    
    def get(self, key: str) -> Optional[T]:
        """
        Get cached value if still valid.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if expired/missing
        """
        if key in self._cache:
            value, timestamp = self._cache[key]
            if time.time() - timestamp < self._ttl:
                self._hits += 1
                return value
            else:
                # Expired, remove it
                del self._cache[key]
        
        self._misses += 1
        return None
    
    def set(self, key: str, value: T) -> None:
        """
        Set cached value with current timestamp.
        
        Args:
            key: Cache key
            value: Value to cache
        """
        # Evict oldest if at max size
        if len(self._cache) >= self._max_size and key not in self._cache:
            # Remove oldest entry
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
        
        self._cache[key] = (value, time.time())
    
    def invalidate(self, key: str) -> None:
        """Remove key from cache."""
        self._cache.pop(key, None)
    
    def clear(self) -> None:
        """Clear all cached items."""
        self._cache.clear()
        self._hits = 0
        self._misses = 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total = self._hits + self._misses
        hit_rate = self._hits / total if total > 0 else 0.0
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": hit_rate,
            "size": len(self._cache),
            "max_size": self._max_size,
        }


class LRUCache(Generic[T]):
    """Least Recently Used cache with size limit."""
    
    def __init__(self, max_size: int = 100):
        """
        Initialize LRU cache.
        
        Args:
            max_size: Maximum number of items to cache
        """
        self._cache: OrderedDict[str, T] = OrderedDict()
        self._max_size = max_size
        self._hits = 0
        self._misses = 0
    
    def get(self, key: str) -> Optional[T]:
        """
        Get cached value and move to end (most recently used).
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if missing
        """
        if key in self._cache:
            # Move to end (most recently used)
            self._cache.move_to_end(key)
            self._hits += 1
            return self._cache[key]
        
        self._misses += 1
        return None
    
    def set(self, key: str, value: T) -> None:
        """
        Set cached value.
        
        Args:
            key: Cache key
            value: Value to cache
        """
        if key in self._cache:
            # Move to end
            self._cache.move_to_end(key)
        else:
            # Evict least recently used if at max size
            if len(self._cache) >= self._max_size:
                self._cache.popitem(last=False)
        
        self._cache[key] = value
    
    def invalidate(self, key: str) -> None:
        """Remove key from cache."""
        self._cache.pop(key, None)
    
    def clear(self) -> None:
        """Clear all cached items."""
        self._cache.clear()
        self._hits = 0
        self._misses = 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total = self._hits + self._misses
        hit_rate = self._hits / total if total > 0 else 0.0
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": hit_rate,
            "size": len(self._cache),
            "max_size": self._max_size,
        }


class PersistentCache(Generic[T]):
    """File-based persistent cache with automatic serialization."""
    
    def __init__(
        self,
        cache_dir: str,
        max_size: int = 10000,
        use_json: bool = True
    ):
        """
        Initialize persistent cache.
        
        Args:
            cache_dir: Directory to store cache files
            max_size: Maximum number of items to cache
            use_json: Use JSON instead of pickle (slower but portable)
        """
        self._cache_dir = Path(cache_dir)
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._max_size = max_size
        self._use_json = use_json
        self._index_file = self._cache_dir / "cache_index.json"
        self._index = self._load_index()
        self._hits = 0
        self._misses = 0
    
    def _load_index(self) -> Dict[str, float]:
        """Load cache index from disk."""
        if self._index_file.exists():
            try:
                with open(self._index_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {}
        return {}
    
    def _save_index(self) -> None:
        """Save cache index to disk."""
        try:
            with open(self._index_file, 'w') as f:
                json.dump(self._index, f)
        except IOError:
            pass  # Ignore write errors
    
    def _get_cache_path(self, key: str) -> Path:
        """Get file path for cache key."""
        # Hash the key to get a safe filename
        key_hash = hashlib.sha256(key.encode()).hexdigest()
        ext = ".json" if self._use_json else ".pkl"
        return self._cache_dir / f"{key_hash}{ext}"
    
    def get(self, key: str) -> Optional[T]:
        """
        Get cached value from disk.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if missing
        """
        cache_path = self._get_cache_path(key)
        
        if not cache_path.exists():
            self._misses += 1
            return None
        
        try:
            if self._use_json:
                with open(cache_path, 'r') as f:
                    value = json.load(f)
            else:
                with open(cache_path, 'rb') as f:
                    value = pickle.load(f)
            
            # Update access time in index
            self._index[key] = time.time()
            self._save_index()
            self._hits += 1
            return value
        except (json.JSONDecodeError, pickle.PickleError, IOError):
            self._misses += 1
            return None
    
    def set(self, key: str, value: T) -> None:
        """
        Set cached value to disk.
        
        Args:
            key: Cache key
            value: Value to cache
        """
        # Evict oldest if at max size
        if len(self._index) >= self._max_size and key not in self._index:
            oldest_key = min(self._index.items(), key=lambda x: x[1])[0]
            self.invalidate(oldest_key)
        
        cache_path = self._get_cache_path(key)
        
        try:
            if self._use_json:
                with open(cache_path, 'w') as f:
                    json.dump(value, f)
            else:
                with open(cache_path, 'wb') as f:
                    pickle.dump(value, f)
            
            self._index[key] = time.time()
            self._save_index()
        except (IOError, TypeError):
            pass  # Ignore write errors
    
    def invalidate(self, key: str) -> None:
        """Remove key from cache."""
        cache_path = self._get_cache_path(key)
        if cache_path.exists():
            try:
                cache_path.unlink()
            except IOError:
                pass
        
        self._index.pop(key, None)
        self._save_index()
    
    def clear(self) -> None:
        """Clear all cached items."""
        for cache_file in self._cache_dir.glob("*.json"):
            try:
                cache_file.unlink()
            except IOError:
                pass
        for cache_file in self._cache_dir.glob("*.pkl"):
            try:
                cache_file.unlink()
            except IOError:
                pass
        
        self._index.clear()
        self._save_index()
        self._hits = 0
        self._misses = 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total = self._hits + self._misses
        hit_rate = self._hits / total if total > 0 else 0.0
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": hit_rate,
            "size": len(self._index),
            "max_size": self._max_size,
        }


def cache_key_from_args(*args, **kwargs) -> str:
    """
    Generate cache key from function arguments.
    
    Args:
        *args: Positional arguments
        **kwargs: Keyword arguments
        
    Returns:
        Cache key string
    """
    key_parts = [str(arg) for arg in args]
    key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
    key_str = "|".join(key_parts)
    return hashlib.sha256(key_str.encode()).hexdigest()


def memoize(cache: TTLCache[T]) -> Callable:
    """
    Decorator to memoize function results using provided cache.
    
    Args:
        cache: Cache instance to use
        
    Returns:
        Decorated function
    """
    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs) -> T:
            cache_key = cache_key_from_args(*args, **kwargs)
            result = cache.get(cache_key)
            if result is not None:
                return result
            
            result = func(*args, **kwargs)
            cache.set(cache_key, result)
            return result
        
        return wrapper
    return decorator