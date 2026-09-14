"""
Privacy-safe UI for the Clipboard Privacy Guard (design 53, 54, 55, 56, 57).

Components:
  * ConsentDialog        - opt-in on first activation (design 56).
  * ProtectionPanel      - shows risk, entity counts, protected preview, and
                           Copy protected / Ignore actions (design 54). The
                           original text is NOT shown by default.
  * ClipboardTrayMenu    - tray state indicator + controls (design 55, 57, 58).

All widgets live on the GUI thread. They render only metadata + protected
preview - never raw clipboard values (design 53, 54).
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from sandiraksa.app.i18n import tr
from sandiraksa.clipboard.models import (
    ClipboardMonitorState,
    ClipboardProtectionResult,
    ClipboardRiskLevel,
)

# Risk -> indicator color (design 47/57 aligned).
_RISK_COLOR = {
    ClipboardRiskLevel.LOW: "#6b7280",
    ClipboardRiskLevel.MEDIUM: "#d97706",
    ClipboardRiskLevel.HIGH: "#dc2626",
    ClipboardRiskLevel.CRITICAL: "#7f1d1d",
}

# Monitor state -> indicator color (design 57).
STATE_COLOR = {
    ClipboardMonitorState.OFF: "#9ca3af",            # gray
    ClipboardMonitorState.ACTIVE: "#2563eb",         # blue
    ClipboardMonitorState.PAUSED: "#eab308",         # yellow
    ClipboardMonitorState.USER_INITIATED_ONLY: "#ea580c",  # orange (restricted)
    ClipboardMonitorState.DEGRADED: "#ea580c",       # orange
    ClipboardMonitorState.ERROR: "#dc2626",          # red
    ClipboardMonitorState.PERMISSION_REQUIRED: "#dc2626",  # red
    ClipboardMonitorState.UNSUPPORTED: "#9ca3af",    # gray
}


class ConsentDialog(QDialog):
    """First-activation opt-in consent (design 56)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("clipboard.consent_title"))
        self.setMinimumWidth(440)

        layout = QVBoxLayout(self)
        title = QLabel(tr("clipboard.consent_title"))
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title)

        body = QLabel(tr("clipboard.consent_body"))
        body.setWordWrap(True)
        body.setStyleSheet("color: #374151;")
        layout.addWidget(body)

        buttons = QHBoxLayout()
        buttons.addStretch()
        not_now = QPushButton(tr("clipboard.consent_not_now"))
        not_now.clicked.connect(self.reject)
        enable = QPushButton(tr("clipboard.consent_enable"))
        enable.setDefault(True)
        enable.clicked.connect(self.accept)
        buttons.addWidget(not_now)
        buttons.addWidget(enable)
        layout.addLayout(buttons)


class ProtectionPanel(QDialog):
    """
    Shows a detected result and offers protected copy / ignore (design 54).

    Only the protected preview + metadata are shown; the original clipboard
    text is never displayed.
    """

    #: Emitted when the user chooses to copy the protected version.
    copyRequested = Signal(object)  # ClipboardProtectionResult

    def __init__(
        self,
        result: ClipboardProtectionResult,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._result = result
        self.setWindowTitle(tr("clipboard.feature_name"))
        self.setMinimumWidth(460)

        layout = QVBoxLayout(self)

        title = QLabel(tr("clipboard.panel_title"))
        title.setStyleSheet("font-size: 15px; font-weight: bold;")
        layout.addWidget(title)

        risk_color = _RISK_COLOR.get(result.risk_level, "#374151")
        risk = QLabel(tr("clipboard.panel_risk", risk=result.risk_level.value.upper()))
        risk.setStyleSheet(f"color: {risk_color}; font-weight: 600;")
        layout.addWidget(risk)

        found = QLabel(tr("clipboard.panel_found"))
        found.setStyleSheet("font-weight: 600; margin-top: 6px;")
        layout.addWidget(found)
        for entity_type, count in sorted(result.entity_counts().items()):
            layout.addWidget(QLabel(f"  • {entity_type} × {count}"))

        preview_label = QLabel(tr("clipboard.panel_preview"))
        preview_label.setStyleSheet("font-weight: 600; margin-top: 6px;")
        layout.addWidget(preview_label)

        preview = QTextEdit()
        preview.setReadOnly(True)
        # Only the PROTECTED text is shown (design 54).
        preview.setPlainText(result.safe_text)
        preview.setMaximumHeight(140)
        layout.addWidget(preview)

        buttons = QHBoxLayout()
        buttons.addStretch()
        ignore = QPushButton(tr("clipboard.ignore"))
        ignore.clicked.connect(self.reject)
        copy_btn = QPushButton(tr("clipboard.copy_protected"))
        copy_btn.setDefault(True)
        copy_btn.clicked.connect(self._on_copy)
        buttons.addWidget(ignore)
        buttons.addWidget(copy_btn)
        layout.addLayout(buttons)

    def _on_copy(self) -> None:
        self.copyRequested.emit(self._result)
        self.accept()


def notification_summary(result: ClipboardProtectionResult) -> str:
    """
    Build a privacy-safe notification summary (design 53).

    Contains only entity type + count metadata, never raw values.
    """
    counts = result.entity_counts()
    if not counts:
        return ""
    return ", ".join(f"{k} × {v}" for k, v in sorted(counts.items()))


__all__ = [
    "ConsentDialog",
    "ProtectionPanel",
    "ClipboardMonitorState",
    "STATE_COLOR",
    "notification_summary",
]
