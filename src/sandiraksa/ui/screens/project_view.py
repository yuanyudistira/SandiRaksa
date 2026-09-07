"""
Project View Screen.

Shows project details with file list and per-file actions.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QBrush
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from sandiraksa.app.i18n import tr
from sandiraksa.ui.theme import ColorPalette, FONT_SIZE, SPACING
from sandiraksa.ui.widgets import (
    EmptyState,
    FileDropZone,
    IconButton,
    SectionHeader,
)

if TYPE_CHECKING:
    pass


class ProjectViewScreen(QWidget):
    """Screen showing project details and file list."""

    # Signals
    files_added = Signal(list)
    file_removed = Signal(str)
    protect_file_requested = Signal(str)
    download_file_requested = Signal(str)
    restore_file_requested = Signal()  # Request to restore a file
    settings_requested = Signal()
    back_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._project_id: str | None = None
        self._project_name: str = ""
        self._files: list[dict] = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Setup the UI layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # Header
        header = QHBoxLayout()
        
        back_btn = QPushButton("← Kembali")
        back_btn.setFixedWidth(100)
        back_btn.clicked.connect(self.back_requested.emit)
        header.addWidget(back_btn)

        self._title = QLabel("")
        self._title.setStyleSheet("font-size: 24px; font-weight: bold;")
        header.addWidget(self._title)
        header.addStretch()

        settings_btn = QPushButton("⚙ Pengaturan")
        settings_btn.clicked.connect(self.settings_requested.emit)
        header.addWidget(settings_btn)

        layout.addLayout(header)

        # Main content - horizontal split
        content = QHBoxLayout()
        content.setSpacing(16)

        # Left: File list
        left_panel = QFrame()
        left_panel.setFrameStyle(QFrame.Shape.StyledPanel)
        left_panel.setStyleSheet("QFrame { background: white; border: 1px solid #e5e7eb; border-radius: 8px; }")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(12, 12, 12, 12)

        files_label = QLabel("📁 Daftar File")
        files_label.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 8px;")
        left_layout.addWidget(files_label)

        # File table
        self._file_table = QTableWidget()
        self._file_table.setColumnCount(5)
        self._file_table.setHorizontalHeaderLabels(["File", "Tipe", "Info", "Status", "Aksi"])
        self._file_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._file_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self._file_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self._file_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self._file_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self._file_table.setColumnWidth(1, 60)
        self._file_table.setColumnWidth(2, 100)
        self._file_table.setColumnWidth(3, 80)
        self._file_table.setColumnWidth(4, 90)
        self._file_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._file_table.setAlternatingRowColors(True)
        self._file_table.verticalHeader().setVisible(False)
        self._file_table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #e5e7eb;
                gridline-color: #f3f4f6;
                font-size: 12px;
            }
            QTableWidget::item {
                padding: 4px;
            }
            QHeaderView::section {
                background-color: #f9fafb;
                padding: 8px 4px;
                border: none;
                border-bottom: 1px solid #e5e7eb;
                font-weight: bold;
                font-size: 12px;
            }
        """)
        left_layout.addWidget(self._file_table)

        # Empty state
        self._files_empty = QLabel("Belum ada file. Seret file ke area sebelah kanan.")
        self._files_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._files_empty.setStyleSheet("color: #9ca3af; padding: 40px;")
        left_layout.addWidget(self._files_empty)

        content.addWidget(left_panel, stretch=2)

        # Right: Drop zone
        right_panel = QFrame()
        right_panel.setFrameStyle(QFrame.Shape.StyledPanel)
        right_panel.setStyleSheet("""
            QFrame { 
                background: #f0f9ff; 
                border: 2px dashed #93c5fd; 
                border-radius: 8px; 
            }
        """)
        right_layout = QVBoxLayout(right_panel)
        right_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        drop_icon = QLabel("📄")
        drop_icon.setStyleSheet("font-size: 48px;")
        drop_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        right_layout.addWidget(drop_icon)

        drop_text = QLabel("Seret & lepas file di sini")
        drop_text.setStyleSheet("font-size: 16px; font-weight: bold; color: #1e40af;")
        drop_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        right_layout.addWidget(drop_text)

        drop_hint = QLabel("atau klik untuk memilih file")
        drop_hint.setStyleSheet("color: #6b7280;")
        drop_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        right_layout.addWidget(drop_hint)

        # Make right panel clickable
        right_panel.mousePressEvent = self._on_drop_zone_click

        # Use FileDropZone for actual drop handling
        self._drop_zone = FileDropZone()
        self._drop_zone.files_dropped.connect(self._on_files_dropped)
        self._drop_zone.setVisible(False)  # Hidden, just for drop handling
        right_layout.addWidget(self._drop_zone)

        # Enable drops on right panel
        right_panel.setAcceptDrops(True)
        right_panel.dragEnterEvent = self._drop_zone.dragEnterEvent
        right_panel.dragLeaveEvent = self._drop_zone.dragLeaveEvent
        right_panel.dropEvent = self._drop_zone.dropEvent

        content.addWidget(right_panel, stretch=1)

        layout.addLayout(content, stretch=1)

        # Bottom bar
        bottom_bar = QHBoxLayout()
        
        self._summary_label = QLabel("Total: 0 file")
        self._summary_label.setStyleSheet("color: #6b7280;")
        bottom_bar.addWidget(self._summary_label)
        
        bottom_bar.addStretch()
        
        self._protect_all_btn = QPushButton("🔒 Proteksi Semua")
        self._protect_all_btn.setEnabled(False)
        self._protect_all_btn.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: white;
                font-weight: bold;
                padding: 10px 20px;
                border: none;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #1d4ed8;
            }
            QPushButton:disabled {
                background-color: #9ca3af;
            }
        """)
        self._protect_all_btn.clicked.connect(self._on_protect_all)
        bottom_bar.addWidget(self._protect_all_btn)
        
        # Restore button
        self._restore_btn = QPushButton("🔓 Pulihkan File")
        self._restore_btn.setStyleSheet("""
            QPushButton {
                background-color: #10b981;
                color: white;
                font-weight: bold;
                padding: 10px 20px;
                border: none;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #059669;
            }
        """)
        self._restore_btn.clicked.connect(self._on_restore_click)
        bottom_bar.addWidget(self._restore_btn)
        
        layout.addLayout(bottom_bar)

    def _on_drop_zone_click(self, event) -> None:
        """Handle click on drop zone to open file dialog."""
        self._drop_zone._open_file_dialog()

    def set_project(self, project_id: str, name: str) -> None:
        """Set the current project."""
        self._project_id = project_id
        self._project_name = name
        self._title.setText(name)
        
        # Clear files when switching project
        self._files = []
        self._refresh_file_list()

    def set_files(self, files: list[dict]) -> None:
        """Set the list of files."""
        self._files = files
        self._refresh_file_list()

    def _refresh_file_list(self) -> None:
        """Refresh the file list display."""
        has_files = bool(self._files)
        self._file_table.setVisible(has_files)
        self._files_empty.setVisible(not has_files)

        self._file_table.setRowCount(len(self._files))

        pending_count = 0
        protected_count = 0

        for row, file_info in enumerate(self._files):
            file_id = file_info["id"]
            status = file_info.get("status", "pending")
            file_format = file_info.get("format", "").lower()
            
            if status == "pending":
                pending_count += 1
            elif status == "protected":
                protected_count += 1

            self._file_table.setRowHeight(row, 45)

            # Column 0: File name
            icon = self._get_file_icon(file_format)
            name_item = QTableWidgetItem(f"{icon} {file_info.get('name', 'Unknown')}")
            name_item.setData(Qt.ItemDataRole.UserRole, file_id)
            self._file_table.setItem(row, 0, name_item)

            # Column 1: Format
            format_item = QTableWidgetItem(file_format.upper())
            format_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._file_table.setItem(row, 1, format_item)

            # Column 2: Info
            info_text = self._get_file_info_text(file_info)
            info_item = QTableWidgetItem(info_text)
            info_item.setForeground(QBrush(QColor("#6b7280")))
            self._file_table.setItem(row, 2, info_item)

            # Column 3: Status
            status_text, status_color = self._get_status_config(status)
            status_item = QTableWidgetItem(status_text)
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            status_item.setForeground(QBrush(QColor("white")))
            status_item.setBackground(QBrush(QColor(status_color)))
            self._file_table.setItem(row, 3, status_item)

            # Column 4: Action button
            btn = self._create_action_button(file_info)
            if btn:
                container = QWidget()
                layout = QHBoxLayout(container)
                layout.setContentsMargins(4, 4, 4, 4)
                layout.addWidget(btn)
                self._file_table.setCellWidget(row, 4, container)

        # Update summary
        total = len(self._files)
        self._summary_label.setText(
            f"Total: {total} file | Menunggu: {pending_count} | Terproteksi: {protected_count}"
        )
        
        # Enable protect all button
        can_protect = any(
            f.get("selected_columns") or f.get("format", "").lower() not in ("xlsx", "xls", "csv")
            for f in self._files
            if f.get("status") == "pending"
        )
        self._protect_all_btn.setEnabled(can_protect)

    def _get_file_icon(self, file_format: str) -> str:
        """Get icon for file format."""
        icons = {
            "xlsx": "📊", "xls": "📊", "csv": "📋",
            "docx": "📄", "doc": "📄",
            "pptx": "📽", "ppt": "📽",
            "txt": "📝", "pdf": "📕",
        }
        return icons.get(file_format, "📄")

    def _get_file_info_text(self, file_info: dict) -> str:
        """Get info text for file."""
        selected_columns = file_info.get("selected_columns")
        if selected_columns:
            return f"{len(selected_columns)} kolom"
        
        output_path = file_info.get("output_path")
        if output_path:
            return Path(output_path).name
        
        return "-"

    def _get_status_config(self, status: str) -> tuple[str, str]:
        """Get status text and color."""
        config = {
            "pending": ("Tunggu", "#6b7280"),
            "ready": ("Siap", "#0ea5e9"),
            "processing": ("Proses", "#f59e0b"),
            "protected": ("Selesai", "#10b981"),
            "error": ("Error", "#ef4444"),
        }
        return config.get(status, ("?", "#6b7280"))

    def _create_action_button(self, file_info: dict) -> QPushButton | None:
        """Create action button based on file status."""
        file_id = file_info["id"]
        status = file_info.get("status", "pending")
        file_format = file_info.get("format", "").lower()
        
        btn = QPushButton()
        btn.setFixedHeight(26)
        
        if status == "protected":
            btn.setText("Unduh")
            btn.setStyleSheet("""
                QPushButton { background: #10b981; color: white; padding: 2px 6px; 
                border: none; border-radius: 3px; font-size: 11px; font-weight: bold; }
                QPushButton:hover { background: #059669; }
            """)
            btn.clicked.connect(lambda: self.download_file_requested.emit(file_id))
            
        elif status == "processing":
            btn.setText("⏳")
            btn.setEnabled(False)
            btn.setStyleSheet("""
                QPushButton { background: #f59e0b; color: white; padding: 2px 6px;
                border: none; border-radius: 3px; font-size: 14px; }
            """)
            
        elif status == "pending":
            if file_format in ("xlsx", "xls", "csv"):
                if file_info.get("selected_columns"):
                    btn.setText("Proses")
                    btn.setStyleSheet("""
                        QPushButton { background: #2563eb; color: white; padding: 2px 6px;
                        border: none; border-radius: 3px; font-size: 11px; font-weight: bold; }
                        QPushButton:hover { background: #1d4ed8; }
                    """)
                    btn.clicked.connect(lambda: self.protect_file_requested.emit(file_id))
                else:
                    btn.setText("Kolom")
                    btn.setStyleSheet("""
                        QPushButton { background: #0ea5e9; color: white; padding: 2px 6px;
                        border: none; border-radius: 3px; font-size: 11px; font-weight: bold; }
                        QPushButton:hover { background: #0284c7; }
                    """)
                    btn.clicked.connect(lambda fid=file_id: self._on_select_columns(fid))
            else:
                btn.setText("Proses")
                btn.setStyleSheet("""
                    QPushButton { background: #2563eb; color: white; padding: 2px 6px;
                    border: none; border-radius: 3px; font-size: 11px; font-weight: bold; }
                    QPushButton:hover { background: #1d4ed8; }
                """)
                btn.clicked.connect(lambda: self.protect_file_requested.emit(file_id))
        
        elif status == "error":
            btn.setText("Ulang")
            btn.setStyleSheet("""
                QPushButton { background: #ef4444; color: white; padding: 2px 6px;
                border: none; border-radius: 3px; font-size: 11px; font-weight: bold; }
                QPushButton:hover { background: #dc2626; }
            """)
            btn.clicked.connect(lambda: self.protect_file_requested.emit(file_id))
        else:
            return None
            
        return btn

    def _on_files_dropped(self, files: list[Path]) -> None:
        """Handle files dropped."""
        self.files_added.emit(files)

    def _on_remove_file(self, file_id: str) -> None:
        """Handle file removal."""
        self.file_removed.emit(file_id)

    def _on_select_columns(self, file_id: str) -> None:
        """Handle column selection request."""
        file_info = next((f for f in self._files if f["id"] == file_id), None)
        if file_info:
            path = Path(file_info["path"])
            self.files_added.emit([path])

    def _on_protect_all(self) -> None:
        """Protect all ready files."""
        for file_info in self._files:
            if file_info.get("status") == "pending":
                if file_info.get("selected_columns") or file_info.get("format", "").lower() not in ("xlsx", "xls", "csv"):
                    self.protect_file_requested.emit(file_info["id"])

    def _on_restore_click(self) -> None:
        """Handle restore button click."""
        self.restore_file_requested.emit()

    def add_files(self, files: list[Path]) -> None:
        """Add files to the project view."""
        import uuid
        for file_path in files:
            self._files.append({
                "id": str(uuid.uuid4()),
                "name": file_path.name,
                "path": str(file_path),
                "format": file_path.suffix.lstrip(".").lower(),
                "status": "pending",
            })
        self._refresh_file_list()

    def remove_file(self, file_id: str) -> None:
        """Remove a file."""
        self._files = [f for f in self._files if f["id"] != file_id]
        self._refresh_file_list()

    def update_file_status(self, file_id: str, status: str, **kwargs) -> None:
        """Update status of a file."""
        for file_info in self._files:
            if file_info["id"] == file_id:
                file_info["status"] = status
                file_info.update(kwargs)
                break
        self._refresh_file_list()

    def get_file_info(self, file_id: str) -> dict | None:
        """Get file info by ID."""
        return next((f for f in self._files if f["id"] == file_id), None)


__all__ = ["ProjectViewScreen"]
