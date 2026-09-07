"""
About Dialog.

Shows application information, version, and credits.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from sandiraksa.app.i18n import tr
from sandiraksa.ui.theme import ColorPalette, FONT_SIZE, SPACING
from sandiraksa.version import __version__

if TYPE_CHECKING:
    pass


class AboutDialog(QDialog):
    """About dialog showing application info."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Setup the UI layout."""
        self.setWindowTitle(tr("about.title"))
        self.setFixedSize(450, 400)

        layout = QVBoxLayout(self)
        layout.setSpacing(SPACING.LG)
        layout.setContentsMargins(SPACING.XL, SPACING.XL, SPACING.XL, SPACING.XL)

        # App icon/name
        title = QLabel("🛡️ SandiRaksa")
        title.setStyleSheet(
            f"font-size: {FONT_SIZE.TITLE}px; "
            f"font-weight: bold; "
            f"color: {ColorPalette.PRIMARY.value};"
        )
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Version
        version_label = QLabel(tr("about.version", version=__version__))
        version_label.setStyleSheet(
            f"font-size: {FONT_SIZE.MD}px; color: {ColorPalette.GRAY_500.value};"
        )
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(version_label)

        # Tagline
        tagline = QLabel(tr("app.tagline"))
        tagline.setStyleSheet(
            f"font-size: {FONT_SIZE.LG}px; color: {ColorPalette.GRAY_700.value};"
        )
        tagline.setWordWrap(True)
        tagline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(tagline)

        layout.addSpacing(SPACING.MD)

        # Description
        desc = QLabel(tr("about.description"))
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color: {ColorPalette.GRAY_600.value};")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(desc)

        layout.addSpacing(SPACING.MD)

        # Features
        features_title = QLabel(tr("about.features_title"))
        features_title.setStyleSheet(
            f"font-weight: 600; color: {ColorPalette.GRAY_800.value};"
        )
        layout.addWidget(features_title)

        features = [
            ("🔒", tr("about.feature_local")),
            ("🔍", tr("about.feature_detect")),
            ("🎯", tr("about.feature_token")),
            ("🔄", tr("about.feature_restore")),
        ]
        for icon, text in features:
            feature = QLabel(f"{icon}  {text}")
            feature.setStyleSheet(
                f"color: {ColorPalette.GRAY_600.value}; "
                f"padding-left: {SPACING.MD}px;"
            )
            feature.setWordWrap(True)
            layout.addWidget(feature)

        layout.addStretch()

        # Copyright
        copyright_label = QLabel(tr("about.copyright"))
        copyright_label.setStyleSheet(
            f"font-size: {FONT_SIZE.SM}px; color: {ColorPalette.GRAY_400.value};"
        )
        copyright_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(copyright_label)

        # Close button
        close_btn = QPushButton(tr("buttons.close"))
        close_btn.clicked.connect(self.accept)
        close_btn.setFixedWidth(100)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignCenter)


__all__ = ["AboutDialog"]
