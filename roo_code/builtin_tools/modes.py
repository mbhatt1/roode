"""Mode system with file restrictions for tool execution."""

import re
from typing import List, Optional
from pydantic import BaseModel, Field


class FileRestrictionError(Exception):
    """Exception raised when a file operation is not allowed in the current mode."""

    def __init__(self, file_path: str, mode_name: str, allowed_patterns: List[str]):
        self.file_path = file_path
        self.mode_name = mode_name
        self.allowed_patterns = allowed_patterns
        message = (
            f"File operation on '{file_path}' is not allowed in {mode_name} mode. "
            f"This mode can only edit files matching: {', '.join(allowed_patterns)}"
        )
        super().__init__(message)


class ModeConfig(BaseModel):
    """Configuration for a specific mode with file restrictions.
    
    Modes define the context in which tools operate, including which files
    they are allowed to modify.
    
    Attributes:
        name: Human-readable name of the mode (e.g., "💻 Code")
        slug: Machine-readable identifier (e.g., "code")
        file_patterns: List of regex patterns for allowed file edits.
                      Empty list means all files are allowed.
        description: Optional description of the mode's purpose
    
    Examples:
        >>> architect_mode = ModeConfig(
        ...     name="🏗️ Architect",
        ...     slug="architect",
        ...     file_patterns=[r"\.md$"],
        ...     description="Planning and design mode - can only edit markdown files"
        ... )
        >>> architect_mode.allows_file_edit("README.md")
        True
        >>> architect_mode.allows_file_edit("src/main.py")
        False
    """

    name: str = Field(description="Human-readable mode name")
    slug: str = Field(description="Machine-readable mode identifier")
    file_patterns: List[str] = Field(
        default_factory=list,
        description="Regex patterns for allowed file edits. Empty = all files allowed"
    )
    description: Optional[str] = Field(
        default=None,
        description="Description of the mode's purpose"
    )

    def allows_file_edit(self, file_path: str) -> bool:
        """Check if a file path is allowed for editing in this mode.
        
        Args:
            file_path: Path to the file to check
            
        Returns:
            True if the file can be edited, False otherwise
        """
        # Empty patterns list means all files are allowed
        if not self.file_patterns:
            return True
        
        # Check if file matches any of the allowed patterns
        for pattern in self.file_patterns:
            if re.search(pattern, file_path):
                return True
        
        return False
    
    def check_file_edit(self, file_path: str) -> None:
        """Check if a file edit is allowed, raising an exception if not.
        
        Args:
            file_path: Path to the file to check
            
        Raises:
            FileRestrictionError: If the file cannot be edited in this mode
        """
        if not self.allows_file_edit(file_path):
            raise FileRestrictionError(file_path, self.name, self.file_patterns)


# Predefined mode configurations matching the TypeScript implementation
ARCHITECT_MODE = ModeConfig(
    name="🏗️ Architect",
    slug="architect",
    file_patterns=[r"\.md$"],
    description="Planning and design mode - can only edit markdown files"
)

CODE_MODE = ModeConfig(
    name="💻 Code",
    slug="code",
    file_patterns=[],  # Can edit all files
    description="Full code editing mode - can edit any file"
)

ASK_MODE = ModeConfig(
    name="❓ Ask",
    slug="ask",
    file_patterns=[],  # No editing typically, but no restrictions if needed
    description="Q&A mode for explanations and documentation"
)

DEBUG_MODE = ModeConfig(
    name="🪲 Debug",
    slug="debug",
    file_patterns=[],  # Can edit all files for fixes
    description="Debugging mode - can edit any file to fix issues"
)

TEST_MODE = ModeConfig(
    name="🧪 Test",
    slug="test",
    file_patterns=[
        r"test[s]?/.*",  # Files in test/tests directories
        r".*[._]test\.py$",  # Python test files
        r".*[._]spec\.py$",  # Python spec files
        r".*\.test\..*$",  # Generic test files
        r".*\.spec\..*$",  # Generic spec files
    ],
    description="Testing mode - can only edit test files"
)


def get_mode_by_slug(slug: str) -> Optional[ModeConfig]:
    """Get a mode configuration by its slug.
    
    Args:
        slug: The mode slug to look up
        
    Returns:
        The ModeConfig if found, None otherwise
    """
    modes = {
        "architect": ARCHITECT_MODE,
        "code": CODE_MODE,
        "ask": ASK_MODE,
        "debug": DEBUG_MODE,
        "test": TEST_MODE,
    }
    return modes.get(slug)


def get_all_modes() -> List[ModeConfig]:
    """Get all predefined mode configurations.
    
    Returns:
        List of all available ModeConfig objects
    """
    return [
        ARCHITECT_MODE,
        CODE_MODE,
        ASK_MODE,
        DEBUG_MODE,
        TEST_MODE,
    ]