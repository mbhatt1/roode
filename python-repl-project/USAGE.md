# PyREPL Usage Guide

This comprehensive guide covers all aspects of using PyREPL, from basic usage to advanced features and configuration options.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Basic Usage](#basic-usage)
3. [Special Commands](#special-commands)
4. [Configuration](#configuration)
5. [Advanced Features](#advanced-features)
6. [Tips and Tricks](#tips-and-tricks)
7. [Keyboard Shortcuts](#keyboard-shortcuts)
8. [Troubleshooting](#troubleshooting)

## Getting Started

### Starting PyREPL

Simply run the following command to start the REPL:

```bash
pyrepl
```

You'll be greeted with a banner showing version information:

```
PyREPL v1.0.0
Python 3.11.0

Type !help for help, !exit to quit.
Press Ctrl+D or Ctrl+C twice to exit.

>>> 
```

### Your First Commands

Try entering some Python code:

```python
>>> 2 + 2
4

>>> name = "Python"
>>> f"Hello, {name}!"
'Hello, Python!'

>>> import math
>>> math.pi
3.141592653589793
```

## Basic Usage

### Simple Expressions

PyREPL evaluates expressions and displays their results:

```python
>>> 5 * 10
50

>>> len("PyREPL")
6

>>> [x**2 for x in range(5)]
[0, 1, 4, 9, 16]
```

### Variable Assignment

Variables are automatically persisted across commands:

```python
>>> x = 42
>>> y = 100
>>> x + y
142
```

### Multi-line Input

Write functions, classes, and loops across multiple lines:

```python
>>> def factorial(n):
...     if n <= 1:
...         return 1
...     return n * factorial(n-1)
... 
>>> factorial(5)
120
```

**Note**: PyREPL automatically detects when you need multi-line input. Just press Enter after incomplete statements, and the prompt will change to `...` for continuation lines.

### Importing Modules

Import and use any Python module:

```python
>>> import json
>>> data = {"name": "PyREPL", "version": "1.0.0"}
>>> json.dumps(data, indent=2)
'{
  "name": "PyREPL",
  "version": "1.0.0"
}'
```

## Special Commands

PyREPL provides special commands that start with `!` for various operations.

### `!help` - Show Help

Display available commands and tips:

```python
>>> !help
```

This shows a table of all special commands with descriptions.

### `!vars` - List Variables

Display all variables in the current context:

```python
>>> x = 42
>>> y = "hello"
>>> z = [1, 2, 3]
>>> !vars
```

Output:
```
┏━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┓
┃ Name     ┃ Type        ┃ Value        ┃
┡━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━━━━━━━┩
│ x        │ int         │ 42           │
│ y        │ str         │ 'hello'      │
│ z        │ list        │ [1, 2, 3]    │
└──────────┴─────────────┴──────────────┘
Total: 3 variable(s)
```

### `!save` - Save Session

Save your current session state to a file:

```python
>>> x = 42
>>> y = [1, 2, 3]
>>> !save my_session.pkl
Session saved to: my_session.pkl
```

The session file includes all variables and imported modules.

### `!load` - Load Session

Restore a previously saved session:

```python
>>> !load my_session.pkl
Session loaded from: my_session.pkl
Loaded 2 variable(s)
```

### `!clear` - Clear Namespace

Clear all variables from the current session:

```python
>>> !clear
Clear all variables? [y/N]: y
Namespace cleared (3 variable(s) removed)
```

**Note**: Built-in functions are preserved.

### `!history` - Show History

Display recent command history:

```python
>>> !history
```

Shows the last 50 commands with syntax highlighting.

### `!exit` / `!quit` - Exit REPL

Exit the REPL:

```python
>>> !exit
Goodbye!
```

## Configuration

PyREPL can be configured through multiple methods, with the following priority (highest to lowest):

1. Command-line arguments (coming soon)
2. Environment variables
3. Configuration file
4. Default settings

### Configuration File

Create a configuration file at `~/.pyrepl/config.toml`:

```toml
[appearance]
theme = "monokai"
show_line_numbers = true
prompt_style = ">>> "
continuation_prompt = "... "
enable_syntax_highlighting = true
color_depth = 24

[behavior]
auto_indent = true
confirm_exit = true
enable_pager = true
auto_suggest = true
vi_mode = false
multiline_mode = true
auto_parentheses = true

[history]
history_size = 10000
save_history = true
search_history = true
```

### Environment Variables

Set environment variables with the `PYREPL_` prefix:

```bash
# Set theme
export PYREPL_APPEARANCE__THEME="dracula"

# Set history size
export PYREPL_HISTORY__HISTORY_SIZE=20000

# Enable VI mode
export PYREPL_BEHAVIOR__VI_MODE=true

# Disable auto-suggest
export PYREPL_BEHAVIOR__AUTO_SUGGEST=false
```

**Note**: Use double underscores (`__`) to separate section and setting names.

### Configuration Options Reference

#### Appearance Settings

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `theme` | string | `"monokai"` | Syntax highlighting theme |
| `show_line_numbers` | boolean | `true` | Show line numbers in output |
| `prompt_style` | string | `">>> "` | Primary prompt string |
| `continuation_prompt` | string | `"... "` | Continuation prompt string |
| `enable_syntax_highlighting` | boolean | `true` | Enable syntax highlighting |
| `color_depth` | integer | `24` | Color depth (1, 4, 8, or 24) |

#### Behavior Settings

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `auto_indent` | boolean | `true` | Automatic indentation |
| `confirm_exit` | boolean | `true` | Confirm before clearing/exiting |
| `enable_pager` | boolean | `true` | Use pager for long output |
| `auto_suggest` | boolean | `true` | Auto-suggest from history |
| `vi_mode` | boolean | `false` | Enable VI key bindings |
| `multiline_mode` | boolean | `true` | Enable multi-line editing |
| `auto_parentheses` | boolean | `true` | Auto-close parentheses |

#### History Settings

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `history_size` | integer | `10000` | Maximum history entries |
| `save_history` | boolean | `true` | Save history to disk |
| `search_history` | boolean | `true` | Enable history search |

### Available Themes

PyREPL supports any Pygments theme. Popular options include:

- `monokai` (default)
- `dracula`
- `solarized-dark`
- `solarized-light`
- `github-dark`
- `one-dark`
- `nord`
- `gruvbox-dark`
- `gruvbox-light`

## Advanced Features

### Auto-completion

Press **Tab** while typing to see completion suggestions:

```python
>>> import ma[TAB]
math  mailbox  marshal  ...

>>> math.p[TAB]
math.pi  math.pow  math.prod  ...
```

Auto-completion works for:
- Module names
- Function names
- Variable names
- Object attributes
- Dictionary keys (when possible)

### History Search

Use **Ctrl+R** to search through command history:

```
(reverse-i-search)`def': def factorial(n):
```

Press **Ctrl+R** again to cycle through matches.

### Auto-suggestion from History

As you type, PyREPL suggests commands from your history in gray text:

```python
>>> import mat[h]  # Gray suggestion
```

Press **→** (right arrow) or **End** to accept the suggestion.

### Context Persistence

All variables, functions, and imported modules persist throughout your session:

```python
>>> def greet(name):
...     return f"Hello, {name}!"
...
>>> greet("World")
'Hello, World!'

# Later in the session...
>>> greet("PyREPL")
'Hello, PyREPL!'
```

### Session Save/Load

Save your work and restore it later:

```python
# Session 1
>>> data = [1, 2, 3, 4, 5]
>>> def process(items):
...     return [x * 2 for x in items]
...
>>> !save work.pkl

# Later... (Session 2)
>>> !load work.pkl
>>> process(data)
[2, 4, 6, 8, 10]
```

### Rich Output Formatting

PyREPL uses the Rich library for beautiful output:

```python
>>> {"name": "PyREPL", "features": ["highlighting", "completion", "history"]}
{
    'name': 'PyREPL',
    'features': [
        'highlighting',
        'completion',
        'history'
    ]
}
```

### Exception Display

Errors are displayed with helpful formatting:

```python
>>> 1 / 0
╭─────────────────────────────────────╮
│ ZeroDivisionError                   │
│ division by zero                    │
╰─────────────────────────────────────╯
```

## Tips and Tricks

### 1. Quick Math

Use PyREPL as a powerful calculator:

```python
>>> from math import *
>>> sqrt(16)
4.0
>>> sin(pi / 2)
1.0
>>> log10(1000)
3.0
```

### 2. String Manipulation

Test string operations interactively:

```python
>>> text = "PyREPL is awesome"
>>> text.upper()
'PYREPL IS AWESOME'
>>> text.split()
['PyREPL', 'is', 'awesome']
>>> "".join(reversed(text))
'emosewa si LPERyP'
```

### 3. List Comprehensions

Experiment with list comprehensions:

```python
>>> [x**2 for x in range(10) if x % 2 == 0]
[0, 4, 16, 36, 64]
```

### 4. JSON Testing

Test JSON operations:

```python
>>> import json
>>> data = {"users": [{"name": "Alice", "age": 30}, {"name": "Bob", "age": 25}]}
>>> print(json.dumps(data, indent=2))
{
  "users": [
    {
      "name": "Alice",
      "age": 30
    },
    {
      "name": "Bob",
      "age": 25
    }
  ]
}
```

### 5. Module Exploration

Explore module contents:

```python
>>> import datetime
>>> dir(datetime)
[... list of available items ...]
>>> help(datetime.datetime.now)
```

### 6. Quick Prototyping

Test function implementations:

```python
>>> def fibonacci(n):
...     a, b = 0, 1
...     result = []
...     for _ in range(n):
...         result.append(a)
...         a, b = b, a + b
...     return result
...
>>> fibonacci(10)
[0, 1, 1, 2, 3, 5, 8, 13, 21, 34]
```

### 7. Working with Files

Test file operations safely:

```python
>>> from pathlib import Path
>>> Path.cwd()
PosixPath('/home/user/projects')
>>> list(Path.cwd().glob('*.py'))
[PosixPath('/home/user/projects/main.py'), ...]
```

### 8. Regular Expressions

Test regex patterns:

```python
>>> import re
>>> pattern = r'\d{3}-\d{3}-\d{4}'
>>> re.match(pattern, '123-456-7890')
<re.Match object; span=(0, 12), match='123-456-7890'>
```

### 9. Using _ for Last Result

The underscore `_` holds the last result:

```python
>>> 2 + 2
4
>>> _ * 10
40
>>> _ + 5
45
```

### 10. Multiline Strings

Create multiline strings easily:

```python
>>> text = """
... This is a
... multiline string
... """
>>> print(text)

This is a
multiline string

```

## Keyboard Shortcuts

### Navigation

| Shortcut | Action |
|----------|--------|
| **←** / **→** | Move cursor left/right |
| **Ctrl+A** / **Home** | Move to beginning of line |
| **Ctrl+E** / **End** | Move to end of line |
| **Ctrl+←** / **Ctrl+→** | Move by word |

### Editing

| Shortcut | Action |
|----------|--------|
| **Backspace** | Delete character before cursor |
| **Delete** | Delete character after cursor |
| **Ctrl+K** | Delete from cursor to end of line |
| **Ctrl+U** | Delete from cursor to beginning of line |
| **Ctrl+W** | Delete word before cursor |

### History

| Shortcut | Action |
|----------|--------|
| **↑** / **↓** | Navigate command history |
| **Ctrl+R** | Search history (reverse) |
| **Ctrl+S** | Search history (forward) |
| **→** / **End** | Accept auto-suggestion |

### Completion

| Shortcut | Action |
|----------|--------|
| **Tab** | Show completions / cycle forward |
| **Shift+Tab** | Cycle completions backward |

### Control

| Shortcut | Action |
|----------|--------|
| **Enter** | Execute command (or continue multiline) |
| **Ctrl+C** | Interrupt / clear input (press twice to exit) |
| **Ctrl+D** | Exit REPL |
| **Ctrl+L** | Clear screen (if supported) |

### VI Mode Shortcuts

If VI mode is enabled (`vi_mode = true`), you can use VI key bindings:

| Shortcut | Action |
|----------|--------|
| **Esc** | Enter command mode |
| **i** | Enter insert mode |
| **h/j/k/l** | Navigate (left/down/up/right) |
| **w/b** | Move by word (forward/backward) |
| **0/$** | Beginning/end of line |
| **dd** | Delete line |
| **yy** | Yank (copy) line |
| **p** | Paste |

## Troubleshooting

### Issue: PyREPL won't start

**Solution**: Ensure Python 3.9+ is installed and PyREPL is properly installed:

```bash
python --version  # Should be 3.9 or higher
pip show pyrepl   # Verify installation
```

### Issue: Syntax highlighting not working

**Solution**: Check your color depth setting:

```toml
[appearance]
color_depth = 24  # Try 8 or 4 if 24 doesn't work
```

Or disable it temporarily:

```bash
export PYREPL_APPEARANCE__ENABLE_SYNTAX_HIGHLIGHTING=false
```

### Issue: History not saving

**Solution**: Check file permissions:

```bash
ls -la ~/.pyrepl/
chmod 755 ~/.pyrepl/
```

Or specify a different location:

```toml
[history]
history_file = "/tmp/pyrepl_history"
```

### Issue: Auto-completion not working

**Solution**: Ensure you have the latest version and check that `complete_while_typing` isn't disabled by your terminal.

### Issue: Colors look wrong

**Solution**: Try different themes:

```python
>>> # Test in REPL
>>> from pyrepl.config import Config
>>> Config().appearance.theme = "solarized-dark"
```

Or set permanently:

```bash
export PYREPL_APPEARANCE__THEME="solarized-dark"
```

### Issue: VI mode keybindings not working

**Solution**: Ensure VI mode is enabled:

```toml
[behavior]
vi_mode = true
```

### Issue: Memory usage is high

**Solution**: Reduce history size:

```toml
[history]
history_size = 1000  # Reduced from default 10000
```

### Getting More Help

- Check the [GitHub Issues](https://github.com/yourusername/pyrepl/issues)
- Run `!help` within the REPL
- Read the [CONTRIBUTING.md](CONTRIBUTING.md) for development setup
- Check the [README.md](README.md) for architecture details

## Next Steps

- Explore the [examples](examples/) directory for more usage patterns
- Read [CONTRIBUTING.md](CONTRIBUTING.md) to contribute
- Check out the [API documentation](docs/) for advanced usage
- Customize your configuration to match your workflow

---

**Happy coding with PyREPL!** 🐍✨
