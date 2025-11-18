"""
Tests for completion engine.
"""

import os
import sys
from unittest.mock import Mock

import pytest

from src.pyrepl.completion import (
    CompletionEngine,
    CompletionResult,
    get_completions,
)


class MockContext:
    """Mock execution context for testing."""
    
    def __init__(self, locals_dict=None, globals_dict=None):
        self.locals = locals_dict or {}
        self.globals = globals_dict or {}


class TestCompletionResult:
    """Tests for CompletionResult class."""
    
    def test_creation(self):
        result = CompletionResult("test", type_="keyword", priority=10)
        assert result.text == "test"
        assert result.display == "test"
        assert result.type == "keyword"
        assert result.priority == 10
    
    def test_custom_display(self):
        result = CompletionResult("method", display="method()", type_="function")
        assert result.text == "method"
        assert result.display == "method()"
    
    def test_equality(self):
        r1 = CompletionResult("test")
        r2 = CompletionResult("test")
        r3 = CompletionResult("other")
        
        assert r1 == r2
        assert r1 != r3
    
    def test_hashable(self):
        r1 = CompletionResult("test")
        r2 = CompletionResult("test")
        
        result_set = {r1, r2}
        assert len(result_set) == 1


class TestCompletionEngine:
    """Tests for CompletionEngine class."""
    
    def test_initialization(self):
        engine = CompletionEngine()
        assert engine is not None
    
    def test_keyword_completion(self):
        engine = CompletionEngine(use_jedi=False)
        completions = engine.get_completions("fo", None)
        
        assert "for" in completions
        
        # Test 'from' separately
        completions = engine.get_completions("fr", None)
        assert "from" in completions
    
    def test_builtin_completion(self):
        engine = CompletionEngine(use_jedi=False)
        completions = engine.get_completions("pri", None)
        
        assert "print" in completions
    
    def test_context_variable_completion(self):
        engine = CompletionEngine(use_jedi=False)
        context = MockContext(
            locals_dict={"my_var": 42, "my_func": lambda: None},
        )
        
        completions = engine.get_completions("my", context)
        
        assert "my_var" in completions
        assert "my_func" in completions
    
    def test_global_variable_completion(self):
        engine = CompletionEngine(use_jedi=False)
        context = MockContext(
            globals_dict={"global_var": "test", "sys": sys},
        )
        
        completions = engine.get_completions("glo", context)
        assert "global_var" in completions
        
        completions = engine.get_completions("sy", context)
        assert "sys" in completions
    
    def test_empty_prefix(self):
        engine = CompletionEngine(use_jedi=False)
        context = MockContext(locals_dict={"var1": 1, "var2": 2})
        
        completions = engine.get_completions("", context)
        
        # Should return all available completions
        assert len(completions) > 0
        assert "var1" in completions
        assert "var2" in completions
    
    def test_no_context(self):
        engine = CompletionEngine(use_jedi=False)
        completions = engine.get_completions("prin", None)
        
        # Should still complete builtins and keywords
        assert "print" in completions
    
    def test_cursor_position(self):
        engine = CompletionEngine(use_jedi=False)
        text = "print(x)"
        
        # Complete at position 3 (should complete "pri")
        completions = engine.get_completions(text, None, cursor_pos=3)
        assert "print" in completions


class TestAttributeCompletion:
    """Tests for attribute completion."""
    
    def test_simple_attribute_completion(self):
        engine = CompletionEngine(use_jedi=False)
        
        obj = "test string"
        completions = engine.complete_attribute(obj, "upp")
        
        completion_texts = [c.text for c in completions]
        assert "upper" in completion_texts
    
    def test_method_display(self):
        engine = CompletionEngine(use_jedi=False)
        
        obj = "test"
        completions = engine.complete_attribute(obj, "")
        
        # Methods should have () in display
        method_comp = next((c for c in completions if c.text == "upper"), None)
        assert method_comp is not None
        assert method_comp.display == "upper()"
    
    def test_module_attribute_completion(self):
        engine = CompletionEngine(use_jedi=False)
        
        completions = engine.complete_attribute(os, "path")
        
        completion_texts = [c.text for c in completions]
        assert "path" in completion_texts
    
    def test_private_attributes_excluded(self):
        engine = CompletionEngine(use_jedi=False)
        
        obj = []
        completions = engine.complete_attribute(obj, "")
        
        # Private attributes should be excluded unless prefix starts with _
        completion_texts = [c.text for c in completions]
        assert not any(c.startswith("_") for c in completion_texts)
    
    def test_private_attributes_with_prefix(self):
        engine = CompletionEngine(use_jedi=False)
        
        obj = []
        completions = engine.complete_attribute(obj, "_")
        
        # Should include private attributes when explicitly requested
        completion_texts = [c.text for c in completions]
        assert any(c.startswith("_") for c in completion_texts)
    
    def test_attribute_chain_completion(self):
        engine = CompletionEngine(use_jedi=False)
        context = MockContext(locals_dict={"my_str": "test"})
        
        completions = engine.get_completions("my_str.upp", context)
        
        assert "upper" in completions


