#!/usr/bin/env python3
"""
Bedrock Jekyll Documentation Generator

This script demonstrates using the roo_code orchestrator mode with Amazon Bedrock
to analyze a codebase and generate comprehensive Jekyll-based documentation.

This script exclusively uses Amazon Bedrock as the provider to create a complete
documentation website that can be deployed on GitHub Pages.

Usage:
    # Setup AWS credentials first
    export AWS_REGION=your-region
    export AWS_ACCESS_KEY_ID=your-access-key
    export AWS_SECRET_ACCESS_KEY=your-secret-key
    
    # Show workflow without executing (dry run)
    python bedrock_jekyll_docs_generator.py --dry-run
    
    # Actually execute the workflow (requires AWS credentials)
    python bedrock_jekyll_docs_generator.py --execute --codebase-dir /path/to/codebase
    
    # Execute specific phases only
    python bedrock_jekyll_docs_generator.py --execute --phases 1,2,3
    
    # Interactive mode (pause after each phase)
    python bedrock_jekyll_docs_generator.py --execute --interactive
    
    # Resume from checkpoint
    python bedrock_jekyll_docs_generator.py --execute --resume checkpoint.json
    
    # Specify output directory for the documentation site
    python bedrock_jekyll_docs_generator.py --execute --output-dir ./docs-site

Key Features:
    - Uses real ModeAgent from roo_code.modes.agent
    - Exclusively uses AWS Bedrock as the LLM provider
    - Creates real tasks via ModeOrchestrator
    - Executes actual agent.run() calls with AWS Bedrock
    - Analyzes codebase and generates comprehensive documentation
    - Generates a complete Jekyll website ready for GitHub Pages
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
    from roo_code.types import ApiProvider
except ImportError as e:
    print("Error: roo_code package not found or has import issues.")
    print(f"Details: {e}")
    print("\nTo fix:")
    print("  1. Install the package: pip install -e .")
    print("  2. Or install from PyPI: pip install roo-code")
    print("  3. Ensure all dependencies are installed, including boto3")
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


class JekyllDocsWorkflowRunner:
    """
    Orchestrator runner that uses the roo_code mode system with AWS Bedrock
    to build a Jekyll-based documentation site from a codebase.
    
    This class demonstrates:
    - Real ModeAgent usage with Amazon Bedrock
    - Actual subtask creation via agent.create_subtask()
    - Real API calls with Bedrock provider
    - Building a complete documentation site through a series of steps
    - Progress tracking and checkpointing
    """
    
    def __init__(
        self,
        project_root: Path,
        codebase_dir: Path,
        output_dir: Path,
        model: str = "anthropic.claude-3-sonnet-20240229-v1:0",
        aws_region: str = None,
        aws_access_key: str = None,
        aws_secret_key: str = None,
        aws_session_token: str = None,
        dry_run: bool = True,
        interactive: bool = False,
        checkpoint_file: Optional[Path] = None,
        selected_phases: Optional[List[int]] = None,
    ):
        """
        Initialize the workflow runner.
        
        Args:
            project_root: Root directory of roo-code project
            codebase_dir: Directory containing the codebase to document
            output_dir: Directory where the Jekyll docs will be generated
            model: Bedrock model ID to use
            aws_region: AWS region for Bedrock
            aws_access_key: AWS access key ID
            aws_secret_key: AWS secret access key
            aws_session_token: Optional AWS session token
            dry_run: If True, only show what would be done without executing
            interactive: If True, pause after each phase for user confirmation
            checkpoint_file: Optional file to save/load checkpoints
            selected_phases: Optional list of phase IDs to run (None = all)
        """
        self.project_root = project_root
        self.codebase_dir = codebase_dir
        self.output_dir = output_dir
        self.model = model
        self.dry_run = dry_run
        self.interactive = interactive
        self.checkpoint_file = checkpoint_file or (project_root / "jekyll_docs_checkpoint.json")
        self.selected_phases = selected_phases
        
        # AWS credentials
        self.aws_region = aws_region
        self.aws_access_key = aws_access_key
        self.aws_secret_key = aws_secret_key
        self.aws_session_token = aws_session_token
        
        # Setup logging
        self.logger = self._setup_logging()
        
        # Initialize client and agent (only if not dry-run)
        self.client: Optional[RooClient] = None
        self.orchestrator_agent: Optional[ModeAgent] = None
        
        if not dry_run:
            self._initialize_client()
        
        # Initialize workflow state
        self.state = self._initialize_workflow()
        
    def _setup_logging(self) -> logging.Logger:
        """Setup logging configuration."""
        log_file = self.project_root / "examples" / "bedrock_jekyll_workflow.log"
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
    
    def _initialize_client(self) -> None:
        """Initialize the RooClient with Bedrock provider settings."""
        # Get AWS credentials from args or environment
        aws_region = self.aws_region or os.getenv("AWS_REGION")
        aws_access_key = self.aws_access_key or os.getenv("AWS_ACCESS_KEY_ID")
        aws_secret_key = self.aws_secret_key or os.getenv("AWS_SECRET_ACCESS_KEY")
        aws_session_token = self.aws_session_token or os.getenv("AWS_SESSION_TOKEN")
        
        if not aws_region:
            raise ValueError(
                "AWS region required for Bedrock. "
                "Set AWS_REGION environment variable or pass --aws-region"
            )
        
        # Create provider settings - Note that we're specifically using BEDROCK provider
        provider_settings = ProviderSettings(
            api_provider=ApiProvider.BEDROCK,
            api_model_id=self.model,
            aws_region=aws_region,
            aws_access_key=aws_access_key,
            aws_secret_key=aws_secret_key,
            aws_session_token=aws_session_token,
        )
        
        # Create client
        self.client = RooClient(provider_settings=provider_settings)
        
        # Create orchestrator agent
        self.orchestrator_agent = ModeAgent(
            client=self.client,
            mode_slug="orchestrator",
            project_root=self.output_dir,  # Work in output directory
        )
        
        self.logger.info(f"Initialized Bedrock client with model {self.model}")
    
    def _initialize_workflow(self) -> WorkflowState:
        """
        Initialize the workflow with all phases and subtasks for building
        a Jekyll documentation site from a codebase.
        """
        phases = [
            # Phase 1: Codebase Analysis
            PhaseSpec(
                phase_id=1,
                name="Codebase Analysis",
                description="Analyze the codebase structure and extract key information",
                subtasks=[
                    SubtaskSpec(
                        mode="architect",
                        description="Analyze codebase architecture",
                        message=f"""Analyze the codebase in {self.codebase_dir} to create an architecture overview document.

