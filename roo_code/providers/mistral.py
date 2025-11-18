"""Mistral AI provider implementation"""

from typing import Optional
from ..types import ModelInfo, ProviderSettings
from .openai import OpenAIProvider


class MistralProvider(OpenAIProvider):
    """
    Provider for Mistral AI API
    Mistral uses OpenAI-compatible format
    """

    MODEL_INFO = {
        "mistral-large-latest": ModelInfo(
            max_tokens=128000,
            context_window=128000,
            supports_images=False,
            supports_prompt_cache=False,
            input_price=2.00,
            output_price=6.00,
        ),
        "mistral-small-latest": ModelInfo(
            max_tokens=32000,
            context_window=32000,
            supports_images=False,
            supports_prompt_cache=False,
            input_price=0.20,
            output_price=0.60,
        ),
        "codestral-latest": ModelInfo(
            max_tokens=32000,
            context_window=32000,
            supports_images=False,
            supports_prompt_cache=False,
            input_price=0.20,
            output_price=0.60,
        ),
        "mistral-nemo": ModelInfo(
            max_tokens=128000,
            context_window=128000,
            supports_images=False,
            supports_prompt_cache=False,
            input_price=0.15,
            output_price=0.15,
        ),
        "pixtral-12b-2409": ModelInfo(
            max_tokens=8192,
            context_window=128000,
            supports_images=True,
            supports_prompt_cache=False,
            input_price=0.15,
            output_price=0.15,
        ),
    }

    def __init__(self, settings: ProviderSettings):
        """
        Initialize Mistral provider

        Args:
            settings: Provider configuration settings
        """
        if not settings.api_key:
            raise ValueError("Mistral API key is required")

        # Set Mistral base URL
        settings.api_base_url = settings.api_base_url or "https://api.mistral.ai/v1"
        
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
                context_window=32000,
                supports_images=False,
                supports_prompt_cache=False,
            ),
        )
        return model_id, model_info