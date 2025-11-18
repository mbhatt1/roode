"""Tests for parameter similarity calculation."""

import pytest
from roo_code.builtin_tools.parameter_similarity import ParameterSimilarity


class TestParameterSimilarity:
    """Test parameter similarity calculations."""
    
    def test_exact_match(self):
        """Test that identical parameters return 1.0 similarity."""
        params1 = {"path": "test.py", "line": 10}
        params2 = {"path": "test.py", "line": 10}
        
        similarity = ParameterSimilarity.calculate(params1, params2)
        assert similarity == 1.0
    
    def test_completely_different(self):
        """Test that completely different parameters return low similarity."""
        params1 = {"path": "test.py", "line": 10}
        params2 = {"file": "other.js", "number": 20}
        
        similarity = ParameterSimilarity.calculate(params1, params2)
        assert similarity == 0.0
    
    def test_empty_params(self):
        """Test that empty parameters are handled correctly."""
        # Both empty
        assert ParameterSimilarity.calculate({}, {}) == 1.0
        
        # One empty
        assert ParameterSimilarity.calculate({}, {"key": "value"}) == 0.0
        assert ParameterSimilarity.calculate({"key": "value"}, {}) == 0.0
    
    def test_string_similarity(self):
        """Test string similarity using Levenshtein distance."""
        params1 = {"search": "TODO"}
        params2 = {"search": "TODOO"}  # Very similar
        
        similarity = ParameterSimilarity.calculate(params1, params2)
        assert similarity > 0.8
        
        params3 = {"search": "FIXME"}  # Different
        similarity2 = ParameterSimilarity.calculate(params1, params3)
        assert similarity2 < 0.5
    
    def test_numeric_values(self):
        """Test exact matching for numeric values."""
        params1 = {"line": 10, "count": 5}
        params2 = {"line": 10, "count": 5}
        params3 = {"line": 10, "count": 6}
        
        assert ParameterSimilarity.calculate(params1, params2) == 1.0
        assert ParameterSimilarity.calculate(params1, params3) == 0.5  # One match, one diff
    
    def test_boolean_values(self):
        """Test exact matching for boolean values."""
        params1 = {"recursive": True, "hidden": False}
        params2 = {"recursive": True, "hidden": False}
        params3 = {"recursive": False, "hidden": False}
        
        assert ParameterSimilarity.calculate(params1, params2) == 1.0
        assert ParameterSimilarity.calculate(params1, params3) == 0.5
    
    def test_none_values(self):
        """Test handling of None values."""
        params1 = {"key": None}
        params2 = {"key": None}
        params3 = {"key": "value"}
        
        assert ParameterSimilarity.calculate(params1, params2) == 1.0
        assert ParameterSimilarity.calculate(params1, params3) == 0.0
    
    def test_list_similarity(self):
        """Test similarity for list parameters."""
        params1 = {"files": ["a.py", "b.py", "c.py"]}
        params2 = {"files": ["a.py", "b.py", "c.py"]}
        params3 = {"files": ["a.py", "b.py", "d.py"]}  # One different
        
        # Exact match
        assert ParameterSimilarity.calculate(params1, params2) == 1.0
        
        # Partial match
        similarity = ParameterSimilarity.calculate(params1, params3)
        assert 0.6 < similarity < 1.0
    
    def test_nested_dict_similarity(self):
        """Test similarity for nested dictionaries."""
        params1 = {
            "config": {
                "host": "localhost",
                "port": 8080
            }
        }
        params2 = {
            "config": {
                "host": "localhost",
                "port": 8080
            }
        }
        params3 = {
            "config": {
                "host": "localhost",
                "port": 9000
            }
        }
        
        # Exact match
        assert ParameterSimilarity.calculate(params1, params2) == 1.0
        
        # Partial match (recursive comparison)
        similarity = ParameterSimilarity.calculate(params1, params3)
        assert 0.4 < similarity < 0.6
    
    def test_mixed_types(self):
        """Test handling of mixed parameter types."""
        params1 = {
            "path": "test.py",
            "line": 10,
            "recursive": True,
            "tags": ["todo", "bug"]
        }
        params2 = {
            "path": "test.py",
            "line": 10,
            "recursive": True,
            "tags": ["todo", "bug"]
        }
        
        assert ParameterSimilarity.calculate(params1, params2) == 1.0
    
    def test_normalize_strings(self):
        """Test that string normalization works."""
        params1 = {"Path": "TEST.PY"}
        params2 = {"path": "test.py"}
        
        # Without normalization, these would be different
        # With normalization, they should be similar
        similarity = ParameterSimilarity.calculate(params1, params2)
        assert similarity > 0.8
    
    def test_normalize_paths(self):
        """Test that path normalization removes trailing slashes."""
        params1 = {"path": "/home/user/project/"}
        params2 = {"path": "/home/user/project"}
        
        similarity = ParameterSimilarity.calculate(params1, params2)
        assert similarity == 1.0
    
    def test_normalize_lists(self):
        """Test that lists are sorted for comparison."""
        params1 = {"items": ["c", "a", "b"]}
        params2 = {"items": ["a", "b", "c"]}
        
        similarity = ParameterSimilarity.calculate(params1, params2)
        assert similarity == 1.0
    
    def test_set_similarity(self):
        """Test Jaccard similarity for sets."""
        params1 = {"tags": {"todo", "bug", "urgent"}}
        params2 = {"tags": {"todo", "bug", "urgent"}}
        params3 = {"tags": {"todo", "bug"}}
        
        assert ParameterSimilarity.calculate(params1, params2) == 1.0
        
        # 2 common, 1 unique to each = 2/3
        similarity = ParameterSimilarity.calculate(params1, params3)
        assert 0.6 < similarity < 0.7
    
    def test_complex_nested_structure(self):
        """Test similarity for complex nested structures."""
        params1 = {
            "search": {
                "query": "TODO",
                "paths": ["/src", "/lib"],
                "options": {
                    "recursive": True,
                    "case_sensitive": False
                }
            }
        }
        params2 = {
            "search": {
                "query": "TODO",
                "paths": ["/src", "/lib"],
                "options": {
                    "recursive": True,
                    "case_sensitive": False
                }
            }
        }
        
        assert ParameterSimilarity.calculate(params1, params2) == 1.0
    
    def test_partially_similar_complex(self):
        """Test partial similarity for complex structures."""
        params1 = {
            "search": {
                "query": "TODO",
                "paths": ["/src", "/lib"],
                "options": {
                    "recursive": True,
                    "case_sensitive": False
                }
            }
        }
        params2 = {
            "search": {
                "query": "FIXME",  # Different
                "paths": ["/src", "/lib"],
                "options": {
                    "recursive": True,
                    "case_sensitive": False
                }
            }
        }
        
        similarity = ParameterSimilarity.calculate(params1, params2)
        # Should be high but not perfect (only query is different)
        assert 0.7 < similarity < 0.9
    
    def test_edge_case_very_long_lists(self):
        """Test handling of very long lists."""
        params1 = {"items": list(range(100))}
        params2 = {"items": list(range(100))}
        params3 = {"items": list(range(50, 150))}
        
        # Exact match
        assert ParameterSimilarity.calculate(params1, params2) == 1.0
        
        # Partial overlap (50 items in common, 100 total unique)
        similarity = ParameterSimilarity.calculate(params1, params3)
        assert 0.3 < similarity < 0.5
    
    def test_tuple_similarity(self):
        """Test similarity for tuples."""
        params1 = {"coords": (10, 20, 30)}
        params2 = {"coords": (10, 20, 30)}
        params3 = {"coords": (10, 20, 40)}
        
        assert ParameterSimilarity.calculate(params1, params2) == 1.0
        
        # 2 out of 3 match
        similarity = ParameterSimilarity.calculate(params1, params3)
        assert 0.6 < similarity < 0.7
    
    def test_different_key_sets(self):
        """Test parameters with different keys."""
        params1 = {"a": 1, "b": 2, "c": 3}
        params2 = {"a": 1, "b": 2, "d": 4}
        
        # 2 keys match exactly, 2 keys are different
        # Similarity should be around 0.5
        similarity = ParameterSimilarity.calculate(params1, params2)
        assert 0.4 < similarity < 0.6


