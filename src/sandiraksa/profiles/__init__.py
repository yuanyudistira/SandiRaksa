"""
Privacy Profiles for SandiRaksa.

Predefined configurations for common use cases.
"""

from sandiraksa.profiles.definitions import (
    BANKING_PROFILE,
    HEALTHCARE_PROFILE,
    HR_PROFILE,
    LEGAL_PROFILE,
    STANDARD_PROFILE,
    PrivacyProfile,
    get_all_profiles,
    get_profile,
    get_profile_names,
)

__all__ = [
    "PrivacyProfile",
    "get_profile",
    "get_all_profiles",
    "get_profile_names",
    "STANDARD_PROFILE",
    "HR_PROFILE",
    "BANKING_PROFILE",
    "HEALTHCARE_PROFILE",
    "LEGAL_PROFILE",
]
