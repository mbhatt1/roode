"""Tests for image generation providers."""

import pytest
import base64
import json
from unittest.mock import AsyncMock, MagicMock, patch
from roo_code.builtin_tools.image_providers import (
    OllamaProvider,
    OpenAIProvider,
    StabilityAIProvider,
    OllamaAssistedProvider,
    ProviderFactory,
    ImageGenerationResult
)


class TestOllamaProvider:
    """Tests for Ollama provider."""
    
    @pytest.fixture
    def provider(self):
        """Create Ollama provider instance."""
        config = {
            "base_url": "http://localhost:11434",
            "model": "llama3.2-vision",
            "timeout": 30
        }
        return OllamaProvider(config)
    
    def test_provider_name(self, provider):
        """Test provider name."""
        assert provider.name == "ollama"
    
    @pytest.mark.asyncio
    async def test_generate_not_implemented(self, provider):
        """Test that generate raises NotImplementedError."""
        with pytest.raises(NotImplementedError):
            await provider.generate("test prompt")
    
    @pytest.mark.asyncio
    async def test_enhance_prompt_success(self, provider):
        """Test successful prompt enhancement."""
        mock_response = {
            "response": "A photorealistic image of a cat sitting on a windowsill, "
                       "natural lighting, 4k resolution, detailed fur texture"
        }
        
        with patch('aiohttp.ClientSession') as mock_session:
            mock_post = AsyncMock()
            mock_post.__aenter__.return_value.status = 200
            mock_post.__aenter__.return_value.json = AsyncMock(return_value=mock_response)
            mock_session.return_value.__aenter__.return_value.post = MagicMock(return_value=mock_post)
            
            enhanced = await provider.enhance_prompt("a cat")
            
            assert "photorealistic" in enhanced.lower()
            assert len(enhanced) > len("a cat")
    
    @pytest.mark.asyncio
    async def test_enhance_prompt_fallback(self, provider):
        """Test prompt enhancement fallback to original."""
        # Mock response with shorter or empty enhancement
        mock_response = {"response": ""}
        
        with patch('aiohttp.ClientSession') as mock_session:
            mock_post = AsyncMock()
            mock_post.__aenter__.return_value.status = 200
            mock_post.__aenter__.return_value.json = AsyncMock(return_value=mock_response)
            mock_session.return_value.__aenter__.return_value.post = MagicMock(return_value=mock_post)
            
            enhanced = await provider.enhance_prompt("a cat")
            
            # Should fallback to original
            assert enhanced == "a cat"
    
    @pytest.mark.asyncio
    async def test_enhance_prompt_error(self, provider):
        """Test prompt enhancement error handling."""
        with patch('aiohttp.ClientSession') as mock_session:
            mock_post = AsyncMock()
            mock_post.__aenter__.return_value.status = 500
            mock_post.__aenter__.return_value.text = AsyncMock(return_value="Server error")
            mock_session.return_value.__aenter__.return_value.post = MagicMock(return_value=mock_post)
            
            with pytest.raises(RuntimeError, match="Ollama API error"):
                await provider.enhance_prompt("test")
    
    @pytest.mark.asyncio
    async def test_describe_image_success(self, provider, tmp_path):
        """Test successful image description."""
        # Create a temporary image file
        image_path = tmp_path / "test.png"
        image_path.write_bytes(b"fake_image_data")
        
        mock_response = {
            "response": "This is a colorful landscape with mountains and a lake"
        }
        
        with patch('aiohttp.ClientSession') as mock_session:
            mock_post = AsyncMock()
            mock_post.__aenter__.return_value.status = 200
            mock_post.__aenter__.return_value.json = AsyncMock(return_value=mock_response)
            mock_session.return_value.__aenter__.return_value.post = MagicMock(return_value=mock_post)
            
            description = await provider.describe_image(str(image_path))
            
            assert "landscape" in description.lower()
            assert len(description) > 0
    
    @pytest.mark.asyncio
    async def test_validate_config_success(self, provider):
        """Test successful config validation."""
        mock_response = {
            "models": [
                {"name": "llama3.2-vision"},
                {"name": "llama3.2"}
            ]
        }
        
        with patch('aiohttp.ClientSession') as mock_session:
            mock_get = AsyncMock()
            mock_get.__aenter__.return_value.status = 200
            mock_get.__aenter__.return_value.json = AsyncMock(return_value=mock_response)
            mock_session.return_value.__aenter__.return_value.get = MagicMock(return_value=mock_get)
            
            is_valid, error = await provider.validate_config()
            
            assert is_valid
            assert error is None
    
    @pytest.mark.asyncio
    async def test_validate_config_model_not_found(self, provider):
        """Test validation failure when model not found."""
        mock_response = {
            "models": [
                {"name": "llama3.2"}
            ]
        }
        
        with patch('aiohttp.ClientSession') as mock_session:
            mock_get = AsyncMock()
            mock_get.__aenter__.return_value.status = 200
            mock_get.__aenter__.return_value.json = AsyncMock(return_value=mock_response)
            mock_session.return_value.__aenter__.return_value.get = MagicMock(return_value=mock_get)
            
            is_valid, error = await provider.validate_config()
            
            assert not is_valid
            assert "not found" in error


