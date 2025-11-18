"""
Example demonstrating the Mode/Persona system in Roo Code SDK.

This example shows how to use different modes for different types of tasks,
including mode switching, task delegation, and custom mode configuration.
"""

import asyncio
from pathlib import Path

from roo_code import RooClient, ProviderSettings
from roo_code.modes import ModeAgent


async def basic_mode_usage():
    """Basic example of using a mode-aware agent."""
    print("=== Basic Mode Usage ===\n")

    client = RooClient(
        provider_settings=ProviderSettings(
            api_provider="anthropic",
            api_key="your-api-key",
            api_model_id="claude-sonnet-4-5",
        )
    )

    # Create agent in code mode
    agent = ModeAgent(client=client, mode_slug="code", project_root=Path.cwd())

    # Get mode information
    mode_info = agent.get_mode_info()
    print(f"Current mode: {mode_info['name']}")
    print(f"Description: {mode_info['description']}")
    print(f"Tool groups: {mode_info['groups']}\n")

    # Run a coding task
    result = await agent.run("Create a simple function to calculate fibonacci numbers")
    print(f"Result: {result}\n")


async def mode_switching():
    """Example of switching between modes."""
    print("=== Mode Switching ===\n")

    client = RooClient(
        provider_settings=ProviderSettings(
            api_provider="anthropic",
            api_key="your-api-key",
            api_model_id="claude-sonnet-4-5",
        )
    )

    # Start in architect mode for planning
    agent = ModeAgent(client=client, mode_slug="architect")
    print(f"Starting in {agent.get_current_mode_name()}\n")

    # Plan the solution
    plan = await agent.run(
        "Plan the architecture for a REST API that manages a todo list"
    )
    print(f"Plan: {plan}\n")

    # Switch to code mode for implementation
    agent.switch_mode("code", reason="Ready to implement the planned architecture")
    print(f"Switched to {agent.get_current_mode_name()}\n")

    # Implement the code
    result = await agent.run("Implement the todo list API based on the plan")
    print(f"Implementation: {result}\n")


async def using_orchestrator():
    """Example of using the orchestrator mode for complex workflows."""
    print("=== Using Orchestrator Mode ===\n")

    client = RooClient(
        provider_settings=ProviderSettings(
            api_provider="anthropic",
            api_key="your-api-key",
            api_model_id="claude-sonnet-4-5",
        )
    )

    # Create agent in orchestrator mode
    agent = ModeAgent(client=client, mode_slug="orchestrator")

    # The orchestrator will break down the complex task and delegate to appropriate modes
    result = await agent.run(
        """
        Build a web scraper that:
        1. Scrapes job listings from a website
        2. Stores data in a SQLite database
        3. Includes error handling and logging
        4. Has comprehensive tests
        
        Break this down into steps and delegate to appropriate modes.
        """
    )

    print(f"Project completion: {result}\n")

    # Get task hierarchy
    task_info = agent.get_task_info()
    print(f"Created {len(task_info['child_task_ids'])} subtasks")


async def read_only_mode():
    """Example of using ask mode for read-only analysis."""
    print("=== Read-Only Mode (Ask) ===\n")

    client = RooClient(
        provider_settings=ProviderSettings(
            api_provider="anthropic",
            api_key="your-api-key",
            api_model_id="claude-sonnet-4-5",
        )
    )

    # Create agent in ask mode (read-only)
    agent = ModeAgent(client=client, mode_slug="ask")

    # The agent can read and analyze but not modify files
    result = await agent.run(
        "Analyze the codebase and explain the main architectural patterns used"
    )

    print(f"Analysis: {result}\n")

    # Verify read-only restrictions
    available_tools = agent.get_available_tools()
    print(f"Available tools in ask mode: {available_tools}")
    print(
        f"Can edit files: {'write_to_file' in available_tools}"
    )  # Should be False


async def debug_mode_example():
    """Example of using debug mode for troubleshooting."""
    print("=== Debug Mode ===\n")

    client = RooClient(
        provider_settings=ProviderSettings(
            api_provider="anthropic",
            api_key="your-api-key",
            api_model_id="claude-sonnet-4-5",
        )
    )

    # Create agent in debug mode
    agent = ModeAgent(client=client, mode_slug="debug")

    # Debug mode encourages systematic problem diagnosis
    result = await agent.run(
        """
        The application crashes when processing large files.
        Investigate the root cause:
        1. Analyze the error logs
        2. Identify likely sources
        3. Add diagnostic logging
        4. Confirm the hypothesis
        """
    )

    print(f"Debug findings: {result}\n")


async def custom_modes():
    """Example of working with custom modes."""
    print("=== Custom Modes ===\n")

    client = RooClient(
        provider_settings=ProviderSettings(
            api_provider="anthropic",
            api_key="your-api-key",
            api_model_id="claude-sonnet-4-5",
        )
    )

    agent = ModeAgent(client=client, mode_slug="code")

    # List all available modes
    all_modes = agent.get_all_modes()
    print("Available modes:")
    for mode in all_modes:
        source = mode.get("source", "builtin")
        print(f"  - {mode['slug']}: {mode['name']} ({source})")

    print(
        "\nTo add custom modes, create:"
    )
    print("  - Global: ~/.roo-code/modes.yaml")
    print("  - Project: .roomodes in project root\n")


async def file_restrictions():
    """Example demonstrating file editing restrictions."""
    print("=== File Restrictions ===\n")

    client = RooClient(
        provider_settings=ProviderSettings(
            api_provider="anthropic",
            api_key="your-api-key",
            api_model_id="claude-sonnet-4-5",
        )
    )

    # Architect mode can only edit markdown files
    agent = ModeAgent(client=client, mode_slug="architect")

    # Check file editing permissions
    can_edit_md = agent.orchestrator.can_edit_file(agent.current_task, "README.md")
    can_edit_py = agent.orchestrator.can_edit_file(agent.current_task, "main.py")

    print(f"Architect mode file permissions:")
    print(f"  - Can edit README.md: {can_edit_md}")  # True
    print(f"  - Can edit main.py: {can_edit_py}\n")  # False

    # This would work
    result = await agent.run("Update the README.md with project documentation")
    print(f"Markdown edit: Success\n")

    # This would be blocked
    try:
        result = await agent.run("Update main.py with new features")
    except PermissionError as e:
        print(f"Python edit blocked: {e}\n")


async def main():
    """Run all examples."""
    examples = [
        ("Basic Mode Usage", basic_mode_usage),
        ("Mode Switching", mode_switching),
        ("Orchestrator Mode", using_orchestrator),
        ("Read-Only Mode", read_only_mode),
        ("Debug Mode", debug_mode_example),
        ("Custom Modes", custom_modes),
        ("File Restrictions", file_restrictions),
    ]

    for title, example_func in examples:
        try:
            print(f"\n{'=' * 60}")
            print(f"{title}")
            print(f"{'=' * 60}\n")
            await example_func()
        except Exception as e:
            print(f"Error in {title}: {e}\n")

    print("\nAll examples completed!")


if __name__ == "__main__":
    # Note: Replace "your-api-key" with your actual API key
    # You can also set it via environment variable:
    # export ANTHROPIC_API_KEY=your-api-key
    asyncio.run(main())