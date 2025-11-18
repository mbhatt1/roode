# Built-in Tools Implementation

This directory contains Python implementations of the core tools from the TypeScript Roo Code implementation.

## Implementation Status

### ✅ Completed Core Structure
- [x] Base tool classes following the Python SDK pattern
- [x] All 18 concrete tools implemented
- [x] Tool registry with group categorization
- [x] Test suite with comprehensive coverage

### 🔧 Tools Implemented

#### File Operations (`file_operations.py`)
1. **ReadFileTool** - Read file contents with optional line ranges
2. **WriteToFileTool** - Write complete file contents
3. **ApplyDiffTool** - Apply surgical edits using search/replace blocks
4. **InsertContentTool** - Insert lines at specific positions

#### Search & Discovery (`search.py`)
5. **SearchFilesTool** - Regex search across files with context
6. **ListFilesTool** - List directory contents (recursive option)
7. **ListCodeDefinitionNamesTool** - Extract code definitions (classes, functions, etc.)

#### Execution (`execution.py`)
8. **ExecuteCommandTool** - Run shell commands with output capture

#### Browser Automation (`browser.py`)
9. **BrowserActionTool** - Browser automation using Playwright

#### MCP Integration (`mcp.py`)
10. **UseMcpToolTool** - Execute MCP server tools (placeholder)
11. **AccessMcpResourceTool** - Access MCP resources (placeholder)

#### Workflow (`workflow.py`)
12. **AskFollowupQuestionTool** - Request user input with suggestions
13. **AttemptCompletionTool** - Signal task completion
14. **UpdateTodoListTool** - Manage task checklist

#### Advanced (`advanced.py`)
15. **FetchInstructionsTool** - Load mode-specific instructions
16. **CodebaseSearchTool** - Semantic code search (placeholder)
17. **RunSlashCommandTool** - Execute custom commands (placeholder)
18. **GenerateImageTool** - AI image generation (placeholder)

## Architecture Differences from TypeScript

### TypeScript Implementation
The TypeScript tools are **functions** that:
- Execute within a Task/Cline context
- Have direct access to VSCode APIs
- Integrate with user approval flows
- Handle streaming responses
- Manage checkpoints and state

### Python Implementation
The Python tools are **classes** that:
- Extend the `Tool` base class
- Execute independently with provided context
- Return `ToolResult` objects
- Are designed for programmatic use

## Key Gaps for Full Parity

### 1. **Context Integration**
The TypeScript tools operate within a rich context that includes:
- User interaction callbacks (approval, feedback)
- File system watchers
- Git integration
- Checkpoint management
- UI state synchronization

**Python Solution**: The tools should accept a `context` parameter containing:
```python
class ToolContext:
    cwd: str
    ask_approval: Callable
    handle_error: Callable  
    push_result: Callable
    workspace_config: Dict[str, Any]
```

### 2. **User Approval Flow**
TypeScript tools show diffs and request approval before making changes.

**Python Solution**: Implement approval callbacks in tool execution:
```python
if requires_approval:
    approved = await context.ask_approval(proposed_changes)
    if not approved:
        return ToolResult(is_error=True, content="Operation cancelled by user")
```

### 3. **Advanced Features Not Yet Implemented**
- **Tree-sitter integration** for accurate code parsing (list_code_definition_names)
- **Ripgrep integration** for faster file searching (search_files)
- **MCP client** for actual MCP server communication
- **Vector database** for semantic codebase search
- **Image generation APIs** integration

### 4. **Error Handling & Recovery**
TypeScript implementation includes:
- Consecutive mistake counting
- Tool repetition detection
- Automatic retry logic
- Detailed error diagnostics

### 5. **File Restrictions & Mode System**
TypeScript supports mode-specific file editing restrictions.

**Example**: Architect mode can only edit `.md` files

**Python Solution**: Implement in tool execution:
```python
if self.mode and not self.mode.allows_file_edit(file_path):
    raise FileRestrictionError(...)
```

## Usage Examples

### Basic Usage
```python
from roo_code.builtin_tools import ReadFileTool

# Create tool instance
tool = ReadFileTool(cwd="/path/to/workspace")
tool.current_use_id = "unique-id"

# Execute tool
result = await tool.execute({
    "path": "src/main.py",
    "start_line": 1,
    "end_line": 50
})

print(result.content)  # Line-numbered file content
```

### Registry Usage
```python
from roo_code.builtin_tools.registry import get_all_builtin_tools, get_tools_by_group

# Get all tools
all_tools = get_all_builtin_tools(cwd="/workspace")

# Get tools by group
read_tools = get_tools_by_group("read", cwd="/workspace")
edit_tools = get_tools_by_group("edit", cwd="/workspace")

# Register with agent
from roo_code.tools import ToolRegistry

registry = ToolRegistry()
for tool in all_tools:
    registry.register(tool)
```

### Integration with Agent
```python
from roo_code.client import RooClient
from roo_code.builtin_tools.registry import get_all_builtin_tools

# Create client
client = RooClient(api_key="...")

# Register tools
tools = get_all_builtin_tools(cwd="/workspace")
tool_definitions = [tool.get_definition() for tool in tools]

# Use with streaming
async for chunk in client.stream(
    messages=[{"role": "user", "content": "Read the README file"}],
    tools=tool_definitions
):
    if chunk.type == "tool_use":
        # Execute tool
        tool = next(t for t in tools if t.name == chunk.name)
        tool.current_use_id = chunk.id
        result = await tool.execute(chunk.input)
        
        # Send result back
        # ... (continue conversation)
```

## Testing

Run tests:
```bash
cd roo-code-python
python3 -m pytest tests/test_builtin_tools.py -v
```

## Dependencies

### Required
- `pathlib` (stdlib)
- `re` (stdlib)
- `asyncio` (stdlib)

### Optional
- `playwright>=1.40.0` - For browser automation
- `tree-sitter>=0.20.0` - For accurate code parsing
- `pygments>=2.15.0` - For syntax highlighting

Install with tools support:
```bash
pip install roo-code[tools]
```

## Roadmap to Full Parity

### Phase 1: Core Functionality (Current)
- ✅ All 18 tools implemented
- ✅ Basic file operations working
- ✅ Tool registry system
- ✅ Test coverage

### Phase 2: Integration (Next)
- [ ] Add ToolContext for rich contextual execution
- [ ] Implement approval/feedback flows
- [ ] Add file watching capabilities
- [ ] Integrate with mode system

### Phase 3: Advanced Features
- [ ] Tree-sitter for code parsing
- [ ] Ripgrep for fast searching
- [ ] MCP client implementation
- [ ] Vector database for semantic search
- [ ] Image generation integration

### Phase 4: Production Ready
- [ ] Error recovery mechanisms
- [ ] Tool repetition detection
- [ ] Performance optimization
- [ ] Comprehensive documentation
- [ ] Production testing

## Contributing

When adding or modifying tools:
1. Ensure consistency with TypeScript implementation
2. Add comprehensive tests
3. Update registry if adding new tools
4. Document any differences from TypeScript version
5. Consider context requirements

## License

Apache 2.0 - Same as Roo Code