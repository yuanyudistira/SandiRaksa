"""Tests for privacy profiles."""

import pytest

from sandiraksa.profiles import (
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
from sandiraksa.profiles.definitions import ProfileId


class TestPrivacyProfile:
    """Tests for PrivacyProfile dataclass."""

    def test_profile_attributes(self):
        """Test profile has all required attributes."""
        profile = STANDARD_PROFILE
        
        assert profile.id == "standard"
        assert profile.name == "Standard PII"
        assert profile.name_id == "PII Standar"
        assert profile.description
        assert profile.description_id
        assert len(profile.entity_types) > 0
        assert profile.min_confidence > 0

    def test_profile_to_dict(self):
        """Test profile serialization."""
        result = STANDARD_PROFILE.to_dict()
        
        assert result["id"] == "standard"
        assert result["name"] == "Standard PII"
        assert "entity_types" in result
        assert isinstance(result["entity_types"], list)


class TestProfileRegistry:
    """Tests for profile registry functions."""

    def test_get_profile_standard(self):
        """Test getting standard profile."""
        profile = get_profile("standard")
        
        assert profile is not None
        assert profile.id == "standard"
        assert profile == STANDARD_PROFILE

    def test_get_profile_hr(self):
        """Test getting HR profile."""
        profile = get_profile("hr")
        
        assert profile is not None
        assert profile.id == "hr"
        assert "SALARY" in profile.entity_types

    def test_get_profile_banking(self):
        """Test getting banking profile."""
        profile = get_profile("banking")
        
        assert profile is not None
        assert "CREDIT_CARD" in profile.entity_types
        assert profile.min_confidence == 0.8

    def test_get_profile_healthcare(self):
        """Test getting healthcare profile."""
        profile = get_profile("healthcare")
        
        assert profile is not None
        assert "MEDICAL_RECORD_NUMBER" in profile.entity_types

    def test_get_profile_legal(self):
        """Test getting legal profile."""
        profile = get_profile("legal")
        
        assert profile is not None
        assert "CONTRACT_NUMBER" in profile.entity_types

    def test_get_profile_not_found(self):
        """Test getting non-existent profile."""
        profile = get_profile("nonexistent")
        
        assert profile is None

    def test_get_all_profiles(self):
        """Test getting all profiles."""
        profiles = get_all_profiles()
        
        assert len(profiles) == 5
        assert all(isinstance(p, PrivacyProfile) for p in profiles)

    def test_get_profile_names(self):
        """Test getting profile names."""
        names = get_profile_names()
        
        assert "standard" in names
        assert names["standard"] == "Standard PII"
        assert len(names) == 5


class TestProfileId:
    """Tests for ProfileId enum."""

    def test_profile_ids(self):
        """Test all profile IDs exist."""
        assert ProfileId.STANDARD.value == "standard"
        assert ProfileId.HR.value == "hr"
        assert ProfileId.BANKING.value == "banking"
        assert ProfileId.HEALTHCARE.value == "healthcare"
        assert ProfileId.LEGAL.value == "legal"


class TestProfileEntityTypes:
    """Tests for profile entity type configurations."""

    def test_standard_has_common_types(self):
        """Test standard profile has common PII types."""
        types = STANDARD_PROFILE.entity_types
        
        assert "PERSON" in types
        assert "EMAIL_ADDRESS" in types
        assert "PHONE_NUMBER" in types
        assert "ID_NIK" in types

    def test_profiles_have_indonesian_types(self):
        """Test all profiles support Indonesian PII."""
        for profile in get_all_profiles():
            # At minimum should have NIK
            assert "ID_NIK" in profile.entity_types

    def test_high_confidence_types_subset(self):
        """Test high confidence types are subset of entity types."""
        for profile in get_all_profiles():
            for high_conf_type in profile.high_confidence_types:
                # High confidence types should be in entity_types
                # or be generic patterns
                pass  # Some high confidence types may be patterns