class TestOpenAIProvider:
    """Tests for OpenAI provider."""
    
    @pytest.fixture
    def provider(self):
        """Create OpenAI provider instance."""
        config = {
            "api_key": "sk-test-key-123",
            "model": "dall-e-3"
        }
        return OpenAIProvider(config)
    
    def test_provider_name(self, provider):
        """Test provider name."""
        assert provider.name == "openai"
    
    def test_missing_api_key(self):
        """Test initialization without API key."""
        config = {}
        with pytest.raises(ValueError, match="API key not provided"):
            OpenAIProvider(config)
    
    @pytest.mark.asyncio
    async def test_generate_success(self, provider):
        """Test successful image generation."""
        fake_image = b"fake_image_bytes_here"
        fake_b64 = base64.b64encode(fake_image).decode()
        
        mock_response = {
            "data": [{
                "b64_json": fake_b64,
                "revised_prompt": "Enhanced: a beautiful cat"
            }]
        }
        
        with patch('aiohttp.ClientSession') as mock_session:
            mock_post = AsyncMock()
            mock_post.__aenter__.return_value.status = 200
            mock_post.__aenter__.return_value.json = AsyncMock(return_value=mock_response)
            mock_session.return_value.__aenter__.return_value.post = MagicMock(return_value=mock_post)
            
            result = await provider.generate("a cat", size="1024x1024")
            
            assert isinstance(result, ImageGenerationResult)
            assert result.image_data == fake_image
            assert result.provider == "openai"
            assert result.model == "dall-e-3"
            assert result.enhanced_prompt == "Enhanced: a beautiful cat"
    
    @pytest.mark.asyncio
    async def test_generate_api_error(self, provider):
        """Test API error handling."""
        mock_response = {
            "error": {
                "message": "Invalid prompt"
            }
        }
        
        with patch('aiohttp.ClientSession') as mock_session:
            mock_post = AsyncMock()
            mock_post.__aenter__.return_value.status = 400
            mock_post.__aenter__.return_value.json = AsyncMock(return_value=mock_response)
            mock_session.return_value.__aenter__.return_value.post = MagicMock(return_value=mock_post)
            
            with pytest.raises(RuntimeError, match="Invalid prompt"):
                await provider.generate("bad prompt")
    
    @pytest.mark.asyncio
    async def test_validate_config_success(self, provider):
        """Test successful config validation."""
        with patch('aiohttp.ClientSession') as mock_session:
            mock_get = AsyncMock()
            mock_get.__aenter__.return_value.status = 200
            mock_session.return_value.__aenter__.return_value.get = MagicMock(return_value=mock_get)
            
            is_valid, error = await provider.validate_config()
            
            assert is_valid
            assert error is None
    
    @pytest.mark.asyncio
    async def test_validate_config_invalid_key(self, provider):
        """Test validation with invalid API key."""
        with patch('aiohttp.ClientSession') as mock_session:
            mock_get = AsyncMock()
            mock_get.__aenter__.return_value.status = 401
            mock_session.return_value.__aenter__.return_value.get = MagicMock(return_value=mock_get)
            
            is_valid, error = await provider.validate_config()
            
            assert not is_valid
            assert "Invalid" in error


