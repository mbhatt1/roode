"""Workflow tools for agent interaction and task management."""

from typing import Any, Dict, List, Optional, TYPE_CHECKING
from ..tools import Tool, ToolInputSchema, ToolResult
from ..client import RooClient
from ..types import MessageParam
import logging

logger = logging.getLogger(__name__)

# Use TYPE_CHECKING to avoid circular imports
if TYPE_CHECKING:
    from ..agent import Agent


class AskFollowupQuestionTool(Tool):
    """Tool for asking the user follow-up questions or querying AI."""
    
    def __init__(self, client: Optional[RooClient] = None):
        self.logger = logging.getLogger(__name__)
        super().__init__(
            name="ask_followup_question",
            description=(
                "Ask a question to gather additional information needed to complete the task. "
                "The question can be directed to the user or to an AI assistant. "
                "Use when you need clarification, research, or more details to proceed effectively."
            ),
            input_schema=ToolInputSchema(
                type="object",
                properties={
                    "question": {
                        "type": "string",
                        "description": "A clear, specific question addressing the information needed"
                    },
                    "suggestions": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "2-4 suggested answers when asking the user. Suggestions must be complete, actionable "
                            "answers without placeholders."
                        )
                    },
                    "ask_ai": {
                        "type": "boolean",
                        "description": "If true, ask AI instead of user. Default is false (ask user)."
                    },
                    "context": {
                        "type": "string",
                        "description": "Optional additional context for the AI query"
                    },
                    "use_tools": {
                        "type": "boolean",
                        "description": "If true and ask_ai is true, AI will have access to tools. Default is false."
                    },
                    "max_iterations": {
                        "type": "integer",
                        "description": "Maximum number of tool iterations for AI (default: 5)",
                        "minimum": 1,
                        "maximum": 20
                    }
                },
                required=["question"]
            )
        )
        self.client = client
    
    async def execute(self, input_data: Dict[str, Any]) -> ToolResult:
        """Ask a follow-up question to user or AI."""
        try:
            # Log complete input data for debugging
            self.logger.info(f"AskFollowupQuestionTool: Received input: {input_data}")
            
            question = input_data["question"]
            ask_ai = input_data.get("ask_ai", False)
            
            if ask_ai:
                # Query AI instead of user
                self.logger.info(f"AskFollowupQuestionTool: Querying AI with question: {question[:100]}...")
                return await self._query_ai(input_data)
            else:
                # Format question for user
                self.logger.info(f"AskFollowupQuestionTool: Asking user question: {question[:100]}...")
                suggestions = input_data.get("suggestions", [])
                if not suggestions:
                    error_msg = "Error: When asking the user, you must provide suggested answers"
                    self.logger.error(f"AskFollowupQuestionTool: {error_msg}")
                    return ToolResult(
                        tool_use_id=self.current_use_id,
                        content=error_msg,
                        is_error=True
                    )
                
                self.logger.info(f"AskFollowupQuestionTool: Using {len(suggestions)} suggestions")
                
                # Format the question with suggestions
                content_parts = [f"Question: {question}"]
                
                content_parts.append("\nSuggested answers:")
                for i, suggestion in enumerate(suggestions, 1):
                    content_parts.append(f"{i}. {suggestion}")
                
                content = "\n".join(content_parts)
                
                return ToolResult(
                    tool_use_id=self.current_use_id,
                    content=content,
                    is_error=False
                )
            
        except Exception as e:
            self.logger.error(f"AskFollowupQuestionTool: Error formatting question: {type(e).__name__}: {str(e)}", exc_info=True)
            return ToolResult(
                tool_use_id=self.current_use_id,
                content=f"Error formatting question: {type(e).__name__}: {str(e)}",
                is_error=True,
                exception=e
            )
    
    async def _query_ai(self, input_data: Dict[str, Any]) -> ToolResult:
        """Query AI for an answer."""
        try:
            question = input_data["question"]
            context = input_data.get("context", "")
            use_tools = input_data.get("use_tools", False)
            max_iterations = input_data.get("max_iterations", 5)
            
            logger.info(f"Querying AI: {question[:100]}...")
            
            # Use the current client if none provided
            if self.client is None:
                error_msg = "Error: No AI client available for querying. The ask_followup_question tool needs access to an AI client when ask_ai=true."
                self.logger.error(f"AskFollowupQuestionTool: {error_msg}")
                return ToolResult(
                    tool_use_id=self.current_use_id,
                    content=error_msg,
                    is_error=True
                )
            
            if use_tools:
                # Import Agent here to avoid circular import
                from ..agent import Agent
                
                # Create system prompt for the sub-agent
                system_prompt = (
                    "You are a research assistant with access to tools. Your job is to answer "
                    "questions and complete tasks using the available tools. Be thorough in your "
                    "research and provide detailed, accurate answers. Use tools as needed to "
                    "gather information, access files, query databases, or perform other tasks."
                )
                
                if context:
                    system_prompt += f"\n\nAdditional context: {context}"
                
                # Create a sub-agent
                self.logger.info(f"AskFollowupQuestionTool: Creating sub-agent with max {max_iterations} iterations")
                agent = Agent(
                    client=self.client,
                    system_prompt=system_prompt,
                    max_iterations=max_iterations
                )
                
                # Run the agent to get the answer
                self.logger.info(f"AskFollowupQuestionTool: Running sub-agent to answer: {question[:100]}...")
                
                try:
                    answer = await agent.run(task=question)
                    
                    self.logger.info(f"AskFollowupQuestionTool: AI assistant query completed successfully, answer length: {len(answer)} chars")
                    
                    return ToolResult(
                        tool_use_id=self.current_use_id,
                        content=f"AI Response:\n\n{answer}",
                        is_error=False
                    )
                    
                except Exception as e:
                    self.logger.error(f"AskFollowupQuestionTool: Error running AI assistant: {type(e).__name__}: {str(e)}", exc_info=True)
                    return ToolResult(
                        tool_use_id=self.current_use_id,
                        content=(
                            f"Error running AI assistant query: {type(e).__name__}: {str(e)}\n\n"
                            f"The AI assistant encountered an error while trying to answer: {question}"
                        ),
                        is_error=True,
                        exception=e
                    )
            else:
                # Simple AI query without tools
                # Create system prompt
                system_prompt = (
                    "You are a helpful AI assistant. Answer questions clearly and concisely. "
                    "If you don't know something, say so rather than guessing."
                )
                
                if context:
                    system_prompt += f"\n\nContext: {context}"
                
                # Create messages
                messages = [
                    MessageParam(role="user", content=question)
                ]
                
                self.logger.info(f"AskFollowupQuestionTool: Making API call to answer question with model: {self.client.provider_settings.api_model_id}")
                
                # Get response from AI (no tools)
                try:
                    response = await self.client.create_message(
                        system_prompt=system_prompt,
                        messages=messages,
                        # No tools parameter - simple Q&A
                    )
                except Exception as e:
                    self.logger.error(f"AskFollowupQuestionTool: API call failed: {type(e).__name__}: {str(e)}", exc_info=True)
                    raise
                
                # Extract the text response
                try:
                    answer = await response.get_text()
                    self.logger.info(f"AskFollowupQuestionTool: AI question answered successfully, answer length: {len(answer)} chars")
                except Exception as e:
                    self.logger.error(f"AskFollowupQuestionTool: Failed to extract text from response: {type(e).__name__}: {str(e)}", exc_info=True)
                    raise
                
                return ToolResult(
                    tool_use_id=self.current_use_id,
                    content=f"AI Response:\n\n{answer}",
                    is_error=False
                )
        except Exception as e:
            self.logger.exception(f"AskFollowupQuestionTool: Unexpected error in AI query: {type(e).__name__}: {str(e)}")
            return ToolResult(
                tool_use_id=self.current_use_id,
                content=f"Unexpected error querying AI: {type(e).__name__}: {str(e)}",
                is_error=True,
                exception=e
            )


