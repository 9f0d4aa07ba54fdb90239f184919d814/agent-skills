"""Tests for Job system — Job, JobStep, JobPriority."""

import pytest
import sys
import json
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from kernel.job import Job, JobStep, JobPriority
from kernel.state_machine import JobState, StepState


class TestJobPriority:
    """Tests for JobPriority enum."""

    def test_priority_values(self):
        assert JobPriority.LOW.value == 1
        assert JobPriority.NORMAL.value == 2
        assert JobPriority.HIGH.value == 3
        assert JobPriority.CRITICAL.value == 4

    def test_priority_ordering(self):
        assert JobPriority.LOW.value < JobPriority.NORMAL.value < JobPriority.HIGH.value < JobPriority.CRITICAL.value


class TestJobStep:
    """Tests for JobStep creation and lifecycle."""

    def test_step_creation(self):
        step = JobStep("test_step", worker_type="executor", params={"key": "val"})
        assert step.name == "test_step"
        assert step.worker_type == "executor"
        assert step.params == {"key": "val"}
        assert step.description == "test_step"
        assert step.id is not None
        assert step.status == StepState.PENDING

    def test_step_creation_with_description(self):
        step = JobStep("s", description="my description")
        assert step.description == "my description"

    def test_step_initial_state(self):
        step = JobStep("s")
        assert step.status == StepState.PENDING
        assert step.started is None
        assert step.completed is None
        assert step.duration == 0.0
        assert step.result == {}
        assert step.error == ""
        assert step.artifacts == []

    def test_step_status_setter_string(self):
        step = JobStep("s")
        step._state.transition_to(StepState.QUEUED)
        step._state.transition_to(StepState.RUNNING)
        assert step.status == StepState.RUNNING

    def test_step_status_setter_enum(self):
        step = JobStep("s")
        step._state.transition_to(StepState.QUEUED)
        step._state.transition_to(StepState.RUNNING)
        step._state.transition_to(StepState.COMPLETED)
        assert step.status == StepState.COMPLETED

    def test_step_status_setter_invalid_ignored(self):
        step = JobStep("s")
        original = step.status
        step.status = "bogus_value"
        assert step.status == original

    def test_step_to_dict(self):
        step = JobStep("s", worker_type="w", params={"a": 1}, description="desc")
        d = step.to_dict()
        assert d["name"] == "s"
        assert d["worker_type"] == "w"
        assert d["params"] == {"a": 1}
        assert d["description"] == "desc"
        assert d["status"] == "pending"
        assert "id" in d

    def test_step_id_is_unique(self):
        s1 = JobStep("s")
        time.sleep(0.001)
        s2 = JobStep("s")
        assert s1.id != s2.id


class TestJob:
    """Tests for Job creation and all features."""

    def test_job_creation_defaults(self):
        job = Job("my_job")
        assert job.name == "my_job"
        assert job.description == "my_job"
        assert job.priority == JobPriority.NORMAL
        assert job.deadline == 0.0
        assert job.tags == []
        assert job.status == JobState.CREATED

    def test_job_creation_with_params(self):
        job = Job("j", description="desc", priority=JobPriority.HIGH,
                  deadline=100.0, tags=["t1", "t2"])
        assert job.description == "desc"
        assert job.priority == JobPriority.HIGH
        assert job.deadline == 100.0
        assert job.tags == ["t1", "t2"]

    def test_job_id_is_unique(self):
        j1 = Job("j")
        time.sleep(0.001)
        j2 = Job("j")
        assert j1.id != j2.id

    def test_job_initial_enriched_fields(self):
        job = Job("j")
        assert job.goal == ""
        assert job.intent == ""
        assert job.plan == {}
        assert job.cost == 0.0
        assert job.models_used == []
        assert job.workers_used == []
        assert job.history == []
        assert job.result == {}
        assert job.error == ""
        assert job.source == ""
        assert job.parent_job_id == ""

    def test_job_metrics_initialized(self):
        job = Job("j")
        assert job.metrics["tokens_used"] == 0
        assert job.metrics["llm_calls"] == 0
        assert job.metrics["tool_calls"] == 0
        assert job.metrics["commands_dispatched"] == 0
        assert job.metrics["errors"] == 0
        assert job.metrics["retries"] == 0

    def test_job_context_initialized(self):
        job = Job("j")
        assert job.context["task"] == ""
        assert job.context["goal"] == ""
        assert job.context["files"] == []
        assert job.context["requirements"] == []
        assert job.context["version"] == 1

    def test_job_timing(self):
        before = time.time()
        job = Job("j")
        after = time.time()
        assert before <= job.created_at <= after
        assert job.started_at is None
        assert job.completed_at is None
        assert job.duration == 0.0


