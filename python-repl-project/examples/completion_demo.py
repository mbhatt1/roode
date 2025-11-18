#!/usr/bin/env python3
"""
Demonstration of the completion engine capabilities.

This script shows various completion scenarios and how the engine handles them.
"""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.pyrepl.completion import CompletionEngine, CompletionResult


class DemoContext:
    """Demo execution context."""
    
    def __init__(self):
        self.locals = {
            "my_variable": 42,
            "my_string": "hello world",
            "my_list": [1, 2, 3],
            "my_dict": {"key": "value"},
            "calculate": lambda x, y: x + y,
        }
        
        self.globals = {
            "sys": sys,
            "os": os,
            "Path": Path,
            "global_setting": True,
        }


def print_completions(title: str, completions: list):
    """Pretty print completions."""
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print('=' * 60)
    
    if not completions:
        print("  (no completions)")
        return
    
    for i, comp in enumerate(completions[:15], 1):  # Show first 15
        if isinstance(comp, CompletionResult):
            type_str = f"[{comp.type}]"
            print(f"  {i:2}. {comp.text:25} {type_str:15} (priority: {comp.priority})")
            if comp.description:
                desc = comp.description[:50]
                print(f"      → {desc}")
        else:
            print(f"  {i:2}. {comp}")
    
    if len(completions) > 15:
        print(f"  ... and {len(completions) - 15} more")


def demo_basic_completions():
    """Demo basic keyword and builtin completions."""
    print("\n" + "█" * 60)
    print("  BASIC COMPLETIONS")
    print("█" * 60)
    
    engine = CompletionEngine(use_jedi=False)
    
    # Keywords
    completions = engine.get_completions("fo", None)
    print_completions("Keywords starting with 'fo'", completions)
    
    # Builtins
    completions = engine.get_completions("pri", None)
    print_completions("Builtins starting with 'pri'", completions)
    
    # Empty prefix (show all)
    results = engine.get_completion_results("", None)
    print_completions("All available completions (sample)", results[:10])


def demo_context_completions():
    """Demo context-aware completions."""
    print("\n" + "█" * 60)
    print("  CONTEXT-AWARE COMPLETIONS")
    print("█" * 60)
    
    engine = CompletionEngine(use_jedi=False)
    context = DemoContext()
    
    # Local variables
    completions = engine.get_completions("my", context)
    print_completions("Variables starting with 'my'", completions)
    
    # Global variables
    completions = engine.get_completions("global", context)
    print_completions("Global variables starting with 'global'", completions)
    
    # Modules
    completions = engine.get_completions("sy", context)
    print_completions("Modules starting with 'sy'", completions)


def demo_attribute_completions():
    """Demo attribute and method completions."""
    print("\n" + "█" * 60)
    print("  ATTRIBUTE COMPLETIONS")
    print("█" * 60)
    
    engine = CompletionEngine(use_jedi=False)
    context = DemoContext()
    
    # String methods
    completions = engine.get_completions("my_string.up", context)
    print_completions("String methods starting with 'up'", completions)
    
    # List methods
    completions = engine.get_completions("my_list.app", context)
    print_completions("List methods starting with 'app'", completions)
    
    # Module attributes
    completions = engine.get_completions("os.path", context)
    print_completions("os module attributes containing 'path'", completions)
    
    # All string attributes
    results = engine.complete_attribute("test", "")
    print_completions("All string methods", results[:20])


def demo_import_completions():
    """Demo import statement completions."""
    print("\n" + "█" * 60)
    print("  IMPORT COMPLETIONS")
    print("█" * 60)
    
    engine = CompletionEngine(use_jedi=False)
    
    # Simple import
    completions = engine.get_completions("import sy", None)
    print_completions("Import statement: 'import sy'", completions)
    
    # From import
    completions = engine.get_completions("from os import ", None)
    print_completions("From import: 'from os import '", completions[:15])
    
    # Direct method
    completions = engine.complete_import("dat")
    print_completions("Module names starting with 'dat'", completions)
    
    # Submodule
    completions = engine.complete_import("os.pa")
    print_completions("Submodule: 'os.pa'", completions)


def demo_path_completions():
    """Demo file path completions."""
    print("\n" + "█" * 60)
    print("  PATH COMPLETIONS")
    print("█" * 60)
    
    engine = CompletionEngine(use_jedi=False)
    
    # Current directory
    completions = engine.complete_path("")
    print_completions("Current directory contents", completions[:10])
    
    # With prefix
    completions = engine.complete_path("sr")
    print_completions("Paths starting with 'sr'", completions)
    
    # Parent directory
    completions = engine.complete_path("../")
    print_completions("Parent directory contents", completions[:10])


