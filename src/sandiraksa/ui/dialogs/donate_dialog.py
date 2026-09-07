"""
Donate Dialog - Support Development.

Shows donation information.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
    QFrame,
)

from sandiraksa.ui.theme import ColorPalette, FONT_SIZE, SPACING


class DonateDialog(QDialog):
    """Donation information dialog."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Setup the UI layout."""
        self.setWindowTitle("Dukung Pengembangan SandiRaksa")
        self.setFixedSize(450, 420)

        layout = QVBoxLayout(self)
        layout.setSpacing(SPACING.LG)
        layout.setContentsMargins(SPACING.XL, SPACING.XL, SPACING.XL, SPACING.XL)

        # Title
        title = QLabel("❤️ Dukung Pengembangan")
        title.setStyleSheet(
            f"font-size: {FONT_SIZE.TITLE}px; "
            f"font-weight: bold; "
            f"color: {ColorPalette.PRIMARY.value};"
        )
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Description
        desc = QLabel(
            "SandiRaksa adalah proyek open source yang dikembangkan secara mandiri. "
            "Dukungan Anda membantu pengembangan fitur baru dan pemeliharaan aplikasi."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color: {ColorPalette.GRAY_600.value}; line-height: 1.5;")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(desc)

        layout.addSpacing(SPACING.MD)

        # Donation methods
        methods_title = QLabel("💳 Metode Donasi")
        methods_title.setStyleSheet(
            f"font-weight: 600; "
            f"font-size: {FONT_SIZE.LG}px; "
            f"color: {ColorPalette.GRAY_800.value};"
        )
        layout.addWidget(methods_title)

        # GoPay/OVO Card
        card = QFrame()
        card.setStyleSheet(
            f"background-color: {ColorPalette.GRAY_50.value}; "
            f"border: 1px solid {ColorPalette.GRAY_200.value}; "
            f"border-radius: 8px; "
            f"padding: {SPACING.MD}px;"
        )
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(SPACING.SM)

        gopay_title = QLabel("📱 GoPay / OVO")
        gopay_title.setStyleSheet(
            f"font-weight: 600; color: {ColorPalette.GRAY_800.value};"
        )
        card_layout.addWidget(gopay_title)

        phone_number = "+6281264656688"
        phone_label = QLabel(f"<b>{phone_number}</b>")
        phone_label.setStyleSheet(
            f"font-size: {FONT_SIZE.LG}px; "
            f"color: {ColorPalette.PRIMARY.value}; "
            f"padding: {SPACING.SM}px 0;"
        )
        phone_label.setTextFormat(Qt.TextFormat.RichText)
        card_layout.addWidget(phone_label)

        # Copy button
        copy_btn = QPushButton("📋 Salin Nomor")
        copy_btn.clicked.connect(lambda: self._copy_to_clipboard(phone_number))
        copy_btn.setStyleSheet(
            f"padding: {SPACING.SM}px {SPACING.MD}px; "
            f"background-color: {ColorPalette.GRAY_100.value};"
        )
        card_layout.addWidget(copy_btn)

        layout.addWidget(card)

        layout.addSpacing(SPACING.SM)

        # Thank you message
        thanks = QLabel(
            "🙏 Terima kasih atas dukungan Anda!\n"
            "Setiap kontribusi sangat berarti untuk pengembangan SandiRaksa."
        )
        thanks.setWordWrap(True)
        thanks.setStyleSheet(
            f"color: {ColorPalette.GRAY_500.value}; "
            f"font-style: italic; "
            f"text-align: center;"
        )
        thanks.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(thanks)

        layout.addStretch()

        # Status label for copy feedback
        self._status_label = QLabel("")
        self._status_label.setStyleSheet(f"color: {ColorPalette.SUCCESS.value};")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._status_label)

        # Close button
        close_btn = QPushButton("Tutup")
        close_btn.clicked.connect(self.accept)
        close_btn.setFixedWidth(100)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignCenter)

    def _copy_to_clipboard(self, text: str) -> None:
        """Copy text to clipboard."""
        clipboard = QGuiApplication.clipboard()
        clipboard.setText(text)
        self._status_label.setText("✓ Nomor disalin ke clipboard!")


__all__ = ["DonateDialog"]
