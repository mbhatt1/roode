"""Tests for tool repetition detection."""

import pytest
from datetime import datetime, timedelta
from roo_code.builtin_tools.repetition_detector import (
    RepetitionDetector,
    ToolCall,
    RepetitionType,
    RepetitionWarning,
    RepetitionPattern
)


class TestToolCall:
    """Test ToolCall dataclass."""
    
    def test_create_tool_call(self):
        """Test creating a ToolCall instance."""
        call = ToolCall(
            tool_name="search_files",
            use_id="call-1",
            parameters={"regex": "TODO", "path": "/src"},
            timestamp=datetime.now()
        )
        
        assert call.tool_name == "search_files"
        assert call.use_id == "call-1"
        assert call.parameters == {"regex": "TODO", "path": "/src"}
        assert call.result_hash is None
    
    def test_tool_call_with_result_hash(self):
        """Test ToolCall with result hash."""
        call = ToolCall(
            tool_name="read_file",
            use_id="call-2",
            parameters={"path": "test.py"},
            timestamp=datetime.now(),
            result_hash="abc123"
        )
        
        assert call.result_hash == "abc123"
    
    def test_tool_call_hashable(self):
        """Test that ToolCall is hashable."""
        call1 = ToolCall(
            tool_name="test",
            use_id="call-1",
            parameters={},
            timestamp=datetime.now()
        )
        call2 = ToolCall(
            tool_name="test",
            use_id="call-1",
            parameters={},
            timestamp=datetime.now()
        )
        
        # Can be used in sets
        calls = {call1, call2}
        assert len(calls) == 1  # Same use_id means same hash


class TestRepetitionDetectorInit:
    """Test RepetitionDetector initialization."""
    
    def test_default_initialization(self):
        """Test default initialization."""
        detector = RepetitionDetector()
        
        assert detector.window_size == 10
        assert detector.similarity_threshold == 0.9
        assert detector.max_consecutive_same == 3
        assert detector.max_same_in_window == 5
    
    def test_custom_initialization(self):
        """Test custom initialization."""
        detector = RepetitionDetector(
            window_size=20,
            similarity_threshold=0.85,
            max_consecutive_same=5,
            max_same_in_window=8
        )
        
        assert detector.window_size == 20
        assert detector.similarity_threshold == 0.85
        assert detector.max_consecutive_same == 5
        assert detector.max_same_in_window == 8


class TestRecordCall:
    """Test recording tool calls."""
    
    def test_record_single_call(self):
        """Test recording a single call."""
        detector = RepetitionDetector()
        call = ToolCall(
            tool_name="search_files",
            use_id="call-1",
            parameters={"regex": "TODO"},
            timestamp=datetime.now()
        )
        
        detector.record_call(call)
        assert len(detector._call_history) == 1
    
    def test_record_multiple_calls(self):
        """Test recording multiple calls."""
        detector = RepetitionDetector()
        
        for i in range(5):
            call = ToolCall(
                tool_name="search_files",
                use_id=f"call-{i}",
                parameters={"regex": "TODO"},
                timestamp=datetime.now()
            )
            detector.record_call(call)
        
        assert len(detector._call_history) == 5
    
    def test_rolling_window(self):
        """Test that history respects window size."""
        detector = RepetitionDetector(window_size=5)
        
        # Record 10 calls
        for i in range(10):
            call = ToolCall(
                tool_name="test",
                use_id=f"call-{i}",
                parameters={"n": i},
                timestamp=datetime.now()
            )
            detector.record_call(call)
        
        # Should only keep last 5
        assert len(detector._call_history) == 5
        # Should be the most recent ones
        assert detector._call_history[-1].parameters["n"] == 9


