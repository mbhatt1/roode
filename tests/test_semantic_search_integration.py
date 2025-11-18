"""Integration tests for semantic search functionality."""

import pytest
import tempfile
import shutil
import os
from unittest.mock import AsyncMock, MagicMock, patch

from roo_code.builtin_tools.advanced import CodebaseSearchTool
from roo_code.builtin_tools.code_indexer import CodeIndexer, IndexingConfig
from roo_code.builtin_tools.vector_store import VectorStore, CodeChunk
from roo_code.builtin_tools.ollama_embedder import OllamaEmbedder


@pytest.fixture
def temp_workspace():
    """Create a temporary workspace with sample code."""
    temp_dir = tempfile.mkdtemp()
    
    # Create sample Python files
    files = {
        "authentication.py": """
def login(username, password):
    '''Authenticate user with username and password'''
    if validate_credentials(username, password):
        return create_session(username)
    return None

def logout(session_id):
    '''End user session'''
    destroy_session(session_id)
""",
        "database.py": """
def connect_database(host, port):
    '''Establish database connection'''
    connection = DatabaseConnection(host, port)
    return connection

def execute_query(query, params):
    '''Run SQL query with parameters'''
    result = db.execute(query, params)
    return result.fetchall()
""",
        "utils.py": """
def format_date(date_obj):
    '''Format date object as string'''
    return date_obj.strftime('%Y-%m-%d')

def parse_json(json_string):
    '''Parse JSON string to dictionary'''
    import json
    return json.loads(json_string)
"""
    }
    
    for file_path, content in files.items():
        full_path = os.path.join(temp_dir, file_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, 'w') as f:
            f.write(content)
    
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def mock_embedder():
    """Create a mock embedder with deterministic embeddings."""
    embedder = MagicMock(spec=OllamaEmbedder)
    
    # Create a simple embedding function based on content
    def mock_embed_batch(texts):
        embeddings = []
        for text in texts:
            # Create deterministic embeddings based on keywords
            embedding = [0.0] * 768
            
            # Set specific dimensions based on keywords
            if 'login' in text.lower() or 'auth' in text.lower():
                embedding[0] = 0.9
            if 'database' in text.lower() or 'query' in text.lower():
                embedding[1] = 0.9
            if 'json' in text.lower() or 'parse' in text.lower():
                embedding[2] = 0.9
            if 'session' in text.lower():
                embedding[3] = 0.9
            
            embeddings.append(embedding)
        
        return embeddings
    
    embedder.embed_batch = AsyncMock(side_effect=mock_embed_batch)
    embedder.embed_text = AsyncMock(side_effect=lambda text: mock_embed_batch([text])[0])
    embedder.validate_configuration = AsyncMock(return_value=(True, None))
    embedder.close = AsyncMock()
    
    return embedder


@pytest.fixture
async def indexed_workspace(temp_workspace, mock_embedder):
    """Create and index a workspace."""
    # Create vector store
    vector_store = VectorStore(workspace_path=temp_workspace)
    await vector_store.initialize()
    
    # Create indexer
    indexer = CodeIndexer(
        workspace_path=temp_workspace,
        vector_store=vector_store,
        embedder=mock_embedder,
        config=IndexingConfig(chunk_size=200, chunk_overlap=20)
    )
    
    # Index the workspace
    stats = await indexer.index_workspace()
    
    yield {
        "workspace": temp_workspace,
        "vector_store": vector_store,
        "embedder": mock_embedder,
        "stats": stats
    }
    
    # Cleanup
    vector_store.close()


@pytest.mark.asyncio
async def test_end_to_end_indexing_and_search(indexed_workspace):
    """Test complete workflow from indexing to search."""
    workspace = indexed_workspace["workspace"]
    stats = indexed_workspace["stats"]
    
    # Verify indexing succeeded
    assert stats["files_processed"] > 0
    assert stats["chunks_created"] > 0
    
    # Verify store has data
    store_stats = await indexed_workspace["vector_store"].get_stats()
    assert store_stats["total_chunks"] > 0


@pytest.mark.asyncio
async def test_search_authentication_code(indexed_workspace):
    """Test searching for authentication-related code."""
    vector_store = indexed_workspace["vector_store"]
    embedder = indexed_workspace["embedder"]
    
    # Search for authentication code
    query = "user login authentication"
    query_embedding = await embedder.embed_text(query)
    
    results = await vector_store.search(
        query_embedding=query_embedding,
        max_results=5,
        min_score=0.1
    )
    
    # Should find authentication.py
    assert len(results) > 0
    auth_results = [r for r in results if 'authentication.py' in r.chunk.file_path]
    assert len(auth_results) > 0
    
    # Should contain relevant code
    assert any('login' in r.chunk.content.lower() for r in auth_results)