Examine the codebase and create a PROJECT_OVERVIEW.md file in {self.output_dir} that includes:
1. Project purpose and main functionality
2. Major components and their relationships
3. Key features and capabilities
4. Technologies and frameworks used
5. Project structure overview
6. Design patterns and architectural approaches

This document will serve as the foundation for the Jekyll documentation site. 
Focus on understanding the high-level architecture rather than implementation details.""",
                        expected_outputs=["PROJECT_OVERVIEW.md"],
                    ),
                ],
            ),
            
            # Phase 2: Documentation Planning
            PhaseSpec(
                phase_id=2,
                name="Documentation Planning",
                description="Plan the documentation structure and navigation",
                subtasks=[
                    SubtaskSpec(
                        mode="architect",
                        description="Design documentation structure",
                        message=f"""Design a comprehensive documentation structure for the codebase.

Based on the PROJECT_OVERVIEW.md, create a DOCUMENTATION_PLAN.md file in {self.output_dir} that outlines:

1. Overall documentation organization
2. Navigation structure with main sections and subsections
3. Types of documentation pages needed (tutorials, API reference, guides, etc.)
4. Integration points between different documentation sections
5. Key user journeys through the documentation
6. Recommended Jekyll themes and plugins

The documentation should be organized to serve both new users and experienced developers.
Structure it to progressively reveal complexity and make the most important information easily accessible.""",
                        expected_outputs=["DOCUMENTATION_PLAN.md"],
                        dependencies=["PROJECT_OVERVIEW.md"],
                    ),
                ],
            ),
            
            # Phase 3: Jekyll Setup
            PhaseSpec(
                phase_id=3,
                name="Jekyll Site Setup",
                description="Create Jekyll site structure and configuration",
                subtasks=[
                    SubtaskSpec(
                        mode="code",
                        description="Create Jekyll configuration",
                        message=f"""Set up the basic Jekyll site structure and configuration in {self.output_dir}.

