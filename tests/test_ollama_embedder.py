"""Tests for Ollama embeddings client."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

from roo_code.builtin_tools.ollama_embedder import OllamaEmbedder


@pytest.fixture
def mock_httpx_client():
    """Create a mock httpx.AsyncClient."""
    client = MagicMock()
    client.aclose = AsyncMock()
    return client


@pytest.fixture
def embedder(mock_httpx_client):
    """Create an OllamaEmbedder with a mocked client."""
    with patch('roo_code.builtin_tools.ollama_embedder.httpx.AsyncClient', return_value=mock_httpx_client):
        embedder = OllamaEmbedder()
        embedder.client = mock_httpx_client
        yield embedder


@pytest.mark.asyncio
async def test_embed_text_success(embedder, mock_httpx_client):
    """Test successful single text embedding."""
    # Mock response
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "embeddings": [[0.1, 0.2, 0.3]]
    }
    mock_httpx_client.post = AsyncMock(return_value=mock_response)
    
    # Test
    result = await embedder.embed_text("test text")
    
    assert result == [0.1, 0.2, 0.3]
    mock_httpx_client.post.assert_called_once()


@pytest.mark.asyncio
async def test_embed_batch_success(embedder, mock_httpx_client):
    """Test successful batch embedding."""
    # Mock response
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "embeddings": [
            [0.1, 0.2, 0.3],
            [0.4, 0.5, 0.6]
        ]
    }
    mock_httpx_client.post = AsyncMock(return_value=mock_response)
    
    # Test
    result = await embedder.embed_batch(["text1", "text2"])
    
    assert len(result) == 2
    assert result[0] == [0.1, 0.2, 0.3]
    assert result[1] == [0.4, 0.5, 0.6]


@pytest.mark.asyncio
async def test_embed_batch_empty(embedder):
    """Test embedding empty list."""
    result = await embedder.embed_batch([])
    assert result == []


@pytest.mark.asyncio
async def test_embed_batch_large(embedder, mock_httpx_client):
    """Test batch embedding with multiple batches."""
    # Create embedder with small batch size
    embedder.batch_size = 2
    
    # Mock response
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.side_effect = [
        {"embeddings": [[0.1], [0.2]]},
        {"embeddings": [[0.3]]}
    ]
    mock_httpx_client.post = AsyncMock(return_value=mock_response)
    
    # Test with 3 texts (should split into 2 batches)
    result = await embedder.embed_batch(["text1", "text2", "text3"])
    
    assert len(result) == 3
    assert mock_httpx_client.post.call_count == 2


@pytest.mark.asyncio
async def test_embed_connection_error(embedder, mock_httpx_client):
    """Test handling of connection errors."""
    mock_httpx_client.post = AsyncMock(
        side_effect=httpx.ConnectError("Connection refused")
    )
    
    with pytest.raises(httpx.HTTPError) as exc_info:
        await embedder.embed_text("test")
    
    assert "Could not connect to Ollama" in str(exc_info.value)


@pytest.mark.asyncio
async def test_embed_timeout_error(embedder, mock_httpx_client):
    """Test handling of timeout errors."""
    mock_httpx_client.post = AsyncMock(
        side_effect=httpx.TimeoutException("Timeout")
    )
    
    with pytest.raises(httpx.HTTPError) as exc_info:
        await embedder.embed_text("test")
    
    assert "timed out" in str(exc_info.value)


@pytest.mark.asyncio
async def test_embed_http_status_error(embedder, mock_httpx_client):
    """Test handling of HTTP status errors."""
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.text = "Internal Server Error"
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Error", request=MagicMock(), response=mock_response
    )
    mock_httpx_client.post = AsyncMock(return_value=mock_response)
    
    with pytest.raises(httpx.HTTPError) as exc_info:
        await embedder.embed_text("test")
    
    assert "500" in str(exc_info.value)


@pytest.mark.asyncio
async def test_embed_invalid_response(embedder, mock_httpx_client):
    """Test handling of invalid response structure."""
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"wrong_key": "value"}
    mock_httpx_client.post = AsyncMock(return_value=mock_response)
    
    with pytest.raises(ValueError) as exc_info:
        await embedder.embed_text("test")
    
    assert "Invalid response structure" in str(exc_info.value)


@pytest.mark.asyncio
async def test_embed_wrong_count(embedder, mock_httpx_client):
    """Test handling of wrong number of embeddings."""
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "embeddings": [[0.1, 0.2]]  # Only 1 embedding
    }
    mock_httpx_client.post = AsyncMock(return_value=mock_response)
    
    with pytest.raises(ValueError) as exc_info:
        await embedder.embed_batch(["text1", "text2"])  # Request 2 embeddings
    
    assert "Expected 2 embeddings but got 1" in str(exc_info.value)


@pytest.mark.asyncio
async def test_validate_configuration_success(embedder, mock_httpx_client):
    """Test successful configuration validation."""
    # Mock models list response
    models_response = MagicMock()
    models_response.raise_for_status = MagicMock()
    models_response.json.return_value = {
        "models": [
            {"name": "nomic-embed-text"},
            {"name": "other-model"}
        ]
    }
    
    # Mock test embedding response
    test_response = MagicMock()
    test_response.raise_for_status = MagicMock()
    test_response.json.return_value = {"embeddings": [[0.1]]}
    
    mock_httpx_client.get = AsyncMock(return_value=models_response)
    mock_httpx_client.post = AsyncMock(return_value=test_response)
    
    is_valid, error = await embedder.validate_configuration()
    
    assert is_valid is True
    assert error is None


@pytest.mark.asyncio
async def test_validate_configuration_service_not_running(embedder, mock_httpx_client):
    """Test validation when service is not running."""
    mock_httpx_client.get = AsyncMock(
        side_effect=httpx.ConnectError("Connection refused")
    )
    
    is_valid, error = await embedder.validate_configuration()
    
    assert is_valid is False
    assert "not running" in error


@pytest.mark.asyncio
async def test_validate_configuration_model_not_found(embedder, mock_httpx_client):
    """Test validation when model doesn't exist."""
    models_response = MagicMock()
    models_response.raise_for_status = MagicMock()
    models_response.json.return_value = {
        "models": [
            {"name": "other-model"}
        ]
    }
    mock_httpx_client.get = AsyncMock(return_value=models_response)
    
    is_valid, error = await embedder.validate_configuration()
    
    assert is_valid is False
    assert "not found" in error


