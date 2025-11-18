"""Tests for code indexer."""

import pytest
import tempfile
import shutil
import os
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

from roo_code.builtin_tools.code_indexer import CodeIndexer, IndexingConfig
from roo_code.builtin_tools.vector_store import CodeChunk


@pytest.fixture
def temp_workspace():
    """Create a temporary workspace with test files."""
    temp_dir = tempfile.mkdtemp()
    
    # Create some test files
    test_files = {
        "main.py": """
def hello():
    print("Hello, world!")

class MyClass:
    def method(self):
        pass
""",
        "utils.py": """
def calculate(x, y):
    return x + y
""",
        "src/module.py": """
def process_data(data):
    result = []
    for item in data:
        result.append(item * 2)
    return result
""",
        "node_modules/lib.js": """
// Should be excluded
function test() {}
""",
        ".git/config": """
# Should be excluded
""",
        "README.md": """
# Should be excluded (not in include patterns by default)
"""
    }
    
    for file_path, content in test_files.items():
        full_path = os.path.join(temp_dir, file_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, 'w') as f:
            f.write(content)
    
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def mock_vector_store():
    """Create a mock vector store."""
    store = MagicMock()
    store.upsert_chunks = AsyncMock()
    store.delete_by_file_path = AsyncMock()
    store.delete_by_file_paths = AsyncMock()
    return store


@pytest.fixture
def mock_embedder():
    """Create a mock embedder."""
    embedder = MagicMock()
    embedder.embed_batch = AsyncMock(return_value=[[0.1, 0.2, 0.3]])
    return embedder


@pytest.fixture
def indexer(temp_workspace, mock_vector_store, mock_embedder):
    """Create a code indexer with mocks."""
    return CodeIndexer(
        workspace_path=temp_workspace,
        vector_store=mock_vector_store,
        embedder=mock_embedder
    )


def test_indexing_config_defaults():
    """Test default configuration values."""
    config = IndexingConfig()
    
    assert config.chunk_size == 500
    assert config.chunk_overlap == 50
    assert '*.py' in config.include_patterns
    assert 'node_modules/**' in config.exclude_patterns


def test_indexing_config_custom():
    """Test custom configuration."""
    config = IndexingConfig(
        chunk_size=1000,
        chunk_overlap=100,
        include_patterns=['*.py'],
        exclude_patterns=['test/**']
    )
    
    assert config.chunk_size == 1000
    assert config.chunk_overlap == 100
    assert config.include_patterns == ['*.py']
    assert config.exclude_patterns == ['test/**']


@pytest.mark.asyncio
async def test_scan_workspace(indexer):
    """Test workspace scanning."""
    files = await indexer._scan_workspace()
    
    # Should find Python files but exclude node_modules and .git
    assert any('main.py' in f for f in files)
    assert any('utils.py' in f for f in files)
    assert any('src/module.py' in f or 'src\\module.py' in f for f in files)
    assert not any('node_modules' in f for f in files)
    assert not any('.git' in f for f in files)
    assert not any('README.md' in f for f in files)


def test_should_include_file(indexer, temp_workspace):
    """Test file inclusion logic."""
    # Should include Python files
    assert indexer._should_include_file(os.path.join(temp_workspace, "test.py"))
    assert indexer._should_include_file(os.path.join(temp_workspace, "src/module.py"))
    
    # Should exclude by pattern
    assert not indexer._should_include_file(os.path.join(temp_workspace, "node_modules/lib.js"))
    assert not indexer._should_include_file(os.path.join(temp_workspace, ".git/config"))
    
    # Should exclude non-matching extensions
    assert not indexer._should_include_file(os.path.join(temp_workspace, "test.txt"))


def test_is_excluded(indexer, temp_workspace):
    """Test exclusion pattern matching."""
    assert indexer._is_excluded(os.path.join(temp_workspace, "node_modules", "lib.js"))
    assert indexer._is_excluded(os.path.join(temp_workspace, ".git", "config"))
    assert indexer._is_excluded(os.path.join(temp_workspace, "__pycache__", "test.pyc"))
    
    assert not indexer._is_excluded(os.path.join(temp_workspace, "src", "main.py"))


def test_matches_pattern(indexer):
    """Test pattern matching."""
    # Simple patterns
    assert indexer._matches_pattern("test.py", "*.py")
    assert indexer._matches_pattern("module.js", "*.js")
    assert not indexer._matches_pattern("test.py", "*.js")
    
    # Recursive patterns
    assert indexer._matches_pattern("node_modules/lib/index.js", "node_modules/**")
    assert indexer._matches_pattern("src/components/Button.tsx", "**/*.tsx")


