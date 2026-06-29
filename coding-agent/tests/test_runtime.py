"""Tests for Runtime — execution engine, JobQueue, and job lifecycle."""

import pytest
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from kernel.event_bus import EventBus
from kernel.job import Job, JobStep, JobPriority
from kernel.runtime import JobQueue, Runtime
from kernel.state_machine import JobState, StepState
from kernel.worker import BaseWorker
from kernel.artifact import ArtifactStore


class StubWorker(BaseWorker):
    """A test worker that succeeds or fails on demand."""

    def __init__(self, event_bus, artifact_store, should_fail=False, delay=0.0):
        super().__init__("stub", "StubWorker", event_bus, artifact_store)
        self.should_fail = should_fail
        self.delay = delay
        self.handle_calls = []

    def handle(self, job, step):
        self.handle_calls.append((job.id, step.id))
        if self.delay > 0:
            time.sleep(self.delay)
        if self.should_fail:
            raise RuntimeError("stub failure")
        return {"status": "ok"}


class TestJobQueue:
    """Tests for the JobQueue priority queue."""

    def test_push_and_pop(self):
        q = JobQueue()
        job = Job("j")
        q.push(job)
        popped = q.pop()
        assert popped is job

    def test_pop_empty(self):
        q = JobQueue()
        assert q.pop() is None

    def test_peek(self):
        q = JobQueue()
        job = Job("j")
        q.push(job)
        peeked = q.peek()
        assert peeked is job
        assert len(q) == 1

    def test_peek_empty(self):
        q = JobQueue()
        assert q.peek() is None

    def test_priority_ordering(self):
        q = JobQueue()
        low = Job("low", priority=JobPriority.LOW)
        high = Job("high", priority=JobPriority.HIGH)
        normal = Job("normal", priority=JobPriority.NORMAL)
        q.push(low)
        q.push(high)
        q.push(normal)
        assert q.pop().name == "high"
        assert q.pop().name == "normal"
        assert q.pop().name == "low"

    def test_fifo_within_same_priority(self):
        q = JobQueue()
        j1 = Job("first", priority=JobPriority.NORMAL)
        j2 = Job("second", priority=JobPriority.NORMAL)
        q.push(j1)
        q.push(j2)
        assert q.pop().name == "first"
        assert q.pop().name == "second"

    def test_remove(self):
        q = JobQueue()
        job = Job("j")
        q.push(job)
        assert q.remove(job.id) is True
        assert len(q) == 0

    def test_remove_nonexistent(self):
        q = JobQueue()
        assert q.remove("nonexistent") is False

    def test_get(self):
        q = JobQueue()
        job = Job("j")
        q.push(job)
        assert q.get(job.id) is job

    def test_get_nonexistent(self):
        q = JobQueue()
        assert q.get("nonexistent") is None

    def test_len(self):
        q = JobQueue()
        assert len(q) == 0
        q.push(Job("a"))
        q.push(Job("b"))
        assert len(q) == 2

    def test_is_empty(self):
        q = JobQueue()
        assert q.is_empty is True
        q.push(Job("a"))
        assert q.is_empty is False

    def test_list_all(self):
        q = JobQueue()
        q.push(Job("a"))
        q.push(Job("b"))
        jobs = q.list()
        assert len(jobs) == 2

    def test_list_by_status(self):
        q = JobQueue()
        j1 = Job("a")
        j2 = Job("b")
        q.push(j1)
        q.push(j2)
        queued = q.list(status=JobState.QUEUED)
        assert len(queued) == 2

    def test_push_transitions_to_queued(self):
        q = JobQueue()
        job = Job("j")
        q.push(job)
        assert job.status == JobState.QUEUED


class TestRuntimeSubmit:
    """Tests for Runtime job submission."""

    def setup_method(self):
        self.bus = EventBus()
        self.runtime = Runtime(self.bus)

    def test_submit_returns_job_id(self):
        job = Job("j")
        job_id = self.runtime.submit(job)
        assert job_id == job.id

    def test_submit_transitions_to_queued(self):
        job = Job("j")
        self.runtime.submit(job)
        assert job.status == JobState.QUEUED

    def test_submit_adds_to_queue(self):
        job = Job("j")
        self.runtime.submit(job)
        assert len(self.runtime.queue) == 1

    def test_submit_publishes_event(self):
        events = []
        self.bus.subscribe("task.created", lambda e: events.append(e))
        job = Job("j")
        self.runtime.submit(job)
        assert len(events) == 1
        assert events[0].data["job_id"] == job.id

    def test_submit_increments_stats(self):
        job = Job("j")
        self.runtime.submit(job)
        stats = self.runtime.get_stats()
        assert stats["jobs_queued"] == 1


