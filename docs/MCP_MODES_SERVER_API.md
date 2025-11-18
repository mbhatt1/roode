# MCP Modes Server - API Reference

Complete API reference for the MCP Modes Server. This document provides detailed specifications for all tools, resources, schemas, and error handling.

## Table of Contents

1. [Overview](#overview)
2. [Resources API](#resources-api)
3. [Tools API](#tools-api)
4. [Error Handling](#error-handling)
5. [Data Types](#data-types)
6. [Examples](#examples)

---

## Overview

### Protocol

The MCP Modes Server implements the Model Context Protocol using JSON-RPC 2.0 over stdin/stdout.

**Communication Format:**
- Transport: stdin/stdout
- Encoding: UTF-8
- Delimiter: Newline (`\n`)
- Protocol: JSON-RPC 2.0

**Base Message Structure:**

```typescript
interface JsonRpcRequest {
  jsonrpc: "2.0";
  id: number | string;
  method: string;
  params?: object;
}

interface JsonRpcResponse {
  jsonrpc: "2.0";
  id: number | string;
  result?: any;
  error?: {
    code: number;
    message: string;
    data?: any;
  };
}

interface JsonRpcNotification {
  jsonrpc: "2.0";
  method: string;
  params?: object;
}
```

### Initialization

Before using any API methods, clients must initialize the connection:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "initialize",
  "params": {
    "protocolVersion": "2024-11-05",
    "capabilities": {},
    "clientInfo": {
      "name": "client-name",
      "version": "1.0.0"
    }
  }
}
```

**Response:**

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "protocolVersion": "2024-11-05",
    "capabilities": {
      "resources": { "listChanged": false },
      "tools": { "listChanged": false }
    },
    "serverInfo": {
      "name": "roo-modes-server",
      "version": "1.0.0"
    }
  }
}
```

After receiving the response, send initialized notification:

```json
{
  "jsonrpc": "2.0",
  "method": "notifications/initialized",
  "params": {}
}
```

---

## Resources API

Resources represent modes and their configurations using the URI scheme `mode://{slug}[/subresource]`.

### resources/list

List all available mode resources.

#### Request

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "resources/list",
  "params": {}
}
```

#### Response

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "result": {
    "resources": [
      {
        "uri": "mode://code",
        "name": "💻 Code",
        "mimeType": "application/json",
        "description": "Full configuration for code mode"
      },
      {
        "uri": "mode://code/config",
        "name": "💻 Code - Configuration",
        "mimeType": "application/json",
        "description": "Structured configuration for code mode"
      },
      {
        "uri": "mode://code/system_prompt",
        "name": "💻 Code - System Prompt",
        "mimeType": "text/plain",
        "description": "System prompt for code mode"
      }
    ]
  }
}
```

#### Schema

```typescript
interface ListResourcesResponse {
  resources: Resource[];
}

interface Resource {
  uri: string;           // Resource URI (e.g., "mode://code")
  name: string;          // Human-readable name
  mimeType: string;      // MIME type of resource content
  description: string;   // Resource description
}
```

### resources/read

Read a specific mode resource.

#### Request

```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "resources/read",
  "params": {
    "uri": "mode://code"
  }
}
```

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| uri | string | Yes | Resource URI to read |

**URI Formats:**
- `mode://{slug}` - Full mode configuration
- `mode://{slug}/config` - Structured configuration only
- `mode://{slug}/system_prompt` - System prompt text

#### Response

**For Full Mode (`mode://code`):**

```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "result": {
    "contents": [
      {
        "uri": "mode://code",
        "mimeType": "application/json",
        "text": "{\"slug\":\"code\",\"name\":\"💻 Code\",\"source\":\"builtin\",\"description\":\"Write, modify, or refactor code\",\"when_to_use\":\"Use this mode when...\",\"role_definition\":\"You are an expert programmer...\",\"custom_instructions\":\"...\",\"tool_groups\":{\"read\":{\"enabled\":true},\"edit\":{\"enabled\":true},\"browser\":{\"enabled\":true},\"command\":{\"enabled\":true},\"mcp\":{\"enabled\":true},\"modes\":{\"enabled\":true}}}"
      }
    ]
  }
}
```

**For Config Resource (`mode://code/config`):**

```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "result": {
    "contents": [
      {
        "uri": "mode://code/config",
        "mimeType": "application/json",
        "text": "{\"slug\":\"code\",\"name\":\"💻 Code\",\"source\":\"builtin\",\"groups\":[\"read\",\"edit\",\"browser\",\"command\",\"mcp\",\"modes\"],\"description\":\"Write, modify, or refactor code\",\"when_to_use\":\"Use this mode when...\"}"
      }
    ]
  }
}
```

**For System Prompt (`mode://code/system_prompt`):**

```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "result": {
    "contents": [
      {
        "uri": "mode://code/system_prompt",
        "mimeType": "text/plain",
        "text": "You are Roo, an expert programmer...\n[Full system prompt text]"
      }
    ]
  }
}
```

#### Schema

```typescript
interface ReadResourceResponse {
  contents: ResourceContent[];
}

interface ResourceContent {
  uri: string;        // Resource URI
  mimeType: string;   // Content MIME type
  text: string;       // Resource content as string
}
```

#### Errors

| Code | Message | Description |
|------|---------|-------------|
| -32004 | Validation Error | Invalid URI format |
| -32001 | Mode Not Found | Mode slug doesn't exist |
| -32004 | Validation Error | Unknown subresource |

---

## Tools API

The server provides 7 tools for mode operations.

### tools/list

List all available tools with their schemas.

#### Request

```json
{
  "jsonrpc": "2.0",
  "id": 4,
  "method": "tools/list",
  "params": {}
}
```

#### Response

```json
{
  "jsonrpc": "2.0",
  "id": 4,
  "result": {
    "tools": [
      {
        "name": "list_modes",
        "description": "List all available modes with their metadata",
        "inputSchema": {
          "type": "object",
          "properties": {
            "source": {
              "type": "string",
              "enum": ["builtin", "global", "project", "all"],
              "description": "Filter modes by source (default: all)"
            }
          }
        }
      },
      {
        "name": "get_mode_info",
        "description": "Get detailed information about a specific mode",
        "inputSchema": {
          "type": "object",
          "properties": {
            "mode_slug": {
              "type": "string",
              "description": "Slug of the mode to get info for"
            },
            "include_system_prompt": {
              "type": "boolean",
              "description": "Include the full system prompt (default: false)"
            }
          },
          "required": ["mode_slug"]
        }
      }
    ]
  }
}
```

### tools/call

Execute a tool.

#### Request Format

```json
{
  "jsonrpc": "2.0",
  "id": 5,
  "method": "tools/call",
  "params": {
    "name": "tool_name",
    "arguments": {
      "param1": "value1",
      "param2": "value2"
    }
  }
}
```

#### Response Format

```json
{
  "jsonrpc": "2.0",
  "id": 5,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "Tool execution result"
      }
    ],
    "metadata": {
      "key": "value"
    }
  }
}
```

---

## Tool: list_modes

List all available modes with their metadata.

### Input Schema

```typescript
interface ListModesInput {
  source?: "builtin" | "global" | "project" | "all";  // Default: "all"
}
```

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| source | string | No | "all" | Filter modes by source |

**Valid values:**
- `builtin` - Built-in modes only (code, architect, ask, debug, orchestrator)
- `global` - Global custom modes (`~/.roo-code/modes.yaml`)
- `project` - Project-specific modes (`.roomodes` file)
- `all` - All modes from all sources

### Request Example

```json
{
  "jsonrpc": "2.0",
  "id": 10,
  "method": "tools/call",
  "params": {
    "name": "list_modes",
    "arguments": {
      "source": "builtin"
    }
  }
}
```

### Response Example

```json
{
  "jsonrpc": "2.0",
  "id": 10,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "Available modes:\n\n1. code (💻 Code) - builtin\n   Description: Write, modify, or refactor code\n   Tool groups: read, edit, browser, command, mcp, modes\n\n2. architect (🏗️ Architect) - builtin\n   Description: Plan, design, or strategize before implementation\n   Tool groups: read, browser, mcp, modes, edit (\\.md$)\n\n3. ask (❓ Ask) - builtin\n   Description: Get explanations, documentation, or answers\n   Tool groups: read, browser, mcp, modes\n\n4. debug (🪲 Debug) - builtin\n   Description: Troubleshoot issues, investigate errors\n   Tool groups: read, edit, browser, command, mcp, modes\n\n5. orchestrator (🪃 Orchestrator) - builtin\n   Description: Coordinate complex multi-step projects\n   Tool groups: modes\n"
      }
    ]
  }
}
```

### Response Schema

```typescript
interface ListModesOutput {
  content: [
    {
      type: "text";
      text: string;  // Formatted list of modes
    }
  ];
}
```

---

## Tool: get_mode_info

Get detailed information about a specific mode.

### Input Schema

```typescript
interface GetModeInfoInput {
  mode_slug: string;                   // Required
  include_system_prompt?: boolean;     // Default: false
}
```

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| mode_slug | string | Yes | - | Slug of the mode to query |
| include_system_prompt | boolean | No | false | Include full system prompt in response |

### Request Example

```json
{
  "jsonrpc": "2.0",
  "id": 11,
  "method": "tools/call",
  "params": {
    "name": "get_mode_info",
    "arguments": {
      "mode_slug": "architect",
      "include_system_prompt": false
    }
  }
}
```

### Response Example

```json
{
  "jsonrpc": "2.0",
  "id": 11,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "Mode: 🏗️ Architect (architect)\nSource: builtin\nDescription: Plan, design, or strategize before implementation\n\nWhen to use:\nUse this mode when you need to plan, design, or strategize before implementation...\n\nTool Groups:\n✓ read\n✓ edit (restricted to: \\.md$)\n✓ browser\n✗ command (not available)\n✓ mcp\n✓ modes\n\nCustom Instructions:\n1. Do some information gathering...\n2. Ask clarifying questions...\n3. Create actionable todo lists...\n"
      }
    ]
  }
}
```

### Response Schema

```typescript
interface GetModeInfoOutput {
  content: [
    {
      type: "text";
      text: string;  // Formatted mode information
    }
  ];
}
```

### Errors

| Code | Message | Description |
|------|---------|-------------|
| -32004 | Validation Error | Invalid mode slug format |
| -32001 | Mode Not Found | Mode doesn't exist |

---

## Tool: create_task

Create a new task in a specific mode.

### Input Schema

```typescript
interface CreateTaskInput {
  mode_slug: string;                // Required
  initial_message?: string;         // Optional
  parent_session_id?: string;       // Optional, for subtasks
}
```

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| mode_slug | string | Yes | Mode to use for this task |
| initial_message | string | No | Initial user message for the task |
| parent_session_id | string | No | Parent session ID if creating a subtask |

### Request Example

```json
{
  "jsonrpc": "2.0",
  "id": 12,
  "method": "tools/call",
  "params": {
    "name": "create_task",
    "arguments": {
      "mode_slug": "code",
      "initial_message": "Create a new Python module for data processing"
    }
  }
}
```

### Response Example

```json
{
  "jsonrpc": "2.0",
  "id": 12,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "Task created successfully\n\nSession ID: sess_1a2b3c4d5e6f\nTask ID: task_7g8h9i0j1k2l\nMode: code (💻 Code)\nState: active\n\nUse this session_id for subsequent operations."
      }
    ],
    "metadata": {
      "session_id": "sess_1a2b3c4d5e6f",
      "task_id": "task_7g8h9i0j1k2l",
      "mode_slug": "code"
    }
  }
}
```

### Response Schema

```typescript
interface CreateTaskOutput {
  content: [
    {
      type: "text";
      text: string;  // Success message with session info
    }
  ];
  metadata: {
    session_id: string;   // Unique session identifier
    task_id: string;      // Unique task identifier
    mode_slug: string;    // Mode slug
  };
}
```

### Errors

| Code | Message | Description |
|------|---------|-------------|
| -32004 | Validation Error | Invalid mode slug or parent session ID |
| -32001 | Mode Not Found | Mode doesn't exist |
| -32002 | Task Not Found | Parent session not found |

---

## Tool: switch_mode

Switch a task to a different mode.

### Input Schema

```typescript
interface SwitchModeInput {
  session_id: string;       // Required
  new_mode_slug: string;    // Required
  reason?: string;          // Optional
}
```

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| session_id | string | Yes | Session ID of the task to switch |
| new_mode_slug | string | Yes | Slug of the mode to switch to |
| reason | string | No | Reason for switching modes |

### Request Example

```json
{
  "jsonrpc": "2.0",
  "id": 13,
  "method": "tools/call",
  "params": {
    "name": "switch_mode",
    "arguments": {
      "session_id": "sess_1a2b3c4d5e6f",
      "new_mode_slug": "debug",
      "reason": "Need to investigate a runtime error"
    }
  }
}
```

### Response Example

```json
{
  "jsonrpc": "2.0",
  "id": 13,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "Mode switched successfully\n\nSession: sess_1a2b3c4d5e6f\nOld mode: code\nNew mode: debug\nReason: Need to investigate a runtime error\n\nNew tool groups:\n✓ read\n✓ edit\n✓ browser\n✓ command\n✓ mcp\n✓ modes\n"
      }
    ],
    "metadata": {
      "old_mode": "code",
      "new_mode": "debug"
    }
  }
}
```

### Response Schema

```typescript
interface SwitchModeOutput {
  content: [
    {
      type: "text";
      text: string;  // Switch confirmation with new capabilities
    }
  ];
  metadata: {
    old_mode: string;
    new_mode: string;
  };
}
```

### Errors

| Code | Message | Description |
|------|---------|-------------|
| -32004 | Validation Error | Invalid session ID or mode slug |
| -32002 | Task Not Found | Session doesn't exist |
| -32003 | Session Expired | Session timed out |
| -32001 | Mode Not Found | New mode doesn't exist |

---

## Tool: get_task_info

Get information about a task/session.

### Input Schema

```typescript
interface GetTaskInfoInput {
  session_id: string;            // Required
  include_messages?: boolean;    // Default: false
  include_hierarchy?: boolean;   // Default: false
}
```

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| session_id | string | Yes | - | Session ID to query |
| include_messages | boolean | No | false | Include conversation history |
| include_hierarchy | boolean | No | false | Include parent/child task info |

### Request Example

```json
{
  "jsonrpc": "2.0",
  "id": 14,
  "method": "tools/call",
  "params": {
    "name": "get_task_info",
    "arguments": {
      "session_id": "sess_1a2b3c4d5e6f",
      "include_messages": false,
      "include_hierarchy": true
    }
  }
}
```

### Response Example

```json
{
  "jsonrpc": "2.0",
  "id": 14,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "Task Information\n\nSession ID: sess_1a2b3c4d5e6f\nTask ID: task_7g8h9i0j1k2l\nMode: code (💻 Code)\nState: active\nCreated: 2025-01-13T10:30:00.000Z\n\nSession Age: 300s\nIdle Time: 60s\n\nHierarchy:\n  Parent Task: task_parent123\n  Child Tasks: task_child456, task_child789\n"
      }
    ]
  }
}
```

### Response Schema

```typescript
interface GetTaskInfoOutput {
  content: [
    {
      type: "text";
      text: string;  // Formatted task information
    }
  ];
}
```

### Errors

| Code | Message | Description |
|------|---------|-------------|
| -32004 | Validation Error | Invalid session ID format |
| -32002 | Task Not Found | Session doesn't exist |
| -32003 | Session Expired | Session timed out |

---

## Tool: validate_tool_use

Check if a tool can be used in the current mode.

### Input Schema

```typescript
interface ValidateToolUseInput {
  session_id: string;      // Required
  tool_name: string;       // Required
  file_path?: string;      // Optional, for edit operations
}
```

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| session_id | string | Yes | Session ID |
| tool_name | string | Yes | Name of tool to validate |
| file_path | string | No | File path (for edit operations) |

### Request Example

```json
{
  "jsonrpc": "2.0",
  "id": 15,
  "method": "tools/call",
  "params": {
    "name": "validate_tool_use",
    "arguments": {
      "session_id": "sess_1a2b3c4d5e6f",
      "tool_name": "write_to_file",
      "file_path": "config.json"
    }
  }
}
```

### Response Example (Allowed)

```json
{
  "jsonrpc": "2.0",
  "id": 15,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "Tool validation result\n\nTool: write_to_file\nSession: sess_1a2b3c4d5e6f\nMode: code\n\nResult: ✓ Allowed\n"
      }
    ]
  }
}
```

### Response Example (Blocked)

```json
{
  "jsonrpc": "2.0",
  "id": 15,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "Tool validation result\n\nTool: write_to_file\nSession: sess_architect123\nMode: architect\nFile: config.json\n\nResult: ❌ Not allowed\nReason: Tool group 'edit' is restricted to files matching: \\.md$\n"
      }
    ]
  }
}
```

### Response Schema

```typescript
interface ValidateToolUseOutput {
  content: [
    {
      type: "text";
      text: string;  // Validation result with reason if blocked
    }
  ];
}
```

### Errors

| Code | Message | Description |
|------|---------|-------------|
| -32004 | Validation Error | Invalid session ID or tool name |
| -32002 | Task Not Found | Session doesn't exist |

---

## Tool: complete_task

Mark a task as completed, failed, or cancelled.

### Input Schema

```typescript
interface CompleteTaskInput {
  session_id: string;                              // Required
  status: "completed" | "failed" | "cancelled";   // Required
  result?: string;                                  // Optional
}
```

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| session_id | string | Yes | Session ID to complete |
| status | string | Yes | Final status (completed, failed, or cancelled) |
| result | string | No | Completion result or error message |

### Request Example

```json
{
  "jsonrpc": "2.0",
  "id": 16,
  "method": "tools/call",
  "params": {
    "name": "complete_task",
    "arguments": {
      "session_id": "sess_1a2b3c4d5e6f",
      "status": "completed",
      "result": "Successfully created the Python module with all required functions"
    }
  }
}
```

### Response Example

```json
{
  "jsonrpc": "2.0",
  "id": 16,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "Task completed successfully\n\nSession: sess_1a2b3c4d5e6f\nTask: task_7g8h9i0j1k2l\nStatus: completed\nResult: Successfully created the Python module with all required functions\n\nThe session will be cleaned up automatically."
      }
    ]
  }
}
```

### Response Schema

```typescript
interface CompleteTaskOutput {
  content: [
    {
      type: "text";
      text: string;  // Completion confirmation
    }
  ];
}
```

### Errors

| Code | Message | Description |
|------|---------|-------------|
| -32004 | Validation Error | Invalid session ID or status |
| -32002 | Task Not Found | Session doesn't exist |
| -32003 | Session Expired | Session timed out |

---

## Error Handling

### Error Response Format

```typescript
interface ErrorResponse {
  jsonrpc: "2.0";
  id: number | string | null;
  error: {
    code: number;
    message: string;
    data?: any;
  };
}
```

### Error Codes

| Code | Name | Category | Description |
|------|------|----------|-------------|
| -32700 | Parse Error | Protocol | Invalid JSON received |
| -32600 | Invalid Request | Protocol | Request structure is invalid |
| -32601 | Method Not Found | Protocol | Unknown method name |
| -32602 | Invalid Params | Protocol | Invalid method parameters |
| -32603 | Internal Error | Server | Server internal error |
| -32001 | Mode Not Found | Application | Requested mode doesn't exist |
| -32002 | Task Not Found | Application | Session/task doesn't exist |
| -32003 | Session Expired | Application | Session timed out |
| -32004 | Validation Error | Application | Input validation failed |
| -32005 | Tool Restriction Error | Application | Tool not allowed in mode |
| -32006 | File Restriction Error | Application | File editing not allowed |

### Error Examples

#### Mode Not Found

```json
{
  "jsonrpc": "2.0",
  "id": 10,
  "error": {
    "code": -32001,
    "message": "Mode not found",
    "data": "Mode not found: invalid-mode. Available: code, architect, ask, debug, orchestrator"
  }
}
```

#### Session Expired

```json
{
  "jsonrpc": "2.0",
  "id": 11,
  "error": {
    "code": -32003,
    "message": "Session expired",
    "data": "Session sess_1a2b3c4d5e6f has expired (timeout: 3600s)"
  }
}
```

#### Tool Restriction Error

```json
{
  "jsonrpc": "2.0",
  "id": 12,
  "error": {
    "code": -32005,
    "message": "Tool restriction error",
    "data": "Tool 'write_to_file' cannot be used in 'ask' mode. Tool group 'edit' is not enabled."
  }
}
```

#### File Restriction Error

```json
{
  "jsonrpc": "2.0",
  "id": 13,
  "error": {
    "code": -32006,
    "message": "File restriction error",
    "data": "Cannot edit 'config.py' in 'architect' mode. Only files matching '\\.md$' are allowed."
  }
}
```

### Error Handling Best Practices

#### Client-Side Error Handling

```python
async def handle_request(client, method, params):
    try:
        result = await client.send_request(method, params)
        return result
        
    except McpError as e:
        if e.code == -32001:  # Mode Not Found
            logger.error(f"Invalid mode: {e.data}")
            # Show available modes
            modes = await client.send_request("tools/call", {
                "name": "list_modes",
                "arguments": {}
            })
            
        elif e.code == -32003:  # Session Expired
            logger.warning("Session expired, creating new session")
            # Create new session
            
        elif e.code in [-32005, -32006]:  # Tool/File Restriction
            logger.error(f"Permission denied: {e.message}")
            # Handle gracefully, maybe switch modes
            
        else:
            logger.exception(f"Unexpected error: {e}")
            raise
```

---

## Data Types

### Mode Configuration

```typescript
interface ModeConfig {
  slug: string;              // Unique identifier
  name: string;              // Display name with emoji
  source: "builtin" | "global" | "project";
  description?: string;      // Short description
  when_to_use?: string;      // Usage guidelines
  role_definition?: string;  // System prompt base
  custom_instructions?: string;
  tool_groups: {
    [group: string]: ToolGroupConfig;
  };
}

interface ToolGroupConfig {
  enabled: boolean;
  file_regex?: string;       // For edit restrictions
  description?: string;
}
```

### Task State

```typescript
type TaskState = 
  | "active"      // Task is running
  | "completed"   // Task finished successfully
  | "failed"      // Task failed with error
  | "cancelled";  // Task was cancelled

interface Task {
  task_id: string;
  mode_slug: string;
  state: TaskState;
  created_at: string;        // ISO 8601 timestamp
  completed_at?: string;     // ISO 8601 timestamp
  parent_task_id?: string;
  child_task_ids: string[];
  messages: Message[];
  metadata: Record<string, any>;
}
```

### Session

```typescript
interface Session {
  session_id: string;        // Unique session identifier
  task: Task;                // Associated task
  created_at: number;        // Unix timestamp
  last_activity: number;     // Unix timestamp
}
```

### Message

```typescript
interface Message {
  role: "user" | "assistant";
  content: string;
  timestamp: string;         // ISO 8601 timestamp
}
```

---

## Examples

### Complete Workflow Example

```python
import asyncio
from mcp_client import McpModesClient

async def complete_workflow():
    client = McpModesClient()
    
    # 1. Initialize
    await client.start()
    print("✓ Server initialized")
    
    # 2. List available modes
    modes_result = await client.send_request("tools/call", {
        "name": "list_modes",
        "arguments": {"source": "all"}
    })
    print("✓ Listed modes")
    
    # 3. Get detailed mode info
    mode_info = await client.send_request("tools/call", {
        "name": "get_mode_info",
        "arguments": {
            "mode_slug": "architect",
            "include_system_prompt": False
        }
    })
    print("✓ Got architect mode info")
    
    # 4. Create task in architect mode
    task_result = await client.send_request("tools/call", {
        "name": "create_task",
        "arguments": {
            "mode_slug": "architect",
            "initial_message": "Design a microservices architecture"
        }
    })
    session_id = task_result["metadata"]["session_id"]
    print(f"✓ Created task: {session_id}")
    
    # 5. Get task info
    task_info = await client.send_request("tools/call", {
        "name": "get_task_info",
        "arguments": {
            "session_id": session_id,
            "include_hierarchy": True
        }
    })
    print("✓ Retrieved task info")
    
    # 6. Validate tool use
    validation = await client.send_request("tools/call", {
        "name": "validate_tool_use",
        "arguments": {
            "session_id": session_id,
            "tool_name": "write_to_file",
            "file_path": "design.md"
        }
    })
    print("✓ Validated tool use (write to .md)")
    
    # 7. Switch to code mode
    switch_result = await client.send_request("tools/call", {
        "name": "switch_mode",
        "arguments": {
            "session_id": session_id,
            "new_mode_slug": "code",
            "reason": "Ready to implement the design"
        }
    })
    print("✓ Switched to code mode")
    
    # 8. Complete task
    complete_result = await client.send_request("tools/call", {
        "name": "complete_task",
        "arguments": {
            "session_id": session_id,
            "status": "completed",
            "result": "Architecture designed and approved"
        }
    })
    print("✓ Completed task")
    
    # 9. Cleanup
    await client.stop()
    print("✓ Server stopped")

asyncio.run(complete_workflow())
```

### Resource Access Example

```python
async def explore_resources():
    client = McpModesClient()
    await client.start()
    
    # List all resources
    resources = await client.send_request("resources/list", {})
    
    for resource in resources["resources"]:
        print(f"\nResource: {resource['uri']}")
        print(f"  Name: {resource['name']}")
        print(f"  Type: {resource['mimeType']}")
        
        # Read each resource
        content = await client.send_request("resources/read", {
            "uri": resource["uri"]
        })
        
        print(f"  Content: {content['contents'][0]['text'][:100]}...")
    
    await client.stop()

asyncio.run(explore_resources())
```

### Error Handling Example

```python
async def robust_request(client, tool_name, arguments):
    """Make a request with comprehensive error handling."""
    try:
        result = await client.send_request("tools/call", {
            "name": tool_name,
            "arguments": arguments
        })
        return result
        
    except Exception as e:
        error_code = getattr(e, 'code', None)
        
        if error_code == -32001:  # Mode Not Found
            print("Error: Mode doesn't exist")
            # List available modes
            modes = await client.send_request("tools/call", {
                "name": "list_modes",
                "arguments": {}
            })
            print("Available modes:", modes)
            
        elif error_code == -32002:  # Task Not Found
            print("Error: Session doesn't exist or expired")
            # Create new session
            
        elif error_code == -32003:  # Session Expired
            print("Error: Session timed out")
            # Handle timeout gracefully
            
        elif error_code in [-32005, -32006]:  # Restrictions
            print(f"Error: Operation not allowed - {e}")
            # Maybe switch modes or adjust request
            
        else:
            print(f"Unexpected error: {e}")
            raise

# Usage
async def main():
    client = McpModesClient()
    await client.start()
    
    # This might fail due to various reasons
    result = await robust_request(client, "create_task", {
        "mode_slug": "code",
        "initial_message": "Build a feature"
    })
    
    await client.stop()

asyncio.run(main())
```

---

## Versioning

### Protocol Version

Current protocol version: `2024-11-05`

The protocol version is specified during initialization and must match between client and server.

### API Compatibility

The MCP Modes Server follows semantic versioning:

- **Major version** (1.x.x): Breaking API changes
- **Minor version** (x.1.x): New features, backward compatible
- **Patch version** (x.x.1): Bug fixes, backward compatible

Current API version: `1.0.0`

---

## Rate Limits

The MCP Modes Server has no built-in rate limits. However:

- Session timeout limits long-running operations (default: 1 hour)
- Cleanup interval affects memory usage (default: 5 minutes)
- Client should implement its own rate limiting if needed

---

## Related Documentation

- **[User Guide](MCP_MODES_SERVER_USER_GUIDE.md)**: Installation and usage
- **[Integration Guide](MCP_MODES_SERVER_INTEGRATION.md)**: Platform integration
- **[Architecture Document](../ARCHITECTURE_MCP_MODES_SERVER.md)**: System design
- **[Main README](../roo_code/mcp/README.md)**: Server overview

---

**Last Updated**: 2025-01-13  
**API Version**: 1.0.0  
**Protocol Version**: 2024-11-05