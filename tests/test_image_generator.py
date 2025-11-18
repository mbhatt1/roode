"""Tests for image generation system."""

import pytest
import json
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from roo_code.builtin_tools.image_generator import (
    ImageStorage,
    ImageMetadata,
    ImageGenerator
)
from roo_code.builtin_tools.image_providers import ImageGenerationResult


class TestImageMetadata:
    """Tests for ImageMetadata."""
    
    def test_to_dict(self):
        """Test converting metadata to dictionary."""
        metadata = ImageMetadata(
            image_id="abc123",
            filename="test.png",
            prompt="a cat",
            enhanced_prompt="a beautiful cat",
            provider="openai",
            model="dall-e-3",
            size="1024x1024",
            quality="standard",
            timestamp="2024-01-01T00:00:00",
            file_size=1024,
            provider_metadata={"seed": 42}
        )
        
        data = metadata.to_dict()
        
        assert data["image_id"] == "abc123"
        assert data["filename"] == "test.png"
        assert data["prompt"] == "a cat"
        assert data["provider_metadata"]["seed"] == 42
    
    def test_from_dict(self):
        """Test creating metadata from dictionary."""
        data = {
            "image_id": "xyz789",
            "filename": "test2.png",
            "prompt": "a dog",
            "enhanced_prompt": None,
            "provider": "stability_ai",
            "model": "sdxl",
            "size": "512x512",
            "quality": "hd",
            "timestamp": "2024-01-01T00:00:00",
            "file_size": 2048,
            "provider_metadata": None
        }
        
        metadata = ImageMetadata.from_dict(data)
        
        assert metadata.image_id == "xyz789"
        assert metadata.prompt == "a dog"
        assert metadata.provider == "stability_ai"


