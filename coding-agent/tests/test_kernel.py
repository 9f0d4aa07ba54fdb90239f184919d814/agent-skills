"""Tests for Kernel — central orchestrator."""

import pytest
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from kernel.kernel import Kernel
from kernel.event_bus import EventBus, Event
from kernel.job import Job, JobStep, JobPriority
from kernel.state_machine import JobState, StepState
from kernel.worker import BaseWorker
from kernel.artifact import ArtifactStore
from kernel.runtime import Runtime


class StubWorker(BaseWorker):
    """Minimal worker for testing."""

    def __init__(self, event_bus, artifact_store, should_fail=False):
        super().__init__("stub", "StubWorker", event_bus, artifact_store)
        self.should_fail = should_fail

    def handle(self, job, step):
        if self.should_fail:
            raise RuntimeError("worker error")
        return {"status": "ok"}


class TestKernelInitialization:
    """Tests for Kernel creation and initialization."""

    def test_kernel_creation(self):
        kernel = Kernel(workdir=".")
        assert kernel.workdir is not None
        assert isinstance(kernel.event_bus, EventBus)
        assert isinstance(kernel.artifacts, ArtifactStore)
        assert isinstance(kernel.runtime, Runtime)

    def test_kernel_initial_state(self):
        kernel = Kernel()
        assert kernel._initialized is False
        assert kernel._job_history == []

    def test_kernel_stats_initialized(self):
        kernel = Kernel()
        stats = kernel.get_kernel_stats()
        assert "kernel" in stats
        assert "runtime" in stats
        assert "event_bus" in stats

    def test_kernel_workdir_resolved(self):
        kernel = Kernel(workdir=".")
        from pathlib import Path
        assert Path(kernel.workdir).is_absolute()

    def test_kernel_initializes(self):
        kernel = Kernel()
        kernel.initialize()
        assert kernel._initialized is True
        kernel.shutdown()

    def test_kernel_shutdown(self):
        kernel = Kernel()
        kernel.initialize()
        kernel.shutdown()
        assert kernel._initialized is False

    def test_kernel_initialize_idempotent(self):
        kernel = Kernel()
        kernel.initialize()
        kernel.initialize()
        assert kernel._initialized is True
        kernel.shutdown()


class TestKernelEventListeners:
    """Tests for internal event listeners set up in __init__."""

    def test_setup_listeners_subscribes_to_job_events(self):
        kernel = Kernel()
        stats = kernel.event_bus.get_stats()
        assert stats["total_subscribers"] >= 4

    def test_on_job_finished_increments_stats(self):
        kernel = Kernel()
        event = Event("job.finished", data={"duration": 1.0})
        kernel._on_job_finished(event)
        assert kernel._stats["jobs_completed"] == 1
        assert kernel._stats["total_duration"] == 1.0

    def test_on_job_failed_increments_stats(self):
        kernel = Kernel()
        event = Event("job.failed")
        kernel._on_job_failed(event)
        assert kernel._stats["jobs_failed"] == 1

    def test_on_error_increments_stats(self):
        kernel = Kernel()
        event = Event("system.error")
        kernel._on_error(event)
        assert kernel._stats["errors"] == 1


class TestKernelWorkerRegistration:
    """Tests for worker registration through kernel."""

    def setup_method(self):
        self.kernel = Kernel()

    def test_register_worker(self):
        worker = StubWorker(self.kernel.event_bus, self.kernel.artifacts)
        self.kernel.register_worker(worker)
        assert "stub" in self.kernel.list_workers()

    def test_get_worker(self):
        worker = StubWorker(self.kernel.event_bus, self.kernel.artifacts)
        self.kernel.register_worker(worker)
        w = self.kernel.get_worker("stub")
        assert w is worker

    def test_get_worker_not_found(self):
        assert self.kernel.get_worker("nonexistent") is None

    def test_list_workers_empty(self):
        assert self.kernel.list_workers() == []

    def test_register_worker_publishes_log_event(self):
        events = []
        self.kernel.event_bus.subscribe("system.log", lambda e: events.append(e))
        worker = StubWorker(self.kernel.event_bus, self.kernel.artifacts)
        self.kernel.register_worker(worker)
        assert any("Worker registered" in e.data.get("message", "") for e in events)

    def test_register_worker_registers_capability(self):
        worker = StubWorker(self.kernel.event_bus, self.kernel.artifacts)
        self.kernel.register_worker(worker)
        caps = self.kernel.capabilities.domains
        assert "worker" in caps


