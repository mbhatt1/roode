# Amazon Bedrock Integration

This document provides instructions on how to use the Amazon Bedrock provider with Roo Code SDK.

## Overview

The Amazon Bedrock provider allows you to use Claude AI models hosted on AWS Bedrock with the Roo Code SDK. This integration supports all standard features, including:

- Text generation
- Tool calling
- Streaming responses
- Image handling

## Setup

### 1. Install Dependencies

Make sure you have the required dependencies:

```bash
pip install roo-code[all]
# Or if you only need Bedrock specifically:
pip install roo-code boto3
```

### 2. AWS Authentication

The Bedrock provider supports the following authentication methods:

#### Environment Variables

Set the following environment variables:

```bash
export AWS_REGION="us-east-1"  # Your desired AWS region
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
export AWS_SESSION_TOKEN="your-session-token"  # Optional
```

#### AWS Configuration Files

Alternatively, you can use AWS configuration files (`~/.aws/credentials` and `~/.aws/config`).

#### Explicit Credentials

You can also provide credentials directly to the `ProviderSettings` object.

### 3. Model IDs

Here are the Claude model IDs available on Bedrock:

| Model | Bedrock Model ID |
|-------|------------------|
| Claude 3 Opus | anthropic.claude-3-opus-20240229-v1:0 |
| Claude 3 Sonnet | anthropic.claude-3-sonnet-20240229-v1:0 |
| Claude 3 Haiku | anthropic.claude-3-haiku-20240307-v1:0 |
| Claude 3.5 Sonnet | anthropic.claude-3-5-sonnet-20240620-v1:0 |

## Basic Usage

Here's a simple example of using the Bedrock provider:

```python
from roo_code import RooClient, ProviderSettings, ApiProvider
from roo_code.types import MessageParam

async def main():
    # Create client with Bedrock provider
    client = RooClient(
        provider_settings=ProviderSettings(
            api_provider=ApiProvider.BEDROCK,
            api_model_id="anthropic.claude-3-sonnet-20240229-v1:0",
            aws_region="us-east-1",
            # AWS credentials will be loaded from environment variables or configuration files
        )
    )
    
    # Create a conversation
    messages = [
        MessageParam(role="user", content="Hello, who are you?")
    ]
    
    # Get response
    response = await client.create_message(
        system_prompt="You are a helpful assistant.",
        messages=messages,
    )
    
    # Process streaming response
    async for chunk in response.stream():
        if chunk.type == "content_block_delta" and hasattr(chunk.delta, "text"):
            print(chunk.delta.text, end="", flush=True)
```

## Important Considerations for Bedrock

The Bedrock provider has some important differences from other providers:

1. **Request Format**: Bedrock uses a different API format than direct Anthropic API calls. Our implementation handles these differences automatically.

2. **Streaming Responses**: Bedrock's streaming format differs from other providers. Our implementation normalizes these differences so your code works consistently.

3. **Tool Calling**: Bedrock supports tool calling with Claude models, but the request format is specific to Bedrock's implementation.

4. **Model IDs**: Remember to use the full Bedrock model IDs (e.g., `anthropic.claude-3-sonnet-20240229-v1:0`) rather than the shorter names used with direct Anthropic API.

5. **API Limits**: Be aware that AWS Bedrock may have different rate limits and quotas than direct provider APIs.

## Tool Calling

Amazon Bedrock supports tool calling with Claude models. Here's an example:

```python
# Define a tool
CALCULATOR_TOOL = {
    "name": "calculator",
    "description": "Perform mathematical calculations",
    "input_schema": {
        "type": "object",
        "properties": {
            "expression": {
                "type": "string",
                "description": "The mathematical expression to calculate"
            }
        },
        "required": ["expression"]
    }
}

# In your code:
response = await client.create_message(
    system_prompt="You are a helpful assistant with access to tools.",
    messages=[MessageParam(role="user", content="Calculate 15 * 24")],
    tools=[CALCULATOR_TOOL]
)

# Process streaming response with tool use
async for chunk in response.stream():
    if chunk.type == "content_block_start" and chunk.content_block.type == "tool_use":
        tool_name = chunk.content_block.name
        tool_input = chunk.content_block.input
        print(f"\n[Tool Use: {tool_name}]")
        print(f"Input: {tool_input}")
        
        # Execute the tool and send the result back to the model...
```

## Example Code

See `examples/bedrock_example.py` for a complete working example.

## Testing

You can run the tests for the Bedrock provider using:

```bash
pytest tests/test_bedrock_provider.py -v
```

Note that these tests use mocks and don't require actual AWS credentials.

## Troubleshooting

If you encounter issues:

1. Check your AWS credentials and permissions
2. Ensure you have enabled the required models in your AWS Bedrock console
3. Verify your region supports the model you're trying to use
4. Check for any service quotas that might be limiting your usage

### Common Errors

1. **ValidationException: Extra inputs are not permitted**
   - This usually means the request format doesn't match what Bedrock expects
   - Our implementation should handle this automatically, but if you see this error, please report it

2. **ResourceNotFoundException**
   - Ensure the model ID is correct and the model is enabled in your AWS account
   - Check that your region supports the requested model

3. **AccessDeniedException**
   - Verify your IAM permissions include `bedrock:InvokeModel` and `bedrock:InvokeModelWithResponseStream`
   - Check that your AWS credentials are valid and have the necessary permissions

4. **ThrottlingException**
   - You may be exceeding your AWS Bedrock quota
   - Consider implementing backoff/retry logic for production applications