class TestStabilityAIProvider:
    """Tests for Stability AI provider."""
    
    @pytest.fixture
    def provider(self):
        """Create Stability AI provider instance."""
        config = {
            "api_key": "sk-test-stability-key",
            "engine": "stable-diffusion-xl-1024-v1-0"
        }
        return StabilityAIProvider(config)
    
    def test_provider_name(self, provider):
        """Test provider name."""
        assert provider.name == "stability_ai"
    
    @pytest.mark.asyncio
    async def test_generate_success(self, provider):
        """Test successful image generation."""
        fake_image = b"fake_stability_image"
        fake_b64 = base64.b64encode(fake_image).decode()
        
        mock_response = {
            "artifacts": [{
                "base64": fake_b64,
                "seed": 12345
            }]
        }
        
        with patch('aiohttp.ClientSession') as mock_session:
            mock_post = AsyncMock()
            mock_post.__aenter__.return_value.status = 200
            mock_post.__aenter__.return_value.json = AsyncMock(return_value=mock_response)
            mock_session.return_value.__aenter__.return_value.post = MagicMock(return_value=mock_post)
            
            result = await provider.generate("a mountain", size="1024x1024")
            
            assert isinstance(result, ImageGenerationResult)
            assert result.image_data == fake_image
            assert result.provider == "stability_ai"
            assert result.metadata["seed"] == 12345
    
    @pytest.mark.asyncio
    async def test_generate_with_custom_params(self, provider):
        """Test generation with custom parameters."""
        fake_image = b"fake_image"
        fake_b64 = base64.b64encode(fake_image).decode()
        
        mock_response = {
            "artifacts": [{
                "base64": fake_b64,
                "seed": 67890
            }]
        }
        
        with patch('aiohttp.ClientSession') as mock_session:
            mock_post = AsyncMock()
            mock_post.__aenter__.return_value.status = 200
            mock_post.__aenter__.return_value.json = AsyncMock(return_value=mock_response)
            mock_session.return_value.__aenter__.return_value.post = MagicMock(return_value=mock_post)
            
            result = await provider.generate(
                "a sunset",
                size="512x512",
                quality="hd",
                steps=50,
                cfg_scale=8.5,
                style_preset="anime"
            )
            
            assert result.image_data == fake_image
            assert result.metadata["steps"] == 50
            assert result.metadata["cfg_scale"] == 8.5