Create these files:
1. _config.yml - Jekyll configuration
   - Set up site title, description, and base URL
   - Configure a suitable theme (like 'just-the-docs' or 'jekyll-theme-minimal')
   - Add necessary plugins (jekyll-seo-tag, jekyll-sitemap, etc.)
   - Set up collections for API docs, guides, and tutorials if needed
   
2. Gemfile - Ruby dependencies
   - Include Jekyll and required plugins
   - Specify the theme gem
   
3. index.md - Site homepage
   - Create a welcoming homepage
   - Include navigation links to main sections
   - Add a brief project description
   
4. README.md - Instructions for maintaining the docs
   - How to build the site locally
   - How to add new pages
   - How to deploy updates
   
5. .gitignore - Standard Jekyll gitignore
   - Include _site, .sass-cache, .jekyll-cache, etc.

Configure the site to use a clean, readable theme with good support for code highlighting and navigation.""",
                        expected_outputs=[
                            "_config.yml",
                            "Gemfile",
                            "index.md",
                            "README.md",
                            ".gitignore"
                        ],
                        dependencies=["DOCUMENTATION_PLAN.md"],
                    ),
                    SubtaskSpec(
                        mode="code",
                        description="Create site structure and layouts",
                        message=f"""Create the Jekyll site structure and basic layouts in {self.output_dir}.

Create the following directory structure:
1. _layouts/ - Template layouts
   - default.html - Base layout
   - page.html - Standard page layout
   - home.html - Homepage layout
   - api.html - API documentation layout
   
2. _includes/ - Reusable components
   - header.html - Site header with navigation
   - footer.html - Site footer with links
   - sidebar.html - Documentation sidebar navigation
   - code_example.html - Template for code examples
   
3. assets/ - Static assets
   - css/main.scss - Custom CSS/SCSS
   - js/main.js - Custom JavaScript
   - images/ - Directory for images
   
4. _data/ - Data files
   - navigation.yml - Navigation structure
   - versions.yml - Version information

Ensure the layouts are responsive, accessible, and optimize the reading experience for technical documentation.""",
                        expected_outputs=[
                            "_layouts/default.html",
                            "_layouts/page.html",
                            "_layouts/home.html",
                            "_layouts/api.html",
                            "_includes/header.html",
                            "_includes/footer.html",
                            "_includes/sidebar.html",
                            "_includes/code_example.html",
                            "assets/css/main.scss",
                            "assets/js/main.js",
                            "_data/navigation.yml",
                        ],
                        dependencies=["_config.yml"],
                    ),
                ],
            ),
            
            # Phase 4: Content Generation - Getting Started
            PhaseSpec(
                phase_id=4,
                name="Getting Started Documentation",
                description="Create getting started guides and tutorials",
                subtasks=[
                    SubtaskSpec(
                        mode="code",
                        description="Create getting started documentation",
                        message=f"""Create getting started guides and installation documentation in {self.output_dir}.

Create these files in a 'getting-started' directory:
1. index.md - Getting started hub page
   - Introduction to the getting started section
   - Links to each guide with brief descriptions
   
2. installation.md - Installation guide
   - Prerequisites
   - Step-by-step installation instructions
   - Troubleshooting common issues
   
3. quickstart.md - Quick start tutorial
   - First steps after installation
   - Simple example to demonstrate core functionality
   - Links to next steps
   
4. configuration.md - Configuration guide
   - Available configuration options
   - Example configurations
   - Best practices