class TestImportCompletion:
    """Tests for import statement completion."""
    
    def test_import_statement_detection(self):
        engine = CompletionEngine(use_jedi=False)
        
        # Trigger import completion
        completions = engine.get_completions("import o", None)
        assert "os" in completions
    
    def test_from_import_statement(self):
        engine = CompletionEngine(use_jedi=False)
        
        completions = engine.get_completions("from os import ", None)
        # Should complete os module members
        assert len(completions) > 0
    
    def test_import_completion_method(self):
        engine = CompletionEngine(use_jedi=False)
        
        completions = engine.complete_import("sy")
        assert "sys" in completions
    
    def test_submodule_import(self):
        engine = CompletionEngine(use_jedi=False)
        
        completions = engine.complete_import("os.pa")
        assert "os.path" in completions
    
    def test_import_cache_building(self):
        engine = CompletionEngine(use_jedi=False)
        engine._build_import_cache()
        
        assert engine._import_cache is not None
        assert len(engine._import_cache) > 0
        assert "sys" in engine._import_cache
        assert "os" in engine._import_cache


class TestPathCompletion:
    """Tests for file path completion."""
    
    def test_current_directory_completion(self):
        engine = CompletionEngine(use_jedi=False)
        
        completions = engine.complete_path("")
        
        # Should list current directory contents
        assert len(completions) > 0
    
    def test_directory_slash(self):
        engine = CompletionEngine(use_jedi=False)
        
        # Create results directly since we need CompletionResult objects
        results = engine._get_path_completions(".")
        
        # Directories should have trailing slash in display
        for result in results:
            if result.display.endswith("/"):
                # This is a directory
                assert result.type == "path"
    
    def test_path_with_prefix(self):
        engine = CompletionEngine(use_jedi=False)
        
        # Test with src prefix (assuming src directory exists)
        completions = engine.complete_path("sr")
        
        # Should filter to items starting with sr
        assert all("sr" in c.lower() or c.startswith("sr") for c in completions if completions)
    
    def test_invalid_path(self):
        engine = CompletionEngine(use_jedi=False)
        
        completions = engine.complete_path("/nonexistent/path/xyz")
        
        # Should return empty list or handle gracefully
        assert isinstance(completions, list)


class TestCompletionContext:
    """Tests for context analysis."""
    
    def test_general_completion_context(self):
        engine = CompletionEngine(use_jedi=False)
        
        prefix, comp_type = engine._analyze_completion_context("prin")
        assert prefix == "prin"
        assert comp_type == "general"
    
    def test_attribute_completion_context(self):
        engine = CompletionEngine(use_jedi=False)
        
        prefix, comp_type = engine._analyze_completion_context("obj.attr")
        assert comp_type == "attribute"
    
    def test_import_completion_context(self):
        engine = CompletionEngine(use_jedi=False)
        
        prefix, comp_type = engine._analyze_completion_context("import sy")
        assert comp_type == "import"
        assert prefix == "sy"
    
    def test_from_import_context(self):
        engine = CompletionEngine(use_jedi=False)
        
        prefix, comp_type = engine._analyze_completion_context("from os import pa")
        assert comp_type == "import"
        assert prefix == "pa"


class TestSafeEval:
    """Tests for safe evaluation."""
    
    def test_simple_variable(self):
        engine = CompletionEngine(use_jedi=False)
        context = MockContext(locals_dict={"x": 42})
        
        result = engine._safe_eval("x", context)
        assert result == 42
    
    def test_attribute_access(self):
        engine = CompletionEngine(use_jedi=False)
        context = MockContext(locals_dict={"s": "test"})
        
        result = engine._safe_eval("s", context)
        assert result == "test"
    
    def test_invalid_expression(self):
        engine = CompletionEngine(use_jedi=False)
        context = MockContext()
        
        result = engine._safe_eval("undefined_var", context)
        assert result is None
    
    def test_no_context(self):
        engine = CompletionEngine(use_jedi=False)
        
        result = engine._safe_eval("anything", None)
        assert result is None


