"""Command execution tools."""

import asyncio
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional
from ..tools import Tool, ToolInputSchema, ToolResult


class ExecuteCommandTool(Tool):
    """Tool for executing CLI commands with automatic retry on transient failures."""
    
    def __init__(self, cwd: str = ".", enable_retry: bool = True):
        self.cwd = cwd
        super().__init__(
            name="execute_command",
            description=(
                "Request to execute a CLI command on the system. Use this when you need to "
                "perform system operations or run specific commands to accomplish any step in "
                "the user's task. You must tailor your command to the user's system and provide "
                "a clear explanation of what the command does."
            ),
            input_schema=ToolInputSchema(
                type="object",
                properties={
                    "command": {
                        "type": "string",
                        "description": (
                            "The CLI command to execute. This should be valid for the current "
                            "operating system."
                        )
                    },
                    "cwd": {
                        "type": "string",
                        "description": (
                            "The working directory to execute the command in. Optional, "
                            "defaults to workspace directory."
                        )
                    }
                },
                required=["command"]
            ),
            enable_retry=enable_retry,
            enable_circuit_breaker=False  # Commands are often one-off, don't need circuit breaker
        )
    
    async def execute(self, input_data: Dict[str, Any]) -> ToolResult:
        """Execute a shell command with proper error classification."""
        from .error_recovery import (
            ValidationError, FileNotFoundError as RooFileNotFoundError,
            NetworkError, TimeoutError as RooTimeoutError
        )
        
        try:
            # Validate input_data structure
            if not isinstance(input_data, dict):
                raise ValidationError(
                    f"Invalid input_data type: expected dict, got {type(input_data).__name__}. "
                    f"Value: {input_data}"
                )
            
            # Check for required 'command' parameter
            if "command" not in input_data:
                available_keys = list(input_data.keys())
                raise ValidationError(
                    f"Missing required parameter 'command'. "
                    f"Available parameters: {available_keys}. "
                    f"Input data: {input_data}"
                )
            
            command = input_data["command"]
            cwd = input_data.get("cwd", self.cwd)
            
            # Resolve absolute path for cwd
            abs_cwd = Path(cwd).resolve()
            
            if not abs_cwd.exists():
                # Non-recoverable: directory doesn't exist
                raise RooFileNotFoundError(f"Working directory not found: {cwd}")
            
            # Execute command
            try:
                # Use shell=True to support command chaining, pipes, etc.
                process = await asyncio.create_subprocess_shell(
                    command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=str(abs_cwd)
                )
                
                # Wait for command to complete with timeout
                try:
                    stdout, stderr = await asyncio.wait_for(
                        process.communicate(),
                        timeout=300  # 5 minute timeout
                    )
                except asyncio.TimeoutError:
                    process.kill()
                    # Recoverable: might succeed on retry
                    raise RooTimeoutError("Command timed out after 5 minutes")
                
                # Decode output
                stdout_text = stdout.decode('utf-8', errors='replace').strip()
                stderr_text = stderr.decode('utf-8', errors='replace').strip()
                
                # Format output
                output_parts = []
                
                if process.returncode == 0:
                    output_parts.append(f"Command executed successfully (exit code: 0)")
                else:
                    output_parts.append(f"Command failed with exit code: {process.returncode}")
                
                if stdout_text:
                    output_parts.append(f"\nStdout:\n{stdout_text}")
                
                if stderr_text:
                    output_parts.append(f"\nStderr:\n{stderr_text}")
                
                if not stdout_text and not stderr_text:
                    output_parts.append("\n(No output)")
                
                content = "\n".join(output_parts)
                
                return ToolResult(
                    tool_use_id=self.current_use_id,
                    content=content,
                    is_error=process.returncode != 0
                )
                
            except OSError as e:
                # Network/IO errors might be transient
                if "Connection" in str(e) or "Network" in str(e):
                    raise NetworkError(f"Network error executing command: {str(e)}")
                else:
                    # Other OS errors are likely permanent
                    raise ValidationError(f"OS error executing command: {str(e)}")
            
            except Exception as e:
                # Unknown errors - don't retry by default
                raise ValidationError(f"Error executing command: {str(e)}")
            
        except (ValidationError, RooFileNotFoundError, RooTimeoutError, NetworkError):
            # These are our custom errors, re-raise them
            raise
        except Exception as e:
            # Unexpected errors preparing execution
            raise ValidationError(f"Error preparing command execution: {str(e)}")