These guides should be beginner-friendly and help new users successfully get up and running with the project.""",
                        expected_outputs=[
                            "getting-started/index.md",
                            "getting-started/installation.md",
                            "getting-started/quickstart.md",
                            "getting-started/configuration.md",
                        ],
                        dependencies=["PROJECT_OVERVIEW.md", "_layouts/page.html"],
                    ),
                ],
            ),
            
            # Phase 5: API Documentation
            PhaseSpec(
                phase_id=5,
                name="API Reference Documentation",
                description="Generate comprehensive API documentation",
                subtasks=[
                    SubtaskSpec(
                        mode="code",
                        description="Create API reference structure",
                        message=f"""Create the API reference documentation structure in {self.output_dir}.

Create an 'api' directory with:
1. index.md - API documentation hub page
   - Overview of the API documentation
   - How to use the API reference
   - High-level API categories or modules
   
2. Core API pages based on the project's main components
   - Create one .md file per major module/component
   - Include method signatures, parameters, return values
   - Add examples for each API method
   - Document edge cases and error handling
   
3. api-conventions.md - API conventions and patterns
   - Common patterns used throughout the API
   - Error handling conventions
   - Authentication and authorization if applicable

Organize the API documentation logically, making it easy for developers to find specific methods and understand how they work together.""",
                        expected_outputs=[
                            "api/index.md",
                            "api/api-conventions.md",
                        ],
                        dependencies=["PROJECT_OVERVIEW.md", "_layouts/api.html"],
                    ),
                ],
            ),
            
            # Phase 6: Guides and Tutorials
            PhaseSpec(
                phase_id=6,
                name="Guides and Tutorials",
                description="Create guides and tutorials for common tasks",
                subtasks=[
                    SubtaskSpec(
                        mode="code",
                        description="Create how-to guides and tutorials",
                        message=f"""Create how-to guides and tutorials in {self.output_dir}.

Create a 'guides' directory with:
1. index.md - Guides hub page
   - Overview of available guides and tutorials
   - Categorization by difficulty or use case
   
2. Create specific guide pages covering common tasks and use cases
   - Each guide should be focused on accomplishing a specific task
   - Include step-by-step instructions with code examples
   - Show expected outcomes and how to verify success
   - Mention common pitfalls and troubleshooting tips
   
3. best-practices.md - Best practices guide
   - Recommendations for effective use of the project
   - Performance optimization tips
   - Security considerations
   
4. troubleshooting.md - Troubleshooting guide
   - Common errors and their solutions
   - Debugging techniques
   - Where to get additional help

The guides should be practical, focusing on real-world tasks users need to accomplish.""",
                        expected_outputs=[
                            "guides/index.md",
                            "guides/best-practices.md",
                            "guides/troubleshooting.md",
                        ],
                        dependencies=["PROJECT_OVERVIEW.md", "_layouts/page.html"],
                    ),
                ],
            ),
            
            # Phase 7: Examples and Code Snippets
            PhaseSpec(
                phase_id=7,
                name="Examples and Code Snippets",
                description="Add concrete examples and code snippets",
                subtasks=[
                    SubtaskSpec(
                        mode="code",
                        description="Create examples and code snippets",
                        message=f"""Create examples and code snippets in {self.output_dir}.

Create an 'examples' directory with:
1. index.md - Examples hub page
   - Overview of available examples
   - How to use the examples effectively
   
2. Basic examples
   - Create pages with basic usage examples
   - Fully working, copy-paste ready code snippets
   - Clear explanations of what each example demonstrates
   
3. Advanced examples
   - More complex scenarios
   - Integration examples
   - Performance optimization examples
   
4. code-snippets.md - Common code snippets
   - Frequently used patterns
   - Helper functions
   - Utility code

