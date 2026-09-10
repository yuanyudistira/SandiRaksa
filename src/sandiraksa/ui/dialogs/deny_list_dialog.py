"""
Deny-list Dialog (Daftar Pengecualian).

Lets the user define global terms that must NEVER be reported as PII, even if a
recognizer flags them (e.g. IT jargon "server"/"log", ticket prefixes, common
words misdetected as PERSON). The list applies to all projects.

Input format: one term per line. Lines starting with '#' are comments.
An empty list means normal detection (nothing is excluded).
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QPushButton,
    QPlainTextEdit,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
    QMessageBox,
)

from sandiraksa.ui.theme import ColorPalette, FONT_SIZE, SPACING
from sandiraksa.detection.deny_list import (
    DenyListStore,
    parse_deny_text,
    deny_terms_to_text,
    save_global_deny_list_from_text,
)


PLACEHOLDER = (
    "# Kosongkan saja jika tidak perlu — deteksi standar tetap berjalan.\n"
    "#\n"
    "# Tulis satu istilah per baris. Istilah ini TIDAK akan pernah dianggap PII.\n"
    "#\n"
    "# Contoh (silakan hapus dan ganti dengan milik Anda):\n"
    "server\n"
    "log\n"
    "backup\n"
    "INC"
)

HELP_TEXT = (
    "Daftar istilah yang TIDAK boleh dianggap data pribadi, meski terdeteksi "
    "oleh sistem. Berguna untuk jargon IT (server, log, host), awalan tiket "
    "(INC, TKT), atau kata umum yang keliru dikenali sebagai nama. Daftar ini "
    "berlaku untuk SEMUA project."
)

EXAMPLE_HTML = (
    "<b>Format:</b> satu istilah per baris.<br>"
    "<b>Contoh:</b><br>"
    "&nbsp;&nbsp;<code>server</code> → \"server\" tidak lagi dianggap nama<br>"
    "&nbsp;&nbsp;<code>backup</code>, <code>host</code>, <code>cluster</code><br>"
    "&nbsp;&nbsp;<code>INC</code> → awalan nomor tiket<br>"
    "<span style='color:#64748b'>Pencocokan tidak membedakan huruf besar/kecil. "
    "Baris diawali <code>#</code> dianggap komentar. Boleh dikosongkan (opsional).</span>"
)


class DenyListDialog(QDialog):
    """Dialog for editing the global deny-list (exclusion terms)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._store = DenyListStore()
        self._setup_ui()
        self._load_existing()

    def _setup_ui(self) -> None:
        self.setWindowTitle("Daftar Pengecualian")
        self.setMinimumSize(560, 480)

        layout = QVBoxLayout(self)
        layout.setSpacing(SPACING.MD)
        layout.setContentsMargins(SPACING.XL, SPACING.XL, SPACING.XL, SPACING.XL)

        # Title
        title = QLabel("🚫 Daftar Pengecualian (Global)")
        title.setStyleSheet(
            f"font-size: {FONT_SIZE.TITLE}px; "
            f"font-weight: bold; "
            f"color: {ColorPalette.PRIMARY.value};"
        )
        layout.addWidget(title)

        # Help text
        help_lbl = QLabel(HELP_TEXT)
        help_lbl.setWordWrap(True)
        help_lbl.setStyleSheet(f"color: {ColorPalette.GRAY_600.value};")
        layout.addWidget(help_lbl)

        # Example panel
        example_box = QLabel(EXAMPLE_HTML)
        example_box.setWordWrap(True)
        example_box.setTextFormat(Qt.TextFormat.RichText)
        example_box.setStyleSheet(
            f"background-color: {ColorPalette.GRAY_50.value}; "
            f"border: 1px solid {ColorPalette.GRAY_200.value}; "
            f"border-radius: 6px; "
            f"padding: {SPACING.MD}px; "
            f"font-size: {FONT_SIZE.SM}px;"
        )
        layout.addWidget(example_box)

        # Editor label
        editor_lbl = QLabel("Istilah Anda (opsional — boleh dikosongkan):")
        editor_lbl.setStyleSheet(
            f"color: {ColorPalette.GRAY_700.value}; font-weight: bold;"
        )
        layout.addWidget(editor_lbl)

        # Text area
        self._text_edit = QPlainTextEdit()
        self._text_edit.setPlaceholderText(PLACEHOLDER)
        self._text_edit.setStyleSheet(
            f"font-family: 'Consolas', 'Courier New', monospace; "
            f"font-size: {FONT_SIZE.MD}px; "
            f"padding: {SPACING.SM}px;"
        )
        layout.addWidget(self._text_edit, stretch=1)

        # Status label
        self._status_lbl = QLabel("")
        self._status_lbl.setWordWrap(True)
        layout.addWidget(self._status_lbl)

        # Buttons
        btn_row = QHBoxLayout()

        example_btn = QPushButton("Isi Contoh")
        example_btn.setToolTip("Isi editor dengan istilah contoh untuk memulai")
        example_btn.clicked.connect(self._on_fill_example)
        btn_row.addWidget(example_btn)

        count_btn = QPushButton("Hitung")
        count_btn.clicked.connect(self._on_count)
        btn_row.addWidget(count_btn)

        btn_row.addStretch()

        cancel_btn = QPushButton("Batal")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        save_btn = QPushButton("Simpan")
        save_btn.setDefault(True)
        save_btn.clicked.connect(self._on_save)
        btn_row.addWidget(save_btn)

        layout.addLayout(btn_row)

    def _on_fill_example(self) -> None:
        """Fill the editor with example terms to help the user start."""
        example = (
            "# Contoh — ubah atau hapus sesuai kebutuhan Anda\n"
            "server\n"
            "log\n"
            "host\n"
            "backup\n"
            "INC\n"
            "TKT"
        )
        self._text_edit.setPlainText(example)
        self._status_lbl.setStyleSheet(f"color: {ColorPalette.GRAY_600.value};")
        self._status_lbl.setText(
            "Contoh diisi. Ubah sesuai kebutuhan, lalu klik Simpan."
        )

    def _load_existing(self) -> None:
        """Load existing terms into the text area."""
        terms = self._store.load()
        if terms:
            self._text_edit.setPlainText(deny_terms_to_text(terms))

    def _on_count(self) -> None:
        """Show how many valid terms are currently in the editor."""
        terms = parse_deny_text(self._text_edit.toPlainText())
        self._status_lbl.setStyleSheet(f"color: {ColorPalette.SUCCESS.value};")
        self._status_lbl.setText(f"✅ {len(terms)} istilah pengecualian.")

    def _on_save(self) -> None:
        """Save terms to the global store. Empty input is allowed."""
        text = self._text_edit.toPlainText()
        try:
            terms = save_global_deny_list_from_text(text)

            if not terms:
                QMessageBox.information(
                    self,
                    "Tersimpan",
                    "Tidak ada istilah pengecualian yang disimpan. "
                    "Deteksi standar tetap berjalan seperti biasa.",
                )
            else:
                QMessageBox.information(
                    self,
                    "Tersimpan",
                    f"{len(terms)} istilah pengecualian tersimpan dan akan "
                    f"dipakai untuk semua project.",
                )
            self.accept()
        except Exception as e:
            QMessageBox.critical(
                self,
                "Gagal Menyimpan",
                f"Tidak dapat menyimpan daftar pengecualian: {e}",
            )


__all__ = ["DenyListDialog"]
