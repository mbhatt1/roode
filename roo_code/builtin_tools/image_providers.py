"""Image generation providers for multiple AI services."""

import os
import json
import base64
import asyncio
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import aiohttp


@dataclass
class ImageGenerationResult:
    """Result from image generation."""
    image_data: bytes
    provider: str
    model: str
    enhanced_prompt: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class ImageProvider(ABC):
    """Abstract base class for image generation providers."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize provider with configuration.
        
        Args:
            config: Provider-specific configuration dictionary
        """
        self.config = config
    
    @abstractmethod
    async def generate(
        self,
        prompt: str,
        size: str = "1024x1024",
        quality: str = "standard",
        **kwargs
    ) -> ImageGenerationResult:
        """Generate an image from a text prompt.
        
        Args:
            prompt: Text description of the image to generate
            size: Image dimensions (e.g., "1024x1024")
            quality: Image quality setting
            **kwargs: Provider-specific parameters
            
        Returns:
            ImageGenerationResult with image data and metadata
        """
        pass
    
    @abstractmethod
    async def validate_config(self) -> tuple[bool, Optional[str]]:
        """Validate provider configuration.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name."""
        pass


class OllamaProvider(ImageProvider):
    """Ollama provider for prompt enhancement and image understanding.
    
    Note: Ollama doesn't natively generate images, but we use it for:
    1. Enhancing prompts using LLMs
    2. Describing images using vision models (llava)
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.base_url = config.get("base_url", "http://localhost:11434")
        self.model = config.get("model", "llama3.2-vision")
        self.timeout = config.get("timeout", 30)
    
    @property
    def name(self) -> str:
        return "ollama"
    
    async def generate(
        self,
        prompt: str,
        size: str = "1024x1024",
        quality: str = "standard",
        **kwargs
    ) -> ImageGenerationResult:
        """Ollama cannot generate images directly."""
        raise NotImplementedError(
            "Ollama provider cannot generate images. Use it for prompt enhancement "
            "with OllamaAssistedProvider instead."
        )
    
    async def enhance_prompt(self, user_prompt: str) -> str:
        """Use Ollama's LLM to enhance an image generation prompt.
        
        Args:
            user_prompt: Basic user prompt
            
        Returns:
            Enhanced, detailed prompt suitable for image generation
        """
        enhancement_instruction = (
            f"You are an expert at creating detailed image generation prompts. "
            f"Take this basic prompt and expand it into a detailed, vivid description "
            f"that will produce a high-quality AI-generated image. Include details about "
            f"style, lighting, composition, and quality. Keep it concise but descriptive.\n\n"
            f"Basic prompt: {user_prompt}\n\n"
            f"Enhanced prompt:"
        )
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": enhancement_instruction,
                        "stream": False
                    },
                    timeout=aiohttp.ClientTimeout(total=self.timeout)
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise RuntimeError(f"Ollama API error: {error_text}")
                    
                    result = await response.json()
                    enhanced = result.get("response", "").strip()
                    
                    # If the model didn't produce a good enhancement, return original
                    if not enhanced or len(enhanced) < len(user_prompt):
                        return user_prompt
                    
                    return enhanced
                    
            except asyncio.TimeoutError:
                raise RuntimeError(f"Ollama request timed out after {self.timeout}s")
            except aiohttp.ClientError as e:
                raise RuntimeError(f"Failed to connect to Ollama: {str(e)}")
    
    async def describe_image(self, image_path: str) -> str:
        """Use Ollama vision model to describe an image.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Text description of the image
        """
        # Read and encode image
        with open(image_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode()
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": "Describe this image in detail.",
                        "images": [image_data],
                        "stream": False
                    },
                    timeout=aiohttp.ClientTimeout(total=self.timeout)
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise RuntimeError(f"Ollama API error: {error_text}")
                    
                    result = await response.json()
                    return result.get("response", "").strip()
                    
            except asyncio.TimeoutError:
                raise RuntimeError(f"Ollama request timed out after {self.timeout}s")
            except aiohttp.ClientError as e:
                raise RuntimeError(f"Failed to connect to Ollama: {str(e)}")
    
    async def validate_config(self) -> tuple[bool, Optional[str]]:
        """Validate Ollama is running and model is available."""
        async with aiohttp.ClientSession() as session:
            try:
                # Check if Ollama is running
                async with session.get(
                    f"{self.base_url}/api/tags",
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    if response.status != 200:
                        return False, "Ollama server is not responding"
                    
                    data = await response.json()
                    models = [m["name"] for m in data.get("models", [])]
                    
                    # Check if required model is available
                    if not any(self.model in m for m in models):
                        return False, f"Model '{self.model}' not found. Run: ollama pull {self.model}"
                    
                    return True, None
                    
            except (aiohttp.ClientError, asyncio.TimeoutError):
                return False, f"Cannot connect to Ollama at {self.base_url}"


class OpenAIProvider(ImageProvider):
    """OpenAI DALL-E image generation provider."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key = config.get("api_key") or os.getenv("OPENAI_API_KEY")
        self.model = config.get("model", "dall-e-3")
        self.base_url = config.get("base_url", "https://api.openai.com/v1")
        self.timeout = config.get("timeout", 60)
        
        if not self.api_key:
            raise ValueError("OpenAI API key not provided in config or OPENAI_API_KEY env var")
    
    @property
    def name(self) -> str:
        return "openai"
    
    async def generate(
        self,
        prompt: str,
        size: str = "1024x1024",
        quality: str = "standard",
        **kwargs
    ) -> ImageGenerationResult:
        """Generate image using OpenAI DALL-E.
        
        Args:
            prompt: Text description of the image
            size: One of "1024x1024", "1024x1792", "1792x1024" for DALL-E 3
            quality: "standard" or "hd"
            **kwargs: Additional parameters (style, n, etc.)
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # Validate size for DALL-E 3
        valid_sizes = ["1024x1024", "1024x1792", "1792x1024"]
        if self.model == "dall-e-3" and size not in valid_sizes:
            size = "1024x1024"
        
        payload = {
            "model": self.model,
            "prompt": prompt,
            "size": size,
            "quality": quality,
            "n": 1,
            "response_format": "b64_json"
        }
        
        # Add optional parameters
        if "style" in kwargs:
            payload["style"] = kwargs["style"]
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(
                    f"{self.base_url}/images/generations",
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=self.timeout)
                ) as response:
                    if response.status != 200:
                        error_data = await response.json()
                        error_msg = error_data.get("error", {}).get("message", "Unknown error")
                        raise RuntimeError(f"OpenAI API error: {error_msg}")
                    
                    result = await response.json()
                    image_b64 = result["data"][0]["b64_json"]
                    image_data = base64.b64decode(image_b64)
                    
                    revised_prompt = result["data"][0].get("revised_prompt")
                    
                    return ImageGenerationResult(
                        image_data=image_data,
                        provider=self.name,
                        model=self.model,
                        enhanced_prompt=revised_prompt,
                        metadata={
                            "size": size,
                            "quality": quality,
                            "original_prompt": prompt
                        }
                    )
                    
            except asyncio.TimeoutError:
                raise RuntimeError(f"OpenAI request timed out after {self.timeout}s")
            except aiohttp.ClientError as e:
                raise RuntimeError(f"Failed to connect to OpenAI API: {str(e)}")
    
    async def validate_config(self) -> tuple[bool, Optional[str]]:
        """Validate OpenAI API key and access."""
        if not self.api_key:
            return False, "OpenAI API key not configured"
        
        # Quick validation - check models endpoint
        headers = {"Authorization": f"Bearer {self.api_key}"}
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(
                    f"{self.base_url}/models",
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    if response.status == 401:
                        return False, "Invalid OpenAI API key"
                    elif response.status != 200:
                        return False, f"OpenAI API returned status {response.status}"
                    return True, None
            except (aiohttp.ClientError, asyncio.TimeoutError):
                return False, "Cannot connect to OpenAI API"


class StabilityAIProvider(ImageProvider):
    """Stability AI image generation provider."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key = config.get("api_key") or os.getenv("STABILITY_AI_KEY")
        self.engine = config.get("engine", "stable-diffusion-xl-1024-v1-0")
        self.base_url = config.get("base_url", "https://api.stability.ai/v1")
        self.timeout = config.get("timeout", 60)
        
        if not self.api_key:
            raise ValueError("Stability AI API key not provided in config or STABILITY_AI_KEY env var")
    
    @property
    def name(self) -> str:
        return "stability_ai"
    
    async def generate(
        self,
        prompt: str,
        size: str = "1024x1024",
        quality: str = "standard",
        **kwargs
    ) -> ImageGenerationResult:
        """Generate image using Stability AI.
        
        Args:
            prompt: Text description of the image
            size: Image dimensions (e.g., "1024x1024")
            quality: Not directly used, but affects steps/cfg_scale
            **kwargs: Additional parameters (steps, cfg_scale, style_preset, etc.)
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        # Parse size
        try:
            width, height = map(int, size.split("x"))
        except ValueError:
            width, height = 1024, 1024
        
        # Quality affects generation parameters
        steps = kwargs.get("steps", 50 if quality == "hd" else 30)
        cfg_scale = kwargs.get("cfg_scale", 7)
        
        payload = {
            "text_prompts": [{"text": prompt, "weight": 1}],
            "cfg_scale": cfg_scale,
            "height": height,
            "width": width,
            "samples": 1,
            "steps": steps
        }
        
        # Add optional parameters
        if "style_preset" in kwargs:
            payload["style_preset"] = kwargs["style_preset"]
        if "seed" in kwargs:
            payload["seed"] = kwargs["seed"]
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(
                    f"{self.base_url}/generation/{self.engine}/text-to-image",
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=self.timeout)
                ) as response:
                    if response.status != 200:
                        error_data = await response.json()
                        error_msg = error_data.get("message", "Unknown error")
                        raise RuntimeError(f"Stability AI API error: {error_msg}")
                    
                    result = await response.json()
                    image_b64 = result["artifacts"][0]["base64"]
                    image_data = base64.b64decode(image_b64)
                    
                    return ImageGenerationResult(
                        image_data=image_data,
                        provider=self.name,
                        model=self.engine,
                        enhanced_prompt=None,
                        metadata={
                            "size": size,
                            "steps": steps,
                            "cfg_scale": cfg_scale,
                            "seed": result["artifacts"][0].get("seed"),
                            "original_prompt": prompt
                        }
                    )
                    
            except asyncio.TimeoutError:
                raise RuntimeError(f"Stability AI request timed out after {self.timeout}s")
            except aiohttp.ClientError as e:
                raise RuntimeError(f"Failed to connect to Stability AI API: {str(e)}")
    
    async def validate_config(self) -> tuple[bool, Optional[str]]:
        """Validate Stability AI API key and access."""
        if not self.api_key:
            return False, "Stability AI API key not configured"
        
        headers = {"Authorization": f"Bearer {self.api_key}"}
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(
                    f"{self.base_url}/user/account",
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    if response.status == 401:
                        return False, "Invalid Stability AI API key"
                    elif response.status != 200:
                        return False, f"Stability AI API returned status {response.status}"
                    return True, None
            except (aiohttp.ClientError, asyncio.TimeoutError):
                return False, "Cannot connect to Stability AI API"


class OllamaAssistedProvider(ImageProvider):
    """Uses Ollama to enhance prompts, then delegates to another provider for generation."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.ollama_config = config.get("ollama", {})
        self.delegate_provider_name = config.get("delegate_provider", "openai")
        self.delegate_config = config.get(self.delegate_provider_name, {})
        
        # Initialize Ollama for prompt enhancement
        self.ollama = OllamaProvider(self.ollama_config)
        
        # Initialize delegate provider
        if self.delegate_provider_name == "openai":
            self.delegate = OpenAIProvider(self.delegate_config)
        elif self.delegate_provider_name == "stability_ai":
            self.delegate = StabilityAIProvider(self.delegate_config)
        else:
            raise ValueError(f"Unknown delegate provider: {self.delegate_provider_name}")
    
    @property
    def name(self) -> str:
        return f"ollama_assisted_{self.delegate_provider_name}"
    
    async def generate(
        self,
        prompt: str,
        size: str = "1024x1024",
        quality: str = "standard",
        **kwargs
    ) -> ImageGenerationResult:
        """Generate image with Ollama-enhanced prompt.
        
        Args:
            prompt: Basic user prompt
            size: Image dimensions
            quality: Image quality setting
            **kwargs: Additional parameters for delegate provider
        """
        # Enhance prompt using Ollama
        try:
            enhanced_prompt = await self.ollama.enhance_prompt(prompt)
        except Exception as e:
            # If enhancement fails, use original prompt
            print(f"Warning: Prompt enhancement failed: {e}")
            enhanced_prompt = prompt
        
        # Generate image using delegate provider
        result = await self.delegate.generate(
            enhanced_prompt,
            size=size,
            quality=quality,
            **kwargs
        )
        
        # Update result to show it was Ollama-assisted
        result.provider = self.name
        result.enhanced_prompt = enhanced_prompt
        if result.metadata:
            result.metadata["original_prompt"] = prompt
            result.metadata["ollama_enhanced"] = True
        
        return result
    
    async def validate_config(self) -> tuple[bool, Optional[str]]:
        """Validate both Ollama and delegate provider."""
        # Check Ollama
        ollama_valid, ollama_error = await self.ollama.validate_config()
        if not ollama_valid:
            return False, f"Ollama validation failed: {ollama_error}"
        
        # Check delegate
        delegate_valid, delegate_error = await self.delegate.validate_config()
        if not delegate_valid:
            return False, f"Delegate provider validation failed: {delegate_error}"
        
        return True, None


