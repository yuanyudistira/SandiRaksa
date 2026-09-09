# Changelog

All notable changes to SandiRaksa will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-09-09

### 🎉 First Stable Release

SandiRaksa v1.0.0 marks the first production-ready release with comprehensive PII detection, 
multi-format document support, and enterprise-grade accuracy for Indonesian data.

### Added

#### Detection Engine
- **Unified Detection Engine** - Presidio-based engine with multi-layer detection
- **Indonesian ID Recognizers** - Custom recognizers for NIK, NPWP, KK, BPJS, Indonesian phone numbers
- **Context-Aware Detection** - Contextual analysis using surrounding text patterns
- **Context-Aware Person Names** - Detects Indonesian names via labels, EMR row patterns, and table headers (works across TXT, DOCX, PPTX)
- **Smart Date of Birth Detection** - Distinguishes birth dates from visit/appointment dates using labels, name context, and date plausibility
- **Custom Patterns (Global)** - User-defined regex patterns (e.g. hospital-specific Medical Record formats) that apply across all projects, editable via Settings → Custom Patterns
- **Content-Based Column Recommendation** - Excel/CSV column type suggestions now use both header names AND sample cell content, with false-positive guards for identifier and status columns
- **NER Integration** - Named Entity Recognition with ONNX runtime for PERSON, LOCATION, ORGANIZATION
- **Confidence Scoring** - High/Medium/Low confidence bands with evidence-based explanations

#### Document Support
- **CSV Handler** - Column-based detection and protection
- **Excel Handler** (.xlsx) - Full workbook processing with sheet-aware detection
- **Word Handler** (.docx) - Paragraphs, tables, headers, footers support
- **PowerPoint Handler** (.pptx) - Slides, text frames, tables, speaker notes
- **TXT Handler** - Plain text with pattern-based detection

#### Detection Capabilities
- **Entity Types**: EMAIL, PHONE_NUMBER, NIK, NPWP, KK, BPJS, CREDIT_CARD, IP_ADDRESS, DATE_TIME, PERSON, LOCATION, ORGANIZATION, MEDICAL_LICENSE, IBAN, URL
- **Indonesian Patterns**: 16-digit NIK with province/date validation, NPWP format, KK format, BPJS format, +62/08xx phone patterns
- **Custom Terms**: User-definable sensitive terms per project

#### Protection Pipeline
- **Consistent Tokenization** - Same PII → same token within project
- **Format Preservation** - Maintains document structure and formatting
- **Reversible Protection** - Restore original data from protected files
- **AES-256-GCM Encryption** - Secure token vault with OS keychain integration

#### Confidence & Explainability
- **Confidence Classifier** - ML-based confidence scoring
- **Scan Modes** - STRICT (high recall) and BALANCED (reduced noise)
- **Evidence Builder** - Human-readable explanations for detections
- **Confidence Filtering** - Configurable threshold filtering
- **Leakage Re-scan** - Post-protection verification

#### Quality Assurance
- **Benchmark Corpus** - Synthetic test data (HR, medical, banking documents)
- **Accuracy Metrics** - Precision/recall/F1 measurement per entity type
- **Release Gates** - Minimum F1 thresholds (NIK≥0.95, NPWP≥0.90, EMAIL≥0.95)
- **Performance Benchmarks** - Cold start <5s, warm inference <100ms/KB
- **Backward Compatibility** - Projects/vaults from v0.2.x supported

### Changed
- Detection engine refactored from single-layer to multi-layer architecture
- Improved Indonesian name detection with ethnic diversity support
- Enhanced phone number patterns for all Indonesian carriers
- Better handling of edge cases in OOXML documents

### Security
- 100% local processing - no data transmission
- AES-256-GCM encryption for all token mappings
- OS keychain integration for key storage
- Secure XML parsing (XXE protection)
- No telemetry or crash reporting with document content

### Performance
- Cold start: <5 seconds
- Warm inference: <100ms per KB of text
- Throughput: >10 documents/second
- Peak memory: <500MB

---

## [0.2.2] - 2026-09-09

### Fixed
- **CI Release Workflow** - Simplified to Windows-only build (removed macOS build that was blocking releases)

## [0.2.0] - 2026-09-08

### Added
- **Word Document Support** (.docx) - Proteksi data sensitif dalam paragraf, tabel, header, footer
- **PowerPoint Support** (.pptx) - Proteksi data sensitif dalam slides, text frames, tabel, notes
- **Document Preview Dialog** - Preview entities sebelum proteksi untuk DOCX/PPTX
- **Help Menu Complete**:
  - Panduan Cepat (F1) - Quick start guide
  - Dokumentasi - Link ke website dan GitHub
  - Hubungi Kami - Email dan kontak
  - Dukung Pengembangan - Info donasi
- **GitHub Actions** - Auto-build untuk Windows dan macOS saat release
- **Build Scripts** - `build_windows.ps1` dan `build_macos.sh`

### Changed
- Improved PII detection patterns for Indonesian data
- Better error handling untuk file I/O
- GC disabled globally untuk mencegah PySide6 heap corruption

### Fixed
- Crash saat upload file kedua dengan nama sama
- File metadata (selected_columns) tidak tersimpan ke database
- Project settings tidak load saat dibuka kembali

## [0.1.0] - 2026-09-01

### Added
- Initial MVP release
- **Excel Support** (.xlsx) - Column-based protection
- **CSV Support** - Column-based protection
- **TXT Support** - Entity detection dengan regex patterns
- **Project Management** - Create, delete, switch projects
- **PII Detection**:
  - Email addresses
  - Phone numbers (Indonesia format)
  - NIK (Nomor Induk Kependudukan)
  - NPWP
  - Credit card numbers
  - IP addresses
  - Dates
  - Person names (context-based)
- **Tokenization** - Consistent token generation per project
- **Encryption** - AES-256-GCM untuk token mapping
- **Settings** - Output folder, filename suffix
- **Indonesian Localization** - Full Indonesian UI

### Security
- 100% local processing - no data leaves your computer
- AES-256-GCM encryption for token mappings
- OS keychain integration for key storage

---

## Release Process

To create a new release:

```bash
# Update version in:
# - src/sandiraksa/version.py
# - pyproject.toml
# - CHANGELOG.md

# Commit changes
git add .
git commit -m "Release v0.2.0"

# Create and push tag
git tag v0.2.0
git push origin main --tags
```

GitHub Actions will automatically:
1. Build Windows executable
2. Build macOS DMG (Intel + Apple Silicon)
3. Create GitHub Release with all artifacts
