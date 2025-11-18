"""OpenRouter provider implementation"""

from typing import Any, Dict, List, Optional
from openai import AsyncOpenAI
from anthropic.types import ContentBlock

from ..types import (
    ModelInfo,
    ProviderSettings,
    MessageParam,
    ApiHandlerCreateMessageMetadata,
)
from ..stream import ApiStream
from .openai import OpenAIProvider


class OpenRouterProvider(OpenAIProvider):
    """
    Provider for OpenRouter API
    OpenRouter uses OpenAI-compatible format, so we inherit from OpenAIProvider
    """

    def __init__(self, settings: ProviderSettings):
        """
        Initialize OpenRouter provider

        Args:
            settings: Provider configuration settings
        """
        # OpenRouter uses OpenAI format, so we use the parent's initialization
        # but override the base URL
        if not settings.api_key:
            raise ValueError("OpenRouter API key is required")

        # Set OpenRouter base URL
        settings.api_base_url = settings.api_base_url or "https://openrouter.ai/api/v1"
        
        # Call parent constructor
        super(OpenAIProvider, self).__init__(settings)
        
        self.client = AsyncOpenAI(
            api_key=settings.api_key,
            base_url=settings.api_base_url,
        )

    def get_model(self) -> tuple[str, ModelInfo]:
        """
        Get model ID and information
        
        OpenRouter supports many models, so we provide generic defaults

        Returns:
            tuple: (model_id, ModelInfo)
        """
        model_id = self.settings.api_model_id
        
        # OpenRouter supports many models - provide sensible defaults
        model_info = ModelInfo(
            context_window=128000,  # Most models support at least this
            supports_images=True,   # Many OpenRouter models support images
            supports_prompt_cache=False,
        )
        
        return model_id, model_info

    async def create_message(
        self,
        system_prompt: str,
        messages: List[MessageParam],
        metadata: Optional[ApiHandlerCreateMessageMetadata] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> ApiStream:
        """
        Create a message with OpenRouter

        Args:
            system_prompt: System prompt for the conversation
            messages: List of messages in the conversation
            metadata: Optional metadata for tracking
            tools: Optional list of tool definitions (not yet implemented for OpenRouter)

        Returns:
            ApiStream: Streaming response
        """
        # Use parent's create_message but add OpenRouter-specific headers
        return await super().create_message(system_prompt, messages, metadata, tools)

    def _prepare_headers(self, metadata: Optional[ApiHandlerCreateMessageMetadata] = None) -> dict:
        """
        Prepare headers with OpenRouter-specific additions

        Args:
            metadata: Optional metadata for headers

        Returns:
            dict: HTTP headers
        """
        headers = super()._prepare_headers(metadata)
        
        # Add OpenRouter-specific headers
        headers["HTTP-Referer"] = "https://roocode.com"
        headers["X-Title"] = "Roo Code Python SDK"
        
        return headers