"""
Example of using Amazon Bedrock with Roo Code SDK

This example demonstrates how to use Amazon Bedrock as a provider for the Roo Code SDK.
You'll need valid AWS credentials with Bedrock access to run this example.

Usage:
    python -m examples.bedrock_example
"""

import asyncio
import os
import logging
from typing import Dict, Any, List

from roo_code import RooClient, ProviderSettings, ApiProvider
from roo_code.types import MessageParam, TextContent

# Configure logging
logging.basicConfig(level=logging.INFO)

# Simple tool definition for demonstration
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


async def main():
    # Get API credentials from environment variables
    aws_region = os.getenv("AWS_REGION", "us-east-1")
    aws_access_key = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
    aws_session_token = os.getenv("AWS_SESSION_TOKEN")  # Optional
    
    if not aws_access_key or not aws_secret_key:
        # You can still use Bedrock if AWS credentials are configured in ~/.aws/credentials
        logging.warning("AWS credentials not found in environment variables")
        logging.info("Attempting to use credentials from AWS config files")
    
    # Create client with Bedrock provider settings
    client = RooClient(
        provider_settings=ProviderSettings(
            api_provider=ApiProvider.BEDROCK,
            api_model_id="anthropic.claude-3-sonnet-20240229-v1:0",  # Use the Bedrock model ID
            aws_region=aws_region,
            aws_access_key=aws_access_key,
            aws_secret_key=aws_secret_key,
            aws_session_token=aws_session_token,
        )
    )
    
    # Get model info
    model_id, model_info = client.get_model()
    print(f"Using model: {model_id}")
    print(f"Context window: {model_info.context_window}")
    print(f"Supports images: {model_info.supports_images}")
    
    # Example conversation without tools
    print("\n=== Basic conversation ===")
    messages = [
        MessageParam(role="user", content="What's the capital of France?")
    ]
    
    response = await client.create_message(
        system_prompt="You are a helpful assistant.",
        messages=messages,
    )
    
    # Process the streaming response
    print("\nResponse:")
    async for chunk in response.stream():
        if chunk.type == "content_block_delta" and hasattr(chunk.delta, "text"):
            print(chunk.delta.text, end="", flush=True)
    print("\n")
    
    # Example with tool use
    print("\n=== Tool use example ===")
    messages = [
        MessageParam(role="user", content="Calculate 15 * 24")
    ]
    
    response = await client.create_message(
        system_prompt="You are a helpful assistant with access to tools.",
        messages=messages,
        tools=[CALCULATOR_TOOL]
    )
    
    # Process the streaming response with tool use
    print("\nResponse with tools:")
    tool_use_found = False
    tool_name = ""
    tool_input = {}
    
    async for chunk in response.stream():
        # Track tool use
        if chunk.type == "content_block_start" and chunk.content_block.type == "tool_use":
            tool_use_found = True
            tool_name = chunk.content_block.name
            tool_input = chunk.content_block.input
            print(f"\n[Tool Use: {tool_name}]")
            print(f"Input: {tool_input}")
            
            # In a real application, you would execute the tool here
            # For this example, we'll simulate a calculator result
            if tool_name == "calculator" and "expression" in tool_input:
                try:
                    result = eval(tool_input["expression"])
                    print(f"Result: {result}")
                    
                    # In a real application, you would send this result back to the model
                    # through another message
                    tool_result_message = MessageParam(
                        role="user",
                        content=[
                            TextContent(
                                type="text",
                                text=f"Here's the result of the calculation: {result}"
                            )
                        ]
                    )
                    print("\nSending result back to model...")
                    
                    # This would be your next API call with the tool result
                    # For this example, we'll just show the structure
                    print(f"Would send: {tool_result_message}")
                except Exception as e:
                    print(f"Error calculating: {e}")
            
        elif chunk.type == "content_block_delta" and hasattr(chunk.delta, "text"):
            print(chunk.delta.text, end="", flush=True)
    
    print("\n\nDone!")


if __name__ == "__main__":
    asyncio.run(main())