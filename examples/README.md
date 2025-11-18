# Roo Code Python SDK Examples

This directory contains example scripts demonstrating various features of the Roo Code Python SDK.

## 📚 Available Examples

### 1. Basic Usage (`basic_usage.py`)
Simple examples showing fundamental SDK features:
- Creating a client
- Running basic tasks
- Handling responses

### 2. Mode Usage (`mode_usage.py`)
Comprehensive demonstration of the Mode/Persona system:
- Using different modes (code, architect, ask, debug)
- Mode switching during tasks
- File editing restrictions
- Custom mode configuration
- Orchestrator mode for complex workflows

### 3. Agentic Example (`agentic_example.py`)
Advanced agentic patterns:
- Multi-step reasoning
- Tool use and coordination
- Error handling and recovery

### 4. MCP Server Recreation Runner (`recreate_mcp_server.py`) ⭐

**A demonstration script showing how to use the orchestrator mode to recreate complex projects through coordinated multi-phase workflows.**

This script demonstrates:
- **Orchestration Patterns**: How to break down large projects into manageable phases
- **Mode Coordination**: Using different specialized modes (ask, architect, code) for different tasks
- **Progress Tracking**: Checkpoint/resume capability and detailed logging
- **Workflow Definition**: Clear phase and subtask structure with dependencies

#### Quick Start

```bash
# View the complete workflow (dry-run mode, default)
python examples/recreate_mcp_server.py

# View specific phases only
python examples/recreate_mcp_server.py --phases 1,2,3

# Run with execution (requires API keys configured)
python examples/recreate_mcp_server.py --execute

# Resume from a checkpoint
python examples/recreate_mcp_server.py --resume checkpoint.json
```

#### Command-Line Options

```
usage: recreate_mcp_server.py [-h] [--dry-run] [--execute] [--phases PHASES]
                               [--resume CHECKPOINT_FILE] [--config CONFIG_FILE]
                               [--project-root PROJECT_ROOT]

Options:
  --dry-run              Show what would be done without executing (default)
  --execute              Actually execute the workflow
  --phases PHASES        Comma-separated list of phase IDs to run (e.g., '1,2,3')
  --resume CHECKPOINT_FILE
                         Resume from a checkpoint file
  --config CONFIG_FILE   Load workflow configuration from YAML file
  --project-root PROJECT_ROOT
                         Project root directory (default: current directory)
```

#### Workflow Phases

The script demonstrates a 9-phase workflow for recreating the MCP Modes Server:

1. **System Analysis** - Analyze existing mode system (ask mode)
2. **MCP Protocol Research** - Research protocol requirements (ask mode)
3. **Architecture Design** - Design system architecture (architect mode)
4. **Core Infrastructure** - Implement protocol, config, validation (code mode)
5. **Session Management** - Implement session handling (code mode)
6. **Resources and Tools** - Implement MCP resources and tools (code mode)
7. **Server Core** - Implement main server and CLI (code mode)
8. **Comprehensive Testing** - Create test suites (code mode)
9. **Documentation** - Create user guides and API docs (architect mode)

Each phase contains multiple subtasks with:
- **Mode specification**: Which mode to use
- **Clear objectives**: What to accomplish
- **Expected outputs**: Files/artifacts to create
- **Dependencies**: What must be completed first
- **Detailed instructions**: Context and scope for the task

#### Key Patterns Demonstrated

**1. Proper Subtask Structure**

```python
SubtaskSpec(
    mode="code",
    description="Clear one-sentence goal",
    message="""Detailed instructions including:
    1. What to implement
    2. Key requirements
    3. Files to create/modify
    4. Acceptance criteria
    
    Provide full context so the subtask is self-contained.""",
    expected_outputs=["file1.py", "file2.py"],
    dependencies=["previous_subtask_output"],
)
```

**2. Mode Selection Strategy**

- **ask mode**: Analysis, research, understanding existing code
- **architect mode**: Planning, design, documentation (can only edit .md files)
- **code mode**: Implementation, testing (can edit all code files)
- **debug mode**: Troubleshooting, investigation
- **orchestrator mode**: Breaking down and delegating complex multi-step projects

**3. Progress Management**

```python
# Checkpoint after each subtask
runner.save_checkpoint()

# Resume from checkpoint
runner.load_checkpoint()

# Track status
phase.status = PhaseStatus.RUNNING
phase.started_at = datetime.now()
```

