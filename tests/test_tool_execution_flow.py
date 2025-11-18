"""
Test to diagnose why tools aren't being executed despite proper parsing.

This test traces the complete flow from agent setup through tool execution.
"""

import pytest
from typing import Dict, Any
from roo_code.agent import Agent
from roo_code.client import RooClient
from roo_code.types import ProviderSettings, ApiProvider
from roo_code.tools import FunctionTool, ToolInputSchema, ToolResult


class TestToolExecutionFlow:
    """Test the complete tool execution flow"""

    def test_tool_definitions_available(self):
        """Test that tools are properly registered in the agent's registry"""
        # Create a simple test tool
        def test_function(message: str) -> str:
            return f"Processed: {message}"
        
        tool = FunctionTool(
            name="test_tool",
            description="A test tool",
            function=test_function,
            input_schema=ToolInputSchema(
                type="object",
                properties={"message": {"type": "string"}},
                required=["message"]
            )
        )
        
        # Create client (with dummy settings, won't actually call API in this test)
        client = RooClient(
            provider_settings=ProviderSettings(
                api_provider=ApiProvider.ANTHROPIC,
                api_key="test-key",
                api_model_id="claude-sonnet-4-5"
            )
        )
        
        # Create agent with tool
        agent = Agent(client=client, tools=[tool])
        
        # Check tool is registered
        assert agent.tool_registry.get("test_tool") is not None
        
        # Check tool definitions are available
        definitions = agent.tool_registry.get_definitions()
        assert len(definitions) == 1
        assert definitions[0].name == "test_tool"
        print(f"✓ Tool registered: {definitions[0].name}")
        print(f"✓ Tool description: {definitions[0].description}")
    
    def test_client_create_message_signature(self):
        """Test what parameters client.create_message accepts"""
        import inspect
        from roo_code.client import RooClient
        
        sig = inspect.signature(RooClient.create_message)
        params = list(sig.parameters.keys())
        
        print(f"\nRooClient.create_message parameters: {params}")
        
        # Check if 'tools' parameter exists
        has_tools_param = 'tools' in params
        print(f"Has 'tools' parameter: {has_tools_param}")
        
        if not has_tools_param:
            print("❌ ISSUE FOUND: client.create_message does NOT accept a 'tools' parameter!")
            print("   This means the agent cannot pass tool definitions to the API.")
    
    def test_provider_create_message_signature(self):
        """Test what parameters provider.create_message accepts"""
        import inspect
        from roo_code.providers.anthropic import AnthropicProvider
        
        sig = inspect.signature(AnthropicProvider.create_message)
        params = list(sig.parameters.keys())
        
        print(f"\nAnthropicProvider.create_message parameters: {params}")
        
        # Check if 'tools' parameter exists
        has_tools_param = 'tools' in params
        print(f"Has 'tools' parameter: {has_tools_param}")
        
        if not has_tools_param:
            print("❌ ISSUE FOUND: provider.create_message does NOT accept a 'tools' parameter!")
            print("   This means tools are never sent to the Anthropic API.")
    
    def test_agent_run_flow(self):
        """Test the agent.run() flow to see where tools should be passed"""
        import inspect
        from roo_code.agent import Agent
        
        # Get the source of the run method
        source = inspect.getsource(Agent.run)
        
        print("\n=== Analyzing Agent.run() method ===")
        
        # Check if tools are mentioned anywhere in the run method
        if "tools" in source.lower():
            print("✓ The word 'tools' appears in agent.run()")
        else:
            print("❌ The word 'tools' does NOT appear in agent.run()")
        
        # Check if tool_registry is used to get definitions
        if "tool_registry.get_definitions" in source:
            print("✓ agent.run() gets tool definitions from registry")
        else:
            print("❌ agent.run() does NOT get tool definitions from registry")
        
        # Check if tools are passed to create_message
        if "create_message" in source:
            print("✓ agent.run() calls create_message")
            # Check what parameters are passed
            import re
            create_msg_calls = re.findall(r'create_message\((.*?)\)', source, re.DOTALL)
            if create_msg_calls:
                params = create_msg_calls[0]
                print(f"  Parameters passed: {params[:100]}...")
                if "tool" in params.lower():
                    print("  ✓ Tools are passed to create_message")
                else:
                    print("  ❌ Tools are NOT passed to create_message")
    
    def test_anthropic_api_call(self):
        """Test what the Anthropic provider actually sends to the API"""
        import inspect
        from roo_code.providers.anthropic import AnthropicProvider
        
        # Get the source of create_message
        source = inspect.getsource(AnthropicProvider.create_message)
        
        print("\n=== Analyzing Anthropic API Call ===")
        
        # Look for the actual API call
        if "client.messages.create" in source:
            print("✓ Found API call: client.messages.create")
            
            # Extract the parameters being passed
            import re
            api_calls = re.findall(r'client\.messages\.create\((.*?)\)', source, re.DOTALL)
            if api_calls:
                params_str = api_calls[0]
                print(f"  Parameters in API call:")
                
                # Check for each possible parameter
                for param in ["model", "max_tokens", "system", "messages", "stream", "tools"]:
                    if param in params_str:
                        print(f"    ✓ {param}")
                    else:
                        print(f"    ❌ {param} (missing)")
                
                if "tools" not in params_str:
                    print("\n❌ CRITICAL ISSUE: 'tools' parameter is NOT being passed to Anthropic API!")
                    print("   Without this, the LLM doesn't know about available tools.")
                    print("   Therefore, it will never generate tool_use blocks.")


if __name__ == "__main__":
    # Run tests individually to see detailed output
    test = TestToolExecutionFlow()
    
    print("=" * 70)
    print("DIAGNOSTIC TEST: Why Tools Aren't Executing")
    print("=" * 70)
    
    print("\n[1/5] Testing tool registration...")
    test.test_tool_definitions_available()
    
    print("\n[2/5] Testing RooClient signature...")
    test.test_client_create_message_signature()
    
    print("\n[3/5] Testing Provider signature...")
    test.test_provider_create_message_signature()
    
    print("\n[4/5] Testing Agent.run() flow...")
    test.test_agent_run_flow()
    
    print("\n[5/5] Testing Anthropic API call...")
    test.test_anthropic_api_call()
    
    print("\n" + "=" * 70)
    print("DIAGNOSTIC COMPLETE")
    print("=" * 70)