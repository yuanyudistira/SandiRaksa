"""Resources module for SandiRaksa."""

from pathlib import Path

RESOURCES_DIR = Path(__file__).parent
I18N_DIR = RESOURCES_DIR / "i18n"

__all__ = ["I18N_DIR", "RESOURCES_DIR"]
