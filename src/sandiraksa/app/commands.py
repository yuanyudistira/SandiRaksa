"""
Application commands and actions.

This module defines the command pattern for application actions,
enabling undo/redo and consistent action handling.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any
from uuid import UUID, uuid4


class Command(ABC):
    """Base class for all application commands."""

    def __init__(self) -> None:
        self.id: UUID = uuid4()
        self.executed: bool = False

    @abstractmethod
    def execute(self) -> Any:
        """Execute the command."""
        ...

    def can_undo(self) -> bool:
        """Check if the command can be undone."""
        return False

    def undo(self) -> None:
        """Undo the command. Override in subclasses that support undo."""
        raise NotImplementedError("This command does not support undo")


class CommandHistory:
    """Manages command history for undo/redo functionality."""

    def __init__(self, max_history: int = 100) -> None:
        self._history: list[Command] = []
        self._redo_stack: list[Command] = []
        self._max_history = max_history

    def execute(self, command: Command) -> Any:
        """Execute a command and add it to history."""
        result = command.execute()
        command.executed = True

        if command.can_undo():
            self._history.append(command)
            self._redo_stack.clear()

            # Limit history size
            if len(self._history) > self._max_history:
                self._history.pop(0)

        return result

    def undo(self) -> bool:
        """Undo the last command."""
        if not self._history:
            return False

        command = self._history.pop()
        command.undo()
        self._redo_stack.append(command)
        return True

    def redo(self) -> bool:
        """Redo the last undone command."""
        if not self._redo_stack:
            return False

        command = self._redo_stack.pop()
        command.execute()
        self._history.append(command)
        return True

    def can_undo(self) -> bool:
        """Check if there are commands to undo."""
        return bool(self._history)

    def can_redo(self) -> bool:
        """Check if there are commands to redo."""
        return bool(self._redo_stack)

    def clear(self) -> None:
        """Clear all command history."""
        self._history.clear()
        self._redo_stack.clear()
