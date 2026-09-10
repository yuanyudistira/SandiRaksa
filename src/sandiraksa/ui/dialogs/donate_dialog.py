"""
Sponsor Dialog.

Shows a sponsored recommendation instead of donation details.
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
    QFrame,
)

from sandiraksa.ui.theme import ColorPalette, FONT_SIZE, SPACING


SPONSOR_URL = (
    "https://lakukeras.id/seller/toko-digital-tenda-mina/"
    "pdf-buku-panduan-cyber-security/pay"
)


class DonateDialog(QDialog):
    """Sponsor / recommended-resource dialog."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Setup the UI layout."""
        self.setWindowTitle("Sponsor")
        self.setFixedSize(460, 360)

        layout = QVBoxLayout(self)
        layout.setSpacing(SPACING.LG)
        layout.setContentsMargins(SPACING.XL, SPACING.XL, SPACING.XL, SPACING.XL)

        # Title
        title = QLabel("Sponsor")
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
            "Dukung pengembangan dengan melihat sumber belajar rekomendasi kami."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color: {ColorPalette.GRAY_600.value}; line-height: 1.5;")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(desc)

        layout.addSpacing(SPACING.MD)

        # Sponsor card
        card = QFrame()
        card.setStyleSheet(
            f"background-color: {ColorPalette.GRAY_50.value}; "
            f"border: 1px solid {ColorPalette.GRAY_200.value}; "
            f"border-radius: 8px; "
            f"padding: {SPACING.MD}px;"
        )
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(SPACING.SM)

        product_title = QLabel("Panduan Cyber Security (PDF)")
        product_title.setStyleSheet(
            f"font-weight: 600; "
            f"font-size: {FONT_SIZE.LG}px; "
            f"color: {ColorPalette.GRAY_800.value};"
        )
        product_title.setWordWrap(True)
        card_layout.addWidget(product_title)

        product_desc = QLabel(
            "Buku panduan praktis untuk meningkatkan keamanan digital Anda."
        )
        product_desc.setWordWrap(True)
        product_desc.setStyleSheet(f"color: {ColorPalette.GRAY_600.value};")
        card_layout.addWidget(product_desc)

        download_btn = QPushButton("Download Panduan")
        download_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        download_btn.clicked.connect(self._open_sponsor_link)
        download_btn.setStyleSheet(
            f"padding: {SPACING.SM}px {SPACING.MD}px; "
            f"background-color: {ColorPalette.PRIMARY.value}; "
            f"color: white; "
            f"font-weight: 600; "
            f"border-radius: 6px;"
        )
        card_layout.addWidget(download_btn)

        layout.addWidget(card)

        layout.addStretch()

        # Close button
        close_btn = QPushButton("Tutup")
        close_btn.clicked.connect(self.accept)
        close_btn.setFixedWidth(100)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignCenter)

    def _open_sponsor_link(self) -> None:
        """Open the sponsor URL in the default browser."""
        QDesktopServices.openUrl(QUrl(SPONSOR_URL))


__all__ = ["DonateDialog"]
