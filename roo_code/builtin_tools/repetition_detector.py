"""Tool repetition detection to identify problematic patterns."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from collections import deque

from .parameter_similarity import ParameterSimilarity


class RepetitionType(Enum):
    """Types of repetition patterns."""
    EXACT_DUPLICATE = "exact_duplicate"  # Same tool, same params
    SIMILAR_PARAMS = "similar_params"    # Same tool, very similar params
    ALTERNATING = "alternating"          # A -> B -> A -> B pattern
    CIRCULAR = "circular"                # A -> B -> C -> A pattern
    ESCALATING = "escalating"            # Same tool with incrementing params


@dataclass
class ToolCall:
    """Record of a tool call."""
    tool_name: str
    use_id: str
    parameters: Dict[str, Any]
    timestamp: datetime
    result_hash: Optional[str] = None
    
    def __hash__(self) -> int:
        """Make ToolCall hashable for use in sets."""
        # Use tool_name and use_id for hash
        return hash((self.tool_name, self.use_id))


@dataclass
class RepetitionPattern:
    """Detected repetition pattern."""
    type: RepetitionType
    tool_names: List[str]
    frequency: int
    first_seen: datetime
    last_seen: datetime
    example_calls: List[ToolCall]
    severity: str  # "info", "warning", "critical"
    
    def __str__(self) -> str:
        """String representation of pattern."""
        tools = " -> ".join(self.tool_names[:3])
        if len(self.tool_names) > 3:
            tools += "..."
        return f"{self.type.value}: {tools} (frequency: {frequency})"


@dataclass
class RepetitionWarning:
    """Warning about detected repetition."""
    type: RepetitionType
    severity: str  # "info", "warning", "critical"
    message: str
    suggestion: str
    calls_involved: List[ToolCall]
    
    def __str__(self) -> str:
        """Format warning for display."""
        return f"[{self.severity.upper()}] {self.message}\nSuggestion: {self.suggestion}"


class RepetitionDetector:
    """Detects repeated tool calls that may indicate problems."""
    
    def __init__(
        self,
        window_size: int = 10,
        similarity_threshold: float = 0.9,
        max_consecutive_same: int = 3,
        max_same_in_window: int = 5
    ):
        """
        Initialize repetition detector.
        
        Args:
            window_size: Number of recent calls to analyze
            similarity_threshold: Threshold for parameter similarity (0-1)
            max_consecutive_same: Max identical consecutive calls allowed
            max_same_in_window: Max similar calls in window allowed
        """
        self.window_size = window_size
        self.similarity_threshold = similarity_threshold
        self.max_consecutive_same = max_consecutive_same
        self.max_same_in_window = max_same_in_window
        
        # Use deque for efficient rolling window
        self._call_history: deque[ToolCall] = deque(maxlen=window_size)
        
        # Cache for parameter hashes
        self._param_hash_cache: Dict[str, int] = {}
    
    def record_call(self, call: ToolCall) -> None:
        """
        Record a tool call for analysis.
        
        Args:
            call: The tool call to record
        """
        self._call_history.append(call)
        
        # Cache parameter hash for quick comparison
        param_key = f"{call.tool_name}:{call.use_id}"
        self._param_hash_cache[param_key] = hash(str(sorted(call.parameters.items())))
    
    def check_repetition(
        self, 
        tool_name: str, 
        parameters: Dict[str, Any]
    ) -> Optional[RepetitionWarning]:
        """
        Check if new call would be problematic repetition.
        
        Args:
            tool_name: Name of the tool being called
            parameters: Parameters for the tool call
            
        Returns:
            RepetitionWarning if problematic pattern detected, None otherwise
        """
        if not self._call_history:
            return None
        
        # Convert to list for easier analysis
        history = list(self._call_history)
        
        # Check different types of repetition
        warning = self._detect_consecutive_repetition(
            history, tool_name, parameters
        )
        if warning:
            return warning
        
        warning = self._detect_window_repetition(
            history, tool_name, parameters
        )
        if warning:
            return warning
        
        warning = self._detect_alternating_pattern(
            history, tool_name, parameters
        )
        if warning:
            return warning
        
        warning = self._detect_circular_pattern(
            history, tool_name, parameters
        )
        if warning:
            return warning
        
        return None
    
    def get_patterns(self) -> List[RepetitionPattern]:
        """
        Analyze call history for patterns.
        
        Returns:
            List of detected patterns
        """
        patterns = []
        history = list(self._call_history)
        
        if not history:
            return patterns
        
        # Find exact duplicates
        patterns.extend(self._find_exact_duplicates(history))
        
        # Find similar parameter calls
        patterns.extend(self._find_similar_calls(history))
        
        # Find alternating patterns
        patterns.extend(self._find_alternating_patterns(history))
        
        # Find circular patterns
        patterns.extend(self._find_circular_patterns(history))
        
        return patterns
    
    def _detect_consecutive_repetition(
        self,
        history: List[ToolCall],
        tool_name: str,
        parameters: Dict[str, Any]
    ) -> Optional[RepetitionWarning]:
        """Detect same tool called multiple times in a row."""
        if not history:
            return None
        
        # Count consecutive calls to the same tool with similar params
        consecutive_count = 0
        for call in reversed(history):
            if call.tool_name != tool_name:
                break
            
            similarity = ParameterSimilarity.calculate(call.parameters, parameters)
            if similarity >= self.similarity_threshold:
                consecutive_count += 1
            else:
                break
        
        # Check if we would exceed the limit
        if consecutive_count >= self.max_consecutive_same:
            severity = "critical" if consecutive_count >= self.max_consecutive_same + 2 else "warning"
            
            return RepetitionWarning(
                type=RepetitionType.EXACT_DUPLICATE,
                severity=severity,
                message=f"Tool '{tool_name}' called {consecutive_count + 1} times consecutively with similar parameters",
                suggestion=f"Consider reviewing your approach. Repeated calls suggest the tool may not be achieving the desired result. Try analyzing the tool's output or adjusting parameters significantly.",
                calls_involved=history[-consecutive_count:] if consecutive_count > 0 else []
            )
        
        return None
    
    def _detect_window_repetition(
        self,
        history: List[ToolCall],
        tool_name: str,
        parameters: Dict[str, Any]
    ) -> Optional[RepetitionWarning]:
        """Detect high frequency of similar calls within window."""
        # Count similar calls to the same tool in the window
        similar_count = 0
        similar_calls = []
        
        for call in history:
            if call.tool_name == tool_name:
                similarity = ParameterSimilarity.calculate(call.parameters, parameters)
                if similarity >= self.similarity_threshold:
                    similar_count += 1
                    similar_calls.append(call)
        
        # Check if we would exceed the limit
        if similar_count >= self.max_same_in_window:
            return RepetitionWarning(
                type=RepetitionType.SIMILAR_PARAMS,
                severity="warning",
                message=f"Tool '{tool_name}' called {similar_count + 1} times in last {len(history)} calls with similar parameters",
                suggestion=f"High frequency of similar calls detected. Consider refining your search pattern, parameters, or strategy to avoid redundant operations.",
                calls_involved=similar_calls
            )
        
        return None
    
    def _detect_alternating_pattern(
        self,
        history: List[ToolCall],
        tool_name: str,
        parameters: Dict[str, Any]
    ) -> Optional[RepetitionWarning]:
        """Detect A -> B -> A -> B pattern."""
        if len(history) < 3:
            return None
        
        # Look at last 4 calls
        recent = history[-4:] if len(history) >= 4 else history[-3:]
        
        # Check for alternating pattern
        if len(recent) >= 3:
            # Get the tools involved
            tools = [call.tool_name for call in recent]
            
            # Check if alternating (e.g., A, B, A or A, B, A, B)
            if len(set(tools)) == 2:
                # Check if they alternate
                alternates = all(
                    tools[i] != tools[i + 1] 
                    for i in range(len(tools) - 1)
                )
                
                if alternates and tools[0] == tool_name:
                    return RepetitionWarning(
                        type=RepetitionType.ALTERNATING,
                        severity="warning",
                        message=f"Alternating pattern detected: {' -> '.join(tools)} -> {tool_name}",
                        suggestion=f"You're alternating between '{tools[0]}' and '{tools[1]}'. Consider planning your changes before applying them, or verify the tool is working as expected.",
                        calls_involved=recent
                    )
        
        return None
    
    def _detect_circular_pattern(
        self,
        history: List[ToolCall],
        tool_name: str,
        parameters: Dict[str, Any]
    ) -> Optional[RepetitionWarning]:
        """Detect A -> B -> C -> A circular pattern."""
        if len(history) < 3:
            return None
        
        # Look for cycles in recent history
        recent = history[-6:] if len(history) >= 6 else history
        tools = [call.tool_name for call in recent] + [tool_name]
        
        # Try to find a repeating cycle
        for cycle_len in range(2, min(4, len(tools) // 2 + 1)):
            # Check if last cycle_len tools repeat
            if len(tools) >= cycle_len * 2:
                cycle = tools[-cycle_len:]
                prev_cycle = tools[-(cycle_len * 2):-cycle_len]
                
                if cycle == prev_cycle:
                    return RepetitionWarning(
                        type=RepetitionType.CIRCULAR,
                        severity="warning",
                        message=f"Circular pattern detected: {' -> '.join(cycle)} (repeating)",
                        suggestion=f"You're in a cycle of {cycle_len} tools. This may indicate unsuccessful edits or miscommunication. Review the results of each tool call.",
                        calls_involved=recent[-(cycle_len * 2):]
                    )
        
        return None
    
    def _find_exact_duplicates(self, history: List[ToolCall]) -> List[RepetitionPattern]:
        """Find exact duplicate calls in history."""
        patterns = []
        tool_param_map: Dict[str, List[ToolCall]] = {}
        
        for call in history:
            key = f"{call.tool_name}:{hash(str(sorted(call.parameters.items())))}"
            if key not in tool_param_map:
                tool_param_map[key] = []
            tool_param_map[key].append(call)
        
        # Find groups with multiple calls
        for key, calls in tool_param_map.items():
            if len(calls) >= 2:
                patterns.append(RepetitionPattern(
                    type=RepetitionType.EXACT_DUPLICATE,
                    tool_names=[calls[0].tool_name],
                    frequency=len(calls),
                    first_seen=min(c.timestamp for c in calls),
                    last_seen=max(c.timestamp for c in calls),
                    example_calls=calls[:3],
                    severity="warning" if len(calls) >= 3 else "info"
                ))
        
        return patterns
    
    def _find_similar_calls(self, history: List[ToolCall]) -> List[RepetitionPattern]:
        """Find calls with similar parameters."""
        patterns = []
        tool_groups: Dict[str, List[ToolCall]] = {}
        
        # Group by tool name
        for call in history:
            if call.tool_name not in tool_groups:
                tool_groups[call.tool_name] = []
            tool_groups[call.tool_name].append(call)
        
        # Find similar calls within each tool group
        for tool_name, calls in tool_groups.items():
            if len(calls) < 2:
                continue
            
            # Find clusters of similar calls
            clusters: List[List[ToolCall]] = []
            for call in calls:
                added = False
                for cluster in clusters:
                    # Check if call is similar to cluster
                    similarity = ParameterSimilarity.calculate(
                        call.parameters,
                        cluster[0].parameters
                    )
                    if similarity >= self.similarity_threshold:
                        cluster.append(call)
                        added = True
                        break
                
                if not added:
                    clusters.append([call])
            
            # Report clusters with multiple similar calls
            for cluster in clusters:
                if len(cluster) >= 2:
                    patterns.append(RepetitionPattern(
                        type=RepetitionType.SIMILAR_PARAMS,
                        tool_names=[tool_name],
                        frequency=len(cluster),
                        first_seen=min(c.timestamp for c in cluster),
                        last_seen=max(c.timestamp for c in cluster),
                        example_calls=cluster[:3],
                        severity="info"
                    ))
        
        return patterns
    
    def _find_alternating_patterns(self, history: List[ToolCall]) -> List[RepetitionPattern]:
        """Find alternating patterns in history."""
        patterns = []
        
        if len(history) < 4:
            return patterns
        
        # Slide window through history
        for i in range(len(history) - 3):
            window = history[i:i+4]
            tools = [c.tool_name for c in window]
            
            # Check for alternating
            if len(set(tools)) == 2:
                alternates = all(tools[j] != tools[j+1] for j in range(3))
                if alternates:
                    patterns.append(RepetitionPattern(
                        type=RepetitionType.ALTERNATING,
                        tool_names=[tools[0], tools[1]],
                        frequency=4,
                        first_seen=window[0].timestamp,
                        last_seen=window[-1].timestamp,
                        example_calls=window,
                        severity="info"
                    ))
        
        return patterns
    
    def _find_circular_patterns(self, history: List[ToolCall]) -> List[RepetitionPattern]:
        """Find circular patterns in history."""
        patterns = []
        
        if len(history) < 6:
            return patterns
        
        tools = [c.tool_name for c in history]
        
        # Look for repeating cycles
        for cycle_len in range(2, min(5, len(tools) // 2 + 1)):
            for i in range(len(tools) - cycle_len * 2 + 1):
                cycle1 = tools[i:i+cycle_len]
                cycle2 = tools[i+cycle_len:i+cycle_len*2]
                
                if cycle1 == cycle2:
                    patterns.append(RepetitionPattern(
                        type=RepetitionType.CIRCULAR,
                        tool_names=cycle1,
                        frequency=2,
                        first_seen=history[i].timestamp,
                        last_seen=history[i+cycle_len*2-1].timestamp,
                        example_calls=history[i:i+cycle_len*2],
                        severity="warning"
                    ))
        
        return patterns