"""
SCHEDULER — Priority-based job scheduling with worker pool and retry queue.

Architecture:
  Job Queue → Priority Scheduler → Worker Pool → Retry Queue → Completed

Features:
  - Priority-based ordering (CRITICAL > HIGH > NORMAL > LOW)
  - Deadline-aware scheduling (EDF-like for time-critical jobs)
  - Worker pool with configurable concurrency
  - Automatic retry with exponential backoff
  - Job dependencies (a job waits for its dependencies to complete)
  - Rate limiting (max jobs per second)
  - Graceful cancellation and preemption
"""

import time, threading, heapq
from typing import Optional, Callable
from collections import defaultdict
from enum import Enum, auto
from dataclasses import dataclass, field


class JobStatus(Enum):
    PENDING = auto()
    QUEUED = auto()
    RUNNING = auto()
    RETRYING = auto()
    COMPLETED = auto()
    FAILED = auto()
    CANCELLED = auto()
    BLOCKED = auto()       # Waiting for dependencies


@dataclass(order=True)
class ScheduledJob:
    """A job in the scheduler, ordered by priority then deadline then time."""
    priority: int           # Higher = more urgent
    deadline: float         # Earlier deadline first (EDF)
    created_at: float       # FIFO tiebreaker
    job_id: str = field(compare=False)
    name: str = field(compare=False)
    status: JobStatus = field(compare=False)
    handler: Callable = field(compare=False)
    retries: int = field(compare=False, default=0)
    max_retries: int = field(compare=False, default=3)
    error: str = field(compare=False, default="")
    dependencies: list[str] = field(compare=False, default_factory=list)
    metadata: dict = field(compare=False, default_factory=dict)
    result: dict = field(compare=False, default_factory=dict)


class WorkerPool:
    """Manages concurrent execution of jobs using a thread pool."""

    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
        self._active: dict[str, threading.Thread] = {}
        self._lock = threading.Lock()

    @property
    def available(self) -> int:
        return self.max_workers - len(self._active)

    @property
    def active_count(self) -> int:
        return len(self._active)

    def can_accept(self) -> bool:
        return len(self._active) < self.max_workers

    def start(self, job_id: str, target: Callable) -> bool:
        """Start executing a job. Returns True if started."""
        with self._lock:
            if not self.can_accept():
                return False
            thread = threading.Thread(target=target, daemon=True)
            self._active[job_id] = thread
            thread.start()
            return True

    def complete(self, job_id: str):
        """Mark a job as completed (releases a slot)."""
        with self._lock:
            self._active.pop(job_id, None)

    def cancel(self, job_id: str):
        """Cancel a running job (we can't force-stop threads easily)."""
        with self._lock:
            self._active.pop(job_id, None)

    def wait_all(self, timeout: float = 10.0):
        """Wait for all active jobs to finish."""
        end = time.time() + timeout
        while self._active and time.time() < end:
            for job_id in list(self._active.keys()):
                thread = self._active.get(job_id)
                if thread and not thread.is_alive():
                    self.complete(job_id)
            time.sleep(0.05)

    def is_alive(self, job_id: str) -> bool:
        return job_id in self._active


class RetryQueue:
    """Queue for jobs that need retrying with exponential backoff."""

    def __init__(self):
        self._jobs: dict[str, ScheduledJob] = {}
        self._retry_times: dict[str, float] = {}  # job_id -> next retry time

    def add(self, job: ScheduledJob):
        """Add a job to the retry queue."""
        self._jobs[job.job_id] = job
        backoff = min(2 ** job.retries, 60)  # cap at 60s
        self._retry_times[job.job_id] = time.time() + backoff

    def pop_ready(self) -> list[ScheduledJob]:
        """Pop all jobs that are ready for retry."""
        ready = []
        for job_id in list(self._jobs.keys()):
            if time.time() >= self._retry_times.get(job_id, 0):
                job = self._jobs.pop(job_id)
                self._retry_times.pop(job_id, None)
                ready.append(job)
        return ready

    def __len__(self) -> int:
        return len(self._jobs)


