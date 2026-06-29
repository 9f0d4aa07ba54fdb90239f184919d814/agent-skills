"""
BASE WORKER — Every module becomes a worker.

Workers are the execution units. They subscribe to events, process jobs,
and publish results. Workers don't know about each other — they only
know about the events they handle.

Worker types:
  - RepositoryWorker: Scans and analyzes codebase
  - PlannerWorker: Decomposes tasks into steps
  - ReviewerWorker: Code review and quality analysis
  - SecurityWorker: Security vulnerability assessment
  - TestingWorker: Test generation and execution
  - DocumentationWorker: Documentation generation
  - ContextWorker: Builds context for LLM
  - ExecutorWorker: Executes tool operations
  - VerifierWorker: Verifies changes
  - LearningWorker: Self-improvement and reflection
"""

import time, json, traceback
from typing import Optional
from .event_bus import EventBus, Event, EVT_WORKER_STARTED, EVT_WORKER_COMPLETED, \
    EVT_WORKER_FAILED, EVT_ERROR
from .job import Job, JobStep
from .state_machine import StepState
from .artifact import Artifact, ArtifactType, ArtifactStore


class BaseWorker:
    """Base class for all workers.
    
    Workers subscribe to events, execute job steps, and publish results.
    They are stateless — all state lives in the Job and Artifact.
    """

    def __init__(self, worker_type: str, name: str,
                 event_bus: EventBus, artifact_store: ArtifactStore):
        self.worker_type = worker_type
        self.name = name or worker_type
        self.event_bus = event_bus
        self.artifacts = artifact_store
        self._subscriptions: list[str] = []

    def register(self):
        """Register this worker with the event bus.
        Override to subscribe to specific events.
        """
        pass

    def unregister(self):
        """Unsubscribe from all events."""
        for sub_id in self._subscriptions:
            self.event_bus.unsubscribe(sub_id)
        self._subscriptions = []

    def can_handle(self, step: JobStep) -> bool:
        """Check if this worker can handle a step."""
        return step.worker_type == self.worker_type

    def handle(self, job: Job, step: JobStep) -> dict:
        """Handle a job step. Override in subclasses.
        
        Args:
            job: The parent job
            step: The step to execute
            
        Returns:
            dict with result data
        """
        raise NotImplementedError(f"Worker {self.name} must implement handle()")

    # ── Lifecycle Helpers ──

    def start_step(self, job: Job, step: JobStep):
        """Mark step as running and publish event."""
        if step._state.state == StepState.PENDING:
            step._state.transition_to(StepState.QUEUED)
        step._state.transition_to(StepState.RUNNING)
        step.started = time.time()
        self.event_bus.publish(
            "step.started",
            source=self.name,
            data={"job_id": job.id, "step_id": step.id, "step_name": step.name},
        )

    def complete_step(self, job: Job, step: JobStep, result: dict = None,
                      artifacts: list[Artifact] = None):
        """Mark step as completed and publish event."""
        step._state.transition_to(StepState.COMPLETED)
        step.completed = time.time()
        step.duration = step.completed - (step.started or step.completed)
        step.result = result or {}

        # Store artifacts
        stored_ids = []
        for art in (artifacts or []):
            art.source_job = job.id
            art.source_step = step.id
            stored_ids.append(self.artifacts.store(art))
        step.artifacts = stored_ids

        # Step artifact
        step_artifact = Artifact(
            f"step:{step.name}", ArtifactType.LOG,
            content=json.dumps(step.to_dict(), indent=2),
            source_job=job.id, source_step=step.id,
            tags=["step", step.worker_type],
        )
        self.artifacts.store(step_artifact)

        self.event_bus.publish(
            "step.completed",
            source=self.name,
            data={"job_id": job.id, "step_id": step.id, "step_name": step.name,
                  "duration": step.duration, "artifacts": stored_ids},
        )

    def fail_step(self, job: Job, step: JobStep, error: str):
        """Mark step as failed and publish event."""
        step._state.transition_to(StepState.FAILED)
        step.completed = time.time()
        step.duration = step.completed - (step.started or step.completed)
        step.error = error

        self.event_bus.publish(
            "step.failed",
            source=self.name,
            data={"job_id": job.id, "step_id": step.id, "step_name": step.name,
                  "error": error},
        )

    def create_artifact(self, name: str, artifact_type: ArtifactType,
                        content: str = "", data: dict = None,
                        tags: list[str] = None) -> Artifact:
        """Create a new artifact."""
        return Artifact(name, artifact_type, content, data, tags=tags or [])

    def log(self, message: str, level: str = "info"):
        """Publish a log event."""
        self.event_bus.publish(
            "system.log",
            source=self.name,
            data={"message": message, "level": level, "worker": self.name},
        )

    def __repr__(self):
        return f"<Worker '{self.name}' ({self.worker_type})>"
