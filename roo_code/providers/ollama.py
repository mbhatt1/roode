"""Ollama provider implementation"""

from typing import Optional
from ..types import ModelInfo, ProviderSettings
from .openai import OpenAIProvider


class OllamaProvider(OpenAIProvider):
    """
    Provider for Ollama local models
    Ollama uses OpenAI-compatible format
    """

    def __init__(self, settings: ProviderSettings):
        """
        Initialize Ollama provider

        Args:
            settings: Provider configuration settings
        """
        # Ollama typically runs locally, default to localhost
        settings.api_base_url = settings.api_base_url or "http://localhost:11434/v1"
        
        # Ollama doesn't require an API key for local usage
        if not settings.api_key:
            settings.api_key = "ollama"  # Dummy key for compatibility
        
        # Call parent constructor
        super().__init__(settings)

    def get_model(self) -> tuple[str, ModelInfo]:
        """
        Get model ID and information
        
        Ollama supports many models with varying capabilities

        Returns:
            tuple: (model_id, ModelInfo)
        """
        model_id = self.settings.api_model_id
        
        # Ollama models vary widely - provide sensible defaults
        model_info = ModelInfo(
            context_window=4096,  # Conservative default
            supports_images=False,  # Depends on the specific model
            supports_prompt_cache=False,
        )
        
        return model_id, model_info