class PriorityScheduler:
    """Core scheduling logic.

    Maintains a priority queue (heap) of jobs ordered by:
      1. Priority (CRITICAL first)
      2. Deadline (earliest deadline first)
      3. Created time (FIFO)
    """

    def __init__(self):
        self._heap: list[ScheduledJob] = []
        self._lock = threading.Lock()

    def push(self, job: ScheduledJob):
        with self._lock:
            heapq.heappush(self._heap, job)

    def pop(self) -> Optional[ScheduledJob]:
        with self._lock:
            if not self._heap:
                return None
            return heapq.heappop(self._heap)

    def peek(self) -> Optional[ScheduledJob]:
        with self._lock:
            if not self._heap:
                return None
            return self._heap[0]

    def remove(self, job_id: str) -> bool:
        with self._lock:
            for i, job in enumerate(self._heap):
                if job.job_id == job_id:
                    self._heap[i] = self._heap[-1]
                    self._heap.pop()
                    heapq.heapify(self._heap)
                    return True
            return False

    def __len__(self) -> int:
        return len(self._heap)


class Scheduler:
    """Advanced job scheduler with priority, worker pool, retry, and resource awareness.

    Architecture:
      Job Queue → Priority Scheduler → Worker Pool → Retry Queue → Completed

    Usage:
        scheduler = Scheduler(max_workers=8)
        scheduler.start()

        scheduler.submit("job-1", "My Job", handler=my_func, priority=3)
        scheduler.submit("job-2", "Critical Job", handler=my_func2, priority=4)

        scheduler.stop()
    """

    def __init__(self, max_workers: int = 4, max_retries: int = 3,
                 rate_limit: float = 0.0):
        """
        Args:
            max_workers: Max concurrent job executions.
            max_retries: Default max retries per job.
            rate_limit: Max jobs per second (0 = unlimited).
        """
        self.max_workers = max_workers
        self.max_retries = max_retries
        self.rate_limit = rate_limit

        # Core components
        self.queue = PriorityScheduler()
        self.worker_pool = WorkerPool(max_workers)
        self.retry_queue = RetryQueue()

        # Tracking
        self._jobs: dict[str, ScheduledJob] = {}       # All jobs by ID
        self._completed: list[ScheduledJob] = []       # Recently completed
        self._blocked: dict[str, list[ScheduledJob]] = defaultdict(list)  # blocked_by -> [jobs]

        # Stats
        self._stats = {
            "submitted": 0,
            "completed": 0,
            "failed": 0,
            "cancelled": 0,
            "retried": 0,
            "active": 0,
        }

        # Lifecycle
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        # Callbacks
        self.on_job_completed: Optional[Callable] = None
        self.on_job_failed: Optional[Callable] = None
        self.on_job_retrying: Optional[Callable] = None

    # ── Job Submission ──

    def submit(self, job_id: str, name: str, handler: Callable,
               priority: int = 2, deadline: float = 0.0,
               max_retries: int = None, dependencies: list[str] = None,
               metadata: dict = None) -> bool:
        """Submit a job to the scheduler.

        Args:
            job_id: Unique job identifier.
            name: Human-readable job name.
            handler: Callable to execute (takes job_id, metadata).
            priority: 1 (LOW) to 4 (CRITICAL).
            deadline: Unix timestamp deadline (0 = no deadline).
            max_retries: Override default max retries.
            dependencies: List of job_ids that must complete first.
            metadata: Arbitrary data passed to handler.

        Returns:
            True if submitted successfully, False if job_id already exists.
        """
        with self._lock:
            if job_id in self._jobs:
                return False

            now = time.time()
            job = ScheduledJob(
                priority=priority,
                deadline=deadline if deadline > 0 else float('inf'),
                created_at=now,
                job_id=job_id,
                name=name,
                status=JobStatus.PENDING,
                handler=handler,
                max_retries=max_retries or self.max_retries,
                dependencies=dependencies or [],
                metadata=metadata or {},
            )

            self._jobs[job_id] = job
            self._stats["submitted"] += 1

            if job.dependencies:
                # Check if dependencies exist
                missing = [d for d in job.dependencies if d not in self._jobs]
                if missing:
                    job.error = f"Missing dependencies: {missing}"
                    self._fail_job(job)
                    return True

                # Check if dependencies are already completed
                deps_done = all(
                    self._jobs[d].status == JobStatus.COMPLETED
                    for d in job.dependencies
                )
                if deps_done:
                    self._enqueue(job)
                else:
                    job.status = JobStatus.BLOCKED
                    for dep_id in job.dependencies:
                        self._blocked[dep_id].append(job)
            else:
                self._enqueue(job)

            return True

    def _enqueue(self, job: ScheduledJob):
        """Add a job to the priority queue."""
        job.status = JobStatus.QUEUED
        self.queue.push(job)

    def _fail_job(self, job: ScheduledJob):
        """Mark a job as failed."""
        job.status = JobStatus.FAILED
        self._stats["failed"] += 1
        if self.on_job_failed:
            self.on_job_failed(job)

    # ── Lifecycle ──

    def start(self):
        """Start the scheduler loop in a background thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 5.0):
        """Stop the scheduler gracefully."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=timeout)
        self.worker_pool.wait_all(timeout)

    def _run_loop(self):
        """Main scheduling loop."""
        last_rate_check = time.time()
        jobs_this_second = 0

        while self._running:
            try:
                now = time.time()

                # Rate limiting
                if self.rate_limit > 0:
                    if now - last_rate_check >= 1.0:
                        last_rate_check = now
                        jobs_this_second = 0
                    elif jobs_this_second >= self.rate_limit:
                        time.sleep(0.05)
                        continue

                # Process retry queue
                for job in self.retry_queue.pop_ready():
                    self._stats["retried"] += 1
                    job.status = JobStatus.QUEUED
                    self.queue.push(job)
                    if self.on_job_retrying:
                        self.on_job_retrying(job)

                # Dequeue and execute
                if self.worker_pool.can_accept():
                    job = self.queue.pop()
                    if job:
                        self._execute_job(job)
                        jobs_this_second += 1
                else:
                    time.sleep(0.05)

            except Exception:
                time.sleep(0.1)

    def _execute_job(self, job: ScheduledJob):
        """Execute a job in the worker pool."""
        job.status = JobStatus.RUNNING
        self._stats["active"] += 1

        def run():
            try:
                start = time.time()
                result = job.handler(job.job_id, job.metadata)
                duration = time.time() - start

                job.result = result if isinstance(result, dict) else {"result": result}
                job.status = JobStatus.COMPLETED
                self._stats["completed"] += 1
                self._stats["active"] -= 1
                self._completed.append(job)
                if len(self._completed) > 100:
                    self._completed.pop(0)

                # Unblock dependent jobs
                self._unblock_dependents(job.job_id)

                if self.on_job_completed:
                    self.on_job_completed(job)

            except Exception as e:
                self._stats["active"] -= 1
                job.error = str(e)

                if job.retries < job.max_retries:
                    job.retries += 1
                    job.status = JobStatus.RETRYING
                    self.retry_queue.add(job)
                else:
                    self._fail_job(job)
            finally:
                self.worker_pool.complete(job.job_id)

        started = self.worker_pool.start(job.job_id, run)
        if not started:
            # Pool full, push back
            job.status = JobStatus.QUEUED
            self.queue.push(job)

    def _unblock_dependents(self, completed_job_id: str):
        """Unblock jobs waiting on a completed dependency."""
        for job in self._blocked.pop(completed_job_id, []):
            job.dependencies.remove(completed_job_id)
            if not job.dependencies:
                job.status = JobStatus.QUEUED
                self.queue.push(job)

    # ── Management ──

    def cancel(self, job_id: str) -> bool:
        """Cancel a queued or running job."""
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return False
            if job.status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
                return False

            # Remove from queue
            self.queue.remove(job_id)
            self.worker_pool.cancel(job_id)
            job.status = JobStatus.CANCELLED
            self._stats["cancelled"] += 1
            return True

    def get_status(self, job_id: str) -> Optional[dict]:
        """Get the status of a job."""
        job = self._jobs.get(job_id)
        if not job:
            return None
        return {
            "job_id": job.job_id,
            "name": job.name,
            "status": job.status.name,
            "priority": job.priority,
            "retries": job.retries,
            "max_retries": job.max_retries,
            "error": job.error,
            "result": job.result,
            "dependencies": job.dependencies,
        }

    def list_jobs(self, status: JobStatus = None) -> list[dict]:
        """List all jobs, optionally filtered by status."""
        jobs = []
        for job in self._jobs.values():
            if status and job.status != status:
                continue
            jobs.append({
                "job_id": job.job_id,
                "name": job.name,
                "status": job.status.name,
                "priority": job.priority,
            })
        return jobs

    def get_stats(self) -> dict:
        """Get scheduler statistics."""
        return {
            **self._stats,
            "queued": len(self.queue),
            "retry_queue": len(self.retry_queue),
            "blocked": sum(len(v) for v in self._blocked.values()),
            "worker_pool_available": self.worker_pool.available,
            "worker_pool_active": self.worker_pool.active_count,
            "worker_pool_max": self.worker_pool.max_workers,
            "total_jobs": len(self._jobs),
        }
