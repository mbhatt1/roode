#!/usr/bin/env python3
"""
Python Interactive REPL Recreation Runner

This script demonstrates using the roo_code orchestrator mode to build
a feature-rich Python interpreter/REPL application from scratch through
a coordinated multi-phase workflow.

This is a REAL executable script that uses the actual mode system to
create a complete Python REPL project with advanced features.

Usage:
    # Setup API key first
    export ANTHROPIC_API_KEY=your-key-here
    # or
    export OPENAI_API_KEY=your-key-here
    
    # Show workflow without executing (dry run)
    python recreate_python_interpreter.py --dry-run
    
    # Actually execute the workflow (requires API key)
    python recreate_python_interpreter.py --execute
    
    # Execute specific phases only
    python recreate_python_interpreter.py --execute --phases 1,2,3
    
    # Interactive mode (pause after each phase)
    python recreate_python_interpreter.py --execute --interactive
    
    # Resume from checkpoint
    python recreate_python_interpreter.py --execute --resume checkpoint.json
    
    # Specify output directory for the new project
    python recreate_python_interpreter.py --execute --output-dir ./my-repl-project

Key Features:
    - Uses real ModeAgent from roo_code.modes.agent
    - Creates real tasks via ModeOrchestrator
    - Executes actual agent.run() calls with API provider
    - Demonstrates orchestrator pattern for building a complete project
    - Creates a Python REPL with syntax highlighting, history, and completions
    - Progress tracking and checkpoint/resume capability
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum

# Import the mode system
try:
    from roo_code import RooClient, ProviderSettings
    from roo_code.modes.agent import ModeAgent
    from roo_code.modes.orchestrator import ModeOrchestrator
    from roo_code.modes.task import Task, TaskState
except ImportError as e:
    print("Error: roo_code package not found or has import issues.")
    print(f"Details: {e}")
    print("\nTo fix:")
    print("  1. Install the package: pip install -e .")
    print("  2. Or install from PyPI: pip install roo-code")
    print("  3. Ensure all dependencies are installed")
    sys.exit(1)


class PhaseStatus(str, Enum):
    """Status of a workflow phase."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class SubtaskSpec:
    """Specification for a subtask within a phase."""
    mode: str
    description: str
    message: str
    expected_outputs: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)


@dataclass
class PhaseSpec:
    """Specification for a workflow phase."""
    phase_id: int
    name: str
    description: str
    subtasks: List[SubtaskSpec]
    status: PhaseStatus = PhaseStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    task_results: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class WorkflowState:
    """State of the workflow execution."""
    phases: List[PhaseSpec]
    current_phase_idx: int = 0
    total_subtasks_completed: int = 0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    checkpoint_file: Optional[Path] = None
    execution_mode: str = "dry_run"  # "dry_run" or "execute"


