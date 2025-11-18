# Roo-Code-Python System Architecture & Flow

This document provides a comprehensive explanation of how the roo-code-python system works from a flow perspective, covering all major components and their interactions.

## Table of Contents

1. [System Overview](#system-overview)
2. [Entry Points](#entry-points)
3. [Core Components Flow](#core-components-flow)
4. [Tool Execution Flow](#tool-execution-flow)
5. [Mode System Flow](#mode-system-flow)
6. [MCP Integration Flow](#mcp-integration-flow)
7. [Workflow Orchestration Flow](#workflow-orchestration-flow)
8. [Complete Request-Response Cycles](#complete-request-response-cycles)

---

## System Overview

The roo-code-python system is a sophisticated AI agent framework that enables autonomous task execution through:
- **Multiple AI provider support** (Anthropic, OpenAI, Gemini, etc.)
- **18+ builtin tools** for file operations, code search, command execution, and more
- **Mode-aware execution** with tool restrictions and task management
- **MCP (Model Context Protocol) integration** for external tool/resource access
- **Workflow orchestration** for complex multi-phase projects

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      USER / CLIENT                          │
└────────────────────┬────────────────────────────────────────┘
                     │
        ┌────────────┴────────────┐
        │                         │
        ▼                         ▼
┌───────────────┐        ┌────────────────┐
│  Direct Agent │        │   MCP Server   │
│     Usage     │        │   (JSON-RPC)   │
└───────┬───────┘        └────────┬───────┘
        │                         │
        └────────────┬────────────┘
                     │
                     ▼
        ┌────────────────────────┐
        │   Agent / ModeAgent    │
        │  (Task Coordination)   │
        └────────┬───────────────┘
                 │
    ┌────────────┼────────────┐
    │            │            │
    ▼            ▼            ▼
┌────────┐  ┌─────────┐  ┌──────────────┐
│ Client │  │  Tools  │  │ Orchestrator │
│  (AI)  │  │Registry │  │   (Modes)    │
└────┬───┘  └────┬────┘  └──────┬───────┘
     │           │               │
     ▼           ▼               ▼
┌─────────┐ ┌──────────┐  ┌────────────┐
│Provider │ │ Builtin  │  │   Tasks    │
│ (API)   │ │  Tools   │  │  Sessions  │
└─────────┘ └──────────┘  └────────────┘
```

---

## Entry Points

### 1. Direct Agent Usage

**File:** [`roo_code/agent.py`](../roo_code/agent.py)

Users can directly instantiate and use the `Agent` class for autonomous task execution:

```python
from roo_code import Agent, RooClient, ProviderSettings

# Create client with AI provider
client = RooClient(
    provider_settings=ProviderSettings(
        api_provider="anthropic",
        api_key="your-key",
        api_model_id="claude-sonnet-4-5"
    )
)

# Create agent with builtin tools
agent = Agent(client=client, tools=[])

# Run task
result = await agent.run("Create a Python hello world script")
```

**Flow:**
1. User creates [`RooClient`](../roo_code/client.py:28) with provider configuration
2. User creates [`Agent`](../roo_code/agent.py:14) with client and optional custom tools
3. Agent auto-loads 18 builtin tools from [`registry`](../roo_code/builtin_tools/registry.py:71)
4. User calls [`agent.run()`](../roo_code/agent.py:131) with task description
5. Agent coordinates AI calls and tool executions until task completion

### 2. MCP Server Entry Point

**File:** [`roo_code/mcp/server.py`](../roo_code/mcp/server.py)

External MCP clients connect via JSON-RPC 2.0 over stdio:

```python
from roo_code.mcp import McpModesServer

# Create MCP server
server = McpModesServer(
    project_root=Path("/path/to/project"),
    global_config_dir=Path.home() / ".roo-code"
)

# Run server (reads stdin, writes stdout)
await server.run()
```

**Flow:**
1. MCP client sends JSON-RPC messages over stdin
2. [`McpModesServer`](../roo_code/mcp/server.py:31) parses and routes requests
3. Server handles: `initialize`, `resources/list`, `resources/read`, `tools/list`, `tools/call`
4. Results returned as JSON-RPC responses over stdout
5. Sessions managed with timeout and cleanup

---

## Core Components Flow

### Agent - Task Coordinator

**File:** [`roo_code/agent.py`](../roo_code/agent.py)

The [`Agent`](../roo_code/agent.py:14) class is the central coordinator that:

```
┌─────────────────────────────────────────────────────────┐
│                        Agent                            │
│                                                         │
│  ┌──────────────┐                                      │
│  │ Constructor  │                                      │
│  │  - client    │  Initialize with RooClient          │
│  │  - tools     │  Register tools in ToolRegistry     │
│  │  - system    │  Generate system prompt             │
│  └──────────────┘                                      │
│         │                                               │
│         ▼                                               │
│  ┌──────────────┐                                      │
│  │   run()      │  Main execution loop                │
│  │              │                                      │
│  │  Loop:       │                                      │
│  │  1. Call AI  │────────┐                            │
│  │  2. Get resp │        │                            │
│  │  3. Extract  │        │                            │
│  │     tool use │        │                            │
│  │  4. Execute  │        │                            │
│  │     tool     │        │                            │
│  │  5. Add res  │        │                            │
│  │     to msgs  │        │                            │
│  │  6. Repeat   │←───────┘                            │
│  └──────────────┘                                      │
└─────────────────────────────────────────────────────────┘
```

**Key Methods:**
- [`__init__()`](../roo_code/agent.py:56): Register tools, set system prompt
- [`run()`](../roo_code/agent.py:131): Main execution loop with max iterations
- [`_extract_tool_use()`](../roo_code/agent.py:265): Extract tool requests from AI response
- [`add_tool()`](../roo_code/agent.py:290): Register additional tools

**Iteration Flow:**
```
User Task
    │
    ▼
┌─────────────────────────────────────┐
│ Iteration N (max_iterations=10)    │
├─────────────────────────────────────┤
│ 1. Create message with:             │
│    - System prompt                  │
│    - Message history                │
│    - Tool definitions               │
│                                     │
│ 2. Call client.create_message()    │
│    └─> Returns ApiStream           │
│                                     │
│ 3. Consume stream via               │
│    get_final_message()             │
│                                     │
│ 4. Extract tool_use blocks         │
│    └─> If none: DONE               │
│    └─> If found: Continue          │
│                                     │
│ 5. Execute tool via registry       │
│    └─> Get ToolResult              │
│                                     │
│ 6. Add result to messages          │
│    └─> Create tool_result block   │
│                                     │
│ 7. Loop to next iteration          │
└─────────────────────────────────────┘
    │
    ▼
Final Answer or Max Iterations
```

### Client - AI Provider Communication

**File:** [`roo_code/client.py`](../roo_code/client.py)

The [`RooClient`](../roo_code/client.py:28) manages communication with AI providers:

```
┌────────────────────────────────────────────────────────┐
│                     RooClient                          │
│                                                        │
│  ProviderSettings ──┐                                 │
│    │                │                                 │
│    ▼                ▼                                 │
│  ┌──────────────────────────────┐                    │
│  │  _build_provider()           │                    │
│  │                              │                    │
│  │  Provider Map:               │                    │
│  │  - anthropic → Anthropic     │                    │
│  │  - openai → OpenAI           │                    │
│  │  - gemini → Gemini           │                    │
│  │  - openrouter → OpenRouter   │                    │
│  │  - groq → Groq               │                    │
│  │  - mistral → Mistral         │                    │
│  │  - deepseek → DeepSeek       │                    │
│  │  - ollama → Ollama           │                    │
│  └──────────────────────────────┘                    │
│            │                                          │
│            ▼                                          │
│  ┌──────────────────────────────┐                    │
│  │  create_message()            │                    │
│  │                              │                    │
│  │  Input:                      │                    │
│  │  - system_prompt             │                    │
│  │  - messages                  │                    │
│  │  - tools                     │                    │
│  │  - metadata                  │                    │
│  │                              │                    │
│  │  Output: ApiStream           │                    │
│  └──────────────────────────────┘                    │
└────────────────────────────────────────────────────────┘
```

**Provider Selection Flow:**
```
ProviderSettings
    │
    ├─ api_provider: "anthropic"
    ├─ api_key: "sk-..."
    ├─ api_model_id: "claude-sonnet-4-5"
    └─ api_base_url: optional
    │
    ▼
_build_provider()
    │
    ├─ Check provider_map
    ├─ Get provider class
    └─ Initialize provider
    │
    ▼
BaseProvider instance
    │
    └─> Used by create_message()
```

### ToolRegistry - Tool Management

**File:** [`roo_code/tools.py`](../roo_code/tools.py)

The [`ToolRegistry`](../roo_code/tools.py:465) manages all available tools:

```
┌───────────────────────────────────────────────────┐
│              ToolRegistry                         │
│                                                   │
│  tools: Dict[str, Tool] = {}                     │
│                                                   │
│  ┌────────────────────────────────┐             │
│  │  register(tool)                │             │
│  │  └─> tools[tool.name] = tool   │             │
│  └────────────────────────────────┘             │
│                                                   │
│  ┌────────────────────────────────┐             │
│  │  get(name)                     │             │
│  │  1. Check direct match         │             │
│  │  2. Check TOOL_ALIASES         │             │
│  │  3. Auto-load if builtin       │             │
│  │  └─> Returns Tool or None      │             │
│  └────────────────────────────────┘             │
│                                                   │
│  ┌────────────────────────────────┐             │
│  │  execute(tool_use)             │             │
│  │  1. Get tool by name           │             │
│  │  2. Set tool.current_use_id    │             │
│  │  3. Call tool.execute_with_    │             │
│  │     recovery()                 │             │
│  │  └─> Returns ToolResult        │             │
│  └────────────────────────────────┘             │
└───────────────────────────────────────────────────┘
```

**Tool Aliasing:**
```python
# Defined in tools.py
TOOL_ALIASES = {
    'read_directory': 'list_files',
    'read_dir': 'list_files',
    'list_dir': 'list_files',
    # ... more aliases
}
```

**Execution with Recovery:**
```
execute(tool_use)
    │
    ▼
get(tool_use.name)
    │
    ├─> Check aliases
    └─> Auto-load builtin
    │
    ▼
tool.current_use_id = tool_use.id
    │
    ▼
tool.execute_with_recovery(input_data)
    │
    ├─> Repetition detection
    ├─> Circuit breaker (optional)
    ├─> Error recovery with retry
    └─> Error metrics tracking
    │
    ▼
ToolResult(tool_use_id, content, is_error)
```

### Stream - Response Handling

**File:** [`roo_code/stream.py`](../roo_code/stream.py)

The [`ApiStream`](../roo_code/stream.py:8) handles streaming AI responses:

```
┌────────────────────────────────────────────────────┐
│                   ApiStream                        │
│                                                    │
│  _stream: AsyncIterator[StreamChunk]             │
│  _content_blocks: List[ContentBlock] = []         │
│  _stop_reason: Optional[str] = None               │
│  _usage: Dict[str, int] = {}                      │
│                                                    │
│  ┌─────────────────────────────────┐             │
│  │  async stream()                 │             │
│  │                                 │             │
│  │  async for chunk in _stream:   │             │
│  │    if content_block_start:     │             │
│  │      append to _content_blocks │             │
│  │    if content_block_delta:     │             │
│  │      accumulate text/json      │             │
│  │    if message_delta:           │             │
│  │      track usage, stop_reason  │             │
│  │    yield chunk                 │             │
│  └─────────────────────────────────┘             │
│                                                    │
│  ┌─────────────────────────────────┐             │
│  │  async get_final_message()     │             │
│  │  └─> Consume stream, return    │             │
│  │      complete message           │             │
│  └─────────────────────────────────┘             │
│                                                    │
│  ┌─────────────────────────────────┐             │
│  │  get_tool_uses()               │             │
│  │  └─> Extract ToolUseContent    │             │
│  │      blocks                     │             │
│  └─────────────────────────────────┘             │
└────────────────────────────────────────────────────┘
```

**Stream Processing:**
```
API Response Stream
    │
    ├─> message_start
    │   └─> Track input_tokens
    │
    ├─> content_block_start
    │   └─> Create TextContent or ToolUseContent
    │
    ├─> content_block_delta (multiple)
    │   ├─> For TextContent: accumulate text
    │   └─> For ToolUseContent: accumulate JSON
    │
    ├─> content_block_stop
    │   └─> Block complete
    │
    ├─> message_delta
    │   └─> Track output_tokens, stop_reason
    │
    └─> message_stop
        └─> Stream complete

Result:
{
  "content": [TextContent, ToolUseContent, ...],
  "stop_reason": "end_turn" | "tool_use",
  "usage": {"input_tokens": 100, "output_tokens": 200}
}
```

---

## Tool Execution Flow

### Overview

```
AI Model                                  System
   │                                         │
   │  Tool Use Request                      │
   ├────────────────────────────────────────>│
   │  {                                      │
   │    "type": "tool_use",                 │
   │    "id": "toolu_123",                  │
   │    "name": "read_file",                │
   │    "input": {"path": "main.py"}        │
   │  }                                      │
   │                                         │
   │                                         ▼
   │                           ┌──────────────────────────┐
   │                           │  1. Agent extracts       │
   │                           │     tool use from        │
   │                           │     response             │
   │                           └────────┬─────────────────┘
   │                                    │
   │                                    ▼
   │                           ┌──────────────────────────┐
   │                           │  2. ToolRegistry.get()   │
   │                           │     - Check aliases      │
   │                           │     - Auto-load builtin  │
   │                           └────────┬─────────────────┘
   │                                    │
   │                                    ▼
   │                           ┌──────────────────────────┐
   │                           │  3. Tool.execute_with_   │
   │                           │     recovery()           │
   │                           │     - Repetition check   │
   │                           │     - Circuit breaker    │
   │                           │     - Error retry        │
   │                           └────────┬─────────────────┘
   │                                    │
   │                                    ▼
   │                           ┌──────────────────────────┐
   │                           │  4. Tool.execute()       │
   │                           │     - Actual work        │
   │                           │     - File ops, cmds,    │
   │                           │       searches, etc.     │
   │                           └────────┬─────────────────┘
   │                                    │
   │                                    ▼
   │                           ┌──────────────────────────┐
   │                           │  5. Return ToolResult    │
   │                           │     {                    │
   │                           │       tool_use_id,       │
   │                           │       content,           │
   │                           │       is_error           │
   │                           │     }                    │
   │                           └────────┬─────────────────┘
   │                                    │
   │  Tool Result                       │
   │<───────────────────────────────────┤
   │  {                                 │
   │    "type": "tool_result",         │
   │    "tool_use_id": "toolu_123",    │
   │    "content": "file contents..."  │
   │  }                                 │
   │                                    │
   │  Next response/action              │
   │<───────────────────────────────────┤
```

### 18 Builtin Tools

**File:** [`roo_code/builtin_tools/registry.py`](../roo_code/builtin_tools/registry.py)

Organized into 7 groups:

1. **Read Group** (Discovery & Analysis)
   - [`read_file`](../roo_code/builtin_tools/read_file.py): Read file contents with line numbers
   - [`search_files`](../roo_code/builtin_tools/search_files.py): Regex search across files
   - [`list_files`](../roo_code/builtin_tools/list_files.py): List directory contents
   - [`list_code_definition_names`](../roo_code/builtin_tools/list_code_definitions.py): Extract code symbols
   - [`fetch_instructions`](../roo_code/builtin_tools/fetch_instructions.py): Get task-specific instructions

2. **Edit Group** (File Modification)
   - [`write_to_file`](../roo_code/builtin_tools/write_file.py): Create/overwrite files
   - [`apply_diff`](../roo_code/builtin_tools/apply_diff.py): Surgical edits with SEARCH/REPLACE
   - [`insert_content`](../roo_code/builtin_tools/insert_content.py): Insert lines at position

3. **Command Group** (Execution)
   - [`execute_command`](../roo_code/builtin_tools/execute_command.py): Run shell commands

4. **Browser Group** (Web Interaction)
   - [`browser_action`](../roo_code/builtin_tools/browser.py): Puppeteer browser control

5. **MCP Group** (External Integration)
   - [`use_mcp_tool`](../roo_code/builtin_tools/mcp.py): Call MCP server tools
   - [`access_mcp_resource`](../roo_code/builtin_tools/mcp.py): Read MCP resources

6. **Modes Group** (Workflow)
   - [`ask_followup_question`](../roo_code/builtin_tools/ask_question.py): Request user input
   - [`attempt_completion`](../roo_code/builtin_tools/completion.py): Mark task complete
   - [`update_todo_list`](../roo_code/builtin_tools/todo.py): Track task progress

7. **Advanced Group** (Special Features)
   - [`codebase_search`](../roo_code/builtin_tools/codebase_search.py): Semantic code search
   - [`run_slash_command`](../roo_code/builtin_tools/slash_commands.py): Execute custom commands
   - [`generate_image`](../roo_code/builtin_tools/image_gen.py): Create images

### Error Recovery Flow

**File:** [`roo_code/builtin_tools/error_recovery.py`](../roo_code/builtin_tools/error_recovery.py)

```
Tool Execution
    │
    ▼
┌────────────────────────────────────────┐
│  execute_with_recovery()               │
├────────────────────────────────────────┤
│                                        │
│  1. Repetition Detection               │
│     └─> Check if same call repeated   │
│     └─> Warn if critical pattern      │
│                                        │
│  2. Circuit Breaker (optional)         │
│     └─> Track failure rate            │
│     └─> OPEN circuit if too many      │
│                                        │
│  3. Execute with Retry                 │
│     ┌─────────────────────────┐       │
│     │  Try 1: execute()       │       │
│     │    ├─> Success: Done    │       │
│     │    └─> Fail: Continue   │       │
│     │                          │       │
│     │  Try 2: execute()       │       │
│     │    └─> After backoff    │       │
│     │                          │       │
│     │  Try 3: execute()       │       │
│     │    └─> After backoff    │       │
│     └─────────────────────────┘       │
│                                        │
│  4. Record Metrics                     │
│     └─> Success/failure counts        │
│     └─> Recovery success              │
│                                        │
│  5. Return Result or Error             │
└────────────────────────────────────────┘
```

### Tool Aliasing Example

```python
# User asks: "List the directory contents"
# AI responds with tool_use: "read_directory"

ToolRegistry.get("read_directory")
    │
    ├─> Not in tools dict directly
    │
    ├─> Check TOOL_ALIASES
    │   └─> TOOL_ALIASES["read_directory"] = "list_files"
    │
    ├─> Check if "list_files" in tools
    │   └─> Found: return it
    │
    └─> If not found, auto-load from builtin_tools
        └─> from builtin_tools.registry import get_tool_by_name
        └─> Register and return
```

---

## Mode System Flow

### ModeAgent Architecture

**File:** [`roo_code/modes/agent.py`](../roo_code/modes/agent.py)

[`ModeAgent`](../roo_code/modes/agent.py:20) extends base [`Agent`](../roo_code/agent.py:14) with mode awareness:

```
┌─────────────────────────────────────────────────────┐
│                   ModeAgent                         │
│         (extends Agent)                             │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ┌──────────────────────────────┐                  │
│  │  ModeOrchestrator            │                  │
│  │  - Load modes from config    │                  │
│  │  - Validate tool access      │                  │
│  │  - Manage tasks              │                  │
│  └──────────────────────────────┘                  │
│                 │                                   │
│                 ▼                                   │
│  ┌──────────────────────────────┐                  │
│  │  Current Task                │                  │
│  │  - mode_slug: "code"         │                  │
│  │  - state: RUNNING            │                  │
│  │  - messages: [...]           │                  │
│  │  - parent/child tasks        │                  │
│  └──────────────────────────────┘                  │
│                                                     │
│  ┌──────────────────────────────┐                  │
│  │  Mode Configuration          │                  │
│  │  - name: "Code"              │                  │
│  │  - description: "..."        │                  │
│  │  - groups: ["read", "edit"]  │                  │
│  │  - file_restrictions: []     │                  │
│  └──────────────────────────────┘                  │
│                                                     │
│  ┌──────────────────────────────┐                  │
│  │  Mode Tools                  │                  │
│  │  - switch_mode               │                  │
│  │  - new_task                  │                  │
│  └──────────────────────────────┘                  │
└─────────────────────────────────────────────────────┘
```

### Mode Configuration

Modes are defined in YAML:

```yaml
# .roo/modes/code.yaml
name: "💻 Code"
description: "Write, modify, and refactor code"
when_to_use: "When you need to implement features or fix bugs"

groups:
  - read        # Can use read tools
  - edit        # Can use edit tools
  - command     # Can run commands
  - browser     # Can use browser

file_restrictions:
  allow_patterns:
    - ".*"      # Can edit all files

system_prompt_file: "prompts/code.md"
```

### Mode-Aware Execution Flow

```
User: "Create a Python file"
    │
    ▼
ModeAgent.run(task)
    │
    ├─> Mark task as RUNNING
    ├─> Add user message to task
    │
    ▼
Base Agent.run()  (inherited)
    │
    ├─> Iteration loop
    │   │
    │   ├─> Get system prompt for current mode
    │   ├─> Get tool definitions
    │   ├─> Call AI
    │   │
    │   ▼
    │   Tool use: write_to_file
    │   │
    │   ▼
    ├─> Validate tool use (mode-aware)
    │   │
    │   ├─> Check if tool in allowed groups
    │   │   └─> "write_to_file" in "edit" group
    │   │   └─> "edit" in mode.groups? YES
    │   │
    │   ├─> Check file restrictions
    │   │   └─> file matches allow_patterns? YES
    │   │
    │   └─> ALLOWED
    │
    ├─> Execute tool
    │
    └─> Continue loop
    │
    ▼
Task completed
    └─> Mark task as COMPLETED
```

### Mode Tools: switch_mode and new_task

**File:** [`roo_code/modes/tools.py`](../roo_code/modes/tools.py)

These special tools enable mode coordination:

**1. switch_mode**
```
Current Mode: architect
    │
    │  AI decides: "I need to make code changes"
    │
    ▼
Tool use: switch_mode
    {
      "mode_slug": "code",
      "reason": "Need to implement the design"
    }
    │
    ▼
orchestrator.switch_mode(task, "code")
    │
    ├─> Validate mode exists
    ├─> Update task.mode_slug
    ├─> Reload system prompt
    └─> Add mode switch to conversation
    │
    ▼
Current Mode: code
```

**2. new_task**
```
Parent Task (orchestrator mode)
    │
    │  AI decides: "Create subtask for implementation"
    │
    ▼
Tool use: new_task
    {
      "mode": "code",
      "message": "Implement UserService class"
    }
    │
    ▼
orchestrator.create_task()
    │
    ├─> Create new Task object
    ├─> Set parent_task reference
    ├─> Add to parent's child_task_ids
    ├─> Initialize with mode and message
    │
    ▼
Child Task (code mode)
    │
    ├─> Can be executed independently
    ├─> Has own message history
    └─> Reports back to parent on completion
```

### Mode Restrictions

```
Mode: architect
Groups: ["read"]  (NO edit, command, browser)

Tool use: apply_diff
    │
    ▼
Validate tool use
    │
    ├─> "apply_diff" in "edit" group
    ├─> "edit" NOT in mode.groups
    │
    ▼
REJECT: FileRestrictionError
    └─> "architect mode can only edit files matching \.md$"
```

---

## MCP Integration Flow

### MCP Server Architecture

**File:** [`roo_code/mcp/server.py`](../roo_code/mcp/server.py)

```
┌─────────────────────────────────────────────────────┐
│                 MCP Client                          │
│         (VSCode, Claude Desktop, etc.)              │
└────────────────┬────────────────────────────────────┘
                 │
         stdin (JSON-RPC requests)
                 │
                 ▼
┌─────────────────────────────────────────────────────┐
│            McpModesServer                           │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ┌──────────────────────────────┐                  │
│  │  Protocol Layer              │                  │
│  │  - MessageParser             │                  │
│  │  - MessageWriter             │                  │
│  │  - Request routing           │                  │
│  └──────────────────────────────┘                  │
│                 │                                   │
│                 ▼                                   │
│  ┌──────────────┬──────────────┬────────────────┐  │
│  │              │              │                │  │
│  ▼              ▼              ▼                ▼  │
│ ┌──────┐  ┌──────────┐  ┌─────────┐  ┌─────────┐ │
│ │ Init │  │ Resource │  │  Tool   │  │ Session │ │
│ │      │  │ Handler  │  │ Handler │  │ Manager │ │
│ └──────┘  └──────────┘  └─────────┘  └─────────┘ │
│                 │              │                │  │
│                 ▼              ▼                ▼  │
│            List/Read      List/Call         Tasks │
└─────────────────────────────────────────────────────┘
                 │
         stdout (JSON-RPC responses)
                 │
                 ▼
┌─────────────────────────────────────────────────────┐
│                 MCP Client                          │
└─────────────────────────────────────────────────────┘
```

### JSON-RPC Protocol

**Message Format:**
```json
// Request
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "switch_mode",
    "arguments": {
      "mode_slug": "code",
      "reason": "Implementation needed"
    }
  }
}

// Response
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "Switched to Code mode"
      }
    ],
    "isError": false
  }
}
```

### MCP Connection Flow

```
1. Client Connects
   │
   ▼
2. initialize request
   {
     "method": "initialize",
     "params": {
       "protocolVersion": "2024-11-05",
       "clientInfo": {"name": "vscode"}
     }
   }
   │
   ▼
3. Server responds
   {
     "result": {
       "protocolVersion": "2024-11-05",
       "serverInfo": {
         "name": "roo-modes-server",
         "version": "1.0.0"
       },
       "capabilities": {
         "resources": {},
         "tools": {}
       }
     }
   }
   │
   ▼
4. Client sends initialized notification
   │
   ▼
5. Ready for requests
   ├─> resources/list
   ├─> resources/read
   ├─> tools/list
   └─> tools/call
```

### MCP Tool Execution

```
Client request: tools/call
    │
    ▼
ToolHandler.call_tool(name, arguments)
    │
    ├─> Get or create session
    │   └─> SessionManager.get_session(session_id)
    │
    ├─> Validate tool name
    │   └─> Check against registered mode tools
    │
    ▼
switch_mode tool
    │
    ├─> Get session's current task
    ├─> Call orchestrator.switch_mode()
    ├─> Update task state
    │
    ▼
Return result
    {
      "content": [{
        "type": "text",
        "text": "Switched to Code mode"
      }],
      "isError": false
    }
```

### Session Management

**File:** [`roo_code/mcp/session.py`](../roo_code/mcp/session.py)

```
┌────────────────────────────────────────────┐
│         SessionManager                     │
├────────────────────────────────────────────┤
│                                            │
│  sessions: Dict[str, Session] = {}        │
│                                            │
│  ┌──────────────────────────────┐         │
│  │  get_session(session_id)     │         │
│  │  ├─> If exists: return       │         │
│  │  └─> Else: create new        │         │
│  └──────────────────────────────┘         │
│                                            │
│  ┌──────────────────────────────┐         │
│  │  Session                     │         │
│  │  - session_id                │         │
│  │  - current_task              │         │
│  │  - created_at                │         │
│  │  - last_accessed             │         │
│  │  - message_count             │         │
│  └──────────────────────────────┘         │
│                                            │
│  ┌──────────────────────────────┐         │
│  │  Cleanup (periodic)          │         │
│  │  └─> Remove expired sessions │         │
│  └──────────────────────────────┘         │
└────────────────────────────────────────────┘
```

---

## Workflow Orchestration Flow

### Multi-Phase Workflow Pattern

**File:** [`examples/recreate_python_interpreter.py`](../examples/recreate_python_interpreter.py)

Complex projects use orchestrator pattern:

```
┌──────────────────────────────────────────────────┐
│      PythonInterpreterWorkflowRunner             │
│                                                  │
│  Phase 1: Planning (architect mode)             │
│    └─> Create project structure                 │
│    └─> Define requirements                      │
│                                                  │
│  Phase 2: Core Implementation (code mode)       │
│    └─> Implement REPL loop                      │
│    └─> Add input handling                       │
│                                                  │
│  Phase 3: Features (code mode)                  │
│    └─> Syntax highlighting                      │
│    └─> Command history                          │
│    └─> Auto-completion                          │
│                                                  │
│  Phase 4: Testing (code mode)                   │
│    └─> Write tests                              │
│    └─> Run test suite                           │
│                                                  │
│  Phase 5: Documentation (architect mode)        │
│    └─> Write README                             │
│    └─> Create usage examples                    │
└──────────────────────────────────────────────────┘
```

### Workflow Execution

```
WorkflowRunner
    │
    ├─> Initialize ModeAgent in orchestrator mode
    │
    ▼
For each phase:
    │
    ├─> Load checkpoint (if resuming)
    │
    ├─> Execute subtasks
    │   │
    │   ├─> Create subtask via agent.create_subtask()
    │   │   └─> Task(mode=phase.mode, message=subtask.message)
    │   │
    │   ├─> Execute subtask via agent.run()
    │   │   └─> AI performs work in specified mode
    │   │
    │   └─> Store result
    │
    ├─> Save checkpoint
    │   └─> {phase_id, status, task_results}
    │
    └─> Continue to next phase
    │
    ▼
Workflow complete
```

### Checkpoint System

```python
@dataclass
class WorkflowState:
    phases: List[PhaseSpec]
    current_phase_idx: int = 0
    total_subtasks_completed: int = 0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    checkpoint_file: Optional[Path] = None

# Save checkpoint
checkpoint_data = {
    "current_phase_idx": state.current_phase_idx,
    "phases": [
        {
            "phase_id": p.phase_id,
            "status": p.status.value,
            "task_results": p.task_results,
            "error": p.error
        }
        for p in state.phases
    ],
    "total_subtasks_completed": state.total_subtasks_completed,
    "started_at": state.started_at.isoformat()
}

# Resume from checkpoint
with open(checkpoint_file) as f:
    checkpoint = json.load(f)
    state.current_phase_idx = checkpoint["current_phase_idx"]
    # ... restore state
```

---

## Complete Request-Response Cycles

### Example 1: Simple File Creation

```
┌─────────────────────────────────────────────────────────┐
│  User: "Create a hello.py file with hello world"       │
└────────────────┬────────────────────────────────────────┘
                 │
                 ▼
        ┌─────────────────┐
        │ Agent.run()     │
        └────────┬────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────┐
│ Iteration 1                                             │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  1. Build request:                                     │
│     System: "You are a helpful AI assistant..."       │
│     Messages: [{"role": "user", "content": "Create"}] │
│     Tools: [read_file, write_to_file, ...]           │
│                                                         │
│  2. client.create_message() → ApiStream               │
│                                                         │
│  3. AI Response (streaming):                           │
│     [text] "I'll create a hello world Python file"    │
│     [tool_use] {                                       │
│       "id": "toolu_abc123",                           │
│       "name": "write_to_file",                        │
│       "input": {                                       │
│         "path": "hello.py",                           │
│         "content": "print('Hello, World!')\n",        │
│         "line_count": 1                               │
│       }                                                 │
│     }                                                   │
│                                                         │
│  4. Extract tool use                                   │
│     └─> ToolUse(id=toolu_abc123, name=write_to_file) │
│                                                         │
│  5. Execute tool:                                      │
│     registry.execute(tool_use)                        │
│       └─> get("write_to_file")                        │
│       └─> tool.execute_with_recovery({path, content}) │
│       └─> Create file hello.py                        │
│       └─> Return ToolResult(                          │
│             tool_use_id="toolu_abc123",               │
│             content="Successfully created hello.py",  │
│             is_error=False                            │
│           )                                             │
│                                                         │
│  6. Add tool result to messages:                       │
│     [{"role": "user", "content": [                    │
│       {"type": "tool_result",                         │
│        "tool_use_id": "toolu_abc123",                 │
│        "content": "Successfully created..."}          │
│     ]}]                                                 │
└─────────────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────┐
│ Iteration 2                                             │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  1. Send updated messages to AI                        │
│                                                         │
│  2. AI Response:                                        │
│     [text] "I've created hello.py with a hello world" │
│            "message. The file is ready to run."        │
│     (No tool_use - task complete)                      │
│                                                         │
│  3. No tool use detected                               │
│     └─> Return final answer                           │
└─────────────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────┐
│  Result: "I've created hello.py with a hello world     │
│           message. The file is ready to run."          │
└─────────────────────────────────────────────────────────┘
```

### Example 2: Mode Switch Workflow

```
┌─────────────────────────────────────────────────────────┐
│  User: "Design a REST API then implement it"           │
└────────────────┬────────────────────────────────────────┘
                 │
                 ▼
      ModeAgent (architect mode)
                 │
                 ▼
┌─────────────────────────────────────────────────────────┐
│ Phase 1: Design (architect mode)                        │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Iteration 1:                                           │
│    AI creates design document using write_to_file      │
│    → API_DESIGN.md created                             │
│                                                         │
│  Iteration 2:                                           │
│    AI creates architecture diagram                     │
│    → ARCHITECTURE.md created                           │
│                                                         │
│  Iteration 3:                                           │
│    AI decides implementation needed                     │
│    [tool_use] {                                         │
│      "name": "switch_mode",                            │
│      "input": {                                         │
│        "mode_slug": "code",                            │
│        "reason": "Ready to implement the API design"   │
│      }                                                   │
│    }                                                     │
│    → Mode switched to code                             │
└─────────────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────┐
│ Phase 2: Implementation (code mode)                     │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  (System prompt now from code mode)                    │
│  (Can use edit + command tools)                        │
│                                                         │
│  Iteration 1:                                           │
│    AI reads design: read_file("API_DESIGN.md")        │
│                                                         │
│  Iteration 2:                                           │
│    AI creates main.py with FastAPI code                │
│    → write_to_file("main.py", ...)                    │
│                                                         │
│  Iteration 3:                                           │
│    AI creates models.py                                │
│    → write_to_file("models.py", ...)                  │
│                                                         │
│  Iteration 4:                                           │
│    AI tests the API                                     │
│    → execute_command("python main.py")                │
│                                                         │
│  Iteration 5:                                           │
│    [tool_use] attempt_completion                       │
│    → Task complete                                      │
└─────────────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────┐
│  Result: REST API designed and implemented              │
│  - API_DESIGN.md (design doc)                          │
│  - ARCHITECTURE.md (architecture)                       │
│  - main.py (FastAPI implementation)                    │
│  - models.py (data models)                             │
└─────────────────────────────────────────────────────────┘
```

### Example 3: MCP Tool Integration

```
External MCP Client (e.g., VSCode)
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│  JSON-RPC Request: tools/call                           │
│  {                                                      │
│    "method": "tools/call",                             │
│    "params": {                                          │
│      "name": "new_task",                               │
│      "arguments": {                                     │
│        "mode": "code",                                  │
│        "message": "Create UserService"                 │
│      }                                                   │
│    }                                                     │
│  }                                                       │
└────────────────┬────────────────────────────────────────┘
                 │
                 ▼
     McpModesServer.run()
                 │
                 ▼
   ToolHandler.call_tool("new_task", {...})
                 │
                 ▼
┌─────────────────────────────────────────────────────────┐
│  1. Get/create session                                  │
│     session = session_manager.get_session("sess_123")  │
│                                                         │
│  2. Get session's current task                         │
│     parent_task = session.current_task                 │
│                                                         │
│  3. Create new subtask                                  │
│     child_task = orchestrator.create_task(             │
│       mode_slug="code",                                │
│       initial_message="Create UserService",           │
│       parent_task=parent_task                         │
│     )                                                   │
│                                                         │
│  4. Link tasks                                          │
│     parent_task.child_task_ids.append(child_task.id)  │
│                                                         │
│  5. Set as current task                                │
│     session.current_task = child_task                  │
└─────────────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────┐
│  JSON-RPC Response                                      │
│  {                                                      │
│    "result": {                                          │
│      "content": [{                                      │
│        "type": "text",                                  │
│        "text": "Created new task in code mode: ..."    │
│      }],                                                 │
│      "isError": false                                   │
│    }                                                     │
│  }                                                       │
└─────────────────────────────────────────────────────────┘
                 │
                 ▼
          MCP Client
    (Now operating in new task context)
```

---

## Summary

The roo-code-python system provides a flexible, powerful framework for building AI agents:

### Key Architectural Principles

1. **Separation of Concerns**
   - [`Client`](../roo_code/client.py:28): AI provider communication
   - [`Agent`](../roo_code/agent.py:14): Task coordination & iteration
   - [`ToolRegistry`](../roo_code/tools.py:465): Tool management & execution
   - [`Stream`](../roo_code/stream.py:8): Response handling

2. **Extensibility**
   - Custom tools via [`Tool`](../roo_code/tools.py:56) class
   - Multiple provider support via [`BaseProvider`](../roo_code/providers/base.py)
   - Mode customization via YAML configs
   - MCP server for external integration

3. **Reliability**
   - Tool aliasing for backward compatibility
   - Error recovery with retry logic
   - Circuit breakers for failing tools
   - Repetition detection to prevent loops

4. **Mode System**
   - Tool restriction enforcement
   - File editing permissions
   - Task lifecycle management
   - Mode switching and subtask creation

5. **Workflow Support**
   - Multi-phase orchestration
   - Checkpoint/resume capability
   - Progress tracking
   - Hierarchical task management

### Data Flow Summary

```
User Request
    ↓
Agent (coordination)
    ↓
Client (AI communication)
    ↓
Provider (API)
    ↓
Stream (response handling)
    ↓
ToolRegistry (execution)
    ↓
Tool (implementation)
    ↓
Result
    ↓
Back to Agent (iteration)
    ↓
Final Answer
```

This architecture enables complex autonomous behaviors while maintaining control, reliability, and extensibility.