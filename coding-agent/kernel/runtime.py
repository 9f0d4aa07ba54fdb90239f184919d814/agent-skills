"""
RUNTIME — The execution engine.

Runtime manages:
  - Queue: Ordered queue of pending jobs
  - Scheduler: Priority-based scheduling
  - Workers: Dispatch steps to registered workers
  - Retry: Automatic retry on failure
  - Timeout: Step-level timeout enforcement
  - Cancel: Graceful job cancellation
  - Resume: Continue paused/failed jobs from last successful step

Exactly like a distributed system.
"""

import time, json, threading, traceback
from typing import Optional
from collections import defaultdict
from .event_bus import EventBus, Event, EVT_TASK_CREATED, EVT_CONTEXT_BUILT, \
    EVT_PLAN_CREATED, EVT_STEP_STARTED, EVT_STEP_COMPLETED, EVT_STEP_FAILED, \
    EVT_WORKER_STARTED, EVT_WORKER_COMPLETED, EVT_WORKER_FAILED, \
    EVT_VERIFICATION_STARTED, EVT_VERIFICATION_PASSED, EVT_VERIFICATION_FAILED, \
    EVT_JOB_FINISHED, EVT_JOB_FAILED, EVT_JOB_CANCELLED, EVT_ERROR
from .job import Job, JobStep, JobPriority
from .state_machine import JobState, StepState
from .worker import BaseWorker


class JobQueue:
    """Priority queue for jobs."""

    def __init__(self):
        # Jobs grouped by priority, then FIFO within priority
        self._queues: dict[int, list[Job]] = defaultdict(list)
        self._all_jobs: dict[str, Job] = {}

    def push(self, job: Job):
        """Add a job to the queue."""
        priority = job.priority.value
        self._queues[priority].append(job)
        self._all_jobs[job.id] = job
        job.transition_to(JobState.QUEUED)

    def pop(self) -> Optional[Job]:
        """Get the highest priority job. Returns None if empty."""
        for priority in sorted(self._queues.keys(), reverse=True):
            q = self._queues[priority]
            if q:
                job = q.pop(0)
                return job
        return None

    def peek(self) -> Optional[Job]:
        """Look at the highest priority job without removing it."""
        for priority in sorted(self._queues.keys(), reverse=True):
            q = self._queues[priority]
            if q:
                return q[0]
        return None

    def remove(self, job_id: str) -> bool:
        """Remove a job by ID."""
        if job_id in self._all_jobs:
            job = self._all_jobs[job_id]
            priority = job.priority.value
            self._queues[priority] = [j for j in self._queues[priority] if j.id != job_id]
            del self._all_jobs[job_id]
            return True
        return False

    def get(self, job_id: str) -> Optional[Job]:
        """Get a job by ID."""
        return self._all_jobs.get(job_id)

    def list(self, status: JobState = None) -> list[Job]:
        """List all jobs, optionally filtered by status."""
        jobs = list(self._all_jobs.values())
        if status:
            return [j for j in jobs if j.status == status]
        return sorted(jobs, key=lambda j: (j.priority.value, j.created_at), reverse=True)

    def __len__(self) -> int:
        return len(self._all_jobs)

    @property
    def is_empty(self) -> bool:
        return len(self._all_jobs) == 0