def demo_completion_ranking():
    """Demo completion ranking."""
    print("\n" + "█" * 60)
    print("  COMPLETION RANKING")
    print("█" * 60)
    
    engine = CompletionEngine(use_jedi=False)
    
    # Create test results with different priorities
    results = [
        CompletionResult("test_builtin", type_="builtin", priority=80),
        CompletionResult("test_local", type_="local", priority=100),
        CompletionResult("test_global", type_="global", priority=90),
        CompletionResult("test_keyword", type_="keyword", priority=70),
    ]
    
    print("\nOriginal order:")
    for r in results:
        print(f"  {r.text:20} priority={r.priority}")
    
    ranked = engine.rank_completions(results, "test")
    
    print("\nRanked by priority:")
    for r in ranked:
        print(f"  {r.text:20} priority={r.priority}")
    
    # With frequency
    history = ["test_keyword"] * 20 + ["test_builtin"] * 5
    ranked_with_freq = engine.rank_completions(results, "test", history=history)
    
    print("\nRanked with frequency (test_keyword used 20x, test_builtin 5x):")
    for r in ranked_with_freq:
        print(f"  {r.text:20} priority={r.priority}")


def demo_detailed_results():
    """Demo detailed completion results."""
    print("\n" + "█" * 60)
    print("  DETAILED COMPLETION RESULTS")
    print("█" * 60)
    
    engine = CompletionEngine(use_jedi=False)
    
    # Get detailed results
    results = engine.get_completion_results("pri", None)
    
    print("\nDetailed information about 'pri' completions:")
    for result in results[:5]:
        print(f"\n  Text: {result.text}")
        print(f"  Display: {result.display}")
        print(f"  Type: {result.type}")
        print(f"  Priority: {result.priority}")
        if result.description:
            print(f"  Description: {result.description[:60]}...")


def demo_edge_cases():
    """Demo edge cases and special scenarios."""
    print("\n" + "█" * 60)
    print("  EDGE CASES")
    print("█" * 60)
    
    engine = CompletionEngine(use_jedi=False)
    context = DemoContext()
    
    # Empty string
    completions = engine.get_completions("", context)
    print_completions("Empty string (all completions)", completions[:10])
    
    # No matches
    completions = engine.get_completions("zzzzzzz", context)
    print_completions("No matches for 'zzzzzzz'", completions)
    
    # Multiple dots
    completions = engine.get_completions("sys.path", context)
    print_completions("Nested attribute: 'sys.path'", completions[:5])
    
    # Cursor in middle
    text = "print(x)"
    completions = engine.get_completions(text, context, cursor_pos=3)
    print_completions("Cursor at position 3 in 'print(x)'", completions[:5])


def demo_jedi_completions():
    """Demo Jedi-powered completions if available."""
    print("\n" + "█" * 60)
    print("  JEDI COMPLETIONS")
    print("█" * 60)
    
    try:
        import jedi
        print(f"\n✓ Jedi is available (version {jedi.__version__})")
        
        engine = CompletionEngine(use_jedi=True)
        context = DemoContext()
        
        # Jedi can provide more intelligent completions
        completions = engine.get_completions("my_string.sp", context)
        print_completions("Jedi completions for 'my_string.sp'", completions)
        
        # Get detailed results
        results = engine.get_completion_results("import js", None)
        print_completions("Jedi import completions for 'import js'", results)
        
    except ImportError:
        print("\n✗ Jedi is not available")
        print("  Install with: pip install jedi")
        print("  Falling back to basic completions")


def main():
    """Run all demonstrations."""
    print("""
    ╔════════════════════════════════════════════════════════════╗
    ║                                                            ║
    ║         PYTHON REPL COMPLETION ENGINE DEMO                ║
    ║                                                            ║
    ║  Showcasing intelligent, context-aware code completion    ║
    ║                                                            ║
    ╚════════════════════════════════════════════════════════════╝
    """)
    
    try:
        demo_basic_completions()
        demo_context_completions()
        demo_attribute_completions()
        demo_import_completions()
        demo_path_completions()
        demo_completion_ranking()
        demo_detailed_results()
        demo_edge_cases()
        demo_jedi_completions()
        
        print("\n" + "█" * 60)
        print("  DEMO COMPLETE")
        print("█" * 60)
        print("\nThe completion engine provides:")
        print("  ✓ Context-aware variable/function completions")
        print("  ✓ Attribute/method completions via introspection")
        print("  ✓ Import statement completions")
        print("  ✓ File path completions")
        print("  ✓ Smart ranking based on priority and frequency")
        print("  ✓ Detailed metadata for each completion")
        print("  ✓ Optional Jedi integration for advanced completions")
        print()
        
    except KeyboardInterrupt:
        print("\n\nDemo interrupted.")
    except Exception as e:
        print(f"\n\nError during demo: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
