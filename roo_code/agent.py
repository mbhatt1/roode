"""Agentic capabilities for autonomous task execution"""

from typing import List, Optional, Dict, Any, Callable
from .client import RooClient
from .types import MessageParam, ApiHandlerCreateMessageMetadata, ToolUseContent, TextContent, ToolResultContent
from .tools import Tool, ToolRegistry, ToolUse, ToolResult, ToolDefinition
import json
import logging

# Import MCP manager for dynamic tool discovery
from .builtin_tools.mcp import get_mcp_manager


class Agent:
    """
    Autonomous agent that can use tools to accomplish tasks
    
    Example:
        ```python
        from roo_code import Agent, RooClient, ProviderSettings, FunctionTool, ToolInputSchema
        
        # Define tools
        def search_docs(query: str) -> str:
            return f"Documentation results for: {query}"
        
        search_tool = FunctionTool(
            name="search_docs",
            description="Search documentation",
            function=search_docs,
            input_schema=ToolInputSchema(
                type="object",
                properties={"query": {"type": "string"}},
                required=["query"]
            )
        )
        
        # Create agent
        client = RooClient(
            provider_settings=ProviderSettings(
                api_provider="anthropic",
                api_key="your-key",
                api_model_id="claude-sonnet-4-5"
            )
        )
        
        agent = Agent(client=client, tools=[search_tool])
        
        # Run agent
        result = await agent.run(
            "Find information about Python async/await"
        )
        print(result)
        ```
    """
    
    def __init__(
        self,
        client: RooClient,
        tools: Optional[List[Tool]] = None,
        system_prompt: Optional[str] = None,
        max_iterations: int = 10,
        metadata: Optional[ApiHandlerCreateMessageMetadata] = None,
        cwd: str = ".",
        load_builtin_tools: bool = True,
    ):
        """
        Initialize the agent
        
        Args:
            client: RooClient instance
            tools: List of additional tools to register (beyond builtin tools)
            system_prompt: System prompt for the agent
            max_iterations: Maximum number of iterations (prevent infinite loops)
            metadata: Optional metadata for tracking
            cwd: Current working directory for file operations
            load_builtin_tools: Whether to automatically load all builtin tools (default: True)
        """
        self.client = client
        self.tool_registry = ToolRegistry()
        self.max_iterations = max_iterations
        self.metadata = metadata
        self.logger = logging.getLogger(__name__)
        
        # Auto-load builtin tools if enabled
        if load_builtin_tools:
            from .builtin_tools.registry import get_all_builtin_tools
            builtin_tools = get_all_builtin_tools(cwd=cwd)
            logging.info(f"AGENT_INIT: Auto-loading {len(builtin_tools)} builtin tools")
            for tool in builtin_tools:
                self.tool_registry.register(tool)
        
        # Register additional custom tools
        if tools:
            logging.info(f"AGENT_INIT: Registering {len(tools)} additional custom tools")
            for tool in tools:
                self.tool_registry.register(tool)
        
        # Set system prompt
        self.system_prompt = system_prompt or self._default_system_prompt()
        
        # Conversation history
        self.messages: List[MessageParam] = []
    
    def _default_system_prompt(self) -> str:
        """Generate default system prompt with tool descriptions"""
        tool_descriptions = []
        for tool_def in self.tool_registry.get_definitions():
            tool_descriptions.append(
                f"- {tool_def.name}: {tool_def.description}"
            )
        
        tools_text = "\n".join(tool_descriptions) if tool_descriptions else "No tools available."
        
        return f"""You are a helpful AI assistant with access to tools.

Available tools:
{tools_text}

When you need to use a tool, respond with a JSON object in this format:
{{
    "tool": "tool_name",
    "input": {{
        "param1": "value1",
        "param2": "value2"
    }}
}}

After using a tool, you'll receive the result and can continue reasoning or use more tools.
When you have completed the task, provide your final answer without using any tools."""
    
    async def run(
        self,
        task: str,
        on_iteration: Optional[Callable[[int, str], None]] = None,
    ) -> str:
        """
        Run the agent on a task
        
        Args:
            task: The task to accomplish
            on_iteration: Optional callback called after each iteration with (iteration, response)
            
        Returns:
            str: Final response from the agent
        """
        # Start with the user's task
        self.messages = [
            MessageParam(role="user", content=task)
        ]
        
        for iteration in range(self.max_iterations):
            logging.info(f"AGENT_ITERATION: Starting iteration {iteration + 1}/{self.max_iterations}")
            
            # Get tool definitions from registry
            tool_definitions = self.tool_registry.get_tool_definitions() if hasattr(self.tool_registry, 'get_tool_definitions') else []
            
            # Get MCP tool definitions and add them dynamically
            try:
                mcp_manager = get_mcp_manager()
                mcp_tools = await mcp_manager.get_mcp_tool_definitions()
                # Combine built-in and MCP tools
                all_tools = tool_definitions + mcp_tools
                logging.info(f"AGENT_TOOLS: Sending {len(tool_definitions)} built-in tools + {len(mcp_tools)} MCP tools to API")
                logging.debug(f"AGENT_TOOLS: Tool names: {[t.get('name', 'unknown') for t in all_tools]}")
            except Exception as e:
                # If MCP fails, just use built-in tools
                logging.warning(f"AGENT_TOOLS: Failed to get MCP tools: {e}")
                all_tools = tool_definitions
            
            # Log message history being sent
            logging.info(f"AGENT_REQUEST: Sending {len(self.messages)} messages to API")
            for idx, msg in enumerate(self.messages):
                content_preview = ""
                if isinstance(msg.content, str):
                    content_preview = msg.content[:200] + ("..." if len(msg.content) > 200 else "")
                    logging.debug(f"AGENT_REQUEST: Message {idx} ({msg.role}): text content ({len(msg.content)} chars)")
                else:
                    block_types = [b.type for b in msg.content]
                    logging.debug(f"AGENT_REQUEST: Message {idx} ({msg.role}): {len(msg.content)} blocks - types: {block_types}")
                    for block_idx, block in enumerate(msg.content):
                        if hasattr(block, 'text'):
                            preview = block.text[:100] + ("..." if len(block.text) > 100 else "")
                            logging.debug(f"AGENT_REQUEST:   Block {block_idx}: text ({len(block.text)} chars)")
                        elif hasattr(block, 'name'):
                            logging.debug(f"AGENT_REQUEST:   Block {block_idx}: tool_use - {block.name}")
                        elif hasattr(block, 'tool_use_id'):
                            logging.debug(f"AGENT_REQUEST:   Block {block_idx}: tool_result for {block.tool_use_id}")
            
            # Get response from AI
            response = await self.client.create_message(
                system_prompt=self.system_prompt,
                messages=self.messages,
                metadata=self.metadata,
                tools=all_tools,
            )
            
            # Get the complete response message (this consumes the stream)
            final_message = await response.get_final_message()
            
            # Extract text from content blocks for callback
            text_parts = []
            for block in final_message.get("content", []):
                if isinstance(block, TextContent):
                    text_parts.append(block.text)
            response_text = "".join(text_parts)
            
            # Call iteration callback if provided
            if on_iteration:
                on_iteration(iteration, response_text)
            
            # Add assistant's response to history with full content blocks
            # Anthropic API requires all messages to have non-empty content
            # When tool use is present, we need to include both text and tool_use blocks
            content_blocks = final_message.get("content", [])
            
            if content_blocks:
                # If we have content blocks, add them as-is (includes text and tool_use)
                self.messages.append(
                    MessageParam(role="assistant", content=content_blocks)
                )
            elif response_text.strip():
                # Fallback: if no content blocks but we have text, add as string
                self.messages.append(
                    MessageParam(role="assistant", content=response_text)
                )
            
            # Check if the response contains tool uses
            tool_uses = self._extract_tool_uses(response)
            
            if not tool_uses:
                # No tool use, this is the final answer
                logging.info(f"AGENT_COMPLETE: No tool use detected, returning final answer ({len(response_text)} chars)")
                return response_text
            
            # Execute ALL tool uses and collect results
            logging.info(f"TOOL_CALL: LLM requested {len(tool_uses)} tool(s)")
            tool_result_blocks = []
            
            for tool_use in tool_uses:
                # Log tool call details
                logging.info(f"TOOL_CALL: Executing tool '{tool_use.name}' (id: {tool_use.id})")
                logging.debug(f"TOOL_CALL: Parameters: {tool_use.input}")
                
                # Execute the tool
                tool_result = await self.tool_registry.execute(tool_use)
                
                # Log tool result
                result_preview = str(tool_result.content)[:200] + ("..." if len(str(tool_result.content)) > 200 else "")
                logging.info(f"TOOL_RESULT: Tool '{tool_use.name}' completed - is_error: {tool_result.is_error}, result length: {len(str(tool_result.content))} chars")
                logging.debug(f"TOOL_RESULT: Preview: {result_preview}")
                
                # Create tool result block
                tool_result_block = ToolResultContent(
                    type="tool_result",
                    tool_use_id=tool_use.id,
                    content=tool_result.content,
                    is_error=tool_result.is_error
                )
                tool_result_blocks.append(tool_result_block)
            
            # Add ALL tool results to conversation in a single message
            # Anthropic API requires tool_result blocks after tool_use blocks
            logging.debug(f"TOOL_RESULT: Adding {len(tool_result_blocks)} tool_result block(s) to message history")
            self.messages.append(
                MessageParam(role="user", content=tool_result_blocks)
            )
        
        # Max iterations reached
        return "Maximum iterations reached. Task may be incomplete."
    
    def _extract_tool_uses(
        self, response: "ApiStream"
    ) -> List[ToolUse]:
        """Extract all tool uses from response content blocks."""
        try:
            # Get tool use blocks from the response
            tool_uses = response.get_tool_uses()
            
            logging.debug(f"TOOL_EXTRACTION: Found {len(tool_uses) if tool_uses else 0} tool use blocks in response")
            
            if not tool_uses:
                return []
            
            # Convert all tool uses to ToolUse objects
            result = []
            for tool_use in tool_uses:
                logging.debug(f"TOOL_EXTRACTION: Extracted tool_use: {tool_use.name} (id: {tool_use.id})")
                result.append(ToolUse(
                    id=tool_use.id,
                    name=tool_use.name,
                    input=tool_use.input,
                ))
            
            return result
        except Exception as e:
            self.logger.error(f"TOOL_EXTRACTION: Error extracting tool uses: {e}")
            return []
    
    def add_tool(self, tool: Tool) -> None:
        """Add a tool to the agent"""
        self.tool_registry.register(tool)
    
    def get_conversation_history(self) -> List[MessageParam]:
        """Get the conversation history"""
        return self.messages
    
    def clear_history(self) -> None:
        """Clear the conversation history"""
        self.messages = []


class ReActAgent(Agent):
    """
    Agent using ReAct (Reasoning + Acting) pattern
    Explicitly structures thinking in Thought -> Action -> Observation loops
    
    Example:
        ```python
        agent = ReActAgent(client=client, tools=[search_tool, calculator_tool])
        result = await agent.run("Calculate the square root of 144 then search for its significance")
        ```
    """
    
    def _default_system_prompt(self) -> str:
        """ReAct-specific system prompt"""
        tool_descriptions = []
        for tool_def in self.tool_registry.get_definitions():
            tool_descriptions.append(
                f"- {tool_def.name}: {tool_def.description}"
            )
        
        tools_text = "\n".join(tool_descriptions) if tool_descriptions else "No tools available."
        
        return f"""You are a helpful AI assistant using the ReAct (Reasoning + Acting) framework.

Available tools:
{tools_text}

For each step, use this format:
Thought: [Your reasoning about what to do next]
Action: [JSON object with tool use]
{{
    "tool": "tool_name",
    "input": {{"param": "value"}}
}}

After receiving an Observation (tool result), continue with:
Thought: [Your reasoning about the result]
Action: [Next tool use] OR Answer: [Final answer]

When you're done, provide your final answer as:
Answer: [Your final response]"""