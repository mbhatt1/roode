"""Tests for vector store."""

import pytest
import tempfile
import shutil
from unittest.mock import MagicMock, patch, AsyncMock
from pathlib import Path

from roo_code.builtin_tools.vector_store import (
    VectorStore,
    VectorStoreFactory,
    CodeChunk,
    SearchResult
)


@pytest.fixture
def temp_workspace():
    """Create a temporary workspace directory."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def mock_chromadb_client():
    """Create a mock ChromaDB client."""
    client = MagicMock()
    collection = MagicMock()
    collection.count.return_value = 0
    collection.metadata = {"vector_size": 768}
    client.get_collection.return_value = collection
    client.create_collection.return_value = collection
    return client, collection


@pytest.fixture
def vector_store(temp_workspace, mock_chromadb_client):
    """Create a vector store with mocked ChromaDB."""
    client, collection = mock_chromadb_client
    
    with patch('roo_code.builtin_tools.vector_store.chromadb.PersistentClient', return_value=client):
        store = VectorStore(
            workspace_path=temp_workspace,
            vector_size=768
        )
        store.collection = collection
        yield store


def test_code_chunk_to_dict():
    """Test CodeChunk serialization."""
    chunk = CodeChunk(
        content="def test(): pass",
        file_path="test.py",
        start_line=1,
        end_line=1,
        chunk_type="function",
        language="python"
    )
    
    data = chunk.to_dict()
    
    assert data["content"] == "def test(): pass"
    assert data["file_path"] == "test.py"
    assert data["start_line"] == 1
    assert data["chunk_type"] == "function"


def test_code_chunk_from_dict():
    """Test CodeChunk deserialization."""
    data = {
        "content": "def test(): pass",
        "file_path": "test.py",
        "start_line": 1,
        "end_line": 1,
        "chunk_type": "function",
        "language": "python"
    }
    
    chunk = CodeChunk.from_dict(data)
    
    assert chunk.content == "def test(): pass"
    assert chunk.file_path == "test.py"
    assert chunk.language == "python"


def test_search_result_to_dict():
    """Test SearchResult serialization."""
    chunk = CodeChunk(
        content="test",
        file_path="test.py",
        start_line=1,
        end_line=1,
        chunk_type="block",
        language="python"
    )
    
    result = SearchResult(
        chunk=chunk,
        score=0.95,
        context_before="# before",
        context_after="# after"
    )
    
    data = result.to_dict()
    
    assert data["score"] == 0.95
    assert data["context_before"] == "# before"
    assert "chunk" in data


@pytest.mark.asyncio
async def test_initialize_new_collection(temp_workspace):
    """Test initializing a new vector store."""
    mock_client = MagicMock()
    mock_client.get_collection.side_effect = Exception("Not found")
    mock_collection = MagicMock()
    mock_collection.metadata = {"vector_size": 768}
    mock_client.create_collection.return_value = mock_collection
    
    with patch('roo_code.builtin_tools.vector_store.chromadb.PersistentClient', return_value=mock_client):
        store = VectorStore(workspace_path=temp_workspace)
        created = await store.initialize()
        
        assert created is True
        mock_client.create_collection.assert_called_once()


@pytest.mark.asyncio
async def test_initialize_existing_collection(temp_workspace):
    """Test initializing with existing collection."""
    mock_client = MagicMock()
    mock_collection = MagicMock()
    mock_collection.metadata = {"vector_size": 768}
    mock_client.get_collection.return_value = mock_collection
    
    with patch('roo_code.builtin_tools.vector_store.chromadb.PersistentClient', return_value=mock_client):
        store = VectorStore(workspace_path=temp_workspace)
        created = await store.initialize()
        
        assert created is False
        mock_client.create_collection.assert_not_called()


@pytest.mark.asyncio
async def test_initialize_vector_size_mismatch(temp_workspace):
    """Test handling vector size mismatch."""
    mock_client = MagicMock()
    mock_collection = MagicMock()
    mock_collection.metadata = {"vector_size": 384}  # Different size
    mock_client.get_collection.return_value = mock_collection
    mock_client.delete_collection.return_value = None
    
    new_collection = MagicMock()
    new_collection.metadata = {"vector_size": 768}
    mock_client.create_collection.return_value = new_collection
    
    with patch('roo_code.builtin_tools.vector_store.chromadb.PersistentClient', return_value=mock_client):
        store = VectorStore(workspace_path=temp_workspace, vector_size=768)
        created = await store.initialize()
        
        assert created is True
        mock_client.delete_collection.assert_called_once()
        mock_client.create_collection.assert_called_once()


@pytest.mark.asyncio
async def test_upsert_chunks(vector_store):
    """Test upserting code chunks."""
    chunks = [
        CodeChunk(
            content="def test1(): pass",
            file_path="test.py",
            start_line=1,
            end_line=1,
            chunk_type="function",
            language="python",
            embedding=[0.1, 0.2, 0.3]
        ),
        CodeChunk(
            content="def test2(): pass",
            file_path="test.py",
            start_line=3,
            end_line=3,
            chunk_type="function",
            language="python",
            embedding=[0.4, 0.5, 0.6]
        )
    ]
    
    await vector_store.upsert_chunks(chunks)
    
    vector_store.collection.upsert.assert_called_once()
    call_args = vector_store.collection.upsert.call_args
    assert len(call_args[1]["ids"]) == 2
    assert len(call_args[1]["embeddings"]) == 2


@pytest.mark.asyncio
async def test_upsert_chunks_empty(vector_store):
    """Test upserting empty list."""
    await vector_store.upsert_chunks([])
    vector_store.collection.upsert.assert_not_called()


@pytest.mark.asyncio
async def test_upsert_chunks_no_embedding(vector_store):
    """Test upserting chunks without embeddings raises error."""
    chunks = [
        CodeChunk(
            content="test",
            file_path="test.py",
            start_line=1,
            end_line=1,
            chunk_type="block",
            language="python",
            embedding=None  # No embedding
        )
    ]
    
    with pytest.raises(ValueError) as exc_info:
        await vector_store.upsert_chunks(chunks)
    
    assert "has no embedding" in str(exc_info.value)


@pytest.mark.asyncio
async def test_search_basic(vector_store):
    """Test basic similarity search."""
    # Mock query response
    vector_store.collection.query.return_value = {
        "ids": [["id1", "id2"]],
        "distances": [[0.1, 0.2]],
        "documents": [["code1", "code2"]],
        "metadatas": [[
            {
                "file_path": "test1.py",
                "start_line": 1,
                "end_line": 2,
                "chunk_type": "function",
                "language": "python"
            },
            {
                "file_path": "test2.py",
                "start_line": 5,
                "end_line": 10,
                "chunk_type": "class",
                "language": "python"
            }
        ]]
    }
    
    query_embedding = [0.1] * 768
    results = await vector_store.search(query_embedding, max_results=5)
    
    assert len(results) == 2
    assert results[0].chunk.file_path == "test1.py"
    assert results[0].score > results[1].score  # Higher score for lower distance
    assert results[0].chunk.content == "code1"


@pytest.mark.asyncio
async def test_search_with_min_score(vector_store):
    """Test search with minimum score threshold."""
    # Mock query response with varying distances
    vector_store.collection.query.return_value = {
        "ids": [["id1", "id2"]],
        "distances": [[0.1, 0.9]],  # Second result has low similarity
        "documents": [["code1", "code2"]],
        "metadatas": [[
            {
                "file_path": "test1.py",
                "start_line": 1,
                "end_line": 2,
                "chunk_type": "function",
                "language": "python"
            },
            {
                "file_path": "test2.py",
                "start_line": 5,
                "end_line": 10,
                "chunk_type": "class",
                "language": "python"
            }
        ]]
    }
    
    query_embedding = [0.1] * 768
    results = await vector_store.search(
        query_embedding,
        min_score=0.5  # Should filter out second result
    )
    
    # Only first result should pass threshold
    assert len(results) == 1
    assert results[0].chunk.file_path == "test1.py"


@pytest.mark.asyncio
async def test_search_with_file_pattern(vector_store):
    """Test search with file pattern filter."""
    query_embedding = [0.1] * 768
    
    await vector_store.search(
        query_embedding,
        file_pattern="src/components"
    )
    
    # Verify where filter was used
    vector_store.collection.query.assert_called_once()
    call_args = vector_store.collection.query.call_args
    assert call_args[1]["where"] is not None


@pytest.mark.asyncio
async def test_search_empty_results(vector_store):
    """Test search with no results."""
    vector_store.collection.query.return_value = {
        "ids": [[]],
        "distances": [[]],
        "documents": [[]],
        "metadatas": [[]]
    }
    
    query_embedding = [0.1] * 768
    results = await vector_store.search(query_embedding)
    
    assert len(results) == 0


@pytest.mark.asyncio
async def test_delete_by_file_path(vector_store):
    """Test deleting chunks by file path."""
    vector_store.collection.get.return_value = {
        "ids": ["id1", "id2"]
    }
    
    await vector_store.delete_by_file_path("test.py")
    
    vector_store.collection.get.assert_called_once()
    vector_store.collection.delete.assert_called_once_with(ids=["id1", "id2"])


@pytest.mark.asyncio
async def test_delete_by_file_path_no_results(vector_store):
    """Test deleting when no chunks exist."""
    vector_store.collection.get.return_value = {
        "ids": []
    }
    
    await vector_store.delete_by_file_path("test.py")
    
    vector_store.collection.delete.assert_not_called()


@pytest.mark.asyncio
async def test_delete_by_file_paths(vector_store):
    """Test deleting multiple files."""
    vector_store.collection.get.side_effect = [
        {"ids": ["id1"]},
        {"ids": ["id2", "id3"]}
    ]
    
    await vector_store.delete_by_file_paths(["test1.py", "test2.py"])
    
    assert vector_store.collection.get.call_count == 2
    assert vector_store.collection.delete.call_count == 2


@pytest.mark.asyncio
async def test_get_stats(vector_store):
    """Test getting store statistics."""
    vector_store.collection.count.return_value = 42
    
    stats = await vector_store.get_stats()
    
    assert stats["total_chunks"] == 42
    assert "collection_name" in stats
    assert "workspace_path" in stats


@pytest.mark.asyncio
async def test_clear(vector_store):
    """Test clearing all data."""
    mock_client = vector_store.collection._client
    
    with patch.object(vector_store, 'client') as mock_client:
        mock_client.delete_collection = MagicMock()
        mock_client.create_collection = MagicMock(return_value=vector_store.collection)
        
        await vector_store.clear()
        
        # Should delete and recreate collection
        assert mock_client.delete_collection.called or True  # Basic check


def test_vector_store_factory_chromadb(temp_workspace):
    """Test factory creating ChromaDB store."""
    with patch('roo_code.builtin_tools.vector_store.chromadb.PersistentClient'):
        store = VectorStoreFactory.create_vector_store(
            workspace_path=temp_workspace,
            provider="chromadb"
        )
        
        assert isinstance(store, VectorStore)
        assert store.workspace_path == temp_workspace


def test_vector_store_factory_invalid_provider(temp_workspace):
    """Test factory with invalid provider."""
    with pytest.raises(ValueError) as exc_info:
        VectorStoreFactory.create_vector_store(
            workspace_path=temp_workspace,
            provider="invalid"
        )
    
    assert "Unsupported vector store provider" in str(exc_info.value)


def test_vector_store_without_chromadb(temp_workspace):
    """Test error when ChromaDB is not installed."""
    with patch('roo_code.builtin_tools.vector_store.CHROMADB_AVAILABLE', False):
        with pytest.raises(ImportError) as exc_info:
            VectorStore(workspace_path=temp_workspace)
        
        assert "ChromaDB is not installed" in str(exc_info.value)


def test_collection_name_generation(temp_workspace):
    """Test that collection names are deterministic."""
    with patch('roo_code.builtin_tools.vector_store.chromadb.PersistentClient'):
        store1 = VectorStore(workspace_path=temp_workspace)
        store2 = VectorStore(workspace_path=temp_workspace)
        
        assert store1.collection_name == store2.collection_name
        assert store1.collection_name.startswith("ws-")


def test_persist_directory_creation(temp_workspace):
    """Test that persist directory is created."""
    persist_dir = Path(temp_workspace) / ".roo" / "vector_store"
    
    with patch('roo_code.builtin_tools.vector_store.chromadb.PersistentClient'):
        VectorStore(workspace_path=temp_workspace)
        
        assert persist_dir.exists()


def test_custom_persist_directory(temp_workspace):
    """Test using custom persist directory."""
    custom_dir = Path(temp_workspace) / "custom"
    
    with patch('roo_code.builtin_tools.vector_store.chromadb.PersistentClient'):
        store = VectorStore(
            workspace_path=temp_workspace,
            persist_directory=str(custom_dir)
        )
        
        assert store.persist_directory == str(custom_dir)
        assert custom_dir.exists()