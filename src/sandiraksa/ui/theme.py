"""
UI Theme and Styling for SandiRaksa.

Defines colors, fonts, and styles used throughout the application.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ColorPalette(str, Enum):
    """Application color palette."""

    # Primary colors
    PRIMARY = "#2563eb"
    PRIMARY_DARK = "#1d4ed8"
    PRIMARY_LIGHT = "#3b82f6"

    # Secondary colors
    SECONDARY = "#64748b"
    SECONDARY_DARK = "#475569"
    SECONDARY_LIGHT = "#94a3b8"

    # Semantic colors
    SUCCESS = "#22c55e"
    SUCCESS_DARK = "#16a34a"
    WARNING = "#f59e0b"
    WARNING_DARK = "#d97706"
    ERROR = "#ef4444"
    ERROR_DARK = "#dc2626"
    INFO = "#3b82f6"

    # Neutrals
    WHITE = "#ffffff"
    BLACK = "#000000"
    GRAY_50 = "#f8fafc"
    GRAY_100 = "#f1f5f9"
    GRAY_200 = "#e2e8f0"
    GRAY_300 = "#cbd5e1"
    GRAY_400 = "#94a3b8"
    GRAY_500 = "#64748b"
    GRAY_600 = "#475569"
    GRAY_700 = "#334155"
    GRAY_800 = "#1e293b"
    GRAY_900 = "#0f172a"

    # Entity type colors
    ENTITY_PERSON = "#8b5cf6"
    ENTITY_EMAIL = "#06b6d4"
    ENTITY_PHONE = "#10b981"
    ENTITY_ADDRESS = "#f97316"
    ENTITY_ID = "#ec4899"
    ENTITY_FINANCIAL = "#eab308"
    ENTITY_DEFAULT = "#6b7280"


@dataclass(frozen=True)
class Spacing:
    """Standard spacing values."""

    NONE: int = 0
    XS: int = 4
    SM: int = 8
    MD: int = 12
    LG: int = 16
    XL: int = 24
    XXL: int = 32


@dataclass(frozen=True)
class FontSize:
    """Standard font sizes."""

    XS: int = 10
    SM: int = 12
    MD: int = 14
    LG: int = 16
    XL: int = 20
    XXL: int = 24
    TITLE: int = 32
    HERO: int = 48


@dataclass(frozen=True)
class BorderRadius:
    """Standard border radius values."""

    NONE: int = 0
    SM: int = 4
    MD: int = 8
    LG: int = 12
    XL: int = 16
    FULL: int = 9999


SPACING = Spacing()
FONT_SIZE = FontSize()
BORDER_RADIUS = BorderRadius()


def get_entity_color(entity_type: str) -> str:
    """Get color for an entity type."""
    type_colors = {
        "PERSON": ColorPalette.ENTITY_PERSON.value,
        "EMAIL": ColorPalette.ENTITY_EMAIL.value,
        "PHONE": ColorPalette.ENTITY_PHONE.value,
        "ID_PHONE": ColorPalette.ENTITY_PHONE.value,
        "ADDRESS": ColorPalette.ENTITY_ADDRESS.value,
        "LOCATION": ColorPalette.ENTITY_ADDRESS.value,
        "ID_NIK": ColorPalette.ENTITY_ID.value,
        "ID_NPWP": ColorPalette.ENTITY_ID.value,
        "ID_KK": ColorPalette.ENTITY_ID.value,
        "CREDIT_CARD": ColorPalette.ENTITY_FINANCIAL.value,
        "BANK_ACCOUNT": ColorPalette.ENTITY_FINANCIAL.value,
    }
    return type_colors.get(entity_type, ColorPalette.ENTITY_DEFAULT.value)


# Global stylesheet
STYLESHEET = f"""
/* Global styles */
QMainWindow {{
    background-color: {ColorPalette.WHITE.value};
}}

QWidget {{
    font-family: "Segoe UI", "SF Pro Display", system-ui, sans-serif;
    font-size: {FONT_SIZE.MD}px;
    color: {ColorPalette.GRAY_800.value};
}}