class TestRuntimeWorkerRegistration:
    """Tests for worker registration."""

    def setup_method(self):
        self.bus = EventBus()
        self.store = ArtifactStore()
        self.runtime = Runtime(self.bus)

    def test_register_worker(self):
        worker = StubWorker(self.bus, self.store)
        self.runtime.register_worker(worker)
        assert "stub" in self.runtime.list_workers()

    def test_get_worker(self):
        worker = StubWorker(self.bus, self.store)
        self.runtime.register_worker(worker)
        assert self.runtime.get_worker("stub") is worker

    def test_get_worker_not_found(self):
        assert self.runtime.get_worker("nonexistent") is None

    def test_list_workers(self):
        worker = StubWorker(self.bus, self.store)
        self.runtime.register_worker(worker)
        workers = self.runtime.list_workers()
        assert workers == ["stub"]


class TestRuntimeJobExecution:
    """Tests for job execution flow through the runtime."""

    def setup_method(self):
        self.bus = EventBus()
        self.store = ArtifactStore()
        self.runtime = Runtime(self.bus, default_timeout=5.0)

    def test_execute_single_step_job(self):
        worker = StubWorker(self.bus, self.store)
        self.runtime.register_worker(worker)
        job = Job("j")
        job.add_step("s1", "stub")
        self.runtime.submit(job)
        self.runtime._execute_job(job)
        assert job.status == JobState.COMPLETED
        assert job.steps[0].status == StepState.COMPLETED

    def test_execute_multi_step_job(self):
        worker = StubWorker(self.bus, self.store)
        self.runtime.register_worker(worker)
        job = Job("j")
        job.add_step("s1", "stub")
        job.add_step("s2", "stub")
        self.runtime.submit(job)
        self.runtime._execute_job(job)
        assert job.status == JobState.COMPLETED
        assert all(s.status == StepState.COMPLETED for s in job.steps)

    def test_execute_step_without_worker_fails(self):
        job = Job("j")
        job.add_step("s1", "unknown_worker")
        self.runtime.submit(job)
        self.runtime._execute_job(job)
        assert job.status == JobState.FAILED
        assert job.steps[0].status == StepState.FAILED
        assert "No worker registered" in job.steps[0].error

    def test_execute_failing_worker(self):
        worker = StubWorker(self.bus, self.store, should_fail=True)
        self.runtime.register_worker(worker)
        job = Job("j")
        job.add_step("s1", "stub")
        self.runtime.submit(job)
        self.runtime._execute_job(job)
        assert job.status == JobState.FAILED
        assert job.steps[0].status == StepState.FAILED
        assert job.steps[0].error == "stub failure"

    def test_execute_step_publishes_events(self):
        events = []
        self.bus.subscribe("step.started", lambda e: events.append("started"))
        self.bus.subscribe("step.completed", lambda e: events.append("completed"))
        worker = StubWorker(self.bus, self.store)
        self.runtime.register_worker(worker)
        job = Job("j")
        job.add_step("s1", "stub")
        self.runtime.submit(job)
        self.runtime._execute_job(job)
        assert "started" in events
        assert "completed" in events

    def test_execute_step_sets_timing(self):
        worker = StubWorker(self.bus, self.store)
        self.runtime.register_worker(worker)
        job = Job("j")
        job.add_step("s1", "stub")
        self.runtime.submit(job)
        self.runtime._execute_job(job)
        step = job.steps[0]
        assert step.started is not None
        assert step.completed is not None
        assert step.duration >= 0

    def test_worker_handle_is_called(self):
        worker = StubWorker(self.bus, self.store)
        self.runtime.register_worker(worker)
        job = Job("j")
        step = job.add_step("s1", "stub")
        self.runtime.submit(job)
        self.runtime._execute_job(job)
        assert len(worker.handle_calls) == 1
        assert worker.handle_calls[0][0] == job.id

    def test_skip_completed_steps_on_resume(self):
        worker = StubWorker(self.bus, self.store)
        self.runtime.register_worker(worker)
        job = Job("j")
        s1 = job.add_step("s1", "stub")
        s2 = job.add_step("s2", "stub")
        s1._state.transition_to(StepState.QUEUED)
        s1._state.transition_to(StepState.RUNNING)
        s1._state.transition_to(StepState.COMPLETED)
        job.started_at = time.time()
        self.runtime.submit(job)
        self.runtime._execute_job(job)
        assert worker.handle_calls == [(job.id, s2.id)]

    def test_finalize_marks_duration(self):
        worker = StubWorker(self.bus, self.store)
        self.runtime.register_worker(worker)
        job = Job("j")
        job.add_step("s1", "stub")
        self.runtime.submit(job)
        self.runtime._execute_job(job)
        assert job.completed_at is not None
        assert job.duration >= 0


