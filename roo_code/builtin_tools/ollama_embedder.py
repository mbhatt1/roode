"""Ollama embeddings client for generating code embeddings."""

import asyncio
import hashlib
from typing import List, Optional
from dataclasses import dataclass

import httpx

from .cache import PersistentCache


@dataclass
class EmbedderConfig:
    """Configuration for Ollama embedder."""
    
    base_url: str = "http://localhost:11434"
    model: str = "nomic-embed-text"
    timeout: float = 60.0
    batch_size: int = 32


class OllamaEmbedder:
    """Client for generating embeddings using Ollama."""
    
    # Timeout constants
    EMBEDDING_TIMEOUT = 60.0  # 60 seconds for embedding requests
    VALIDATION_TIMEOUT = 30.0  # 30 seconds for validation requests
    
    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "nomic-embed-text",
        timeout: float = 60.0,
        batch_size: int = 32,
        cache_dir: Optional[str] = None
    ):
        """
        Initialize Ollama embedder.
        
        Args:
            base_url: Ollama server URL (default: http://localhost:11434)
            model: Embedding model name (default: nomic-embed-text)
            timeout: Request timeout in seconds (default: 60.0)
            batch_size: Number of texts to embed in a single batch (default: 32)
            cache_dir: Directory for persistent embedding cache (default: .roo/embedding_cache)
        """
        # Normalize base URL by removing trailing slashes
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.batch_size = batch_size
        
        # Create async HTTP client with connection pooling
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5)
        )
        
        # Initialize persistent cache
        if cache_dir is None:
            cache_dir = ".roo/embedding_cache"
        self.cache = PersistentCache[List[float]](
            cache_dir=cache_dir,
            max_size=10000,
            use_json=True
        )
    
    def _get_cache_key(self, text: str) -> str:
        """Generate cache key for text embedding."""
        # Include model name in key to avoid conflicts between models
        key_str = f"{self.model}:{text}"
        return hashlib.sha256(key_str.encode()).hexdigest()
    
    async def embed_text(self, text: str) -> List[float]:
        """
        Generate embeddings for a single text with caching.
        
        Args:
            text: Text to embed
            
        Returns:
            List of embedding values
            
        Raises:
            httpx.HTTPError: If the request fails
            ValueError: If the response is invalid
        """
        # Check cache first
        cache_key = self._get_cache_key(text)
        cached_embedding = self.cache.get(cache_key)
        if cached_embedding is not None:
            return cached_embedding
        
        # Generate embedding
        result = await self.embed_batch([text])
        embedding = result[0]
        
        # Cache the result
        self.cache.set(cache_key, embedding)
        
        return embedding
    
    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts efficiently with caching.
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of embedding vectors, one per input text
            
        Raises:
            httpx.HTTPError: If the request fails
            ValueError: If the response is invalid
        """
        if not texts:
            return []
        
        # Check which texts need to be embedded (not in cache)
        all_embeddings: List[Optional[List[float]]] = []
        texts_to_embed: List[tuple[int, str]] = []  # (index, text)
        
        for i, text in enumerate(texts):
            cache_key = self._get_cache_key(text)
            cached_embedding = self.cache.get(cache_key)
            if cached_embedding is not None:
                all_embeddings.append(cached_embedding)
            else:
                all_embeddings.append(None)  # Placeholder
                texts_to_embed.append((i, text))
        
        # If all texts were cached, return immediately
        if not texts_to_embed:
            return all_embeddings  # type: ignore
        
        # Embed texts that weren't in cache
        texts_only = [text for _, text in texts_to_embed]
        
        # Process in batches to avoid overwhelming the server
        batch_embeddings: List[List[float]] = []
        for i in range(0, len(texts_only), self.batch_size):
            batch = texts_only[i:i + self.batch_size]
            batch_result = await self._embed_batch_internal(batch)
            batch_embeddings.extend(batch_result)
        
        # Cache and fill in the results
        for (original_idx, text), embedding in zip(texts_to_embed, batch_embeddings):
            cache_key = self._get_cache_key(text)
            self.cache.set(cache_key, embedding)
            all_embeddings[original_idx] = embedding
        
        return all_embeddings  # type: ignore
    
    async def _embed_batch_internal(self, texts: List[str]) -> List[List[float]]:
        """
        Internal method to embed a single batch.
        
        Args:
            texts: List of texts to embed (should be <= batch_size)
            
        Returns:
            List of embedding vectors
            
        Raises:
            httpx.HTTPError: If the request fails
            ValueError: If the response is invalid
        """
        url = f"{self.base_url}/api/embed"
        
        try:
            response = await self.client.post(
                url,
                json={
                    "model": self.model,
                    "input": texts
                },
                timeout=self.EMBEDDING_TIMEOUT
            )
            response.raise_for_status()
            
            data = response.json()
            
            # Extract embeddings from response
            embeddings = data.get("embeddings")
            if not embeddings or not isinstance(embeddings, list):
                raise ValueError(
                    f"Invalid response structure from Ollama: missing or invalid 'embeddings' field"
                )
            
            # Validate we got the right number of embeddings
            if len(embeddings) != len(texts):
                raise ValueError(
                    f"Expected {len(texts)} embeddings but got {len(embeddings)}"
                )
            
            return embeddings
            
        except httpx.TimeoutException as e:
            raise httpx.HTTPError(
                f"Ollama request timed out after {self.EMBEDDING_TIMEOUT}s"
            ) from e
        except httpx.ConnectError as e:
            raise httpx.HTTPError(
                f"Could not connect to Ollama at {self.base_url}. "
                f"Make sure Ollama is running."
            ) from e
        except httpx.HTTPStatusError as e:
            raise httpx.HTTPError(
                f"Ollama request failed with status {e.response.status_code}: "
                f"{e.response.text}"
            ) from e
    
    async def validate_configuration(self) -> tuple[bool, Optional[str]]:
        """
        Validate the Ollama embedder configuration.
        
        Checks if:
        1. Ollama service is running
        2. The specified model exists
        3. The model supports embeddings
        
        Returns:
            Tuple of (is_valid, error_message)
            If valid, error_message is None
        """
        try:
            # Check if Ollama service is running by listing models
            models_url = f"{self.base_url}/api/tags"
            
            try:
                response = await self.client.get(
                    models_url,
                    timeout=self.VALIDATION_TIMEOUT
                )
                response.raise_for_status()
            except httpx.ConnectError:
                return False, f"Ollama service is not running at {self.base_url}"
            except httpx.TimeoutException:
                return False, f"Connection to Ollama at {self.base_url} timed out"
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    return False, f"Ollama service not found at {self.base_url}"
                return False, f"Ollama service unavailable (status {e.response.status_code})"
            
            # Check if the specific model exists
            models_data = response.json()
            models = models_data.get("models", [])
            
            # Check both with and without :latest suffix
            model_exists = any(
                m.get("name") == self.model or
                m.get("name") == f"{self.model}:latest" or
                m.get("name") == self.model.replace(":latest", "")
                for m in models
            )
            
            if not model_exists:
                available_models = ", ".join(m.get("name", "unknown") for m in models)
                return False, (
                    f"Model '{self.model}' not found. "
                    f"Available models: {available_models or 'none'}"
                )
            
            # Try a test embedding to ensure the model works
            test_url = f"{self.base_url}/api/embed"
            
            try:
                test_response = await self.client.post(
                    test_url,
                    json={
                        "model": self.model,
                        "input": ["test"]
                    },
                    timeout=self.VALIDATION_TIMEOUT
                )
                test_response.raise_for_status()
                
                # Verify response structure
                test_data = test_response.json()
                if "embeddings" not in test_data:
                    return False, f"Model '{self.model}' does not support embeddings"
                    
            except httpx.HTTPStatusError as e:
                return False, (
                    f"Model '{self.model}' failed test embedding "
                    f"(status {e.response.status_code})"
                )
            
            return True, None
            
        except Exception as e:
            return False, f"Validation failed: {str(e)}"
    
    def clear_cache(self) -> None:
        """Clear the embedding cache."""
        self.cache.clear()
    
    def get_cache_stats(self) -> dict:
        """Get cache statistics."""
        return self.cache.get_stats()
    
    async def close(self) -> None:
        """Close the HTTP client and clean up resources."""
        await self.client.aclose()
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
    
    def get_model_info(self) -> dict:
        """
        Get information about the configured model.
        
        Returns:
            Dictionary with model configuration
        """
        return {
            "model": self.model,
            "base_url": self.base_url,
            "batch_size": self.batch_size,
            "timeout": self.timeout
        }