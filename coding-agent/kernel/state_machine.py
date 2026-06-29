"""
STATE MACHINE — Formal job lifecycle with validated transitions.

Every worker understands the lifecycle. Invalid transitions raise errors.

States:
  Created → Queued → Planning → ContextBuilding → Executing → Verifying → Reviewing → Completed
                                                                  ↓
                                                            Failed → Retrying → (back to step)
                                                                  ↓
                                                            Cancelled
"""

from enum import Enum, auto
from typing import Optional


class JobState(Enum):
    """Formal states for the job lifecycle."""
    CREATED = "created"
    QUEUED = "queued"
    PLANNING = "planning"
    CONTEXT_BUILDING = "context_building"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    REVIEWING = "reviewing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    CANCELLED = "cancelled"
    PAUSED = "paused"


# ── Valid State Transitions ──
# Maps each state to the set of states it can transition to.
VALID_TRANSITIONS: dict[JobState, set[JobState]] = {
    JobState.CREATED: {JobState.QUEUED, JobState.CANCELLED},
    JobState.QUEUED: {JobState.PLANNING, JobState.CANCELLED, JobState.PAUSED},
    JobState.PLANNING: {JobState.CONTEXT_BUILDING, JobState.EXECUTING, JobState.FAILED, JobState.CANCELLED},
    JobState.CONTEXT_BUILDING: {JobState.EXECUTING, JobState.PLANNING, JobState.FAILED, JobState.CANCELLED},
    JobState.EXECUTING: {JobState.VERIFYING, JobState.FAILED, JobState.CANCELLED, JobState.PAUSED},
    JobState.VERIFYING: {JobState.REVIEWING, JobState.EXECUTING, JobState.FAILED, JobState.CANCELLED},
    JobState.REVIEWING: {JobState.COMPLETED, JobState.EXECUTING, JobState.FAILED, JobState.CANCELLED},
    JobState.COMPLETED: set(),  # Terminal state
    JobState.FAILED: {JobState.RETRYING, JobState.QUEUED, JobState.CANCELLED},
    JobState.RETRYING: {JobState.PLANNING, JobState.EXECUTING, JobState.VERIFYING, JobState.FAILED, JobState.CANCELLED},
    JobState.CANCELLED: set(),  # Terminal state
    JobState.PAUSED: {JobState.QUEUED, JobState.CANCELLED},
}


class StateMachine:
    """Validates and manages state transitions."""

    def __init__(self, initial_state: JobState = JobState.CREATED):
        self._state = initial_state
        self._history: list[tuple[JobState, JobState, str]] = []  # (from, to, reason)

    @property
    def state(self) -> JobState:
        return self._state

    @property
    def history(self) -> list[dict]:
        """Get full transition history."""
        return [
            {"from": from_s.value, "to": to_s.value, "reason": reason}
            for from_s, to_s, reason in self._history
        ]

    def can_transition_to(self, new_state: JobState) -> bool:
        """Check if a transition is valid."""
        if new_state == self._state:
            return True
        allowed = VALID_TRANSITIONS.get(self._state, set())
        return new_state in allowed

    def transition_to(self, new_state: JobState, reason: str = "") -> JobState:
        """Transition to a new state. Raises ValueError if invalid."""
        if new_state == self._state:
            return self._state
        
        if not self.can_transition_to(new_state):
            allowed_names = [s.value for s in VALID_TRANSITIONS.get(self._state, set())]
            raise ValueError(
                f"Cannot transition from '{self._state.value}' to '{new_state.value}'. "
                f"Allowed transitions: {allowed_names}"
            )
        
        old_state = self._state
        self._state = new_state
        self._history.append((old_state, new_state, reason or f"{old_state.value} → {new_state.value}"))
        return new_state

    def get_available_transitions(self) -> list[JobState]:
        """Get list of valid next states."""
        return list(VALID_TRANSITIONS.get(self._state, set()))

    def reset(self, state: JobState = JobState.CREATED):
        """Reset the state machine."""
        self._state = state
        self._history = []


# ── Step-Level State Machine ──

class StepState(Enum):
    """Formal states for a job step."""
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


STEP_VALID_TRANSITIONS: dict[StepState, set[StepState]] = {
    StepState.PENDING: {StepState.QUEUED, StepState.SKIPPED, StepState.CANCELLED},
    StepState.QUEUED: {StepState.RUNNING, StepState.CANCELLED},
    StepState.RUNNING: {StepState.COMPLETED, StepState.FAILED, StepState.CANCELLED},
    StepState.COMPLETED: set(),
    StepState.FAILED: {StepState.QUEUED, StepState.CANCELLED},  # Retry
    StepState.SKIPPED: set(),
    StepState.CANCELLED: set(),
}


class StepStateMachine:
    """State machine for individual steps."""

    def __init__(self, initial_state: StepState = StepState.PENDING):
        self._state = initial_state
        self._history: list[tuple[StepState, StepState, str]] = []

    @property
    def state(self) -> StepState:
        return self._state

    def can_transition_to(self, new_state: StepState) -> bool:
        if new_state == self._state:
            return True
        return new_state in STEP_VALID_TRANSITIONS.get(self._state, set())

    def transition_to(self, new_state: StepState, reason: str = "") -> StepState:
        if new_state == self._state:
            return self._state
        if not self.can_transition_to(new_state):
            allowed = [s.value for s in STEP_VALID_TRANSITIONS.get(self._state, set())]
            raise ValueError(
                f"Cannot transition step from '{self._state.value}' to '{new_state.value}'. "
                f"Allowed: {allowed}"
            )
        old = self._state
        self._state = new_state
        self._history.append((old, new_state, reason))
        return new_state
