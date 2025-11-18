# MCP Modes Server

The MCP Modes Server exposes Roo-Code's mode system through the Model Context Protocol (MCP), enabling external clients to interact with modes, manage tasks, and enforce tool restrictions.

## Architecture

The server is organized into several key components:

### Core Components

1. **protocol.py** - JSON-RPC 2.0 protocol handling
   - Message parsing and serialization
   - Error code definitions
   - Protocol validation

2. **config.py** - Server configuration management
   - Configuration loading from files and environment
   - Validation and defaults
   - Support for persistent sessions

3. **validation.py** - Input validation
   - Schema validation for tool arguments
   - URI and session ID validation
   - Input sanitization

4. **session.py** - Session and state management
   - Session lifecycle management
   - Task tracking and expiration
   - Background cleanup tasks

5. **resources.py** - Mode resource handlers
   - List available modes
   - Read mode configurations
   - Access system prompts

6. **tools.py** - Mode operation tools
   - List and query modes
   - Create and manage tasks
   - Switch modes and validate tool use

7. **server.py** - Main server implementation
   - JSON-RPC message routing
   - Request/response handling
   - Server lifecycle management

8. **__main__.py** - CLI entry point
   - Command-line argument parsing
   - Configuration loading
   - Logging setup

## Features

- **Standards-Based**: Full MCP protocol compliance (JSON-RPC 2.0)
- **Zero Dependencies**: Uses Python stdlib only
- **Async Architecture**: Built on asyncio for concurrent operations
- **Type-Safe**: Comprehensive type hints throughout
- **Stateful Sessions**: Maintains task hierarchies and conversation history
- **Security-First**: File access validation and tool restriction enforcement

## Usage

### Basic Usage

```bash
# Run with default configuration
python -m roo_code.mcp

# Run with project root
python -m roo_code.mcp --project-root /path/to/project

# Run with custom configuration
python -m roo_code.mcp --config /path/to/config.json

# Run with debug logging
python -m roo_code.mcp --log-level DEBUG
```

### Configuration

Configuration can be provided via:
1. Configuration file (JSON)
2. Environment variables
3. Command-line arguments

**Environment Variables:**
- `ROO_PROJECT_ROOT` - Project root directory
- `ROO_CONFIG_DIR` - Global config directory (default: ~/.roo-code)
- `ROO_SESSION_TIMEOUT` - Session timeout in seconds
- `ROO_LOG_LEVEL` - Logging level (DEBUG, INFO, WARNING, ERROR)
- `ROO_LOG_FILE` - Log file path

**Configuration File Format:**

```json
{
  "server": {
    "name": "roo-modes-server",
    "version": "1.0.0",
    "description": "MCP server exposing Roo-Code mode system"
  },
  "paths": {
    "project_root": null,
    "global_config_dir": "~/.roo-code"
  },
  "sessions": {
    "timeout": 3600,
    "cleanup_interval": 300,
    "persistence": {
      "enabled": false,
      "storage_path": "~/.roo-code/mcp_sessions"
    }
  },
  "logging": {
    "level": "INFO",
    "file": "~/.roo-code/mcp_modes_server.log",
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  }
}
```

### Integration with MCP Clients

For VSCode or other MCP clients, add to your MCP configuration:

```json
{
  "mcpServers": {
    "roo-modes": {
      "command": "python",
      "args": [
        "-m",
        "roo_code.mcp",
        "--project-root",
        "${workspaceFolder}"
      ],
      "env": {
        "ROO_CONFIG_DIR": "~/.roo-code",
        "PYTHONUNBUFFERED": "1"
      }
    }
  }
}
```

## Available Resources

The server exposes three types of resources per mode:

1. **Full Mode Resource** (`mode://{slug}`)
   - Complete mode configuration including all metadata
   - Tool group information
   - Custom instructions

2. **Config Resource** (`mode://{slug}/config`)
   - Structured configuration data
   - Group definitions with restrictions

3. **System Prompt Resource** (`mode://{slug}/system_prompt`)
   - The complete system prompt for the mode
   - Generated dynamically

## Available Tools

The server provides seven tools for mode operations:

1. **list_modes** - List all available modes with metadata
2. **get_mode_info** - Get detailed information about a specific mode
3. **create_task** - Create a new task in a specific mode
4. **switch_mode** - Switch a task to a different mode
5. **get_task_info** - Get information about a task/session
6. **validate_tool_use** - Check if a tool can be used in the current mode
7. **complete_task** - Mark a task as completed, failed, or cancelled

## Protocol Flow

### Initialization

```
Client → Server: initialize
Server → Client: server info + capabilities
Client → Server: notifications/initialized
```

### Resource Access

```
Client → Server: resources/list
Server → Client: List of available resources

Client → Server: resources/read (uri: mode://code)
Server → Client: Mode configuration
```

### Task Management

```
Client → Server: tools/call (create_task)
Server → Client: Session ID + Task info

Client → Server: tools/call (switch_mode)
Server → Client: Mode switched confirmation

Client → Server: tools/call (complete_task)
Server → Client: Task completion status
```

## Error Handling

The server uses standard JSON-RPC error codes plus MCP-specific codes:

- `-32700` - Parse error
- `-32600` - Invalid request
- `-32601` - Method not found
- `-32602` - Invalid params
- `-32603` - Internal error
- `-32001` - Mode not found
- `-32002` - Task not found
- `-32003` - Session expired
- `-32004` - Validation error
- `-32005` - Tool restriction error
- `-32006` - File restriction error

## Security

The server enforces security at multiple levels:

1. **Mode Configuration** - File regex patterns restrict file access
2. **Orchestrator Validation** - Tool group and file access validation
3. **Input Sanitization** - All inputs are validated and sanitized
4. **Session Management** - Automatic expiration of inactive sessions

## Logging

Logs are written to both file and stderr:
- File: `~/.roo-code/mcp_modes_server.log` (configurable)
- Stderr: For console output (stdout is reserved for JSON-RPC)

Log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL

## Development

### Running Tests

```bash
# Run all MCP tests
pytest tests/mcp/

# Run specific test file
pytest tests/mcp/test_server.py

# Run with coverage
pytest tests/mcp/ --cov=roo_code.mcp
```

### Architecture

For detailed architecture documentation, see:
- `ARCHITECTURE_MCP_MODES_SERVER.md` - Complete architecture specification
- Individual module docstrings for implementation details

## License

See the main Roo-Code project license.