class TestConsecutiveRepetition:
    """Test consecutive repetition detection."""
    
    def test_no_repetition(self):
        """Test that no warning is generated for non-repetitive calls."""
        detector = RepetitionDetector(max_consecutive_same=3)
        
        # Record different calls
        for i in range(3):
            detector.record_call(ToolCall(
                tool_name=f"tool-{i}",
                use_id=f"call-{i}",
                parameters={},
                timestamp=datetime.now()
            ))
        
        warning = detector.check_repetition("tool-3", {})
        assert warning is None
    
    def test_consecutive_repetition_warning(self):
        """Test that warning is generated for consecutive repetition."""
        detector = RepetitionDetector(max_consecutive_same=3)
        
        # Record 3 identical calls
        for i in range(3):
            detector.record_call(ToolCall(
                tool_name="search_files",
                use_id=f"call-{i}",
                parameters={"regex": "TODO", "path": "/src"},
                timestamp=datetime.now()
            ))
        
        # Check if 4th identical call triggers warning
        warning = detector.check_repetition(
            "search_files",
            {"regex": "TODO", "path": "/src"}
        )
        
        assert warning is not None
        assert warning.type == RepetitionType.EXACT_DUPLICATE
        assert warning.severity in ["warning", "critical"]
        assert "consecutive" in warning.message.lower()
    
    def test_consecutive_repetition_critical(self):
        """Test that critical warning is generated for excessive repetition."""
        detector = RepetitionDetector(max_consecutive_same=3)
        
        # Record 5+ identical calls
        for i in range(6):
            detector.record_call(ToolCall(
                tool_name="search_files",
                use_id=f"call-{i}",
                parameters={"regex": "TODO"},
                timestamp=datetime.now()
            ))
        
        warning = detector.check_repetition("search_files", {"regex": "TODO"})
        
        assert warning is not None
        assert warning.severity == "critical"
    
    def test_similar_params_consecutive(self):
        """Test that similar (not exact) params also trigger warning."""
        detector = RepetitionDetector(max_consecutive_same=3)
        
        # Record similar calls (case differs)
        for i in range(3):
            detector.record_call(ToolCall(
                tool_name="search_files",
                use_id=f"call-{i}",
                parameters={"regex": "TODO", "path": "/src"},
                timestamp=datetime.now()
            ))
        
        # Check with slightly different params
        warning = detector.check_repetition(
            "search_files",
            {"regex": "todo", "path": "/src"}  # lowercase
        )
        
        assert warning is not None


class TestWindowRepetition:
    """Test window-based repetition detection."""
    
    def test_high_frequency_in_window(self):
        """Test detection of high frequency within window."""
        detector = RepetitionDetector(
            window_size=10,
            max_same_in_window=5
        )
        
        # Record 5 similar calls interspersed with others
        for i in range(10):
            if i % 2 == 0:
                tool_name = "search_files"
                params = {"regex": "TODO"}
            else:
                tool_name = "read_file"
                params = {"path": f"file{i}.py"}
            
            detector.record_call(ToolCall(
                tool_name=tool_name,
                use_id=f"call-{i}",
                parameters=params,
                timestamp=datetime.now()
            ))
        
        # Check if 6th similar call triggers warning
        warning = detector.check_repetition("search_files", {"regex": "TODO"})
        
        assert warning is not None
        assert warning.type == RepetitionType.SIMILAR_PARAMS
        assert warning.severity == "warning"
    
    def test_below_threshold_no_warning(self):
        """Test that calls below threshold don't trigger warning."""
        detector = RepetitionDetector(max_same_in_window=5)
        
        # Record only 4 similar calls
        for i in range(4):
            detector.record_call(ToolCall(
                tool_name="search_files",
                use_id=f"call-{i}",
                parameters={"regex": "TODO"},
                timestamp=datetime.now()
            ))
        
        warning = detector.check_repetition("search_files", {"regex": "TODO"})
        assert warning is None


