"""
Test suite for State Machine
Demonstrates how comprehensive testing should be implemented for the entire codebase.
"""

import pytest
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from kernel.state_machine import (
    JobState, StepState, StateMachine, StepStateMachine, 
    VALID_TRANSITIONS, STEP_VALID_TRANSITIONS
)


class TestJobState:
    """Test JobState enum and transitions."""
    
    def test_all_states_defined(self):
        """Verify all expected states exist."""
        expected_states = {
            "CREATED", "QUEUED", "PLANNING", "CONTEXT_BUILDING",
            "EXECUTING", "VERIFYING", "REVIEWING", "COMPLETED",
            "FAILED", "RETRYING", "CANCELLED", "PAUSED"
        }
        actual_states = {state.name for state in JobState}
        assert actual_states == expected_states
    
    def test_all_states_have_transitions(self):
        """Every state should have defined transitions."""
        for state in JobState:
            assert state in VALID_TRANSITIONS, f"State {state} missing from VALID_TRANSITIONS"
    
    def test_terminal_states_have_no_transitions(self):
        """Terminal states should have empty transition sets."""
        assert len(VALID_TRANSITIONS[JobState.COMPLETED]) == 0
        assert len(VALID_TRANSITIONS[JobState.CANCELLED]) == 0


class TestStateMachine:
    """Test StateMachine class."""
    
    def test_initial_state(self):
        """State machine should start in CREATED state by default."""
        sm = StateMachine()
        assert sm.state == JobState.CREATED
    
    def test_valid_transition(self):
        """Valid transitions should succeed."""
        sm = StateMachine(JobState.CREATED)
        new_state = sm.transition_to(JobState.QUEUED)
        assert new_state == JobState.QUEUED
        assert sm.state == JobState.QUEUED
    
    def test_invalid_transition_raises_error(self):
        """Invalid transitions should raise ValueError."""
        sm = StateMachine(JobState.CREATED)
        with pytest.raises(ValueError, match="Cannot transition"):
            sm.transition_to(JobState.COMPLETED)
    
    def test_history_tracking(self):
        """State machine should track transition history."""
        sm = StateMachine(JobState.CREATED)
        sm.transition_to(JobState.QUEUED, "User submitted job")
        sm.transition_to(JobState.PLANNING, "Context ready")
        
        history = sm.history
        assert len(history) == 2
        assert history[0]["from"] == JobState.CREATED.value
        assert history[0]["to"] == JobState.QUEUED.value


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
