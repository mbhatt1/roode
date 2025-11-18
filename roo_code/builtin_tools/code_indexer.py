"""Code indexing pipeline for semantic search."""

import os
import asyncio
from typing import List, Optional, Dict, Set, Callable
from pathlib import Path
from dataclasses import dataclass

from .vector_store import VectorStore, CodeChunk
from .ollama_embedder import OllamaEmbedder


@dataclass
class IndexingConfig:
    """Configuration for code indexing."""
    
    chunk_size: int = 500  # Maximum tokens per chunk
    chunk_overlap: int = 50  # Overlap between chunks in tokens
    include_patterns: List[str] = None  # File patterns to include (e.g., ['*.py', '*.js'])
    exclude_patterns: List[str] = None  # File patterns to exclude (e.g., ['node_modules/**'])
    max_file_size: int = 1_000_000  # Maximum file size in bytes (1MB)
    batch_size: int = 32  # Batch size for embedding generation
    
    def __post_init__(self):
        if self.include_patterns is None:
            self.include_patterns = [
                '*.py', '*.js', '*.ts', '*.jsx', '*.tsx',
                '*.java', '*.c', '*.cpp', '*.h', '*.hpp',
                '*.go', '*.rs', '*.rb', '*.php', '*.cs',
                '*.swift', '*.kt', '*.scala', '*.sh'
            ]
        if self.exclude_patterns is None:
            self.exclude_patterns = [
                'node_modules/**',
                '.git/**',
                '__pycache__/**',
                '*.pyc',
                'dist/**',
                'build/**',
                '.venv/**',
                'venv/**',
                '.roo/**'
            ]


