"""
Restore View Screen.

Screen for restoring tokens to original values.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from sandiraksa.app.i18n import tr
from sandiraksa.ui.theme import ColorPalette, FONT_SIZE, SPACING
from sandiraksa.ui.widgets import Card, SectionHeader

if TYPE_CHECKING:
    pass


class RestoreViewScreen(QWidget):
    """
    Screen for restoring tokens.

    User pastes content with tokens, and the app restores original values.
    """

    restore_requested = Signal(str)  # text content
    back_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Setup the UI layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING.XL, SPACING.XL, SPACING.XL, SPACING.XL)
        layout.setSpacing(SPACING.LG)

        # Header
        header = SectionHeader(tr("restore.title"))
        layout.addWidget(header)

        # Description
        desc = QLabel(tr("restore.description"))
        desc.setStyleSheet(f"color: {ColorPalette.GRAY_600.value};")
        layout.addWidget(desc)

        # Splitter for input/output
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: Input
        input_panel = QWidget()
        input_layout = QVBoxLayout(input_panel)
        input_layout.setContentsMargins(0, 0, 0, 0)

        input_label = QLabel(tr("restore.paste_content"))
        input_label.setStyleSheet(f"font-weight: 600;")
        input_layout.addWidget(input_label)

        self._input_text = QPlainTextEdit()
        self._input_text.setPlaceholderText(tr("restore.paste_hint"))
        self._input_text.setStyleSheet(
            f"font-family: 'Consolas', 'Monaco', monospace; "
            f"font-size: {FONT_SIZE.MD}px;"
        )
        self._input_text.textChanged.connect(self._on_input_changed)
        input_layout.addWidget(self._input_text)

        # Token count
        self._tokens_found = QLabel("")
        self._tokens_found.setStyleSheet(f"color: {ColorPalette.GRAY_500.value};")
        input_layout.addWidget(self._tokens_found)

        splitter.addWidget(input_panel)

        # Right: Output
        output_panel = QWidget()
        output_layout = QVBoxLayout(output_panel)
        output_layout.setContentsMargins(0, 0, 0, 0)

        output_label = QLabel(tr("restore.restored"))
        output_label.setStyleSheet(f"font-weight: 600;")
        output_layout.addWidget(output_label)

        self._output_text = QPlainTextEdit()
        self._output_text.setReadOnly(True)
        self._output_text.setStyleSheet(
            f"font-family: 'Consolas', 'Monaco', monospace; "
            f"font-size: {FONT_SIZE.MD}px; "
            f"background-color: {ColorPalette.GRAY_50.value};"
        )
        output_layout.addWidget(self._output_text)

        # Status
        self._status_label = QLabel("")
        output_layout.addWidget(self._status_label)

        splitter.addWidget(output_panel)

        layout.addWidget(splitter, stretch=1)

        # Actions
        actions = QHBoxLayout()

        back_btn = QPushButton(tr("buttons.back"))
        back_btn.setProperty("secondary", True)
        back_btn.clicked.connect(self.back_requested.emit)
        actions.addWidget(back_btn)

        actions.addStretch()

        self._restore_btn = QPushButton(tr("restore.restore_button"))
        self._restore_btn.clicked.connect(self._do_restore)
        self._restore_btn.setEnabled(False)
        actions.addWidget(self._restore_btn)

        self._copy_btn = QPushButton(tr("restore.copy_result"))
        self._copy_btn.setProperty("secondary", True)
        self._copy_btn.clicked.connect(self._copy_result)
        self._copy_btn.setEnabled(False)
        actions.addWidget(self._copy_btn)

        layout.addLayout(actions)

    def _on_input_changed(self) -> None:
        """Handle input text change."""
        text = self._input_text.toPlainText()

        # Count tokens (simple regex match for [[TYPE_HEXID]])
        import re
        tokens = re.findall(r"\[\[[A-Z_]+_[A-Fa-f0-9]+\]\]", text)
        count = len(tokens)

        if count > 0:
            self._tokens_found.setText(tr("restore.tokens_found", count=count))
            self._tokens_found.setStyleSheet(f"color: {ColorPalette.SUCCESS.value};")
            self._restore_btn.setEnabled(True)
        else:
            self._tokens_found.setText(tr("restore.no_tokens"))
            self._tokens_found.setStyleSheet(f"color: {ColorPalette.GRAY_500.value};")
            self._restore_btn.setEnabled(False)

    def _do_restore(self) -> None:
        """Trigger restore operation."""
        text = self._input_text.toPlainText()
        self.restore_requested.emit(text)

    def set_result(self, restored_text: str, invalid_count: int = 0) -> None:
        """
        Set restoration result.

        Args:
            restored_text: Text with tokens replaced.
            invalid_count: Number of tokens that couldn't be restored.
        """
        self._output_text.setPlainText(restored_text)
        self._copy_btn.setEnabled(bool(restored_text))

        if invalid_count > 0:
            self._status_label.setText(
                tr("restore.invalid_tokens", count=invalid_count)
            )
            self._status_label.setStyleSheet(f"color: {ColorPalette.WARNING.value};")
        else:
            self._status_label.setText("✓ " + tr("restore.restored"))
            self._status_label.setStyleSheet(f"color: {ColorPalette.SUCCESS.value};")

    def _copy_result(self) -> None:
        """Copy result to clipboard."""
        from PySide6.QtWidgets import QApplication

        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(self._output_text.toPlainText())

    def clear(self) -> None:
        """Clear input and output."""
        self._input_text.clear()
        self._output_text.clear()
        self._tokens_found.clear()
        self._status_label.clear()
        self._restore_btn.setEnabled(False)
        self._copy_btn.setEnabled(False)


__all__ = ["RestoreViewScreen"]
