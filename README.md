# SandiRaksa

**Local Privacy Gateway for AI**

> Lindungi Data Sebelum Berbagi ke AI

SandiRaksa adalah aplikasi desktop standalone yang melindungi informasi sensitif dalam dokumen sebelum dibagikan ke sistem AI publik.

## ✨ Fitur Utama

- 🔒 **100% Lokal** — Semua pemrosesan dilakukan di komputer Anda
- 🔄 **Perlindungan Reversibel** — Kembalikan data asli setelah menerima hasil dari AI
- 🇮🇩 **Dukungan Indonesia** — Deteksi NIK, NPWP, No. KK, dan data Indonesia lainnya
- 📄 **Multi-Format** — Dukung CSV, Excel, Word, PowerPoint
- 🛡️ **Aman** — Enkripsi AES-256-GCM untuk pemetaan reversibel

## 📦 Format yang Didukung

| Format | Ekstensi | Status |
|--------|----------|--------|
| CSV | `.csv` | ✅ MVP |
| Excel | `.xlsx` | ✅ MVP |
| Word | `.docx` | ✅ MVP |
| PowerPoint | `.pptx` | ✅ MVP |
| PDF | `.pdf` | 🔮 Future |

## 🚀 Instalasi

### Windows

Download installer dari [Release Page](https://github.com/yuanyudistira/sandiraksa/releases):
- `SandiRaksa-Setup-x64.exe`

### macOS

Download DMG:
- Apple Silicon: `SandiRaksa-macOS-arm64.dmg`
- Intel: `SandiRaksa-macOS-x64.dmg`

### Linux

Download AppImage:
- `SandiRaksa-x86_64.AppImage`

## 🔧 Development

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (recommended) atau pip

### Setup

```bash
# Clone repository
git clone https://github.com/example/sandiraksa.git
cd sandiraksa

# Install dependencies dengan uv
uv sync

# Atau dengan pip
pip install -e ".[dev]"

# Download spaCy model
python -m spacy download en_core_web_sm
```

### Running

```bash
# Run application
python -m sandiraksa

# Atau setelah install
sandiraksa
```

### Testing

```bash
# Run tests
pytest

# Run dengan coverage
pytest --cov=sandiraksa --cov-report=html
```

### Linting

```bash
# Check code style
ruff check src tests

# Format code
ruff format src tests

# Type checking
mypy src
```

## 🏗️ Build Executable

### Windows

```powershell
# Menggunakan build script
.\scripts\build_windows.ps1

# Output: dist\SandiRaksa.exe
```

### macOS

```bash
# Menggunakan build script
chmod +x scripts/build_macos.sh
./scripts/build_macos.sh

# Output: dist/SandiRaksa.app
```

Lihat [BUILD.md](BUILD.md) untuk panduan lengkap termasuk Nuitka dan cx_Freeze.

## 🏗️ Arsitektur

```
SandiRaksa/
├── src/sandiraksa/
│   ├── app/          # Application core
│   ├── ui/           # PySide6 GUI
│   ├── domain/       # Domain models
│   ├── detection/    # PII detection engine
│   ├── documents/    # Document handlers
│   ├── protection/   # Protection pipeline
│   ├── restore/      # Restore pipeline
│   ├── storage/      # Database & vault
│   ├── security/     # Crypto & security
│   ├── profiles/     # Privacy profiles
│   ├── config/       # Configuration
│   └── resources/    # Assets & i18n
├── tests/            # Test suite
├── scripts/          # Build scripts
└── docs/             # Documentation
```

## 🔐 Keamanan

- Tidak ada upload dokumen ke server eksternal
- Tidak ada telemetri atau crash reporting dengan konten dokumen
- Enkripsi AES-256-GCM untuk pemetaan reversibel
- OS keychain untuk penyimpanan kunci
- XML parsing yang aman terhadap XXE attacks

## 📝 Lisensi

Proprietary - Hak Cipta © 2024 SandiRaksa Team

## 🤝 Kontribusi

Lihat [CONTRIBUTING.md](CONTRIBUTING.md) untuk panduan kontribusi.

## 📧 Kontak

- Email: infosecguru.id@gmail.com
- GitHub: https://github.com/yuanyudistira/sandiraksa
- Website: https://sandiraksa.infosecguru.id
