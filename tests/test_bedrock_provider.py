"""Tests for Amazon Bedrock provider integration"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from roo_code import RooClient, ProviderSettings
from roo_code.types import ApiProvider, MessageParam
from roo_code.providers.bedrock import BedrockProvider
from roo_code.stream import ApiStream


class MockStreamResponse:
    """Mock for Bedrock streaming response"""
    
    def __init__(self, chunks):
        self.chunks = chunks
    
    def get(self, key, default=None):
        if key == 'body':
            return self
    
    def __iter__(self):
        for chunk in self.chunks:
            yield {'chunk': {'bytes': json.dumps(chunk).encode('utf-8')}}


@pytest.fixture
def mock_bedrock_client():
    """Create a mocked bedrock client"""
    with patch('boto3.Session') as mock_session:
        mock_client = MagicMock()
        mock_session.return_value.client.return_value = mock_client
        yield mock_client


@pytest.mark.asyncio
async def test_bedrock_provider_initialization():
    """Test initializing the Bedrock provider"""
    with patch('boto3.Session') as mock_session:
        provider = BedrockProvider(
            ProviderSettings(
                api_provider=ApiProvider.BEDROCK,
                api_model_id="anthropic.claude-3-sonnet-20240229-v1:0",
                aws_region="us-east-1",
                aws_access_key="test-key",
                aws_secret_key="test-secret",
            )
        )
        
        assert provider.settings.api_provider == ApiProvider.BEDROCK
        assert provider.settings.api_model_id == "anthropic.claude-3-sonnet-20240229-v1:0"
        assert mock_session.called


@pytest.mark.asyncio
async def test_bedrock_create_message(mock_bedrock_client):
    """Test creating a message with the Bedrock provider"""
    # Set up mock response data
    mock_response = MockStreamResponse([
        {"type": "message_start", "message": {"id": "msg_123", "role": "assistant"}},
        {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}},
        {"completion": "Hello, ", "type": "content_block_delta"},
        {"completion": "world!", "type": "content_block_delta"},
        {"type": "content_block_stop", "index": 0},
        {"type": "message_stop"}
    ])
    
    # Configure the mock to return our response
    mock_bedrock_client.invoke_model_with_response_stream.return_value = {'body': mock_response}
    
    # Create provider and test
    provider = BedrockProvider(
        ProviderSettings(
            api_provider=ApiProvider.BEDROCK,
            api_model_id="anthropic.claude-3-sonnet-20240229-v1:0",
            aws_region="us-east-1",
        )
    )
    
    # Call create_message
    response = await provider.create_message(
        system_prompt="You are a helpful assistant.",
        messages=[MessageParam(role="user", content="Hello!")]
    )
    
    assert isinstance(response, ApiStream)
    assert mock_bedrock_client.invoke_model_with_response_stream.called
    
    # Check the arguments passed to invoke_model_with_response_stream
    call_args = mock_bedrock_client.invoke_model_with_response_stream.call_args[1]
    assert call_args['modelId'] == "anthropic.claude-3-sonnet-20240229-v1:0"
    
    # Parse the request body to verify its structure
    body = json.loads(call_args['body'])
    assert body['system'] == "You are a helpful assistant."
    assert len(body['messages']) == 1
    assert body['messages'][0]['role'] == "user"
    assert body['messages'][0]['content'] == "Hello!"
    assert body['stream'] is True


@pytest.mark.asyncio
async def test_bedrock_tool_calling(mock_bedrock_client):
    """Test tool calling with Bedrock provider"""
    # Mock tool usage in response
    mock_response = MockStreamResponse([
        {"type": "message_start", "message": {"id": "msg_123", "role": "assistant"}},
        {
            "type": "content_block_start", 
            "index": 0, 
            "content_block": {
                "type": "tool_use",
                "id": "tool_123",
                "name": "calculator",
                "input": {"expression": "2+2"}
            }
        },
        {"type": "content_block_stop", "index": 0},
        {"type": "message_stop"}
    ])
    
    # Configure the mock
    mock_bedrock_client.invoke_model_with_response_stream.return_value = {'body': mock_response}
    
    # Create provider
    provider = BedrockProvider(
        ProviderSettings(
            api_provider=ApiProvider.BEDROCK,
            api_model_id="anthropic.claude-3-sonnet-20240229-v1:0",
            aws_region="us-east-1",
        )
    )
    
    # Tool definition
    calculator_tool = {
        "name": "calculator",
        "description": "Perform calculations",
        "input_schema": {
            "type": "object",
            "properties": {
                "expression": {"type": "string"}
            },
            "required": ["expression"]
        }
    }
    
    # Call create_message with tool
    response = await provider.create_message(
        system_prompt="You are a helpful assistant.",
        messages=[MessageParam(role="user", content="Calculate 2+2")],
        tools=[calculator_tool]
    )
    
    # Verify tool was included in request
    call_args = mock_bedrock_client.invoke_model_with_response_stream.call_args[1]
    body = json.loads(call_args['body'])
    assert 'tools' in body
    assert len(body['tools']) == 1
    assert body['tools'][0]['name'] == "calculator"
    
    # Process response to verify tool use is properly parsed
    chunks = []
    async for chunk in response.stream():
        chunks.append(chunk)
    
    # Find the tool use chunk
    tool_use_chunk = next((c for c in chunks if c.type == "content_block_start" and 
                          hasattr(c.content_block, 'type') and 
                          c.content_block.type == "tool_use"), None)
    
    assert tool_use_chunk is not None
    assert tool_use_chunk.content_block.name == "calculator"
    assert tool_use_chunk.content_block.input == {"expression": "2+2"}