class Runtime:
    """The execution engine.
    
    Manages the lifecycle of jobs from queue to completion.
    """

    def __init__(self, event_bus: EventBus, max_workers: int = 4,
                 default_timeout: float = 300.0, max_retries: int = 2):
        self.event_bus = event_bus
        self.queue = JobQueue()
        self.max_workers = max_workers
        self.default_timeout = default_timeout
        self.max_retries = max_retries

        # Worker registry: worker_type -> BaseWorker
        self._workers: dict[str, BaseWorker] = {}

        # Active jobs: job_id -> job
        self._active: dict[str, Job] = {}

        # Execution tracking
        self._completed_jobs: list[Job] = []
        self._failed_jobs: list[Job] = []
        self._cancelled_jobs: list[Job] = []

        # Stats
        self._stats = {
            "jobs_queued": 0,
            "jobs_started": 0,
            "jobs_completed": 0,
            "jobs_failed": 0,
            "jobs_cancelled": 0,
            "steps_executed": 0,
            "retries": 0,
            "timeouts": 0,
        }

        # Internal
        self._running = False
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None

    # ── Worker Management ──

    def register_worker(self, worker: BaseWorker):
        """Register a worker with the runtime."""
        self._workers[worker.worker_type] = worker
        worker.register()
        self.event_bus.publish(
            "system.log",
            source="runtime",
            data={"message": f"Worker registered: {worker.name}", "level": "info"},
        )

    def get_worker(self, worker_type: str) -> Optional[BaseWorker]:
        """Get a registered worker by type."""
        return self._workers.get(worker_type)

    def list_workers(self) -> list[str]:
        """List all registered worker types."""
        return list(self._workers.keys())

    # ── Job Submission ──

    def submit(self, job: Job) -> str:
        """Submit a job to the queue. Returns job ID."""
        job.transition_to(JobState.QUEUED)
        self.queue.push(job)
        self._stats["jobs_queued"] += 1
        self.event_bus.publish(
            EVT_TASK_CREATED,
            source="runtime",
            data={"job_id": job.id, "job_name": job.name, "priority": job.priority.name},
        )
        return job.id

    # ── Lifecycle ──

    def start(self):
        """Start the runtime in a background thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        self.event_bus.publish(
            "system.log",
            source="runtime",
            data={"message": "Runtime started", "level": "info"},
        )

    def stop(self, timeout: float = 5.0):
        """Stop the runtime."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=timeout)
        self.event_bus.publish(
            "system.log",
            source="runtime",
            data={"message": "Runtime stopped", "level": "info"},
        )

    def _run_loop(self):
        """Main execution loop."""
        while self._running:
            try:
                job = self.queue.pop()
                if job is None:
                    time.sleep(0.1)
                    continue
                self._execute_job(job)
            except Exception as e:
                self.event_bus.publish(
                    EVT_ERROR,
                    source="runtime",
                    data={"error": f"Runtime loop error: {e}",
                          "traceback": traceback.format_exc()},
                )
                time.sleep(0.5)

    # ── Job Execution ──

    def _execute_job(self, job: Job):
        """Execute a single job through its steps."""
        with self._lock:
            self._active[job.id] = job
            self._stats["jobs_started"] += 1

        try:
            job.transition_to(JobState.PLANNING)
            job.transition_to(JobState.EXECUTING)
            job.started_at = time.time()

            # Try to execute all steps
            retry_count = 0
            for step in job.steps:
                if step.status == StepState.COMPLETED:
                    continue  # Already done (resume scenario)

                executed = self._execute_step(job, step, retry_count)
                if not executed:
                    # Step failed
                    if job.status == JobState.CANCELLED:
                        break
                    # Retry
                    while retry_count < self.max_retries:
                        retry_count += 1
                        self._stats["retries"] += 1
                        job.metrics["retries"] += 1
                        self.event_bus.publish(
                            "system.log",
                            source="runtime",
                            data={"message": f"Retrying step '{step.name}' (attempt {retry_count + 1})",
                                  "level": "warning"},
                        )
                        executed = self._execute_step(job, step, retry_count)
                        if executed:
                            break
                    if not executed:
                        break

        finally:
            # Finalize job with lock to ensure thread safety
            with self._lock:
                self._finalize_job(job)
                if job.id in self._active:
                    del self._active[job.id]

    def _execute_step(self, job: Job, step: JobStep, attempt: int = 0) -> bool:
        """Execute a single step. Returns True if successful."""
        worker = self._workers.get(step.worker_type)
        if not worker:
            if step.status == StepState.PENDING:
                step._state.transition_to(StepState.QUEUED)
            if step.can_transition_to(StepState.FAILED):
                step._state.transition_to(StepState.FAILED)
            step.error = f"No worker registered for type: {step.worker_type}"
            self.event_bus.publish(
                EVT_ERROR,
                source="runtime",
                data={"error": step.error, "job_id": job.id, "step_id": step.id},
            )
            return False

        if step.status == StepState.PENDING:
            step._state.transition_to(StepState.QUEUED)
        step._state.transition_to(StepState.RUNNING)
        step.started = time.time()
        self._stats["steps_executed"] += 1

        self.event_bus.publish(
            EVT_STEP_STARTED,
            source=f"runtime/{worker.name}",
            data={"job_id": job.id, "step_id": step.id, "step_name": step.name,
                  "worker": worker.name, "attempt": attempt},
        )

        try:
            # Execute with timeout
            result = self._run_with_timeout(worker.handle, job, step, timeout=self.default_timeout)
            worker.complete_step(job, step, result)
            job.metrics["tool_calls"] += 1
            return True

        except TimeoutError:
            step._state.transition_to(StepState.FAILED)
            step.error = f"Timeout after {self.default_timeout}s"
            step.completed = time.time()
            step.duration = step.completed - step.started
            self._stats["timeouts"] += 1
            job.metrics["errors"] += 1
            self.event_bus.publish(
                EVT_STEP_FAILED,
                source=f"runtime/{worker.name}",
                data={"job_id": job.id, "step_id": step.id, "step_name": step.name,
                      "error": "timeout", "timeout": self.default_timeout},
            )
            return False

        except Exception as e:
            worker.fail_step(job, step, str(e))
            job.metrics["errors"] += 1
            self.event_bus.publish(
                EVT_STEP_FAILED,
                source=f"runtime/{worker.name}",
                data={"job_id": job.id, "step_id": step.id, "step_name": step.name,
                      "error": str(e), "traceback": traceback.format_exc()},
            )
            return False

    def _run_with_timeout(self, fn, *args, timeout: float, **kwargs):
        """Run a function with a timeout using ThreadPoolExecutor."""
        from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
        
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(fn, *args, **kwargs)
            try:
                return future.result(timeout=timeout)
            except FuturesTimeoutError:
                future.cancel()
                raise TimeoutError(f"Execution timed out after {timeout}s")
            except Exception as e:
                raise e

    def _finalize_job(self, job: Job):
        """Finalize a job after all steps complete."""
        job.completed_at = time.time()
        job.duration = job.completed_at - (job.started_at or job.completed_at)

        # Determine overall status
        all_completed = all(s.status == StepState.COMPLETED for s in job.steps)
        any_failed = any(s.status == StepState.FAILED for s in job.steps)
        any_cancelled = job.status == JobState.CANCELLED

        if all_completed:
            if job.status == JobState.EXECUTING:
                job.transition_to(JobState.VERIFYING)
                job.transition_to(JobState.REVIEWING)
            if job.can_transition_to(JobState.COMPLETED):
                job.transition_to(JobState.COMPLETED)
            self._completed_jobs.append(job)
            self._stats["jobs_completed"] += 1
            self.event_bus.publish(
                EVT_JOB_FINISHED,
                source="runtime",
                data={"job_id": job.id, "job_name": job.name,
                      "duration": job.duration, "steps": len(job.steps),
                      "metrics": job.metrics},
            )
        elif any_cancelled:
            self._cancelled_jobs.append(job)
            self._stats["jobs_cancelled"] += 1
            self.event_bus.publish(
                EVT_JOB_CANCELLED,
                source="runtime",
                data={"job_id": job.id, "job_name": job.name},
            )
        else:
            job.transition_to(JobState.FAILED)
            self._failed_jobs.append(job)
            self._stats["jobs_failed"] += 1
            failed_steps = [s for s in job.steps if s.status == StepState.FAILED]
            self.event_bus.publish(
                EVT_JOB_FAILED,
                source="runtime",
                data={"job_id": job.id, "job_name": job.name,
                      "failed_steps": [s.name for s in failed_steps],
                      "errors": [s.error for s in failed_steps]},
            )

    # ── Job Control ──

    def cancel(self, job_id: str) -> bool:
        """Cancel a job."""
        job = self.queue.get(job_id) or self._active.get(job_id)
        if job:
            job.transition_to(JobState.CANCELLED)
            self.event_bus.publish(
                EVT_JOB_CANCELLED,
                source="runtime",
                data={"job_id": job.id, "job_name": job.name},
            )
            return True
        return False

    def pause(self, job_id: str) -> bool:
        """Pause a running job."""
        job = self._active.get(job_id)
        if job and job.status == JobState.EXECUTING:
            job.transition_to(JobState.PAUSED)
            return True
        return False

    def resume(self, job_id: str) -> bool:
        """Resume a paused or failed job from last successful step."""
        job = self._queue.get(job_id)
        if not job:
            job = next((j for j in self._failed_jobs if j.id == job_id), None)
        if job and job.status in (JobState.PAUSED, JobState.FAILED):
            job.transition_to(JobState.QUEUED)
            self.queue.push(job)
            return True
        return False

    def get_status(self, job_id: str) -> Optional[dict]:
        """Get detailed status of a job."""
        job = (self.queue.get(job_id) or self._active.get(job_id) or
               next((j for j in self._completed_jobs if j.id == job_id), None) or
               next((j for j in self._failed_jobs if j.id == job_id), None))
        if job:
            return {
                "id": job.id,
                "name": job.name,
                "status": job.status.value,
                "progress": job.progress,
                "duration": job.duration,
                "current_step": job.get_current_step().name if job.get_current_step() else None,
                "steps": [{"name": s.name, "status": s.status.value, "duration": s.duration,
                          "error": s.error[:100] if s.error else ""}
                         for s in job.steps],
                "metrics": job.metrics,
            }
        return None

    # ── Statistics ──

    def get_stats(self) -> dict:
        """Get runtime statistics."""
        return {
            **self._stats,
            "active_jobs": len(self._active),
            "queued_jobs": len(self.queue),
            "completed_jobs": len(self._completed_jobs),
            "failed_jobs": len(self._failed_jobs),
            "registered_workers": len(self._workers),
            "worker_types": list(self._workers.keys()),
        }

    def get_active_jobs(self) -> list[Job]:
        """Get currently running jobs."""
        return list(self._active.values())
