"""Tests for command system."""

import pytest

from sandiraksa.app.commands import Command, CommandHistory


class IncrementCommand(Command):
    """Test command that increments a counter."""

    def __init__(self, counter: dict, key: str = "value"):
        super().__init__()
        self.counter = counter
        self.key = key
        self._old_value: int | None = None

    def execute(self) -> int:
        self._old_value = self.counter.get(self.key, 0)
        self.counter[self.key] = self._old_value + 1
        return self.counter[self.key]

    def can_undo(self) -> bool:
        return True

    def undo(self) -> None:
        if self._old_value is not None:
            self.counter[self.key] = self._old_value


class NonUndoableCommand(Command):
    """Test command that cannot be undone."""

    def __init__(self, results: list):
        super().__init__()
        self.results = results

    def execute(self) -> str:
        result = "executed"
        self.results.append(result)
        return result


class TestCommand:
    """Tests for Command base class."""

    def test_command_has_unique_id(self):
        """Each command should have a unique ID."""
        counter = {"value": 0}
        cmd1 = IncrementCommand(counter)
        cmd2 = IncrementCommand(counter)
        assert cmd1.id != cmd2.id

    def test_command_execute(self):
        """Command should execute its action."""
        counter = {"value": 0}
        cmd = IncrementCommand(counter)
        result = cmd.execute()
        assert result == 1
        assert counter["value"] == 1

    def test_command_undo(self):
        """Undoable command should restore previous state."""
        counter = {"value": 5}
        cmd = IncrementCommand(counter)
        cmd.execute()
        assert counter["value"] == 6
        
        cmd.undo()
        assert counter["value"] == 5

    def test_non_undoable_command(self):
        """Non-undoable command should raise on undo."""
        results = []
        cmd = NonUndoableCommand(results)
        cmd.execute()
        
        assert cmd.can_undo() is False
        with pytest.raises(NotImplementedError):
            cmd.undo()


class TestCommandHistory:
    """Tests for CommandHistory class."""

    def test_execute_through_history(self):
        """Commands executed through history should work."""
        history = CommandHistory()
        counter = {"value": 0}
        
        cmd = IncrementCommand(counter)
        result = history.execute(cmd)
        
        assert result == 1
        assert cmd.executed is True

    def test_undo(self):
        """History should support undo."""
        history = CommandHistory()
        counter = {"value": 0}
        
        history.execute(IncrementCommand(counter))
        history.execute(IncrementCommand(counter))
        assert counter["value"] == 2
        
        history.undo()
        assert counter["value"] == 1

    def test_redo(self):
        """History should support redo after undo."""
        history = CommandHistory()
        counter = {"value": 0}
        
        history.execute(IncrementCommand(counter))
        history.undo()
        assert counter["value"] == 0
        
        history.redo()
        assert counter["value"] == 1

    def test_redo_cleared_after_new_command(self):
        """Redo stack should clear after new command."""
        history = CommandHistory()
        counter = {"value": 0}
        
        history.execute(IncrementCommand(counter))
        history.undo()
        history.execute(IncrementCommand(counter))
        
        assert history.can_redo() is False

    def test_non_undoable_not_in_history(self):
        """Non-undoable commands should not be added to history."""
        history = CommandHistory()
        results = []
        
        history.execute(NonUndoableCommand(results))
        
        assert history.can_undo() is False

    def test_history_limit(self):
        """History should respect max size."""
        history = CommandHistory(max_history=3)
        counter = {"value": 0}
        
        for _ in range(5):
            history.execute(IncrementCommand(counter))
        
        assert counter["value"] == 5
        
        # Can only undo 3 times
        undo_count = 0
        while history.undo():
            undo_count += 1
        
        assert undo_count == 3
        assert counter["value"] == 2

    def test_clear_history(self):
        """Clear should remove all history."""
        history = CommandHistory()
        counter = {"value": 0}
        
        history.execute(IncrementCommand(counter))
        history.undo()
        
        history.clear()
        
        assert history.can_undo() is False
        assert history.can_redo() is False