class TestNormalization:
    """Test parameter normalization."""
    
    def test_normalize_string(self):
        """Test string normalization."""
        result = ParameterSimilarity.normalize_parameters({"key": "VALUE"})
        assert result["key"] == "value"
    
    def test_normalize_path(self):
        """Test path normalization."""
        result = ParameterSimilarity.normalize_parameters({"path": "/home/user/"})
        assert result["path"] == "/home/user"
    
    def test_normalize_list(self):
        """Test list normalization and sorting."""
        result = ParameterSimilarity.normalize_parameters({"items": ["c", "a", "b"]})
        assert result["items"] == ["a", "b", "c"]
    
    def test_normalize_nested(self):
        """Test nested structure normalization."""
        params = {
            "config": {
                "Path": "/HOME/USER/",
                "Items": ["C", "A", "B"]
            }
        }
        result = ParameterSimilarity.normalize_parameters(params)
        
        assert result["config"]["path"] == "/home/user"
        assert result["config"]["items"] == ["a", "b", "c"]
    
    def test_normalize_preserves_types(self):
        """Test that normalization preserves appropriate types."""
        params = {
            "string": "Test",
            "number": 42,
            "boolean": True,
            "none": None,
            "list": [1, 2, 3],
            "dict": {"key": "value"}
        }
        result = ParameterSimilarity.normalize_parameters(params)
        
        assert isinstance(result["string"], str)
        assert isinstance(result["number"], int)
        assert isinstance(result["boolean"], bool)
        assert result["none"] is None
        assert isinstance(result["list"], list)
        assert isinstance(result["dict"], dict)
    
    def test_normalize_handles_unsortable_lists(self):
        """Test that unsortable lists are handled gracefully."""
        params = {"items": [{"a": 1}, {"b": 2}, {"c": 3}]}
        result = ParameterSimilarity.normalize_parameters(params)
        
        # Should not crash, should return list (possibly unsorted)
        assert isinstance(result["items"], list)
        assert len(result["items"]) == 3


