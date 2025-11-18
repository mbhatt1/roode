"""
Roo Code Mode/Persona System

This module provides a complete mode/persona system for task orchestration,
including mode configuration, task management, and mode-aware agent capabilities.
"""

from .config import (
    ModeConfig,
    GroupOptions,
    GroupEntry,
    ModeConfigLoader,
    ModeSource,
)
from .task import Task, TaskState
from .builtin_modes import BUILTIN_MODES, get_builtin_mode
from .orchestrator import ModeOrchestrator
from .tools import SwitchModeTool, NewTaskTool
from .agent import ModeAgent

__all__ = [
    "ModeConfig",
    "GroupOptions",
    "GroupEntry",
    "ModeConfigLoader",
    "ModeSource",
    "Task",
    "TaskState",
    "BUILTIN_MODES",
    "get_builtin_mode",
    "ModeOrchestrator",
    "SwitchModeTool",
    "NewTaskTool",
    "ModeAgent",
]