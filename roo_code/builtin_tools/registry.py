"""Registry for built-in tools with categorization by group."""

import logging
from typing import Dict, List
from ..tools import Tool, TOOL_ALIASES
from . import (
    # File operations
    ReadFileTool,
    WriteToFileTool,
    ApplyDiffTool,
    InsertContentTool,
    # Search & discovery
    SearchFilesTool,
    ListFilesTool,
    ListCodeDefinitionNamesTool,
    # Execution
    ExecuteCommandTool,
    # Browser
    BrowserActionTool,
    # MCP
    UseMcpToolTool,
    AccessMcpResourceTool,
    # Workflow
    AskFollowupQuestionTool,
    AttemptCompletionTool,
    UpdateTodoListTool,
    # Advanced
    FetchInstructionsTool,
    CodebaseSearchTool,
    RunSlashCommandTool,
    GenerateImageTool,
)

# Logger for tool registry
logger = logging.getLogger(__name__)


# Tool group definitions matching the TypeScript implementation
TOOL_GROUPS = {
    "read": {
        "description": "Read files and search codebase",
        "tools": ["read_file", "fetch_instructions", "search_files", "list_files", "list_code_definition_names"],
    },
    "edit": {
        "description": "Edit and create files",
        "tools": ["apply_diff", "write_to_file", "insert_content"],
    },
    "command": {
        "description": "Execute shell commands",
        "tools": ["execute_command"],
    },
    "browser": {
        "description": "Browser automation",
        "tools": ["browser_action"],
    },
    "mcp": {
        "description": "MCP server integration",
        "tools": ["use_mcp_tool", "access_mcp_resource"],
    },
    "modes": {
        "description": "Workflow and task management",
        "tools": ["ask_followup_question", "attempt_completion", "update_todo_list"],
    },
    "advanced": {
        "description": "Advanced features",
        "tools": ["codebase_search", "run_slash_command", "generate_image"],
    },
}


def get_all_builtin_tools(cwd: str = ".") -> List[Tool]:
    """
    Get all built-in tools with default initialization.
    
    Args:
        cwd: Current working directory for file operation tools
        
    Returns:
        List of all built-in tool instances
    """
    tools = [
        # File operations (read group)
        ReadFileTool(cwd=cwd),
        # Search & discovery (read group)
        SearchFilesTool(cwd=cwd),
        ListFilesTool(cwd=cwd),
        ListCodeDefinitionNamesTool(cwd=cwd),
        # Edit operations (edit group)
        WriteToFileTool(cwd=cwd),
        ApplyDiffTool(cwd=cwd),
        InsertContentTool(cwd=cwd),
        # Execution (command group)
        ExecuteCommandTool(cwd=cwd),
        # Browser (browser group)
        BrowserActionTool(),
        # MCP (mcp group)
        UseMcpToolTool(),
        AccessMcpResourceTool(),
        # Workflow (modes group)
        AskFollowupQuestionTool(),
        AttemptCompletionTool(),
        UpdateTodoListTool(),
        # Advanced
        FetchInstructionsTool(),
        CodebaseSearchTool(),
        RunSlashCommandTool(),
        GenerateImageTool(),
    ]
    
    return tools


def get_tools_by_group(group: str, cwd: str = ".") -> List[Tool]:
    """
    Get tools for a specific group.
    
    Args:
        group: Tool group name (e.g., "read", "edit", "command")
        cwd: Current working directory for file operation tools
        
    Returns:
        List of tool instances for the specified group
    """
    if group not in TOOL_GROUPS:
        raise ValueError(f"Unknown tool group: {group}. Available groups: {list(TOOL_GROUPS.keys())}")
    
    group_info = TOOL_GROUPS[group]
    tool_names = set(group_info["tools"])
    
    all_tools = get_all_builtin_tools(cwd=cwd)
    
    return [tool for tool in all_tools if tool.name in tool_names]


def get_tools_by_groups(groups: List[str], cwd: str = ".") -> List[Tool]:
    """
    Get tools for multiple groups.
    
    Args:
        groups: List of tool group names
        cwd: Current working directory for file operation tools
        
    Returns:
        List of tool instances for the specified groups (deduplicated)
    """
    tool_dict: Dict[str, Tool] = {}
    
    for group in groups:
        group_tools = get_tools_by_group(group, cwd=cwd)
        for tool in group_tools:
            tool_dict[tool.name] = tool
    
    return list(tool_dict.values())


def get_tool_by_name(name: str, cwd: str = ".") -> Tool:
    """
    Get a specific tool by name.
    
    Args:
        name: Tool name (or alias)
        cwd: Current working directory for file operation tools
        
    Returns:
        Tool instance
        
    Raises:
        ValueError: If tool name is not found
    """
    # Check if name is an alias and resolve it first
    resolved_name = name
    if name in TOOL_ALIASES:
        resolved_name = TOOL_ALIASES[name]
        logger.info(f"Tool alias used: '{name}' -> '{resolved_name}'")
    
    # Now search for the tool using the resolved name
    all_tools = get_all_builtin_tools(cwd=cwd)
    for tool in all_tools:
        if tool.name == resolved_name:
            return tool
    
    raise ValueError(f"Unknown tool: {resolved_name}")


def list_available_tools() -> Dict[str, List[str]]:
    """
    List all available tools organized by group.
    
    Returns:
        Dictionary mapping group names to lists of tool names
    """
    return {
        group: info["tools"]
        for group, info in TOOL_GROUPS.items()
    }


def get_tool_group(tool_name: str) -> str:
    """
    Get the group that a tool belongs to.
    
    Args:
        tool_name: Name of the tool
        
    Returns:
        Group name
        
    Raises:
        ValueError: If tool is not found in any group
    """
    for group, info in TOOL_GROUPS.items():
        if tool_name in info["tools"]:
            return group
    
    raise ValueError(f"Tool {tool_name} not found in any group")