"""
JOB SYSTEM — Everything is a Job.

Each Job has: id, goal, intent, priority, deadline, plan, steps, context,
artifacts, cost, models_used, workers_used, metrics, history, state.

Jobs flow through a formal state machine:
  Created → Queued → Planning → ContextBuilding → Executing → Verifying → Reviewing → Completed
                                                                  ↓
                                                            Failed → Retrying → Cancelled
"""

import json, time, hashlib
from typing import Optional
from datetime import datetime
from enum import Enum
from .state_machine import StateMachine, JobState, StepStateMachine, StepState
from .task_graph import TaskGraph


class JobPriority(Enum):
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


class JobStep:
    """A single step within a Job, with its own state machine."""

    def __init__(self, name: str, worker_type: str = "",
                 params: dict = None, description: str = ""):
        self.id = hashlib.md5(f"{name}:{time.time()}".encode()).hexdigest()[:8]
        self.name = name
        self.worker_type = worker_type
        self.params = params or {}
        self.description = description or name
        self._state = StepStateMachine()
        self.started: Optional[float] = None
        self.completed: Optional[float] = None
        self.duration: float = 0.0
        self.result: dict = {}
        self.error: str = ""
        self.artifacts: list[str] = []
        self.command_id: str = ""

    @property
    def status(self) -> StepState:
        return self._state.state

    @status.setter
    def status(self, value):
        if isinstance(value, str):
            try:
                self._state.transition_to(StepState(value))
            except (ValueError, KeyError):
                pass
        elif isinstance(value, StepState):
            self._state.transition_to(value)

    def to_dict(self) -> dict:
        return {
            "id": self.id, "name": self.name, "worker_type": self.worker_type,
            "params": self.params, "description": self.description,
            "status": self._state.state.value, "started": self.started,
            "completed": self.completed, "duration": self.duration,
            "result": self.result, "error": self.error,
            "artifacts": self.artifacts,
        }


