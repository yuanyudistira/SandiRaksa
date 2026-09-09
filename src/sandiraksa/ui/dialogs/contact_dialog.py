"""
Contact Dialog.

Shows contact information and links.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
)

from sandiraksa.ui.theme import ColorPalette, FONT_SIZE, SPACING


class ContactDialog(QDialog):
    """Contact information dialog."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Setup the UI layout."""
        self.setWindowTitle("Hubungi Kami")
        self.setFixedSize(400, 220)

        layout = QVBoxLayout(self)
        layout.setSpacing(SPACING.LG)
        layout.setContentsMargins(SPACING.XL, SPACING.XL, SPACING.XL, SPACING.XL)

        # Title
        title = QLabel("📬 Hubungi Kami")
        title.setStyleSheet(
            f"font-size: {FONT_SIZE.TITLE}px; "
            f"font-weight: bold; "
            f"color: {ColorPalette.PRIMARY.value};"
        )
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Description
        desc = QLabel(
            "Punya pertanyaan, saran, atau menemukan bug?\n"
            "Hubungi kami melalui GitHub."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color: {ColorPalette.GRAY_600.value};")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(desc)

        layout.addSpacing(SPACING.MD)

        # GitHub button
        github_btn = QPushButton("🐙 GitHub: github.com/yuanyudistira/sandiraksa")
        github_btn.setStyleSheet(
            f"padding: {SPACING.MD}px; "
            f"font-size: {FONT_SIZE.MD}px; "
            f"text-align: left;"
        )
        github_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        github_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl("https://github.com/yuanyudistira/sandiraksa"))
        )
        layout.addWidget(github_btn)

        layout.addStretch()

        # Close button
        close_btn = QPushButton("Tutup")
        close_btn.clicked.connect(self.accept)
        close_btn.setFixedWidth(100)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignCenter)


__all__ = ["ContactDialog"]
