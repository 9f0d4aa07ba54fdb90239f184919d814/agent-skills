"""
KERNEL — Event-driven AI agent platform.

The kernel is the brain of the system. Everything communicates through events.
Nothing talks directly to anything else.

Core components:
  - EventBus: Publish/subscribe event system
  - Job: Unit of work with steps, context, artifacts, metrics
  - StateMachine: Formal job lifecycle with validated transitions
  - CommandBus: Directed worker instructions
  - TaskGraph: DAG-based parallel task execution
  - VersionedContext: Immutable context snapshots
  - CapabilityRegistry: Domain-organized tool/worker registry
  - Artifact: Immutable records of work done
  - Worker: Base class for all processing units
  - Runtime: Execution engine (queue, scheduler, workers, retry, timeout)
  - Kernel: Central orchestrator
  - Monitor: Self-monitoring and dashboards
"""

from .event_bus import EventBus, Event, EventPriority, \
    EVT_TASK_CREATED, EVT_CONTEXT_BUILT, EVT_PLAN_CREATED, \
    EVT_STEP_STARTED, EVT_STEP_COMPLETED, EVT_STEP_FAILED, \
    EVT_WORKER_STARTED, EVT_WORKER_COMPLETED, EVT_WORKER_FAILED, \
    EVT_VERIFICATION_STARTED, EVT_VERIFICATION_PASSED, EVT_VERIFICATION_FAILED, \
    EVT_JOB_FINISHED, EVT_JOB_FAILED, EVT_JOB_CANCELLED, EVT_ERROR
from .job import Job, JobStep, JobPriority
from .state_machine import StateMachine, JobState, StepStateMachine, StepState
from .commands import CommandBus, Command, CommandStatus
from .task_graph import TaskGraph, TaskNode
from .context import VersionedContext, ContextSnapshot
from .capabilities import CapabilityRegistry, Capability
from .artifact import Artifact, ArtifactType, ArtifactStore
from .worker import BaseWorker
from .runtime import Runtime, JobQueue
from .kernel import Kernel
from .monitor import SystemMonitor, MetricsStore, WorkerTelemetry

__all__ = [
    # Event Bus
    "EventBus", "Event", "EventPriority",
    "EVT_TASK_CREATED", "EVT_CONTEXT_BUILT", "EVT_PLAN_CREATED",
    "EVT_STEP_STARTED", "EVT_STEP_COMPLETED", "EVT_STEP_FAILED",
    "EVT_WORKER_STARTED", "EVT_WORKER_COMPLETED", "EVT_WORKER_FAILED",
    "EVT_VERIFICATION_STARTED", "EVT_VERIFICATION_PASSED", "EVT_VERIFICATION_FAILED",
    "EVT_JOB_FINISHED", "EVT_JOB_FAILED", "EVT_JOB_CANCELLED", "EVT_ERROR",
    # Job System
    "Job", "JobStep", "JobPriority",
    # State Machine
    "StateMachine", "JobState", "StepStateMachine", "StepState",
    # Command Bus
    "CommandBus", "Command", "CommandStatus",
    # Task Graph
    "TaskGraph", "TaskNode",
    # Versioned Context
    "VersionedContext", "ContextSnapshot",
    # Capability Registry
    "CapabilityRegistry", "Capability",
    # Artifact System
    "Artifact", "ArtifactType", "ArtifactStore",
    # Worker
    "BaseWorker",
    # Runtime
    "Runtime", "JobQueue",
    # Kernel
    "Kernel",
    # Monitor
    "SystemMonitor", "MetricsStore", "WorkerTelemetry",
]
