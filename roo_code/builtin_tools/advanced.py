"""Advanced tools for specialized operations."""

import os
from typing import Any, Dict, Optional
from ..tools import Tool, ToolInputSchema, ToolResult
from .ollama_embedder import OllamaEmbedder
from .vector_store import VectorStore, VectorStoreFactory
from .image_generator import ImageGenerator


class FetchInstructionsTool(Tool):
    """Tool for fetching mode-specific instructions."""
    
    def __init__(self):
        super().__init__(
            name="fetch_instructions",
            description="Request to fetch instructions to perform a task",
            input_schema=ToolInputSchema(
                type="object",
                properties={
                    "task": {
                        "type": "string",
                        "enum": ["create_mcp_server", "create_mode"],
                        "description": (
                            "The task to get instructions for:\n"
                            "- create_mcp_server: Instructions for creating an MCP server\n"
                            "- create_mode: Instructions for creating a custom mode"
                        )
                    }
                },
                required=["task"]
            )
        )
    
    async def execute(self, input_data: Dict[str, Any]) -> ToolResult:
        """Fetch instructions for a specific task."""
        try:
            task = input_data["task"]
            
            instructions = {
                "create_mcp_server": self._get_mcp_server_instructions(),
                "create_mode": self._get_mode_instructions()
            }
            
            content = instructions.get(task, f"No instructions available for task: {task}")
            
            return ToolResult(
                tool_use_id=self.current_use_id,
                content=content,
                is_error=False
            )
            
        except Exception as e:
            return ToolResult(
                tool_use_id=self.current_use_id,
                content=f"Error fetching instructions: {str(e)}",
                is_error=True
            )
    
    def _get_mcp_server_instructions(self) -> str:
        """Get instructions for creating an MCP server."""
        return """# Instructions for Creating an MCP Server

MCP (Model Context Protocol) servers provide additional capabilities to AI agents.

## Basic Structure

1. Create a new Python project with the following structure:
   ```
   my-mcp-server/
   ├── __init__.py
   ├── server.py
   └── requirements.txt
   ```

2. Implement your server in server.py:
   ```python
   from mcp import Server, Tool
   
   server = Server("my-server")
   
   @server.tool()
   async def my_tool(param: str) -> str:
       # Your tool logic here
       return f"Result: {param}"
   
   if __name__ == "__main__":
       server.run()
   ```

3. Add dependencies to requirements.txt:
   ```
   mcp>=1.0.0
   ```

4. Install and test:
   ```bash
   pip install -e .
   python server.py
   ```

For more details, refer to the MCP documentation.
"""
    
    def _get_mode_instructions(self) -> str:
        """Get instructions for creating a custom mode."""
        return """# Instructions for Creating a Custom Mode

Modes define the behavior and capabilities of the AI agent.

## Mode Configuration Structure

Create a YAML file (e.g., `custom_mode.yaml`):

```yaml
slug: my-custom-mode
name: 🎯 My Custom Mode
roleDefinition: |
  You are a specialized assistant focused on [specific task].
  Your goal is to [describe the mode's purpose].

groups:
  - read      # Read operations
  - edit      # Write operations
  - command   # Command execution
  - browser   # Browser automation

# Optional: File restrictions for edit group
editFilePattern: "\\.md$"  # Only allow editing markdown files
editFilePatternDescription: "Markdown files only"

# Optional: Custom instructions
customInstructions: |
  Additional guidelines for this mode...
```

## Available Tool Groups

- `read`: read_file, search_files, list_files, list_code_definition_names
- `edit`: write_to_file, apply_diff, insert_content
- `command`: execute_command
- `browser`: browser_action
- `mcp`: use_mcp_tool, access_mcp_resource
- `modes`: ask_followup_question, attempt_completion, update_todo_list

## Testing Your Mode

1. Save the YAML configuration file
2. Load it in your agent configuration
3. Test the mode with various tasks
4. Iterate based on results
"""


