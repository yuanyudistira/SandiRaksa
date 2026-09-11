"""
Main window for SandiRaksa application.

This module contains the main window with stacked page navigation.
"""

from __future__ import annotations

from enum import Enum, auto
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QLabel,
    QMainWindow,
    QStackedWidget,
    QWidget,
)

from sandiraksa.app.i18n import Language, Translator, get_translator, tr
from sandiraksa.ui.theme import STYLESHEET
from sandiraksa.version import __version__

# Pre-import heavy modules to avoid GC issues during Qt event loop
from sandiraksa.protection.txt_protector import TxtProtector as _TxtProtector

# Pre-import openpyxl to avoid GC crash during Excel file analysis
try:
    import openpyxl as _openpyxl
except ImportError:
    _openpyxl = None

# Pre-import csv/codecs to avoid GC crash during CSV file analysis
import csv as _csv
import codecs as _codecs

# Pre-import python-docx and python-pptx to avoid GC crash
try:
    import docx as _docx
except ImportError:
    _docx = None

try:
    import pptx as _pptx
except ImportError:
    _pptx = None

# Pre-import file analysis functions to avoid lazy loading during Qt events
from sandiraksa.ui.dialogs.column_selection import (
    analyze_csv_file as _analyze_csv_file,
    analyze_excel_file as _analyze_excel_file,
)

# Pre-import protectors
from sandiraksa.protection.docx_protector import DocxProtector as _DocxProtector
from sandiraksa.protection.pptx_protector import PptxProtector as _PptxProtector

if TYPE_CHECKING:
    pass


class Page(Enum):
    """Available pages in the application."""

    PROJECT_LIST = auto()
    PROJECT_VIEW = auto()
    SCAN_PROGRESS = auto()
    FINDINGS_REVIEW = auto()
    RESULTS_VIEW = auto()
    RESTORE_VIEW = auto()


