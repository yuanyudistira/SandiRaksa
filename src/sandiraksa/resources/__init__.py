"""Resources module for SandiRaksa."""

import sys
from pathlib import Path

RESOURCES_DIR = Path(__file__).parent
I18N_DIR = RESOURCES_DIR / "i18n"
ICONS_DIR = RESOURCES_DIR / "icons"


def resource_path(relative: str) -> Path:
    """
    Resolve a path to a bundled resource, both in dev and when frozen.

    In a PyInstaller onefile build, data files are extracted to ``sys._MEIPASS``.
    The spec bundles ``src/sandiraksa/resources`` as ``sandiraksa/resources``, so
    ``Path(__file__).parent`` already resolves correctly inside the frozen app;
    this helper additionally honors ``sys._MEIPASS`` for assets bundled at other
    roots (e.g. an ``assets/`` tree added to the spec ``datas``).

    Args:
        relative: Path relative to the resources dir (e.g. "icons/sandiraksa.ico")
                  or to the frozen root (e.g. "assets/windows/sandiraksa.ico").

    Returns:
        An absolute Path to the resource. Falls back to the resources-relative
        location when the frozen-root candidate does not exist.
    """
    rel = Path(relative)

    # 1. Resources-relative (works in dev and frozen because resources/ is bundled)
    candidate = RESOURCES_DIR / rel
    if candidate.exists():
        return candidate

    # 2. Frozen root (sys._MEIPASS) for assets bundled at the app root
    base = getattr(sys, "_MEIPASS", None)
    if base:
        meipass_candidate = Path(base) / rel
        if meipass_candidate.exists():
            return meipass_candidate

    # 3. Dev fallback: repo root (three levels up from this file:
    #    src/sandiraksa/resources -> src/sandiraksa -> src -> repo root)
    repo_root = RESOURCES_DIR.parent.parent.parent
    return repo_root / rel


def app_icon_path() -> Path:
    """Path to the application .ico (window/taskbar icon)."""
    return resource_path("icons/sandiraksa.ico")


def splash_image_path() -> Path:
    """Path to the splash-screen image."""
    return resource_path("icons/splash.png")


__all__ = [
    "RESOURCES_DIR",
    "I18N_DIR",
    "ICONS_DIR",
    "resource_path",
    "app_icon_path",
    "splash_image_path",
]