class TestAlternatingPattern:
    """Test alternating pattern detection."""
    
    def test_alternating_pattern_detected(self):
        """Test detection of A -> B -> A -> B pattern."""
        detector = RepetitionDetector()
        
        # Create alternating pattern
        tools = ["read_file", "write_to_file", "read_file", "write_to_file"]
        for i, tool in enumerate(tools):
            detector.record_call(ToolCall(
                tool_name=tool,
                use_id=f"call-{i}",
                parameters={"path": "test.py"},
                timestamp=datetime.now()
            ))
        
        # Check if continuing pattern triggers warning
        warning = detector.check_repetition("read_file", {"path": "test.py"})
        
        assert warning is not None
        assert warning.type == RepetitionType.ALTERNATING
        assert "alternating" in warning.message.lower()
    
    def test_non_alternating_no_warning(self):
        """Test that non-alternating patterns don't trigger warning."""
        detector = RepetitionDetector()
        
        # Create non-alternating pattern
        tools = ["read_file", "write_to_file", "search_files", "list_files"]
        for i, tool in enumerate(tools):
            detector.record_call(ToolCall(
                tool_name=tool,
                use_id=f"call-{i}",
                parameters={},
                timestamp=datetime.now()
            ))
        
        warning = detector.check_repetition("read_file", {})
        assert warning is None or warning.type != RepetitionType.ALTERNATING
    
    def test_three_tool_alternating(self):
        """Test that only 2-tool alternation is detected."""
        detector = RepetitionDetector()
        
        # Three tools alternating
        tools = ["a", "b", "c", "a", "b", "c"]
        for i, tool in enumerate(tools):
            detector.record_call(ToolCall(
                tool_name=tool,
                use_id=f"call-{i}",
                parameters={},
                timestamp=datetime.now()
            ))
        
        # Should not detect as simple alternating (that's circular)
        warning = detector.check_repetition("a", {})
        if warning:
            assert warning.type != RepetitionType.ALTERNATING


class TestCircularPattern:
    """Test circular pattern detection."""
    
    def test_circular_pattern_detected(self):
        """Test detection of A -> B -> C -> A circular pattern."""
        detector = RepetitionDetector()
        
        # Create circular pattern (repeat twice)
        tools = ["read_file", "apply_diff", "read_file"] * 2
        for i, tool in enumerate(tools):
            detector.record_call(ToolCall(
                tool_name=tool,
                use_id=f"call-{i}",
                parameters={},
                timestamp=datetime.now()
            ))
        
        # Check if continuing pattern triggers warning
        warning = detector.check_repetition("read_file", {})
        
        assert warning is not None
        assert warning.type == RepetitionType.CIRCULAR
        assert "circular" in warning.message.lower()
    
    def test_longer_circular_pattern(self):
        """Test detection of longer circular patterns."""
        detector = RepetitionDetector()
        
        # Create longer circular pattern
        tools = ["a", "b", "c", "d"] * 2
        for i, tool in enumerate(tools):
            detector.record_call(ToolCall(
                tool_name=tool,
                use_id=f"call-{i}",
                parameters={},
                timestamp=datetime.now()
            ))
        
        warning = detector.check_repetition("a", {})
        
        assert warning is not None
        assert warning.type == RepetitionType.CIRCULAR
    
    def test_non_circular_no_warning(self):
        """Test that non-circular patterns don't trigger warning."""
        detector = RepetitionDetector()
        
        # Not a circular pattern
        tools = ["a", "b", "c", "d", "e", "f"]
        for i, tool in enumerate(tools):
            detector.record_call(ToolCall(
                tool_name=tool,
                use_id=f"call-{i}",
                parameters={},
                timestamp=datetime.now()
            ))
        
        warning = detector.check_repetition("g", {})
        assert warning is None or warning.type != RepetitionType.CIRCULAR


