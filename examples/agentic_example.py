"""
Example demonstrating agentic capabilities of Roo Code Python SDK
"""

import asyncio
from roo_code import (
    Agent,
    ReActAgent,
    RooClient,
    ProviderSettings,
    FunctionTool,
    ToolInputSchema,
)


# Define tools for the agent
def calculator(operation: str, a: float, b: float) -> str:
    """Perform basic arithmetic operations"""
    operations = {
        "add": lambda x, y: x + y,
        "subtract": lambda x, y: x - y,
        "multiply": lambda x, y: x * y,
        "divide": lambda x, y: x / y if y != 0 else "Error: Division by zero",
    }
    
    if operation not in operations:
        return f"Error: Unknown operation '{operation}'"
    
    result = operations[operation](a, b)
    return str(result)


def get_current_weather(location: str, unit: str = "celsius") -> str:
    """Get current weather (mock implementation)"""
    # In a real implementation, this would call a weather API
    return f"The weather in {location} is 22°{unit[0].upper()}, partly cloudy"


def search_knowledge_base(query: str) -> str:
    """Search a knowledge base (mock implementation)"""
    # In a real implementation, this would search a vector database
    knowledge = {
        "python": "Python is a high-level programming language known for its simplicity and readability.",
        "async": "Async/await in Python allows for concurrent execution of code without blocking.",
        "sdk": "An SDK (Software Development Kit) is a collection of tools for building applications.",
    }
    
    for key, value in knowledge.items():
        if key in query.lower():
            return value
    
    return "No information found in knowledge base."


async def main():
    # Initialize client
    client = RooClient(
        provider_settings=ProviderSettings(
            api_provider="anthropic",
            api_key="your-api-key-here",  # Replace with your actual API key
            api_model_id="claude-sonnet-4-5"
        )
    )
    
    # Create tools
    calc_tool = FunctionTool(
        name="calculator",
        description="Performs basic arithmetic operations (add, subtract, multiply, divide)",
        function=calculator,
        input_schema=ToolInputSchema(
            type="object",
            properties={
                "operation": {
                    "type": "string",
                    "enum": ["add", "subtract", "multiply", "divide"],
                    "description": "The operation to perform"
                },
                "a": {"type": "number", "description": "First number"},
                "b": {"type": "number", "description": "Second number"},
            },
            required=["operation", "a", "b"],
        ),
    )
    
    weather_tool = FunctionTool(
        name="get_weather",
        description="Get the current weather for a location",
        function=get_current_weather,
        input_schema=ToolInputSchema(
            type="object",
            properties={
                "location": {
                    "type": "string",
                    "description": "City name or location"
                },
                "unit": {
                    "type": "string",
                    "enum": ["celsius", "fahrenheit"],
                    "description": "Temperature unit (default: celsius)"
                },
            },
            required=["location"],
        ),
    )
    
    search_tool = FunctionTool(
        name="search_knowledge",
        description="Search the knowledge base for information",
        function=search_knowledge_base,
        input_schema=ToolInputSchema(
            type="object",
            properties={
                "query": {
                    "type": "string",
                    "description": "Search query"
                },
            },
            required=["query"],
        ),
    )
    
    # Example 1: Basic Agent
    print("="*50)
    print("Example 1: Basic Agent")
    print("="*50)
    
    agent = Agent(
        client=client,
        tools=[calc_tool, weather_tool],
        max_iterations=5,
    )
    
    def on_iteration(iteration: int, response: str):
        print(f"\nIteration {iteration + 1}:")
        print(response[:200] + "..." if len(response) > 200 else response)
    
    result = await agent.run(
        "What is 15 multiplied by 7, and what's the weather in San Francisco?",
        on_iteration=on_iteration,
    )
    
    print(f"\nFinal Result: {result}")
    
    # Example 2: ReAct Agent
    print("\n" + "="*50)
    print("Example 2: ReAct Agent")
    print("="*50)
    
    react_agent = ReActAgent(
        client=client,
        tools=[calc_tool, search_tool],
        max_iterations=5,
    )
    
    result = await react_agent.run(
        "Calculate 100 divided by 5, then search for information about Python",
        on_iteration=on_iteration,
    )
    
    print(f"\nFinal Result: {result}")
    
    # Example 3: Custom Tool
    print("\n" + "="*50)
    print("Example 3: Agent with Custom Async Tool")
    print("="*50)
    
    async def fetch_data(url: str) -> str:
        """Async function to fetch data"""
        # In a real implementation, this would use httpx or aiohttp
        await asyncio.sleep(0.1)  # Simulate async operation
        return f"Data fetched from {url}: [mock data]"
    
    fetch_tool = FunctionTool(
        name="fetch_url",
        description="Fetch data from a URL",
        function=fetch_data,
        input_schema=ToolInputSchema(
            type="object",
            properties={
                "url": {"type": "string", "description": "URL to fetch"},
            },
            required=["url"],
        ),
    )
    
    async_agent = Agent(
        client=client,
        tools=[fetch_tool, search_tool],
        max_iterations=5,
    )
    
    result = await async_agent.run(
        "Fetch data from https://api.example.com/data and summarize what an SDK is",
        on_iteration=on_iteration,
    )
    
    print(f"\nFinal Result: {result}")


if __name__ == "__main__":
    asyncio.run(main())