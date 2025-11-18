"""Workflow tools for agent interaction and task management."""

from typing import Any, Dict, List
from ..tools import Tool, ToolInputSchema, ToolResult


class AskFollowupQuestionTool(Tool):
    """Tool for asking the user follow-up questions."""
    
    def __init__(self):
        super().__init__(
            name="ask_followup_question",
            description=(
                "Ask the user a question to gather additional information needed to complete "
                "the task. Use when you need clarification or more details to proceed effectively."
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
                            "2-4 suggested answers. Suggestions must be complete, actionable "
                            "answers without placeholders."
                        )
                    }
                },
                required=["question", "suggestions"]
            )
        )
    
    async def execute(self, input_data: Dict[str, Any]) -> ToolResult:
        """Format a follow-up question."""
        try:
            question = input_data["question"]
            suggestions = input_data.get("suggestions", [])
            
            # Format the question with suggestions
            content_parts = [f"Question: {question}"]
            
            if suggestions:
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
            return ToolResult(
                tool_use_id=self.current_use_id,
                content=f"Error formatting question: {str(e)}",
                is_error=True
            )


class AttemptCompletionTool(Tool):
    """Tool for signaling task completion."""
    
    def __init__(self):
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
            result = input_data["result"]
            
            content = f"Task completed:\n\n{result}"
            
            return ToolResult(
                tool_use_id=self.current_use_id,
                content=content,
                is_error=False
            )
            
        except Exception as e:
            return ToolResult(
                tool_use_id=self.current_use_id,
                content=f"Error formatting completion: {str(e)}",
                is_error=True
            )


class UpdateTodoListTool(Tool):
    """Tool for managing task checklist."""
    
    def __init__(self):
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
            todos = input_data["todos"]
            
            if not todos:
                return ToolResult(
                    tool_use_id=self.current_use_id,
                    content="Error: TODO list cannot be empty",
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
            
            return ToolResult(
                tool_use_id=self.current_use_id,
                content=content,
                is_error=False
            )
            
        except Exception as e:
            return ToolResult(
                tool_use_id=self.current_use_id,
                content=f"Error updating TODO list: {str(e)}",
                is_error=True
            )