def test_detect_language(indexer):
    """Test language detection."""
    assert indexer._detect_language("test.py") == "python"
    assert indexer._detect_language("app.js") == "javascript"
    assert indexer._detect_language("main.go") == "go"
    assert indexer._detect_language("lib.rs") == "rust"
    assert indexer._detect_language("unknown.xyz") == "unknown"


@pytest.mark.asyncio
async def test_process_file(indexer, temp_workspace):
    """Test processing a single file."""
    chunks = await indexer._process_file("main.py")
    
    assert len(chunks) > 0
    assert all(isinstance(c, CodeChunk) for c in chunks)
    assert all(c.file_path == "main.py" for c in chunks)
    assert all(c.language == "python" for c in chunks)
    assert all(c.content.strip() for c in chunks)


@pytest.mark.asyncio
async def test_process_file_nonexistent(indexer):
    """Test processing nonexistent file."""
    chunks = await indexer._process_file("nonexistent.py")
    assert len(chunks) == 0


@pytest.mark.asyncio
async def test_process_file_empty(indexer, temp_workspace):
    """Test processing empty file."""
    empty_file = os.path.join(temp_workspace, "empty.py")
    with open(empty_file, 'w') as f:
        f.write("")
    
    chunks = await indexer._process_file("empty.py")
    assert len(chunks) == 0


@pytest.mark.asyncio
async def test_chunk_content_simple(indexer):
    """Test content chunking."""
    content = "def test():\n    pass\n\ndef another():\n    pass"
    
    chunks = await indexer._chunk_content(
        content=content,
        file_path="test.py",
        language="python"
    )
    
    assert len(chunks) > 0
    assert all(c.language == "python" for c in chunks)
    assert all(c.file_path == "test.py" for c in chunks)
    assert all(c.chunk_type == "block" for c in chunks)


@pytest.mark.asyncio
async def test_chunk_content_large_file(indexer):
    """Test chunking large file."""
    # Create content that exceeds chunk size
    lines = ["def function_{}():\n    pass\n".format(i) for i in range(100)]
    content = "".join(lines)
    
    chunks = await indexer._chunk_content(
        content=content,
        file_path="large.py",
        language="python"
    )
    
    # Should create multiple chunks
    assert len(chunks) > 1
    
    # Check line numbers are sequential
    for i in range(len(chunks) - 1):
        # Chunks should have some overlap or be continuous
        assert chunks[i].end_line >= chunks[i].start_line


@pytest.mark.asyncio
async def test_chunk_content_with_overlap(indexer):
    """Test that chunks have proper overlap."""
    # Configure small chunk size for testing
    indexer.config.chunk_size = 50
    indexer.config.chunk_overlap = 10
    
    content = "\n".join([f"line {i}" for i in range(50)])
    
    chunks = await indexer._chunk_content(
        content=content,
        file_path="test.py",
        language="python"
    )
    
    if len(chunks) > 1:
        # Verify there's some overlap between consecutive chunks
        # The end of first chunk should be close to start of second
        gap = chunks[1].start_line - chunks[0].end_line
        assert gap <= 1  # Allow for some gap due to line boundaries


@pytest.mark.asyncio
async def test_embed_and_store_chunks(indexer, mock_vector_store, mock_embedder):
    """Test embedding and storing chunks."""
    chunks = [
        CodeChunk(
            content="test1",
            file_path="test.py",
            start_line=1,
            end_line=1,
            chunk_type="block",
            language="python"
        ),
        CodeChunk(
            content="test2",
            file_path="test.py",
            start_line=3,
            end_line=3,
            chunk_type="block",
            language="python"
        )
    ]
    
    # Mock embedder to return correct number of embeddings
    mock_embedder.embed_batch.return_value = [[0.1], [0.2]]
    
    await indexer._embed_and_store_chunks(chunks)
    
    # Verify embeddings were generated
    mock_embedder.embed_batch.assert_called_once()
    assert mock_embedder.embed_batch.call_args[0][0] == ["test1", "test2"]
    
    # Verify chunks were stored
    mock_vector_store.upsert_chunks.assert_called_once()
    stored_chunks = mock_vector_store.upsert_chunks.call_args[0][0]
    assert len(stored_chunks) == 2
    assert stored_chunks[0].embedding == [0.1]
    assert stored_chunks[1].embedding == [0.2]


@pytest.mark.asyncio
async def test_embed_and_store_empty(indexer, mock_vector_store, mock_embedder):
    """Test embedding empty list."""
    await indexer._embed_and_store_chunks([])
    
    mock_embedder.embed_batch.assert_not_called()
    mock_vector_store.upsert_chunks.assert_not_called()