@pytest.mark.asyncio
async def test_search_database_code(indexed_workspace):
    """Test searching for database-related code."""
    vector_store = indexed_workspace["vector_store"]
    embedder = indexed_workspace["embedder"]
    
    query = "database query connection"
    query_embedding = await embedder.embed_text(query)
    
    results = await vector_store.search(
        query_embedding=query_embedding,
        max_results=5,
        min_score=0.1
    )
    
    # Should find database.py
    db_results = [r for r in results if 'database.py' in r.chunk.file_path]
    assert len(db_results) > 0


@pytest.mark.asyncio
async def test_search_with_file_pattern(indexed_workspace):
    """Test search with file pattern filtering."""
    vector_store = indexed_workspace["vector_store"]
    embedder = indexed_workspace["embedder"]
    
    query = "function code"
    query_embedding = await embedder.embed_text(query)
    
    # Search only in utils.py
    results = await vector_store.search(
        query_embedding=query_embedding,
        max_results=10,
        file_pattern="utils"
    )
    
    # All results should be from utils.py
    assert all('utils.py' in r.chunk.file_path for r in results)


@pytest.mark.asyncio
async def test_search_no_results(indexed_workspace):
    """Test search that returns no results due to low similarity."""
    vector_store = indexed_workspace["vector_store"]
    embedder = indexed_workspace["embedder"]
    
    # Query with very high threshold
    query = "something completely unrelated"
    query_embedding = await embedder.embed_text(query)
    
    results = await vector_store.search(
        query_embedding=query_embedding,
        max_results=5,
        min_score=0.99  # Very high threshold
    )
    
    # Should return few or no results
    assert len(results) == 0 or len(results) < 3


@pytest.mark.asyncio
async def test_incremental_update(indexed_workspace, mock_embedder):
    """Test incremental index update when file changes."""
    workspace = indexed_workspace["workspace"]
    vector_store = indexed_workspace["vector_store"]
    
    # Create indexer
    indexer = CodeIndexer(
        workspace_path=workspace,
        vector_store=vector_store,
        embedder=mock_embedder
    )
    
    # Modify a file
    new_file = os.path.join(workspace, "new_module.py")
    with open(new_file, 'w') as f:
        f.write("""
def new_function():
    '''A brand new function'''
    return "new"
""")
    
    # Index just the new file
    stats = await indexer.index_files(["new_module.py"])
    
    assert stats["files_processed"] == 1
    assert stats["chunks_created"] > 0
    
    # Verify it's searchable
    query_embedding = await mock_embedder.embed_text("new function")
    results = await vector_store.search(query_embedding, max_results=10)
    
    new_results = [r for r in results if 'new_module.py' in r.chunk.file_path]
    assert len(new_results) > 0


@pytest.mark.asyncio
async def test_delete_and_reindex(indexed_workspace, mock_embedder):
    """Test deleting and reindexing a file."""
    workspace = indexed_workspace["workspace"]
    vector_store = indexed_workspace["vector_store"]
    
    indexer = CodeIndexer(
        workspace_path=workspace,
        vector_store=vector_store,
        embedder=mock_embedder
    )
    
    # Delete chunks for a file
    await indexer.delete_files(["authentication.py"])
    
    # Search should not find deleted file
    query_embedding = await mock_embedder.embed_text("login authentication")
    results = await vector_store.search(query_embedding, max_results=10)
    
    auth_results = [r for r in results if 'authentication.py' in r.chunk.file_path]
    # Should have fewer or no results from authentication.py
    
    # Reindex the file
    await indexer.index_files(["authentication.py"])
    
    # Should be findable again
    results = await vector_store.search(query_embedding, max_results=10)
    auth_results = [r for r in results if 'authentication.py' in r.chunk.file_path]
    assert len(auth_results) > 0


@pytest.mark.asyncio
async def test_codebase_search_tool_integration(temp_workspace, mock_embedder):
    """Test CodebaseSearchTool with mocked Ollama."""
    # Patch the embedder creation
    with patch('roo_code.builtin_tools.advanced.OllamaEmbedder', return_value=mock_embedder):
        tool = CodebaseSearchTool(workspace_path=temp_workspace)
        
        # Initialize and index
        await tool._ensure_initialized()
        
        vector_store = tool._vector_store
        indexer = CodeIndexer(
            workspace_path=temp_workspace,
            vector_store=vector_store,
            embedder=mock_embedder
        )
        await indexer.index_workspace()
        
        # Execute search
        result = await tool.execute({
            "query": "authentication login",
            "max_results": 3
        })
        
        assert result.is_error is False
        assert "authentication" in result.content.lower() or "login" in result.content.lower()
        
        # Cleanup
        await tool.cleanup()


