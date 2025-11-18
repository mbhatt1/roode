"""DeepSeek provider implementation"""

from typing import Optional
from ..types import ModelInfo, ProviderSettings
from .openai import OpenAIProvider


class DeepSeekProvider(OpenAIProvider):
    """
    Provider for DeepSeek API
    DeepSeek uses OpenAI-compatible format
    """

    MODEL_INFO = {
        "deepseek-chat": ModelInfo(
            max_tokens=4096,
            context_window=32768,
            supports_images=False,
            supports_prompt_cache=False,
            input_price=0.14,
            output_price=0.28,
        ),
        "deepseek-coder": ModelInfo(
            max_tokens=4096,
            context_window=16384,
            supports_images=False,
            supports_prompt_cache=False,
            input_price=0.14,
            output_price=0.28,
        ),
    }

    def __init__(self, settings: ProviderSettings):
        """
        Initialize DeepSeek provider

        Args:
            settings: Provider configuration settings
        """
        if not settings.api_key:
            raise ValueError("DeepSeek API key is required")

        # Set DeepSeek base URL
        settings.api_base_url = settings.api_base_url or "https://api.deepseek.com/v1"
        
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