**4. Error Handling**

```python
try:
    success, error = await execute_subtask(subtask, phase)
    if not success:
        phase.status = PhaseStatus.FAILED
        phase.error = error
        return False
except Exception as e:
    logger.error(f"Unexpected error: {e}")
    return False
```

#### Output Example

```
================================================================================
MCP MODES SERVER RECREATION WORKFLOW
================================================================================

Mode: DRY RUN (Demonstration Only)
Project Root: /path/to/project
Total Phases: 9
Total Subtasks: 27

--------------------------------------------------------------------------------
PHASES:
--------------------------------------------------------------------------------

⏸️  Phase 1: System Analysis
   Analyze existing mode system and understand requirements
   Subtasks: 1
     ❓ [ask] Analyze mode system architecture

🏗️  Phase 3: Architecture Design
   Design the MCP Modes Server architecture
   Subtasks: 1
     🏗️  [architect] Design system architecture

💻 Phase 4: Core Infrastructure Implementation
   Implement protocol, config, and validation infrastructure
   Subtasks: 3
     💻 [code] Implement MCP protocol types and messages
     💻 [code] Implement configuration management
     💻 [code] Implement validation utilities

...
```

#### Using This Pattern in Your Projects

This script serves as a reference implementation for:

1. **Project Templates**: Adapt the phase structure for your project type
2. **Team Workflows**: Define standard workflows for common tasks
3. **Automation**: Build automated project scaffolding tools
4. **Documentation**: Show the actual workflow used to build features
5. **Training**: Teach developers effective orchestration patterns

To create a similar runner for your project:

1. Define your phases and subtasks in `_initialize_workflow()`
2. Specify which mode should handle each subtask
3. Provide detailed, self-contained instructions for each subtask
4. Include dependencies and expected outputs
5. Add checkpoint/resume capability for long workflows

#### Configuration Files

You can externalize the workflow definition to YAML:

```yaml
# workflow_config.yaml
phases:
  - id: 1
    name: "Analysis Phase"
    description: "Understand requirements"
    subtasks:
      - mode: "ask"
        description: "Analyze existing system"
        message: "Detailed instructions here..."
        expected_outputs: ["analysis.md"]
```

Then load it with:

```bash
python recreate_mcp_server.py --config workflow_config.yaml
```

## 🚀 Running the Examples

### Prerequisites

1. Install the SDK:
   ```bash
   cd roo-code-python
   pip install -e .
   ```

2. Set up API credentials:
   ```bash
   export ANTHROPIC_API_KEY=your-api-key
   # or
   export OPENAI_API_KEY=your-api-key
   ```

### Running Examples

```bash
# Run individual examples
python examples/basic_usage.py
python examples/mode_usage.py
python examples/agentic_example.py

# Run the MCP server recreation demo
python examples/recreate_mcp_server.py

# Run with different options
python examples/recreate_mcp_server.py --phases 1,2 --dry-run
```

## 📖 Additional Resources

- **[Main README](../README.md)**: SDK overview and installation
- **[Mode System Documentation](../docs/modes.md)**: Detailed mode system guide
- **[MCP Server Architecture](../ARCHITECTURE_MCP_MODES_SERVER.md)**: Technical architecture
- **[MCP Server API](../docs/MCP_MODES_SERVER_API.md)**: API reference
- **[MCP Server User Guide](../docs/MCP_MODES_SERVER_USER_GUIDE.md)**: User guide

## 💡 Tips

1. **Start with dry-run**: Always run in dry-run mode first to understand the workflow
2. **Use checkpoints**: For long workflows, checkpoints allow resuming after interruptions
3. **Customize phases**: Adapt the phase structure to match your project needs
4. **Clear instructions**: Provide detailed, self-contained instructions for each subtask
5. **Track dependencies**: Explicitly specify what outputs each subtask needs
6. **Choose modes wisely**: Use the right mode for each type of task

## 🤝 Contributing

Have an example you'd like to share? Please contribute:

1. Create a new example file with clear documentation
2. Add it to this README
3. Include comments explaining key concepts
4. Provide sample output if relevant
5. Submit a pull request

## 📝 License

These examples are part of the Roo Code Python SDK and are subject to the same license terms.