class CodebaseSearchTool(Tool):
    """Tool for semantic code search using embeddings."""
    
    def __init__(self, workspace_path: Optional[str] = None):
        super().__init__(
            name="codebase_search",
            description=(
                "Perform semantic search across the codebase using embeddings. This finds "
                "code that is conceptually similar to your query, even if it doesn't contain "
                "exact keyword matches. Requires Ollama to be running with an embedding model."
            ),
            input_schema=ToolInputSchema(
                type="object",
                properties={
                    "query": {
                        "type": "string",
                        "description": "The search query describing what you're looking for"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return. Optional, defaults to 5."
                    },
                    "min_score": {
                        "type": "number",
                        "description": "Minimum similarity score (0-1). Optional, defaults to 0.3."
                    },
                    "file_pattern": {
                        "type": "string",
                        "description": "Optional file path pattern to filter results (e.g., 'src/components')"
                    }
                },
                required=["query"]
            )
        )
        self.workspace_path = workspace_path or os.getcwd()
        self._vector_store: Optional[VectorStore] = None
        self._embedder: Optional[OllamaEmbedder] = None
    
    async def _ensure_initialized(self) -> tuple[VectorStore, OllamaEmbedder]:
        """Ensure vector store and embedder are initialized."""
        if self._vector_store is None or self._embedder is None:
            # Initialize embedder
            self._embedder = OllamaEmbedder()
            
            # Validate Ollama is available
            is_valid, error = await self._embedder.validate_configuration()
            if not is_valid:
                raise RuntimeError(f"Ollama validation failed: {error}")
            
            # Initialize vector store
            self._vector_store = VectorStoreFactory.create_vector_store(
                workspace_path=self.workspace_path
            )
            await self._vector_store.initialize()
        
        return self._vector_store, self._embedder
    
    async def execute(self, input_data: Dict[str, Any]) -> ToolResult:
        """Perform semantic codebase search."""
        try:
            query = input_data["query"]
            max_results = input_data.get("max_results", 5)
            min_score = input_data.get("min_score", 0.3)
            file_pattern = input_data.get("file_pattern")
            
            try:
                # Ensure components are initialized
                vector_store, embedder = await self._ensure_initialized()
                
                # Check if index exists
                stats = await vector_store.get_stats()
                if stats["total_chunks"] == 0:
                    return ToolResult(
                        tool_use_id=self.current_use_id,
                        content=(
                            "The codebase index is empty. Please index your workspace first using:\n"
                            "1. Ensure Ollama is running: `ollama serve`\n"
                            "2. Pull an embedding model: `ollama pull nomic-embed-text`\n"
                            "3. Index your codebase (this will be automatic in future versions)\n\n"
                            "Use search_files tool for regex-based search as an alternative."
                        ),
                        is_error=True
                    )
                
                # Generate query embedding
                query_embedding = await embedder.embed_text(query)
                
                # Search vector store
                results = await vector_store.search(
                    query_embedding=query_embedding,
                    max_results=max_results,
                    min_score=min_score,
                    file_pattern=file_pattern
                )
                
                if not results:
                    return ToolResult(
                        tool_use_id=self.current_use_id,
                        content=(
                            f"No results found for query: '{query}'\n"
                            f"(min_score: {min_score}, max_results: {max_results})\n\n"
                            "Try:\n"
                            "- Lowering min_score\n"
                            "- Using different keywords\n"
                            "- Using search_files for regex-based search"
                        ),
                        is_error=False
                    )
                
                # Format results
                output_lines = [
                    f"Found {len(results)} result(s) for query: '{query}'\n",
                    "=" * 80,
                    ""
                ]
                
                for i, result in enumerate(results, 1):
                    chunk = result.chunk
                    score_pct = int(result.score * 100)
                    
                    output_lines.extend([
                        f"Result {i} - Score: {score_pct}%",
                        f"File: {chunk.file_path}",
                        f"Lines: {chunk.start_line}-{chunk.end_line}",
                        f"Language: {chunk.language}",
                        f"Type: {chunk.chunk_type}",
                        "",
                        "```" + chunk.language,
                        chunk.content.strip(),
                        "```",
                        "",
                        "-" * 80,
                        ""
                    ])
                
                output_lines.extend([
                    "",
                    f"Search Stats:",
                    f"- Total chunks in index: {stats['total_chunks']}",
                    f"- Results returned: {len(results)}/{max_results}",
                    f"- Minimum score threshold: {min_score}"
                ])
                
                return ToolResult(
                    tool_use_id=self.current_use_id,
                    content="\n".join(output_lines),
                    is_error=False
                )
                
            except RuntimeError as e:
                # Ollama not available
                return ToolResult(
                    tool_use_id=self.current_use_id,
                    content=(
                        f"Semantic search is not available: {str(e)}\n\n"
                        f"To use semantic search:\n"
                        f"1. Install Ollama: https://ollama.ai/\n"
                        f"2. Start Ollama: `ollama serve`\n"
                        f"3. Pull embedding model: `ollama pull nomic-embed-text`\n\n"
                        f"Use search_files tool for regex-based search as an alternative."
                    ),
                    is_error=True
                )
            
        except Exception as e:
            return ToolResult(
                tool_use_id=self.current_use_id,
                content=f"Error performing codebase search: {str(e)}",
                is_error=True
            )
    
    async def cleanup(self):
        """Clean up resources."""
        if self._embedder:
            await self._embedder.close()
        if self._vector_store:
            self._vector_store.close()


