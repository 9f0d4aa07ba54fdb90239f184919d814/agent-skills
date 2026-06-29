"""
EVENT BUS — Publish/subscribe event system.
Every module communicates through events. Nothing talks directly to anything else.

Events flow through the bus:
  TaskCreated → ContextBuilt → PlanCreated → StepStarted
  → StepCompleted → VerificationPassed → JobFinished
"""

import inspect, json, time, traceback
from collections import defaultdict
from typing import Callable, Optional
from datetime import datetime
from enum import Enum, auto


class EventPriority(Enum):
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


class Event:
    """A single event flowing through the system."""

    def __init__(self, event_type: str, source: str = "",
                 data: dict = None, priority: EventPriority = EventPriority.NORMAL):
        self.id = f"evt-{int(time.time() * 1_000_000)}-{id(self)}"
        self.event_type = event_type
        self.source = source
        self.data = data or {}
        self.priority = priority
        self.timestamp = time.time()
        self.datetime = datetime.now().isoformat()
        self.propagated = False
        self.consumed_by: list[str] = []

    def __repr__(self):
        return (f"<Event '{self.event_type}' | priority={self.priority.name} "
                f"| source='{self.source}' | id={self.id[:16]}>")


# Standard event types used across the system
EVT_TASK_CREATED = "task.created"
EVT_CONTEXT_BUILT = "context.built"
EVT_PLAN_CREATED = "plan.created"
EVT_STEP_STARTED = "step.started"
EVT_STEP_COMPLETED = "step.completed"
EVT_STEP_FAILED = "step.failed"
EVT_ARTIFACT_CREATED = "artifact.created"
EVT_WORKER_STARTED = "worker.started"
EVT_WORKER_COMPLETED = "worker.completed"
EVT_WORKER_FAILED = "worker.failed"
EVT_VERIFICATION_STARTED = "verification.started"
EVT_VERIFICATION_PASSED = "verification.passed"
EVT_VERIFICATION_FAILED = "verification.failed"
EVT_JOB_FINISHED = "job.finished"
EVT_JOB_FAILED = "job.failed"
EVT_JOB_CANCELLED = "job.cancelled"
EVT_ERROR = "system.error"
EVT_LOG = "system.log"


