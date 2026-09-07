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

__all__ = [
    # Indonesian
    "NIKRecognizer",
    "NPWPRecognizer",
    "KKRecognizer",
    "IndonesianPhoneRecognizer",
    # Custom Terms
    "CustomTerm",
    "CustomTermsRecognizer",
    "CustomTermsManager",
    "MatchType",
    "get_custom_terms_manager",
    "initialize_custom_terms_manager",
]
