"""Vector database wrapper for code embeddings storage and retrieval."""

import os
import hashlib
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from pathlib import Path

try:
    import chromadb
    from chromadb.config import Settings
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False


@dataclass
class CodeChunk:
    """Represents a chunk of code with metadata."""
    
    content: str
    file_path: str
    start_line: int
    end_line: int
    chunk_type: str  # 'function', 'class', 'method', 'block'
    language: str
    embedding: Optional[List[float]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "content": self.content,
            "file_path": self.file_path,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "chunk_type": self.chunk_type,
            "language": self.language
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any], embedding: Optional[List[float]] = None) -> "CodeChunk":
        """Create from dictionary."""
        return cls(
            content=data["content"],
            file_path=data["file_path"],
            start_line=data["start_line"],
            end_line=data["end_line"],
            chunk_type=data["chunk_type"],
            language=data["language"],
            embedding=embedding
        )


@dataclass
class SearchResult:
    """Represents a search result with context."""
    
    chunk: CodeChunk
    score: float
    context_before: str = ""
    context_after: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "chunk": self.chunk.to_dict(),
            "score": self.score,
            "context_before": self.context_before,
            "context_after": self.context_after
        }


class VectorStore:
    """Vector database wrapper for semantic code search."""
    
    DEFAULT_SEARCH_MIN_SCORE = 0.3
    DEFAULT_MAX_SEARCH_RESULTS = 10
    
    def __init__(
        self,
        workspace_path: str,
        persist_directory: Optional[str] = None,
        vector_size: int = 768
    ):
        """
        Initialize vector store.
        
        Args:
            workspace_path: Path to the workspace
            persist_directory: Directory to persist the database
            vector_size: Dimension of embedding vectors (default: 768 for nomic-embed-text)
        """
        if not CHROMADB_AVAILABLE:
            raise ImportError(
                "ChromaDB is not installed. Install with: pip install chromadb>=0.4.0"
            )
        
        self.workspace_path = workspace_path
        self.vector_size = vector_size
        
        # Generate collection name from workspace path
        workspace_hash = hashlib.sha256(workspace_path.encode()).hexdigest()
        self.collection_name = f"ws-{workspace_hash[:16]}"
        
        # Set up persist directory
        if persist_directory is None:
            persist_directory = os.path.join(workspace_path, ".roo", "vector_store")
        
        self.persist_directory = persist_directory
        os.makedirs(persist_directory, exist_ok=True)
        
        # Initialize ChromaDB client with persistence
        self.client = chromadb.PersistentClient(
            path=persist_directory,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        
        # Get or create collection
        self.collection = None
    
    async def initialize(self) -> bool:
        """
        Initialize the vector store.
        
        Returns:
            True if a new collection was created, False if existing was used
        """
        try:
            # Try to get existing collection
            self.collection = self.client.get_collection(
                name=self.collection_name
            )
            
            # Verify metadata is compatible
            metadata = self.collection.metadata or {}
            existing_vector_size = metadata.get("vector_size")
            
            if existing_vector_size and existing_vector_size != self.vector_size:
                # Vector size mismatch - need to recreate
                print(
                    f"[VectorStore] Vector size mismatch: existing={existing_vector_size}, "
                    f"required={self.vector_size}. Recreating collection."
                )
                self.client.delete_collection(name=self.collection_name)
                self.collection = self._create_collection()
                return True
            
            return False
            
        except Exception:
            # Collection doesn't exist, create it
            self.collection = self._create_collection()
            return True
    
    def _create_collection(self):
        """Create a new collection."""
        return self.client.create_collection(
            name=self.collection_name,
            metadata={
                "vector_size": self.vector_size,
                "workspace_path": self.workspace_path
            },
            embedding_function=None  # We'll provide embeddings manually
        )
    
    async def upsert_chunks(self, chunks: List[CodeChunk]) -> None:
        """
        Upsert code chunks into the vector store.
        
        Args:
            chunks: List of code chunks with embeddings
        """
        if not chunks:
            return
        
        if not self.collection:
            await self.initialize()
        
        # Prepare data for ChromaDB
        ids = []
        embeddings = []
        documents = []
        metadatas = []
        
        for chunk in chunks:
            if chunk.embedding is None:
                raise ValueError(f"Chunk at {chunk.file_path}:{chunk.start_line} has no embedding")
            
            # Generate unique ID from file path and line numbers
            chunk_id = self._generate_chunk_id(chunk.file_path, chunk.start_line, chunk.end_line)
            
            ids.append(chunk_id)
            embeddings.append(chunk.embedding)
            documents.append(chunk.content)
            metadatas.append({
                "file_path": chunk.file_path,
                "start_line": chunk.start_line,
                "end_line": chunk.end_line,
                "chunk_type": chunk.chunk_type,
                "language": chunk.language
            })
        
        # Upsert to ChromaDB
        self.collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas
        )
    
    def _generate_chunk_id(self, file_path: str, start_line: int, end_line: int) -> str:
        """Generate a unique ID for a code chunk."""
        # Use file path and line numbers to create a unique, deterministic ID
        id_str = f"{file_path}:{start_line}:{end_line}"
        return hashlib.sha256(id_str.encode()).hexdigest()
    
    async def search(
        self,
        query_embedding: List[float],
        max_results: int = 10,
        min_score: float = 0.3,
        file_pattern: Optional[str] = None
    ) -> List[SearchResult]:
        """
        Search for similar code chunks.
        
        Args:
            query_embedding: Query embedding vector
            max_results: Maximum number of results to return
            min_score: Minimum similarity score (0-1)
            file_pattern: Optional file path pattern to filter results
            
        Returns:
            List of search results sorted by relevance
        """
        if not self.collection:
            await self.initialize()
        
        # Build where filter if file pattern specified
        where = None
        if file_pattern:
            # Simple prefix matching for file paths
            where = {"file_path": {"$contains": file_pattern}}
        
        # Query ChromaDB
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=max_results,
            where=where,
            include=["documents", "metadatas", "distances"]
        )
        
        # Convert to SearchResult objects
        search_results = []
        
        if results["ids"] and len(results["ids"]) > 0:
            for i in range(len(results["ids"][0])):
                # ChromaDB returns distances (lower is better)
                # Convert to similarity score (higher is better)
                distance = results["distances"][0][i]
                score = 1 - distance  # For cosine distance
                
                # Filter by minimum score
                if score < min_score:
                    continue
                
                metadata = results["metadatas"][0][i]
                document = results["documents"][0][i]
                
                chunk = CodeChunk(
                    content=document,
                    file_path=metadata["file_path"],
                    start_line=metadata["start_line"],
                    end_line=metadata["end_line"],
                    chunk_type=metadata["chunk_type"],
                    language=metadata["language"]
                )
                
                search_results.append(SearchResult(
                    chunk=chunk,
                    score=score
                ))
        
        return search_results
    
    async def delete_by_file_path(self, file_path: str) -> None:
        """
        Delete all chunks for a specific file.
        
        Args:
            file_path: Path to the file
        """
        if not self.collection:
            await self.initialize()
        
        # Query to get all chunks for this file
        results = self.collection.get(
            where={"file_path": file_path},
            include=[]
        )
        
        if results["ids"]:
            self.collection.delete(ids=results["ids"])
    
    async def delete_by_file_paths(self, file_paths: List[str]) -> None:
        """
        Delete all chunks for multiple files.
        
        Args:
            file_paths: List of file paths
        """
        for file_path in file_paths:
            await self.delete_by_file_path(file_path)
    
    async def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the vector store.
        
        Returns:
            Dictionary with stats
        """
        if not self.collection:
            await self.initialize()
        
        count = self.collection.count()
        
        return {
            "total_chunks": count,
            "collection_name": self.collection_name,
            "workspace_path": self.workspace_path,
            "vector_size": self.vector_size
        }
    
    async def clear(self) -> None:
        """Clear all data from the vector store."""
        if self.collection:
            self.client.delete_collection(name=self.collection_name)
            self.collection = self._create_collection()
    
    def close(self) -> None:
        """Close the vector store and clean up resources."""
        # ChromaDB PersistentClient doesn't need explicit closing
        pass


class VectorStoreFactory:
    """Factory for creating vector store instances."""
    
    @staticmethod
    def create_vector_store(
        workspace_path: str,
        provider: str = "chromadb",
        persist_directory: Optional[str] = None,
        vector_size: int = 768
    ) -> VectorStore:
        """
        Create a vector store instance.
        
        Args:
            workspace_path: Path to the workspace
            provider: Vector store provider (currently only 'chromadb' supported)
            persist_directory: Directory to persist the database
            vector_size: Dimension of embedding vectors
            
        Returns:
            VectorStore instance
            
        Raises:
            ValueError: If provider is not supported
        """
        if provider.lower() == "chromadb":
            return VectorStore(
                workspace_path=workspace_path,
                persist_directory=persist_directory,
                vector_size=vector_size
            )
        else:
            raise ValueError(f"Unsupported vector store provider: {provider}")