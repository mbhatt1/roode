"""Parameter similarity calculation for tool repetition detection."""

from typing import Any, Dict, Set
import difflib
from collections.abc import Mapping, Sequence


class ParameterSimilarity:
    """Calculate similarity between tool parameters."""
    
    @staticmethod
    def calculate(params1: Dict[str, Any], params2: Dict[str, Any]) -> float:
        """
        Calculate similarity score (0-1) between two parameter sets.
        
        Uses different strategies based on parameter types:
        - Exact match for simple types (int, float, bool, None)
        - Levenshtein distance for strings
        - Set similarity for lists
        - Recursive comparison for nested dicts
        
        Args:
            params1: First parameter set
            params2: Second parameter set
            
        Returns:
            Similarity score from 0.0 (completely different) to 1.0 (identical)
        """
        # Normalize parameters before comparison
        norm_params1 = ParameterSimilarity.normalize_parameters(params1)
        norm_params2 = ParameterSimilarity.normalize_parameters(params2)
        
        # If both empty, they're identical
        if not norm_params1 and not norm_params2:
            return 1.0
        
        # If one is empty and other isn't, they're different
        if not norm_params1 or not norm_params2:
            return 0.0
        
        # Get all unique keys
        all_keys = set(norm_params1.keys()) | set(norm_params2.keys())
        
        if not all_keys:
            return 1.0
        
        # Calculate similarity for each key
        total_similarity = 0.0
        for key in all_keys:
            val1 = norm_params1.get(key)
            val2 = norm_params2.get(key)
            
            key_similarity = ParameterSimilarity._compare_values(val1, val2)
            total_similarity += key_similarity
        
        # Return average similarity across all keys
        return total_similarity / len(all_keys)
    
    @staticmethod
    def _compare_values(val1: Any, val2: Any) -> float:
        """Compare two values and return similarity score."""
        # Handle None
        if val1 is None and val2 is None:
            return 1.0
        if val1 is None or val2 is None:
            return 0.0
        
        # Same type checks
        type1, type2 = type(val1), type(val2)
        
        # Exact equality for simple types
        if isinstance(val1, (int, float, bool)):
            if isinstance(val2, (int, float, bool)):
                return 1.0 if val1 == val2 else 0.0
            return 0.0
        
        # String similarity using difflib
        if isinstance(val1, str) and isinstance(val2, str):
            return difflib.SequenceMatcher(None, val1, val2).ratio()
        
        # List/tuple similarity
        if isinstance(val1, (list, tuple)) and isinstance(val2, (list, tuple)):
            return ParameterSimilarity._compare_sequences(val1, val2)
        
        # Dict similarity (recursive)
        if isinstance(val1, dict) and isinstance(val2, dict):
            return ParameterSimilarity.calculate(val1, val2)
        
        # Set similarity
        if isinstance(val1, set) and isinstance(val2, set):
            return ParameterSimilarity._compare_sets(val1, val2)
        
        # Different types or unsupported types
        if type1 != type2:
            return 0.0
        
        # Fallback to equality
        return 1.0 if val1 == val2 else 0.0
    
    @staticmethod
    def _compare_sequences(seq1: Sequence, seq2: Sequence) -> float:
        """Compare two sequences (lists or tuples)."""
        if len(seq1) == 0 and len(seq2) == 0:
            return 1.0
        if len(seq1) == 0 or len(seq2) == 0:
            return 0.0
        
        # Try to match elements
        # For short sequences, use exact matching
        if len(seq1) <= 10 and len(seq2) <= 10:
            matches = 0
            max_len = max(len(seq1), len(seq2))
            
            for i in range(min(len(seq1), len(seq2))):
                if ParameterSimilarity._compare_values(seq1[i], seq2[i]) > 0.9:
                    matches += 1
            
            return matches / max_len
        
        # For longer sequences, use set-based similarity
        set1 = set(str(x) for x in seq1)
        set2 = set(str(x) for x in seq2)
        return ParameterSimilarity._compare_sets(set1, set2)
    
    @staticmethod
    def _compare_sets(set1: Set, set2: Set) -> float:
        """Compare two sets using Jaccard similarity."""
        if len(set1) == 0 and len(set2) == 0:
            return 1.0
        if len(set1) == 0 or len(set2) == 0:
            return 0.0
        
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        
        return intersection / union if union > 0 else 0.0
    
    @staticmethod
    def normalize_parameters(params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize parameters for comparison.
        
        Normalization includes:
        - Lowercase strings
        - Sort lists
        - Normalize paths (remove trailing slashes)
        - Recursively normalize nested dicts
        
        Args:
            params: Parameters to normalize
            
        Returns:
            Normalized parameters
        """
        if not isinstance(params, dict):
            return params
        
        normalized = {}
        for key, value in params.items():
            normalized[key] = ParameterSimilarity._normalize_value(value)
        
        return normalized
    
    @staticmethod
    def _normalize_value(value: Any) -> Any:
        """Normalize a single value."""
        if value is None:
            return None
        
        # Normalize strings
        if isinstance(value, str):
            # Lowercase and strip
            normalized = value.lower().strip()
            # Remove trailing slashes from paths
            if '/' in normalized or '\\' in normalized:
                normalized = normalized.rstrip('/\\')
            return normalized
        
        # Normalize lists (sort if all elements are comparable)
        if isinstance(value, list):
            try:
                # Try to sort if possible
                return sorted([ParameterSimilarity._normalize_value(v) for v in value])
            except TypeError:
                # If not sortable, just normalize values
                return [ParameterSimilarity._normalize_value(v) for v in value]
        
        # Normalize tuples
        if isinstance(value, tuple):
            return tuple(ParameterSimilarity._normalize_value(v) for v in value)
        
        # Normalize dicts (recursive)
        if isinstance(value, dict):
            return ParameterSimilarity.normalize_parameters(value)
        
        # Normalize sets
        if isinstance(value, set):
            try:
                return frozenset(ParameterSimilarity._normalize_value(v) for v in value)
            except TypeError:
                return value
        
        # Return other types as-is
        return value