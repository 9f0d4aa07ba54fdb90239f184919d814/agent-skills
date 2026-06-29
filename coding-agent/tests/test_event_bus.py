"""Tests for EventBus — publish/subscribe event system."""

import pytest
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, call

sys.path.insert(0, str(Path(__file__).parent.parent))

from kernel.event_bus import (
    EventBus, Event, EventPriority,
    EVT_TASK_CREATED, EVT_STEP_STARTED, EVT_STEP_COMPLETED,
    EVT_JOB_FINISHED, EVT_JOB_FAILED, EVT_ERROR, EVT_LOG,
)


class TestEvent:
    """Tests for the Event data class."""

    def test_event_creation_defaults(self):
        e = Event("test.event")
        assert e.event_type == "test.event"
        assert e.source == ""
        assert e.data == {}
        assert e.priority == EventPriority.NORMAL
        assert e.id.startswith("evt-")
        assert e.propagated is False
        assert e.consumed_by == []
        assert isinstance(e.timestamp, float)
        assert isinstance(e.datetime, str)

    def test_event_creation_with_params(self):
        e = Event("custom", source="src", data={"key": "val"}, priority=EventPriority.HIGH)
        assert e.event_type == "custom"
        assert e.source == "src"
        assert e.data == {"key": "val"}
        assert e.priority == EventPriority.HIGH

    def test_event_repr(self):
        e = Event("foo", source="bar")
        r = repr(e)
        assert "foo" in r
        assert "bar" in r
        assert "NORMAL" in r


class TestEventBusSubscribe:
    """Tests for subscribe, unsubscribe, and wildcard."""

    def setup_method(self):
        self.bus = EventBus()

    def test_subscribe_returns_id(self):
        sub_id = self.bus.subscribe("test", lambda e: None)
        assert sub_id.startswith("sub-test-")

    def test_subscribe_with_name(self):
        sub_id = self.bus.subscribe("test", lambda e: None, name="my_sub")
        stats = self.bus.get_stats()
        assert stats["total_subscribers"] == 1

    def test_subscribe_all_returns_id(self):
        sub_id = self.bus.subscribe_all(lambda e: None)
        assert sub_id.startswith("sub-all-")

    def test_unsubscribe_returns_true(self):
        sub_id = self.bus.subscribe("test", lambda e: None)
        assert self.bus.unsubscribe(sub_id) is True

    def test_unsubscribe_nonexistent_returns_false(self):
        assert self.bus.unsubscribe("sub-nonexistent") is False

    def test_unsubscribe_wildcard(self):
        sub_id = self.bus.subscribe_all(lambda e: None)
        assert self.bus.unsubscribe(sub_id) is True
        assert self.bus.get_stats()["total_subscribers"] == 0

    def test_subscribe_priority_ordering(self):
        """Higher priority subscribers are called first."""
        call_order = []
        self.bus.subscribe("test", lambda e: call_order.append("low"), priority=0)
        self.bus.subscribe("test", lambda e: call_order.append("high"), priority=10)
        self.bus.subscribe("test", lambda e: call_order.append("med"), priority=5)
        self.bus.publish("test")
        assert call_order == ["high", "med", "low"]


class TestEventBusPublish:
    """Tests for event publishing and delivery."""

    def setup_method(self):
        self.bus = EventBus()

    def test_publish_returns_event(self):
        e = self.bus.publish("test.event")
        assert isinstance(e, Event)
        assert e.event_type == "test.event"

    def test_publish_delivers_to_subscriber(self):
        received = []
        self.bus.subscribe("test", lambda e: received.append(e))
        e = self.bus.publish("test")
        assert len(received) == 1
        assert received[0] is e

    def test_publish_event_object(self):
        e = Event("pre.created")
        returned = self.bus.publish_event(e)
        assert returned is e
        assert e in self.bus.get_history()

    def test_publish_delivers_to_matching_subscriber(self):
        received = []
        self.bus.subscribe("a", lambda e: received.append("a"))
        self.bus.subscribe("b", lambda e: received.append("b"))
        self.bus.publish("a")
        assert received == ["a"]

    def test_publish_delivers_to_wildcard(self):
        received = []
        self.bus.subscribe_all(lambda e: received.append("wild"))
        self.bus.publish("anything")
        assert received == ["wild"]

    def test_publish_delivers_to_both_specific_and_wildcard(self):
        received = []
        self.bus.subscribe("test", lambda e: received.append("specific"))
        self.bus.subscribe_all(lambda e: received.append("wild"))
        self.bus.publish("test")
        assert "specific" in received
        assert "wild" in received

    def test_publish_consumed_by_tracking(self):
        self.bus.subscribe("test", lambda e: None, name="sub1")
        e = self.bus.publish("test")
        assert "sub1" in e.consumed_by

    def test_publish_wildcard_consumed_by_prefixed(self):
        self.bus.subscribe_all(lambda e: None, name="ws")
        e = self.bus.publish("test")
        assert "*ws" in e.consumed_by

    def test_publish_sets_propagated(self):
        e = self.bus.publish("test")
        assert e.propagated is True


