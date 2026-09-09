"""
Backward Compatibility Tests for SandiRaksa.

Verifies that:
- Existing projects can be opened
- Token vaults remain intact
- Operation history is preserved
- Settings are migrated properly
- Protected files are not reprocessed

Critical for ensuring upgrades don't break existing user data.
"""

from tests.compatibility.test_backward_compat import (
    CompatibilityChecker,
    CompatibilityResult,
    CompatibilityReport,
    check_backward_compatibility,
)

__all__ = [
    "CompatibilityChecker",
    "CompatibilityResult",
    "CompatibilityReport",
    "check_backward_compatibility",
]
