"""
KERNEL — The brain of the system.

The Kernel is the central orchestrator. Everything communicates through it.
- Receives tasks → Creates Jobs → Dispatches events → Collects results → Returns answers
- Nothing talks directly to anything else
- The Kernel manages the Event Bus, Runtime, Workers, Artifacts, and Monitoring
"""

import time, json, threading, traceback
from typing import Optional
from pathlib import Path

from .event_bus import EventBus, Event, EVT_TASK_CREATED, EVT_CONTEXT_BUILT, \
    EVT_PLAN_CREATED, EVT_STEP_STARTED, EVT_STEP_COMPLETED, EVT_STEP_FAILED, \
    EVT_WORKER_STARTED, EVT_WORKER_COMPLETED, EVT_WORKER_FAILED, \
    EVT_VERIFICATION_STARTED, EVT_VERIFICATION_PASSED, EVT_VERIFICATION_FAILED, \
    EVT_JOB_FINISHED, EVT_JOB_FAILED, EVT_JOB_CANCELLED, EVT_ERROR, EVT_LOG, \
    EventPriority
from .job import Job, JobStep, JobPriority
from .state_machine import JobState
from .commands import CommandBus
from .capabilities import CapabilityRegistry
from .artifact import Artifact, ArtifactType, ArtifactStore
from .runtime import Runtime
from .worker import BaseWorker
from .monitor import SystemMonitor, MetricsStore, WorkerTelemetry
from .scheduler import Scheduler
from .resources import ResourceManager