class TestEventBusStats:
    """Tests for statistics tracking."""

    def setup_method(self):
        self.bus = EventBus()

    def test_stats_published_count(self):
        self.bus.publish("a")
        self.bus.publish("b")
        stats = self.bus.get_stats()
        assert stats["published"] == 2

    def test_stats_delivered_count(self):
        self.bus.subscribe("a", lambda e: None)
        self.bus.subscribe("b", lambda e: None)
        self.bus.publish("a")
        self.bus.publish("b")
        stats = self.bus.get_stats()
        assert stats["delivered"] == 2

    def test_stats_events_by_type(self):
        self.bus.publish("a")
        self.bus.publish("a")
        self.bus.publish("b")
        stats = self.bus.get_stats()
        assert stats["events_by_type"]["a"] == 2
        assert stats["events_by_type"]["b"] == 1

    def test_stats_total_subscribers(self):
        self.bus.subscribe("a", lambda e: None)
        self.bus.subscribe("a", lambda e: None)
        self.bus.subscribe_all(lambda e: None)
        stats = self.bus.get_stats()
        assert stats["total_subscribers"] == 3

    def test_stats_event_types(self):
        self.bus.publish("a")
        self.bus.publish("b")
        stats = self.bus.get_stats()
        assert "a" in stats["event_types"]
        assert "b" in stats["event_types"]


class TestEventBusHistory:
    """Tests for event history."""

    def setup_method(self):
        self.bus = EventBus()

    def test_history_empty_by_default(self):
        assert self.bus.get_history() == []

    def test_history_returns_recent(self):
        for i in range(5):
            self.bus.publish(f"event.{i}")
        history = self.bus.get_history()
        assert len(history) == 5

    def test_history_limit(self):
        for i in range(10):
            self.bus.publish(f"event.{i}")
        history = self.bus.get_history(limit=3)
        assert len(history) == 3
        assert history[0].event_type == "event.7"

    def test_history_filter_by_type(self):
        self.bus.publish("a")
        self.bus.publish("b")
        self.bus.publish("a")
        history = self.bus.get_history(event_type="a")
        assert len(history) == 2
        assert all(e.event_type == "a" for e in history)

    def test_history_max_size(self):
        bus = EventBus()
        bus._max_history = 5
        for i in range(10):
            bus.publish(f"event.{i}")
        assert len(bus._history) == 5


