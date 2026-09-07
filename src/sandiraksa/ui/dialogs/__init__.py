"""UI dialogs for SandiRaksa."""

from sandiraksa.ui.dialogs.project_settings import ProjectSettingsDialog
from sandiraksa.ui.dialogs.about_dialog import AboutDialog
from sandiraksa.ui.dialogs.column_selection import (
    ColumnInfo,
    WorksheetInfo,
    ColumnSelectionDialog,
    analyze_excel_file,
)
from sandiraksa.ui.dialogs.txt_preview import TxtPreviewDialog
from sandiraksa.ui.dialogs.document_preview import DocumentPreviewDialog
from sandiraksa.ui.dialogs.help_dialog import HelpDialog
from sandiraksa.ui.dialogs.docs_dialog import DocsDialog
from sandiraksa.ui.dialogs.contact_dialog import ContactDialog
from sandiraksa.ui.dialogs.donate_dialog import DonateDialog

__all__ = [
    "AboutDialog",
    "ProjectSettingsDialog",
    "ColumnInfo",
    "WorksheetInfo",
    "ColumnSelectionDialog",
    "analyze_excel_file",
    "TxtPreviewDialog",
    "DocumentPreviewDialog",
    "HelpDialog",
    "DocsDialog",
    "ContactDialog",
    "DonateDialog",
]
