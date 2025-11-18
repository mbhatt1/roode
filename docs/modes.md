# Mode/Persona System

The Roo Code Python SDK includes a complete mode/persona system that enables mode-based task orchestration, tool restriction enforcement, and intelligent task delegation.

## Overview

Modes (also called personas) are different operational contexts that change how the AI agent behaves and which tools it can use. Each mode has:

- **Role Definition**: The system prompt defining the mode's personality and capabilities
- **Tool Groups**: Which categories of tools the mode can access (read, edit, browser, command, mcp)
- **File Restrictions**: Optional regex patterns limiting which files can be edited
- **Custom Instructions**: Mode-specific guidelines and best practices

## Built-in Modes

The SDK includes five built-in modes:

### 1. Code Mode (`code`)
**When to use**: Writing, modifying, or refactoring code

- **Tool Groups**: read, edit, browser, command, mcp
- **Purpose**: General-purpose coding mode with full tool access
- **Best for**: Implementing features, fixing bugs, creating files

### 2. Architect Mode (`architect`)
**When to use**: Planning and designing before implementation

- **Tool Groups**: read, browser, mcp, edit (markdown only)
- **Purpose**: Strategic planning and design
- **File Restrictions**: Can only edit `.md` files
- **Best for**: Creating technical specifications, system architecture, planning

### 3. Ask Mode (`ask`)
**When to use**: Getting explanations and information

- **Tool Groups**: read, browser, mcp
- **Purpose**: Read-only mode for questions and analysis
- **Best for**: Understanding code, getting recommendations, learning

### 4. Debug Mode (`debug`)
**When to use**: Troubleshooting and investigating issues

- **Tool Groups**: read, edit, browser, command, mcp
- **Purpose**: Systematic problem diagnosis
- **Best for**: Finding bugs, analyzing errors, adding logging

### 5. Orchestrator Mode (`orchestrator`)
**When to use**: Complex multi-step projects requiring coordination

- **Tool Groups**: None (delegation only)
- **Purpose**: Meta-coordination across modes
- **Best for**: Breaking down complex tasks, managing workflows

## Using the Mode System

### Basic Usage

```python
from roo_code import RooClient, ProviderSettings
from roo_code.modes import ModeAgent

# Initialize client
client = RooClient(
    provider_settings=ProviderSettings(
        api_provider="anthropic",
        api_key="your-api-key",
        api_model_id="claude-sonnet-4-5"
    )
)

# Create mode-aware agent
agent = ModeAgent(
    client=client,
    mode_slug="code",  # Start in code mode
    project_root=Path.cwd()
)

# Run task
result = await agent.run("Create a new Python module")
```

### Switching Modes

Modes can be switched programmatically or the AI can request a switch:

```python
# Programmatic mode switch
success = agent.switch_mode("debug", reason="Need to investigate an error")

# The AI can also request mode switches using the switch_mode tool
# when it determines a different mode would be more appropriate
```

### Creating Subtasks

The orchestrator mode can create subtasks in different modes:

```python
# Create agent in orchestrator mode
agent = ModeAgent(client=client, mode_slug="orchestrator")

# The orchestrator can delegate to specialized modes
await agent.run(
    "Build a web scraper: first plan the architecture, "
    "then implement the code, then debug any issues"
)

# The orchestrator will create subtasks like:
# 1. Architect mode: Plan the scraper architecture
# 2. Code mode: Implement the scraper
# 3. Debug mode: Test and fix issues
```

### Getting Mode Information

```python
# Get current mode info
mode_info = agent.get_mode_info()
print(f"Current mode: {mode_info['name']}")
print(f"Available tool groups: {mode_info['groups']}")

# Get all available modes
all_modes = agent.get_all_modes()
for mode in all_modes:
    print(f"{mode['name']}: {mode['description']}")

# Get available tools in current mode
tools = agent.get_available_tools()
print(f"Available tools: {tools}")
```

## Custom Modes

You can create custom modes using YAML configuration files.

### Global Custom Modes

Create `~/.roo-code/modes.yaml`:

```yaml
customModes:
  - slug: reviewer
    name: 🔍 Code Reviewer
    roleDefinition: |
      You are an expert code reviewer focused on code quality,
      best practices, and potential issues.
    groups:
      - read
      - browser
    whenToUse: When you need to review code for quality and issues
    description: Review code for quality and best practices
    customInstructions: |
      Focus on:
      1. Code quality and readability
      2. Potential bugs or issues
      3. Performance considerations
      4. Security vulnerabilities
```

### Project-Specific Modes

Create `.roomodes` in your project root:

```yaml
customModes:
  - slug: test-writer
    name: 🧪 Test Writer
    roleDefinition: You are a test automation specialist
    groups:
      - read
      - [edit, {fileRegex: 'test_.*\.py$|.*_test\.py$'}]
    description: Write and maintain test files
```

### Mode Precedence

Modes are loaded with the following precedence:
1. **Project modes** (`.roomodes`) - highest priority
2. **Global modes** (`~/.roo-code/modes.yaml`)
3. **Built-in modes** - lowest priority

A project mode with the same slug as a built-in mode will override it.

## File Restrictions

Modes can restrict which files they can edit using regex patterns:

```yaml
customModes:
  - slug: config-editor
    name: ⚙️ Config Editor
    roleDefinition: You manage configuration files
    groups:
      - read
      - [edit, {fileRegex: '\.(json|yaml|yml|toml|ini|conf)$'}]
    description: Edit configuration files only
```

This mode can only edit files matching the regex pattern (config file extensions).