class TestImageStorage:
    """Tests for ImageStorage."""
    
    @pytest.fixture
    def storage_dir(self, tmp_path):
        """Create temporary storage directory."""
        storage = tmp_path / "test_images"
        return str(storage)
    
    @pytest.fixture
    def storage(self, storage_dir):
        """Create ImageStorage instance."""
        return ImageStorage(storage_dir)
    
    def test_storage_dir_created(self, storage, storage_dir):
        """Test that storage directory is created."""
        assert Path(storage_dir).exists()
        assert Path(storage_dir).is_dir()
    
    def test_save_image(self, storage):
        """Test saving an image."""
        image_data = b"fake_image_data_here"
        
        image_id, file_path = storage.save_image(
            image_data=image_data,
            prompt="test prompt",
            enhanced_prompt="enhanced test prompt",
            provider="openai",
            model="dall-e-3",
            size="1024x1024",
            quality="standard"
        )
        
        # Check image was saved
        assert Path(file_path).exists()
        assert Path(file_path).read_bytes() == image_data
        
        # Check metadata was saved
        metadata = storage.get_metadata(image_id)
        assert metadata is not None
        assert metadata.prompt == "test prompt"
        assert metadata.provider == "openai"
        assert metadata.file_size == len(image_data)
    
    def test_save_image_with_custom_filename(self, storage):
        """Test saving image with custom filename."""
        image_data = b"custom_image"
        
        image_id, file_path = storage.save_image(
            image_data=image_data,
            prompt="custom",
            enhanced_prompt=None,
            provider="openai",
            model="dall-e-3",
            size="1024x1024",
            quality="standard",
            custom_filename="my_custom_image"
        )
        
        assert "my_custom_image.png" in file_path
        assert Path(file_path).exists()
    
    def test_get_image_path(self, storage):
        """Test retrieving image path by ID."""
        image_data = b"test_data"
        
        image_id, saved_path = storage.save_image(
            image_data=image_data,
            prompt="test",
            enhanced_prompt=None,
            provider="openai",
            model="dall-e-3",
            size="1024x1024",
            quality="standard"
        )
        
        retrieved_path = storage.get_image_path(image_id)
        
        assert retrieved_path == saved_path
        assert Path(retrieved_path).exists()
    
    def test_get_image_path_not_found(self, storage):
        """Test getting path for non-existent image."""
        path = storage.get_image_path("nonexistent_id")
        assert path is None
    
    def test_get_metadata(self, storage):
        """Test retrieving metadata."""
        image_data = b"metadata_test"
        
        image_id, _ = storage.save_image(
            image_data=image_data,
            prompt="metadata test",
            enhanced_prompt="enhanced metadata",
            provider="stability_ai",
            model="sdxl",
            size="512x512",
            quality="hd",
            provider_metadata={"steps": 30, "seed": 12345}
        )
        
        metadata = storage.get_metadata(image_id)
        
        assert metadata is not None
        assert metadata.prompt == "metadata test"
        assert metadata.enhanced_prompt == "enhanced metadata"
        assert metadata.provider == "stability_ai"
        assert metadata.provider_metadata["steps"] == 30
    
    def test_list_images(self, storage):
        """Test listing images."""
        # Save multiple images
        for i in range(5):
            storage.save_image(
                image_data=f"image_{i}".encode(),
                prompt=f"prompt {i}",
                enhanced_prompt=None,
                provider="openai",
                model="dall-e-3",
                size="1024x1024",
                quality="standard"
            )
        
        images = storage.list_images(limit=10)
        
        assert len(images) == 5
        # Should be sorted by timestamp (newest first)
        assert all(isinstance(img, ImageMetadata) for img in images)
    
    def test_list_images_with_limit(self, storage):
        """Test listing images with limit."""
        # Save multiple images
        for i in range(5):
            storage.save_image(
                image_data=f"image_{i}".encode(),
                prompt=f"prompt {i}",
                enhanced_prompt=None,
                provider="openai",
                model="dall-e-3",
                size="1024x1024",
                quality="standard"
            )
        
        images = storage.list_images(limit=3)
        
        assert len(images) == 3
    
    def test_list_images_filter_by_provider(self, storage):
        """Test filtering images by provider."""
        # Save images with different providers
        storage.save_image(
            image_data=b"openai_1",
            prompt="test 1",
            enhanced_prompt=None,
            provider="openai",
            model="dall-e-3",
            size="1024x1024",
            quality="standard"
        )
        storage.save_image(
            image_data=b"stability_1",
            prompt="test 2",
            enhanced_prompt=None,
            provider="stability_ai",
            model="sdxl",
            size="1024x1024",
            quality="standard"
        )
        storage.save_image(
            image_data=b"openai_2",
            prompt="test 3",
            enhanced_prompt=None,
            provider="openai",
            model="dall-e-3",
            size="1024x1024",
            quality="standard"
        )
        
        openai_images = storage.list_images(provider="openai")
        stability_images = storage.list_images(provider="stability_ai")
        
        assert len(openai_images) == 2
        assert len(stability_images) == 1
    
    def test_delete_image(self, storage):
        """Test deleting an image."""
        image_data = b"delete_me"
        
        image_id, file_path = storage.save_image(
            image_data=image_data,
            prompt="to delete",
            enhanced_prompt=None,
            provider="openai",
            model="dall-e-3",
            size="1024x1024",
            quality="standard"
        )
        
        # Verify it exists
        assert Path(file_path).exists()
        assert storage.get_metadata(image_id) is not None
        
        # Delete it
        deleted = storage.delete_image(image_id)
        
        assert deleted is True
        assert not Path(file_path).exists()
        assert storage.get_metadata(image_id) is None
    
    def test_delete_image_not_found(self, storage):
        """Test deleting non-existent image."""
        deleted = storage.delete_image("nonexistent")
        assert deleted is False
    
    def test_get_stats(self, storage):
        """Test getting storage statistics."""
        # Save some images
        for i in range(3):
            storage.save_image(
                image_data=f"data_{i}".encode() * 100,
                prompt=f"prompt {i}",
                enhanced_prompt=None,
                provider="openai" if i % 2 == 0 else "stability_ai",
                model="dall-e-3",
                size="1024x1024",
                quality="standard"
            )
        
        stats = storage.get_stats()
        
        assert stats["total_images"] == 3
        assert stats["total_size_bytes"] > 0
        assert stats["total_size_mb"] >= 0  # May be 0.0 for small test data
        assert "openai" in stats["providers"]
        assert "stability_ai" in stats["providers"]
    
    def test_metadata_persistence(self, storage_dir):
        """Test that metadata persists across instances."""
        # Create storage and save an image
        storage1 = ImageStorage(storage_dir)
        image_id, _ = storage1.save_image(
            image_data=b"persistent_data",
            prompt="persistent",
            enhanced_prompt=None,
            provider="openai",
            model="dall-e-3",
            size="1024x1024",
            quality="standard"
        )
        
        # Create new storage instance (simulates restart)
        storage2 = ImageStorage(storage_dir)
        
        # Should be able to retrieve metadata
        metadata = storage2.get_metadata(image_id)
        assert metadata is not None
        assert metadata.prompt == "persistent"