class TestCompareValues:
    """Test _compare_values method."""
    
    def test_compare_none(self):
        """Test comparing None values."""
        assert ParameterSimilarity._compare_values(None, None) == 1.0
        assert ParameterSimilarity._compare_values(None, "value") == 0.0
        assert ParameterSimilarity._compare_values("value", None) == 0.0
    
    def test_compare_numbers(self):
        """Test comparing numeric values."""
        assert ParameterSimilarity._compare_values(42, 42) == 1.0
        assert ParameterSimilarity._compare_values(42, 43) == 0.0
        assert ParameterSimilarity._compare_values(3.14, 3.14) == 1.0
    
    def test_compare_booleans(self):
        """Test comparing boolean values."""
        assert ParameterSimilarity._compare_values(True, True) == 1.0
        assert ParameterSimilarity._compare_values(False, False) == 1.0
        assert ParameterSimilarity._compare_values(True, False) == 0.0
    
    def test_compare_strings(self):
        """Test comparing string values."""
        assert ParameterSimilarity._compare_values("test", "test") == 1.0
        assert ParameterSimilarity._compare_values("test", "text") > 0.7
        assert ParameterSimilarity._compare_values("abc", "xyz") < 0.3
    
    def test_compare_different_types(self):
        """Test comparing values of different types."""
        assert ParameterSimilarity._compare_values(42, "42") == 0.0
        assert ParameterSimilarity._compare_values(True, 1) == 0.0
        assert ParameterSimilarity._compare_values([1, 2], (1, 2)) == 0.0


class TestSequenceSimilarity:
    """Test _compare_sequences method."""
    
    def test_empty_sequences(self):
        """Test comparing empty sequences."""
        assert ParameterSimilarity._compare_sequences([], []) == 1.0
        assert ParameterSimilarity._compare_sequences([], [1]) == 0.0
        assert ParameterSimilarity._compare_sequences([1], []) == 0.0
    
    def test_identical_sequences(self):
        """Test comparing identical sequences."""
        assert ParameterSimilarity._compare_sequences([1, 2, 3], [1, 2, 3]) == 1.0
        assert ParameterSimilarity._compare_sequences(["a", "b"], ["a", "b"]) == 1.0
    
    def test_partially_matching_sequences(self):
        """Test comparing partially matching sequences."""
        similarity = ParameterSimilarity._compare_sequences([1, 2, 3], [1, 2, 4])
        assert 0.6 < similarity < 0.7
    
    def test_long_sequences(self):
        """Test comparing long sequences (uses set-based approach)."""
        seq1 = list(range(20))
        seq2 = list(range(20))
        assert ParameterSimilarity._compare_sequences(seq1, seq2) == 1.0
        
        seq3 = list(range(10, 30))
        similarity = ParameterSimilarity._compare_sequences(seq1, seq3)
        # 10 items in common, 30 total unique
        assert 0.3 < similarity < 0.4


class TestSetSimilarity:
    """Test _compare_sets method."""
    
    def test_empty_sets(self):
        """Test comparing empty sets."""
        assert ParameterSimilarity._compare_sets(set(), set()) == 1.0
        assert ParameterSimilarity._compare_sets(set(), {1}) == 0.0
        assert ParameterSimilarity._compare_sets({1}, set()) == 0.0
    
    def test_identical_sets(self):
        """Test comparing identical sets."""
        assert ParameterSimilarity._compare_sets({1, 2, 3}, {1, 2, 3}) == 1.0
    
    def test_partial_overlap(self):
        """Test sets with partial overlap."""
        # {1, 2} ∩ {2, 3} = {2}, {1, 2} ∪ {2, 3} = {1, 2, 3}
        # Jaccard = 1/3
        similarity = ParameterSimilarity._compare_sets({1, 2}, {2, 3})
        assert abs(similarity - 1/3) < 0.01
    
    def test_no_overlap(self):
        """Test sets with no overlap."""
        assert ParameterSimilarity._compare_sets({1, 2}, {3, 4}) == 0.0