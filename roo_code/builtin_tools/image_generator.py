"""Core image generation system with storage and provider management."""

import os
import json
import hashlib
from datetime import datetime
from typing import Dict, Any, Optional, List
from pathlib import Path
from dataclasses import dataclass, asdict

from .image_providers import (
    ImageProvider,
    ProviderFactory,
    ImageGenerationResult
)


@dataclass
class ImageMetadata:
    """Metadata for a generated image."""
    image_id: str
    filename: str
    prompt: str
    enhanced_prompt: Optional[str]
    provider: str
    model: str
    size: str
    quality: str
    timestamp: str
    file_size: int
    provider_metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ImageMetadata":
        """Create from dictionary."""
        return cls(**data)


class ImageStorage:
    """Manages storage of generated images with metadata."""
    
    def __init__(self, storage_dir: str = ".roo/generated_images"):
        """Initialize image storage.
        
        Args:
            storage_dir: Directory for storing generated images (relative to workspace)
        """
        self.storage_dir = Path(storage_dir)
        self.metadata_file = self.storage_dir / "metadata.json"
        self._metadata_cache: Dict[str, ImageMetadata] = {}
        self._ensure_storage_dir()
        self._load_metadata()
    
    def _ensure_storage_dir(self):
        """Create storage directory if it doesn't exist."""
        self.storage_dir.mkdir(parents=True, exist_ok=True)
    
    def _load_metadata(self):
        """Load metadata from disk."""
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, 'r') as f:
                    data = json.load(f)
                    self._metadata_cache = {
                        img_id: ImageMetadata.from_dict(meta)
                        for img_id, meta in data.items()
                    }
            except (json.JSONDecodeError, KeyError) as e:
                print(f"Warning: Failed to load metadata: {e}")
                self._metadata_cache = {}
    
    def _save_metadata(self):
        """Save metadata to disk."""
        data = {
            img_id: meta.to_dict()
            for img_id, meta in self._metadata_cache.items()
        }
        with open(self.metadata_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def _generate_image_id(self, prompt: str, timestamp: str) -> str:
        """Generate unique image ID from prompt and timestamp."""
        content = f"{prompt}_{timestamp}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def save_image(
        self,
        image_data: bytes,
        prompt: str,
        enhanced_prompt: Optional[str],
        provider: str,
        model: str,
        size: str,
        quality: str,
        provider_metadata: Optional[Dict[str, Any]] = None,
        custom_filename: Optional[str] = None
    ) -> tuple[str, str]:
        """Save generated image with metadata.
        
        Args:
            image_data: Raw image bytes
            prompt: Original prompt
            enhanced_prompt: Enhanced prompt (if any)
            provider: Provider name
            model: Model name
            size: Image size
            quality: Image quality
            provider_metadata: Additional provider-specific metadata
            custom_filename: Optional custom filename (without extension)
            
        Returns:
            Tuple of (image_id, file_path)
        """
        timestamp = datetime.utcnow().isoformat()
        image_id = self._generate_image_id(prompt, timestamp)
        
        # Generate filename
        if custom_filename:
            filename = f"{custom_filename}.png"
        else:
            # Use timestamp and truncated prompt for filename
            safe_prompt = "".join(c for c in prompt[:30] if c.isalnum() or c in (' ', '-', '_')).strip()
            safe_prompt = safe_prompt.replace(' ', '_')
            timestamp_short = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            filename = f"{timestamp_short}_{safe_prompt}.png"
        
        # Save image file
        file_path = self.storage_dir / filename
        with open(file_path, 'wb') as f:
            f.write(image_data)
        
        # Create and save metadata
        metadata = ImageMetadata(
            image_id=image_id,
            filename=filename,
            prompt=prompt,
            enhanced_prompt=enhanced_prompt,
            provider=provider,
            model=model,
            size=size,
            quality=quality,
            timestamp=timestamp,
            file_size=len(image_data),
            provider_metadata=provider_metadata
        )
        
        self._metadata_cache[image_id] = metadata
        self._save_metadata()
        
        return image_id, str(file_path)
    
    def get_image_path(self, image_id: str) -> Optional[str]:
        """Get path to stored image by ID.
        
        Args:
            image_id: Image ID
            
        Returns:
            File path or None if not found
        """
        metadata = self._metadata_cache.get(image_id)
        if metadata:
            return str(self.storage_dir / metadata.filename)
        return None
    
    def get_metadata(self, image_id: str) -> Optional[ImageMetadata]:
        """Get metadata for an image.
        
        Args:
            image_id: Image ID
            
        Returns:
            ImageMetadata or None if not found
        """
        return self._metadata_cache.get(image_id)
    
    def list_images(
        self,
        limit: int = 10,
        provider: Optional[str] = None
    ) -> List[ImageMetadata]:
        """List recent images.
        
        Args:
            limit: Maximum number of images to return
            provider: Optional filter by provider name
            
        Returns:
            List of ImageMetadata, sorted by timestamp (newest first)
        """
        images = list(self._metadata_cache.values())
        
        # Filter by provider if specified
        if provider:
            images = [img for img in images if img.provider == provider]
        
        # Sort by timestamp (newest first)
        images.sort(key=lambda x: x.timestamp, reverse=True)
        
        return images[:limit]
    
    def delete_image(self, image_id: str) -> bool:
        """Delete an image and its metadata.
        
        Args:
            image_id: Image ID
            
        Returns:
            True if deleted, False if not found
        """
        metadata = self._metadata_cache.get(image_id)
        if not metadata:
            return False
        
        # Delete file
        file_path = self.storage_dir / metadata.filename
        if file_path.exists():
            file_path.unlink()
        
        # Delete metadata
        del self._metadata_cache[image_id]
        self._save_metadata()
        
        return True
    
    def get_stats(self) -> Dict[str, Any]:
        """Get storage statistics.
        
        Returns:
            Dictionary with storage stats
        """
        total_images = len(self._metadata_cache)
        total_size = sum(meta.file_size for meta in self._metadata_cache.values())
        
        providers = {}
        for meta in self._metadata_cache.values():
            providers[meta.provider] = providers.get(meta.provider, 0) + 1
        
        return {
            "total_images": total_images,
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "providers": providers,
            "storage_dir": str(self.storage_dir)
        }