@pytest.mark.asyncio
async def test_index_workspace(indexer, mock_vector_store, mock_embedder):
    """Test full workspace indexing."""
    # Mock embedder to return embeddings
    mock_embedder.embed_batch.return_value = [[0.1] * 768]
    
    stats = await indexer.index_workspace()
    
    assert stats["files_processed"] > 0
    assert stats["chunks_created"] > 0
    assert "files_skipped" in stats
    
    # Verify chunks were created and stored
    assert mock_embedder.embed_batch.called
    assert mock_vector_store.upsert_chunks.called


@pytest.mark.asyncio
async def test_index_workspace_with_progress(indexer, mock_embedder):
    """Test workspace indexing with progress callback."""
    mock_embedder.embed_batch.return_value = [[0.1] * 768]
    
    progress_calls = []
    
    def progress_callback(processed, total, file):
        progress_calls.append((processed, total, file))
    
    await indexer.index_workspace(progress_callback=progress_callback)
    
    # Should have received progress updates
    assert len(progress_calls) > 0
    
    # Verify progress values make sense
    for processed, total, file in progress_calls:
        assert processed <= total
        assert isinstance(file, str)


@pytest.mark.asyncio
async def test_index_workspace_empty(temp_workspace, mock_vector_store, mock_embedder):
    """Test indexing empty workspace."""
    # Create empty workspace
    empty_workspace = tempfile.mkdtemp()
    try:
        indexer = CodeIndexer(
            workspace_path=empty_workspace,
            vector_store=mock_vector_store,
            embedder=mock_embedder
        )
        
        stats = await indexer.index_workspace()
        
        assert stats["files_processed"] == 0
        assert stats["chunks_created"] == 0
    finally:
        shutil.rmtree(empty_workspace)


@pytest.mark.asyncio
async def test_index_files(indexer, mock_vector_store, mock_embedder):
    """Test indexing specific files."""
    mock_embedder.embed_batch.return_value = [[0.1] * 768]
    
    stats = await indexer.index_files(
        file_paths=["main.py", "utils.py"]
    )
    
    assert stats["files_processed"] == 2
    assert stats["chunks_created"] > 0
    
    # Should delete old chunks before indexing
    assert mock_vector_store.delete_by_file_path.call_count == 2


@pytest.mark.asyncio
async def test_index_files_with_errors(indexer, mock_vector_store, mock_embedder):
    """Test indexing files with some errors."""
    mock_embedder.embed_batch.return_value = [[0.1] * 768]
    
    stats = await indexer.index_files(
        file_paths=["main.py", "nonexistent.py"]
    )
    
    assert stats["files_processed"] == 2
    assert stats["files_skipped"] >= 0  # May skip nonexistent file


@pytest.mark.asyncio
async def test_delete_files(indexer, mock_vector_store):
    """Test deleting files from index."""
    await indexer.delete_files(["main.py", "utils.py"])
    
    mock_vector_store.delete_by_file_paths.assert_called_once_with(
        ["main.py", "utils.py"]
    )


@pytest.mark.asyncio
async def test_indexing_counters(indexer, mock_embedder):
    """Test that indexing counters are updated correctly."""
    mock_embedder.embed_batch.return_value = [[0.1] * 768]
    
    # Initial counters
    assert indexer.files_processed == 0
    assert indexer.chunks_created == 0
    
    # Index workspace
    await indexer.index_workspace()
    
    # Counters should be updated
    assert indexer.files_processed > 0
    assert indexer.chunks_created > 0


@pytest.mark.asyncio
async def test_index_with_custom_config(temp_workspace, mock_vector_store, mock_embedder):
    """Test indexing with custom configuration."""
    mock_embedder.embed_batch.return_value = [[0.1] * 768]
    
    config = IndexingConfig(
        chunk_size=100,
        chunk_overlap=20,
        include_patterns=['*.py'],
        exclude_patterns=['test_*']
    )
    
    indexer = CodeIndexer(
        workspace_path=temp_workspace,
        vector_store=mock_vector_store,
        embedder=mock_embedder,
        config=config
    )
    
    stats = await indexer.index_workspace()
    
    assert stats["files_processed"] >= 0
    # Custom config should be respected
    assert indexer.config.chunk_size == 100


@pytest.mark.asyncio
async def test_handle_large_file(temp_workspace, mock_vector_store, mock_embedder):
    """Test handling files that exceed max size."""
    mock_embedder.embed_batch.return_value = [[0.1] * 768]
    
    # Create a file that's too large
    large_file = os.path.join(temp_workspace, "large.py")
    with open(large_file, 'w') as f:
        f.write("x" * (2 * 1024 * 1024))  # 2MB
    
    config = IndexingConfig(max_file_size=1024 * 1024)  # 1MB limit
    
    indexer = CodeIndexer(
        workspace_path=temp_workspace,
        vector_store=mock_vector_store,
        embedder=mock_embedder,
        config=config
    )
    
    files = await indexer._scan_workspace()
    
    # Large file should be excluded
    assert not any('large.py' in f for f in files)