class TestImageGenerator:
    """Tests for ImageGenerator."""
    
    @pytest.fixture
    def workspace(self, tmp_path):
        """Create temporary workspace."""
        return str(tmp_path)
    
    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return {
            "primary_provider": "openai",
            "fallback_providers": ["stability_ai"],
            "storage_dir": ".roo/generated_images",
            "openai": {
                "api_key": "sk-test-key"
            },
            "stability_ai": {
                "api_key": "sk-test-stability"
            }
        }
    
    @pytest.fixture
    def generator(self, workspace, config):
        """Create ImageGenerator instance."""
        return ImageGenerator(config=config, workspace_path=workspace)
    
    def test_initialization(self, generator):
        """Test generator initialization."""
        assert generator.storage is not None
        assert generator.config is not None
    
    def test_default_config(self, workspace):
        """Test loading default configuration."""
        generator = ImageGenerator(workspace_path=workspace)
        
        assert "primary_provider" in generator.config
        assert "storage_dir" in generator.config
    
    @pytest.mark.asyncio
    async def test_generate_success(self, generator):
        """Test successful image generation."""
        fake_image = b"generated_image_data"
        
        # Mock provider
        mock_result = ImageGenerationResult(
            image_data=fake_image,
            provider="openai",
            model="dall-e-3",
            enhanced_prompt="Enhanced: a cat",
            metadata={"quality": "standard"}
        )
        
        with patch.object(generator, '_get_provider') as mock_get_provider:
            mock_provider = AsyncMock()
            mock_provider.validate_config = AsyncMock(return_value=(True, None))
            mock_provider.generate = AsyncMock(return_value=mock_result)
            mock_get_provider.return_value = mock_provider
            
            image_path, metadata = await generator.generate(
                prompt="a cat",
                size="1024x1024",
                quality="standard"
            )
            
            assert Path(image_path).exists()
            assert Path(image_path).read_bytes() == fake_image
            assert metadata.prompt == "a cat"
            assert metadata.provider == "openai"
    
    @pytest.mark.asyncio
    async def test_generate_with_specific_provider(self, generator):
        """Test generation with specific provider."""
        fake_image = b"stability_image"
        
        mock_result = ImageGenerationResult(
            image_data=fake_image,
            provider="stability_ai",
            model="sdxl",
            enhanced_prompt=None,
            metadata={}
        )
        
        with patch.object(generator, '_get_provider') as mock_get_provider:
            mock_provider = AsyncMock()
            mock_provider.validate_config = AsyncMock(return_value=(True, None))
            mock_provider.generate = AsyncMock(return_value=mock_result)
            mock_get_provider.return_value = mock_provider
            
            image_path, metadata = await generator.generate(
                prompt="a mountain",
                provider="stability_ai"
            )
            
            assert metadata.provider == "stability_ai"
            mock_get_provider.assert_called_with("stability_ai")
    
    @pytest.mark.asyncio
    async def test_generate_with_fallback(self, generator):
        """Test fallback to alternative provider."""
        fake_image = b"fallback_image"
        
        mock_result = ImageGenerationResult(
            image_data=fake_image,
            provider="stability_ai",
            model="sdxl",
            enhanced_prompt=None,
            metadata={}
        )
        
        with patch.object(generator, '_get_provider') as mock_get_provider:
            # First provider fails validation
            mock_provider1 = AsyncMock()
            mock_provider1.validate_config = AsyncMock(
                return_value=(False, "API key missing")
            )
            
            # Second provider succeeds
            mock_provider2 = AsyncMock()
            mock_provider2.validate_config = AsyncMock(return_value=(True, None))
            mock_provider2.generate = AsyncMock(return_value=mock_result)
            
            mock_get_provider.side_effect = [mock_provider1, mock_provider2]
            
            image_path, metadata = await generator.generate(prompt="test")
            
            # Should use fallback provider
            assert metadata.provider == "stability_ai"
    
    @pytest.mark.asyncio
    async def test_generate_all_providers_fail(self, generator):
        """Test error when all providers fail."""
        with patch.object(generator, '_get_provider') as mock_get_provider:
            mock_provider = AsyncMock()
            mock_provider.validate_config = AsyncMock(
                return_value=(False, "Not configured")
            )
            mock_get_provider.return_value = mock_provider
            
            with pytest.raises(RuntimeError, match="All image generation providers failed"):
                await generator.generate(prompt="test")
    
    @pytest.mark.asyncio
    async def test_generate_with_custom_output_path(self, generator, workspace):
        """Test generation with custom output path."""
        fake_image = b"custom_output_image"
        custom_path = "custom/output/my_image.png"
        
        mock_result = ImageGenerationResult(
            image_data=fake_image,
            provider="openai",
            model="dall-e-3",
            enhanced_prompt=None,
            metadata={}
        )
        
        with patch.object(generator, '_get_provider') as mock_get_provider:
            mock_provider = AsyncMock()
            mock_provider.validate_config = AsyncMock(return_value=(True, None))
            mock_provider.generate = AsyncMock(return_value=mock_result)
            mock_get_provider.return_value = mock_provider
            
            image_path, metadata = await generator.generate(
                prompt="test",
                output_path=custom_path
            )
            
            # Should be copied to custom location
            expected_path = os.path.join(workspace, custom_path)
            assert Path(expected_path).exists()
    
    @pytest.mark.asyncio
    async def test_validate_providers(self, generator):
        """Test provider validation."""
        # Create separate mocks for each provider
        mock_provider_openai = AsyncMock()
        mock_provider_openai.validate_config = AsyncMock(return_value=(True, None))
        
        mock_provider_stability = AsyncMock()
        mock_provider_stability.validate_config = AsyncMock(
            return_value=(False, "API key missing")
        )
        
        # Cache these in the provider dict to ensure they're used
        generator._providers["openai"] = mock_provider_openai
        generator._providers["stability_ai"] = mock_provider_stability
        
        results = await generator.validate_providers()
        
        assert results["openai"][0] is True
        assert results["stability_ai"][0] is False
        assert "API key" in results["stability_ai"][1]
    
    def test_list_available_providers(self, generator):
        """Test listing available provider types."""
        providers = generator.list_available_providers()
        
        assert "openai" in providers
        assert "stability_ai" in providers
        assert "ollama_assisted_openai" in providers
    
    def test_get_storage_stats(self, generator):
        """Test getting storage statistics."""
        stats = generator.get_storage_stats()
        
        assert "total_images" in stats
        assert "total_size_mb" in stats
        assert "storage_dir" in stats
    
    @pytest.mark.asyncio
    async def test_list_recent_images(self, generator):
        """Test listing recent images."""
        # Generate some images
        fake_image = b"test_image"
        mock_result = ImageGenerationResult(
            image_data=fake_image,
            provider="openai",
            model="dall-e-3",
            enhanced_prompt=None,
            metadata={}
        )
        
        with patch.object(generator, '_get_provider') as mock_get_provider:
            mock_provider = AsyncMock()
            mock_provider.validate_config = AsyncMock(return_value=(True, None))
            mock_provider.generate = AsyncMock(return_value=mock_result)
            mock_get_provider.return_value = mock_provider
            
            for i in range(3):
                await generator.generate(prompt=f"test {i}")
        
        recent = generator.list_recent_images(limit=2)
        
        assert len(recent) <= 2
        assert all(isinstance(img, ImageMetadata) for img in recent)
    
    def test_get_provider_config(self, generator):
        """Test getting provider configuration."""
        # Test regular provider
        openai_config = generator._get_provider_config("openai")
        assert "api_key" in openai_config
        
        # Test composite provider
        assisted_config = generator._get_provider_config("ollama_assisted_openai")
        assert "ollama" in assisted_config
        assert "openai" in assisted_config
        assert assisted_config["delegate_provider"] == "openai"