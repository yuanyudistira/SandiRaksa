"""
Benchmark Corpus for PII Detection Accuracy Testing.

Contains synthetic test data covering:
- Document types: HR, Medical, Banking, Legal, Customer, Payroll
- Indonesian names: Javanese, Sundanese, Batak, Minang, Chinese-Indonesian
- Indonesian IDs: NIK, NPWP, KK, BPJS, Phone
- Negative examples: Company names, addresses, reference numbers

Each corpus entry includes:
- text: The document text
- annotations: List of expected PII with positions
- metadata: Document type, format, etc.
"""

from tests.accuracy.corpus.generator import (
    CorpusEntry,
    Annotation,
    CorpusGenerator,
    load_corpus,
    generate_full_corpus,
)
from tests.accuracy.corpus.indonesian_data import (
    INDONESIAN_NAMES,
    INDONESIAN_ADDRESSES,
    COMPANY_NAMES,
    generate_nik,
    generate_npwp,
    generate_phone,
)

__all__ = [
    "CorpusEntry",
    "Annotation",
    "CorpusGenerator",
    "load_corpus",
    "generate_full_corpus",
    "INDONESIAN_NAMES",
    "INDONESIAN_ADDRESSES",
    "COMPANY_NAMES",
    "generate_nik",
    "generate_npwp",
    "generate_phone",
]