class TestCompletionRanking:
    """Tests for completion ranking."""
    
    def test_priority_ranking(self):
        engine = CompletionEngine(use_jedi=False)
        
        results = [
            CompletionResult("local_var", type_="local", priority=100),
            CompletionResult("global_var", type_="global", priority=90),
            CompletionResult("builtin", type_="builtin", priority=80),
        ]
        
        ranked = engine.rank_completions(results, "")
        
        # Should be sorted by priority (descending)
        assert ranked[0].text == "local_var"
        assert ranked[1].text == "global_var"
        assert ranked[2].text == "builtin"
    
    def test_frequency_ranking(self):
        engine = CompletionEngine(use_jedi=False)
        
        results = [
            CompletionResult("rare", priority=50),
            CompletionResult("common", priority=50),
        ]
        
        history = ["common" for _ in range(10)] + ["rare"]
        
        ranked = engine.rank_completions(results, "", history=history)
        
        # More frequent items should rank higher
        assert ranked[0].text == "common"
    
    def test_prefix_match_quality(self):
        engine = CompletionEngine(use_jedi=False)
        
        results = [
            CompletionResult("test_long", priority=50),
            CompletionResult("test", priority=50),
            CompletionResult("testing", priority=50),
        ]
        
        ranked = engine.rank_completions(results, "test")
        
        # Exact match should rank highest
        assert ranked[0].text == "test"


class TestConvenienceFunction:
    """Tests for convenience function."""
    
    def test_get_completions_function(self):
        context = MockContext(locals_dict={"my_var": 42})
        
        completions = get_completions("my", context)
        
        assert isinstance(completions, list)
        assert "my_var" in completions


class TestDetailedCompletionResults:
    """Tests for detailed completion results."""
    
    def test_get_completion_results(self):
        engine = CompletionEngine(use_jedi=False)
        context = MockContext(locals_dict={"test_var": 123})
        
        results = engine.get_completion_results("test", context)
        
        assert isinstance(results, list)
        assert all(isinstance(r, CompletionResult) for r in results)
        
        # Find our variable
        var_result = next((r for r in results if r.text == "test_var"), None)
        assert var_result is not None
        assert var_result.type == "local"
    
    def test_result_metadata(self):
        engine = CompletionEngine(use_jedi=False)
        
        results = engine.get_completion_results("pri", None)
        
        # Find print
        print_result = next((r for r in results if r.text == "print"), None)
        assert print_result is not None
        assert print_result.type in ["builtin", "function", "class"]
        assert print_result.priority > 0


class TestEdgeCases:
    """Tests for edge cases and error handling."""
    
    def test_empty_string(self):
        engine = CompletionEngine(use_jedi=False)
        
        completions = engine.get_completions("", None)
        
        # Should return some completions
        assert len(completions) > 0
    
    def test_whitespace_handling(self):
        engine = CompletionEngine(use_jedi=False)
        
        completions = engine.get_completions("  pri  ", None)
        
        # Should handle whitespace
        assert isinstance(completions, list)
    
    def test_special_characters(self):
        engine = CompletionEngine(use_jedi=False)
        context = MockContext(locals_dict={"var_with_underscore": 1})
        
        completions = engine.get_completions("var_", context)
        
        assert "var_with_underscore" in completions
    
    def test_unicode_handling(self):
        engine = CompletionEngine(use_jedi=False)
        context = MockContext(locals_dict={"变量": 42})  # Chinese characters
        
        completions = engine.get_completions("变", context)
        
        # Should handle Unicode
        assert isinstance(completions, list)
    
    def test_very_long_prefix(self):
        engine = CompletionEngine(use_jedi=False)
        
        long_prefix = "a" * 1000
        completions = engine.get_completions(long_prefix, None)
        
        # Should handle gracefully
        assert isinstance(completions, list)
    
    def test_malformed_attribute_access(self):
        engine = CompletionEngine(use_jedi=False)
        
        completions = engine.get_completions("...", None)
        
        # Should not crash
        assert isinstance(completions, list)


class TestStringDetection:
    """Tests for string literal detection."""
    
    def test_in_single_quote_string(self):
        engine = CompletionEngine(use_jedi=False)
        
        in_string = engine._is_in_string("'hello")
        assert in_string is True
    
    def test_in_double_quote_string(self):
        engine = CompletionEngine(use_jedi=False)
        
        in_string = engine._is_in_string('"hello')
        assert in_string is True
    
    def test_closed_string(self):
        engine = CompletionEngine(use_jedi=False)
        
        in_string = engine._is_in_string("'hello'")
        assert in_string is False
    
    def test_escaped_quotes(self):
        engine = CompletionEngine(use_jedi=False)
        
        in_string = engine._is_in_string("'hello\\'world")
        assert in_string is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