/* Buttons */
QPushButton {{
    background-color: {ColorPalette.PRIMARY.value};
    color: {ColorPalette.WHITE.value};
    border: none;
    border-radius: {BORDER_RADIUS.MD}px;
    padding: {SPACING.SM}px {SPACING.LG}px;
    font-weight: 500;
    min-height: 36px;
}}

QPushButton:hover {{
    background-color: {ColorPalette.PRIMARY_DARK.value};
}}

QPushButton:pressed {{
    background-color: {ColorPalette.PRIMARY_DARK.value};
}}

QPushButton:disabled {{
    background-color: {ColorPalette.GRAY_300.value};
    color: {ColorPalette.GRAY_500.value};
}}

QPushButton[secondary="true"] {{
    background-color: {ColorPalette.WHITE.value};
    color: {ColorPalette.GRAY_700.value};
    border: 1px solid {ColorPalette.GRAY_300.value};
}}

QPushButton[secondary="true"]:hover {{
    background-color: {ColorPalette.GRAY_50.value};
    border-color: {ColorPalette.GRAY_400.value};
}}

QPushButton[danger="true"] {{
    background-color: {ColorPalette.ERROR.value};
}}

QPushButton[danger="true"]:hover {{
    background-color: {ColorPalette.ERROR_DARK.value};
}}

/* Text inputs */
QLineEdit, QTextEdit, QPlainTextEdit {{
    background-color: {ColorPalette.WHITE.value};
    border: 1px solid {ColorPalette.GRAY_300.value};
    border-radius: {BORDER_RADIUS.MD}px;
    padding: {SPACING.SM}px {SPACING.MD}px;
    selection-background-color: {ColorPalette.PRIMARY_LIGHT.value};
}}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
    border-color: {ColorPalette.PRIMARY.value};
    outline: none;
}}

QLineEdit:disabled {{
    background-color: {ColorPalette.GRAY_100.value};
    color: {ColorPalette.GRAY_500.value};
}}

/* Combo box */
QComboBox {{
    background-color: {ColorPalette.WHITE.value};
    border: 1px solid {ColorPalette.GRAY_300.value};
    border-radius: {BORDER_RADIUS.MD}px;
    padding: {SPACING.SM}px {SPACING.MD}px;
    min-height: 36px;
}}

QComboBox:hover {{
    border-color: {ColorPalette.GRAY_400.value};
}}

QComboBox::drop-down {{
    border: none;
    width: 24px;
}}

QComboBox::down-arrow {{
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 5px solid {ColorPalette.GRAY_600.value};
    margin-right: 8px;
}}

/* Checkboxes */
QCheckBox {{
    spacing: {SPACING.SM}px;
}}

QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border: 2px solid {ColorPalette.GRAY_400.value};
    border-radius: {BORDER_RADIUS.SM}px;
    background-color: {ColorPalette.WHITE.value};
}}

QCheckBox::indicator:checked {{
    background-color: {ColorPalette.PRIMARY.value};
    border-color: {ColorPalette.PRIMARY.value};
}}

/* Tables */
QTableWidget, QTableView {{
    background-color: {ColorPalette.WHITE.value};
    border: 1px solid {ColorPalette.GRAY_200.value};
    border-radius: {BORDER_RADIUS.MD}px;
    gridline-color: {ColorPalette.GRAY_200.value};
}}

QTableWidget::item, QTableView::item {{
    padding: {SPACING.SM}px;
}}

QTableWidget::item:selected, QTableView::item:selected {{
    background-color: {ColorPalette.PRIMARY_LIGHT.value};
    color: {ColorPalette.WHITE.value};
}}

QHeaderView::section {{
    background-color: {ColorPalette.GRAY_50.value};
    color: {ColorPalette.GRAY_700.value};
    font-weight: 600;
    padding: {SPACING.SM}px {SPACING.MD}px;
    border: none;
    border-bottom: 1px solid {ColorPalette.GRAY_200.value};
}}

/* Scroll bars */
QScrollBar:vertical {{
    background-color: {ColorPalette.GRAY_100.value};
    width: 12px;
    border-radius: 6px;
    margin: 0;
}}