class ImageGenerator:
    """Main image generation coordinator."""
    
    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        workspace_path: Optional[str] = None
    ):
        """Initialize image generator.
        
        Args:
            config: Configuration dictionary
            workspace_path: Workspace directory path
        """
        self.config = config or self._load_default_config()
        self.workspace_path = workspace_path or os.getcwd()
        
        # Initialize storage
        storage_dir = self.config.get("storage_dir", ".roo/generated_images")
        full_storage_path = os.path.join(self.workspace_path, storage_dir)
        self.storage = ImageStorage(full_storage_path)
        
        # Provider cache
        self._providers: Dict[str, ImageProvider] = {}
    
    def _load_default_config(self) -> Dict[str, Any]:
        """Load default configuration."""
        return {
            "primary_provider": "ollama_assisted_openai",
            "fallback_providers": ["openai", "stability_ai"],
            "storage_dir": ".roo/generated_images",
            "ollama": {
                "base_url": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
                "model": "llama3.2-vision",
                "timeout": 30
            },
            "openai": {
                "api_key": os.getenv("OPENAI_API_KEY"),
                "model": "dall-e-3",
                "timeout": 60
            },
            "stability_ai": {
                "api_key": os.getenv("STABILITY_AI_KEY"),
                "engine": "stable-diffusion-xl-1024-v1-0",
                "timeout": 60
            }
        }
    
    def _get_provider(self, provider_name: str) -> ImageProvider:
        """Get or create a provider instance.
        
        Args:
            provider_name: Name of the provider
            
        Returns:
            ImageProvider instance
        """
        if provider_name not in self._providers:
            # Get provider config
            provider_config = self._get_provider_config(provider_name)
            self._providers[provider_name] = ProviderFactory.create_provider(
                provider_name,
                provider_config
            )
        return self._providers[provider_name]
    
    def _get_provider_config(self, provider_name: str) -> Dict[str, Any]:
        """Get configuration for a specific provider.
        
        Args:
            provider_name: Name of the provider
            
        Returns:
            Provider configuration dictionary
        """
        # For composite providers like "ollama_assisted_openai"
        if provider_name.startswith("ollama_assisted_"):
            delegate = provider_name.replace("ollama_assisted_", "")
            return {
                "ollama": self.config.get("ollama", {}),
                delegate: self.config.get(delegate, {}),
                "delegate_provider": delegate
            }
        
        return self.config.get(provider_name, {})
    
    async def generate(
        self,
        prompt: str,
        size: str = "1024x1024",
        quality: str = "standard",
        provider: Optional[str] = None,
        output_path: Optional[str] = None,
        **kwargs
    ) -> tuple[str, ImageMetadata]:
        """Generate an image.
        
        Args:
            prompt: Text description of the image
            size: Image dimensions (e.g., "1024x1024")
            quality: Image quality ("standard" or "hd")
            provider: Specific provider to use (uses primary if None)
            output_path: Custom output path (relative to workspace)
            **kwargs: Additional provider-specific parameters
            
        Returns:
            Tuple of (image_path, metadata)
            
        Raises:
            RuntimeError: If all providers fail
        """
        # Determine which provider(s) to try
        providers_to_try = []
        if provider:
            providers_to_try.append(provider)
        else:
            providers_to_try.append(self.config.get("primary_provider", "openai"))
            providers_to_try.extend(self.config.get("fallback_providers", []))
        
        # Remove duplicates while preserving order
        providers_to_try = list(dict.fromkeys(providers_to_try))
        
        last_error = None
        
        for provider_name in providers_to_try:
            try:
                # Get provider instance
                provider_instance = self._get_provider(provider_name)
                
                # Validate provider configuration
                is_valid, error = await provider_instance.validate_config()
                if not is_valid:
                    print(f"Skipping {provider_name}: {error}")
                    last_error = error
                    continue
                
                # Generate image
                result: ImageGenerationResult = await provider_instance.generate(
                    prompt=prompt,
                    size=size,
                    quality=quality,
                    **kwargs
                )
                
                # Determine custom filename from output_path if provided
                custom_filename = None
                if output_path:
                    custom_filename = Path(output_path).stem
                
                # Save image
                image_id, image_path = self.storage.save_image(
                    image_data=result.image_data,
                    prompt=prompt,
                    enhanced_prompt=result.enhanced_prompt,
                    provider=result.provider,
                    model=result.model,
                    size=size,
                    quality=quality,
                    provider_metadata=result.metadata,
                    custom_filename=custom_filename
                )
                
                # Get metadata
                metadata = self.storage.get_metadata(image_id)
                
                # If custom output path specified and different from storage path
                if output_path and not output_path.startswith(str(self.storage.storage_dir)):
                    full_output_path = os.path.join(self.workspace_path, output_path)
                    os.makedirs(os.path.dirname(full_output_path), exist_ok=True)
                    
                    # Copy to custom location
                    import shutil
                    shutil.copy2(image_path, full_output_path)
                    image_path = full_output_path
                
                return image_path, metadata
                
            except Exception as e:
                print(f"Provider {provider_name} failed: {str(e)}")
                last_error = str(e)
                continue
        
        # All providers failed
        raise RuntimeError(
            f"All image generation providers failed. Last error: {last_error}\n"
            f"Tried providers: {', '.join(providers_to_try)}"
        )
    
    async def validate_providers(self) -> Dict[str, tuple[bool, Optional[str]]]:
        """Validate all configured providers.
        
        Returns:
            Dictionary mapping provider names to (is_valid, error_message) tuples
        """
        results = {}
        
        all_providers = [self.config.get("primary_provider")] + \
                       self.config.get("fallback_providers", [])
        
        for provider_name in set(all_providers):
            if not provider_name:
                continue
            
            try:
                provider = self._get_provider(provider_name)
                is_valid, error = await provider.validate_config()
                results[provider_name] = (is_valid, error)
            except Exception as e:
                results[provider_name] = (False, str(e))
        
        return results
    
    def list_available_providers(self) -> List[str]:
        """List all available provider types.
        
        Returns:
            List of provider names
        """
        return ProviderFactory.list_providers()
    
    def get_storage_stats(self) -> Dict[str, Any]:
        """Get image storage statistics.
        
        Returns:
            Storage statistics dictionary
        """
        return self.storage.get_stats()
    
    def list_recent_images(
        self,
        limit: int = 10,
        provider: Optional[str] = None
    ) -> List[ImageMetadata]:
        """List recently generated images.
        
        Args:
            limit: Maximum number to return
            provider: Optional filter by provider
            
        Returns:
            List of ImageMetadata
        """
        return self.storage.list_images(limit=limit, provider=provider)