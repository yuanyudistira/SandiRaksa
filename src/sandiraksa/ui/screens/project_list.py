"""
Project List Screen.

Shows list of existing projects with search and sort options.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from sandiraksa.app.i18n import tr
from sandiraksa.ui.widgets import EmptyState

if TYPE_CHECKING:
    pass


class ProjectCard(QWidget):
    """Simple row displaying project summary."""

    clicked = Signal()
    delete_requested = Signal(str)  # project_id

    def __init__(
        self,
        project_id: str,
        name: str,
        file_count: int,
        last_modified: datetime | None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._project_id = project_id
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        # Simple row style
        self.setStyleSheet("""
            QWidget {
                background-color: white;
                border-bottom: 1px solid #e5e7eb;
            }
            QWidget:hover {
                background-color: #f9fafb;
            }
        """)
        self.setFixedHeight(48)

        # Single row layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(16)

        # Project name
        name_label = QLabel(name)
        name_label.setStyleSheet("""
            font-size: 14px;
            font-weight: 500;
            color: #1f2937;
            background: transparent;
            border: none;
        """)
        name_label.setMinimumWidth(200)
        layout.addWidget(name_label)

        # File count
        file_label = QLabel(f"{file_count} file")
        file_label.setStyleSheet("""
            color: #6b7280;
            font-size: 13px;
            background: transparent;
            border: none;
        """)
        file_label.setFixedWidth(60)
        layout.addWidget(file_label)

        layout.addStretch()

        # Last modified
        if last_modified:
            date_str = last_modified.strftime("%Y-%m-%d %H:%M")
        else:
            date_str = "-"
        modified_label = QLabel(date_str)
        modified_label.setStyleSheet("""
            color: #9ca3af;
            font-size: 12px;
            background: transparent;
            border: none;
        """)
        layout.addWidget(modified_label)

        # Delete button container for alignment
        delete_container = QWidget()
        delete_container.setFixedWidth(60)
        delete_container.setStyleSheet("background: transparent; border: none;")
        delete_layout = QHBoxLayout(delete_container)
        delete_layout.setContentsMargins(0, 0, 0, 0)
        delete_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        delete_btn = QPushButton("Hapus")
        delete_btn.setFixedHeight(26)
        delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #f3f4f6;
                border: 1px solid #e5e7eb;
                border-radius: 4px;
                font-size: 11px;
                color: #6b7280;
                padding: 0 8px;
            }
            QPushButton:hover {
                background-color: #fee2e2;
                border-color: #fecaca;
                color: #ef4444;
            }
        """)
        delete_btn.clicked.connect(self._on_delete_click)
        delete_layout.addWidget(delete_btn)
        layout.addWidget(delete_container)

    def _on_delete_click(self) -> None:
        """Handle delete button click."""
        self.delete_requested.emit(self._project_id)

    def mousePressEvent(self, event) -> None:
        """Handle mouse click on row."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    @property
    def project_id(self) -> str:
        """Get project ID."""
        return self._project_id


class ProjectListScreen(QWidget):
    """
    Screen showing list of projects.

    Emits signals when user wants to create, open, or delete a project.
    """

    project_selected = Signal(str)  # project_id
    new_project_requested = Signal()
    project_delete_requested = Signal(str)  # project_id

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._projects: list[dict] = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Setup the UI layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Header with title and new project button
        header = QHBoxLayout()
        
        title_label = QLabel(tr("project_list.title"))
        title_label.setStyleSheet("""
            font-size: 24px;
            font-weight: 700;
            color: #1f2937;
        """)
        header.addWidget(title_label)
        
        header.addStretch()
        
        new_btn = QPushButton(f"+ {tr('project_list.new_project')}")
        new_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        new_btn.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6;
                color: white;
                font-weight: 600;
                font-size: 14px;
                padding: 10px 20px;
                border: none;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #2563eb;
            }
        """)
        new_btn.clicked.connect(self._on_new_project)
        header.addWidget(new_btn)
        
        layout.addLayout(header)

        # Search and sort bar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(12)

        self._search = QLineEdit()
        self._search.setPlaceholderText(tr("project_list.search_placeholder"))
        self._search.setStyleSheet("""
            QLineEdit {
                padding: 10px 12px;
                border: 1px solid #d1d5db;
                border-radius: 6px;
                font-size: 14px;
                background-color: white;
            }
            QLineEdit:focus {
                border-color: #3b82f6;
                outline: none;
            }
        """)
        self._search.textChanged.connect(self._filter_projects)
        toolbar.addWidget(self._search, stretch=1)

        sort_label = QLabel(tr("project_list.sort_by"))
        sort_label.setStyleSheet("color: #6b7280; font-size: 14px;")
        toolbar.addWidget(sort_label)

        self._sort_combo = QComboBox()
        self._sort_combo.addItem(tr("project_list.sort_date"), "date")
        self._sort_combo.addItem(tr("project_list.sort_name"), "name")
        self._sort_combo.addItem(tr("project_list.sort_files"), "files")
        self._sort_combo.setStyleSheet("""
            QComboBox {
                padding: 8px 12px;
                border: 1px solid #d1d5db;
                border-radius: 6px;
                font-size: 14px;
                background-color: white;
                min-width: 120px;
            }
            QComboBox:hover {
                border-color: #9ca3af;
            }
            QComboBox::drop-down {
                border: none;
                padding-right: 8px;
            }
        """)
        self._sort_combo.currentIndexChanged.connect(self._sort_projects)
        toolbar.addWidget(self._sort_combo)

        layout.addLayout(toolbar)

        # Container for project list with header
        list_container = QWidget()
        list_container.setStyleSheet("""
            QWidget {
                background-color: white;
                border: 1px solid #e5e7eb;
                border-radius: 8px;
            }
        """)
        list_layout = QVBoxLayout(list_container)
        list_layout.setContentsMargins(0, 0, 0, 0)
        list_layout.setSpacing(0)
        
        # Column header
        header_row = QWidget()
        header_row.setFixedHeight(40)
        header_row.setStyleSheet("""
            background-color: #f9fafb;
            border-bottom: 1px solid #e5e7eb;
            border-top-left-radius: 8px;
            border-top-right-radius: 8px;
        """)
        header_layout = QHBoxLayout(header_row)
        header_layout.setContentsMargins(16, 0, 16, 0)
        header_layout.setSpacing(16)
        
        name_header = QLabel("Nama Proyek")
        name_header.setStyleSheet("font-size: 12px; font-weight: 600; color: #6b7280; background: transparent; border: none;")
        name_header.setMinimumWidth(200)
        header_layout.addWidget(name_header)
        
        files_header = QLabel("File")
        files_header.setStyleSheet("font-size: 12px; font-weight: 600; color: #6b7280; background: transparent; border: none;")
        files_header.setFixedWidth(60)
        header_layout.addWidget(files_header)
        
        header_layout.addStretch()
        
        date_header = QLabel("Terakhir Diubah")
        date_header.setStyleSheet("font-size: 12px; font-weight: 600; color: #6b7280; background: transparent; border: none;")
        header_layout.addWidget(date_header)
        
        # Header for action column
        action_header = QLabel("Aksi")
        action_header.setStyleSheet("font-size: 12px; font-weight: 600; color: #6b7280; background: transparent; border: none;")
        action_header.setFixedWidth(60)
        action_header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(action_header)
        
        list_layout.addWidget(header_row)

        # Scroll area for project rows
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent; border: none;")

        self._scroll_content = QWidget()
        self._scroll_content.setStyleSheet("background: white;")
        self._projects_layout = QVBoxLayout(self._scroll_content)
        self._projects_layout.setContentsMargins(0, 0, 0, 0)
        self._projects_layout.setSpacing(0)
        self._projects_layout.addStretch()

        scroll.setWidget(self._scroll_content)
        list_layout.addWidget(scroll, stretch=1)
        
        layout.addWidget(list_container, stretch=1)

        # Empty state (shown when no projects)
        self._empty_state = EmptyState(
            title=tr("project_list.empty"),
            description=tr("project_list.empty_hint"),
            action_text=tr("project_list.new_project"),
            action_callback=self._on_new_project,
            icon="📁",
        )
        layout.addWidget(self._empty_state, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # Store reference to list container
        self._list_container = list_container

    def set_projects(self, projects: list[dict]) -> None:
        """
        Set the list of projects to display.

        Args:
            projects: List of project dicts with id, name, file_count, updated_at
        """
        self._projects = projects
        self._refresh_display()

    def _refresh_display(self) -> None:
        """Refresh the project list display."""
        # Clear existing rows - collect widgets first, then delete
        widgets_to_remove = []
        while self._projects_layout.count() > 1:  # Keep stretch
            item = self._projects_layout.takeAt(0)
            if item.widget():
                widgets_to_remove.append(item.widget())
        
        # Schedule deletion after current event processing
        for widget in widgets_to_remove:
            widget.setParent(None)
            widget.deleteLater()

        # Show/hide empty state
        has_projects = bool(self._projects)
        self._empty_state.setVisible(not has_projects)
        self._list_container.setVisible(has_projects)

        if not has_projects:
            return

        # Filter by search
        search_text = self._search.text().lower()
        filtered = [
            p for p in self._projects
            if search_text in p.get("name", "").lower()
        ]

        # Sort
        sort_key = self._sort_combo.currentData()
        if sort_key == "name":
            filtered.sort(key=lambda p: p.get("name", "").lower())
        elif sort_key == "files":
            filtered.sort(key=lambda p: p.get("file_count", 0), reverse=True)
        else:  # date
            filtered.sort(key=lambda p: p.get("updated_at", ""), reverse=True)

        # Create rows
        for project in filtered:
            updated_at = None
            if project.get("updated_at"):
                try:
                    updated_at = datetime.fromisoformat(project["updated_at"])
                except (ValueError, TypeError):
                    pass

            row = ProjectCard(
                project_id=project["id"],
                name=project.get("name", "Untitled"),
                file_count=project.get("file_count", 0),
                last_modified=updated_at,
            )
            row.clicked.connect(lambda pid=project["id"]: self._on_project_selected(pid))
            row.delete_requested.connect(self._on_delete_requested)
            self._projects_layout.insertWidget(
                self._projects_layout.count() - 1, row
            )

    def _filter_projects(self) -> None:
        """Filter projects by search text."""
        self._refresh_display()

    def _sort_projects(self) -> None:
        """Sort projects by selected criteria."""
        self._refresh_display()

    def _on_new_project(self) -> None:
        """Handle new project button."""
        self.new_project_requested.emit()

    def _on_project_selected(self, project_id: str) -> None:
        """Handle project card click."""
        self.project_selected.emit(project_id)

    def _on_delete_requested(self, project_id: str) -> None:
        """Handle delete button click."""
        # Find project name
        project = next((p for p in self._projects if p["id"] == project_id), None)
        name = project.get("name", "Untitled") if project else "Untitled"

        # Confirm deletion
        result = QMessageBox.warning(
            self,
            tr("dialogs.confirm_title"),
            f"{tr('project_list.delete_confirm', name=name)}\n\n"
            f"{tr('project_list.delete_warning')}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if result == QMessageBox.StandardButton.Yes:
            self.project_delete_requested.emit(project_id)


__all__ = ["ProjectListScreen"]
