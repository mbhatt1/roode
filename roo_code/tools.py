"""Tool definitions and handling for agentic capabilities"""

from typing import Any, Callable, Dict, List, Optional, Union, TYPE_CHECKING
from pydantic import BaseModel, Field
from enum import Enum
import logging

if TYPE_CHECKING:
    from .builtin_tools.context import ToolContext
    from .builtin_tools.error_recovery import ErrorRecoveryManager
    from .builtin_tools.circuit_breaker import CircuitBreaker
    from .builtin_tools.repetition_detector import RepetitionDetector

logger = logging.getLogger(__name__)

# Tool aliases - maps legacy/incorrect tool names to their correct equivalents
TOOL_ALIASES = {
    'read_directory': 'list_files',
    'read_dir': 'list_files',
    'list_dir': 'list_files',
    'list_directory': 'list_files',
    'dir': 'list_files',
    'ls': 'list_files',
    # Add more aliases as needed
}


class ToolInputSchema(BaseModel):
    """Schema for tool input parameters"""
    type: str = "object"
    properties: Dict[str, Any]
    required: Optional[List[str]] = None


class ToolDefinition(BaseModel):
    """Definition of a tool that the AI can use"""
    name: str = Field(description="Name of the tool")
    description: str = Field(description="Description of what the tool does")
    input_schema: ToolInputSchema = Field(description="JSON schema for the tool's input")


class ToolUse(BaseModel):
    """Represents a tool use request from the AI"""
    id: str
    name: str
    input: Dict[str, Any]


class ToolResult(BaseModel):
    """Result of executing a tool"""
    tool_use_id: str
    content: Union[str, List[Dict[str, Any]]]
    is_error: bool = False


