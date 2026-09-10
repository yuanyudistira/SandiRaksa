"""Indonesian-specific entity recognizers and custom terms."""

from sandiraksa.detection.recognizers.id_nik import NIKRecognizer
from sandiraksa.detection.recognizers.id_npwp import NPWPRecognizer
from sandiraksa.detection.recognizers.id_kk import KKRecognizer
from sandiraksa.detection.recognizers.id_phone import IndonesianPhoneRecognizer
from sandiraksa.detection.recognizers.custom_terms import (
    CustomTerm,
    CustomTermsManager,
    CustomTermsRecognizer,
    MatchType,
    get_custom_terms_manager,
    initialize_custom_terms_manager,
)

# Enhanced recognizers (Sprint 4)
from sandiraksa.detection.recognizers.enhanced_nik import (
    EnhancedNIKRecognizer,
    NIKMetadata,
    VALID_PROVINCE_CODES,
    parse_nik,
)
from sandiraksa.detection.recognizers.enhanced_npwp import (
    EnhancedNPWPRecognizer,
    format_npwp,
    parse_npwp,
)
from sandiraksa.detection.recognizers.enhanced_kk import (
    EnhancedKKRecognizer,
    KKMetadata,
    parse_kk,
)
from sandiraksa.detection.recognizers.enhanced_phone import (
    EnhancedPhoneRecognizer,
    CARRIER_PREFIXES,
    format_phone_indonesia,
    parse_phone_indonesia,
)
from sandiraksa.detection.recognizers.id_bpjs import (
    BPJSRecognizer,
    BPJSMetadata,
    format_bpjs,
)
from sandiraksa.detection.recognizers.id_bpjs_legacy import (
    BPJSRecognizerLegacy,
)
from sandiraksa.detection.recognizers.id_sim import (
    SIMRecognizer,
    SIMMetadata,
)
from sandiraksa.detection.recognizers.id_passport import (
    PassportRecognizer,
    PassportMetadata,
    format_passport,
)

# Context-aware recognizers for names and birth dates
from sandiraksa.detection.recognizers.id_dob import DateOfBirthRecognizer
from sandiraksa.detection.recognizers.id_person import IndonesianPersonRecognizer
from sandiraksa.detection.recognizers.context_classifier import (
    classify_label,
    classify_segment_by_context,
    get_segment_label,
)
from sandiraksa.detection.recognizers.person_filter import (
    filter_person_detections,
    is_false_positive_person,
)

__all__ = [
    # Original Indonesian recognizers
    "NIKRecognizer",
    "NPWPRecognizer",
    "KKRecognizer",
    "IndonesianPhoneRecognizer",
    # Context-aware recognizers
    "DateOfBirthRecognizer",
    "IndonesianPersonRecognizer",
    "classify_label",
    "classify_segment_by_context",
    "get_segment_label",
    "filter_person_detections",
    "is_false_positive_person",
    # Enhanced Indonesian recognizers (Sprint 4)
    "EnhancedNIKRecognizer",
    "NIKMetadata",
    "VALID_PROVINCE_CODES",
    "parse_nik",
    "EnhancedNPWPRecognizer",
    "format_npwp",
    "parse_npwp",
    "EnhancedKKRecognizer",
    "KKMetadata",
    "parse_kk",
    "EnhancedPhoneRecognizer",
    "CARRIER_PREFIXES",
    "format_phone_indonesia",
    "parse_phone_indonesia",
    # New Indonesian recognizers (Sprint 4)
    "BPJSRecognizer",
    "BPJSRecognizerLegacy",
    "BPJSMetadata",
    "format_bpjs",
    "SIMRecognizer",
    "SIMMetadata",
    "PassportRecognizer",
    "PassportMetadata",
    "format_passport",
    # Custom Terms
    "CustomTerm",
    "CustomTermsRecognizer",
    "CustomTermsManager",
    "MatchType",
    "get_custom_terms_manager",
    "initialize_custom_terms_manager",
]