class TestEventBusErrorIsolation:
    """Tests that subscriber errors don't crash the bus."""

    def setup_method(self):
        self.bus = EventBus()

    def test_subscriber_error_does_not_crash_bus(self):
        def bad_subscriber(e):
            raise ValueError("boom")

        self.bus.subscribe("test", bad_subscriber, name="bad")
        e = self.bus.publish("test")
        assert e.propagated is True

    def test_subscriber_error_increments_error_stat(self):
        def bad_subscriber(e):
            raise RuntimeError("fail")

        self.bus.subscribe("test", bad_subscriber, name="bad")
        self.bus.publish("test")
        stats = self.bus.get_stats()
        assert stats["errors"] == 1

    def test_other_subscribers_still_receive_after_error(self):
        received = []

        def bad_subscriber(e):
            raise ValueError("boom")

        self.bus.subscribe("test", bad_subscriber, name="bad")
        self.bus.subscribe("test", lambda e: received.append("ok"), name="good")
        self.bus.publish("test")
        assert received == ["ok"]

    def test_error_publishes_error_event(self):
        error_received = []

        def error_handler(e):
            error_received.append(e)

        def bad_subscriber(e):
            raise ValueError("oops")

        self.bus.subscribe(EVT_ERROR, error_handler, name="err_handler")
        self.bus.subscribe("test", bad_subscriber, name="bad")
        self.bus.publish("test")
        assert len(error_received) == 1
        assert error_received[0].data["error"] == "oops"
        assert error_received[0].data["subscriber"] == "bad"

    def test_wildcard_error_increments_stat(self):
        def bad_wildcard(e):
            raise Exception("wildcard fail")

        self.bus.subscribe_all(bad_wildcard, name="bw")
        self.bus.publish("test")
        stats = self.bus.get_stats()
        assert stats["errors"] == 1


class TestEventBusPriority:
    """Tests for priority ordering."""

    def setup_method(self):
        self.bus = EventBus()

    def test_critical_priority_first(self):
        order = []
        self.bus.subscribe("test", lambda e: order.append("low"), priority=EventPriority.LOW.value)
        self.bus.subscribe("test", lambda e: order.append("critical"), priority=EventPriority.CRITICAL.value)
        self.bus.subscribe("test", lambda e: order.append("normal"), priority=EventPriority.NORMAL.value)
        self.bus.subscribe("test", lambda e: order.append("high"), priority=EventPriority.HIGH.value)
        self.bus.publish("test")
        assert order == ["critical", "high", "normal", "low"]

    def test_publish_with_priority(self):
        e = self.bus.publish("test", priority=EventPriority.HIGH)
        assert e.priority == EventPriority.HIGH


class TestEventBusWaitFor:
    """Tests for wait_for method."""

    def setup_method(self):
        self.bus = EventBus()

    def test_wait_for_existing_event(self):
        self.bus.publish("target")
        result = self.bus.wait_for("target", timeout=1.0)
        assert result is not None
        assert result.event_type == "target"

    def test_wait_for_timeout(self):
        result = self.bus.wait_for("nonexistent", timeout=0.1)
        assert result is None


class TestEventBusInactivePruning:
    """Tests for inactive subscriber pruning."""

    def test_prune_removes_inactive_subscribers(self):
        bus = EventBus()
        bus.subscribe("test", lambda e: None, name="keep")
        bus.subscribe("test", lambda e: None, name="remove")
        # Mark second as inactive
        bus._subscribers["test"][1]["active"] = False
        bus._prune_inactive_subscribers()
        remaining = bus._subscribers.get("test", [])
        assert len(remaining) == 1
        assert remaining[0]["name"] == "keep"

    def test_prune_removes_empty_event_type_keys(self):
        bus = EventBus()
        bus.subscribe("temp", lambda e: None)
        bus.unsubscribe(bus._subscribers["temp"][0]["id"])
        bus._prune_inactive_subscribers()
        assert "temp" not in bus._subscribers

    def test_prune_removes_inactive_wildcards(self):
        bus = EventBus()
        bus.subscribe_all(lambda e: None, name="active")
        bus.subscribe_all(lambda e: None, name="inactive")
        bus._wildcard_subscribers[1]["active"] = False
        bus._prune_inactive_subscribers()
        assert len(bus._wildcard_subscribers) == 1
        assert bus._wildcard_subscribers[0]["name"] == "active"


class TestEventBusConstants:
    """Tests for standard event type constants."""

    def test_all_constants_are_strings(self):
        constants = [
            EVT_TASK_CREATED, EVT_STEP_STARTED, EVT_STEP_COMPLETED,
            EVT_JOB_FINISHED, EVT_JOB_FAILED, EVT_ERROR, EVT_LOG,
        ]
        for c in constants:
            assert isinstance(c, str)
            assert "." in c

    def test_publish_with_standard_event_types(self):
        bus = EventBus()
        for evt_type in [EVT_TASK_CREATED, EVT_STEP_STARTED, EVT_JOB_FINISHED]:
            e = bus.publish(evt_type, source="test")
            assert e.event_type == evt_type