class RunSlashCommandTool(Tool):
    """Tool for executing custom slash commands."""
    
    def __init__(self):
        super().__init__(
            name="run_slash_command",
            description=(
                "Execute a custom slash command. Slash commands are user-defined shortcuts "
                "for common operations."
            ),
            input_schema=ToolInputSchema(
                type="object",
                properties={
                    "command": {
                        "type": "string",
                        "description": "The slash command to execute (e.g., '/test', '/deploy')"
                    },
                    "args": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Arguments to pass to the command. Optional."
                    }
                },
                required=["command"]
            )
        )
    
    async def execute(self, input_data: Dict[str, Any]) -> ToolResult:
        """Execute a slash command."""
        try:
            command = input_data["command"]
            args = input_data.get("args", [])
            
            # TODO: Implement custom slash command registry and execution
            # This would integrate with user-defined command configurations
            
            return ToolResult(
                tool_use_id=self.current_use_id,
                content=(
                    f"Slash command execution is not yet fully implemented.\n"
                    f"Command: {command}\n"
                    f"Arguments: {args}"
                ),
                is_error=True
            )
            
        except Exception as e:
            return ToolResult(
                tool_use_id=self.current_use_id,
                content=f"Error executing slash command: {str(e)}",
                is_error=True
            )


class GenerateImageTool(Tool):
    """Tool for AI image generation with multi-provider support."""
    
    def __init__(self, cwd: Optional[str] = None, config: Optional[Dict[str, Any]] = None):
        """Initialize image generation tool.
        
        Args:
            cwd: Current working directory (workspace path)
            config: Optional configuration for image generation
        """
        super().__init__(
            name="generate_image",
            description=(
                "Generate an image using AI based on a text prompt. Supports multiple "
                "providers including OpenAI DALL-E, Stability AI, and Ollama-assisted "
                "generation (uses Ollama to enhance prompts, then generates with other providers). "
                "Images are automatically saved with metadata."
            ),
            input_schema=ToolInputSchema(
                type="object",
                properties={
                    "prompt": {
                        "type": "string",
                        "description": "Text description of the image to generate"
                    },
                    "size": {
                        "type": "string",
                        "enum": ["256x256", "512x512", "1024x1024", "1024x1792", "1792x1024"],
                        "description": "Image size. Optional, defaults to 1024x1024."
                    },
                    "quality": {
                        "type": "string",
                        "enum": ["standard", "hd"],
                        "description": "Image quality. Optional, defaults to standard."
                    },
                    "provider": {
                        "type": "string",
                        "enum": ["openai", "stability_ai", "ollama_assisted_openai", "ollama_assisted_stability"],
                        "description": (
                            "Image generation provider to use. Optional, uses configured primary provider. "
                            "ollama_assisted providers use Ollama to enhance prompts first."
                        )
                    },
                    "output_path": {
                        "type": "string",
                        "description": "Custom output path relative to workspace. Optional, uses default storage."
                    }
                },
                required=["prompt"]
            )
        )
        self.cwd = cwd or os.getcwd()
        self._generator: Optional[ImageGenerator] = None
        self._custom_config = config
    
    def _ensure_generator(self) -> ImageGenerator:
        """Ensure generator is initialized."""
        if self._generator is None:
            self._generator = ImageGenerator(
                config=self._custom_config,
                workspace_path=self.cwd
            )
        return self._generator
    
    async def execute(self, input_data: Dict[str, Any]) -> ToolResult:
        """Generate an image using configured providers."""
        try:
            prompt = input_data["prompt"]
            size = input_data.get("size", "1024x1024")
            quality = input_data.get("quality", "standard")
            provider = input_data.get("provider")
            output_path = input_data.get("output_path")
            
            generator = self._ensure_generator()
            
            # First, validate providers
            validation_results = await generator.validate_providers()
            available_providers = [
                name for name, (is_valid, _) in validation_results.items() if is_valid
            ]
            
            if not available_providers:
                error_details = "\n".join([
                    f"- {name}: {error}"
                    for name, (is_valid, error) in validation_results.items()
                    if not is_valid
                ])
                return ToolResult(
                    tool_use_id=self.current_use_id,
                    content=(
                        f"No image generation providers are available.\n\n"
                        f"Configuration issues:\n{error_details}\n\n"
                        f"To use image generation:\n"
                        f"1. For OpenAI: Set OPENAI_API_KEY environment variable\n"
                        f"2. For Stability AI: Set STABILITY_AI_KEY environment variable\n"
                        f"3. For Ollama-assisted: Install Ollama (https://ollama.ai/) and run:\n"
                        f"   ollama pull llama3.2-vision\n"
                        f"   Then configure one of the above providers for actual generation."
                    ),
                    is_error=True
                )
            
            # Generate image
            try:
                image_path, metadata = await generator.generate(
                    prompt=prompt,
                    size=size,
                    quality=quality,
                    provider=provider,
                    output_path=output_path
                )
                
                # Format success response
                output_lines = [
                    "✅ Image generated successfully!",
                    "",
                    f"📁 Image saved to: {image_path}",
                    f"🎨 Provider: {metadata.provider}",
                    f"🤖 Model: {metadata.model}",
                    f"📐 Size: {metadata.size}",
                    f"⭐ Quality: {quality}",
                    "",
                    f"💭 Original prompt: {metadata.prompt}"
                ]
                
                if metadata.enhanced_prompt and metadata.enhanced_prompt != metadata.prompt:
                    output_lines.extend([
                        "",
                        f"✨ Enhanced prompt: {metadata.enhanced_prompt}"
                    ])
                
                # Add storage stats
                stats = generator.get_storage_stats()
                output_lines.extend([
                    "",
                    "📊 Storage stats:",
                    f"   Total images: {stats['total_images']}",
                    f"   Total size: {stats['total_size_mb']} MB"
                ])
                
                return ToolResult(
                    tool_use_id=self.current_use_id,
                    content="\n".join(output_lines),
                    is_error=False
                )
                
            except RuntimeError as e:
                # Generation failed with all providers
                error_msg = str(e)
                
                # Provide helpful guidance
                help_text = "\n\nTroubleshooting:\n"
                if "API key" in error_msg.lower() or "auth" in error_msg.lower():
                    help_text += (
                        "- Check that API keys are correctly configured\n"
                        "- For OpenAI: export OPENAI_API_KEY='sk-...'\n"
                        "- For Stability AI: export STABILITY_AI_KEY='sk-...'\n"
                    )
                elif "ollama" in error_msg.lower():
                    help_text += (
                        "- Ensure Ollama is running: ollama serve\n"
                        "- Pull required model: ollama pull llama3.2-vision\n"
                    )
                elif "timeout" in error_msg.lower():
                    help_text += "- The request timed out. Try again or check network connection.\n"
                
                return ToolResult(
                    tool_use_id=self.current_use_id,
                    content=f"Failed to generate image: {error_msg}{help_text}",
                    is_error=True
                )
            
        except Exception as e:
            return ToolResult(
                tool_use_id=self.current_use_id,
                content=f"Error generating image: {str(e)}",
                is_error=True
            )
    
    async def cleanup(self):
        """Clean up resources."""
        # ImageGenerator doesn't require explicit cleanup currently
        pass