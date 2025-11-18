"""Base provider implementation"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import tiktoken
from anthropic.types import ContentBlock

from ..types import ModelInfo, ProviderSettings, MessageParam, ApiHandlerCreateMessageMetadata
from ..stream import ApiStream


class BaseProvider(ABC):
    """Base class for all API providers"""

    def __init__(self, settings: ProviderSettings):
        """
        Initialize base provider

        Args:
            settings: Provider configuration settings
        """
        self.settings = settings
        self._tokenizer = None

    @abstractmethod
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
            system_prompt: System prompt for the conversation
            messages: List of messages in the conversation
            metadata: Optional metadata for tracking
            tools: Optional list of tool definitions for the AI to use

        Returns:
            ApiStream: Streaming response
        """
        pass

    @abstractmethod
    def get_model(self) -> tuple[str, ModelInfo]:
        """
        Get model ID and information

        Returns:
            tuple: (model_id, ModelInfo)
        """
        pass

    async def count_tokens(self, content: List[ContentBlock]) -> int:
        """
        Count tokens in content blocks using tiktoken

        Args:
            content: List of content blocks

        Returns:
            int: Token count
        """
        if self._tokenizer is None:
            try:
                self._tokenizer = tiktoken.encoding_for_model("gpt-4")
            except KeyError:
                self._tokenizer = tiktoken.get_encoding("cl100k_base")

        total_tokens = 0
        for block in content:
            if hasattr(block, "text"):
                total_tokens += len(self._tokenizer.encode(block.text))

        return total_tokens

    def _prepare_headers(self, metadata: Optional[ApiHandlerCreateMessageMetadata] = None) -> dict:
        """
        Prepare common headers for API requests

        Args:
            metadata: Optional metadata for headers

        Returns:
            dict: HTTP headers
        """
        headers = {
            "Content-Type": "application/json",
        }

        if self.settings.api_key:
            headers["Authorization"] = f"Bearer {self.settings.api_key}"

        if metadata:
            if metadata.task_id:
                headers["X-Task-ID"] = metadata.task_id
            if metadata.mode:
                headers["X-Mode"] = metadata.mode

        return headers