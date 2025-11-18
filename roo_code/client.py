"""Main client for Roo Code SDK"""

from typing import Any, Dict, List, Optional
from anthropic.types import ContentBlock
import logging

from .types import (
    ProviderSettings,
    ModelInfo,
    MessageParam,
    ApiHandlerCreateMessageMetadata,
    ApiProvider,
)
from .stream import ApiStream
from .providers import (
    AnthropicProvider,
    OpenAIProvider,
    GeminiProvider,
    OpenRouterProvider,
    GroqProvider,
    MistralProvider,
    DeepSeekProvider,
    OllamaProvider,
    BaseProvider,
)


class RooClient:
    """
    Main client for interacting with Roo Code AI models

    Example:
        ```python
        from roo_code import RooClient, ProviderSettings

        client = RooClient(
            provider_settings=ProviderSettings(
                api_provider="anthropic",
                api_key="your-api-key",
                api_model_id="claude-sonnet-4-5"
            )
        )

        response = await client.create_message(
            system_prompt="You are a helpful assistant.",
            messages=[{"role": "user", "content": "Hello!"}]
        )

        async for chunk in response.stream():
            print(chunk)
        ```
    """

    def __init__(
        self,
        provider_settings: ProviderSettings,
        base_url: Optional[str] = None,
        timeout: float = 60.0,
    ):
        """
        Initialize Roo Code client

        Args:
            provider_settings: Configuration for the AI provider
            base_url: Optional custom base URL for API requests
            timeout: Request timeout in seconds (default: 60.0)

        Raises:
            ValueError: If provider is not supported or configuration is invalid
        """
        self.provider_settings = provider_settings
        self.timeout = timeout

        # Override base URL if provided
        if base_url:
            self.provider_settings.api_base_url = base_url

        # Initialize the appropriate provider
        self._provider = self._build_provider(provider_settings)

    def _build_provider(self, settings: ProviderSettings) -> BaseProvider:
        """
        Build the appropriate provider based on settings

        Args:
            settings: Provider configuration

        Returns:
            BaseProvider: Initialized provider

        Raises:
            ValueError: If provider is not supported
        """
        provider_map = {
            ApiProvider.ANTHROPIC: AnthropicProvider,
            ApiProvider.CLAUDE_CODE: AnthropicProvider,
            ApiProvider.OPENAI: OpenAIProvider,
            ApiProvider.OPENAI_NATIVE: OpenAIProvider,
            ApiProvider.GEMINI: GeminiProvider,
            ApiProvider.OPENROUTER: OpenRouterProvider,
            ApiProvider.GROQ: GroqProvider,
            ApiProvider.MISTRAL: MistralProvider,
            ApiProvider.DEEPSEEK: DeepSeekProvider,
            ApiProvider.OLLAMA: OllamaProvider,
            ApiProvider.LMSTUDIO: OpenAIProvider,  # LM Studio is OpenAI-compatible
            ApiProvider.DEEPINFRA: OpenAIProvider,  # DeepInfra is OpenAI-compatible
            ApiProvider.XAI: OpenAIProvider,  # xAI is OpenAI-compatible
        }

        provider_class = provider_map.get(settings.api_provider)

        if provider_class is None:
            raise ValueError(
                f"Provider '{settings.api_provider}' is not yet supported. "
                f"Supported providers: {', '.join([p.value for p in provider_map.keys()])}"
            )

        return provider_class(settings)

    async def create_message(
        self,
        system_prompt: str,
        messages: List[MessageParam],
        metadata: Optional[ApiHandlerCreateMessageMetadata] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> ApiStream:
        """
        Create a message with the AI model

        Args:
            system_prompt: System prompt that defines the AI's behavior
            messages: List of conversation messages
            metadata: Optional metadata for tracking and logging
            tools: Optional list of tool definitions for the AI to use

        Returns:
            ApiStream: Streaming response that can be iterated over

        Example:
            ```python
            response = await client.create_message(
                system_prompt="You are a helpful coding assistant.",
                messages=[
                    {"role": "user", "content": "Write a hello world function"}
                ],
                metadata={"task_id": "task-123", "mode": "code"}
            )

            # Stream the response
            async for chunk in response.stream():
                if chunk.type == "content_block_delta":
                    print(chunk.delta.text, end="", flush=True)

            # Or get the complete text
            text = await response.get_text()
            print(text)
            ```
        """
        logging.info(f"CLIENT: create_message called with {len(messages)} messages")
        logging.debug(f"CLIENT: System prompt length: {len(system_prompt)} chars")
        
        if tools:
            logging.info(f"CLIENT: {len(tools)} tools available for this request")
            logging.debug(f"CLIENT: Available tool names: {[t.get('name', 'unknown') for t in tools]}")
        else:
            logging.debug(f"CLIENT: No tools provided for this request")
        
        if metadata:
            logging.debug(f"CLIENT: Metadata: {metadata}")
        
        return await self._provider.create_message(system_prompt, messages, metadata, tools)

    def get_model(self) -> tuple[str, ModelInfo]:
        """
        Get information about the current model

        Returns:
            tuple: (model_id, ModelInfo) containing model ID and detailed information

        Example:
            ```python
            model_id, model_info = client.get_model()
            print(f"Model: {model_id}")
            print(f"Context window: {model_info.context_window}")
            print(f"Supports images: {model_info.supports_images}")
            ```
        """
        return self._provider.get_model()

    async def count_tokens(self, content: List[ContentBlock]) -> int:
        """
        Count tokens in the given content

        Useful for estimating costs and ensuring content fits within context windows.

        Args:
            content: List of content blocks to count tokens for

        Returns:
            int: Number of tokens

        Example:
            ```python
            from roo_code import TextContent

            content = [TextContent(type="text", text="Hello, world!")]
            token_count = await client.count_tokens(content)
            print(f"Token count: {token_count}")
            ```
        """
        return await self._provider.count_tokens(content)

    @property
    def provider(self) -> BaseProvider:
        """
        Get the underlying provider instance

        Returns:
            BaseProvider: The active provider
        """
        return self._provider

    @property
    def model_id(self) -> str:
        """
        Get the current model ID

        Returns:
            str: Model identifier
        """
        return self.provider_settings.api_model_id

    @property
    def provider_name(self) -> str:
        """
        Get the current provider name

        Returns:
            str: Provider name
        """
        return self.provider_settings.api_provider.value