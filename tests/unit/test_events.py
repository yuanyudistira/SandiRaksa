"""Tests for event system."""

import pytest

from sandiraksa.app.events import (
    Event,
    EventBus,
    EventType,
    ProgressEvent,
    get_event_bus,
)


@pytest.fixture(autouse=True)
def reset_event_bus():
    """Reset event bus before each test."""
    EventBus.reset()
    yield
    EventBus.reset()


class TestEvent:
    """Tests for Event class."""

    def test_event_creation(self):
        """Event should be created with type and optional data."""
        event = Event(type=EventType.PROJECT_CREATED)
        assert event.type == EventType.PROJECT_CREATED
        assert event.data == {}
        assert event.source is None

    def test_event_with_data(self):
        """Event should accept additional data."""
        event = Event(
            type=EventType.PROJECT_CREATED,
            data={"project_id": "123"},
            source="test"
        )
        assert event.data["project_id"] == "123"
        assert event.source == "test"


class TestProgressEvent:
    """Tests for ProgressEvent class."""

    def test_progress_event_defaults(self):
        """ProgressEvent should have sensible defaults."""
        event = ProgressEvent(type=EventType.SCAN_PROGRESS)
        assert event.current == 0
        assert event.total == 0
        assert event.message == ""
        assert event.file_id is None

    def test_progress_event_with_values(self):
        """ProgressEvent should accept progress values."""
        from uuid import uuid4
        file_id = uuid4()
        
        event = ProgressEvent(
            type=EventType.SCAN_PROGRESS,
            current=50,
            total=100,
            message="Processing...",
            file_id=file_id,
            component="sheet1"
        )
        
        assert event.current == 50
        assert event.total == 100
        assert event.message == "Processing..."
        assert event.file_id == file_id
        assert event.component == "sheet1"


class TestEventBus:
    """Tests for EventBus class."""

    def test_singleton_pattern(self):
        """EventBus should be a singleton."""
        bus1 = EventBus()
        bus2 = EventBus()
        assert bus1 is bus2

    def test_get_event_bus_returns_singleton(self):
        """get_event_bus should return the same instance."""
        bus1 = get_event_bus()
        bus2 = get_event_bus()
        assert bus1 is bus2

    def test_subscribe_and_emit(self):
        """Events should be delivered to subscribers."""
        bus = get_event_bus()
        received = []

        def handler(event: Event):
            received.append(event)

        bus.subscribe(EventType.PROJECT_CREATED, handler)
        
        event = Event(type=EventType.PROJECT_CREATED)
        bus.emit(event)

        assert len(received) == 1
        assert received[0] is event

    def test_unsubscribe(self):
        """Unsubscribed handlers should not receive events."""
        bus = get_event_bus()
        received = []

        def handler(event: Event):
            received.append(event)

        bus.subscribe(EventType.PROJECT_CREATED, handler)
        bus.unsubscribe(EventType.PROJECT_CREATED, handler)
        
        bus.emit(Event(type=EventType.PROJECT_CREATED))

        assert len(received) == 0

    def test_multiple_subscribers(self):
        """Multiple handlers can subscribe to same event type."""
        bus = get_event_bus()
        received1 = []
        received2 = []

        def handler1(event: Event):
            received1.append(event)

        def handler2(event: Event):
            received2.append(event)

        bus.subscribe(EventType.SCAN_STARTED, handler1)
        bus.subscribe(EventType.SCAN_STARTED, handler2)
        
        bus.emit(Event(type=EventType.SCAN_STARTED))

        assert len(received1) == 1
        assert len(received2) == 1

    def test_handler_exception_does_not_stop_others(self):
        """One handler's exception should not stop other handlers."""
        bus = get_event_bus()
        received = []

        def bad_handler(event: Event):
            raise ValueError("Test error")

        def good_handler(event: Event):
            received.append(event)

        bus.subscribe(EventType.SCAN_STARTED, bad_handler)
        bus.subscribe(EventType.SCAN_STARTED, good_handler)
        
        # Should not raise
        bus.emit(Event(type=EventType.SCAN_STARTED))

        # Good handler should still receive the event
        assert len(received) == 1

    def test_clear_subscriptions(self):
        """clear() should remove all subscriptions."""
        bus = get_event_bus()
        received = []

        def handler(event: Event):
            received.append(event)

        bus.subscribe(EventType.PROJECT_CREATED, handler)
        bus.clear()
        
        bus.emit(Event(type=EventType.PROJECT_CREATED))

        assert len(received) == 0

    def test_duplicate_subscription_ignored(self):
        """Same handler should not be added twice."""
        bus = get_event_bus()
        received = []

        def handler(event: Event):
            received.append(event)

        bus.subscribe(EventType.PROJECT_CREATED, handler)
        bus.subscribe(EventType.PROJECT_CREATED, handler)
        
        bus.emit(Event(type=EventType.PROJECT_CREATED))

        # Handler should only be called once
        assert len(received) == 1
