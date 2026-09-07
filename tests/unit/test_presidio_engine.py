"""Tests for Presidio integration."""

import pytest

from sandiraksa.detection.presidio_engine import (
    PRESIDIO_ENTITY_MAP,
    RegexRecognizer,
    create_detection_engine,
)


class TestRegexRecognizer:
    """Tests for the regex-based fallback recognizer."""

    def test_detect_email(self):
        """Should detect email addresses."""
        recognizer = RegexRecognizer(["EMAIL_ADDRESS"])
        
        results = recognizer.analyze(
            "Contact me at test@example.com for more info",
            ["EMAIL_ADDRESS"],
        )
        
        assert len(results) == 1
        assert results[0].text == "test@example.com"
        assert results[0].entity_type == "EMAIL_ADDRESS"
        assert results[0].score >= 0.8

    def test_detect_multiple_emails(self):
        """Should detect multiple email addresses."""
        recognizer = RegexRecognizer(["EMAIL_ADDRESS"])
        
        results = recognizer.analyze(
            "Email john@test.com or jane.doe@example.org",
            ["EMAIL_ADDRESS"],
        )
        
        assert len(results) == 2

    def test_detect_phone_international(self):
        """Should detect international phone numbers."""
        recognizer = RegexRecognizer(["PHONE_NUMBER"])
        
        results = recognizer.analyze(
            "Call me at +1-555-123-4567",
            ["PHONE_NUMBER"],
        )
        
        assert len(results) >= 1
        assert "+1-555-123-4567" in results[0].text or "555-123-4567" in results[0].text

    def test_detect_credit_card(self):
        """Should detect credit card numbers."""
        recognizer = RegexRecognizer(["CREDIT_CARD"])
        
        # Visa-like number
        results = recognizer.analyze(
            "Card: 4111-1111-1111-1111",
            ["CREDIT_CARD"],
        )
        
        assert len(results) >= 1

    def test_detect_ip_address_v4(self):
        """Should detect IPv4 addresses."""
        recognizer = RegexRecognizer(["IP_ADDRESS"])
        
        results = recognizer.analyze(
            "Server IP: 192.168.1.100",
            ["IP_ADDRESS"],
        )
        
        assert len(results) == 1
        assert results[0].text == "192.168.1.100"

    def test_detect_url(self):
        """Should detect URLs."""
        recognizer = RegexRecognizer(["URL"])
        
        results = recognizer.analyze(
            "Visit https://example.com/page for details",
            ["URL"],
        )
        
        assert len(results) == 1
        assert "https://example.com" in results[0].text

    def test_detect_iban(self):
        """Should detect IBAN codes."""
        recognizer = RegexRecognizer(["IBAN_CODE"])
        
        results = recognizer.analyze(
            "Bank: DE89370400440532013000",
            ["IBAN_CODE"],
        )
        
        assert len(results) == 1
        assert results[0].text == "DE89370400440532013000"

    def test_filter_by_requested_entities(self):
        """Should only return results for requested entity types."""
        recognizer = RegexRecognizer(["EMAIL_ADDRESS", "PHONE_NUMBER"])
        
        results = recognizer.analyze(
            "Email: test@test.com, IP: 192.168.1.1",
            ["EMAIL_ADDRESS"],  # Only request EMAIL
        )
        
        # Should only find email, not IP (even though text contains it)
        assert len(results) == 1
        assert results[0].entity_type == "EMAIL_ADDRESS"

    def test_no_false_positives_on_partial_match(self):
        """Should not match partial patterns."""
        recognizer = RegexRecognizer(["IP_ADDRESS"])
        
        results = recognizer.analyze(
            "Version 1.2.3 is released",  # Not an IP
            ["IP_ADDRESS"],
        )
        
        # Should not match version numbers as IPs
        # 1.2.3 doesn't have 4 octets
        assert len(results) == 0


class TestPresidioEntityMap:
    """Tests for entity type mapping."""

    def test_standard_entities_mapped(self):
        """Standard entities should be mapped."""
        assert "PERSON" in PRESIDIO_ENTITY_MAP
        assert "EMAIL_ADDRESS" in PRESIDIO_ENTITY_MAP
        assert "CREDIT_CARD" in PRESIDIO_ENTITY_MAP

    def test_mapping_consistency(self):
        """Mappings should be to valid entity types."""
        from sandiraksa.detection.entity_types import get_entity_registry
        
        registry = get_entity_registry()
        
        for presidio_type, our_type in PRESIDIO_ENTITY_MAP.items():
            # Either it maps to a known type or to itself
            entity = registry.get(our_type)
            # Allow mapping to types not in registry (custom/future)
            if entity:
                assert entity.name == our_type


class TestDetectionEngineFactory:
    """Tests for engine factory."""

    def test_create_fallback_engine(self):
        """Should create regex engine when Presidio not requested."""
        engine = create_detection_engine(use_presidio=False)
        
        assert engine is not None
        assert engine._initialized
        
        # Should have regex recognizer
        recognizers = engine.registry.all()
        assert any(r.name == "regex" for r in recognizers)

    def test_engine_can_analyze(self):
        """Engine should be able to analyze text."""
        engine = create_detection_engine(use_presidio=False)
        
        from sandiraksa.detection.context import DetectionContext
        
        context = DetectionContext(
            operation_id="test-op",
            file_id="test-file",
            project_id="test-proj",
        )
        context.config.enabled_entity_types = {"EMAIL_ADDRESS"}
        
        results = engine.analyze_text(
            "Contact: test@example.com",
            context,
        )
        
        assert len(results) == 1
        assert results[0].entity_type == "EMAIL_ADDRESS"
