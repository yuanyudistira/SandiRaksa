"""
Project Settings Dialog.

Dialog for configuring project settings.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from sandiraksa.app.i18n import tr
from sandiraksa.ui.theme import ColorPalette, FONT_SIZE, SPACING

if TYPE_CHECKING:
    pass


class ProjectSettingsDialog(QDialog):
    """
    Dialog for project settings.

    Organized in tabs: General, Privacy, Output.
    """

    settings_saved = Signal(dict)

    def __init__(
        self,
        project_settings: dict | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._settings = project_settings or {}
        self._setup_ui()
        self._load_settings()

    def _setup_ui(self) -> None:
        """Setup the UI layout."""
        self.setWindowTitle(tr("settings.title"))
        self.setMinimumSize(600, 500)

        layout = QVBoxLayout(self)
        layout.setSpacing(SPACING.LG)

        # Tab widget
        tabs = QTabWidget()

        # General tab
        general_tab = self._create_general_tab()
        tabs.addTab(general_tab, tr("settings.general"))

        # Privacy tab
        privacy_tab = self._create_privacy_tab()
        tabs.addTab(privacy_tab, tr("settings.privacy"))

        # Output tab
        output_tab = self._create_output_tab()
        tabs.addTab(output_tab, tr("settings.output"))

        layout.addWidget(tabs)

        # Buttons
        buttons = QHBoxLayout()
        buttons.addStretch()

        cancel_btn = QPushButton(tr("buttons.cancel"))
        cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(cancel_btn)

        save_btn = QPushButton(tr("settings.save_settings"))
        save_btn.clicked.connect(self._save_settings)
        buttons.addWidget(save_btn)

        layout.addLayout(buttons)

    def _create_general_tab(self) -> QWidget:
        """Create the General settings tab."""
        widget = QWidget()
        layout = QFormLayout(widget)
        layout.setSpacing(SPACING.MD)

        # Project name
        self._name_input = QLineEdit()
        layout.addRow(tr("settings.project_name") + ":", self._name_input)

        # Description
        self._desc_input = QTextEdit()
        self._desc_input.setMaximumHeight(100)
        layout.addRow(tr("settings.description") + ":", self._desc_input)

        layout.addItem(layout.itemAt(layout.count() - 1))  # Spacer

        return widget

    def _create_privacy_tab(self) -> QWidget:
        """Create the Privacy settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(SPACING.MD)

        # Profile selection
        profile_group = QGroupBox(tr("settings.profile"))
        profile_layout = QVBoxLayout(profile_group)

        self._profile_combo = QComboBox()
        profiles = [
            ("standard", tr("profiles.standard")),
            ("hr", tr("profiles.hr")),
            ("banking", tr("profiles.banking")),
            ("healthcare", tr("profiles.healthcare")),
            ("legal", tr("profiles.legal")),
        ]
        for value, label in profiles:
            self._profile_combo.addItem(label, value)
        profile_layout.addWidget(self._profile_combo)

        layout.addWidget(profile_group)

        # Entity types
        entity_group = QGroupBox(tr("settings.entity_types"))
        entity_layout = QVBoxLayout(entity_group)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        entity_content = QWidget()
        entity_inner = QVBoxLayout(entity_content)
        entity_inner.setSpacing(SPACING.XS)

        self._entity_checkboxes: dict[str, QCheckBox] = {}
        entity_types = [
            "PERSON", "EMAIL", "PHONE", "ADDRESS",
            "ID_NIK", "ID_NPWP", "ID_KK", "ID_PHONE",
            "CREDIT_CARD", "BANK_ACCOUNT", "DATE",
            "ORGANIZATION", "LOCATION", "IP_ADDRESS", "URL",
        ]
        for entity_type in entity_types:
            cb = QCheckBox(tr(f"entity_types.{entity_type}"))
            cb.setChecked(True)
            self._entity_checkboxes[entity_type] = cb
            entity_inner.addWidget(cb)

        entity_inner.addStretch()
        scroll.setWidget(entity_content)
        entity_layout.addWidget(scroll)

        layout.addWidget(entity_group)

        return widget

    def _create_output_tab(self) -> QWidget:
        """Create the Output settings tab."""
        widget = QWidget()
        layout = QFormLayout(widget)
        layout.setSpacing(SPACING.MD)

        # Output folder
        folder_layout = QHBoxLayout()
        self._folder_input = QLineEdit()
        folder_layout.addWidget(self._folder_input)
        browse_btn = QPushButton(tr("buttons.browse"))
        browse_btn.clicked.connect(self._browse_folder)
        folder_layout.addWidget(browse_btn)
        layout.addRow(tr("settings.output_folder") + ":", folder_layout)

        # Filename suffix
        self._suffix_input = QLineEdit()
        self._suffix_input.setPlaceholderText("_protected")
        layout.addRow(tr("settings.filename_suffix") + ":", self._suffix_input)

        return widget

    def _load_settings(self) -> None:
        """Load settings into UI controls."""
        self._name_input.setText(self._settings.get("name", ""))
        self._desc_input.setPlainText(self._settings.get("description", ""))

        # Profile
        profile = self._settings.get("profile", "standard")
        index = self._profile_combo.findData(profile)
        if index >= 0:
            self._profile_combo.setCurrentIndex(index)

        # Entity types
        enabled_types = self._settings.get("entity_types", [])
        if enabled_types:
            for entity_type, cb in self._entity_checkboxes.items():
                cb.setChecked(entity_type in enabled_types)

        # Output
        self._folder_input.setText(self._settings.get("output_folder", ""))
        self._suffix_input.setText(self._settings.get("filename_suffix", "_protected"))

    def _browse_folder(self) -> None:
        """Open folder browser."""
        folder = QFileDialog.getExistingDirectory(
            self,
            tr("settings.output_folder"),
            self._folder_input.text(),
        )
        if folder:
            self._folder_input.setText(folder)

    def _save_settings(self) -> None:
        """Save settings and close dialog."""
        settings = {
            "name": self._name_input.text().strip(),
            "description": self._desc_input.toPlainText().strip(),
            "profile": self._profile_combo.currentData(),
            "entity_types": [
                entity_type
                for entity_type, cb in self._entity_checkboxes.items()
                if cb.isChecked()
            ],
            "output_folder": self._folder_input.text().strip(),
            "filename_suffix": self._suffix_input.text().strip() or "_protected",
        }
        self.settings_saved.emit(settings)
        self.accept()

    def get_settings(self) -> dict:
        """Get the current settings."""
        return {
            "name": self._name_input.text().strip(),
            "description": self._desc_input.toPlainText().strip(),
            "profile": self._profile_combo.currentData(),
            "entity_types": [
                entity_type
                for entity_type, cb in self._entity_checkboxes.items()
                if cb.isChecked()
            ],
            "output_folder": self._folder_input.text().strip(),
            "filename_suffix": self._suffix_input.text().strip() or "_protected",
        }


__all__ = ["ProjectSettingsDialog"]
