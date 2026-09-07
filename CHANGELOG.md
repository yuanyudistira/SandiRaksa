# Changelog

All notable changes to SandiRaksa will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