class CodeIndexer:
    """Indexes code files for semantic search."""
    
    def __init__(
        self,
        workspace_path: str,
        vector_store: VectorStore,
        embedder: OllamaEmbedder,
        config: Optional[IndexingConfig] = None
    ):
        """
        Initialize code indexer.
        
        Args:
            workspace_path: Path to the workspace
            vector_store: Vector store for embeddings
            embedder: Ollama embedder for generating embeddings
            config: Indexing configuration
        """
        self.workspace_path = workspace_path
        self.vector_store = vector_store
        self.embedder = embedder
        self.config = config or IndexingConfig()
        
        # Track indexing progress
        self.files_processed = 0
        self.files_total = 0
        self.chunks_created = 0
    
    async def index_workspace(
        self,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> Dict[str, int]:
        """
        Index all files in the workspace.
        
        Args:
            progress_callback: Optional callback for progress updates (processed, total, current_file)
            
        Returns:
            Dictionary with indexing statistics
        """
        # Reset counters
        self.files_processed = 0
        self.files_total = 0
        self.chunks_created = 0
        
        # Scan workspace for files
        files_to_index = await self._scan_workspace()
        self.files_total = len(files_to_index)
        
        if self.files_total == 0:
            return {
                "files_processed": 0,
                "chunks_created": 0,
                "files_skipped": 0
            }
        
        # Process files in batches
        all_chunks = []
        files_skipped = 0
        
        for file_path in files_to_index:
            try:
                # Report progress
                if progress_callback:
                    progress_callback(self.files_processed, self.files_total, file_path)
                
                # Read and chunk file
                chunks = await self._process_file(file_path)
                
                if chunks:
                    all_chunks.extend(chunks)
                    
                    # Process in batches to avoid memory issues
                    if len(all_chunks) >= self.config.batch_size:
                        await self._embed_and_store_chunks(all_chunks)
                        all_chunks = []
                
                self.files_processed += 1
                
            except Exception as e:
                print(f"[CodeIndexer] Error processing {file_path}: {e}")
                files_skipped += 1
        
        # Process remaining chunks
        if all_chunks:
            await self._embed_and_store_chunks(all_chunks)
        
        return {
            "files_processed": self.files_processed,
            "chunks_created": self.chunks_created,
            "files_skipped": files_skipped
        }
    
    async def index_files(
        self,
        file_paths: List[str],
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> Dict[str, int]:
        """
        Index specific files (for incremental updates).
        
        Args:
            file_paths: List of file paths to index
            progress_callback: Optional callback for progress updates
            
        Returns:
            Dictionary with indexing statistics
        """
        self.files_processed = 0
        self.files_total = len(file_paths)
        self.chunks_created = 0
        
        all_chunks = []
        files_skipped = 0
        
        for file_path in file_paths:
            try:
                # Delete existing chunks for this file
                await self.vector_store.delete_by_file_path(file_path)
                
                if progress_callback:
                    progress_callback(self.files_processed, self.files_total, file_path)
                
                # Process file
                chunks = await self._process_file(file_path)
                
                if chunks:
                    all_chunks.extend(chunks)
                    
                    if len(all_chunks) >= self.config.batch_size:
                        await self._embed_and_store_chunks(all_chunks)
                        all_chunks = []
                
                self.files_processed += 1
                
            except Exception as e:
                print(f"[CodeIndexer] Error processing {file_path}: {e}")
                files_skipped += 1
        
        # Process remaining chunks
        if all_chunks:
            await self._embed_and_store_chunks(all_chunks)
        
        return {
            "files_processed": self.files_processed,
            "chunks_created": self.chunks_created,
            "files_skipped": files_skipped
        }
    
    async def delete_files(self, file_paths: List[str]) -> None:
        """
        Delete chunks for specific files.
        
        Args:
            file_paths: List of file paths to delete
        """
        await self.vector_store.delete_by_file_paths(file_paths)
    
    async def _scan_workspace(self) -> List[str]:
        """
        Scan workspace for code files.
        
        Returns:
            List of file paths to index
        """
        files_to_index = []
        
        for root, dirs, files in os.walk(self.workspace_path):
            # Filter out excluded directories
            dirs[:] = [d for d in dirs if not self._is_excluded(os.path.join(root, d))]
            
            for file in files:
                file_path = os.path.join(root, file)
                
                # Check if file should be included
                if self._should_include_file(file_path):
                    # Make path relative to workspace
                    rel_path = os.path.relpath(file_path, self.workspace_path)
                    files_to_index.append(rel_path)
        
        return files_to_index
    
    def _should_include_file(self, file_path: str) -> bool:
        """Check if file should be included in indexing."""
        # Check exclusion patterns
        if self._is_excluded(file_path):
            return False
        
        # Check file size
        try:
            if os.path.getsize(file_path) > self.config.max_file_size:
                return False
        except OSError:
            return False
        
        # Check inclusion patterns
        file_name = os.path.basename(file_path)
        
        for pattern in self.config.include_patterns:
            if self._matches_pattern(file_name, pattern):
                return True
        
        return False
    
    def _is_excluded(self, path: str) -> bool:
        """Check if path matches any exclusion pattern."""
        rel_path = os.path.relpath(path, self.workspace_path)
        
        for pattern in self.config.exclude_patterns:
            if self._matches_pattern(rel_path, pattern):
                return True
        
        return False
    
    def _matches_pattern(self, path: str, pattern: str) -> bool:
        """Simple pattern matching (supports * and **)."""
        import fnmatch
        
        # Handle ** for recursive matching
        if '**' in pattern:
            parts = pattern.split('**')
            # Simple check: if any part matches
            for part in parts:
                if part and fnmatch.fnmatch(path, f"*{part}*"):
                    return True
            return False
        
        return fnmatch.fnmatch(path, pattern)
    
    async def _process_file(self, rel_file_path: str) -> List[CodeChunk]:
        """
        Process a single file and create chunks.
        
        Args:
            rel_file_path: Relative file path from workspace
            
        Returns:
            List of code chunks
        """
        abs_path = os.path.join(self.workspace_path, rel_file_path)
        
        try:
            with open(abs_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except Exception as e:
            print(f"[CodeIndexer] Failed to read {rel_file_path}: {e}")
            return []
        
        if not content.strip():
            return []
        
        # Determine language from extension
        language = self._detect_language(rel_file_path)
        
        # Create chunks using simple strategy
        chunks = await self._chunk_content(
            content=content,
            file_path=rel_file_path,
            language=language
        )
        
        return chunks
    
    def _detect_language(self, file_path: str) -> str:
        """Detect programming language from file extension."""
        ext_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.jsx': 'javascript',
            '.tsx': 'typescript',
            '.java': 'java',
            '.c': 'c',
            '.cpp': 'cpp',
            '.h': 'c',
            '.hpp': 'cpp',
            '.go': 'go',
            '.rs': 'rust',
            '.rb': 'ruby',
            '.php': 'php',
            '.cs': 'csharp',
            '.swift': 'swift',
            '.kt': 'kotlin',
            '.scala': 'scala',
            '.sh': 'bash'
        }
        
        ext = os.path.splitext(file_path)[1].lower()
        return ext_map.get(ext, 'unknown')
    
    async def _chunk_content(
        self,
        content: str,
        file_path: str,
        language: str
    ) -> List[CodeChunk]:
        """
        Chunk file content into manageable pieces.
        
        This is a simple line-based chunking strategy.
        For production, consider using tree-sitter for semantic chunking.
        
        Args:
            content: File content
            file_path: Relative file path
            language: Programming language
            
        Returns:
            List of code chunks
        """
        lines = content.split('\n')
        chunks = []
        
        # Estimate tokens (rough approximation: 1 token ≈ 4 characters)
        char_per_token = 4
        max_chars = self.config.chunk_size * char_per_token
        overlap_chars = self.config.chunk_overlap * char_per_token
        
        current_chunk_lines = []
        current_chunk_chars = 0
        start_line = 1
        
        for i, line in enumerate(lines, start=1):
            line_chars = len(line)
            
            # If adding this line would exceed max, create a chunk
            if current_chunk_chars + line_chars > max_chars and current_chunk_lines:
                chunk_content = '\n'.join(current_chunk_lines)
                
                chunks.append(CodeChunk(
                    content=chunk_content,
                    file_path=file_path,
                    start_line=start_line,
                    end_line=i - 1,
                    chunk_type='block',
                    language=language
                ))
                
                # Calculate overlap
                overlap_line_count = 0
                overlap_chars_count = 0
                
                for line_idx in range(len(current_chunk_lines) - 1, -1, -1):
                    line_len = len(current_chunk_lines[line_idx])
                    if overlap_chars_count + line_len <= overlap_chars:
                        overlap_line_count += 1
                        overlap_chars_count += line_len
                    else:
                        break
                
                # Start new chunk with overlap
                if overlap_line_count > 0:
                    current_chunk_lines = current_chunk_lines[-overlap_line_count:]
                    current_chunk_chars = overlap_chars_count
                    start_line = i - overlap_line_count
                else:
                    current_chunk_lines = []
                    current_chunk_chars = 0
                    start_line = i
            
            current_chunk_lines.append(line)
            current_chunk_chars += line_chars
        
        # Add final chunk
        if current_chunk_lines:
            chunk_content = '\n'.join(current_chunk_lines)
            chunks.append(CodeChunk(
                content=chunk_content,
                file_path=file_path,
                start_line=start_line,
                end_line=len(lines),
                chunk_type='block',
                language=language
            ))
        
        return chunks
    
    async def _embed_and_store_chunks(self, chunks: List[CodeChunk]) -> None:
        """
        Generate embeddings for chunks and store them.
        
        Args:
            chunks: List of code chunks to embed and store
        """
        if not chunks:
            return
        
        # Extract text content for embedding
        texts = [chunk.content for chunk in chunks]
        
        try:
            # Generate embeddings in batch
            embeddings = await self.embedder.embed_batch(texts)
            
            # Attach embeddings to chunks
            for chunk, embedding in zip(chunks, embeddings):
                chunk.embedding = embedding
            
            # Store in vector database
            await self.vector_store.upsert_chunks(chunks)
            
            self.chunks_created += len(chunks)
            
        except Exception as e:
            print(f"[CodeIndexer] Failed to embed and store chunks: {e}")
            raise