"""
COMMANDS — Tell workers what to do. Separate from Events.

Commands are directed at specific workers. Events inform everyone.
  Command: "ContextWorker, build context for job X"
  Event:   "Context was built for job X"

This separation makes debugging much easier.
"""

from dataclasses import dataclass, field
from typing import Optional
from enum import Enum, auto
import time


class CommandStatus(Enum):
    PENDING = "pending"
    DISPATCHED = "dispatched"
    ACKNOWLEDGED = "acknowledged"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass
class Command:
    """A directed instruction to a specific worker.
    
    Commands tell workers what to do.
    Workers publish Events when done.
    """
    command_type: str            # e.g. "build_context", "create_plan", "execute_step"
    target_worker: str           # e.g. "context_worker", "planner_worker"
    job_id: str = ""
    step_id: str = ""
    params: dict = field(default_factory=dict)
    priority: int = 0
    created_at: float = 0.0
    dispatched_at: float = 0.0
    completed_at: float = 0.0
    status: CommandStatus = CommandStatus.PENDING
    result: dict = field(default_factory=dict)
    error: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = time.time()

    @property
    def duration(self) -> float:
        if self.completed_at and self.dispatched_at:
            return self.completed_at - self.dispatched_at
        return 0.0

    def to_dict(self) -> dict:
        return {
            "command_type": self.command_type,
            "target_worker": self.target_worker,
            "job_id": self.job_id,
            "step_id": self.step_id,
            "params": self.params,
            "priority": self.priority,
            "status": self.status.value,
            "duration": self.duration,
            "error": self.error[:200] if self.error else "",
        }


# ── Standard Command Types ──

CMD_BUILD_CONTEXT = "build_context"
CMD_CREATE_PLAN = "create_plan"
CMD_EXECUTE_STEP = "execute_step"
CMD_RUN_VERIFICATION = "run_verification"
CMD_RUN_REVIEW = "run_review"
CMD_SCAN_REPOSITORY = "scan_repository"
CMD_REFRESH_CACHE = "refresh_cache"
CMD_QUERY_CACHE = "query_cache"
CMD_RUN_SECURITY = "run_security"
CMD_RUN_TESTS = "run_tests"
CMD_GENERATE_DOCS = "generate_docs"


# ── Command Helpers ──

def make_command(command_type: str, target_worker: str,
                 job_id: str = "", step_id: str = "",
                 params: dict = None, priority: int = 0) -> Command:
    """Create a new command with default values."""
    return Command(
        command_type=command_type,
        target_worker=target_worker,
        job_id=job_id,
        step_id=step_id,
        params=params or {},
        priority=priority,
        status=CommandStatus.PENDING,
        created_at=time.time(),
    )


class CommandBus:
    """Publishes commands to workers and collects results.
    
    Commands are directed (worker-specific), not broadcast like Events.
    """

    def __init__(self):
        self._pending: list[Command] = []
        self._history: list[Command] = []
        self._max_history = 500

    def dispatch(self, command: Command) -> str:
        """Dispatch a command to a worker. Returns command type."""
        command.status = CommandStatus.DISPATCHED
        command.dispatched_at = time.time()
        self._pending.append(command)
        self._history.append(command)
        if len(self._history) > self._max_history:
            self._history.pop(0)
        return command.command_type

    def acknowledge(self, command_type: str, target_worker: str) -> bool:
        """Mark a command as acknowledged by a worker."""
        for cmd in self._pending:
            if cmd.command_type == command_type and cmd.target_worker == target_worker:
                cmd.status = CommandStatus.ACKNOWLEDGED
                return True
        return False

    def complete(self, command_type: str, target_worker: str,
                 result: dict = None) -> bool:
        """Mark a command as completed."""
        for cmd in self._pending[:]:
            if cmd.command_type == command_type and cmd.target_worker == target_worker:
                cmd.status = CommandStatus.COMPLETED
                cmd.completed_at = time.time()
                cmd.result = result or {}
                self._pending.remove(cmd)
                return True
        return False

    def fail(self, command_type: str, target_worker: str, error: str) -> bool:
        """Mark a command as failed."""
        for cmd in self._pending[:]:
            if cmd.command_type == command_type and cmd.target_worker == target_worker:
                cmd.status = CommandStatus.FAILED
                cmd.completed_at = time.time()
                cmd.error = error
                self._pending.remove(cmd)
                return True
        return False

    def get_pending(self, target_worker: str = "") -> list[Command]:
        """Get pending commands, optionally filtered by worker."""
        if target_worker:
            return [c for c in self._pending if c.target_worker == target_worker]
        return list(self._pending)

    def get_history(self, limit: int = 20) -> list[Command]:
        """Get recent command history."""
        return self._history[-limit:]

    def get_stats(self) -> dict:
        """Get command bus statistics."""
        dispatched = len(self._history)
        completed = sum(1 for c in self._history if c.status == CommandStatus.COMPLETED)
        failed = sum(1 for c in self._history if c.status == CommandStatus.FAILED)
        return {
            "dispatched": dispatched,
            "completed": completed,
            "failed": failed,
            "pending": len(self._pending),
        }