class TestJobStateManagement:
    """Tests for Job state transitions."""

    def test_initial_state(self):
        job = Job("j")
        assert job.status == JobState.CREATED

    def test_status_setter_string(self):
        job = Job("j")
        job.status = "queued"
        assert job.status == JobState.QUEUED

    def test_status_setter_enum(self):
        job = Job("j")
        job.status = JobState.QUEUED
        assert job.status == JobState.QUEUED

    def test_status_setter_invalid_ignored(self):
        job = Job("j")
        job.status = "invalid_state"
        assert job.status == JobState.CREATED

    def test_transition_to(self):
        job = Job("j")
        job.transition_to(JobState.QUEUED)
        assert job.status == JobState.QUEUED

    def test_transition_to_with_reason(self):
        job = Job("j")
        job.transition_to(JobState.QUEUED, "user submitted")
        history = job.state_history()
        assert len(history) == 1
        assert history[0]["reason"] == "user submitted"

    def test_can_transition_to(self):
        job = Job("j")
        assert job.can_transition_to(JobState.QUEUED) is True
        assert job.can_transition_to(JobState.COMPLETED) is False

    def test_state_history(self):
        job = Job("j")
        job.transition_to(JobState.QUEUED)
        job.transition_to(JobState.PLANNING)
        history = job.state_history()
        assert len(history) == 2
        assert history[0]["from"] == "created"
        assert history[0]["to"] == "queued"


class TestJobGoalIntent:
    """Tests for goal and intent setting."""

    def test_set_goal(self):
        job = Job("j")
        job.set_goal("Fix the bug")
        assert job.goal == "Fix the bug"
        assert job.context["goal"] == "Fix the bug"

    def test_set_intent(self):
        job = Job("j")
        job.set_intent("Improve performance")
        assert job.intent == "Improve performance"


class TestJobStepManagement:
    """Tests for adding, getting, and querying steps."""

    def setup_method(self):
        self.job = Job("j")

    def test_add_step(self):
        step = self.job.add_step("step1", "executor", {"task": "do stuff"})
        assert step.name == "step1"
        assert step.worker_type == "executor"
        assert len(self.job.steps) == 1

    def test_add_step_returns_job_step(self):
        step = self.job.add_step("s")
        assert isinstance(step, JobStep)

    def test_get_step_by_id(self):
        step = self.job.add_step("s")
        found = self.job.get_step(step.id)
        assert found is step

    def test_get_step_not_found(self):
        assert self.job.get_step("nonexistent") is None

    def test_get_step_by_name(self):
        self.job.add_step("find_me")
        found = self.job.get_step_by_name("find_me")
        assert found.name == "find_me"

    def test_get_step_by_name_not_found(self):
        assert self.job.get_step_by_name("nope") is None

    def test_get_current_step_when_no_steps(self):
        assert self.job.get_current_step() is None

    def test_get_current_step_pending(self):
        self.job.add_step("s1")
        current = self.job.get_current_step()
        assert current.name == "s1"

    def test_get_current_step_running_takes_priority(self):
        s1 = self.job.add_step("s1")
        s2 = self.job.add_step("s2")
        s2._state.transition_to(StepState.QUEUED)
        s2._state.transition_to(StepState.RUNNING)
        current = self.job.get_current_step()
        assert current.name == "s2"

    def test_add_step_with_dependency(self):
        s1 = self.job.add_step("dep")
        s2 = self.job.add_step_with_dependency("child", "executor", "dep")
        assert s2.name == "child"
        deps = self.job.task_graph.get_dependencies(s2.id)
        assert len(deps) == 1
        assert deps[0].name == "dep"


