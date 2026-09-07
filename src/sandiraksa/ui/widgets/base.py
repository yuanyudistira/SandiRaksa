"""
Base UI widgets for SandiRaksa.

Reusable components used across the application.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QMouseEvent, QPainter
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from sandiraksa.ui.theme import (
    BORDER_RADIUS,
    FONT_SIZE,
    SPACING,
    ColorPalette,
)

if TYPE_CHECKING:
    from collections.abc import Callable


class Card(QFrame):
    """A card container with border and padding."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("card", True)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(SPACING.LG, SPACING.LG, SPACING.LG, SPACING.LG)
        self._layout.setSpacing(SPACING.MD)

    def add_widget(self, widget: QWidget) -> None:
        """Add a widget to the card."""
        self._layout.addWidget(widget)

    def add_layout(self, layout: QVBoxLayout | QHBoxLayout) -> None:
        """Add a layout to the card."""
        self._layout.addLayout(layout)


class ClickableCard(Card):
    """A card that can be clicked."""

    clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Handle mouse press."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class SectionHeader(QWidget):
    """Section header with title and optional action."""

    def __init__(
        self,
        title: str,
        action_text: str | None = None,
        action_callback: Callable[[], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._title = QLabel(title)
        self._title.setProperty("heading", True)
        font = self._title.font()
        font.setPointSize(FONT_SIZE.LG)
        font.setBold(True)
        self._title.setFont(font)
        layout.addWidget(self._title)

        layout.addStretch()

        if action_text and action_callback:
            self._action = QPushButton(action_text)
            self._action.setProperty("secondary", True)
            self._action.clicked.connect(action_callback)
            layout.addWidget(self._action)

    def set_title(self, title: str) -> None:
        """Update the title text."""
        self._title.setText(title)


class EmptyState(QWidget):
    """Empty state with icon, title, and optional action."""

    def __init__(
        self,
        title: str,
        description: str | None = None,
        action_text: str | None = None,
        action_callback: Callable[[], None] | None = None,
        icon: str = "📁",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(SPACING.MD)

        # Icon
        icon_label = QLabel(icon)
        icon_label.setStyleSheet(f"font-size: {FONT_SIZE.HERO}px;")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_label)

        # Title
        title_label = QLabel(title)
        title_label.setStyleSheet(
            f"font-size: {FONT_SIZE.XL}px; "
            f"font-weight: 600; "
            f"color: {ColorPalette.GRAY_700.value};"
        )
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        # Description
        if description:
            desc_label = QLabel(description)
            desc_label.setStyleSheet(
                f"font-size: {FONT_SIZE.MD}px; color: {ColorPalette.GRAY_500.value};"
            )
            desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            desc_label.setWordWrap(True)
            layout.addWidget(desc_label)

        # Action button
        if action_text and action_callback:
            layout.addSpacing(SPACING.MD)
            action_btn = QPushButton(action_text)
            action_btn.clicked.connect(action_callback)
            action_btn.setFixedWidth(200)
            layout.addWidget(action_btn, alignment=Qt.AlignmentFlag.AlignCenter)


class SearchInput(QLineEdit):
    """Search input with icon."""

    def __init__(
        self,
        placeholder: str = "Search...",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setPlaceholderText(f"🔍 {placeholder}")
        self.setClearButtonEnabled(True)
        self.setMinimumHeight(40)


class StatusBadge(QLabel):
    """Status badge with background color."""

    def __init__(
        self,
        text: str,
        color: str = ColorPalette.GRAY_500.value,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(text, parent)
        self._set_style(color)

    def _set_style(self, color: str) -> None:
        """Apply badge styling."""
        self.setStyleSheet(
            f"background-color: {color}; "
            f"color: white; "
            f"padding: {SPACING.XS}px {SPACING.SM}px; "
            f"border-radius: {BORDER_RADIUS.SM}px; "
            f"font-size: {FONT_SIZE.SM}px; "
            f"font-weight: 500;"
        )

    def set_color(self, color: str) -> None:
        """Update badge color."""
        self._set_style(color)


class IconButton(QPushButton):
    """Button with icon only."""

    def __init__(
        self,
        icon: str,
        tooltip: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(icon, parent)
        self.setFixedSize(36, 36)
        self.setStyleSheet(
            f"QPushButton {{ "
            f"background-color: transparent; "
            f"border: 1px solid {ColorPalette.GRAY_300.value}; "
            f"border-radius: {BORDER_RADIUS.MD}px; "
            f"font-size: 16px; "
            f"}} "
            f"QPushButton:hover {{ "
            f"background-color: {ColorPalette.GRAY_100.value}; "
            f"}}"
        )
        if tooltip:
            self.setToolTip(tooltip)


class LoadingSpinner(QWidget):
    """Simple loading indicator."""

    def __init__(
        self,
        size: int = 40,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setFixedSize(size, size)
        self._angle = 0

        # Use a label with emoji for simplicity
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._label = QLabel("⏳")
        self._label.setStyleSheet(f"font-size: {size - 8}px;")
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._label)

    def set_loading(self, loading: bool) -> None:
        """Show or hide the spinner."""
        self.setVisible(loading)


__all__ = [
    "Card",
    "ClickableCard",
    "EmptyState",
    "IconButton",
    "LoadingSpinner",
    "SearchInput",
    "SectionHeader",
    "StatusBadge",
]
