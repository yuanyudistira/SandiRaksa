<p align="center">
  <img src="docs/sandiraksa-hero-banner.png" alt="SandiRaksa" width="720">
</p>

# SandiRaksa

**Local Privacy Gateway for AI**

> Lindungi Data Sebelum Berbagi ke AI

SandiRaksa adalah aplikasi desktop standalone yang melindungi informasi sensitif dalam dokumen sebelum dibagikan ke sistem AI publik.

## ✨ Fitur Utama

- 🔒 **100% Lokal** — Semua pemrosesan dilakukan di komputer Anda
- 🔄 **Perlindungan Reversibel** — Kembalikan data asli setelah menerima hasil dari AI
- 🇮🇩 **Dukungan Indonesia** — Deteksi NIK, NPWP, No. KK, BPJS, dan data Indonesia lainnya
- 📄 **Multi-Format** — Dukung CSV, Excel, Word, PowerPoint, TXT
- 🛡️ **Aman** — Enkripsi AES-256-GCM untuk pemetaan reversibel
- 🎯 **Akurasi Tinggi** — F1 Score ≥95% untuk NIK dan Email, ≥90% untuk NPWP
- 🧠 **Deteksi Nama Kontekstual** — Mengenali nama orang dari label, pola EMR, dan header kolom
- 📅 **Tanggal Lahir Cerdas** — Membedakan tanggal lahir dari tanggal kunjungan/janji temu
- 🧩 **Pola Kustom Global** — Definisikan pola sendiri (mis. format Rekam Medis tiap RS) untuk semua project
- 📊 **Rekomendasi Kolom Otomatis** — Kolom sensitif di Excel/CSV direkomendasikan dari nama header dan isi kolom

## 📦 Format yang Didukung

| Format | Ekstensi | Status |
|--------|----------|--------|
| CSV | `.csv` | ✅ Stable |
| Excel | `.xlsx` | ✅ Stable |
| Word | `.docx` | ✅ Stable |
| PowerPoint | `.pptx` | ✅ Stable |
| TXT | `.txt` | ✅ Stable |
| PDF | `.pdf` | 🔮 Future |

## 🎯 Entitas yang Dideteksi

| Entitas | Deskripsi | Akurasi Target |
|---------|-----------|----------------|
| NIK | Nomor Induk Kependudukan (16 digit) | ≥95% F1 |
| NPWP | Nomor Pokok Wajib Pajak | ≥90% F1 |
| KK | Nomor Kartu Keluarga | ≥90% F1 |
| BPJS | Nomor BPJS Kesehatan | ≥85% F1 |
| EMAIL | Alamat email | ≥95% F1 |
| PHONE | Nomor telepon Indonesia | ≥90% F1 |
| PERSON | Nama orang (NER) | ≥80% F1 |
| LOCATION | Lokasi/alamat (NER) | ≥70% F1 |
| ORGANIZATION | Nama organisasi (NER) | ≥70% F1 |
| CREDIT_CARD | Nomor kartu kredit | ≥95% F1 |
| IP_ADDRESS | Alamat IP | ≥95% F1 |

## 🚀 Instalasi

### Windows

Download installer dari [Release Page](https://github.com/yuanyudistira/sandiraksa/releases):
- `SandiRaksa-1.0.0-windows-x64.exe`

> ⚠️ **Windows SmartScreen:** Saat pertama kali run, Windows mungkin menampilkan warning "Windows protected your PC" karena aplikasi belum ditandatangani. Klik **"More info"** → **"Run anyway"** untuk melanjutkan.

### macOS

Download DMG dari [Release Page](https://github.com/yuanyudistira/sandiraksa/releases):
- `SandiRaksa-1.0.0-macos-x64.dmg`

> ⚠️ **macOS Gatekeeper:** macOS mungkin memblokir aplikasi karena belum ditandatangani. Buka **System Preferences → Security & Privacy**, lalu klik **"Open Anyway"**.

## 🧪 File Contoh untuk Testing

Folder [`example_file/`](example_file/) berisi file mockup untuk mencoba SandiRaksa:

| File | Format | Deskripsi |
|------|--------|-----------|
| `Data export CSV.csv` | CSV | Data tabular dengan kolom PII |
| `Data_Pasien_dan_EMR_3000.xlsx` | Excel | Mockup data pasien 3000 baris |
| `Mockup_Data_Sensitif_Pasien.docx` | Word | Dokumen dengan data sensitif |
| `Mockup_Data_Sensitif_Pasien 1.pptx` | PowerPoint | Presentasi dengan PII |
| `Mockup_Data_Sensitif_Pasien.txt` | Text | File teks dengan data PII |

> ⚠️ Semua data dalam file contoh adalah **100% fiktif** untuk keperluan demo.

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
│   ├── app/          # Application core (commands, events, i18n)
│   ├── ui/           # PySide6 GUI
│   ├── domain/       # Domain models (finding, token, policy)
│   ├── detection/    # PII detection engine
│   │   ├── recognizers/  # Indonesian ID recognizers (NIK, NPWP, KK, etc.)
│   │   ├── ner/          # Named Entity Recognition (ONNX-based)
│   │   └── confidence/   # Confidence scoring & filtering
│   ├── documents/    # Document handlers (CSV, XLSX, DOCX, PPTX)
│   ├── protection/   # Protection pipeline & tokenization
│   ├── restore/      # Restore pipeline
│   ├── storage/      # Database & vault
│   ├── security/     # Crypto & security
│   ├── profiles/     # Privacy profiles
│   ├── config/       # Configuration
│   └── resources/    # Assets & i18n
├── tests/
│   ├── unit/         # Unit tests
│   ├── integration/  # Integration tests
│   ├── accuracy/     # Benchmark corpus & metrics
│   ├── performance/  # Performance benchmarks
│   ├── compatibility/# Backward compatibility tests
│   └── security/     # Security tests
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

MIT License - Lihat [LICENSE](LICENSE) untuk detail.

Copyright (c) 2024 Yuan Yudistira

## 🤝 Kontribusi

Lihat [CONTRIBUTING.md](CONTRIBUTING.md) untuk panduan kontribusi.

## 📧 Kontak

- Email: infosecguru.id@gmail.com
- GitHub: https://github.com/yuanyudistira/sandiraksa
- Website: https://sandiraksa.infosecguru.id