Each example should be thoroughly documented with comments explaining key aspects. Include expected output where appropriate.""",
                        expected_outputs=[
                            "examples/index.md",
                            "examples/code-snippets.md",
                        ],
                        dependencies=["api/index.md", "_includes/code_example.html"],
                    ),
                ],
            ),
            
            # Phase 8: Search and Navigation
            PhaseSpec(
                phase_id=8,
                name="Search and Navigation",
                description="Enhance site search and navigation",
                subtasks=[
                    SubtaskSpec(
                        mode="code",
                        description="Implement search and improve navigation",
                        message=f"""Implement search functionality and enhance navigation in {self.output_dir}.

1. Add search functionality
   - Implement Jekyll-based search solution
   - Create a search results page template
   - Add search box to the layout
   
2. Enhance site navigation
   - Update _data/navigation.yml with complete structure
   - Create breadcrumb navigation
   - Add next/previous links on content pages
   - Ensure mobile-friendly navigation
   
3. Create a sitemap.xml for SEO
   - Configure jekyll-sitemap plugin
   - Ensure all pages are included
   
4. Create a tag/category system
   - Implement a tagging system for content
   - Create tag index pages
   - Add tag filtering capability

These enhancements will make the documentation more discoverable and easier to navigate.""",
                        expected_outputs=[
                            "search.md",
                            "_includes/search-box.html",
                            "_includes/breadcrumbs.html",
                            "_data/navigation.yml",
                            "tags.md",
                        ],
                        dependencies=["_layouts/default.html"],
                    ),
                ],
            ),
            
            # Phase 9: Final Polish and Deployment
            PhaseSpec(
                phase_id=9,
                name="Final Polish and Deployment",
                description="Final enhancements and deployment preparation",
                subtasks=[
                    SubtaskSpec(
                        mode="code",
                        description="Implement visual improvements and prepare for deployment",
                        message=f"""Finalize the documentation site in {self.output_dir} and prepare it for deployment.

1. Add visual enhancements
   - Optimize CSS for readability
   - Ensure consistent styling throughout
   - Improve code highlighting theme
   - Add favicons and branding elements
   
2. Create GitHub Pages configuration
   - Add or update _config.yml for GitHub Pages
   - Create .nojekyll file if needed
   - Add CNAME file if using a custom domain
   
3. Create deployment documentation
   - Add deployment.md with instructions
   - Include GitHub Pages setup steps
   - Document custom domain configuration
   - Include instructions for local testing
   
4. Implement final checks
   - Create a script to check for broken links
   - Validate HTML and accessibility
   - Ensure all images have alt text
   - Check mobile responsiveness

These final touches will make the documentation site professional and ready for deployment.""",
                        expected_outputs=[
                            "assets/css/main.scss",
                            "deployment.md",
                            "favicon.ico",
                            ".nojekyll",
                        ],
                        dependencies=["_config.yml"],
                    ),
                ],
            ),
            
            # Phase 10: Project Verification
            PhaseSpec(
                phase_id=10,
                name="Project Verification",
                description="Verify the documentation project is complete and functional",
                subtasks=[
                    SubtaskSpec(
                        mode="ask",
                        description="Verify documentation completeness",
                        message=f"""Review the completed Jekyll documentation site in {self.output_dir}.

Verify that:
1. All planned documentation sections are present
2. Navigation structure is complete and logical
3. Jekyll configuration is correct and will build successfully
4. Getting started guides are clear and beginner-friendly
5. API documentation covers the major components
6. Examples and code snippets are accurate
7. Search functionality is properly implemented
8. Site is ready for GitHub Pages deployment

Provide a summary of:
- What was created
- Key documentation sections
- Any recommendations for further improvements
- Next steps for deployment