class Kernel:
    """Central orchestrator — the brain of the system.
    
    The Kernel:
    1. Receives tasks from users or the agent loop
    2. Creates Jobs with proper priorities and deadlines
    3. Dispatches events through the Event Bus
    4. Manages the Runtime (queue, scheduling, execution)
    5. Stores artifacts from every step
    6. Collects results and returns answers
    7. Monitors itself (metrics, errors, performance)
    """

    def __init__(self, workdir: str = ".", max_workers: int = 4):
        self.workdir = str(Path(workdir).resolve())

        # Core subsystems
        self.event_bus = EventBus()
        self.artifacts = ArtifactStore()
        self.runtime = Runtime(self.event_bus, max_workers=max_workers)
        self.command_bus = CommandBus()
        self.capabilities = CapabilityRegistry()
        self.scheduler = Scheduler(max_workers=max_workers)
        self.resource_manager = ResourceManager()
        self.monitor = SystemMonitor()
        self.telemetry = WorkerTelemetry()

        # State
        self._initialized = False
        self._job_history: list[Job] = []
        self._max_job_history = 100

        # Stats
        self._stats = {
            "tasks_received": 0,
            "jobs_created": 0,
            "jobs_completed": 0,
            "jobs_failed": 0,
            "total_duration": 0.0,
            "errors": 0,
        }

        # Set up internal event listeners
        self._setup_listeners()

    def _setup_listeners(self):
        """Set up internal event listeners for tracking."""
        self.event_bus.subscribe(EVT_JOB_FINISHED, self._on_job_finished, "kernel")
        self.event_bus.subscribe(EVT_JOB_FAILED, self._on_job_failed, "kernel")
        self.event_bus.subscribe(EVT_JOB_CANCELLED, self._on_job_cancelled, "kernel")
        self.event_bus.subscribe(EVT_ERROR, self._on_error, "kernel")

    # ── Initialization ──

    def initialize(self):
        """Initialize the kernel and start the runtime and scheduler."""
        if self._initialized:
            return
        self.runtime.start()
        self.scheduler.start()
        self._initialized = True
        self.event_bus.publish(
            "system.log",
            source="kernel",
            data={"message": "Kernel initialized", "level": "info",
                  "workdir": self.workdir},
        )

    def shutdown(self, timeout: float = 5.0):
        """Shut down the kernel gracefully."""
        self.scheduler.stop(timeout)
        self.runtime.stop(timeout)
        self._initialized = False
        self.event_bus.publish(
            "system.log",
            source="kernel",
            data={"message": "Kernel shut down", "level": "info"},
        )

    # ── Task Processing ──

    def process_task(self, task: str, context: dict = None,
                     priority: JobPriority = JobPriority.NORMAL) -> dict:
        """Process a user task end-to-end.
        
        This is the main entry point for the agent.
        It creates a job, queues it, and waits for completion.
        
        Returns the job result.
        """
        self._stats["tasks_received"] += 1

        # Create job
        job = Job(
            name=task[:80],
            description=task,
            priority=priority,
            tags=["task"],
        )
        job.source = "kernel"
        job.context["task"] = task
        if context:
            job.context.update(context)

        # Add standard pipeline steps
        self._add_standard_steps(job, task)

        # Submit to runtime
        self._stats["jobs_created"] += 1
        job_id = self.runtime.submit(job)
        self._job_history.append(job)
        if len(self._job_history) > self._max_job_history:
            self._job_history.pop(0)

        # Wait for completion (poll-based)
        return self._wait_for_job(job_id)

    def process_task_async(self, task: str, context: dict = None,
                           priority: JobPriority = JobPriority.NORMAL) -> str:
        """Submit a task and return immediately with the job ID.
        
        Use get_job_result() to retrieve results later.
        """
        self._stats["tasks_received"] += 1

        job = Job(
            name=task[:80],
            description=task,
            priority=priority,
            tags=["task"],
        )
        job.source = "kernel"
        job.context["task"] = task
        if context:
            job.context.update(context)

        self._add_standard_steps(job, task)
        self._stats["jobs_created"] += 1
        job_id = self.runtime.submit(job)
        self._job_history.append(job)

        return job_id

    def _add_standard_steps(self, job: Job, task: str):
        """Add standard pipeline steps to a job."""
        # Step 1: Discover context
        job.add_step("Discover Context", "context",
                     params={"task": task, "workdir": self.workdir},
                     description="Analyze task and find relevant files")

        # Step 2: Plan
        job.add_step("Plan", "planner",
                     params={"task": task},
                     description="Create execution plan")

        # Step 3: Execute
        job.add_step("Execute", "executor",
                     params={"task": task},
                     description="Execute the planned changes")

        # Step 4: Verify
        job.add_step("Verify", "verifier",
                     params={},
                     description="Verify changes")

        # Step 5: Review
        job.add_step("Review", "reviewer",
                     params={},
                     description="Review quality and security")

    def _wait_for_job(self, job_id: str, poll_interval: float = 0.2,
                      timeout: float = 600.0) -> dict:
        """Wait for a job to complete."""
        start = time.time()
        while time.time() - start < timeout:
            status = self.runtime.get_status(job_id)
            if status:
                if status["status"] in ("completed", "failed", "cancelled"):
                    job = self._find_job(job_id)
                    if job:
                        result = {
                            "job_id": job.id,
                            "status": job.status.value,
                            "name": job.name,
                            "duration": job.duration,
                            "steps": [s.to_dict() for s in job.steps],
                            "metrics": job.metrics,
                            "result": job.result,
                            "error": job.error,
                            "artifacts": job.artifacts,
                        }
                        # Gather step artifacts
                        step_artifacts = []
                        for step in job.steps:
                            for art_id in step.artifacts:
                                art = self.artifacts.get(art_id)
                                if art:
                                    step_artifacts.append(art.summary(100))
                        result["step_artifacts"] = step_artifacts
                        return result
                    break
                elif status["status"] == "failed":
                    return {"status": "failed", "error": status.get("error", "Unknown")}
            time.sleep(poll_interval)
        return {"status": "timeout", "error": f"Job did not complete within {timeout}s"}

    def _find_job(self, job_id: str) -> Optional[Job]:
        """Find a job by ID across all stores."""
        return self.runtime.queue.get(job_id) or \
            next((j for j in self.runtime._active.values() if j.id == job_id), None) or \
            next((j for j in self._job_history if j.id == job_id), None)

    # ── Event Handlers ──

    def _on_job_finished(self, event: Event):
        """Handle job completion."""
        data = event.data
        self._stats["jobs_completed"] += 1
        if "duration" in data:
            self._stats["total_duration"] += data["duration"]

    def _on_job_failed(self, event: Event):
        """Handle job failure."""
        self._stats["jobs_failed"] += 1

    def _on_job_cancelled(self, event: Event):
        """Handle job cancellation."""
        pass

    def _on_error(self, event: Event):
        """Handle system errors."""
        self._stats["errors"] += 1

    # ── Query ──

    def get_job_result(self, job_id: str) -> Optional[dict]:
        """Get the result of a job by ID."""
        status = self.runtime.get_status(job_id)
        if status:
            job = self._find_job(job_id)
            if job:
                return {
                    "status": status["status"],
                    "progress": status["progress"],
                    "steps": status.get("steps", []),
                    "result": job.result if job.status == JobState.COMPLETED else None,
                    "error": job.error if job.status in (JobState.FAILED, JobState.CANCELLED) else None,
                }
        return None

    def list_jobs(self, status: str = None) -> list[dict]:
        """List all jobs."""
        jobs = []
        for job in self._job_history:
            if status and job.status.value != status:
                continue
            jobs.append(job.to_dict())
        return jobs

    def get_event_history(self, event_type: str = "", limit: int = 20) -> list[dict]:
        """Get recent event history."""
        events = self.event_bus.get_history(event_type, limit)
        return [{
            "id": e.id,
            "type": e.event_type,
            "source": e.source,
            "data": e.data,
            "time": e.datetime,
            "consumed_by": e.consumed_by,
        } for e in events]

    # ── Registration ──

    def register_worker(self, worker: BaseWorker):
        """Register a worker with the runtime, scheduler, and capabilities."""
        self.runtime.register_worker(worker)

        # Register worker scheduler handler
        worker_type = worker.worker_type
        worker_name = worker.name

        def scheduler_handler(job_id: str, metadata: dict) -> dict:
            """Handler for scheduler jobs that delegates to the worker."""
            command = metadata.get("command", "")
            params = metadata.get("params", {})
            return worker.handle(command, params)

        # Register as a capability
        self.capabilities.register(
            name=worker_type,
            executor=scheduler_handler,
            description=f"{worker_name} worker",
            domain="worker",
            provider=worker_type,
        )

        # Wire up command bus if worker has a command_bus attribute
        if hasattr(worker, 'command_bus') and worker.command_bus is None:
            worker.command_bus = self.command_bus

        # Subscribe worker telemetry to step events
        worker_name = worker.name
        self.event_bus.subscribe(
            "step.started",
            lambda e: self.telemetry.record_worker_execution(
                worker_name=worker_name, command_type="handle",
                success=True, duration=0.0,
            ) if e.data.get("worker") == worker.worker_type else None,
            "kernel"
        )

    def get_worker(self, worker_type: str) -> Optional[BaseWorker]:
        """Get a registered worker."""
        return self.runtime.get_worker(worker_type)

    def list_workers(self) -> list[str]:
        """List all registered worker types."""
        return self.runtime.list_workers()

    # ── Statistics ──

    # ── Scheduler Integration ──

    def schedule_job(self, job_id: str, name: str, handler: callable,
                     priority: int = 2, deadline: float = 0.0,
                     max_retries: int = None, dependencies: list[str] = None,
                     metadata: dict = None) -> bool:
        """Submit a job to the priority scheduler.

        Args:
            job_id: Unique job identifier.
            name: Human-readable job name.
            handler: Callable to execute (takes job_id, metadata).
            priority: 1 (LOW) to 4 (CRITICAL).
            deadline: Unix timestamp deadline.
            max_retries: Override default max retries.
            dependencies: List of job_ids that must complete first.
            metadata: Arbitrary data passed to handler.

        Returns:
            True if submitted successfully.
        """
        return self.scheduler.submit(
            job_id=job_id,
            name=name,
            handler=handler,
            priority=priority,
            deadline=deadline,
            max_retries=max_retries,
            dependencies=dependencies,
            metadata=metadata,
        )

    def get_scheduler_status(self, job_id: str = None):
        """Get scheduler status for a job or all jobs."""
        if job_id:
            return self.scheduler.get_status(job_id)
        return self.scheduler.list_jobs()

    # ── Resource Management Integration ──

    def get_resource_summary(self) -> str:
        """Get human-readable resource usage summary."""
        return self.resource_manager.get_summary()

    # ── Statistics ──

    def get_kernel_stats(self) -> dict:
        """Get comprehensive kernel statistics."""
        runtime_stats = self.runtime.get_stats()
        bus_stats = self.event_bus.get_stats()
        cap_stats = self.capabilities.get_statistics() if hasattr(self.capabilities, 'get_statistics') else {}
        tel_summary = self.telemetry.get_summary() if hasattr(self.telemetry, 'get_summary') else {}
        scheduler_stats = self.scheduler.get_stats()
        resource_stats = self.resource_manager.get_stats()
        return {
            "kernel": self._stats,
            "runtime": runtime_stats,
            "scheduler": scheduler_stats,
            "resource_manager": resource_stats,
            "event_bus": bus_stats,
            "capabilities": cap_stats,
            "telemetry": tel_summary,
            "initialized": self._initialized,
            "workdir": self.workdir,
        }

    def get_snapshot(self) -> dict:
        """Get a snapshot of the entire system state."""
        return {
            "kernel_stats": self.get_kernel_stats(),
            "active_jobs": [{
                "id": j.id, "name": j.name, "status": j.status.value,
                "progress": j.progress, "current_step": j.get_current_step().name if j.get_current_step() else None,
            } for j in self.runtime.get_active_jobs()],
            "queued_jobs": len(self.runtime.queue),
            "workers": self.list_workers(),
            "capabilities": self.capabilities.domains if hasattr(self.capabilities, 'domains') else [],
            "recent_events": self.get_event_history(limit=10),
        }