QScrollBar::handle:vertical {{
    background-color: {ColorPalette.GRAY_400.value};
    border-radius: 6px;
    min-height: 30px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: {ColorPalette.GRAY_500.value};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}

QScrollBar:horizontal {{
    background-color: {ColorPalette.GRAY_100.value};
    height: 12px;
    border-radius: 6px;
}}

QScrollBar::handle:horizontal {{
    background-color: {ColorPalette.GRAY_400.value};
    border-radius: 6px;
    min-width: 30px;
}}

/* Progress bar */
QProgressBar {{
    background-color: {ColorPalette.GRAY_200.value};
    border: none;
    border-radius: {BORDER_RADIUS.SM}px;
    height: 8px;
    text-align: center;
}}

QProgressBar::chunk {{
    background-color: {ColorPalette.PRIMARY.value};
    border-radius: {BORDER_RADIUS.SM}px;
}}

/* Labels */
QLabel[heading="true"] {{
    font-size: {FONT_SIZE.XL}px;
    font-weight: 600;
    color: {ColorPalette.GRAY_900.value};
}}

QLabel[subheading="true"] {{
    font-size: {FONT_SIZE.MD}px;
    color: {ColorPalette.GRAY_600.value};
}}

QLabel[error="true"] {{
    color: {ColorPalette.ERROR.value};
}}

QLabel[success="true"] {{
    color: {ColorPalette.SUCCESS.value};
}}

/* Cards */
QFrame[card="true"] {{
    background-color: {ColorPalette.WHITE.value};
    border: 1px solid {ColorPalette.GRAY_200.value};
    border-radius: {BORDER_RADIUS.LG}px;
    padding: {SPACING.LG}px;
}}

QFrame[card="true"]:hover {{
    border-color: {ColorPalette.GRAY_300.value};
    background-color: {ColorPalette.GRAY_50.value};
}}

/* Status bar */
QStatusBar {{
    background-color: {ColorPalette.GRAY_50.value};
    border-top: 1px solid {ColorPalette.GRAY_200.value};
    color: {ColorPalette.GRAY_600.value};
}}

/* Menu bar */
QMenuBar {{
    background-color: {ColorPalette.WHITE.value};
    border-bottom: 1px solid {ColorPalette.GRAY_200.value};
}}

QMenuBar::item {{
    padding: {SPACING.SM}px {SPACING.MD}px;
}}

QMenuBar::item:selected {{
    background-color: {ColorPalette.GRAY_100.value};
}}

QMenu {{
    background-color: {ColorPalette.WHITE.value};
    border: 1px solid {ColorPalette.GRAY_200.value};
    border-radius: {BORDER_RADIUS.MD}px;
    padding: {SPACING.XS}px;
}}

QMenu::item {{
    padding: {SPACING.SM}px {SPACING.LG}px;
    border-radius: {BORDER_RADIUS.SM}px;
}}

QMenu::item:selected {{
    background-color: {ColorPalette.GRAY_100.value};
}}

QMenu::separator {{
    height: 1px;
    background-color: {ColorPalette.GRAY_200.value};
    margin: {SPACING.XS}px {SPACING.SM}px;
}}

/* Tab widget */
QTabWidget::pane {{
    border: 1px solid {ColorPalette.GRAY_200.value};
    border-radius: {BORDER_RADIUS.MD}px;
    background-color: {ColorPalette.WHITE.value};
}}

QTabBar::tab {{
    background-color: {ColorPalette.GRAY_100.value};
    border: none;
    padding: {SPACING.SM}px {SPACING.LG}px;
    margin-right: 2px;
    border-top-left-radius: {BORDER_RADIUS.MD}px;
    border-top-right-radius: {BORDER_RADIUS.MD}px;
}}

QTabBar::tab:selected {{
    background-color: {ColorPalette.WHITE.value};
    border-bottom: 2px solid {ColorPalette.PRIMARY.value};
}}

QTabBar::tab:hover:!selected {{
    background-color: {ColorPalette.GRAY_200.value};
}}

/* Tool tips */
QToolTip {{
    background-color: {ColorPalette.GRAY_800.value};
    color: {ColorPalette.WHITE.value};
    border: none;
    border-radius: {BORDER_RADIUS.SM}px;
    padding: {SPACING.SM}px {SPACING.MD}px;
}}
"""


__all__ = [
    "BORDER_RADIUS",
    "ColorPalette",
    "FONT_SIZE",
    "SPACING",
    "STYLESHEET",
    "get_entity_color",
]