class Job:
    """A unit of work flowing through the system.
    
    Enriched with: goal, intent, plan, cost, models_used, workers_used,
    history, state, task_graph.
    
    Every job can be replayed later from its history.
    """

    def __init__(self, name: str, description: str = "",
                 priority: JobPriority = JobPriority.NORMAL,
                 deadline: float = 0.0, tags: list[str] = None):
        self.id = hashlib.md5(f"{name}:{time.time()}:{id(self)}".encode()).hexdigest()[:12]
        self.name = name
        self.description = description or name
        self.priority = priority
        self.deadline = deadline
        self.tags = tags or []

        # Enriched fields
        self.goal: str = ""
        self.intent: str = ""
        self.plan: dict = {}
        self.cost: float = 0.0
        self.models_used: list[str] = []
        self.workers_used: list[str] = []
        self.history: list[dict] = []

        # State machine
        self._state = StateMachine(JobState.CREATED)

        # Timing
        self.created_at = time.time()
        self.started_at: Optional[float] = None
        self.completed_at: Optional[float] = None
        self.duration: float = 0.0

        # Steps & Task Graph
        self.steps: list[JobStep] = []
        self.task_graph: TaskGraph = TaskGraph()

        # Context
        self.context: dict = {
            "task": "", "goal": "", "clarification": "",
            "files": [], "related_files": [],
            "requirements": [], "constraints": [],
            "project_knowledge": {},
            "user_input": {}, "version": 1, "created_by": "system",
        }

        # Artifacts
        self.artifacts: list[dict] = []

        # Metrics
        self.metrics: dict = {
            "tokens_used": 0, "llm_calls": 0, "tool_calls": 0,
            "commands_dispatched": 0, "errors": 0, "retries": 0,
        }

        # Result
        self.result: dict = {}
        self.error: str = ""

        # Metadata
        self.source: str = ""
        self.parent_job_id: str = ""

    # ── State Management ──

    @property
    def status(self) -> JobState:
        return self._state.state

    @status.setter
    def status(self, value):
        if isinstance(value, str):
            try:
                self._state.transition_to(JobState(value))
            except (ValueError, KeyError):
                pass
        elif isinstance(value, JobState):
            self._state.transition_to(value)

    def can_transition_to(self, state: JobState) -> bool:
        return self._state.can_transition_to(state)

    def transition_to(self, state: JobState, reason: str = ""):
        self._state.transition_to(state, reason)

    def state_history(self) -> list[dict]:
        return self._state.history

    # ── Goal & Intent ──

    def set_goal(self, goal: str):
        self.goal = goal
        self.context["goal"] = goal

    def set_intent(self, intent: str):
        self.intent = intent

    # ── Step Management ──

    def add_step(self, name: str, worker_type: str = "",
                 params: dict = None, description: str = "") -> JobStep:
        step = JobStep(name, worker_type, params, description)
        self.steps.append(step)
        self.task_graph.add_node(step.id, name, worker_type, description, params)
        return step

    def add_step_with_dependency(self, name: str, worker_type: str,
                                  depends_on: str, params: dict = None,
                                  description: str = "") -> JobStep:
        step = self.add_step(name, worker_type, params, description)
        if depends_on:
            dep_step = self.get_step_by_name(depends_on)
            if dep_step:
                self.task_graph.add_dependency(step.id, dep_step.id)
        return step

    def get_current_step(self) -> Optional[JobStep]:
        for step in self.steps:
            if step._state.state == StepState.RUNNING:
                return step
        for step in self.steps:
            if step._state.state == StepState.PENDING:
                return step
        return None

    def get_step(self, step_id: str) -> Optional[JobStep]:
        for step in self.steps:
            if step.id == step_id:
                return step
        return None

    def get_step_by_name(self, name: str) -> Optional[JobStep]:
        for step in self.steps:
            if step.name == name:
                return step
        return None

    @property
    def progress(self) -> float:
        if not self.steps:
            return 1.0 if self._state.state == JobState.COMPLETED else 0.0
        completed = sum(1 for s in self.steps if s._state.state == StepState.COMPLETED)
        return completed / len(self.steps)

    # ── Context Management ──

    def update_context(self, key: str, value, worker: str = "system"):
        self.context[key] = value
        self.context["version"] = self.context.get("version", 1) + 1
        self.context["created_by"] = worker

    def get_context_summary(self, max_length: int = 500) -> str:
        parts = [f"Task: {self.context.get('task', '')[:100]}"]
        files = self.context.get("files", [])
        if files:
            parts.append(f"Files: {', '.join(files[:5])}")
        return "\n".join(parts)[:max_length]

    # ── Cost Tracking ──

    def add_model_usage(self, model: str, tokens: int, cost: float):
        if model not in self.models_used:
            self.models_used.append(model)
        self.cost += cost
        self.metrics["tokens_used"] += tokens
        self.metrics["llm_calls"] += 1

    def add_worker_usage(self, worker_name: str):
        if worker_name not in self.workers_used:
            self.workers_used.append(worker_name)

    # ── History / Replay ──

    def add_history_entry(self, entry_type: str, data: dict):
        self.history.append({
            "type": entry_type, "data": data,
            "timestamp": time.time(),
            "state": self._state.state.value,
        })
        if len(self.history) > 100:
            self.history = self.history[-100:]

    def get_replay(self) -> list[dict]:
        return [
            {
                "state": self._state.state.value,
                "duration": self.duration,
                "steps": [st.to_dict() for st in self.steps],
                "cost": self.cost,
                "models": list(self.models_used),
                "workers": list(self.workers_used),
                "metrics": dict(self.metrics),
            }
        ] + self.history

    # ── Serialization ──

    def to_dict(self) -> dict:
        return {
            "id": self.id, "name": self.name, "description": self.description,
            "priority": self.priority.value, "deadline": self.deadline,
            "tags": self.tags, "goal": self.goal, "intent": self.intent,
            "state": self._state.state.value,
            "state_history": self._state.history,
            "created_at": self.created_at, "started_at": self.started_at,
            "completed_at": self.completed_at, "duration": self.duration,
            "steps": [s.to_dict() for s in self.steps],
            "task_graph": self.task_graph.to_dict(),
            "context": {k: v for k, v in self.context.items() if k != "llm_context"},
            "artifacts": self.artifacts, "cost": self.cost,
            "models_used": list(self.models_used),
            "workers_used": list(self.workers_used),
            "metrics": dict(self.metrics),
            "history": self.history[-20:],
            "result": self.result, "error": self.error,
            "source": self.source, "parent_job_id": self.parent_job_id,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, default=str)

    def status_line(self) -> str:
        progress = f"{int(self.progress * 100)}%"
        steps_str = f"{sum(1 for s in self.steps if s._state.state == StepState.COMPLETED)}/{len(self.steps)}"
        return (f"[{self._state.state.value.upper()}] {self.name[:50]} "
                f"| progress: {progress} | steps: {steps_str} "
                f"| priority: {self.priority.name} "
                f"| cost: ${self.cost:.4f}")

    # ═══════════════════════════════════════════
    # Backward compatible aliases
    # ═══════════════════════════════════════════

    @property
    def status_old(self):
        """Backward-compatible status enum (JobStatus)."""
        from enum import Enum
        class JobStatus(Enum):
            PENDING = "pending"
            QUEUED = "queued"
            RUNNING = "running"
            COMPLETED = "completed"
            FAILED = "failed"
            CANCELLED = "cancelled"
            PAUSED = "paused"
        
        state_map = {
            JobState.CREATED: JobStatus.PENDING,
            JobState.QUEUED: JobStatus.QUEUED,
            JobState.PLANNING: JobStatus.RUNNING,
            JobState.CONTEXT_BUILDING: JobStatus.RUNNING,
            JobState.EXECUTING: JobStatus.RUNNING,
            JobState.VERIFYING: JobStatus.RUNNING,
            JobState.REVIEWING: JobStatus.RUNNING,
            JobState.COMPLETED: JobStatus.COMPLETED,
            JobState.FAILED: JobStatus.FAILED,
            JobState.RETRYING: JobStatus.RUNNING,
            JobState.CANCELLED: JobStatus.CANCELLED,
            JobState.PAUSED: JobStatus.PAUSED,
        }
        return state_map.get(self._state.state, JobStatus.PENDING)
