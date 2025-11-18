#!/usr/bin/env python3
"""
Real MCP Modes Server Recreation Runner

This script demonstrates ACTUAL orchestrator mode usage to recreate the
MCP Modes Server codebase through a coordinated multi-phase workflow.

This is a REAL executable script that uses the actual mode system.

Usage:
    # Setup API key first
    export ANTHROPIC_API_KEY=your-key-here
    # or
    export OPENAI_API_KEY=your-key-here
    
    # Show workflow without executing (dry run)
    python recreate_mcp_server.py --dry-run
    
    # Actually execute the workflow (requires API key)
    python recreate_mcp_server.py --execute
    
    # Execute specific phases only
    python recreate_mcp_server.py --execute --phases 1,2,3
    
    # Interactive mode (pause after each phase)
    python recreate_mcp_server.py --execute --interactive
    
    # Resume from checkpoint
    python recreate_mcp_server.py --execute --resume checkpoint.json

Key Features:
    - Uses real ModeAgent from roo_code.modes.agent
    - Creates real tasks via ModeOrchestrator
    - Executes actual agent.run() calls with API provider
    - Demonstrates real orchestrator pattern with subtask creation
    - Progress tracking and checkpoint/resume capability
    - Supports multiple API providers (Anthropic, OpenAI, etc.)
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


class MCPServerWorkflowRunner:
    """
    Real orchestrator runner that uses the actual mode system to recreate
    the MCP Modes Server implementation.
    
    This class demonstrates:
    - Real ModeAgent usage in orchestrator mode
    - Actual subtask creation via agent.create_subtask()
    - Real API calls with configured provider
    - Progress tracking and checkpointing
    - Error handling and recovery
    """
    
    def __init__(
        self,
        project_root: Path,
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
            project_root: Root directory of the project
            provider: API provider (anthropic, openai, etc.)
            model: Model ID to use
            api_key: API key (will try env vars if not provided)
            dry_run: If True, only show what would be done without executing
            interactive: If True, pause after each phase for user confirmation
            checkpoint_file: Optional file to save/load checkpoints
            selected_phases: Optional list of phase IDs to run (None = all)
        """
        self.project_root = project_root
        self.provider = provider
        self.model = model
        self.dry_run = dry_run
        self.interactive = interactive
        self.checkpoint_file = checkpoint_file or (project_root / "workflow_checkpoint.json")
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
        log_file = self.project_root / "examples" / "workflow_run.log"
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
            project_root=self.project_root,
        )
        
        self.logger.info(f"Initialized {self.provider} client with model {self.model}")
    
    def _initialize_workflow(self) -> WorkflowState:
        """
        Initialize the workflow with all phases and subtasks.
        
        This defines the complete workflow that was used to create the
        MCP Modes Server implementation.
        """
        phases = [
            # Phase 1: Analysis
            PhaseSpec(
                phase_id=1,
                name="System Analysis",
                description="Analyze existing mode system and understand requirements",
                subtasks=[
                    SubtaskSpec(
                        mode="ask",
                        description="Analyze mode system architecture",
                        message="""
Create a game
""",
                        expected_outputs=["System architecture understanding"],
                    ),
                ],
            ),
            
            # Phase 2: Requirements Research
            PhaseSpec(
                phase_id=2,
                name="MCP Protocol Research",
                description="Research MCP protocol requirements and specifications",
                subtasks=[
                    SubtaskSpec(
                        mode="ask",
                        description="Research MCP protocol and server patterns",
                        message="""Research the Model Context Protocol (MCP) to understand:
1. Protocol specification and message format
2. Server initialization and lifecycle
3. Resource and tool exposure patterns
4. Session management requirements
5. Error handling and validation

Provide a comprehensive summary that will guide the architecture design.""",
                        expected_outputs=["MCP protocol requirements document"],
                    ),
                ],
            ),
            
            # Phase 3: Architecture Design
            PhaseSpec(
                phase_id=3,
                name="Architecture Design",
                description="Design the MCP Modes Server architecture",
                subtasks=[
                    SubtaskSpec(
                        mode="architect",
                        description="Design system architecture",
                        message="""Design a comprehensive architecture for the MCP Modes Server that:

1. Exposes the mode system via MCP protocol
2. Manages mode sessions and task lifecycle
3. Provides resources (mode configs, task state)
4. Provides tools (switch_mode, new_task, get_task_status)
5. Handles validation and error recovery

Create a detailed architecture document (ARCHITECTURE_MCP_MODES_SERVER.md) covering:
- System components and their responsibilities
- Data flow and interaction patterns
- Configuration and deployment
- Error handling strategies
- Testing approach

Consider:
- The existing mode system (ModeOrchestrator, Task, ModeConfig)
- MCP protocol requirements (init, resources, tools)
- Session management and isolation
- Async/await patterns throughout""",
                        expected_outputs=["ARCHITECTURE_MCP_MODES_SERVER.md"],
                        dependencies=["System architecture understanding", "MCP protocol requirements document"],
                    ),
                ],
            ),
            
            # Phase 4: Core Infrastructure
            PhaseSpec(
                phase_id=4,
                name="Core Infrastructure Implementation",
                description="Implement protocol, config, and validation infrastructure",
                subtasks=[
                    SubtaskSpec(
                        mode="code",
                        description="Implement MCP protocol types and messages",
                        message="""Create roo_code/mcp/protocol.py implementing:

1. Core MCP message types (Request, Response, Notification)
2. Protocol-specific types (InitializeRequest, InitializeResult, etc.)
3. Resource and Tool schemas
4. Proper JSON serialization support

Use dataclasses with proper type hints. Follow the MCP specification.
Make sure all types are properly validated and serializable.""",
                        expected_outputs=["roo_code/mcp/protocol.py"],
                        dependencies=["ARCHITECTURE_MCP_MODES_SERVER.md"],
                    ),
                    SubtaskSpec(
                        mode="code",
                        description="Implement configuration management",
                        message="""Create roo_code/mcp/config.py implementing:

1. MCPServerConfig dataclass for server configuration
2. Default configuration values
3. Configuration loading from environment/files
4. Configuration validation

Support configuration of:
- Server name and version
- Enabled resources and tools
- Session timeout settings
- Logging configuration""",
                        expected_outputs=["roo_code/mcp/config.py"],
                        dependencies=["roo_code/mcp/protocol.py"],
                    ),
                    SubtaskSpec(
                        mode="code",
                        description="Implement validation utilities",
                        message="""Create roo_code/mcp/validation.py implementing:

1. Message validation (schema compliance)
2. Request parameter validation
3. Tool argument validation
4. Resource URI validation
5. Custom validation exceptions

Use pydantic or similar for robust validation.
Provide clear error messages for validation failures.""",
                        expected_outputs=["roo_code/mcp/validation.py"],
                        dependencies=["roo_code/mcp/protocol.py"],
                    ),
                ],
            ),
            
            # Additional phases would continue here...
            # For brevity, including just first 4 phases in this implementation
        ]
        
        # Filter phases if specific ones selected
        if self.selected_phases:
            phases = [p for p in phases if p.phase_id in self.selected_phases]
        
        return WorkflowState(phases=phases)
    
    def save_checkpoint(self) -> None:
        """Save current workflow state to checkpoint file."""
        if not self.checkpoint_file:
            return
            
        checkpoint_data = {
            "version": "1.0",
            "saved_at": datetime.now().isoformat(),
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
        print("MCP MODES SERVER RECREATION WORKFLOW")
        print("=" * 80)
        print(f"\nMode: {'DRY RUN' if self.dry_run else 'EXECUTION'}")
        if not self.dry_run:
            print(f"Provider: {self.provider}")
            print(f"Model: {self.model}")
        print(f"Project Root: {self.project_root}")
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
                    "code": "💻",
                }.get(subtask.mode, "🔧")
                print(f"     {mode_icon} [{subtask.mode}] {subtask.description}")
        
        print("\n" + "=" * 80 + "\n")
    
    async def execute_subtask_real(self, subtask: SubtaskSpec, phase: PhaseSpec) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Actually execute a subtask using the real mode system.
        
        Args:
            subtask: The subtask specification
            phase: The parent phase
            
        Returns:
            Tuple of (success, error_message, result)
        """
        mode_icon = {"ask": "❓", "architect": "🏗️ ", "code": "💻"}.get(subtask.mode, "🔧")
        
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
                project_root=self.project_root,
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
        mode_icon = {"ask": "❓", "architect": "🏗️ ", "code": "💻"}.get(subtask.mode, "🔧")
        
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
        
        # Interactive mode: pause for user confirmation
        if self.interactive and not self.dry_run:
            response = input("\n⏸️  Continue to next phase? [Y/n]: ")
            if response.lower() == 'n':
                print("   Workflow paused. Resume with --resume flag.")
                self.save_checkpoint()
                return False
        
        return True
    
    async def run(self) -> bool:
        """
        Run the complete workflow.
        
        Returns:
            True if workflow completed successfully
        """
        self.state.started_at = datetime.now()
        
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
            print(f"   Using {self.provider} with model {self.model}\n")
        
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
            print(f"\n✨ Real execution complete using {self.provider}!")
        
        print()
        
        return True


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Real MCP Modes Server Recreation Workflow Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Show the workflow (dry run)
  python recreate_mcp_server.py --dry-run
  
  # Execute with Anthropic (requires ANTHROPIC_API_KEY)
  python recreate_mcp_server.py --execute
  
  # Execute with OpenAI
  python recreate_mcp_server.py --execute --provider openai --model gpt-4
  
  # Run specific phases only
  python recreate_mcp_server.py --execute --phases 1,2,3
  
  # Interactive mode (pause after each phase)
  python recreate_mcp_server.py --execute --interactive
  
  # Resume from checkpoint
  python recreate_mcp_server.py --execute --resume checkpoint.json
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
        help="Project root directory (default: current directory)",
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
        runner = MCPServerWorkflowRunner(
            project_root=args.project_root,
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
        print("   Checkpoint saved. Resume with: --resume workflow_checkpoint.json")
        sys.exit(130)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())