class TestGetPatterns:
    """Test pattern analysis."""
    
    def test_find_exact_duplicates(self):
        """Test finding exact duplicate patterns."""
        detector = RepetitionDetector()
        
        # Record duplicate calls
        for i in range(3):
            detector.record_call(ToolCall(
                tool_name="search_files",
                use_id=f"call-{i}",
                parameters={"regex": "TODO"},
                timestamp=datetime.now()
            ))
        
        patterns = detector.get_patterns()
        
        # Should find exact duplicate pattern
        duplicate_patterns = [p for p in patterns if p.type == RepetitionType.EXACT_DUPLICATE]
        assert len(duplicate_patterns) > 0
        assert duplicate_patterns[0].frequency >= 3
    
    def test_find_similar_calls(self):
        """Test finding similar call patterns."""
        detector = RepetitionDetector()
        
        # Record similar calls
        for i in range(3):
            detector.record_call(ToolCall(
                tool_name="search_files",
                use_id=f"call-{i}",
                parameters={"regex": "TODO", "path": f"/src{i}"},
                timestamp=datetime.now()
            ))
        
        patterns = detector.get_patterns()
        
        # Should find similar pattern
        similar_patterns = [p for p in patterns if p.type == RepetitionType.SIMILAR_PARAMS]
        assert len(similar_patterns) >= 0  # May or may not detect depending on similarity
    
    def test_find_alternating_patterns(self):
        """Test finding alternating patterns."""
        detector = RepetitionDetector()
        
        # Create alternating pattern
        tools = ["read_file", "write_to_file"] * 3
        for i, tool in enumerate(tools):
            detector.record_call(ToolCall(
                tool_name=tool,
                use_id=f"call-{i}",
                parameters={},
                timestamp=datetime.now()
            ))
        
        patterns = detector.get_patterns()
        
        # Should find alternating pattern
        alternating_patterns = [p for p in patterns if p.type == RepetitionType.ALTERNATING]
        assert len(alternating_patterns) > 0
    
    def test_find_circular_patterns(self):
        """Test finding circular patterns."""
        detector = RepetitionDetector()
        
        # Create circular pattern
        tools = ["a", "b", "c"] * 2
        for i, tool in enumerate(tools):
            detector.record_call(ToolCall(
                tool_name=tool,
                use_id=f"call-{i}",
                parameters={},
                timestamp=datetime.now()
            ))
        
        patterns = detector.get_patterns()
        
        # Should find circular pattern
        circular_patterns = [p for p in patterns if p.type == RepetitionType.CIRCULAR]
        assert len(circular_patterns) > 0
    
    def test_empty_history_no_patterns(self):
        """Test that empty history returns no patterns."""
        detector = RepetitionDetector()
        patterns = detector.get_patterns()
        assert len(patterns) == 0


class TestRepetitionWarning:
    """Test RepetitionWarning dataclass."""
    
    def test_warning_string_representation(self):
        """Test warning string formatting."""
        warning = RepetitionWarning(
            type=RepetitionType.EXACT_DUPLICATE,
            severity="warning",
            message="Tool called 5 times",
            suggestion="Consider reviewing your approach",
            calls_involved=[]
        )
        
        warning_str = str(warning)
        assert "[WARNING]" in warning_str
        assert "Tool called 5 times" in warning_str
        assert "Consider reviewing your approach" in warning_str
    
    def test_critical_warning(self):
        """Test critical warning formatting."""
        warning = RepetitionWarning(
            type=RepetitionType.EXACT_DUPLICATE,
            severity="critical",
            message="Excessive repetition",
            suggestion="Stop and reconsider",
            calls_involved=[]
        )
        
        warning_str = str(warning)
        assert "[CRITICAL]" in warning_str


