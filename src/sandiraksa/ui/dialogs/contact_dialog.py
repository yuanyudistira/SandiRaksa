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
        self.setFixedSize(400, 300)

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
            "Jangan ragu untuk menghubungi kami."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color: {ColorPalette.GRAY_600.value};")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(desc)

        layout.addSpacing(SPACING.MD)

        # Email button
        email_btn = QPushButton("📧 Email: infosecguru.id@gmail.com")
        email_btn.setStyleSheet(
            f"padding: {SPACING.MD}px; "
            f"font-size: {FONT_SIZE.MD}px; "
            f"text-align: left;"
        )
        email_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        email_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl("mailto:infosecguru.id@gmail.com"))
        )
        layout.addWidget(email_btn)

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

        # Website button
        website_btn = QPushButton("🌐 Website: sandiraksa.infosecguru.id")
        website_btn.setStyleSheet(
            f"padding: {SPACING.MD}px; "
            f"font-size: {FONT_SIZE.MD}px; "
            f"text-align: left;"
        )
        website_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        website_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl("https://sandiraksa.infosecguru.id"))
        )
        layout.addWidget(website_btn)

        layout.addStretch()

        # Close button
        close_btn = QPushButton("Tutup")
        close_btn.clicked.connect(self.accept)
        close_btn.setFixedWidth(100)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignCenter)


__all__ = ["ContactDialog"]