class TestKernelProcessTask:
    """Tests for process_task and process_task_async."""

    def setup_method(self):
        self.kernel = Kernel()

    def test_process_task_creates_job(self):
        worker = StubWorker(self.kernel.event_bus, self.kernel.artifacts)
        self.kernel.register_worker(worker)
        result = self.kernel.process_task("Do something")
        assert result is not None
        assert "job_id" in result or "status" in result

    def test_process_task_async_returns_job_id(self):
        worker = StubWorker(self.kernel.event_bus, self.kernel.artifacts)
        self.kernel.register_worker(worker)
        job_id = self.kernel.process_task_async("Do something async")
        assert job_id is not None
        assert isinstance(job_id, str)

    def test_process_task_increments_stats(self):
        worker = StubWorker(self.kernel.event_bus, self.kernel.artifacts)
        self.kernel.register_worker(worker)
        self.kernel.process_task("test task")
        assert self.kernel._stats["tasks_received"] == 1
        assert self.kernel._stats["jobs_created"] >= 1

    def test_process_task_adds_standard_steps(self):
        worker = StubWorker(self.kernel.event_bus, self.kernel.artifacts)
        self.kernel.register_worker(worker)
        self.kernel.process_task("test task")
        history = self.kernel._job_history
        assert len(history) >= 1
        job = history[-1]
        assert len(job.steps) == 5
        step_names = [s.name for s in job.steps]
        assert "Discover Context" in step_names
        assert "Plan" in step_names
        assert "Execute" in step_names
        assert "Verify" in step_names
        assert "Review" in step_names

    def test_process_task_with_context(self):
        worker = StubWorker(self.kernel.event_bus, self.kernel.artifacts)
        self.kernel.register_worker(worker)
        self.kernel.process_task("task", context={"custom_key": "val"})
        job = self.kernel._job_history[-1]
        assert job.context.get("custom_key") == "val"


class TestKernelAddStandardSteps:
    """Tests for _add_standard_steps."""

    def test_standard_steps_count(self):
        kernel = Kernel()
        job = Job("j")
        kernel._add_standard_steps(job, "task")
        assert len(job.steps) == 5

    def test_standard_steps_worker_types(self):
        kernel = Kernel()
        job = Job("j")
        kernel._add_standard_steps(job, "task")
        types = [s.worker_type for s in job.steps]
        assert "context" in types
        assert "planner" in types
        assert "executor" in types
        assert "verifier" in types
        assert "reviewer" in types


class TestKernelFindJob:
    """Tests for _find_job method."""

    def test_find_job_in_history(self):
        kernel = Kernel()
        job = Job("j")
        kernel._job_history.append(job)
        found = kernel._find_job(job.id)
        assert found is job

    def test_find_job_not_found(self):
        kernel = Kernel()
        assert kernel._find_job("nonexistent") is None


class TestKernelGetEventHistory:
    """Tests for get_event_history."""

    def test_event_history_empty(self):
        kernel = Kernel()
        history = kernel.get_event_history()
        assert isinstance(history, list)

    def test_event_history_after_publish(self):
        kernel = Kernel()
        kernel.event_bus.publish("test.event", source="test", data={"key": "val"})
        history = kernel.get_event_history(event_type="test.event")
        assert len(history) == 1
        assert history[0]["type"] == "test.event"
        assert history[0]["source"] == "test"

    def test_event_history_limit(self):
        kernel = Kernel()
        for i in range(5):
            kernel.event_bus.publish(f"event.{i}")
        history = kernel.get_event_history(limit=3)
        assert len(history) == 3

    def test_event_history_structure(self):
        kernel = Kernel()
        kernel.event_bus.publish("test", source="s", data={"d": 1})
        history = kernel.get_event_history()
        assert len(history) >= 1
        entry = history[-1]
        assert "id" in entry
        assert "type" in entry
        assert "source" in entry
        assert "data" in entry
        assert "time" in entry
        assert "consumed_by" in entry


