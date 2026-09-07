"""
Help Dialog - Quick Start Guide.

Shows how to use the application.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from sandiraksa.ui.theme import ColorPalette, FONT_SIZE, SPACING


class HelpDialog(QDialog):
    """Quick start guide dialog."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Setup the UI layout."""
        self.setWindowTitle("Panduan Penggunaan SandiRaksa")
        self.setMinimumSize(600, 500)
        self.resize(650, 550)

        layout = QVBoxLayout(self)
        layout.setSpacing(SPACING.MD)
        layout.setContentsMargins(SPACING.LG, SPACING.LG, SPACING.LG, SPACING.LG)

        # Title
        title = QLabel("🛡️ Panduan Cepat SandiRaksa")
        title.setStyleSheet(
            f"font-size: {FONT_SIZE.TITLE}px; "
            f"font-weight: bold; "
            f"color: {ColorPalette.PRIMARY.value};"
        )
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Scroll area for content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSpacing(SPACING.MD)

        # Introduction
        intro = QLabel(
            "SandiRaksa membantu Anda melindungi data sensitif (PII) dalam dokumen "
            "sebelum dibagikan ke layanan AI seperti ChatGPT, Claude, atau Gemini. "
            "Semua pemrosesan dilakukan 100% lokal di komputer Anda."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet(f"color: {ColorPalette.GRAY_600.value}; line-height: 1.5;")
        content_layout.addWidget(intro)

        # Steps
        steps = [
            ("1️⃣", "Buat Proyek Baru", 
             "Klik tombol <b>+</b> di halaman utama untuk membuat proyek baru. "
             "Beri nama proyek dan pilih folder output untuk menyimpan file yang sudah diproteksi."),
            
            ("2️⃣", "Tambahkan File", 
             "Seret & lepas file ke area drop zone, atau klik untuk memilih file. "
             "Format yang didukung: <b>Excel (.xlsx)</b>, <b>CSV</b>, <b>Word (.docx)</b>, "
             "<b>PowerPoint (.pptx)</b>, dan <b>TXT</b>."),
            
            ("3️⃣", "Pilih Data yang Dilindungi", 
             "Untuk Excel/CSV: pilih kolom yang berisi data sensitif.<br>"
             "Untuk Word/PPT/TXT: aplikasi akan mendeteksi data sensitif secara otomatis, "
             "Anda bisa memilih mana yang ingin dilindungi."),
            
            ("4️⃣", "Proteksi File", 
             "Klik tombol <b>Proses</b> pada setiap file untuk memproteksi. "
             "Data sensitif akan diganti dengan token seperti <code>[[PERSON_A1B2C3]]</code>. "
             "File hasil akan tersimpan di folder output dengan suffix <code>_protected</code>."),
            
            ("5️⃣", "Gunakan File Terproteksi", 
             "Gunakan file yang sudah diproteksi untuk dibagikan ke AI. "
             "Data asli Anda aman karena sudah diganti dengan token."),
            
            ("6️⃣", "Pulihkan Data (Opsional)", 
             "Setelah mendapat hasil dari AI, Anda bisa memulihkan token kembali ke data asli "
             "menggunakan fitur <b>Restore</b>. Copy teks dari AI, paste di SandiRaksa, "
             "dan token akan dikembalikan ke nilai asli."),
        ]

        for icon, title_text, desc in steps:
            step_title = QLabel(f"{icon} <b>{title_text}</b>")
            step_title.setStyleSheet(
                f"font-size: {FONT_SIZE.LG}px; "
                f"color: {ColorPalette.GRAY_800.value}; "
                f"margin-top: {SPACING.MD}px;"
            )
            content_layout.addWidget(step_title)
            
            step_desc = QLabel(desc)
            step_desc.setWordWrap(True)
            step_desc.setStyleSheet(
                f"color: {ColorPalette.GRAY_600.value}; "
                f"padding-left: {SPACING.LG}px; "
                f"line-height: 1.4;"
            )
            step_desc.setTextFormat(Qt.TextFormat.RichText)
            content_layout.addWidget(step_desc)

        # Tips
        tips_title = QLabel("💡 Tips")
        tips_title.setStyleSheet(
            f"font-size: {FONT_SIZE.LG}px; "
            f"font-weight: bold; "
            f"color: {ColorPalette.PRIMARY.value}; "
            f"margin-top: {SPACING.LG}px;"
        )
        content_layout.addWidget(tips_title)

        tips = [
            "Data yang sama akan selalu menghasilkan token yang sama dalam satu proyek.",
            "Gunakan proyek terpisah untuk konteks yang berbeda (misal: HR, Keuangan, Medis).",
            "Backup folder database di <code>%LOCALAPPDATA%\\SandiRaksa</code> untuk keamanan.",
        ]
        
        for tip in tips:
            tip_label = QLabel(f"• {tip}")
            tip_label.setWordWrap(True)
            tip_label.setTextFormat(Qt.TextFormat.RichText)
            tip_label.setStyleSheet(
                f"color: {ColorPalette.GRAY_600.value}; "
                f"padding-left: {SPACING.MD}px;"
            )
            content_layout.addWidget(tip_label)

        content_layout.addStretch()
        scroll.setWidget(content_widget)
        layout.addWidget(scroll, 1)

        # Close button
        close_btn = QPushButton("Tutup")
        close_btn.clicked.connect(self.accept)
        close_btn.setFixedWidth(100)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignCenter)


__all__ = ["HelpDialog"]