class AttemptCompletionTool(Tool):
    """Tool for signaling task completion."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        super().__init__(
            name="attempt_completion",
            description=(
                "After confirming that previous tool uses were successful, use this tool to "
                "present the result of your work to the user. The user may respond with "
                "feedback if they are not satisfied with the result."
            ),
            input_schema=ToolInputSchema(
                type="object",
                properties={
                    "result": {
                        "type": "string",
                        "description": (
                            "The result of the task. Formulate this result in a way that is "
                            "final and does not require further input from the user. Don't end "
                            "your result with questions or offers for further assistance."
                        )
                    }
                },
                required=["result"]
            )
        )
    
    async def execute(self, input_data: Dict[str, Any]) -> ToolResult:
        """Signal task completion."""
        try:
            # Log complete input data for debugging
            self.logger.info(f"AttemptCompletionTool: Received input with result length: {len(input_data.get('result', ''))} chars")
            
            result = input_data["result"]
            
            content = f"Task completed:\n\n{result}"
            self.logger.info("AttemptCompletionTool: Task completion signaled successfully")
            
            return ToolResult(
                tool_use_id=self.current_use_id,
                content=content,
                is_error=False
            )
            
        except Exception as e:
            self.logger.error(f"AttemptCompletionTool: Error formatting completion: {type(e).__name__}: {str(e)}", exc_info=True)
            return ToolResult(
                tool_use_id=self.current_use_id,
                content=f"Error formatting completion: {type(e).__name__}: {str(e)}",
                is_error=True,
                exception=e
            )


class UpdateTodoListTool(Tool):
    """Tool for managing task checklist."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        super().__init__(
            name="update_todo_list",
            description=(
                "Replace the entire TODO list with an updated checklist reflecting the current "
                "state. This tool is designed for step-by-step task tracking, allowing you to "
                "confirm completion of each step before updating, update multiple task statuses "
                "at once, and dynamically add new todos discovered during long or complex tasks."
            ),
            input_schema=ToolInputSchema(
                type="object",
                properties={
                    "todos": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "text": {"type": "string"},
                                "status": {
                                    "type": "string",
                                    "enum": ["pending", "in_progress", "completed"]
                                }
                            },
                            "required": ["text", "status"]
                        },
                        "description": (
                            "List of todo items with their current status. "
                            "Status options: pending, in_progress, completed"
                        )
                    }
                },
                required=["todos"]
            )
        )
    
    async def execute(self, input_data: Dict[str, Any]) -> ToolResult:
        """Update the TODO list."""
        try:
            # Log complete input data for debugging
            self.logger.info(f"UpdateTodoListTool: Received input with {len(input_data.get('todos', []))} todos")
            
            todos = input_data["todos"]
            
            if not todos:
                error_msg = "Error: TODO list cannot be empty"
                self.logger.error(f"UpdateTodoListTool: {error_msg}")
                return ToolResult(
                    tool_use_id=self.current_use_id,
                    content=error_msg,
                    is_error=True
                )
            
            # Format the TODO list
            content_parts = ["Updated TODO list:"]
            
            for todo in todos:
                text = todo["text"]
                status = todo["status"]
                
                # Format with checkbox
                if status == "completed":
                    checkbox = "[x]"
                elif status == "in_progress":
                    checkbox = "[-]"
                else:  # pending
                    checkbox = "[ ]"
                
                content_parts.append(f"{checkbox} {text}")
            
            content = "\n".join(content_parts)
            
            self.logger.info(f"UpdateTodoListTool: Successfully updated TODO list with {len(todos)} items")
            return ToolResult(
                tool_use_id=self.current_use_id,
                content=content,
                is_error=False
            )
            
        except Exception as e:
            self.logger.error(f"UpdateTodoListTool: Error updating TODO list: {type(e).__name__}: {str(e)}", exc_info=True)
            return ToolResult(
                tool_use_id=self.current_use_id,
                content=f"Error updating TODO list: {type(e).__name__}: {str(e)}",
                is_error=True,
                exception=e
            )