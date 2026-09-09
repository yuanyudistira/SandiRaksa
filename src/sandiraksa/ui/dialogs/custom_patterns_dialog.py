"""
Custom Patterns Dialog.

Lets the user define global custom detection patterns (e.g. hospital-specific
Medical Record number formats) via a free-text area. Patterns are stored
globally and apply to all projects.

Input format (one per line):
    LABEL: pattern

Example:
    MEDICAL_RECORD: MR-\\d{6}
    ROOM: (?:Kamar|Room)\\s?\\d+

Lines starting with '#' are comments.
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
from sandiraksa.detection.custom_patterns import (
    CustomPatternStore,
    parse_patterns_text,
    patterns_to_text,
    save_global_patterns_from_text,
)


PLACEHOLDER = (
    "# Kosongkan saja jika tidak perlu — deteksi standar tetap berjalan.\n"
    "#\n"
    "# Tulis satu pola per baris dengan format:  NAMA: pola\n"
    "#\n"
    "# Contoh (silakan hapus dan ganti dengan milik Anda):\n"
    "REKAM_MEDIS: MR-\\d{6}\n"
    "NO_KAMAR: (?:Kamar|Room)\\s?\\d+\n"
    "ID_PEGAWAI: EMP-\\d{4,6}"
)

HELP_TEXT = (
    "Buat pola pendeteksian Anda sendiri, misalnya format Nomor Rekam Medis "
    "yang berbeda di tiap rumah sakit. Pola ini berlaku untuk SEMUA project."
)

# A concrete, friendly example block shown above the editor so users are not
# confused about the format.
EXAMPLE_HTML = (
    "<b>Format:</b> <code>NAMA: pola</code> &nbsp;(satu pola per baris)<br>"
    "<b>Contoh:</b><br>"
    "&nbsp;&nbsp;<code>REKAM_MEDIS: MR-\\d{6}</code> "
    "→ mendeteksi <i>MR-004521</i><br>"
    "&nbsp;&nbsp;<code>NO_KAMAR: (?:Kamar|Room)\\s?\\d+</code> "
    "→ mendeteksi <i>Kamar 12</i>, <i>Room 5</i><br>"
    "&nbsp;&nbsp;<code>NO_BPJS: \\b\\d{13}\\b</code> "
    "→ mendeteksi nomor 13 digit<br>"
    "<span style='color:#64748b'>Pola ditulis sebagai <b>regular expression</b>. "
    "Baris diawali <code>#</code> dianggap komentar. "
    "Boleh dikosongkan (opsional).</span>"
)


class CustomPatternsDialog(QDialog):
    """Dialog for editing global custom detection patterns."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._store = CustomPatternStore()
        self._setup_ui()
        self._load_existing()

    def _setup_ui(self) -> None:
        self.setWindowTitle("Pola Kustom")
        self.setMinimumSize(560, 480)

        layout = QVBoxLayout(self)
        layout.setSpacing(SPACING.MD)
        layout.setContentsMargins(SPACING.XL, SPACING.XL, SPACING.XL, SPACING.XL)

        # Title
        title = QLabel("🧩 Pola Kustom (Global)")
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

        # Example panel (rich text) so users understand the format at a glance
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

        # Editor label with "optional" hint
        editor_lbl = QLabel("Pola Anda (opsional — boleh dikosongkan):")
        editor_lbl.setStyleSheet(
            f"color: {ColorPalette.GRAY_700.value}; font-weight: bold;"
        )
        layout.addWidget(editor_lbl)

        # Text area for patterns
        self._text_edit = QPlainTextEdit()
        self._text_edit.setPlaceholderText(PLACEHOLDER)
        self._text_edit.setStyleSheet(
            f"font-family: 'Consolas', 'Courier New', monospace; "
            f"font-size: {FONT_SIZE.MD}px; "
            f"padding: {SPACING.SM}px;"
        )
        layout.addWidget(self._text_edit, stretch=1)

        # Validation status label
        self._status_lbl = QLabel("")
        self._status_lbl.setWordWrap(True)
        layout.addWidget(self._status_lbl)

        # Buttons
        btn_row = QHBoxLayout()

        example_btn = QPushButton("Isi Contoh")
        example_btn.setToolTip("Isi editor dengan pola contoh untuk memulai")
        example_btn.clicked.connect(self._on_fill_example)
        btn_row.addWidget(example_btn)

        test_btn = QPushButton("Validasi")
        test_btn.clicked.connect(self._on_validate)
        btn_row.addWidget(test_btn)

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
        """Fill the editor with example patterns to help the user start."""
        example = (
            "# Contoh — ubah atau hapus sesuai kebutuhan Anda\n"
            "REKAM_MEDIS: MR-\\d{6}\n"
            "NO_KAMAR: (?:Kamar|Room)\\s?\\d+\n"
            "ID_PEGAWAI: EMP-\\d{4,6}"
        )
        self._text_edit.setPlainText(example)
        self._status_lbl.setStyleSheet(f"color: {ColorPalette.GRAY_600.value};")
        self._status_lbl.setText(
            "Contoh diisi. Ubah sesuai kebutuhan, lalu klik Validasi atau Simpan."
        )

    def _load_existing(self) -> None:
        """Load existing patterns into the text area."""
        patterns = self._store.load()
        if patterns:
            self._text_edit.setPlainText(patterns_to_text(patterns))

    def _on_validate(self) -> None:
        """Validate patterns and show a summary without saving."""
        text = self._text_edit.toPlainText()
        patterns = parse_patterns_text(text)

        # Count raw non-comment lines to detect skipped/invalid lines
        raw_lines = [
            ln.strip() for ln in text.splitlines()
            if ln.strip() and not ln.strip().startswith("#")
        ]
        valid = len(patterns)
        skipped = len(raw_lines) - valid

        if skipped > 0:
            self._status_lbl.setStyleSheet(
                f"color: {ColorPalette.WARNING.value};"
            )
            self._status_lbl.setText(
                f"⚠️ {valid} pola valid, {skipped} baris dilewati (pola tidak valid)."
            )
        else:
            self._status_lbl.setStyleSheet(
                f"color: {ColorPalette.SUCCESS.value};"
            )
            self._status_lbl.setText(f"✅ {valid} pola valid.")

    def _on_save(self) -> None:
        """Save patterns to the global store. Empty input is allowed."""
        text = self._text_edit.toPlainText()
        try:
            patterns = save_global_patterns_from_text(text)

            if not patterns:
                # Empty / no valid patterns is perfectly fine - not a blocker.
                QMessageBox.information(
                    self,
                    "Tersimpan",
                    "Tidak ada pola kustom yang disimpan. "
                    "Deteksi standar tetap berjalan seperti biasa.",
                )
            else:
                QMessageBox.information(
                    self,
                    "Tersimpan",
                    f"{len(patterns)} pola kustom tersimpan dan akan dipakai "
                    f"untuk semua project.",
                )
            self.accept()
        except Exception as e:
            QMessageBox.critical(
                self,
                "Gagal Menyimpan",
                f"Tidak dapat menyimpan pola: {e}",
            )


__all__ = ["CustomPatternsDialog"]