class TestOllamaAssistedProvider:
    """Tests for Ollama-assisted provider."""
    
    @pytest.fixture
    def provider(self):
        """Create Ollama-assisted OpenAI provider."""
        config = {
            "ollama": {
                "base_url": "http://localhost:11434",
                "model": "llama3.2-vision"
            },
            "openai": {
                "api_key": "sk-test-key"
            },
            "delegate_provider": "openai"
        }
        return OllamaAssistedProvider(config)
    
    def test_provider_name(self, provider):
        """Test provider name."""
        assert provider.name == "ollama_assisted_openai"
    
    @pytest.mark.asyncio
    async def test_generate_with_enhancement(self, provider):
        """Test image generation with prompt enhancement."""
        # Mock the Ollama provider's enhance_prompt method
        enhanced_prompt = "A highly detailed, photorealistic cat"
        
        # Mock OpenAI generation
        fake_image = b"enhanced_cat_image"
        fake_b64 = base64.b64encode(fake_image).decode()
        mock_openai_response = {
            "data": [{
                "b64_json": fake_b64,
                "revised_prompt": "DALL-E: " + enhanced_prompt
            }]
        }
        
        with patch.object(provider.ollama, 'enhance_prompt', new_callable=AsyncMock) as mock_enhance:
            mock_enhance.return_value = enhanced_prompt
            
            with patch('aiohttp.ClientSession') as mock_session:
                mock_post = AsyncMock()
                mock_post.__aenter__.return_value.status = 200
                mock_post.__aenter__.return_value.json = AsyncMock(return_value=mock_openai_response)
                mock_session.return_value.__aenter__.return_value.post = MagicMock(return_value=mock_post)
                
                result = await provider.generate("a cat")
                
                assert result.image_data == fake_image
                assert result.provider == "ollama_assisted_openai"
                assert result.enhanced_prompt == enhanced_prompt
                assert result.metadata["ollama_enhanced"]
    
    @pytest.mark.asyncio
    async def test_generate_enhancement_failure_fallback(self, provider):
        """Test fallback when enhancement fails."""
        # Mock Ollama failure
        fake_image = b"fallback_image"
        fake_b64 = base64.b64encode(fake_image).decode()
        mock_openai_response = {
            "data": [{
                "b64_json": fake_b64
            }]
        }
        
        with patch('aiohttp.ClientSession') as mock_session:
            async def mock_post(*args, **kwargs):
                mock_response = AsyncMock()
                
                if "ollama" in str(args) or "localhost:11434" in str(args):
                    # Simulate Ollama failure
                    mock_response.status = 500
                    mock_response.text = AsyncMock(return_value="Ollama error")
                else:
                    mock_response.status = 200
                    mock_response.json = AsyncMock(return_value=mock_openai_response)
                
                return mock_response
            
            mock_post_obj = AsyncMock(side_effect=mock_post)
            mock_post_obj.__aenter__ = AsyncMock(side_effect=mock_post)
            mock_session.return_value.__aenter__.return_value.post = MagicMock(return_value=mock_post_obj)
            
            # Should still work with original prompt
            result = await provider.generate("a dog")
            
            assert result.image_data == fake_image
            # Enhanced prompt should be original since enhancement failed
            assert result.enhanced_prompt == "a dog"
    
    @pytest.mark.asyncio
    async def test_validate_config_both_valid(self, provider):
        """Test validation when both Ollama and delegate are valid."""
        # Mock both Ollama and OpenAI validation
        with patch.object(provider.ollama, 'validate_config', new_callable=AsyncMock) as mock_ollama_validate:
            with patch.object(provider.delegate, 'validate_config', new_callable=AsyncMock) as mock_delegate_validate:
                mock_ollama_validate.return_value = (True, None)
                mock_delegate_validate.return_value = (True, None)
                
                is_valid, error = await provider.validate_config()
                
                assert is_valid
                assert error is None
    
    @pytest.mark.asyncio
    async def test_validate_config_ollama_invalid(self, provider):
        """Test validation when Ollama is invalid."""
        with patch('aiohttp.ClientSession') as mock_session:
            mock_get = AsyncMock()
            mock_get.__aenter__.return_value.status = 500
            mock_session.return_value.__aenter__.return_value.get = MagicMock(return_value=mock_get)
            
            is_valid, error = await provider.validate_config()
            
            assert not is_valid
            assert "Ollama" in error


class TestProviderFactory:
    """Tests for provider factory."""
    
    def test_create_openai_provider(self):
        """Test creating OpenAI provider."""
        config = {"api_key": "sk-test"}
        provider = ProviderFactory.create_provider("openai", config)
        
        assert isinstance(provider, OpenAIProvider)
        assert provider.name == "openai"
    
    def test_create_stability_provider(self):
        """Test creating Stability AI provider."""
        config = {"api_key": "sk-test"}
        provider = ProviderFactory.create_provider("stability_ai", config)
        
        assert isinstance(provider, StabilityAIProvider)
        assert provider.name == "stability_ai"
    
    def test_create_ollama_assisted_openai(self):
        """Test creating Ollama-assisted OpenAI provider."""
        config = {
            "ollama": {"base_url": "http://localhost:11434"},
            "openai": {"api_key": "sk-test"}
        }
        provider = ProviderFactory.create_provider("ollama_assisted_openai", config)
        
        assert isinstance(provider, OllamaAssistedProvider)
        assert provider.name == "ollama_assisted_openai"
    
    def test_create_unknown_provider(self):
        """Test error on unknown provider."""
        with pytest.raises(ValueError, match="Unknown provider"):
            ProviderFactory.create_provider("unknown", {})
    
    def test_list_providers(self):
        """Test listing available providers."""
        providers = ProviderFactory.list_providers()
        
        assert "openai" in providers
        assert "stability_ai" in providers
        assert "ollama_assisted_openai" in providers
        assert "ollama_assisted_stability" in providers
        assert len(providers) >= 4