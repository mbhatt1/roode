"""
Basic usage examples for Roo Code Python SDK
"""

import asyncio
from roo_code import RooClient, ProviderSettings, TextContent


async def basic_example():
    """Basic example of using the SDK"""
    print("="*50)
    print("Basic Example: Simple Message")
    print("="*50)
    
    # Initialize client
    client = RooClient(
        provider_settings=ProviderSettings(
            api_provider="anthropic",
            api_key="your-api-key-here",  # Replace with your actual API key
            api_model_id="claude-sonnet-4-5"
        )
    )
    
    # Create a simple message
    response = await client.create_message(
        system_prompt="You are a helpful coding assistant.",
        messages=[
            {"role": "user", "content": "Write a Python function to calculate fibonacci numbers"}
        ]
    )
    
    # Stream the response
    print("\nStreaming response:")
    async for chunk in response.stream():
        if chunk.type == "content_block_delta":
            print(chunk.delta.text, end="", flush=True)
    
    print("\n")


async def streaming_example():
    """Example of streaming responses"""
    print("="*50)
    print("Streaming Example")
    print("="*50)
    
    client = RooClient(
        provider_settings=ProviderSettings(
            api_provider="openai",
            api_key="your-openai-key",
            api_model_id="gpt-4"
        )
    )
    
    response = await client.create_message(
        system_prompt="You are a helpful assistant.",
        messages=[
            {"role": "user", "content": "Explain async/await in Python in 3 sentences"}
        ]
    )
    
    # Get complete text
    text = await response.get_text()
    print(f"Complete response:\n{text}\n")


async def multi_turn_conversation():
    """Example of multi-turn conversation"""
    print("="*50)
    print("Multi-turn Conversation Example")
    print("="*50)
    
    client = RooClient(
        provider_settings=ProviderSettings(
            api_provider="anthropic",
            api_key="your-api-key-here",
            api_model_id="claude-sonnet-4-5"
        )
    )
    
    # Build conversation history
    messages = [
        {"role": "user", "content": "What is Python?"},
    ]
    
    response1 = await client.create_message(
        system_prompt="You are a helpful assistant.",
        messages=messages
    )
    
    assistant_response = await response1.get_text()
    print(f"Assistant: {assistant_response[:200]}...\n")
    
    # Continue conversation
    messages.append({"role": "assistant", "content": assistant_response})
    messages.append({"role": "user", "content": "What are its main use cases?"})
    
    response2 = await client.create_message(
        system_prompt="You are a helpful assistant.",
        messages=messages
    )
    
    text = await response2.get_text()
    print(f"Assistant: {text}\n")


async def token_counting_example():
    """Example of token counting"""
    print("="*50)
    print("Token Counting Example")
    print("="*50)
    
    client = RooClient(
        provider_settings=ProviderSettings(
            api_provider="anthropic",
            api_key="your-api-key-here",
            api_model_id="claude-sonnet-4-5"
        )
    )
    
    # Count tokens
    content = [TextContent(type="text", text="Hello, how are you doing today?")]
    token_count = await client.count_tokens(content)
    
    print(f"Token count: {token_count}")
    print(f"Content: {content[0].text}\n")


async def model_info_example():
    """Example of getting model information"""
    print("="*50)
    print("Model Information Example")
    print("="*50)
    
    client = RooClient(
        provider_settings=ProviderSettings(
            api_provider="anthropic",
            api_key="your-api-key-here",
            api_model_id="claude-sonnet-4-5"
        )
    )
    
    model_id, model_info = client.get_model()
    
    print(f"Model ID: {model_id}")
    print(f"Context Window: {model_info.context_window:,} tokens")
    print(f"Supports Images: {model_info.supports_images}")
    print(f"Supports Prompt Cache: {model_info.supports_prompt_cache}")
    if model_info.input_price:
        print(f"Input Price: ${model_info.input_price}/1M tokens")
    if model_info.output_price:
        print(f"Output Price: ${model_info.output_price}/1M tokens")
    print()


async def multiple_providers_example():
    """Example of using different providers"""
    print("="*50)
    print("Multiple Providers Example")
    print("="*50)
    
    providers = [
        ("Anthropic", "anthropic", "claude-sonnet-4-5"),
        ("OpenAI", "openai", "gpt-4"),
        ("Gemini", "gemini", "gemini-1.5-pro"),
    ]
    
    for name, provider, model in providers:
        print(f"\n{name} ({model}):")
        try:
            client = RooClient(
                provider_settings=ProviderSettings(
                    api_provider=provider,
                    api_key=f"your-{provider}-key",
                    api_model_id=model
                )
            )
            
            model_id, model_info = client.get_model()
            print(f"  Context: {model_info.context_window:,} tokens")
            print(f"  Images: {model_info.supports_images}")
        except Exception as e:
            print(f"  Error: {e}")


async def main():
    """Run all examples"""
    await basic_example()
    await streaming_example()
    await multi_turn_conversation()
    await token_counting_example()
    await model_info_example()
    await multiple_providers_example()


if __name__ == "__main__":
    asyncio.run(main())