class TestRuntimeStats:
    """Tests for runtime statistics."""

    def setup_method(self):
        self.bus = EventBus()
        self.store = ArtifactStore()
        self.runtime = Runtime(self.bus)

    def test_stats_initial(self):
        stats = self.runtime.get_stats()
        assert stats["jobs_queued"] == 0
        assert stats["jobs_started"] == 0
        assert stats["jobs_completed"] == 0
        assert stats["jobs_failed"] == 0
        assert stats["active_jobs"] == 0
        assert stats["queued_jobs"] == 0
        assert stats["registered_workers"] == 0

    def test_stats_after_execution(self):
        worker = StubWorker(self.bus, self.store)
        self.runtime.register_worker(worker)
        job = Job("j")
        job.add_step("s1", "stub")
        self.runtime.submit(job)
        self.runtime._execute_job(job)
        stats = self.runtime.get_stats()
        assert stats["jobs_started"] == 1
        assert stats["jobs_completed"] == 1

    def test_stats_worker_types(self):
        worker = StubWorker(self.bus, self.store)
        self.runtime.register_worker(worker)
        stats = self.runtime.get_stats()
        assert "stub" in stats["worker_types"]


class TestRuntimeCancellation:
    """Tests for job cancellation."""

    def setup_method(self):
        self.bus = EventBus()
        self.store = ArtifactStore()
        self.runtime = Runtime(self.bus)

    def test_cancel_queued_job(self):
        job = Job("j")
        self.runtime.submit(job)
        assert self.runtime.cancel(job.id) is True
        assert job.status == JobState.CANCELLED

    def test_cancel_nonexistent(self):
        assert self.runtime.cancel("nonexistent") is False

    def test_cancel_publishes_event(self):
        events = []
        self.bus.subscribe("job.cancelled", lambda e: events.append(e))
        job = Job("j")
        self.runtime.submit(job)
        self.runtime.cancel(job.id)
        assert len(events) == 1

    def test_cancelled_job_not_completed(self):
        worker = StubWorker(self.bus, self.store)
        self.runtime.register_worker(worker)
        job = Job("j")
        job.add_step("s1", "stub")
        self.runtime.submit(job)
        self.runtime.cancel(job.id)
        self.runtime._execute_job(job)
        assert job.status != JobState.COMPLETED


class TestRuntimeGetStatus:
    """Tests for get_status method."""

    def setup_method(self):
        self.bus = EventBus()
        self.store = ArtifactStore()
        self.runtime = Runtime(self.bus)

    def test_get_status_queued(self):
        job = Job("j")
        job.add_step("s1")
        self.runtime.submit(job)
        status = self.runtime.get_status(job.id)
        assert status is not None
        assert status["id"] == job.id
        assert status["name"] == "j"

    def test_get_status_nonexistent(self):
        assert self.runtime.get_status("nonexistent") is None

    def test_get_status_completed(self):
        worker = StubWorker(self.bus, self.store)
        self.runtime.register_worker(worker)
        job = Job("j")
        job.add_step("s1", "stub")
        self.runtime.submit(job)
        self.runtime._execute_job(job)
        status = self.runtime.get_status(job.id)
        assert status is not None
        assert status["status"] == "completed"


class TestRuntimeEventTracking:
    """Tests for event publishing during execution."""

    def setup_method(self):
        self.bus = EventBus()
        self.store = ArtifactStore()
        self.runtime = Runtime(self.bus)

    def test_job_finished_event_published(self):
        events = []
        self.bus.subscribe("job.finished", lambda e: events.append(e))
        worker = StubWorker(self.bus, self.store)
        self.runtime.register_worker(worker)
        job = Job("j")
        job.add_step("s1", "stub")
        self.runtime.submit(job)
        self.runtime._execute_job(job)
        assert len(events) == 1
        assert events[0].data["job_id"] == job.id

    def test_job_failed_event_published(self):
        events = []
        self.bus.subscribe("job.failed", lambda e: events.append(e))
        worker = StubWorker(self.bus, self.store, should_fail=True)
        self.runtime.register_worker(worker)
        job = Job("j")
        job.add_step("s1", "stub")
        self.runtime.submit(job)
        self.runtime._execute_job(job)
        assert len(events) == 1

    def test_step_started_event_published(self):
        events = []
        self.bus.subscribe("step.started", lambda e: events.append(e))
        worker = StubWorker(self.bus, self.store)
        self.runtime.register_worker(worker)
        job = Job("j")
        job.add_step("s1", "stub")
        self.runtime.submit(job)
        self.runtime._execute_job(job)
        assert len(events) >= 1
        assert events[0].data["step_name"] == "s1"


class TestRuntimeActiveJobs:
    """Tests for active job tracking."""

    def setup_method(self):
        self.bus = EventBus()
        self.store = ArtifactStore()
        self.runtime = Runtime(self.bus)

    def test_active_jobs_empty(self):
        assert self.runtime.get_active_jobs() == []