class EventBus:
    """Publish/subscribe event bus.
    
    Modules subscribe to event types and are notified when events are published.
    The bus supports priority ordering, error isolation, and event history.
    """

    def __init__(self):
        self._subscribers: dict[str, list[dict]] = defaultdict(list)
        self._history: list[Event] = []
        self._max_history = 1000
        self._wildcard_subscribers: list[dict] = []
        self._stats = {
            "published": 0,
            "delivered": 0,
            "errors": 0,
            "dropped": 0,
        }

    # ── Subscription ──

    def subscribe(self, event_type: str, callback: Callable,
                  name: str = "", priority: int = 0) -> str:
        """Subscribe to an event type. Returns subscription ID for unsubscribe."""
        sub_id = f"sub-{event_type}-{int(time.time() * 1_000_000)}-{id(callback)}"
        self._subscribers[event_type].append({
            "id": sub_id,
            "callback": callback,
            "name": name or getattr(callback, "__name__", "unknown"),
            "priority": priority,
            "active": True,
        })
        # Sort subscribers by priority (higher = first)
        self._subscribers[event_type].sort(key=lambda s: s["priority"], reverse=True)
        return sub_id

    def subscribe_all(self, callback: Callable, name: str = "") -> str:
        """Subscribe to ALL events (wildcard)."""
        sub_id = f"sub-all-{int(time.time() * 1_000_000)}-{id(callback)}"
        self._wildcard_subscribers.append({
            "id": sub_id,
            "callback": callback,
            "name": name or getattr(callback, "__name__", "unknown"),
            "active": True,
        })
        return sub_id

    def unsubscribe(self, sub_id: str) -> bool:
        """Unsubscribe by subscription ID and remove from list."""
        # Remove from type-specific subscribers
        for event_type, subs in list(self._subscribers.items()):
            for i, sub in enumerate(subs):
                if sub["id"] == sub_id:
                    del subs[i]
                    if not subs:
                        del self._subscribers[event_type]
                    return True
        
        # Remove from wildcard subscribers
        for i, sub in enumerate(self._wildcard_subscribers):
            if sub["id"] == sub_id:
                del self._wildcard_subscribers[i]
                return True
        
        return False

    # ── Publishing ──

    def publish(self, event_type: str, source: str = "",
                data: dict = None, priority: EventPriority = EventPriority.NORMAL) -> Event:
        """Publish an event. Returns the Event object."""
        event = Event(event_type, source, data, priority)
        self._history.append(event)
        if len(self._history) > self._max_history:
            self._history.pop(0)
        self._stats["published"] += 1
        self._deliver(event)
        return event

    def publish_event(self, event: Event) -> Event:
        """Publish a pre-created Event object."""
        self._history.append(event)
        if len(self._history) > self._max_history:
            self._history.pop(0)
        self._stats["published"] += 1
        self._deliver(event)
        return event

    # ── Delivery ──

    def _deliver(self, event: Event):
        """Deliver event to all matching subscribers."""
        # Prune inactive subscribers periodically to prevent memory leak
        if self._stats["published"] % 100 == 0:
            self._prune_inactive_subscribers()
        
        # Deliver to type-specific subscribers
        for sub in self._subscribers.get(event.event_type, []):
            if sub["active"]:
                try:
                    sub["callback"](event)
                    event.consumed_by.append(sub["name"])
                    self._stats["delivered"] += 1
                except Exception as e:
                    self._stats["errors"] += 1
                    error_evt = Event(EVT_ERROR, "event_bus",
                                      {"error": str(e), "event": event.event_type,
                                       "subscriber": sub["name"],
                                       "traceback": traceback.format_exc()})
                    self._deliver_direct(error_evt)

        # Deliver to wildcard subscribers
        for sub in self._wildcard_subscribers:
            if sub["active"]:
                try:
                    sub["callback"](event)
                    event.consumed_by.append(f"*{sub['name']}")
                    self._stats["delivered"] += 1
                except Exception as e:
                    self._stats["errors"] += 1

        event.propagated = True

    def _prune_inactive_subscribers(self):
        """Remove inactive subscribers (called periodically to prevent memory leak)."""
        for event_type in list(self._subscribers.keys()):
            self._subscribers[event_type] = [
                sub for sub in self._subscribers[event_type]
                if sub.get("active", True)
            ]
            if not self._subscribers[event_type]:
                del self._subscribers[event_type]
        
        self._wildcard_subscribers = [
            sub for sub in self._wildcard_subscribers
            if sub.get("active", True)
        ]

    def _deliver_direct(self, event: Event):
        """Deliver an error/system event without recursion protection."""
        for sub in self._subscribers.get(event.event_type, []):
            if sub["active"]:
                try:
                    sub["callback"](event)
                except:
                    pass

    # ── Query ──

    def get_history(self, event_type: str = "", limit: int = 20) -> list[Event]:
        """Get recent events, optionally filtered by type."""
        if event_type:
            return [e for e in self._history if e.event_type == event_type][-limit:]
        return self._history[-limit:]

    def get_stats(self) -> dict:
        """Get event bus statistics."""
        counts = defaultdict(int)
        for e in self._history:
            counts[e.event_type] += 1
        return {
            **self._stats,
            "events_by_type": dict(counts),
            "total_subscribers": sum(len(s) for s in self._subscribers.values()) + len(self._wildcard_subscribers),
            "event_types": list(counts.keys()),
        }

    def wait_for(self, event_type: str, timeout: float = 10.0) -> Optional[Event]:
        """Block until an event of the given type is published.
        
        Warning: This is a simple poll-based wait. For production, use
        async wait with condition variables.
        """
        start = time.time()
        initial_count = len(self._history)
        while time.time() - start < timeout:
            for event in reversed(self._history):
                if event.event_type == event_type:
                    return event
            time.sleep(0.05)
        return None