class TestJobProgress:
    """Tests for progress calculation."""

    def test_progress_no_steps_not_completed(self):
        job = Job("j")
        assert job.progress == 0.0

    def test_progress_no_steps_completed(self):
        job = Job("j")
        job.transition_to(JobState.QUEUED)
        job.transition_to(JobState.PLANNING)
        job.transition_to(JobState.EXECUTING)
        job.transition_to(JobState.VERIFYING)
        job.transition_to(JobState.REVIEWING)
        job.transition_to(JobState.COMPLETED)
        assert job.progress == 1.0

    def test_progress_with_steps_none_completed(self):
        job = Job("j")
        job.add_step("s1")
        job.add_step("s2")
        assert job.progress == 0.0

    def test_progress_with_steps_half_completed(self):
        job = Job("j")
        s1 = job.add_step("s1")
        s2 = job.add_step("s2")
        s1._state.transition_to(StepState.QUEUED)
        s1._state.transition_to(StepState.RUNNING)
        s1._state.transition_to(StepState.COMPLETED)
        assert job.progress == 0.5

    def test_progress_with_steps_all_completed(self):
        job = Job("j")
        s1 = job.add_step("s1")
        s2 = job.add_step("s2")
        s1._state.transition_to(StepState.QUEUED)
        s1._state.transition_to(StepState.RUNNING)
        s1._state.transition_to(StepState.COMPLETED)
        s2._state.transition_to(StepState.QUEUED)
        s2._state.transition_to(StepState.RUNNING)
        s2._state.transition_to(StepState.COMPLETED)
        assert job.progress == 1.0


class TestJobContextManagement:
    """Tests for context management."""

    def test_update_context(self):
        job = Job("j")
        job.update_context("task", "fix bug")
        assert job.context["task"] == "fix bug"
        assert job.context["version"] == 2

    def test_update_context_records_worker(self):
        job = Job("j")
        job.update_context("key", "val", worker="planner")
        assert job.context["created_by"] == "planner"

    def test_update_context_increments_version(self):
        job = Job("j")
        job.update_context("k1", "v1")
        job.update_context("k2", "v2")
        assert job.context["version"] == 3

    def test_get_context_summary(self):
        job = Job("j")
        job.context["task"] = "Fix the login page"
        job.context["files"] = ["auth.py", "login.html"]
        summary = job.get_context_summary()
        assert "Fix the login page" in summary
        assert "auth.py" in summary

    def test_get_context_summary_max_length(self):
        job = Job("j")
        job.context["task"] = "x" * 200
        summary = job.get_context_summary(max_length=20)
        assert len(summary) <= 20


class TestJobCostTracking:
    """Tests for cost tracking."""

    def test_add_model_usage(self):
        job = Job("j")
        job.add_model_usage("gpt-4o", tokens=1000, cost=0.05)
        assert "gpt-4o" in job.models_used
        assert job.cost == 0.05
        assert job.metrics["tokens_used"] == 1000
        assert job.metrics["llm_calls"] == 1

    def test_add_model_usage_accumulates(self):
        job = Job("j")
        job.add_model_usage("gpt-4o", tokens=500, cost=0.02)
        job.add_model_usage("gpt-4o", tokens=500, cost=0.03)
        assert job.cost == 0.05
        assert job.metrics["tokens_used"] == 1000
        assert job.metrics["llm_calls"] == 2

    def test_add_model_usage_unique_models(self):
        job = Job("j")
        job.add_model_usage("gpt-4o", 100, 0.01)
        job.add_model_usage("claude-3", 100, 0.01)
        assert len(job.models_used) == 2

    def test_add_model_usage_no_duplicates(self):
        job = Job("j")
        job.add_model_usage("gpt-4o", 100, 0.01)
        job.add_model_usage("gpt-4o", 100, 0.01)
        assert job.models_used.count("gpt-4o") == 1

    def test_add_worker_usage(self):
        job = Job("j")
        job.add_worker_usage("executor")
        assert "executor" in job.workers_used

    def test_add_worker_usage_no_duplicates(self):
        job = Job("j")
        job.add_worker_usage("executor")
        job.add_worker_usage("executor")
        assert job.workers_used.count("executor") == 1