class MainWindow(QMainWindow):
    """Main application window with stacked page navigation."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._translator = get_translator()
        self._pages: dict[Page, QWidget] = {}
        self._current_project_id: str | None = None
        # Keep reference to active dialog to prevent premature cleanup
        self._active_dialog = None
        # Background scan worker + its thread (None when no scan is running).
        self._scan_thread = None
        self._scan_worker = None

        self._setup_window()
        self._create_menus()
        self._create_central_widget()
        self._create_status_bar()
        self._connect_language_changes()

    def _setup_window(self) -> None:
        """Configure window properties."""
        self.setWindowTitle(f"SandiRaksa v{__version__}")
        self.setMinimumSize(1024, 768)
        self.resize(1280, 800)
        self.setStyleSheet(STYLESHEET)

    def _create_menus(self) -> None:
        """Create the application menu bar."""
        menubar = self.menuBar()
        assert menubar is not None

        # File menu
        file_menu = menubar.addMenu(tr("menu.file"))
        assert file_menu is not None

        self._new_project_action = QAction(tr("menu.new_project"), self)
        self._new_project_action.setShortcut("Ctrl+N")
        self._new_project_action.triggered.connect(self._on_new_project)
        file_menu.addAction(self._new_project_action)

        self._open_project_action = QAction(tr("menu.open_project"), self)
        self._open_project_action.setShortcut("Ctrl+O")
        file_menu.addAction(self._open_project_action)

        file_menu.addSeparator()

        self._exit_action = QAction(tr("menu.exit"), self)
        self._exit_action.setShortcut("Ctrl+Q")
        self._exit_action.triggered.connect(self.close)
        file_menu.addAction(self._exit_action)

        # Settings menu
        settings_menu = menubar.addMenu(tr("menu.settings"))
        assert settings_menu is not None

        # Language submenu
        language_menu = settings_menu.addMenu(tr("menu.language"))
        assert language_menu is not None

        self._lang_id_action = QAction("Bahasa Indonesia", self)
        self._lang_id_action.setCheckable(True)
        self._lang_id_action.triggered.connect(
            lambda: self._set_language(Language.INDONESIAN)
        )
        language_menu.addAction(self._lang_id_action)

        self._lang_en_action = QAction("English", self)
        self._lang_en_action.setCheckable(True)
        self._lang_en_action.triggered.connect(
            lambda: self._set_language(Language.ENGLISH)
        )
        language_menu.addAction(self._lang_en_action)

        self._update_language_check()

        # Custom patterns (global)
        settings_menu.addSeparator()
        self._custom_patterns_action = QAction("Pola Kustom...", self)
        self._custom_patterns_action.triggered.connect(self._on_custom_patterns)
        settings_menu.addAction(self._custom_patterns_action)

        # Deny-list / exclusion terms (global)
        self._deny_list_action = QAction("Daftar Pengecualian...", self)
        self._deny_list_action.triggered.connect(self._on_deny_list)
        settings_menu.addAction(self._deny_list_action)

        # Help menu
        help_menu = menubar.addMenu(tr("menu.help"))
        assert help_menu is not None

        self._help_action = QAction(tr("menu.help_contents"), self)
        self._help_action.setShortcut("F1")
        self._help_action.triggered.connect(self._show_help)
        help_menu.addAction(self._help_action)

        self._docs_action = QAction(tr("menu.documentation"), self)
        self._docs_action.triggered.connect(self._show_docs)
        help_menu.addAction(self._docs_action)

        help_menu.addSeparator()

        self._contact_action = QAction(tr("menu.contact"), self)
        self._contact_action.triggered.connect(self._show_contact)
        help_menu.addAction(self._contact_action)

        self._donate_action = QAction(tr("menu.donate"), self)
        self._donate_action.triggered.connect(self._show_donate)
        help_menu.addAction(self._donate_action)

        help_menu.addSeparator()

        self._about_action = QAction(tr("menu.about"), self)
        self._about_action.triggered.connect(self._show_about)
        help_menu.addAction(self._about_action)

    def _create_central_widget(self) -> None:
        """Create the central stacked widget for page navigation."""
        self._stack = QStackedWidget()
        self.setCentralWidget(self._stack)

        # Create pages lazily on first access
        self._init_pages()

        # Start with project list
        self.navigate_to(Page.PROJECT_LIST)

    def _init_pages(self) -> None:
        """Initialize all pages."""
        from sandiraksa.ui.screens import (
            FindingsReviewScreen,
            ProjectListScreen,
            ProjectViewScreen,
            RestoreViewScreen,
            ResultsViewScreen,
            ScanProgressScreen,
        )

        # Project list
        project_list = ProjectListScreen()
        project_list.project_selected.connect(self._on_project_selected)
        project_list.new_project_requested.connect(self._on_new_project)
        project_list.project_delete_requested.connect(self._on_project_delete)
        self._pages[Page.PROJECT_LIST] = project_list
        self._stack.addWidget(project_list)

        # Project view
        project_view = ProjectViewScreen()
        project_view.back_requested.connect(lambda: self.navigate_to(Page.PROJECT_LIST))
        project_view.settings_requested.connect(self._on_project_settings)
        project_view.files_added.connect(self._on_files_added)
        project_view.file_removed.connect(self._on_file_removed)
        project_view.protect_file_requested.connect(self._on_protect_file)
        project_view.download_file_requested.connect(self._on_download_file)
        project_view.restore_file_requested.connect(self._on_restore_file)
        self._pages[Page.PROJECT_VIEW] = project_view
        self._stack.addWidget(project_view)

        # Scan progress
        scan_progress = ScanProgressScreen()
        scan_progress.scan_complete.connect(self._on_scan_complete)
        scan_progress.cancel_requested.connect(self._on_scan_cancelled)
        self._pages[Page.SCAN_PROGRESS] = scan_progress
        self._stack.addWidget(scan_progress)

        # Findings review
        findings_review = FindingsReviewScreen()
        findings_review.back_requested.connect(lambda: self.navigate_to(Page.PROJECT_VIEW))
        findings_review.apply_treatments.connect(self._on_apply_treatments)
        self._pages[Page.FINDINGS_REVIEW] = findings_review
        self._stack.addWidget(findings_review)

        # Results view
        results_view = ResultsViewScreen()
        results_view.back_requested.connect(lambda: self.navigate_to(Page.FINDINGS_REVIEW))
        results_view.done_requested.connect(lambda: self.navigate_to(Page.PROJECT_LIST))
        self._pages[Page.RESULTS_VIEW] = results_view
        self._stack.addWidget(results_view)

        # Restore view
        restore_view = RestoreViewScreen()
        restore_view.back_requested.connect(lambda: self.navigate_to(Page.PROJECT_VIEW))
        restore_view.restore_requested.connect(self._on_restore_requested)
        self._pages[Page.RESTORE_VIEW] = restore_view
        self._stack.addWidget(restore_view)

    def _create_status_bar(self) -> None:
        """Create the status bar."""
        status_bar = self.statusBar()
        assert status_bar is not None
        status_bar.showMessage(tr("status.ready"))

        # Persistent compliance disclaimer shown in the footer. Added as a
        # permanent widget so transient showMessage() calls don't clear it.
        self._disclaimer_label = QLabel(tr("footer.disclaimer"))
        self._disclaimer_label.setWordWrap(False)
        self._disclaimer_label.setStyleSheet(
            "color: #b45309; font-weight: 600; padding: 0 8px;"
        )
        status_bar.addPermanentWidget(self._disclaimer_label)

    def _connect_language_changes(self) -> None:
        """Connect to language change signal."""
        self._translator.language_changed.connect(self._on_language_changed)

    def _on_language_changed(self, language: str) -> None:
        """Handle language change."""
        self._update_menus()
        self._update_status_bar()
        self._update_language_check()

    def _update_menus(self) -> None:
        """Update menu text after language change."""
        self._new_project_action.setText(tr("menu.new_project"))
        self._open_project_action.setText(tr("menu.open_project"))
        self._exit_action.setText(tr("menu.exit"))
        self._help_action.setText(tr("menu.help_contents"))
        self._docs_action.setText(tr("menu.documentation"))
        self._contact_action.setText(tr("menu.contact"))
        self._donate_action.setText(tr("menu.donate"))
        self._about_action.setText(tr("menu.about"))

    def _update_status_bar(self) -> None:
        """Update status bar text."""
        status_bar = self.statusBar()
        if status_bar:
            status_bar.showMessage(tr("status.ready"))
        if getattr(self, "_disclaimer_label", None) is not None:
            self._disclaimer_label.setText(tr("footer.disclaimer"))

    def _update_language_check(self) -> None:
        """Update language menu check marks."""
        current = self._translator.current_language
        self._lang_id_action.setChecked(current == Language.INDONESIAN)
        self._lang_en_action.setChecked(current == Language.ENGLISH)

    def _set_language(self, language: Language) -> None:
        """Set application language."""
        self._translator.set_language(language)

    def navigate_to(self, page: Page) -> None:
        """
        Navigate to a specific page.

        Args:
            page: Page to navigate to.
        """
        if page in self._pages:
            # Load projects from database when navigating to project list
            if page == Page.PROJECT_LIST:
                self._load_projects_from_db()
            
            self._stack.setCurrentWidget(self._pages[page])

    def _load_projects_from_db(self) -> None:
        """Load projects from database and update project list screen."""
        from sandiraksa.storage.repositories import ProjectRepository, FileRepository
        from sandiraksa.security.vault import get_project_vault
        from sandiraksa.security.key_store import get_key_manager
        
        try:
            repo = ProjectRepository()
            file_repo = FileRepository()
            records = repo.get_all()
            
            # Decrypt project names and convert to format expected by ProjectListScreen
            project_list = []
            
            for record in records:
                try:
                    # Decrypt name with same context as encrypt
                    vault = get_project_vault(record.id)
                    project_name = vault.decrypt_string(
                        record.name_enc,
                        table="projects",
                        row_id=record.id,
                        field="name_enc"
                    )
                except Exception as decrypt_err:
                    print(f"Error decrypting project name: {decrypt_err}")
                    project_name = f"Project {record.id[:8]}"
                
                # Count files for this project
                try:
                    files = file_repo.get_by_project(record.id)
                    file_count = len(files)
                except Exception:
                    file_count = 0
                
                project_list.append({
                    "id": record.id,
                    "name": project_name,
                    "file_count": file_count,
                    "updated_at": record.updated_at or "",
                })
            
            project_list_screen = self._pages.get(Page.PROJECT_LIST)
            if project_list_screen:
                project_list_screen.set_projects(project_list)
                
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"ERROR loading projects: {e}")

    def _on_new_project(self) -> None:
        """Handle new project creation."""
        import traceback
        from sandiraksa.ui.dialogs import ProjectSettingsDialog

        try:
            # Create new dialog each time - don't cleanup old one manually
            # Qt will handle memory when parent window closes
            dialog = ProjectSettingsDialog(parent=self)
            
            if dialog.exec():
                settings = dialog.get_settings()
                
                # Save project to database with all settings
                project_id = self._create_project_in_db(settings)
                
                self._current_project_id = project_id
                
                project_name = settings.get("name") or "Untitled Project"
                
                # Set project in project view
                project_view = self._pages.get(Page.PROJECT_VIEW)
                if project_view:
                    project_view.set_project(project_id, project_name)
                    project_view._files = []  # Clear files for new project
                    project_view._refresh_file_list()
                
                self.navigate_to(Page.PROJECT_VIEW)
                
        except Exception as e:
            traceback.print_exc()
            print(f"ERROR in _on_new_project: {e}")

    def _create_project_in_db(self, settings: dict) -> str:
        """Create a new project in the database and return its ID."""
        from sandiraksa.storage.repositories import ProjectRepository
        from sandiraksa.security.vault import get_project_vault
        from sandiraksa.security.key_store import get_key_manager
        import uuid
        import json
        
        project_name = settings.get("name") or "Untitled Project"
        description = settings.get("description", "")
        profile_id = settings.get("profile", "standard")
        
        # Additional settings to store as encrypted JSON
        extra_settings = {
            "entity_types": settings.get("entity_types", []),
            "output_folder": settings.get("output_folder", ""),
            "filename_suffix": settings.get("filename_suffix", "_protected"),
        }
        
        # Generate project ID first so we can create encryption key
        project_id = str(uuid.uuid4())
        
        # Ensure project key exists (this creates it if needed)
        key_manager = get_key_manager()
        key_manager.get_project_key(project_id)
        
        # Get vault for encryption
        vault = get_project_vault(project_id)
        
        # Encrypt project name
        name_enc = vault.encrypt(
            project_name, 
            table="projects", 
            row_id=project_id, 
            field="name_enc"
        )
        
        # Encrypt description if provided
        description_enc = None
        if description:
            description_enc = vault.encrypt(
                description,
                table="projects",
                row_id=project_id,
                field="description_enc"
            )
        
        # Encrypt extra settings as JSON
        settings_json = json.dumps(extra_settings)
        settings_enc = vault.encrypt(
            settings_json,
            table="projects",
            row_id=project_id,
            field="settings_enc"
        )
        
        # Create project record with our pre-generated ID
        repo = ProjectRepository()
        record = repo.create_with_id(
            project_id=project_id,
            name_enc=name_enc,
            profile_id=profile_id,
            description_enc=description_enc,
            settings_enc=settings_enc,
        )
        
        return record.id

    def _on_project_selected(self, project_id: str) -> None:
        """Handle project selection."""
        from sandiraksa.storage.repositories import ProjectRepository, FileRepository
        from sandiraksa.security.vault import get_project_vault
        
        self._current_project_id = project_id
        
        # Load project from database
        try:
            repo = ProjectRepository()
            record = repo.get_by_id(project_id)
            
            # Decrypt project name with same context as encrypt
            vault = get_project_vault(project_id)
            project_name = vault.decrypt_string(
                record.name_enc,
                table="projects",
                row_id=project_id,
                field="name_enc"
            )
        except Exception as e:
            print(f"Error loading project: {e}")
            project_name = f"Project {project_id[:8]}"
        
        project_view = self._pages.get(Page.PROJECT_VIEW)
        if project_view:
            project_view.set_project(project_id, project_name)
            
            # Load files from database
            try:
                file_repo = FileRepository()
                file_records = file_repo.get_by_project(project_id)
                
                # Convert to UI format
                files = []
                for fr in file_records:
                    try:
                        filename = vault.decrypt_string(
                            fr.filename_enc,
                            table="files",
                            row_id="temp",
                            field="filename_enc"
                        )
                        source_path = ""
                        if fr.source_path_enc:
                            source_path = vault.decrypt_string(
                                fr.source_path_enc,
                                table="files",
                                row_id="temp",
                                field="source_path_enc"
                            )
                        
                        # Load metadata (selected_columns, detected_entities)
                        selected_columns = None
                        detected_entities = None
                        if fr.metadata_enc:
                            try:
                                import json
                                metadata_json = vault.decrypt_string(
                                    fr.metadata_enc,
                                    table="files",
                                    row_id="temp",
                                    field="metadata_enc"
                                )
                                metadata = json.loads(metadata_json)
                                selected_columns = self._rehydrate_columns(
                                    metadata.get("selected_columns")
                                )
                                detected_entities = metadata.get("detected_entities")
                            except Exception as meta_err:
                                print(f"Error loading metadata for {fr.id}: {meta_err}")
                        
                        files.append({
                            "id": fr.id,
                            "name": filename,
                            "path": source_path,
                            "format": fr.extension,
                            "status": fr.status,
                            "selected_columns": selected_columns,
                            "detected_entities": detected_entities,
                        })
                    except Exception as decrypt_err:
                        print(f"Error decrypting file {fr.id}: {decrypt_err}")
                
                project_view._files = files
                project_view._refresh_file_list()
                print(f"DEBUG: Loaded {len(files)} files from DB")
                
            except Exception as e:
                print(f"Error loading files: {e}")
        
        self.navigate_to(Page.PROJECT_VIEW)

    def _on_project_delete(self, project_id: str) -> None:
        """Handle project deletion."""
        from sandiraksa.storage.repositories import ProjectRepository, TokenMappingRepository
        
        try:
            # Delete tokens first (foreign key constraint)
            token_repo = TokenMappingRepository()
            token_repo.delete_by_project(project_id)
            
            # Delete project
            project_repo = ProjectRepository()
            project_repo.delete(project_id)
            
            # Refresh project list
            self._load_projects_from_db()
            self.set_status("Project berhasil dihapus")
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"ERROR deleting project: {e}")
            self.set_status(f"Gagal menghapus project: {e}")

    def _on_scan_requested(self) -> None:
        """Handle scan request by starting a background scan worker.

        Scanning runs on a dedicated QThread so the GUI event loop is never
        blocked or re-entered mid-scan. Results are delivered via queued
        signals. This replaced the old processEvents()/self-rescheduling
        QTimer loop that caused heap corruption on large files.
        """
        # Guard against overlapping scans (re-entrancy / double-click).
        if getattr(self, "_scan_thread", None) is not None:
            print("DEBUG: Scan already in progress, ignoring request")
            return

        project_view = self._pages.get(Page.PROJECT_VIEW)
        if not project_view or not project_view._files:
            self.set_status("No files to scan")
            return

        files = project_view._files.copy()

        scan_progress = self._pages.get(Page.SCAN_PROGRESS)
        if scan_progress:
            scan_progress.set_files(files)

        self.navigate_to(Page.SCAN_PROGRESS)

        self._scan_findings = []
        self._start_scan_worker(files)

    def _start_scan_worker(self, files: list[dict]) -> None:
        """Create the worker + thread and wire up queued signals."""
        from PySide6.QtCore import QThread
        from sandiraksa.ui.scan_worker import ScanWorker

        self._scan_thread = QThread(self)
        self._scan_worker = ScanWorker(files, self._current_project_id)
        self._scan_worker.moveToThread(self._scan_thread)

        # Run when the thread starts; the worker signals completion itself.
        self._scan_thread.started.connect(self._scan_worker.run)
        self._scan_worker.file_started.connect(self._on_worker_file_started)
        self._scan_worker.file_finished.connect(self._on_worker_file_finished)
        self._scan_worker.file_error.connect(self._on_worker_file_error)
        self._scan_worker.all_finished.connect(self._on_worker_all_finished)

        self._scan_thread.start()

    def _on_worker_file_started(self, file_id: str) -> None:
        """A file scan has started (GUI thread)."""
        scan_progress = self._pages.get(Page.SCAN_PROGRESS)
        if scan_progress:
            scan_progress.update_file_status(file_id, "scanning")

    def _on_worker_file_finished(self, file_id: str, findings_count: int) -> None:
        """A file finished scanning (GUI thread)."""
        scan_progress = self._pages.get(Page.SCAN_PROGRESS)
        if scan_progress:
            scan_progress.update_file_status(file_id, "completed", findings_count)

    def _on_worker_file_error(self, file_id: str) -> None:
        """A file failed to scan (GUI thread)."""
        scan_progress = self._pages.get(Page.SCAN_PROGRESS)
        if scan_progress:
            scan_progress.update_file_status(file_id, "error")

    def _on_worker_all_finished(self, findings: list) -> None:
        """All files scanned; collect results and clean up the thread."""
        self._scan_findings = findings
        self._current_findings = findings
        total_findings = len(findings)

        findings_review = self._pages.get(Page.FINDINGS_REVIEW)
        if findings_review and hasattr(findings_review, "set_findings"):
            findings_review.set_findings(findings)

        # Tear down the worker thread cleanly before navigating.
        self._teardown_scan_thread()

        scan_progress = self._pages.get(Page.SCAN_PROGRESS)
        if scan_progress:
            scan_progress.scan_complete.emit(total_findings)

    def _teardown_scan_thread(self) -> None:
        """Stop and dispose the scan thread/worker if present."""
        thread = getattr(self, "_scan_thread", None)
        worker = getattr(self, "_scan_worker", None)
        if thread is not None:
            thread.quit()
            thread.wait()
            thread.deleteLater()
        if worker is not None:
            worker.deleteLater()
        self._scan_thread = None
        self._scan_worker = None

    def _on_scan_complete(self, findings_count: int) -> None:
        """Handle scan completion."""
        print(f"DEBUG: _on_scan_complete called with {findings_count}")
        if findings_count > 0:
            print("DEBUG: Navigating to FINDINGS_REVIEW")
            self.navigate_to(Page.FINDINGS_REVIEW)
        else:
            print("DEBUG: No findings, navigating to PROJECT_VIEW")
            self.navigate_to(Page.PROJECT_VIEW)

    def _on_scan_cancelled(self) -> None:
        """Handle scan cancellation."""
        worker = getattr(self, "_scan_worker", None)
        if worker is not None:
            worker.cancel()
        self._teardown_scan_thread()
        self.navigate_to(Page.PROJECT_VIEW)

    def _on_files_added(self, files: list) -> None:
        """Handle files added to project."""
        from pathlib import Path
        from sandiraksa.ui.dialogs import ColumnSelectionDialog, TxtPreviewDialog
        
        print(f"DEBUG _on_files_added: {len(files)} files received")
        
        project_view = self._pages.get(Page.PROJECT_VIEW)
        if not project_view:
            print("DEBUG: No project_view found!")
            return
        
        # Separate file types
        tabular_files = []  # Excel/CSV
        txt_files = []       # Plain text
        document_files = []  # Word/PowerPoint
        other_files = []     # Others
        
        for file_path in files:
            path = Path(file_path) if isinstance(file_path, str) else file_path
            suffix = path.suffix.lower()
            print(f"DEBUG: Processing file {path.name}, suffix={suffix}")
            if suffix in ('.xlsx', '.xls', '.csv'):
                tabular_files.append(path)
            elif suffix in ('.txt', '.log', '.md', '.json', '.xml', '.html'):
                txt_files.append(path)
                print(f"DEBUG: Added to txt_files: {path.name}")
            elif suffix in ('.docx', '.doc', '.pptx', '.ppt'):
                document_files.append(path)
                print(f"DEBUG: Added to document_files: {path.name}")
            else:
                other_files.append(path)
        
        print(f"DEBUG: tabular={len(tabular_files)}, txt={len(txt_files)}, doc={len(document_files)}, other={len(other_files)}")
        
        # First, add all other files directly (unsupported types)
        for path in other_files:
            existing = next(
                (f for f in project_view._files if f.get("path") == str(path)), 
                None
            )
            if not existing:
                self._add_file_to_project(path, None, project_view)
                print(f"DEBUG: Added file: {path.name}")
        
        if other_files:
            self.set_status(f"{len(other_files)} file ditambahkan")
        
        # Process TXT files with preview dialog
        for path in txt_files:
            existing = next(
                (f for f in project_view._files if f.get("path") == str(path)), 
                None
            )
            
            # Show TXT preview dialog
            self._show_txt_preview(path, existing, project_view)
        
        # Process document files (DOCX/PPTX)
        for path in document_files:
            existing = next(
                (f for f in project_view._files if f.get("path") == str(path)), 
                None
            )
            
            # Show document preview dialog
            self._show_document_preview(path, existing, project_view)
        
        # Then process tabular files one by one (they need column selection)
        for path in tabular_files:
            existing = next(
                (f for f in project_view._files if f.get("path") == str(path)), 
                None
            )
            
            # Process Qt events to allow GC to complete before file I/O
            from PySide6.QtWidgets import QApplication
            QApplication.processEvents()
            
            # Pre-analyze file BEFORE creating dialog (avoids GC crash)
            from sandiraksa.ui.dialogs.column_selection import analyze_csv_file, analyze_excel_file
            try:
                if path.suffix.lower() == '.csv':
                    worksheets = analyze_csv_file(path)
                else:
                    worksheets = analyze_excel_file(path)
            except Exception as e:
                print(f"Error analyzing file {path}: {e}")
                worksheets = []
            
            # Process events again before dialog
            QApplication.processEvents()
            
            # Show column selection dialog with pre-analyzed data
            dialog = ColumnSelectionDialog(path, parent=self, worksheets=worksheets)
            if dialog.exec():
                selected_columns = dialog.get_selected_columns()
                if selected_columns:
                    if existing:
                        # Update existing file with new column selection
                        existing["selected_columns"] = selected_columns
                        existing["status"] = "pending"
                        project_view._refresh_file_list()
                    else:
                        # Add new file
                        self._add_file_to_project(path, selected_columns, project_view)
                        print(f"DEBUG: Added {path.suffix} file with {len(selected_columns)} columns: {path.name}")
                    self.set_status(f"{len(selected_columns)} kolom dipilih untuk {path.name}")
                else:
                    # No columns selected, add file without columns (user can select later)
                    if not existing:
                        self._add_file_to_project(path, None, project_view)
                        print(f"DEBUG: Added {path.suffix} file without columns: {path.name}")
                    self.set_status(f"File ditambahkan: {path.name} (pilih kolom untuk proteksi)")
            else:
                # Dialog cancelled - still add file, user can select columns later
                if not existing:
                    self._add_file_to_project(path, None, project_view)
                    print(f"DEBUG: Added {path.suffix} file (dialog cancelled): {path.name}")
                self.set_status(f"File ditambahkan: {path.name}")
    
    def _show_txt_preview(self, path, existing, project_view) -> None:
        """Show TXT preview dialog for text files."""
        from sandiraksa.ui.dialogs import TxtPreviewDialog
        
        print(f"DEBUG _show_txt_preview: {path}")
        
        try:
            # Read file content
            encodings = ['utf-8-sig', 'utf-8', 'latin-1', 'cp1252']
            text_content = None
            
            for encoding in encodings:
                try:
                    with open(path, 'r', encoding=encoding) as f:
                        text_content = f.read()
                    print(f"DEBUG: Read file with {encoding}, length={len(text_content)}")
                    break
                except (UnicodeDecodeError, UnicodeError):
                    continue
            
            if text_content is None:
                print("DEBUG: Could not read file with any encoding")
                self.set_status(f"Tidak dapat membaca file: {path.name}")
                return
            
            # Detect entities
            protector = _TxtProtector(
                self._current_project_id or "temp",
                entity_types=None,  # Detect all types
            )
            detected_entities = protector.detect_entities(text_content)
            print(f"DEBUG: Detected {len(detected_entities)} entities")
            
            if not detected_entities:
                # No entities found, add file directly
                print("DEBUG: No entities found, adding file directly")
                if not existing:
                    self._add_file_to_project(path, None, project_view)
                self.set_status(f"Tidak ditemukan data sensitif dalam {path.name}")
                return
            
            # Keep strong reference to prevent crash
            print("DEBUG: Creating TxtPreviewDialog")
            self._txt_preview_dialog = TxtPreviewDialog(
                filename=path.name,
                text_content=text_content,
                detected_entities=detected_entities,
                parent=self,
            )
            
            print("DEBUG: Showing dialog")
            if self._txt_preview_dialog.exec():
                selected_entities = self._txt_preview_dialog.get_selected_entities()
                print(f"DEBUG: Dialog accepted, {len(selected_entities)} entities selected")
                
                if existing:
                    existing["detected_entities"] = selected_entities
                    existing["status"] = "pending"
                    project_view._refresh_file_list()
                else:
                    self._add_file_to_project(path, None, project_view, detected_entities=selected_entities)
                
                self.set_status(f"{len(selected_entities)} data sensitif akan dilindungi dalam {path.name}")
            else:
                # Dialog cancelled - still add file
                print("DEBUG: Dialog cancelled")
                if not existing:
                    self._add_file_to_project(path, None, project_view)
                self.set_status(f"File ditambahkan: {path.name}")
                
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.set_status(f"Error memproses {path.name}: {e}")
    
    def _show_document_preview(self, path, existing, project_view) -> None:
        """Show document preview dialog for DOCX/PPTX files."""
        from sandiraksa.ui.dialogs import DocumentPreviewDialog
        from PySide6.QtWidgets import QApplication
        
        print(f"DEBUG _show_document_preview: {path}")
        
        try:
            # Process Qt events before file I/O
            QApplication.processEvents()
            
            suffix = path.suffix.lower()
            
            # Detect entities based on file type
            if suffix in ('.docx', '.doc'):
                from sandiraksa.protection.docx_protector import DocxProtector
                protector = DocxProtector(
                    self._current_project_id or "temp",
                    entity_types=None,
                )
                detected_entities = protector.detect_entities(path)
                file_type = "docx"
            else:  # .pptx, .ppt
                from sandiraksa.protection.pptx_protector import PptxProtector
                protector = PptxProtector(
                    self._current_project_id or "temp",
                    entity_types=None,
                )
                detected_entities = protector.detect_entities(path)
                file_type = "pptx"
            
            print(f"DEBUG: Detected {len(detected_entities)} entities in {file_type}")
            
            # Process events again before dialog
            QApplication.processEvents()
            
            if not detected_entities:
                # No entities found, add file directly
                print("DEBUG: No entities found, adding file directly")
                if not existing:
                    self._add_file_to_project(path, None, project_view)
                self.set_status(f"Tidak ditemukan data sensitif dalam {path.name}")
                return
            
            # Keep strong reference to dialog to prevent crash
            print("DEBUG: Creating DocumentPreviewDialog")
            self._document_preview_dialog = DocumentPreviewDialog(
                filename=path.name,
                file_type=file_type,
                detected_entities=detected_entities,
                parent=self,
            )
            
            print("DEBUG: Showing dialog")
            if self._document_preview_dialog.exec():
                selected_entities = self._document_preview_dialog.get_selected_entities()
                print(f"DEBUG: Dialog accepted, {len(selected_entities)} entities selected")
                
                if existing:
                    existing["detected_entities"] = selected_entities
                    existing["status"] = "pending"
                    project_view._refresh_file_list()
                else:
                    self._add_file_to_project(path, None, project_view, detected_entities=selected_entities)
                
                self.set_status(f"{len(selected_entities)} data sensitif akan dilindungi dalam {path.name}")
            else:
                # Dialog cancelled - still add file
                print("DEBUG: Dialog cancelled")
                if not existing:
                    self._add_file_to_project(path, None, project_view)
                self.set_status(f"File ditambahkan: {path.name}")
                
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.set_status(f"Error memproses {path.name}: {e}")

    def _rehydrate_columns(self, columns_data):
        """
        Rebuild ColumnInfo objects from serialized metadata dicts.

        Downstream scan/protect code accesses columns as objects
        (col.sheet_name, col.protection_mode, ...), so reconstruct them here.
        """
        if not columns_data:
            return columns_data
        try:
            from sandiraksa.ui.dialogs.column_selection import ColumnInfo

            rebuilt = []
            for d in columns_data:
                if not isinstance(d, dict):
                    rebuilt.append(d)  # already an object
                    continue
                rebuilt.append(ColumnInfo(
                    sheet_name=d.get("sheet_name", ""),
                    column_index=d.get("column_index", 0),
                    column_letter=d.get("column_letter", ""),
                    header=d.get("header", ""),
                    suggested_type=d.get("suggested_type"),
                    is_selected=True,
                    protection_mode=d.get("protection_mode", "full_cell"),
                ))
            return rebuilt
        except Exception as e:
            print(f"Failed to rehydrate columns: {e}")
            return columns_data

    def _add_file_to_project(self, path, selected_columns, project_view, detected_entities=None) -> str:
        """Add a single file to project and return file_id."""
        from sandiraksa.storage.repositories import FileRepository
        from sandiraksa.security.vault import get_project_vault
        import os
        import json
        
        if not self._current_project_id:
            print("ERROR: No current project ID")
            return ""
        
        try:
            vault = get_project_vault(self._current_project_id)
            repo = FileRepository()
            
            # Get file info
            file_size = path.stat().st_size if path.exists() else None
            
            # Encrypt filename and path
            filename_enc = vault.encrypt(
                path.name,
                table="files",
                row_id="temp",
                field="filename_enc"
            )
            
            source_path_enc = vault.encrypt(
                str(path),
                table="files",
                row_id="temp",
                field="source_path_enc"
            )
            
            # Serialize and encrypt metadata (selected_columns, detected_entities)
            metadata_enc = None
            if selected_columns or detected_entities:
                # Convert selected_columns to serializable format
                columns_data = None
                if selected_columns:
                    columns_data = [
                        {
                            "sheet_name": getattr(col, 'sheet_name', ''),
                            "column_index": getattr(col, 'column_index', 0),
                            "header": getattr(col, 'header', ''),
                            "suggested_type": getattr(col, 'suggested_type', 'PII'),
                            "protection_mode": getattr(col, 'protection_mode', 'full_cell'),
                        }
                        for col in selected_columns
                    ]
                
                # Convert detected_entities to serializable format
                entities_data = None
                if detected_entities:
                    entities_data = [
                        {
                            "entity_type": getattr(e, 'entity_type', 'PII'),
                            "value": getattr(e, 'value', ''),
                            "start": getattr(e, 'start', 0),
                            "end": getattr(e, 'end', 0),
                        }
                        for e in detected_entities
                    ]
                
                metadata = {
                    "selected_columns": columns_data,
                    "detected_entities": entities_data,
                }
                metadata_json = json.dumps(metadata)
                metadata_enc = vault.encrypt(
                    metadata_json,
                    table="files",
                    row_id="temp",
                    field="metadata_enc"
                )
            
            # Create file record in database
            record = repo.create(
                project_id=self._current_project_id,
                filename_enc=filename_enc,
                extension=path.suffix.lstrip(".").lower(),
                source_path_enc=source_path_enc,
                file_size=file_size,
                metadata_enc=metadata_enc,
            )
            
            file_id = record.id
            
            # Create in-memory record for UI
            file_record = {
                "id": file_id,
                "name": path.name,
                "path": str(path),
                "format": path.suffix.lstrip(".").lower(),
                "status": "pending",
                "selected_columns": selected_columns,
                "detected_entities": detected_entities,
            }
            project_view._files.append(file_record)
            project_view._refresh_file_list()
            
            print(f"DEBUG: File saved to DB: {file_id}")
            return file_id
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"ERROR saving file to DB: {e}")
            return ""
    
    def _scan_single_file(self, file_id: str) -> None:
        """Scan a single file by ID using the background scan worker."""
        # Guard against overlapping scans.
        if getattr(self, "_scan_thread", None) is not None:
            print("DEBUG: Scan already in progress, ignoring request")
            return

        project_view = self._pages.get(Page.PROJECT_VIEW)
        if not project_view:
            return

        file_info = next(
            (f for f in project_view._files if f["id"] == file_id), None
        )
        if not file_info:
            return

        self.set_status(f"Memindai {file_info.get('name', 'file')}...")

        scan_progress = self._pages.get(Page.SCAN_PROGRESS)
        if scan_progress:
            scan_progress.set_files([file_info])
        self.navigate_to(Page.SCAN_PROGRESS)

        self._scan_findings = []
        self._start_scan_worker([file_info])

    def _on_file_removed(self, file_id: str) -> None:
        """Handle file removed from project."""
        # Update project view
        project_view = self._pages.get(Page.PROJECT_VIEW)
        if project_view and hasattr(project_view, 'remove_file'):
            project_view.remove_file(file_id)
        
        self.set_status("File removed")

    def _on_project_settings(self) -> None:
        """Handle project settings request."""
        from sandiraksa.ui.dialogs import ProjectSettingsDialog
        from sandiraksa.storage.repositories import ProjectRepository
        from sandiraksa.security.vault import get_project_vault
        
        # Get project name from project view first (this is the display name)
        project_view = self._pages.get(Page.PROJECT_VIEW)
        display_name = ""
        if project_view and hasattr(project_view, '_project_name'):
            display_name = project_view._project_name
        
        # Load existing project settings
        existing_settings = {"name": display_name}  # Start with display name as default
        
        if self._current_project_id:
            try:
                repo = ProjectRepository()
                record = repo.get_by_id(self._current_project_id)
                vault = get_project_vault(self._current_project_id)
                
                # Try to decrypt project name from DB with correct context
                try:
                    db_name = vault.decrypt_string(
                        record.name_enc,
                        table="projects",
                        row_id=self._current_project_id,
                        field="name_enc"
                    )
                    existing_settings["name"] = db_name
                except Exception as decrypt_err:
                    print(f"Decrypt failed, using display name: {display_name}")
                
                # Decrypt description if present
                if record.description_enc:
                    try:
                        description = vault.decrypt_string(
                            record.description_enc,
                            table="projects",
                            row_id=self._current_project_id,
                            field="description_enc"
                        )
                        existing_settings["description"] = description
                    except Exception:
                        pass
                
                # Decrypt extra settings (entity_types, output_folder, filename_suffix)
                if record.settings_enc:
                    try:
                        import json
                        settings_json = vault.decrypt_string(
                            record.settings_enc,
                            table="projects",
                            row_id=self._current_project_id,
                            field="settings_enc"
                        )
                        extra_settings = json.loads(settings_json)
                        existing_settings.update(extra_settings)
                    except Exception as e:
                        print(f"Failed to decrypt settings_enc: {e}")
                
                existing_settings["profile"] = record.profile_id
                
            except Exception as e:
                print(f"Error loading project settings: {e}")
        
        # Cleanup any previous dialog to prevent memory issues
        if hasattr(self, '_settings_dialog') and self._settings_dialog is not None:
            try:
                self._settings_dialog.setParent(None)
                self._settings_dialog.deleteLater()
            except Exception:
                pass
            self._settings_dialog = None
        
        # Keep strong reference to dialog to prevent crash
        self._settings_dialog = ProjectSettingsDialog(project_settings=existing_settings, parent=self)
        if self._settings_dialog.exec():
            new_settings = self._settings_dialog.get_settings()
            self._save_project_settings(new_settings)

    def _save_project_settings(self, settings: dict) -> None:
        """Save project settings to database."""
        from sandiraksa.storage.repositories import ProjectRepository
        from sandiraksa.security.vault import get_project_vault
        import json
        
        if not self._current_project_id:
            return
        
        try:
            vault = get_project_vault(self._current_project_id)
            repo = ProjectRepository()
            
            # Encrypt name and description
            name_enc = vault.encrypt(
                settings.get("name", "Untitled"), 
                table="projects", 
                row_id=self._current_project_id, 
                field="name_enc"
            )
            
            description = settings.get("description", "")
            description_enc = None
            if description:
                description_enc = vault.encrypt(
                    description,
                    table="projects",
                    row_id=self._current_project_id,
                    field="description_enc"
                )
            
            # Encrypt extra settings as JSON
            extra_settings = {
                "entity_types": settings.get("entity_types", []),
                "output_folder": settings.get("output_folder", ""),
                "filename_suffix": settings.get("filename_suffix", "_protected"),
            }
            settings_json = json.dumps(extra_settings)
            settings_enc = vault.encrypt(
                settings_json,
                table="projects",
                row_id=self._current_project_id,
                field="settings_enc"
            )
            
            # Update project
            repo.update(
                self._current_project_id,
                name_enc=name_enc,
                description_enc=description_enc,
                settings_enc=settings_enc,
                profile_id=settings.get("profile", "standard"),
            )
            
            # Update UI title
            project_view = self._pages.get(Page.PROJECT_VIEW)
            if project_view:
                project_view._title.setText(settings.get("name", "Untitled"))
            
            self.set_status("Pengaturan project berhasil disimpan")
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.set_status(f"Gagal menyimpan pengaturan: {e}")

    def _on_apply_treatments(self, finding_ids: list[str]) -> None:
        """Handle treatment application."""
        # TODO: Apply treatments via service
        self.navigate_to(Page.RESULTS_VIEW)

    def _on_restore_requested(self, text: str) -> None:
        """Handle restore request - replace tokens with original values."""
        import re
        from sandiraksa.protection.tokenizer import TokenizerFactory
        
        if not self._current_project_id:
            restore_view = self._pages.get(Page.RESTORE_VIEW)
            if restore_view:
                restore_view.set_result(text, 0)
            return
        
        try:
            tokenizer = TokenizerFactory.get_tokenizer(self._current_project_id)
            
            # Find all tokens in text
            token_pattern = r"\[\[[A-Z_]+_[A-Fa-f0-9]+\]\]"
            tokens = re.findall(token_pattern, text)
            
            restored_text = text
            invalid_count = 0
            
            for token in set(tokens):  # Use set to avoid duplicate lookups
                result = tokenizer.lookup_token(token)
                if result.found and result.original_value:
                    restored_text = restored_text.replace(token, result.original_value)
                else:
                    invalid_count += 1
            
            restore_view = self._pages.get(Page.RESTORE_VIEW)
            if restore_view:
                restore_view.set_result(restored_text, invalid_count)
                
        except Exception as e:
            import traceback
            traceback.print_exc()
            restore_view = self._pages.get(Page.RESTORE_VIEW)
            if restore_view:
                restore_view.set_result(f"Error: {str(e)}", 0)

    def _on_restore_file(self) -> None:
        """Handle restore file request - open file dialog and restore file."""
        from pathlib import Path
        from PySide6.QtWidgets import QFileDialog, QMessageBox, QApplication
        
        # Open file dialog
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Pilih File untuk Dipulihkan",
            str(Path.home()),
            "Tabular Files (*.xlsx *.xls *.csv);;Excel Files (*.xlsx *.xls);;CSV Files (*.csv);;All Files (*.*)",
        )
        
        if not file_path:
            return
        
        self.set_status(f"Memulihkan {Path(file_path).name}...")
        QApplication.processEvents()
        
        try:
            # Determine file type and call appropriate restore method
            file_ext = Path(file_path).suffix.lower()
            if file_ext == '.csv':
                result = self._restore_csv_file(file_path)
            else:
                result = self._restore_excel_file(file_path)
            
            if result.get("success"):
                output_path = result.get("output_path")
                cells_restored = result.get("cells_restored", 0)
                
                self.set_status(f"Berhasil memulihkan {cells_restored} sel")
                
                reply = QMessageBox.question(
                    self,
                    "Berhasil",
                    f"File berhasil dipulihkan!\n\n"
                    f"Sel dipulihkan: {cells_restored}\n"
                    f"File tersimpan: {Path(output_path).name}\n\n"
                    f"Buka folder?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                
                if reply == QMessageBox.StandardButton.Yes:
                    import subprocess
                    import os
                    folder = Path(output_path).parent
                    if os.name == 'nt':
                        subprocess.run(['explorer', '/select,', str(output_path)])
                    else:
                        subprocess.run(['xdg-open', str(folder)])
            else:
                error_msg = result.get("error", "Unknown error")
                self.set_status(f"Gagal: {error_msg}")
                QMessageBox.warning(
                    self,
                    "Error",
                    f"Gagal memulihkan file:\n{error_msg}",
                )
                
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.set_status(f"Error: {str(e)}")
            QMessageBox.warning(self, "Error", f"Terjadi kesalahan:\n{str(e)}")

    def _restore_excel_file(self, file_path: str) -> dict:
        """Restore tokens in Excel file back to original values."""
        from pathlib import Path
        import re
        import openpyxl
        from sandiraksa.protection.tokenizer import TokenizerFactory
        
        if not self._current_project_id:
            return {"success": False, "error": "Tidak ada project aktif"}
        
        try:
            input_path = Path(file_path)
            output_dir = self._get_output_directory()
            
            # Create output filename
            stem = input_path.stem
            # Remove _protected suffix if present
            if stem.endswith("_protected"):
                stem = stem[:-10]
            output_path = output_dir / f"{stem}_restored.xlsx"
            counter = 1
            while output_path.exists():
                output_path = output_dir / f"{stem}_restored_{counter}.xlsx"
                counter += 1
            
            # Load workbook
            wb = openpyxl.load_workbook(input_path)
            tokenizer = TokenizerFactory.get_tokenizer(self._current_project_id)
            
            token_pattern = re.compile(r"\[\[[A-Z_]+_[A-Fa-f0-9]+\]\]")
            cells_restored = 0
            tokens_not_found = 0
            
            # Process all sheets
            for sheet_name in wb.sheetnames:
                ws = wb[sheet_name]
                
                for row in ws.iter_rows():
                    for cell in row:
                        if cell.value and isinstance(cell.value, str):
                            tokens = token_pattern.findall(cell.value)
                            if tokens:
                                new_value = cell.value
                                for token in tokens:
                                    result = tokenizer.lookup_token(token)
                                    if result.found and result.original_value:
                                        new_value = new_value.replace(token, result.original_value)
                                        cells_restored += 1
                                    else:
                                        tokens_not_found += 1
                                cell.value = new_value
            
            # Save restored workbook
            output_path.parent.mkdir(parents=True, exist_ok=True)
            wb.save(output_path)
            wb.close()
            
            return {
                "success": True,
                "output_path": str(output_path),
                "cells_restored": cells_restored,
                "tokens_not_found": tokens_not_found,
            }
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"success": False, "error": str(e)}

    def _restore_csv_file(self, file_path: str) -> dict:
        """Restore tokens in CSV file back to original values."""
        from pathlib import Path
        import re
        import csv
        from sandiraksa.protection.tokenizer import TokenizerFactory
        
        if not self._current_project_id:
            return {"success": False, "error": "Tidak ada project aktif"}
        
        try:
            input_path = Path(file_path)
            output_dir = self._get_output_directory()
            
            # Create output filename
            stem = input_path.stem
            if stem.endswith("_protected"):
                stem = stem[:-10]
            output_path = output_dir / f"{stem}_restored.csv"
            counter = 1
            while output_path.exists():
                output_path = output_dir / f"{stem}_restored_{counter}.csv"
                counter += 1
            
            # Detect delimiter
            with open(input_path, 'r', encoding='utf-8-sig') as f:
                sample = f.read(4096)
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=',;\t|')
                delimiter = dialect.delimiter
            except csv.Error:
                delimiter = ','
            
            # Read CSV
            with open(input_path, 'r', encoding='utf-8-sig', newline='') as f:
                reader = csv.reader(f, delimiter=delimiter)
                rows = list(reader)
            
            tokenizer = TokenizerFactory.get_tokenizer(self._current_project_id)
            token_pattern = re.compile(r"\[\[[A-Z_]+_[A-Fa-f0-9]+\]\]")
            cells_restored = 0
            tokens_not_found = 0
            
            # Process all rows
            restored_rows = []
            for row in rows:
                restored_row = []
                for cell in row:
                    if cell and isinstance(cell, str):
                        tokens = token_pattern.findall(cell)
                        if tokens:
                            new_value = cell
                            for token in tokens:
                                result = tokenizer.lookup_token(token)
                                if result.found and result.original_value:
                                    new_value = new_value.replace(token, result.original_value)
                                    cells_restored += 1
                                else:
                                    tokens_not_found += 1
                            restored_row.append(new_value)
                        else:
                            restored_row.append(cell)
                    else:
                        restored_row.append(cell)
                restored_rows.append(restored_row)
            
            # Save restored CSV
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w', encoding='utf-8-sig', newline='') as f:
                writer = csv.writer(f, delimiter=delimiter)
                writer.writerows(restored_rows)
            
            return {
                "success": True,
                "output_path": str(output_path),
                "cells_restored": cells_restored,
                "tokens_not_found": tokens_not_found,
            }
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"success": False, "error": str(e)}

    def _show_about(self) -> None:
        """Show about dialog."""
        from sandiraksa.ui.dialogs import AboutDialog

        dialog = AboutDialog(parent=self)
        dialog.exec()

    def _show_help(self) -> None:
        """Show help/quick start guide dialog."""
        from sandiraksa.ui.dialogs import HelpDialog

        dialog = HelpDialog(parent=self)
        dialog.exec()

    def _show_docs(self) -> None:
        """Show documentation dialog."""
        from sandiraksa.ui.dialogs import DocsDialog

        dialog = DocsDialog(parent=self)
        dialog.exec()

    def _show_contact(self) -> None:
        """Show contact dialog."""
        from sandiraksa.ui.dialogs import ContactDialog

        dialog = ContactDialog(parent=self)
        dialog.exec()

    def _show_donate(self) -> None:
        """Show donate dialog."""
        from sandiraksa.ui.dialogs import DonateDialog

        dialog = DonateDialog(parent=self)
        dialog.exec()

    def _on_custom_patterns(self) -> None:
        """Show the global custom patterns editor dialog."""
        from sandiraksa.ui.dialogs import CustomPatternsDialog

        # Keep a strong reference to prevent premature GC crash
        self._custom_patterns_dialog = CustomPatternsDialog(parent=self)
        if self._custom_patterns_dialog.exec():
            # Refresh cached patterns so subsequent scans use the new set
            try:
                from sandiraksa.detection.custom_patterns import (
                    reload_global_patterns,
                )

                reload_global_patterns()
            except Exception as e:
                print(f"Failed to reload custom patterns: {e}")

    def _on_deny_list(self) -> None:
        """Show the global deny-list (exclusion terms) editor dialog."""
        from sandiraksa.ui.dialogs import DenyListDialog

        # Keep a strong reference to prevent premature GC crash
        self._deny_list_dialog = DenyListDialog(parent=self)
        if self._deny_list_dialog.exec():
            # Refresh cached deny-list so subsequent scans use the new set
            try:
                from sandiraksa.detection.deny_list import (
                    reload_global_deny_list,
                )

                reload_global_deny_list()
            except Exception as e:
                print(f"Failed to reload deny-list: {e}")

    def set_status(self, message: str) -> None:
        """Update status bar message."""
        status_bar = self.statusBar()
        if status_bar:
            status_bar.showMessage(message)

    def _on_protect_file(self, file_id: str) -> None:
        """Handle protect file request."""
        from pathlib import Path
        from PySide6.QtWidgets import QApplication, QMessageBox, QProgressDialog
        from PySide6.QtCore import Qt, QTimer
        
        project_view = self._pages.get(Page.PROJECT_VIEW)
        if not project_view:
            return
        
        file_info = project_view.get_file_info(file_id)
        if not file_info:
            self.set_status("File tidak ditemukan")
            return
        
        file_path = file_info.get("path")
        file_format = file_info.get("format", "").lower()
        selected_columns = file_info.get("selected_columns")
        detected_entities = file_info.get("detected_entities")
        
        if not file_path or not Path(file_path).exists():
            self.set_status("File tidak ditemukan di disk")
            return
        
        # For tabular files (Excel/CSV) without selected columns, prompt to select columns first
        if file_format in ("xlsx", "xls", "csv") and not selected_columns:
            QMessageBox.information(
                self,
                "Pilih Kolom",
                "Silakan pilih kolom yang akan diproteksi terlebih dahulu.",
            )
            # Trigger column selection
            self._on_files_added([Path(file_path)])
            return
        
        # For TXT files without detected entities, show preview first
        if file_format in ("txt", "log", "md", "json", "xml", "html") and not detected_entities:
            self._show_txt_preview(Path(file_path), file_info, project_view)
            # After preview, if user selected entities, protect will be triggered again
            if file_info.get("detected_entities"):
                # Re-trigger protect with entities now set
                self._on_protect_file(file_id)
            return
        
        # For document files (DOCX/PPTX) without detected entities, show preview first
        if file_format in ("docx", "doc", "pptx", "ppt") and not detected_entities:
            self._show_document_preview(Path(file_path), file_info, project_view)
            # After preview, if user selected entities, protect will be triggered again
            if file_info.get("detected_entities"):
                # Re-trigger protect with entities now set
                self._on_protect_file(file_id)
            return
        
        # Update status to processing
        project_view.update_file_status(file_id, "processing")
        self.set_status(f"Memproteksi {file_info.get('name', 'file')}...")
        QApplication.processEvents()
        
        # Run protection in background
        self._protect_file_async(file_id, file_info, project_view)
    
    def _protect_file_async(self, file_id: str, file_info: dict, project_view) -> None:
        """Run file protection asynchronously."""
        from pathlib import Path
        from PySide6.QtWidgets import QApplication, QMessageBox
        from PySide6.QtCore import QTimer
        
        file_path = file_info.get("path")
        file_format = file_info.get("format", "").lower()
        selected_columns = file_info.get("selected_columns")
        detected_entities = file_info.get("detected_entities")
        
        try:
            if file_format in ("xlsx", "xls"):
                result = self._protect_excel_file(file_path, selected_columns)
            elif file_format == "csv":
                result = self._protect_csv_file(file_path, selected_columns)
            elif file_format in ("txt", "log", "md", "json", "xml", "html"):
                result = self._protect_txt_file(file_path, detected_entities)
            elif file_format in ("docx", "doc"):
                result = self._protect_docx_file(file_path, detected_entities)
            elif file_format in ("pptx", "ppt"):
                result = self._protect_pptx_file(file_path, detected_entities)
            else:
                # For other file types, use generic protection
                result = self._protect_generic_file(file_path)
            
            if result.get("success"):
                output_path = result.get("output_path")
                cells_protected = result.get("cells_protected", 0)
                
                # Update file status in UI
                project_view.update_file_status(
                    file_id, 
                    "protected",
                    output_path=output_path,
                )
                
                # Update file status in database
                self._update_file_status_in_db(file_id, "protected")
                
                self.set_status(
                    f"Berhasil memproteksi {cells_protected} sel. "
                    f"File tersimpan: {Path(output_path).name}"
                )
            else:
                error_msg = result.get("error", "Unknown error")
                project_view.update_file_status(file_id, "error")
                self._update_file_status_in_db(file_id, "error")
                self.set_status(f"Gagal memproteksi: {error_msg}")
                QMessageBox.warning(
                    self,
                    "Error Proteksi",
                    f"Gagal memproteksi file:\n{error_msg}",
                )
                
        except Exception as e:
            import traceback
            traceback.print_exc()
            project_view.update_file_status(file_id, "error")
            self._update_file_status_in_db(file_id, "error")
            self.set_status(f"Error: {str(e)}")
            QMessageBox.warning(
                self,
                "Error",
                f"Terjadi kesalahan:\n{str(e)}",
            )
    
    def _update_file_status_in_db(self, file_id: str, status: str) -> None:
        """Update file status in database."""
        from sandiraksa.storage.repositories import FileRepository
        
        try:
            repo = FileRepository()
            repo.update(file_id, status=status)
            print(f"DEBUG: File status updated in DB: {file_id} -> {status}")
        except Exception as e:
            print(f"ERROR updating file status in DB: {e}")
    
    def _protect_excel_file(self, file_path: str, selected_columns: list) -> dict:
        """Protect an Excel file using tokenizer."""
        from pathlib import Path
        from sandiraksa.protection.excel_protector import (
            ExcelProtector,
            ColumnConfig,
            generate_output_path,
        )
        
        try:
            # Generate output path with suffix from settings
            input_path = Path(file_path)
            output_dir = self._get_output_directory()
            filename_suffix = self._get_filename_suffix()
            output_path = generate_output_path(input_path, output_dir, suffix=filename_suffix)
            
            # Convert selected columns to ColumnConfig
            column_configs = []
            for col in selected_columns:
                column_configs.append(ColumnConfig(
                    sheet_name=col.sheet_name,
                    column_index=col.column_index,
                    column_name=col.header,
                    entity_type=col.suggested_type or "PII",
                    protection_mode=getattr(col, "protection_mode", "full_cell"),
                ))
            
            # Create protector with current project ID
            project_id = self._current_project_id
            if not project_id:
                return {"success": False, "error": "Project ID tidak ditemukan"}
            
            protector = ExcelProtector(project_id)
            
            # Run protection
            result = protector.protect_file(
                input_path,
                output_path,
                column_configs,
            )
            
            return {
                "success": result.success,
                "output_path": result.output_path,
                "cells_protected": result.cells_protected,
                "error": result.error_message,
            }
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": str(e),
            }
    
    def _protect_csv_file(self, file_path: str, selected_columns: list) -> dict:
        """Protect a CSV file using tokenizer."""
        from pathlib import Path
        from sandiraksa.protection.csv_protector import (
            CSVProtector,
            CSVColumnConfig,
        )
        from sandiraksa.protection.excel_protector import generate_output_path
        
        try:
            # Generate output path with suffix from settings
            input_path = Path(file_path)
            output_dir = self._get_output_directory()
            filename_suffix = self._get_filename_suffix()
            output_path = generate_output_path(input_path, output_dir, suffix=filename_suffix)
            
            # Convert selected columns to CSVColumnConfig
            column_configs = []
            for col in selected_columns:
                column_configs.append(CSVColumnConfig(
                    column_index=col.column_index,  # CSV uses 0-based index
                    column_name=col.header,
                    entity_type=col.suggested_type or "PII",
                ))
            
            # Create protector with current project ID
            project_id = self._current_project_id
            if not project_id:
                return {"success": False, "error": "Project ID tidak ditemukan"}
            
            protector = CSVProtector(project_id)
            
            # Run protection
            result = protector.protect_file(
                input_path,
                output_path,
                column_configs,
            )
            
            return {
                "success": result.success,
                "output_path": result.output_path,
                "cells_protected": result.cells_protected,
                "error": result.error_message,
            }
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": str(e),
            }
    
    def _protect_txt_file(self, file_path: str, detected_entities: list | None = None) -> dict:
        """Protect a TXT file using tokenizer."""
        from pathlib import Path
        from sandiraksa.protection.txt_protector import (
            TxtProtector,
            generate_txt_output_path,
        )
        
        try:
            # Generate output path with suffix from settings
            input_path = Path(file_path)
            output_dir = self._get_output_directory()
            filename_suffix = self._get_filename_suffix()
            output_path = generate_txt_output_path(input_path, output_dir, suffix=filename_suffix)
            
            # Create protector with current project ID
            project_id = self._current_project_id
            if not project_id:
                return {"success": False, "error": "Project ID tidak ditemukan"}
            
            protector = TxtProtector(project_id)
            
            # If we have pre-detected entities, use them
            if detected_entities:
                # Read file and protect with specific entities
                encodings = ['utf-8-sig', 'utf-8', 'latin-1', 'cp1252']
                text_content = None
                
                for encoding in encodings:
                    try:
                        with open(input_path, 'r', encoding=encoding) as f:
                            text_content = f.read()
                        break
                    except (UnicodeDecodeError, UnicodeError):
                        continue
                
                if text_content is None:
                    return {"success": False, "error": "Tidak dapat membaca file"}
                
                protected_text, count = protector.protect_text(text_content, detected_entities)
                
                # Ensure output directory exists
                output_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Write protected file
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(protected_text)
                
                return {
                    "success": True,
                    "output_path": str(output_path),
                    "cells_protected": count,
                    "error": None,
                }
            else:
                # Run full protection (detect + protect)
                result = protector.protect_file(input_path, output_path)
                
                return {
                    "success": result.success,
                    "output_path": result.output_path,
                    "cells_protected": result.entities_protected,
                    "error": result.error_message,
                }
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": str(e),
            }
    
    def _protect_docx_file(self, file_path: str, detected_entities: list | None = None) -> dict:
        """Protect a DOCX file using tokenizer."""
        from pathlib import Path
        from sandiraksa.protection.docx_protector import DocxProtector
        
        try:
            input_path = Path(file_path)
            output_dir = self._get_output_directory()
            filename_suffix = self._get_filename_suffix()
            
            # Generate output path
            output_filename = f"{input_path.stem}{filename_suffix}{input_path.suffix}"
            output_path = output_dir / output_filename
            
            # Create protector with current project ID
            project_id = self._current_project_id
            if not project_id:
                return {"success": False, "error": "Project ID tidak ditemukan"}
            
            protector = DocxProtector(project_id)
            
            # Protect with specific entities or auto-detect
            result = protector.protect_file(
                input_path, 
                output_path,
                entities_to_protect=detected_entities,
            )
            
            return {
                "success": result.success,
                "output_path": result.output_path,
                "cells_protected": result.entities_protected,
                "error": result.error_message,
            }
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": str(e),
            }
    
    def _protect_pptx_file(self, file_path: str, detected_entities: list | None = None) -> dict:
        """Protect a PPTX file using tokenizer."""
        from pathlib import Path
        from sandiraksa.protection.pptx_protector import PptxProtector
        
        try:
            input_path = Path(file_path)
            output_dir = self._get_output_directory()
            filename_suffix = self._get_filename_suffix()
            
            # Generate output path
            output_filename = f"{input_path.stem}{filename_suffix}{input_path.suffix}"
            output_path = output_dir / output_filename
            
            # Create protector with current project ID
            project_id = self._current_project_id
            if not project_id:
                return {"success": False, "error": "Project ID tidak ditemukan"}
            
            protector = PptxProtector(project_id)
            
            # Protect with specific entities or auto-detect
            result = protector.protect_file(
                input_path, 
                output_path,
                entities_to_protect=detected_entities,
            )
            
            return {
                "success": result.success,
                "output_path": result.output_path,
                "cells_protected": result.entities_protected,
                "error": result.error_message,
            }
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": str(e),
            }

    def _protect_generic_file(self, file_path: str) -> dict:
        """Protect a generic (non-tabular) file."""
        from pathlib import Path
        
        path = Path(file_path)
        ext = path.suffix.lower()
        
        # For now, these file types are not yet supported
        supported_soon = {
            ".docx": "Word Document",
            ".doc": "Word Document", 
            ".pptx": "PowerPoint",
            ".ppt": "PowerPoint",
            ".pdf": "PDF Document",
        }
        
        file_type = supported_soon.get(ext, f"File {ext}")
        
        return {
            "success": False,
            "error": f"Proteksi untuk {file_type} akan segera tersedia.\n\nSaat ini didukung: Excel (XLSX/XLS), CSV, dan TXT.",
        }
    
    def _get_output_directory(self) -> Path:
        """Get the output directory for protected files."""
        from pathlib import Path
        from sandiraksa.config import get_app_config
        
        # Try to get from config
        try:
            config = get_app_config()
            if hasattr(config, 'output_directory') and config.output_directory:
                output_dir = Path(config.output_directory)
                output_dir.mkdir(parents=True, exist_ok=True)
                return output_dir
        except Exception:
            pass
        
        # Default to user documents folder
        import os
        docs_dir = Path(os.path.expanduser("~/Documents/SandiRaksa/Protected"))
        docs_dir.mkdir(parents=True, exist_ok=True)
        return docs_dir
    
    def _get_filename_suffix(self) -> str:
        """Get the filename suffix from project settings."""
        from sandiraksa.storage.repositories import ProjectRepository
        from sandiraksa.security.vault import get_project_vault
        import json
        
        if not self._current_project_id:
            return "_protected"
        
        try:
            repo = ProjectRepository()
            record = repo.get_by_id(self._current_project_id)
            
            if record.settings_enc:
                vault = get_project_vault(self._current_project_id)
                settings_json = vault.decrypt_string(
                    record.settings_enc,
                    table="projects",
                    row_id=self._current_project_id,
                    field="settings_enc"
                )
                extra_settings = json.loads(settings_json)
                return extra_settings.get("filename_suffix", "_protected") or "_protected"
        except Exception as e:
            print(f"Error getting filename suffix: {e}")
        
        return "_protected"
    
    def _on_download_file(self, file_id: str) -> None:
        """Handle download file request."""
        from pathlib import Path
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        import subprocess
        import os
        
        project_view = self._pages.get(Page.PROJECT_VIEW)
        if not project_view:
            return
        
        file_info = project_view.get_file_info(file_id)
        if not file_info:
            self.set_status("File tidak ditemukan")
            return
        
        output_path = file_info.get("output_path")
        if not output_path or not Path(output_path).exists():
            QMessageBox.warning(
                self,
                "File Tidak Ditemukan",
                "File yang diproteksi tidak ditemukan. Silakan proteksi ulang.",
            )
            return
        
        # Show save dialog
        output_path = Path(output_path)
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Simpan File Terproteksi",
            str(Path.home() / "Downloads" / output_path.name),
            f"Excel Files (*{output_path.suffix})",
        )
        
        # Process pending events to ensure dialog fully closed
        from PySide6.QtWidgets import QApplication
        QApplication.processEvents()
        
        if not save_path:
            return
        
        import shutil
        try:
            shutil.copy2(output_path, save_path)
            self.set_status(f"File tersimpan: {save_path}")
            
            # Ask if user wants to open folder
            reply = QMessageBox.question(
                self,
                "Berhasil",
                f"File tersimpan di:\n{save_path}\n\nBuka folder?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                # Open folder containing file
                folder = Path(save_path).parent
                if os.name == 'nt':  # Windows
                    subprocess.run(['explorer', '/select,', str(save_path)])
                else:  # Linux/Mac
                    subprocess.run(['xdg-open', str(folder)])
                    
        except Exception as e:
            QMessageBox.warning(
                self,
                "Error",
                f"Gagal menyimpan file:\n{str(e)}",
            )