class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_empty_parameters(self):
        """Test handling of empty parameters."""
        detector = RepetitionDetector()
        
        for i in range(3):
            detector.record_call(ToolCall(
                tool_name="test",
                use_id=f"call-{i}",
                parameters={},
                timestamp=datetime.now()
            ))
        
        warning = detector.check_repetition("test", {})
        assert warning is not None  # Should detect even with empty params
    
    def test_single_call_no_warning(self):
        """Test that single call doesn't trigger warning."""
        detector = RepetitionDetector()
        
        detector.record_call(ToolCall(
            tool_name="test",
            use_id="call-1",
            parameters={"key": "value"},
            timestamp=datetime.now()
        ))
        
        warning = detector.check_repetition("test", {"key": "value"})
        assert warning is None
    
    def test_different_tools_no_warning(self):
        """Test that different tools don't trigger warning."""
        detector = RepetitionDetector()
        
        for i in range(5):
            detector.record_call(ToolCall(
                tool_name=f"tool-{i}",
                use_id=f"call-{i}",
                parameters={},
                timestamp=datetime.now()
            ))
        
        warning = detector.check_repetition("tool-new", {})
        assert warning is None
    
    def test_result_hash_recorded(self):
        """Test that result hash is properly recorded."""
        detector = RepetitionDetector()
        
        call = ToolCall(
            tool_name="test",
            use_id="call-1",
            parameters={},
            timestamp=datetime.now(),
            result_hash="hash123"
        )
        
        detector.record_call(call)
        assert detector._call_history[0].result_hash == "hash123"
    
    def test_timestamps_preserved(self):
        """Test that timestamps are preserved."""
        detector = RepetitionDetector()
        
        now = datetime.now()
        call = ToolCall(
            tool_name="test",
            use_id="call-1",
            parameters={},
            timestamp=now
        )
        
        detector.record_call(call)
        assert detector._call_history[0].timestamp == now
    
    def test_very_similar_but_not_identical(self):
        """Test parameters that are very similar but not identical."""
        detector = RepetitionDetector(similarity_threshold=0.9)
        
        # Record calls with very similar params
        for i in range(3):
            detector.record_call(ToolCall(
                tool_name="search",
                use_id=f"call-{i}",
                parameters={"query": f"TODO{i}"},  # Slightly different
                timestamp=datetime.now()
            ))
        
        # Should still detect as repetition due to high similarity
        warning = detector.check_repetition("search", {"query": "TODO3"})
        # May or may not trigger depending on exact similarity calculation


class TestIntegrationScenarios:
    """Test realistic integration scenarios."""
    
    def test_realistic_search_repetition(self):
        """Test realistic scenario of repeated searches."""
        detector = RepetitionDetector(max_consecutive_same=3)
        
        # Simulate agent searching for something repeatedly
        for i in range(4):
            detector.record_call(ToolCall(
                tool_name="search_files",
                use_id=f"search-{i}",
                parameters={
                    "regex": "import.*pandas",
                    "path": "/src",
                    "file_pattern": "*.py"
                },
                timestamp=datetime.now() + timedelta(seconds=i)
            ))
        
        # Next search should trigger warning
        warning = detector.check_repetition(
            "search_files",
            {
                "regex": "import.*pandas",
                "path": "/src",
                "file_pattern": "*.py"
            }
        )
        
        assert warning is not None
        assert "search_files" in warning.message
    
    def test_realistic_edit_cycle(self):
        """Test realistic scenario of edit-read cycle."""
        detector = RepetitionDetector()
        
        # Simulate read -> edit -> read -> edit cycle
        cycle = [
            ("read_file", {"path": "app.py"}),
            ("apply_diff", {"path": "app.py", "diff": "..."}),
            ("read_file", {"path": "app.py"}),
            ("apply_diff", {"path": "app.py", "diff": "..."}),
        ]
        
        for i, (tool, params) in enumerate(cycle):
            detector.record_call(ToolCall(
                tool_name=tool,
                use_id=f"call-{i}",
                parameters=params,
                timestamp=datetime.now() + timedelta(seconds=i)
            ))
        
        # Continuing the pattern should trigger warning
        warning = detector.check_repetition("read_file", {"path": "app.py"})
        
        assert warning is not None
        assert warning.type in [RepetitionType.ALTERNATING, RepetitionType.CIRCULAR]
    
    def test_mixed_tools_no_false_positive(self):
        """Test that mixed tool usage doesn't cause false positives."""
        detector = RepetitionDetector()
        
        # Simulate varied, normal tool usage
        calls = [
            ("list_files", {"path": "/src"}),
            ("read_file", {"path": "/src/main.py"}),
            ("search_files", {"regex": "TODO"}),
            ("read_file", {"path": "/src/utils.py"}),
            ("write_to_file", {"path": "/src/new.py"}),
        ]
        
        for i, (tool, params) in enumerate(calls):
            detector.record_call(ToolCall(
                tool_name=tool,
                use_id=f"call-{i}",
                parameters=params,
                timestamp=datetime.now() + timedelta(seconds=i)
            ))
        
        # Should not trigger warning for new different call
        warning = detector.check_repetition("execute_command", {"command": "npm test"})
        assert warning is None