## Tool Groups

The available tool groups and their associated tools:

### Read Group
- `read_file`: Read file contents
- `list_files`: List directory contents
- `list_code_definition_names`: List code definitions
- `search_files`: Search for patterns across files

### Edit Group
- `write_to_file`: Create or overwrite files
- `apply_diff`: Apply targeted edits
- `insert_content`: Insert lines into files

### Browser Group
- `browser_action`: Interact with web pages via Puppeteer

### Command Group
- `execute_command`: Run CLI commands

### MCP Group
- `use_mcp_tool`: Use Model Context Protocol tools
- `access_mcp_resource`: Access MCP resources

### Modes Group (Always Available)
- `switch_mode`: Switch to a different mode
- `new_task`: Create a subtask in another mode

### Always Available Tools
- `ask_followup_question`: Ask the user for clarification
- `attempt_completion`: Signal task completion
- `update_todo_list`: Update task checklist

## Advanced Features

### Task Management

Each mode operates within a task context:

```python
# Get task information
task_info = agent.get_task_info()
print(f"Task ID: {task_info['task_id']}")
print(f"State: {task_info['state']}")
print(f"Messages: {task_info['message_count']}")
```

### Programmatic Mode Creation

```python
from roo_code.modes import ModeConfig, ModeSource, GroupOptions

# Create a custom mode programmatically
custom_mode = ModeConfig(
    slug="my-mode",
    name="My Custom Mode",
    role_definition="You are a specialized assistant",
    groups=["read", ("edit", GroupOptions(file_regex=r"\.py$"))],
    source=ModeSource.PROJECT
)

# Load it into the orchestrator
agent.orchestrator.modes[custom_mode.slug] = custom_mode
```

### Validation

The system enforces tool restrictions automatically:

```python
# This will raise PermissionError if the tool isn't allowed
try:
    await agent._execute_tool(ToolUse(
        name="write_to_file",
        input={"path": "test.py", "content": "..."}
    ))
except PermissionError as e:
    print(f"Tool use blocked: {e}")
```

### Reloading Modes

If you modify mode configuration files, reload them:

```python
agent.reload_modes()
```

## Best Practices

### 1. Choose the Right Mode

Start with the mode that best matches your task:
- **Planning?** Use `architect` mode
- **Coding?** Use `code` mode
- **Questions?** Use `ask` mode
- **Debugging?** Use `debug` mode
- **Complex workflows?** Use `orchestrator` mode

### 2. Use File Restrictions

When creating custom modes, use file restrictions to prevent accidental edits:

```yaml
groups:
  - [edit, {fileRegex: '\.test\.ts$'}]  # Only test files
```

### 3. Leverage the Orchestrator

For complex tasks, let the orchestrator break them down:

```python
agent = ModeAgent(client=client, mode_slug="orchestrator")
await agent.run("Build a complete web application with tests")
```

### 4. Mode-Specific Instructions

Add custom instructions to guide the AI's behavior in each mode:

```yaml
customInstructions: |
  Always:
  1. Check existing code first
  2. Follow project style guidelines
  3. Add appropriate comments
  4. Run tests after changes
```

### 5. Task Organization

Use the orchestrator to maintain clean task hierarchies:
- Parent task for overall goal
- Child tasks for specific steps
- Each child in the appropriate mode

## Examples

### Example 1: Code Review Workflow

```python
# Create architect agent for planning
agent = ModeAgent(client=client, mode_slug="architect")
review_plan = await agent.run("Create a code review checklist for our API")

# Switch to read-only mode for actual review
agent.switch_mode("ask")
review_results = await agent.run("Review the API code against the checklist")
```

### Example 2: Debug and Fix

```python
# Start in debug mode
agent = ModeAgent(client=client, mode_slug="debug")
diagnosis = await agent.run("Investigate why the login fails")

# Switch to code mode to apply fix
agent.switch_mode("code")
fix_result = await agent.run("Apply the fix for the login issue")
```

### Example 3: Complex Project

```python
# Use orchestrator for multi-step project
agent = ModeAgent(client=client, mode_slug="orchestrator")

result = await agent.run("""
Create a REST API with the following:
1. Plan the API design and structure
2. Implement the API endpoints
3. Write comprehensive tests
4. Add API documentation
""")

# The orchestrator will:
# 1. Create architect subtask for design
# 2. Create code subtask for implementation
# 3. Create test-writer subtask for tests
# 4. Create code subtask for documentation
```

## API Reference

See the main [API Reference](api-reference.md) for detailed class and method documentation.

## Troubleshooting

### Mode Not Found

```python
# Check available modes
print(agent.orchestrator.get_mode_names())
```

### Tool Blocked

```python
# Check which tools are available
print(agent.get_available_tools())

# Validate before using
is_valid, error = agent.orchestrator.validate_tool_use(
    agent.current_task,
    "write_to_file",
    {"path": "test.py"}
)
```

### File Restriction Error

```python
# Check if file can be edited in current mode
can_edit = agent.orchestrator.can_edit_file(
    agent.current_task,
    "test.py"
)
```

## Migration from Base Agent

If you're currently using the base `Agent` class:

```python
# Before
from roo_code import Agent
agent = Agent(client=client, tools=[...])

# After
from roo_code.modes import ModeAgent
agent = ModeAgent(
    client=client,
    mode_slug="code",  # Specify mode
    tools=[...]  # Additional tools still supported
)
```

The `ModeAgent` extends `Agent` so all existing functionality still works, with added mode capabilities.