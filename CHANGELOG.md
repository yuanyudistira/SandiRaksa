# Changelog

All notable changes to SandiRaksa will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2024-XX-XX

### Added

#### Core Features
- **Project Management**: Create, manage, and organize protection projects
- **PII Detection Engine**: Multi-recognizer architecture supporting various PII types
- **Tokenization System**: HMAC-based deterministic token generation
- **Protection Pipeline**: End-to-end document protection workflow
- **Restoration Pipeline**: Token-to-original-value restoration

#### Indonesian PII Support
- NIK (Nomor Induk Kependudukan) - 16-digit national ID
- NPWP (Nomor Pokok Wajib Pajak) - Tax identification number
- KK (Kartu Keluarga) - Family card number
- Indonesian phone numbers (+62, 0xxx formats)

#### Document Formats
- CSV with encoding auto-detection
- XLSX (Excel) with multi-sheet support
- DOCX (Word) with paragraphs, tables, headers/footers
- PPTX (PowerPoint) with slides, shapes, notes

#### Privacy Profiles
- Standard PII
- HR & Recruitment
- Banking & Finance
- Healthcare
- Legal & M&A

#### Security
- AES-256-GCM encryption for stored mappings
- OS keyring integration (Windows, macOS, Linux)
- Password-derived fallback key store
- XML security (XXE prevention)
- ZIP bomb protection
- PII redaction in logs

#### User Interface
- Modern PySide6-based GUI
- Bilingual support (English, Bahasa Indonesia)
- Dark/Light theme support
- Project list view
- Scan progress tracking
- Findings review interface
- Restoration interface
- Offline help documentation

### Security
- HMAC-based token IDs prevent prediction
- Project isolation prevents cross-project token leakage
- Input validation and sanitization
- Secure XML parsing with defusedxml

### Technical
- SQLite database with migrations
- Pydantic models for data validation
- Event-driven architecture
- Comprehensive test suite

---

## Version History

- **0.1.0**: Initial MVP release
