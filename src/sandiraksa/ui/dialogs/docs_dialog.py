"""
Documentation Dialog.

Shows documentation links and resources.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from sandiraksa.ui.theme import ColorPalette, FONT_SIZE, SPACING


class DocsDialog(QDialog):
    """Documentation links dialog."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Setup the UI layout."""
        self.setWindowTitle("Dokumentasi")
        self.setFixedSize(450, 350)

        layout = QVBoxLayout(self)
        layout.setSpacing(SPACING.LG)
        layout.setContentsMargins(SPACING.XL, SPACING.XL, SPACING.XL, SPACING.XL)

        # Title
        title = QLabel("📚 Dokumentasi SandiRaksa")
        title.setStyleSheet(
            f"font-size: {FONT_SIZE.TITLE}px; "
            f"font-weight: bold; "
            f"color: {ColorPalette.PRIMARY.value};"
        )
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Description
        desc = QLabel(
            "Temukan panduan lengkap, tutorial, dan referensi API "
            "untuk memaksimalkan penggunaan SandiRaksa."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color: {ColorPalette.GRAY_600.value};")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(desc)

        layout.addSpacing(SPACING.MD)

        # Documentation links
        links = [
            ("🌐", "Website & Dokumentasi Online", "https://sandiraksa.infosecguru.id"),
            ("📖", "README & Panduan Memulai", "https://github.com/yuanyudistira/sandiraksa#readme"),
            ("🐛", "Laporkan Bug / Issue", "https://github.com/yuanyudistira/sandiraksa/issues"),
            ("💡", "Request Fitur Baru", "https://github.com/yuanyudistira/sandiraksa/issues/new"),
        ]

        for icon, label_text, url in links:
            btn = QPushButton(f"{icon} {label_text}")
            btn.setStyleSheet(
                f"padding: {SPACING.MD}px; "
                f"font-size: {FONT_SIZE.MD}px; "
                f"text-align: left;"
            )
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked, u=url: QDesktopServices.openUrl(QUrl(u)))
            layout.addWidget(btn)

        layout.addStretch()

        # Note
        note = QLabel(
            "💡 Tekan F1 kapan saja untuk membuka Panduan Cepat"
        )
        note.setStyleSheet(
            f"color: {ColorPalette.GRAY_500.value}; "
            f"font-size: {FONT_SIZE.SM}px;"
        )
        note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(note)

        # Close button
        close_btn = QPushButton("Tutup")
        close_btn.clicked.connect(self.accept)
        close_btn.setFixedWidth(100)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignCenter)


__all__ = ["DocsDialog"]
