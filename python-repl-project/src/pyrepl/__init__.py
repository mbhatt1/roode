"""
PyREPL - A Modern Python REPL

A feature-rich, modern Python Read-Eval-Print Loop (REPL) with syntax highlighting,
auto-completion, and advanced interactive features.

Example:
    >>> from pyrepl import REPL
    >>> repl = REPL()
    >>> repl.run()

Attributes:
    __version__ (str): The current version of PyREPL
    __author__ (str): The author of PyREPL
    __license__ (str): The license under which PyREPL is distributed
"""

from typing import List

__version__ = "0.1.0"
__author__ = "Your Name"
__license__ = "MIT"

# Public API exports
__all__: List[str] = [
    "__version__",
    "__author__",
    "__license__",
]


def get_version() -> str:
    """
    Get the current version of PyREPL.

    Returns:
        str: The version string in semantic versioning format (e.g., "0.1.0")

    Example:
        >>> from pyrepl import get_version
        >>> print(get_version())
        0.1.0
    """
    return __version__


def get_info() -> dict[str, str]:
    """
    Get information about PyREPL.

    Returns:
        dict[str, str]: A dictionary containing version, author, and license information

    Example:
        >>> from pyrepl import get_info
        >>> info = get_info()
        >>> print(f"PyREPL v{info['version']}")
        PyREPL v0.1.0
    """
    return {
        "version": __version__,
        "author": __author__,
        "license": __license__,
    }


# Package-level initialization
def _initialize() -> None:
    """
    Initialize the PyREPL package.

    This function is called when the package is imported and performs any
    necessary initialization tasks.
    """
    pass


# Run initialization
_initialize()