class TestKernelListJobs:
    """Tests for list_jobs."""

    def test_list_jobs_empty(self):
        kernel = Kernel()
        assert kernel.list_jobs() == []

    def test_list_jobs_after_task(self):
        kernel = Kernel()
        worker = StubWorker(kernel.event_bus, kernel.artifacts)
        kernel.register_worker(worker)
        kernel.process_task("task1")
        jobs = kernel.list_jobs()
        assert len(jobs) >= 1

    def test_list_jobs_filter_by_status(self):
        kernel = Kernel()
        worker = StubWorker(kernel.event_bus, kernel.artifacts)
        kernel.register_worker(worker)
        kernel.process_task("task1")
        completed = kernel.list_jobs(status="completed")
        assert all(j["state"] == "completed" for j in completed)


class TestKernelGetJobResult:
    """Tests for get_job_result."""

    def test_get_job_result_not_found(self):
        kernel = Kernel()
        assert kernel.get_job_result("nonexistent") is None


class TestKernelGetSnapshot:
    """Tests for get_snapshot."""

    def test_snapshot_structure(self):
        kernel = Kernel()
        snapshot = kernel.get_snapshot()
        assert "kernel_stats" in snapshot
        assert "active_jobs" in snapshot
        assert "queued_jobs" in snapshot
        assert "workers" in snapshot
        assert "recent_events" in snapshot

    def test_snapshot_kernel_stats(self):
        kernel = Kernel()
        snapshot = kernel.get_snapshot()
        ks = snapshot["kernel_stats"]
        assert "kernel" in ks
        assert "runtime" in ks
        assert "event_bus" in ks
        assert "initialized" in ks
        assert "workdir" in ks


class TestKernelGetKernelStats:
    """Tests for get_kernel_stats."""

    def test_stats_structure(self):
        kernel = Kernel()
        stats = kernel.get_kernel_stats()
        assert "kernel" in stats
        assert "runtime" in stats
        assert "scheduler" in stats
        assert "resource_manager" in stats
        assert "event_bus" in stats

    def test_kernel_stats_values(self):
        kernel = Kernel()
        stats = kernel.get_kernel_stats()
        ks = stats["kernel"]
        assert ks["tasks_received"] == 0
        assert ks["jobs_created"] == 0
        assert ks["errors"] == 0


class TestKernelSchedulerIntegration:
    """Tests for scheduler integration."""

    def test_schedule_job(self):
        kernel = Kernel()
        result = kernel.schedule_job(
            job_id="test-job",
            name="Test Job",
            handler=lambda jid, meta: {"ok": True},
        )
        assert result is True

    def test_get_scheduler_status(self):
        kernel = Kernel()
        kernel.schedule_job(
            job_id="j1", name="J1",
            handler=lambda jid, meta: {},
        )
        status = kernel.get_scheduler_status("j1")
        assert status is not None

    def test_get_scheduler_status_all(self):
        kernel = Kernel()
        all_status = kernel.get_scheduler_status()
        assert isinstance(all_status, list)


class TestKernelResourceIntegration:
    """Tests for resource manager integration."""

    def test_get_resource_summary(self):
        kernel = Kernel()
        summary = kernel.get_resource_summary()
        assert isinstance(summary, str)
        assert "CPU" in summary or "Memory" in summary


class TestKernelEndToEnd:
    """End-to-end tests combining multiple components."""

    def test_full_lifecycle_with_worker(self):
        kernel = Kernel()
        worker = StubWorker(kernel.event_bus, kernel.artifacts)
        kernel.register_worker(worker)

        result = kernel.process_task("Fix the bug")
        assert result["status"] == "completed"

    def test_full_lifecycle_async(self):
        kernel = Kernel()
        worker = StubWorker(kernel.event_bus, kernel.artifacts)
        kernel.register_worker(worker)

        job_id = kernel.process_task_async("Do something")
        result = kernel.get_job_result(job_id)
        assert result is not None

    def test_shutdown_stops_runtime(self):
        kernel = Kernel()
        kernel.initialize()
        kernel.shutdown()
        assert kernel._initialized is False

    def test_event_history_populated_after_lifecycle(self):
        kernel = Kernel()
        worker = StubWorker(kernel.event_bus, kernel.artifacts)
        kernel.register_worker(worker)
        kernel.process_task("task")
        history = kernel.get_event_history()
        assert len(history) > 0