class TestJobHistory:
    """Tests for history and replay."""

    def test_add_history_entry(self):
        job = Job("j")
        job.add_history_entry("step_started", {"step": "s1"})
        assert len(job.history) == 1
        assert job.history[0]["type"] == "step_started"
        assert "data" in job.history[0]
        assert "timestamp" in job.history[0]
        assert "state" in job.history[0]

    def test_history_truncated_at_100(self):
        job = Job("j")
        for i in range(110):
            job.add_history_entry(f"event_{i}", {"i": i})
        assert len(job.history) == 100
        assert job.history[-1]["type"] == "event_109"

    def test_get_replay(self):
        job = Job("j")
        job.add_step("s1")
        job.add_history_entry("custom", {"key": "val"})
        replay = job.get_replay()
        assert isinstance(replay, list)
        assert len(replay) >= 2
        assert "state" in replay[0]
        assert "steps" in replay[0]
        assert "cost" in replay[0]


class TestJobSerialization:
    """Tests for to_dict and to_json."""

    def test_to_dict(self):
        job = Job("test_job", description="d", priority=JobPriority.HIGH, tags=["t1"])
        job.set_goal("fix things")
        job.set_intent("improve code")
        d = job.to_dict()
        assert d["name"] == "test_job"
        assert d["description"] == "d"
        assert d["priority"] == JobPriority.HIGH.value
        assert d["tags"] == ["t1"]
        assert d["goal"] == "fix things"
        assert d["intent"] == "improve code"
        assert d["state"] == "created"

    def test_to_dict_has_steps(self):
        job = Job("j")
        job.add_step("s1")
        d = job.to_dict()
        assert len(d["steps"]) == 1
        assert d["steps"][0]["name"] == "s1"

    def test_to_dict_has_task_graph(self):
        job = Job("j")
        d = job.to_dict()
        assert "task_graph" in d

    def test_to_json(self):
        job = Job("j")
        j = job.to_json()
        parsed = json.loads(j)
        assert parsed["name"] == "j"

    def test_to_json_with_steps(self):
        job = Job("j")
        job.add_step("s1")
        j = job.to_json()
        parsed = json.loads(j)
        assert len(parsed["steps"]) == 1


class TestJobStatusLine:
    """Tests for status_line method."""

    def test_status_line(self):
        job = Job("test_job")
        line = job.status_line()
        assert "CREATED" in line
        assert "test_job" in line
        assert "0%" in line
        assert "NORMAL" in line

    def test_status_line_with_steps(self):
        job = Job("j")
        s1 = job.add_step("s1")
        s1._state.transition_to(StepState.QUEUED)
        s1._state.transition_to(StepState.RUNNING)
        s1._state.transition_to(StepState.COMPLETED)
        line = job.status_line()
        assert "1/1" in line


class TestJobBackwardCompat:
    """Tests for backward-compatible status_old property."""

    def test_status_old_created(self):
        job = Job("j")
        old = job.status_old
        assert old.name == "PENDING"
        assert old.value == "pending"

    def test_status_old_executing(self):
        job = Job("j")
        job.transition_to(JobState.QUEUED)
        job.transition_to(JobState.PLANNING)
        job.transition_to(JobState.EXECUTING)
        assert job.status_old.name == "RUNNING"

    def test_status_old_completed(self):
        job = Job("j")
        job.transition_to(JobState.QUEUED)
        job.transition_to(JobState.PLANNING)
        job.transition_to(JobState.EXECUTING)
        job.transition_to(JobState.VERIFYING)
        job.transition_to(JobState.REVIEWING)
        job.transition_to(JobState.COMPLETED)
        assert job.status_old.name == "COMPLETED"

    def test_status_old_cancelled(self):
        job = Job("j")
        job.transition_to(JobState.QUEUED)
        job.transition_to(JobState.CANCELLED)
        assert job.status_old.name == "CANCELLED"

    def test_status_old_failed(self):
        job = Job("j")
        job.transition_to(JobState.QUEUED)
        job.transition_to(JobState.PLANNING)
        job.transition_to(JobState.FAILED)
        assert job.status_old.name == "FAILED"
