"""Groq provider implementation"""

from typing import Optional
from ..types import ModelInfo, ProviderSettings
from .openai import OpenAIProvider


class GroqProvider(OpenAIProvider):
    """
    Provider for Groq API
    Groq uses OpenAI-compatible format
    """

    MODEL_INFO = {
        "llama-3.3-70b-versatile": ModelInfo(
            max_tokens=8000,
            context_window=128000,
            supports_images=False,
            supports_prompt_cache=False,
            input_price=0.59,
            output_price=0.79,
        ),
        "llama-3.1-70b-versatile": ModelInfo(
            max_tokens=8000,
            context_window=128000,
            supports_images=False,
            supports_prompt_cache=False,
            input_price=0.59,
            output_price=0.79,
        ),
        "llama-3.1-8b-instant": ModelInfo(
            max_tokens=8000,
            context_window=128000,
            supports_images=False,
            supports_prompt_cache=False,
            input_price=0.05,
            output_price=0.08,
        ),
        "mixtral-8x7b-32768": ModelInfo(
            max_tokens=32768,
            context_window=32768,
            supports_images=False,
            supports_prompt_cache=False,
            input_price=0.24,
            output_price=0.24,
        ),
        "gemma2-9b-it": ModelInfo(
            max_tokens=8192,
            context_window=8192,
            supports_images=False,
            supports_prompt_cache=False,
            input_price=0.20,
            output_price=0.20,
        ),
    }

    def __init__(self, settings: ProviderSettings):
        """
        Initialize Groq provider

        Args:
            settings: Provider configuration settings
        """
        if not settings.api_key:
            raise ValueError("Groq API key is required")

        # Set Groq base URL
        settings.api_base_url = settings.api_base_url or "https://api.groq.com/openai/v1"
        
        # Call parent constructor
        super().__init__(settings)

    def get_model(self) -> tuple[str, ModelInfo]:
        """
        Get model ID and information

        Returns:
            tuple: (model_id, ModelInfo)
        """
        model_id = self.settings.api_model_id
        model_info = self.MODEL_INFO.get(
            model_id,
            ModelInfo(
                context_window=32768,
                supports_images=False,
                supports_prompt_cache=False,
            ),
        )
        return model_id, model_info