@pytest.mark.asyncio
async def test_codebase_search_tool_empty_index(temp_workspace, mock_embedder):
    """Test CodebaseSearchTool with empty index."""
    with patch('roo_code.builtin_tools.advanced.OllamaEmbedder', return_value=mock_embedder):
        tool = CodebaseSearchTool(workspace_path=temp_workspace)
        
        # Initialize but don't index
        await tool._ensure_initialized()
        
        # Execute search on empty index
        result = await tool.execute({
            "query": "test",
            "max_results": 5
        })
        
        assert result.is_error is True
        assert "empty" in result.content.lower()
        
        await tool.cleanup()


@pytest.mark.asyncio
async def test_codebase_search_tool_no_results(indexed_workspace, mock_embedder):
    """Test CodebaseSearchTool when no results match."""
    workspace = indexed_workspace["workspace"]
    
    with patch('roo_code.builtin_tools.advanced.OllamaEmbedder', return_value=mock_embedder):
        tool = CodebaseSearchTool(workspace_path=workspace)
        tool._vector_store = indexed_workspace["vector_store"]
        tool._embedder = mock_embedder
        
        # Search with very high threshold
        result = await tool.execute({
            "query": "nonexistent code pattern",
            "max_results": 5,
            "min_score": 0.99
        })
        
        assert "No results found" in result.content
        
        await tool.cleanup()


@pytest.mark.asyncio
async def test_performance_large_codebase(temp_workspace, mock_embedder):
    """Test performance with larger codebase."""
    # Create multiple files
    for i in range(10):
        file_path = os.path.join(temp_workspace, f"module_{i}.py")
        with open(file_path, 'w') as f:
            f.write(f"""
def function_{i}_a():
    '''Function {i} part a'''
    return {i}

def function_{i}_b():
    '''Function {i} part b'''
    return {i} * 2

class Class_{i}:
    '''Class number {i}'''
    def method(self):
        return {i}
""")
    
    # Index all files
    vector_store = VectorStore(workspace_path=temp_workspace)
    await vector_store.initialize()
    
    indexer = CodeIndexer(
        workspace_path=temp_workspace,
        vector_store=vector_store,
        embedder=mock_embedder
    )
    
    import time
    start = time.time()
    stats = await indexer.index_workspace()
    index_time = time.time() - start
    
    # Should complete in reasonable time
    assert index_time < 30  # 30 seconds for 10 files
    assert stats["files_processed"] >= 10
    assert stats["chunks_created"] > 10
    
    # Test search performance
    query_embedding = await mock_embedder.embed_text("function code")
    
    start = time.time()
    results = await vector_store.search(query_embedding, max_results=10)
    search_time = time.time() - start
    
    # Search should be fast
    assert search_time < 1  # Under 1 second
    assert len(results) > 0
    
    vector_store.close()


@pytest.mark.asyncio
async def test_ollama_unavailable_fallback(temp_workspace):
    """Test graceful fallback when Ollama is unavailable."""
    mock_embedder = MagicMock(spec=OllamaEmbedder)
    mock_embedder.validate_configuration = AsyncMock(
        return_value=(False, "Ollama service is not running")
    )
    
    with patch('roo_code.builtin_tools.advanced.OllamaEmbedder', return_value=mock_embedder):
        tool = CodebaseSearchTool(workspace_path=temp_workspace)
        
        result = await tool.execute({
            "query": "test",
            "max_results": 5
        })
        
        assert result.is_error is True
        assert "not available" in result.content.lower()


@pytest.mark.asyncio  
async def test_chunk_metadata_preserved(indexed_workspace):
    """Test that chunk metadata is preserved through indexing and search."""
    vector_store = indexed_workspace["vector_store"]
    embedder = indexed_workspace["embedder"]
    
    query_embedding = await embedder.embed_text("function")
    results = await vector_store.search(query_embedding, max_results=5)
    
    assert len(results) > 0
    
    for result in results:
        chunk = result.chunk
        # Verify all metadata is present
        assert chunk.file_path
        assert chunk.start_line > 0
        assert chunk.end_line >= chunk.start_line
        assert chunk.chunk_type in ['function', 'class', 'method', 'block']
        assert chunk.language in ['python', 'unknown']
        assert chunk.content.strip()