class Tool:
    """
    Base class for implementing tools
    
    Example:
        ```python
        class CalculatorTool(Tool):
            def __init__(self):
                super().__init__(
                    name="calculator",
                    description="Performs basic arithmetic operations",
                    input_schema=ToolInputSchema(
                        type="object",
                        properties={
                            "operation": {
                                "type": "string",
                                "enum": ["add", "subtract", "multiply", "divide"],
                                "description": "The operation to perform"
                            },
                            "a": {"type": "number", "description": "First number"},
                            "b": {"type": "number", "description": "Second number"}
                        },
                        required=["operation", "a", "b"]
                    )
                )
            
            async def execute(self, input_data: Dict[str, Any]) -> ToolResult:
                op = input_data["operation"]
                a = input_data["a"]
                b = input_data["b"]
                
                result = {
                    "add": a + b,
                    "subtract": a - b,
                    "multiply": a * b,
                    "divide": a / b if b != 0 else "Error: Division by zero"
                }[op]
                
                return ToolResult(
                    tool_use_id=self.current_use_id,
                    content=str(result),
                    is_error=isinstance(result, str) and result.startswith("Error")
                )
        ```
    """
    
    def __init__(
        self,
        name: str,
        description: str,
        input_schema: ToolInputSchema,
        context: Optional["ToolContext"] = None,
        enable_retry: bool = True,
        enable_circuit_breaker: bool = False,
        enable_repetition_detection: bool = True,
    ):
        self.name = name
        self.description = description
        self.input_schema = input_schema
        self.current_use_id: Optional[str] = None
        self.context = context
        self.enable_retry = enable_retry
        self.enable_circuit_breaker = enable_circuit_breaker
        self.enable_repetition_detection = enable_repetition_detection
        
        # Error recovery components (lazy-loaded)
        self._recovery_manager: Optional["ErrorRecoveryManager"] = None
        self._circuit_breaker: Optional["CircuitBreaker"] = None
        self._repetition_detector: Optional["RepetitionDetector"] = None
    
    def get_definition(self) -> ToolDefinition:
        """Get the tool definition for the AI"""
        return ToolDefinition(
            name=self.name,
            description=self.description,
            input_schema=self.input_schema,
        )
    
    def set_context(self, context: "ToolContext") -> None:
        """Set the execution context for this tool.
        
        Args:
            context: ToolContext to use for execution
        """
        self.context = context
    
    async def _request_approval(
        self,
        action: str,
        details: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Request approval from the user via context.
        
        Args:
            action: Description of the action requiring approval
            details: Additional details about the action
            
        Returns:
            True if approved or no context, False otherwise
        """
        if self.context:
            return await self.context.request_approval(action, details)
        return True  # Default to approved if no context
    
    async def _stream_result(self, message: str) -> None:
        """Stream a result message via context.
        
        Args:
            message: Message to stream
        """
        if self.context:
            await self.context.stream_result(message)
    
    async def _report_error(self, error: Exception) -> None:
        """Report an error via context.
        
        Args:
            error: Exception to report
        """
        if self.context:
            await self.context.report_error(error)
    
    def _check_file_edit_allowed(self, file_path: str) -> None:
        """Check if file editing is allowed via context.
        
        Args:
            file_path: Path to check
            
        Raises:
            FileRestrictionError: If file cannot be edited in current mode
        """
        if self.context:
            self.context.check_file_edit_allowed(file_path)
    
    async def _track_file_change(
        self,
        file_path: str,
        change_type: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Track a file change via context.
        
        Args:
            file_path: Path to the file that changed
            change_type: Type of change ("created", "modified", "deleted")
            metadata: Additional metadata
        """
        if self.context:
            await self.context.track_file_change(
                file_path,
                change_type,
                tool_name=self.name,
                metadata=metadata
            )
    
    def get_recovery_manager(self) -> Optional["ErrorRecoveryManager"]:
        """Get the error recovery manager for this tool.
        
        Returns:
            ErrorRecoveryManager instance or None if retry disabled
        """
        if not self.enable_retry:
            return None
        
        if self._recovery_manager is None:
            from .builtin_tools.error_recovery import get_recovery_manager
            self._recovery_manager = get_recovery_manager()
        
        return self._recovery_manager
    
    def get_circuit_breaker(self) -> Optional["CircuitBreaker"]:
        """Get the circuit breaker for this tool.
        
        Returns:
            CircuitBreaker instance or None if disabled
        """
        if not self.enable_circuit_breaker:
            return None
        
        if self._circuit_breaker is None:
            from .builtin_tools.circuit_breaker import get_circuit_breaker_registry
            registry = get_circuit_breaker_registry()
            # Use asyncio.create_task workaround for sync context
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Can't use await in sync context, create task
                    logger.warning("Circuit breaker creation in sync context, using defaults")
                    from .builtin_tools.circuit_breaker import CircuitBreaker
                    self._circuit_breaker = CircuitBreaker(name=self.name)
                else:
                    self._circuit_breaker = loop.run_until_complete(
                        registry.get_or_create(self.name)
                    )
            except RuntimeError:
                # No event loop, create breaker directly
                from .builtin_tools.circuit_breaker import CircuitBreaker
                self._circuit_breaker = CircuitBreaker(name=self.name)
        
        return self._circuit_breaker
    
    def get_repetition_detector(self) -> Optional["RepetitionDetector"]:
        """Get the repetition detector for this tool.
        
        Returns:
            RepetitionDetector instance or None if disabled
        """
        if not self.enable_repetition_detection:
            return None
        
        if self._repetition_detector is None:
            from .builtin_tools.repetition_detector import RepetitionDetector
            self._repetition_detector = RepetitionDetector()
        
        return self._repetition_detector
    
    async def execute_with_recovery(
        self,
        input_data: Dict[str, Any],
        timeout: Optional[float] = None
    ) -> ToolResult:
        """Execute the tool with error recovery if enabled.
        
        Args:
            input_data: Input parameters for the tool
            timeout: Optional timeout in seconds
            
        Returns:
            ToolResult: Result of the tool execution
        """
        logger.info(f"TOOL_RECOVERY: Executing '{self.name}' with recovery enabled (use_id: {self.current_use_id})")
        logger.debug(f"TOOL_RECOVERY: Input data: {input_data}")
        
        recovery_manager = self.get_recovery_manager()
        circuit_breaker = self.get_circuit_breaker()
        
        # Track metrics
        from .builtin_tools.error_metrics import get_error_metrics
        metrics = get_error_metrics()
        
        # Check for repetition before execution
        repetition_detector = self.get_repetition_detector()
        if repetition_detector:
            warning = repetition_detector.check_repetition(self.name, input_data)
            if warning and warning.severity == "critical":
                logger.warning(f"TOOL_RECOVERY: Repetition detected for '{self.name}': {warning.message}")
                return ToolResult(
                    tool_use_id=self.current_use_id or "unknown",
                    content=f"Tool repetition detected: {warning.message}\n\n{warning.suggestion}",
                    is_error=True
                )
        
        try:
            # Execute with circuit breaker if enabled
            if circuit_breaker:
                logger.debug(f"TOOL_RECOVERY: Using circuit breaker for '{self.name}'")
                if recovery_manager:
                    # Both circuit breaker and retry
                    logger.debug(f"TOOL_RECOVERY: Using both circuit breaker and retry for '{self.name}'")
                    async def execute_fn():
                        return await recovery_manager.execute_with_recovery(
                            self.execute,
                            input_data,
                            tool_name=self.name,
                            use_id=self.current_use_id or "unknown",
                            timeout=timeout
                        )
                    result = await circuit_breaker.call(execute_fn)
                else:
                    # Circuit breaker only
                    logger.debug(f"TOOL_RECOVERY: Using circuit breaker only for '{self.name}'")
                    result = await circuit_breaker.call(self.execute, input_data)
            
            # Execute with retry only
            elif recovery_manager:
                logger.debug(f"TOOL_RECOVERY: Using retry only for '{self.name}'")
                result = await recovery_manager.execute_with_recovery(
                    self.execute,
                    input_data,
                    tool_name=self.name,
                    use_id=self.current_use_id or "unknown",
                    timeout=timeout
                )
            
            # Execute without recovery
            else:
                logger.debug(f"TOOL_RECOVERY: Executing '{self.name}' without recovery")
                result = await self.execute(input_data)
            
            # Record successful call for repetition detection
            if repetition_detector:
                from .builtin_tools.repetition_detector import ToolCall
                from datetime import datetime
                
                call = ToolCall(
                    tool_name=self.name,
                    use_id=self.current_use_id or "unknown",
                    parameters=input_data,
                    timestamp=datetime.now(),
                    result_hash=str(hash(str(result.content)))
                )
                repetition_detector.record_call(call)
            
            # Record successful recovery if this wasn't the first attempt
            if recovery_manager and recovery_manager.get_error_count(self.name) > 0:
                metrics.record_recovery(self.name)
                logger.info(f"TOOL_RECOVERY: '{self.name}' recovered after errors")
            
            result_preview = str(result.content)[:200] + ("..." if len(str(result.content)) > 200 else "")
            logger.info(f"TOOL_RECOVERY: '{self.name}' completed successfully - is_error: {result.is_error}, length: {len(str(result.content))} chars")
            logger.debug(f"TOOL_RECOVERY: Result preview: {result_preview}")
            
            return result
            
        except Exception as e:
            # Record permanent failure
            metrics.record_permanent_failure(self.name)
            
            # Re-raise with context
            logger.error(f"TOOL_RECOVERY: Tool '{self.name}' failed permanently: {type(e).__name__}: {str(e)}")
            raise
    
    async def execute(self, input_data: Dict[str, Any]) -> ToolResult:
        """
        Execute the tool with the given input
        
        Args:
            input_data: Input parameters for the tool
            
        Returns:
            ToolResult: Result of the tool execution
        """
        raise NotImplementedError("Tool must implement execute method")


class FunctionTool(Tool):
    """
    Tool that wraps a Python function
    
    Example:
        ```python
        def get_weather(location: str, unit: str = "celsius") -> str:
            # Implementation here
            return f"Weather in {location}: 22°{unit[0].upper()}"
        
        weather_tool = FunctionTool(
            name="get_weather",
            description="Get the current weather for a location",
            function=get_weather,
            input_schema=ToolInputSchema(
                type="object",
                properties={
                    "location": {"type": "string", "description": "City name"},
                    "unit": {
                        "type": "string",
                        "enum": ["celsius", "fahrenheit"],
                        "description": "Temperature unit"
                    }
                },
                required=["location"]
            )
        )
        ```
    """
    
    def __init__(
        self,
        name: str,
        description: str,
        function: Callable,
        input_schema: ToolInputSchema,
    ):
        super().__init__(name, description, input_schema)
        self.function = function
    
    async def execute(self, input_data: Dict[str, Any]) -> ToolResult:
        """Execute the wrapped function"""
        logger.info(f"FUNCTION_TOOL: Executing function '{self.name}' (use_id: {self.current_use_id})")
        logger.debug(f"FUNCTION_TOOL: Input: {input_data}")
        
        try:
            # Handle both sync and async functions
            import inspect
            if inspect.iscoroutinefunction(self.function):
                logger.debug(f"FUNCTION_TOOL: Calling async function '{self.name}'")
                result = await self.function(**input_data)
            else:
                logger.debug(f"FUNCTION_TOOL: Calling sync function '{self.name}'")
                result = self.function(**input_data)
            
            result_str = str(result)
            logger.info(f"FUNCTION_TOOL: Function '{self.name}' succeeded - result length: {len(result_str)} chars")
            logger.debug(f"FUNCTION_TOOL: Result preview: {result_str[:200]}{'...' if len(result_str) > 200 else ''}")
            
            return ToolResult(
                tool_use_id=self.current_use_id,
                content=result_str,
                is_error=False,
            )
        except Exception as e:
            logger.error(f"FUNCTION_TOOL: Function '{self.name}' failed: {type(e).__name__}: {str(e)}")
            return ToolResult(
                tool_use_id=self.current_use_id,
                content=f"Error executing tool: {str(e)}",
                is_error=True,
            )


class ToolRegistry:
    """Registry for managing tools"""
    
    def __init__(self):
        self.tools: Dict[str, Tool] = {}
    
    def register(self, tool: Tool) -> None:
        """Register a tool"""
        self.tools[tool.name] = tool
    
    def get(self, name: str) -> Optional[Tool]:
        """Get a tool by name or alias"""
        # Check direct match first
        tool = self.tools.get(name)
        if tool is not None:
            return tool
        
        # Check if name is an alias
        actual_name = TOOL_ALIASES.get(name)
        if actual_name is not None:
            logger.info(f"REGISTRY: Tool alias used: '{name}' -> '{actual_name}'")
            resolved_tool = self.tools.get(actual_name)
            
            if resolved_tool:
                logger.debug(f"REGISTRY: Alias resolved to registered tool '{actual_name}'")
                return resolved_tool
            
            # If alias resolves but tool not registered, try to load from builtin registry
            logger.debug(f"REGISTRY: Tool '{actual_name}' not in registry, attempting to load from builtin tools")
            try:
                from .builtin_tools.registry import get_tool_by_name as get_builtin_tool
                builtin_tool = get_builtin_tool(actual_name, cwd=".")
                self.register(builtin_tool)
                logger.info(f"REGISTRY: Auto-registered builtin tool '{actual_name}' for alias '{name}'")
                return builtin_tool
            except (ImportError, ValueError) as e:
                logger.error(f"REGISTRY: Failed to load builtin tool '{actual_name}': {e}")
                return None
        
        return None
    
    def get_definitions(self) -> List[ToolDefinition]:
        """Get all tool definitions"""
        return [tool.get_definition() for tool in self.tools.values()]
    
    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """Get all registered tools in API format for Anthropic"""
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.input_schema.model_dump()
            }
            for tool in self.tools.values()
        ]
    
    async def execute(self, tool_use: ToolUse) -> ToolResult:
        """Execute a tool use request with error recovery if enabled"""
        logger.info(f"REGISTRY: Executing tool '{tool_use.name}' (use_id: {tool_use.id})")
        logger.debug(f"REGISTRY: Tool input: {tool_use.input}")
        
        tool = self.get(tool_use.name)
        if tool is None:
            logger.error(f"REGISTRY: Unknown tool requested: '{tool_use.name}'")
            
            # Generate suggestions for similar tools
            suggestions = []
            requested_name_lower = tool_use.name.lower()
            requested_parts = set(requested_name_lower.split('_'))
            
            # Find tools with overlapping words or concepts
            for tool_name in self.tools.keys():
                tool_name_lower = tool_name.lower()
                tool_parts = set(tool_name_lower.split('_'))
                
                # Check for common words between requested name and tool name
                common_parts = requested_parts & tool_parts
                if common_parts:
                    suggestions.append(tool_name)
                    continue
                
                # Check for semantic similarity (directory -> list, file, etc.)
                semantic_matches = {
                    'directory': ['list', 'file', 'files'],
                    'dir': ['list', 'file', 'files'],
                    'folder': ['list', 'file', 'files'],
                    'read': ['read', 'file', 'files', 'search'],
                    'write': ['write', 'file', 'apply', 'insert'],
                    'edit': ['write', 'apply', 'diff', 'insert'],
                    'run': ['execute', 'command'],
                    'exec': ['execute', 'command'],
                    'browse': ['browser'],
                    'search': ['search', 'file', 'files'],
                }
                
                # Check if any requested part has semantic matches in tool name
                for req_part in requested_parts:
                    if req_part in semantic_matches:
                        semantic_terms = semantic_matches[req_part]
                        if any(term in tool_parts for term in semantic_terms):
                            suggestions.append(tool_name)
                            break
            
            # Construct error message
            error_msg = f"Unknown tool: {tool_use.name}"
            if suggestions:
                # Limit to top 3 suggestions
                error_msg += f". Did you mean: {', '.join(suggestions[:3])}?"
            
            logger.error(f"REGISTRY: {error_msg}")
            return ToolResult(
                tool_use_id=tool_use.id,
                content=error_msg,
                is_error=True,
            )
        
        tool.current_use_id = tool_use.id
        
        # Use execute_with_recovery if retry is enabled
        if tool.enable_retry or tool.enable_circuit_breaker:
            logger.debug(f"REGISTRY: Tool '{tool_use.name}' has recovery enabled (retry: {tool.enable_retry}, circuit_breaker: {tool.enable_circuit_breaker})")
            return await tool.execute_with_recovery(tool_use.input)
        else:
            logger.debug(f"REGISTRY: Tool '{tool_use.name}' executing without recovery")
            result = await tool.execute(tool_use.input)
            logger.info(f"REGISTRY: Tool '{tool_use.name}' completed - is_error: {result.is_error}")
            return result