class PythonInterpreterWorkflowRunner:
    """
    Orchestrator runner that uses the roo_code mode system to build
    a feature-rich Python REPL/interpreter application.
    
    This class demonstrates:
    - Real ModeAgent usage in orchestrator mode
    - Actual subtask creation via agent.create_subtask()
    - Real API calls with configured provider
    - Building a complete project from specification to implementation
    - Progress tracking and checkpointing
    """
    
    def __init__(
        self,
        project_root: Path,
        output_dir: Path,
        provider: str = "anthropic",
        model: str = "claude-sonnet-4-5",
        api_key: Optional[str] = None,
        dry_run: bool = True,
        interactive: bool = False,
        checkpoint_file: Optional[Path] = None,
        selected_phases: Optional[List[int]] = None,
    ):
        """
        Initialize the workflow runner.
        
        Args:
            project_root: Root directory of roo-code-python project
            output_dir: Directory where the new REPL project will be created
            provider: API provider (anthropic, openai, etc.)
            model: Model ID to use
            api_key: API key (will try env vars if not provided)
            dry_run: If True, only show what would be done without executing
            interactive: If True, pause after each phase for user confirmation
            checkpoint_file: Optional file to save/load checkpoints
            selected_phases: Optional list of phase IDs to run (None = all)
        """
        self.project_root = project_root
        self.output_dir = output_dir
        self.provider = provider
        self.model = model
        self.dry_run = dry_run
        self.interactive = interactive
        self.checkpoint_file = checkpoint_file or (project_root / "interpreter_checkpoint.json")
        self.selected_phases = selected_phases
        
        # Setup logging
        self.logger = self._setup_logging()
        
        # Initialize client and agent (only if not dry-run)
        self.client: Optional[RooClient] = None
        self.orchestrator_agent: Optional[ModeAgent] = None
        
        if not dry_run:
            self._initialize_client(api_key)
        
        # Initialize workflow state
        self.state = self._initialize_workflow()
        
    def _setup_logging(self) -> logging.Logger:
        """Setup logging configuration."""
        log_file = self.project_root / "examples" / "interpreter_workflow.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler(sys.stdout)
            ]
        )
        
        return logging.getLogger(__name__)
    
    def _initialize_client(self, api_key: Optional[str] = None) -> None:
        """Initialize the RooClient with provider settings."""
        # Get API key from args or environment
        if api_key is None:
            if self.provider == "anthropic":
                api_key = os.getenv("ANTHROPIC_API_KEY")
            elif self.provider == "openai":
                api_key = os.getenv("OPENAI_API_KEY")
            else:
                api_key = os.getenv(f"{self.provider.upper()}_API_KEY")
        
        if not api_key:
            raise ValueError(
                f"API key required for {self.provider}. "
                f"Set {self.provider.upper()}_API_KEY environment variable or pass --api-key"
            )
        
        # Create provider settings
        provider_settings = ProviderSettings(
            api_provider=self.provider,
            api_key=api_key,
            api_model_id=self.model,
        )
        
        # Create client
        self.client = RooClient(provider_settings=provider_settings)
        
        # Create orchestrator agent
        self.orchestrator_agent = ModeAgent(
            client=self.client,
            mode_slug="orchestrator",
            project_root=self.output_dir,  # Work in output directory
        )
        
        self.logger.info(f"Initialized {self.provider} client with model {self.model}")
    
    def _initialize_workflow(self) -> WorkflowState:
        """
        Initialize the workflow with all phases and subtasks for building
        a Python REPL/interpreter application.
        """
        phases = [
            # Phase 1: Project Planning
            PhaseSpec(
                phase_id=1,
                name="Requirements & Architecture",
                description="Define requirements and design system architecture for Python REPL",
                subtasks=[
                    SubtaskSpec(
                        mode="architect",
                        description="Design Python REPL architecture",
                        message=f"""Design a comprehensive architecture and full functional correct repo for a feature-rich Python REPL/interpreter application.

The project should be created in: {self.output_dir}

Requirements:
1. Interactive Python REPL with command history
2. Syntax highlighting for Python code
3. Tab completion for variables and functions
4. Multi-line input support
5. Exception handling and display
6. Variable inspection and introspection
7. Save/load session functionality
8. Extensible plugin system

Create an architecture document (ARCHITECTURE.md) covering:
- System components and their responsibilities
- Core REPL loop design
- Input handling and parsing
- Code execution and namespace management
- History and completion mechanisms
- Error handling strategies
- Plugin architecture
- Configuration system

The architecture should be modular and well-organized with clear separation of concerns.""",
                        expected_outputs=["ARCHITECTURE.md"],
                    ),
                ],
            ),
            
            # Phase 2: Core Infrastructure
            PhaseSpec(
                phase_id=2,
                name="Core Infrastructure",
                description="Implement core REPL infrastructure and utilities",
                subtasks=[
                    SubtaskSpec(
                        mode="code",
                        description="Create project structure and configuration",
                        message=f"""Create the basic project structure in {self.output_dir}:

Create these files:
1. pyproject.toml - Project metadata and dependencies
   - Include: prompt_toolkit, pygments, rich
   - Python 3.8+ compatibility
   - Entry point for 'pyrepl' command

2. README.md - Project documentation
   - Installation instructions
   - Usage examples
   - Feature list
   - Architecture overview

3. src/pyrepl/__init__.py - Package initialization
   - Version info
   - Main exports

4. src/pyrepl/config.py - Configuration management
   - Default settings
   - Config file loading
   - Environment variable support

Make sure all files have proper docstrings and type hints.""",
                        expected_outputs=[
                            "pyproject.toml",
                            "README.md",
                            "src/pyrepl/__init__.py",
                            "src/pyrepl/config.py"
                        ],
                        dependencies=["ARCHITECTURE.md"],
                    ),
                    SubtaskSpec(
                        mode="code",
                        description="Implement namespace and context management",
                        message=f"""Create src/pyrepl/context.py in {self.output_dir}:

Implement ExecutionContext class:
1. Manages global and local namespaces
2. Handles variable storage and retrieval
3. Tracks imported modules
4. Provides introspection capabilities
5. Supports context save/restore

Include methods:
- execute_code(code: str) -> Any
- get_variable(name: str) -> Any
- list_variables() -> Dict[str, Any]
- clear_namespace()
- save_state(filename: str)
- load_state(filename: str)

Use proper error handling and type hints throughout.""",
                        expected_outputs=["src/pyrepl/context.py"],
                        dependencies=["src/pyrepl/config.py"],
                    ),
                ],
            ),
            
            # Phase 3: REPL Core
            PhaseSpec(
                phase_id=3,
                name="REPL Engine",
                description="Implement the core REPL functionality",
                subtasks=[
                    SubtaskSpec(
                        mode="code",
                        description="Implement input handler with syntax highlighting",
                        message=f"""Create src/pyrepl/input_handler.py in {self.output_dir}:

Implement InputHandler class using prompt_toolkit:
1. Multi-line input support with automatic indentation detection
2. Syntax highlighting using Pygments Python lexer
3. Smart bracket matching and auto-completion
4. Vi/Emacs key bindings support
5. Input validation (detect incomplete code)

Include methods:
- get_input() -> str
- validate_input(text: str) -> bool
- handle_multiline() -> str
- setup_key_bindings()

Use prompt_toolkit.PromptSession for robust input handling.""",
                        expected_outputs=["src/pyrepl/input_handler.py"],
                        dependencies=["src/pyrepl/config.py"],
                    ),
                    SubtaskSpec(
                        mode="code",
                        description="Implement command history manager",
                        message=f"""Create src/pyrepl/history.py in {self.output_dir}:

Implement HistoryManager class:
1. Store command history persistently
2. Search history (reverse-i-search like bash)
3. History navigation (up/down arrows)
4. Session-based history tracking
5. Export/import history

Include methods:
- add_command(cmd: str)
- get_history() -> List[str]
- search_history(pattern: str) -> List[str]
- save_to_file(filename: str)
- load_from_file(filename: str)
- clear_history()

Use SQLite or JSON for persistent storage.""",
                        expected_outputs=["src/pyrepl/history.py"],
                        dependencies=["src/pyrepl/config.py"],
                    ),
                    SubtaskSpec(
                        mode="code",
                        description="Implement tab completion engine",
                        message=f"""Create src/pyrepl/completion.py in {self.output_dir}:

Implement CompletionEngine class:
1. Context-aware completions for variables, functions, modules
2. Attribute completion using introspection
3. File path completion for strings
4. Keyword and built-in completions
5. Smart completion ranking

Include methods:
- get_completions(text: str, context: ExecutionContext) -> List[str]
- complete_attribute(obj: Any, prefix: str) -> List[str]
- complete_import(prefix: str) -> List[str]
- complete_path(prefix: str) -> List[str]

Use jedi or similar for intelligent completions.""",
                        expected_outputs=["src/pyrepl/completion.py"],
                        dependencies=["src/pyrepl/context.py"],
                    ),
                ],
            ),
            
            # Phase 4: Output & Display
            PhaseSpec(
                phase_id=4,
                name="Output Management",
                description="Implement output formatting and display",
                subtasks=[
                    SubtaskSpec(
                        mode="code",
                        description="Implement output formatter with rich display",
                        message=f"""Create src/pyrepl/output.py in {self.output_dir}:

Implement OutputFormatter class using rich library:
1. Pretty-print Python objects
2. Syntax-highlighted tracebacks
3. Color-coded output types
4. Table/tree formatting for complex objects
5. Pager support for long output

Include methods:
- format_result(obj: Any) -> str
- format_exception(exc: Exception) -> str
- format_traceback(tb: traceback) -> str
- display_help(obj: Any)
- print_with_paging(text: str)

Use rich.console for beautiful terminal output.""",
                        expected_outputs=["src/pyrepl/output.py"],
                        dependencies=["src/pyrepl/config.py"],
                    ),
                ],
            ),
            
            # Phase 5: Main REPL Loop
            PhaseSpec(
                phase_id=5,
                name="REPL Integration",
                description="Integrate all components into main REPL loop",
                subtasks=[
                    SubtaskSpec(
                        mode="code",
                        description="Implement main REPL class",
                        message=f"""Create src/pyrepl/repl.py in {self.output_dir}:

Implement REPL class that integrates all components:
1. Initialize all subsystems (context, history, completion, etc.)
2. Main REPL loop with proper error handling
3. Special commands (!help, !vars, !save, !load, !clear, !exit)
4. Signal handling (Ctrl+C, Ctrl+D)
5. Startup banner and configuration

Include methods:
- run() - Main REPL loop
- handle_command(cmd: str) -> Optional[Any]
- execute_special_command(cmd: str) -> bool
- display_banner()
- shutdown()

The REPL should:
- Show >>> prompt for new input
- Show ... prompt for continuation
- Display results with proper formatting
- Handle exceptions gracefully
- Support EOF (Ctrl+D) to exit""",
                        expected_outputs=["src/pyrepl/repl.py"],
                        dependencies=[
                            "src/pyrepl/input_handler.py",
                            "src/pyrepl/history.py",
                            "src/pyrepl/completion.py",
                            "src/pyrepl/output.py",
                            "src/pyrepl/context.py"
                        ],
                    ),
                    SubtaskSpec(
                        mode="code",
                        description="Create command-line interface",
                        message=f"""Create src/pyrepl/__main__.py in {self.output_dir}:

Implement CLI entry point with argparse:
1. Command-line argument parsing
2. Configuration file loading
3. Script execution mode (-c flag)
4. File execution mode (script.py)
5. Version and help display

Arguments to support:
- --config: Path to config file
- --no-history: Disable history
- --execute/-c: Execute code and exit
- --version: Show version
- --help: Show help

The entry point should:
- Create REPL instance with config
- Handle command-line scripts
- Exit with proper status codes""",
                        expected_outputs=["src/pyrepl/__main__.py"],
                        dependencies=["src/pyrepl/repl.py"],
                    ),
                ],
            ),
            
            # Phase 6: Testing & Documentation
            PhaseSpec(
                phase_id=6,
                name="Testing & Documentation",
                description="Add tests and comprehensive documentation",
                subtasks=[
                    SubtaskSpec(
                        mode="code",
                        description="Create test suite",
                        message=f"""Create test files in {self.output_dir}/tests/:

1. tests/test_context.py - Test execution context
2. tests/test_history.py - Test history management
3. tests/test_completion.py - Test completion engine
4. tests/test_output.py - Test output formatting
5. tests/test_repl.py - Integration tests for REPL

Each test file should:
- Use pytest framework
- Include fixtures for common setup
- Test normal cases and edge cases
- Test error handling
- Include docstrings

Also create:
- tests/__init__.py
- tests/conftest.py (pytest configuration)""",
                        expected_outputs=[
                            "tests/test_context.py",
                            "tests/test_history.py",
                            "tests/test_completion.py",
                            "tests/test_output.py",
                            "tests/test_repl.py",
                            "tests/conftest.py"
                        ],
                        dependencies=["src/pyrepl/repl.py"],
                    ),
                    SubtaskSpec(
                        mode="code",
                        description="Create usage examples and documentation",
                        message=f"""Create documentation files in {self.output_dir}:

1. USAGE.md - Comprehensive usage guide
   - Basic usage examples
   - Special commands reference
   - Configuration options
   - Tips and tricks

2. examples/basic_usage.py - Simple usage examples
3. examples/advanced_features.py - Advanced features demo
4. CONTRIBUTING.md - Contribution guidelines

Also update README.md with:
- Quick start guide
- Feature showcase
- Installation instructions
- Link to full documentation""",
                        expected_outputs=[
                            "USAGE.md",
                            "examples/basic_usage.py",
                            "examples/advanced_features.py",
                            "CONTRIBUTING.md"
                        ],
                        dependencies=["src/pyrepl/__main__.py"],
                    ),
                ],
            ),
            
            # Phase 7: Finalization
            PhaseSpec(
                phase_id=7,
                name="Project Finalization",
                description="Final touches and verification",
                subtasks=[
                    SubtaskSpec(
                        mode="orchestrator",
                        description="Add packaging and deployment files",
                        message=f"""Create deployment files in {self.output_dir}:

1. .gitignore - Git ignore patterns
2. LICENSE - MIT or Apache 2.0 license
3. CHANGELOG.md - Version history
4. Makefile or justfile - Common commands
   - install: Install package in dev mode
   - test: Run test suite
   - lint: Run linters
   - format: Format code
   - clean: Clean build artifacts

5. .github/workflows/ci.yml - CI/CD pipeline (if applicable)

Ensure all files are properly formatted and documented.""",
                        expected_outputs=[
                            ".gitignore",
                            "LICENSE",
                            "CHANGELOG.md",
                            "Makefile"
                        ],
                        dependencies=["tests/test_repl.py"],
                    ),
                    SubtaskSpec(
                        mode="ask",
                        description="Verify project completeness",
                        message=f"""Review the completed Python REPL project in {self.output_dir}.

Verify that:
1. All core features are implemented
2. Code is well-documented with docstrings
3. Tests cover main functionality
4. README provides clear usage instructions
5. Package structure follows Python best practices
6. All dependencies are specified in pyproject.toml
7. Project can be installed and run successfully

Provide a summary of:
- What was created
- Key features implemented
- Any recommendations for improvements
- Next steps for users""",
                        expected_outputs=["Project verification summary"],
                        dependencies=["All previous outputs"],
                    ),
                ],
            ),
        ]
        
        # Filter phases if specific ones selected
        if self.selected_phases:
            phases = [p for p in phases if p.phase_id in self.selected_phases]
        
        # Set execution mode based on dry_run flag
        execution_mode = "dry_run" if self.dry_run else "execute"
        
        return WorkflowState(phases=phases, execution_mode=execution_mode)
    
    def save_checkpoint(self) -> None:
        """Save current workflow state to checkpoint file."""
        if not self.checkpoint_file:
            return
            
        checkpoint_data = {
            "version": "1.0",
            "project_type": "python_interpreter",
            "saved_at": datetime.now().isoformat(),
            "execution_mode": self.state.execution_mode,
            "output_dir": str(self.output_dir),
            "current_phase_idx": self.state.current_phase_idx,
            "total_subtasks_completed": self.state.total_subtasks_completed,
            "phases": [
                {
                    "phase_id": p.phase_id,
                    "status": p.status.value,
                    "started_at": p.started_at.isoformat() if p.started_at else None,
                    "completed_at": p.completed_at.isoformat() if p.completed_at else None,
                    "error": p.error,
                    "task_results": p.task_results,
                }
                for p in self.state.phases
            ],
        }
        
        self.checkpoint_file.write_text(json.dumps(checkpoint_data, indent=2))
        self.logger.info(f"Checkpoint saved to {self.checkpoint_file}")
    
    def load_checkpoint(self) -> bool:
        """
        Load workflow state from checkpoint file.
        
        Returns:
            True if checkpoint was loaded successfully
        """
        if not self.checkpoint_file or not self.checkpoint_file.exists():
            return False
        
        try:
            checkpoint_data = json.loads(self.checkpoint_file.read_text())
            
            # Validate execution mode compatibility
            current_mode = self.state.execution_mode
            checkpoint_mode = checkpoint_data.get("execution_mode", "dry_run")
            
            if current_mode != checkpoint_mode:
                print(f"\n⚠️  CHECKPOINT MODE MISMATCH DETECTED")
                print(f"{'=' * 80}")
                print(f"The checkpoint was created in '{checkpoint_mode}' mode,")
                print(f"but you're currently running in '{current_mode}' mode.")
                print(f"\nThis mismatch can cause issues because:")
                if checkpoint_mode == "dry_run" and current_mode == "execute":
                    print(f"  • The checkpoint marked phases as completed during dry-run simulation")
                    print(f"  • Running in execute mode would skip these phases")
                    print(f"  • This would leave your project directory empty or incomplete")
                else:
                    print(f"  • The checkpoint contains actual execution results")
                    print(f"  • Running in dry-run mode may not accurately reflect the state")
                print(f"\n💡 Recommended action:")
                print(f"   Delete the checkpoint file to start fresh:")
                print(f"   rm {self.checkpoint_file}")
                print(f"\n   Then re-run your command.")
                print(f"{'=' * 80}")
                
                self.logger.warning(
                    f"Checkpoint mode mismatch: checkpoint={checkpoint_mode}, current={current_mode}"
                )
                
                # Reject the incompatible checkpoint
                return False
            
            # Restore phase statuses
            phase_states = {p["phase_id"]: p for p in checkpoint_data["phases"]}
            for phase in self.state.phases:
                if phase.phase_id in phase_states:
                    phase_data = phase_states[phase.phase_id]
                    phase.status = PhaseStatus(phase_data["status"])
                    if phase_data.get("started_at"):
                        phase.started_at = datetime.fromisoformat(phase_data["started_at"])
                    if phase_data.get("completed_at"):
                        phase.completed_at = datetime.fromisoformat(phase_data["completed_at"])
                    phase.error = phase_data.get("error")
                    phase.task_results = phase_data.get("task_results", [])
            
            self.state.current_phase_idx = checkpoint_data["current_phase_idx"]
            self.state.total_subtasks_completed = checkpoint_data["total_subtasks_completed"]
            
            self.logger.info(f"Checkpoint loaded from {self.checkpoint_file}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to load checkpoint: {e}")
            return False
    
    def print_workflow_summary(self) -> None:
        """Print a summary of the workflow phases."""
        print("\n" + "=" * 80)
        print("PYTHON REPL/INTERPRETER PROJECT CREATION WORKFLOW")
        print("=" * 80)
        print(f"\nMode: {'DRY RUN' if self.dry_run else 'EXECUTION'}")
        if not self.dry_run:
            print(f"Provider: {self.provider}")
            print(f"Model: {self.model}")
        print(f"Output Directory: {self.output_dir}")
        print(f"Total Phases: {len(self.state.phases)}")
        
        total_subtasks = sum(len(p.subtasks) for p in self.state.phases)
        print(f"Total Subtasks: {total_subtasks}")
        
        print("\n" + "-" * 80)
        print("PHASES:")
        print("-" * 80)
        
        for phase in self.state.phases:
            status_symbol = {
                PhaseStatus.PENDING: "⏸️ ",
                PhaseStatus.RUNNING: "▶️ ",
                PhaseStatus.COMPLETED: "✅",
                PhaseStatus.FAILED: "❌",
                PhaseStatus.SKIPPED: "⏭️ ",
            }[phase.status]
            
            print(f"\n{status_symbol} Phase {phase.phase_id}: {phase.name}")
            print(f"   {phase.description}")
            print(f"   Subtasks: {len(phase.subtasks)}")
            
            for subtask in phase.subtasks:
                mode_icon = {
                    "ask": "❓",
                    "architect": "🏗️ ",
                    "orchestrator": "💻",
                    "debug": "🐛",
                }.get(subtask.mode, "🔧")
                print(f"     {mode_icon} [{subtask.mode}] {subtask.description}")
        
        print("\n" + "=" * 80 + "\n")
    
    async def execute_subtask_real(self, subtask: SubtaskSpec, phase: PhaseSpec) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Execute a subtask using the real mode system.
        
        Args:
            subtask: The subtask specification
            phase: The parent phase
            
        Returns:
            Tuple of (success, error_message, result)
        """
        mode_icon = {"ask": "❓", "architect": "🏗️ ", "orchestrator": "💻", "debug": "🐛"}.get(subtask.mode, "🔧")
        
        print(f"\n{mode_icon} Executing: {subtask.description}")
        print(f"   Mode: {subtask.mode}")
        print(f"   Expected outputs: {', '.join(subtask.expected_outputs)}")
        
        try:
            # Create subtask via orchestrator agent
            self.logger.info(f"Creating subtask in {subtask.mode} mode")
            
            # Create the subtask
            task = await asyncio.to_thread(
                self.orchestrator_agent.create_subtask,
                mode_slug=subtask.mode,
                initial_message=subtask.message,
            )
            
            print(f"   ✓ Subtask created: {task.task_id}")
            self.logger.info(f"Subtask {task.task_id} created in {subtask.mode} mode")
            
            # Create a new agent for this subtask
            subtask_agent = ModeAgent(
                client=self.client,
                mode_slug=subtask.mode,
                project_root=self.output_dir,  # Work in output directory
            )
            
            # Set the agent's current task to our subtask
            subtask_agent.current_task = task
            subtask_agent.orchestrator.set_current_task(task)
            
            # Execute the task
            print(f"   ⚙️  Executing task with {self.provider} {self.model}...")
            
            def on_iteration(iteration: int, response: str):
                preview = response[:150] + "..." if len(response) > 150 else response
                print(f"      Iteration {iteration + 1}: {preview}")
            
            result = await subtask_agent.run(
                task=subtask.message,
                on_iteration=on_iteration,
            )
            
            print(f"   ✓ Task completed")
            
            # Mark task as completed
            task.mark_completed(result)
            
            return True, None, result
            
        except Exception as e:
            error_msg = f"Failed to execute subtask: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            return False, error_msg, None
    
    async def execute_subtask_dry_run(self, subtask: SubtaskSpec, phase: PhaseSpec) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Dry run of a subtask execution (no actual API calls).
        
        Args:
            subtask: The subtask specification
            phase: The parent phase
            
        Returns:
            Tuple of (success, error_message, result)
        """
        mode_icon = {"ask": "❓", "architect": "🏗️ ", "orchestrator": "💻", "debug": "🐛"}.get(subtask.mode, "🔧")
        
        print(f"\n{mode_icon} [DRY RUN] {subtask.description}")
        print(f"   Mode: {subtask.mode}")
        print(f"   Expected outputs: {', '.join(subtask.expected_outputs)}")
        print(f"   [DRY RUN] Would create task in '{subtask.mode}' mode")
        
        # Show message preview
        preview = subtask.message[:200].replace('\n', '\n             ')
        print(f"   [DRY RUN] Task message preview:")
        print(f"             {preview}...")
        
        # Simulate some processing
        await asyncio.sleep(0.1)
        
        return True, None, "[DRY RUN] Task would be executed here"
    
    async def execute_phase(self, phase: PhaseSpec) -> bool:
        """
        Execute a complete phase with all its subtasks.
        
        Args:
            phase: The phase to execute
            
        Returns:
            True if phase completed successfully
        """
        phase.status = PhaseStatus.RUNNING
        phase.started_at = datetime.now()
        phase.completed_at = None  # Clear any previous completion timestamp
        phase.error = None  # Clear any previous error
        
        print(f"\n{'=' * 80}")
        print(f"PHASE {phase.phase_id}: {phase.name}")
        print(f"{'=' * 80}")
        print(f"{phase.description}\n")
        
        # Execute each subtask
        for subtask_idx, subtask in enumerate(phase.subtasks, 1):
            print(f"\n[{subtask_idx}/{len(phase.subtasks)}] {subtask.description}")
            
            # Execute subtask (real or dry run)
            if self.dry_run:
                success, error, result = await self.execute_subtask_dry_run(subtask, phase)
            else:
                success, error, result = await self.execute_subtask_real(subtask, phase)
            
            # Record result
            phase.task_results.append({
                "subtask": subtask.description,
                "mode": subtask.mode,
                "success": success,
                "error": error,
                "result": result[:500] if result else None,  # Truncate for storage
            })
            
            if success:
                self.state.total_subtasks_completed += 1
                print(f"   ✓ Completed")
            else:
                phase.status = PhaseStatus.FAILED
                phase.error = error
                phase.completed_at = datetime.now()
                print(f"   ✗ Failed: {error}")
                return False
            
            # Save checkpoint after each subtask
            self.save_checkpoint()
        
        # Phase completed successfully
        phase.status = PhaseStatus.COMPLETED
        phase.completed_at = datetime.now()
        
        duration = (phase.completed_at - phase.started_at).total_seconds()
        print(f"\n✅ Phase {phase.phase_id} completed in {duration:.1f}s")
        
        # Save checkpoint after phase completion
        self.save_checkpoint()
        
        # Interactive mode: pause for user confirmation
        if self.interactive and not self.dry_run:
            response = input("\n⏸️  Continue to next phase? [Y/n]: ")
            if response.lower() == 'n':
                print("   Workflow paused. Resume with --resume flag.")
                return False
        
        return True
    
    async def run(self) -> bool:
        """
        Run the complete workflow.
        
        Returns:
            True if workflow completed successfully
        """
        self.state.started_at = datetime.now()
        
        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Print workflow summary
        self.print_workflow_summary()
        
        # Try to load checkpoint if resuming
        if self.checkpoint_file and self.checkpoint_file.exists():
            if self.load_checkpoint():
                print(f"\n📂 Resuming from checkpoint at phase {self.state.current_phase_idx + 1}")
        
        if self.dry_run:
            print("\n⚠️  DRY RUN MODE: No actual API calls will be made")
            print("    This shows the workflow structure.\n")
        else:
            print("\n🚀 EXECUTION MODE: Real tasks will be created and executed")
            print(f"   Using {self.provider} with model {self.model}")
            print(f"   Creating project in: {self.output_dir}\n")
        
        # Execute phases
        for phase_idx in range(self.state.current_phase_idx, len(self.state.phases)):
            phase = self.state.phases[phase_idx]
            self.state.current_phase_idx = phase_idx
            
            # Skip completed phases
            if phase.status == PhaseStatus.COMPLETED:
                print(f"\n⏭️  Skipping completed phase {phase.phase_id}: {phase.name}")
                continue
            
            # Execute phase
            success = await self.execute_phase(phase)
            
            if not success:
                if phase.status == PhaseStatus.FAILED:
                    print(f"\n❌ Workflow failed at phase {phase.phase_id}")
                    print(f"   Error: {phase.error}")
                self.save_checkpoint()
                return False
        
        # Workflow completed
        self.state.completed_at = datetime.now()
        duration = (self.state.completed_at - self.state.started_at).total_seconds()
        
        print(f"\n{'=' * 80}")
        print("WORKFLOW COMPLETED SUCCESSFULLY")
        print(f"{'=' * 80}")
        print(f"\nTotal Duration: {duration:.1f}s")
        print(f"Phases Completed: {len(self.state.phases)}")
        print(f"Subtasks Completed: {self.state.total_subtasks_completed}")
        
        if self.dry_run:
            print("\n💡 This was a dry run showing the workflow structure.")
            print("   To actually execute, run with --execute flag and configure API key.")
        else:
            print(f"\n✨ Python REPL project created successfully!")
            print(f"   Location: {self.output_dir}")
            print(f"\n📦 Next steps:")
            print(f"   1. cd {self.output_dir}")
            print(f"   2. pip install -e .")
            print(f"   3. pyrepl  # Run your new REPL!")
        
        print()
        
        return True


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Python REPL/Interpreter Project Creation Workflow",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Show the workflow (dry run)
  python recreate_python_interpreter.py --dry-run
  
  # Execute with Anthropic (requires ANTHROPIC_API_KEY)
  python recreate_python_interpreter.py --execute --output-dir ./my-python-repl
  
  # Execute with OpenAI
  python recreate_python_interpreter.py --execute --provider openai --model gpt-4
  
  # Run specific phases only
  python recreate_python_interpreter.py --execute --phases 1,2,3
  
  # Interactive mode (pause after each phase)
  python recreate_python_interpreter.py --execute --interactive
  
  # Resume from checkpoint
  python recreate_python_interpreter.py --execute --resume checkpoint.json
        """,
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show workflow structure without executing (no API calls)",
    )
    
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually execute the workflow (requires API key)",
    )
    
    parser.add_argument(
        "--provider",
        type=str,
        default="anthropic",
        choices=["anthropic", "openai", "gemini", "ollama"],
        help="API provider to use (default: anthropic)",
    )
    
    parser.add_argument(
        "--model",
        type=str,
        default="claude-sonnet-4-5",
        help="Model ID to use (default: claude-sonnet-4-5)",
    )
    
    parser.add_argument(
        "--api-key",
        type=str,
        help="API key (will use environment variable if not provided)",
    )
    
    parser.add_argument(
        "--phases",
        type=str,
        help="Comma-separated list of phase IDs to run (e.g., '1,2,3')",
    )
    
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Pause after each phase for user confirmation",
    )
    
    parser.add_argument(
        "--resume",
        type=Path,
        metavar="CHECKPOINT_FILE",
        help="Resume from a checkpoint file",
    )
    
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path.cwd(),
        help="Roo-code project root directory (default: current directory)",
    )
    
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path.cwd() / "python-repl-project",
        help="Directory where the new project will be created (default: ./python-repl-project)",
    )
    
    return parser.parse_args()


async def main():
    """Main entry point."""
    args = parse_args()
    
    # Determine execution mode
    if not args.dry_run and not args.execute:
        # Default to dry run if neither specified
        dry_run = True
    else:
        dry_run = args.dry_run and not args.execute
    
    # Parse selected phases
    selected_phases = None
    if args.phases:
        try:
            selected_phases = [int(p.strip()) for p in args.phases.split(',')]
        except ValueError:
            print("Error: Invalid phase list. Use comma-separated integers (e.g., '1,2,3')")
            sys.exit(1)
    
    # Create runner
    try:
        runner = PythonInterpreterWorkflowRunner(
            project_root=args.project_root,
            output_dir=args.output_dir,
            provider=args.provider,
            model=args.model,
            api_key=args.api_key,
            dry_run=dry_run,
            interactive=args.interactive,
            checkpoint_file=args.resume,
            selected_phases=selected_phases,
        )
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)
    
    # Run workflow
    try:
        success = await runner.run()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Workflow interrupted by user")
        runner.save_checkpoint()
        print("   Checkpoint saved. Resume with: --resume interpreter_checkpoint.json")
        sys.exit(130)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())