class ProviderFactory:
    """Factory for creating image generation providers."""
    
    @staticmethod
    def create_provider(provider_name: str, config: Dict[str, Any]) -> ImageProvider:
        """Create an image provider instance.
        
        Args:
            provider_name: Name of the provider (e.g., "openai", "stability_ai")
            config: Provider configuration
            
        Returns:
            ImageProvider instance
            
        Raises:
            ValueError: If provider name is unknown
        """
        providers = {
            "ollama": OllamaProvider,
            "openai": OpenAIProvider,
            "stability_ai": StabilityAIProvider,
            "ollama_assisted_openai": lambda cfg: OllamaAssistedProvider({
                **cfg,
                "delegate_provider": "openai"
            }),
            "ollama_assisted_stability": lambda cfg: OllamaAssistedProvider({
                **cfg,
                "delegate_provider": "stability_ai"
            })
        }
        
        if provider_name not in providers:
            raise ValueError(
                f"Unknown provider: {provider_name}. "
                f"Available: {', '.join(providers.keys())}"
            )
        
        return providers[provider_name](config)
    
    @staticmethod
    def list_providers() -> List[str]:
        """List all available provider names."""
        return [
            "ollama",
            "openai",
            "stability_ai",
            "ollama_assisted_openai",
            "ollama_assisted_stability"
        ]