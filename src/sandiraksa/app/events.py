"""
Application event system.

This module provides a simple pub/sub event system for
decoupled communication between application components.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable
from uuid import UUID


class EventType(Enum):
    """Application event types."""

    # Project events
    PROJECT_CREATED = auto()
    PROJECT_OPENED = auto()
    PROJECT_CLOSED = auto()
    PROJECT_DELETED = auto()
    PROJECT_UPDATED = auto()

    # File events
    FILE_ADDED = auto()
    FILE_REMOVED = auto()
    FILE_PROCESSING_STARTED = auto()
    FILE_PROCESSING_COMPLETED = auto()
    FILE_PROCESSING_FAILED = auto()

    # Scan events
    SCAN_STARTED = auto()
    SCAN_PROGRESS = auto()
    SCAN_COMPLETED = auto()
    SCAN_CANCELLED = auto()
    SCAN_FAILED = auto()

    # Protection events
    PROTECTION_STARTED = auto()
    PROTECTION_PROGRESS = auto()
    PROTECTION_COMPLETED = auto()
    PROTECTION_FAILED = auto()

    # Restore events
    RESTORE_STARTED = auto()
    RESTORE_PROGRESS = auto()
    RESTORE_COMPLETED = auto()
    RESTORE_FAILED = auto()

    # UI events
    LANGUAGE_CHANGED = auto()
    THEME_CHANGED = auto()
    SETTINGS_CHANGED = auto()


@dataclass
class Event:
    """Base event class."""

    type: EventType
    data: dict[str, Any] = field(default_factory=dict)
    source: str | None = None


@dataclass
class ProgressEvent(Event):
    """Event for progress updates."""

    current: int = 0
    total: int = 0
    message: str = ""
    file_id: UUID | None = None
    component: str | None = None


EventHandler = Callable[[Event], None]


class EventBus:
    """Simple event bus for application-wide events."""

    _instance: EventBus | None = None

    def __new__(cls) -> EventBus:
        """Singleton pattern for global event bus."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._handlers = defaultdict(list)
        return cls._instance

    def __init__(self) -> None:
        # Initialize only if not already done (singleton)
        if not hasattr(self, "_handlers"):
            self._handlers: dict[EventType, list[EventHandler]] = defaultdict(list)

    def subscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """Subscribe to an event type."""
        if handler not in self._handlers[event_type]:
            self._handlers[event_type].append(handler)

    def unsubscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """Unsubscribe from an event type."""
        if handler in self._handlers[event_type]:
            self._handlers[event_type].remove(handler)

    def emit(self, event: Event) -> None:
        """Emit an event to all subscribers."""
        for handler in self._handlers[event.type]:
            try:
                handler(event)
            except Exception:
                # Log error but don't crash - handlers should be fault tolerant
                # TODO: Add proper logging
                pass

    def clear(self) -> None:
        """Clear all subscriptions."""
        self._handlers.clear()

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton instance (for testing)."""
        cls._instance = None


def get_event_bus() -> EventBus:
    """Get the global event bus instance."""
    return EventBus()