If any critical issues or gaps are found, highlight them as areas for immediate attention.""",
                        expected_outputs=["Documentation verification summary"],
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
            "project_type": "jekyll_docs",
            "saved_at": datetime.now().isoformat(),
            "execution_mode": self.state.execution_mode,
            "output_dir": str(self.output_dir),
            "codebase_dir": str(self.codebase_dir),
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
        print("JEKYLL DOCUMENTATION SITE GENERATOR WORKFLOW")
        print("=" * 80)
        print(f"\nMode: {'DRY RUN' if self.dry_run else 'EXECUTION'}")
        if not self.dry_run:
            print(f"Provider: AWS Bedrock")
            print(f"Model: {self.model}")
        print(f"Codebase Directory: {self.codebase_dir}")
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
                    "code": "🔧",
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
        mode_icon = {"ask": "❓", "architect": "🏗️ ", "code": "🔧", "orchestrator": "💻", "debug": "🐛"}.get(subtask.mode, "🔧")
        
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
            print(f"   ⚙️  Executing task with AWS Bedrock {self.model}...")
            
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
        mode_icon = {"ask": "❓", "architect": "🏗️ ", "code": "🔧", "orchestrator": "💻", "debug": "🐛"}.get(subtask.mode, "🔧")
        
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
            print(f"   Using AWS Bedrock with model {self.model}")
            print(f"   Creating documentation from: {self.codebase_dir}")
            print(f"   Generating Jekyll site in: {self.output_dir}\n")
        
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
            print("   To actually execute, run with --execute flag and configure AWS credentials.")
        else:
            print(f"\n✨ Jekyll documentation site created successfully!")
            print(f"   Location: {self.output_dir}")
            print(f"\n📦 Next steps:")
            print(f"   1. cd {self.output_dir}")
            print(f"   2. bundle install")
            print(f"   3. bundle exec jekyll serve")
            print(f"   4. Open http://localhost:4000 in your browser")
        
        print()
        
        return True


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Jekyll Documentation Site Generator using AWS Bedrock",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Show the workflow (dry run)
  python bedrock_jekyll_docs_generator.py --dry-run
  
  # Execute with AWS Bedrock (requires AWS credentials)
  python bedrock_jekyll_docs_generator.py --execute --codebase-dir ./my-project --output-dir ./docs
  
  # Run specific phases only
  python bedrock_jekyll_docs_generator.py --execute --phases 1,2,3
  
  # Interactive mode (pause after each phase)
  python bedrock_jekyll_docs_generator.py --execute --interactive
  
  # Resume from checkpoint
  python bedrock_jekyll_docs_generator.py --execute --resume jekyll_docs_checkpoint.json
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
        help="Actually execute the workflow (requires AWS credentials)",
    )
    
    parser.add_argument(
        "--model",
        type=str,
        default="anthropic.claude-3-sonnet-20240229-v1:0",
        help="Bedrock model ID to use (default: anthropic.claude-3-sonnet-20240229-v1:0)",
    )
    
    parser.add_argument(
        "--aws-region",
        type=str,
        help="AWS region for Bedrock (defaults to AWS_REGION env var)",
    )
    
    parser.add_argument(
        "--aws-access-key",
        type=str,
        help="AWS access key ID (defaults to AWS_ACCESS_KEY_ID env var)",
    )
    
    parser.add_argument(
        "--aws-secret-key",
        type=str,
        help="AWS secret access key (defaults to AWS_SECRET_ACCESS_KEY env var)",
    )
    
    parser.add_argument(
        "--aws-session-token",
        type=str,
        help="AWS session token (defaults to AWS_SESSION_TOKEN env var)",
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
        "--codebase-dir",
        type=Path,
        required=True,
        help="Directory containing the codebase to document",
    )
    
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path.cwd() / "jekyll-docs-site",
        help="Directory where Jekyll documentation will be created (default: ./jekyll-docs-site)",
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
    
    # Check if codebase directory exists
    if not args.codebase_dir.exists():
        print(f"Error: Codebase directory '{args.codebase_dir}' does not exist")
        sys.exit(1)
    
    # Create runner
    try:
        runner = JekyllDocsWorkflowRunner(
            project_root=args.project_root,
            codebase_dir=args.codebase_dir,
            output_dir=args.output_dir,
            model=args.model,
            aws_region=args.aws_region,
            aws_access_key=args.aws_access_key,
            aws_secret_key=args.aws_secret_key,
            aws_session_token=args.aws_session_token,
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
        print("   Checkpoint saved. Resume with: --resume jekyll_docs_checkpoint.json")
        sys.exit(130)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())