@pytest.mark.asyncio
async def test_validate_configuration_timeout(embedder, mock_httpx_client):
    """Test validation timeout."""
    mock_httpx_client.get = AsyncMock(
        side_effect=httpx.TimeoutException("Timeout")
    )
    
    is_valid, error = await embedder.validate_configuration()
    
    assert is_valid is False
    assert "timed out" in error or "Timeout" in error


@pytest.mark.asyncio
async def test_context_manager():
    """Test async context manager."""
    with patch('roo_code.builtin_tools.ollama_embedder.httpx.AsyncClient') as mock_client_class:
        mock_client = MagicMock()
        mock_client.aclose = AsyncMock()
        mock_client_class.return_value = mock_client
        
        async with OllamaEmbedder() as embedder:
            assert embedder is not None
        
        mock_client.aclose.assert_called_once()


def test_get_model_info():
    """Test getting model information."""
    with patch('roo_code.builtin_tools.ollama_embedder.httpx.AsyncClient'):
        embedder = OllamaEmbedder(
            base_url="http://test:11434",
            model="test-model",
            batch_size=16
        )
        
        info = embedder.get_model_info()
        
        assert info["model"] == "test-model"
        assert info["base_url"] == "http://test:11434"
        assert info["batch_size"] == 16


def test_base_url_normalization():
    """Test that base URL trailing slashes are removed."""
    with patch('roo_code.builtin_tools.ollama_embedder.httpx.AsyncClient'):
        embedder = OllamaEmbedder(base_url="http://localhost:11434/")
        assert embedder.base_url == "http://localhost:11434"
        
        embedder = OllamaEmbedder(base_url="http://localhost:11434///")
        assert embedder.base_url == "http://localhost:11434"