# SandiRaksa Backlog

## 🎯 Improvement Plan: Akurasi Deteksi PII

### Status Saat Ini (MVP v0.2.0)

Deteksi PII pada file TXT, Word (DOCX), dan PowerPoint (PPTX) menggunakan **regex patterns** sederhana. Akurasi masih terbatas karena:

- Tidak ada context awareness
- False positives pada angka yang mirip NIK/NPWP
- Tidak mendeteksi nama Indonesia dengan baik
- Tidak ada NLP/NER (Named Entity Recognition)

---

## 📋 Backlog Items

### 1. Integrasi Presidio Analyzer untuk TXT/DOCX/PPTX

**Priority:** High  
**Effort:** Medium  
**Status:** Planned

**Deskripsi:**
Saat ini hanya file CSV dan Excel yang menggunakan Presidio Analyzer. File TXT, DOCX, dan PPTX masih menggunakan regex manual.

**Tasks:**
- [ ] Refactor `txt_protector.py` untuk menggunakan `PresidioEngine`
- [ ] Refactor `docx_protector.py` untuk menggunakan `PresidioEngine`
- [ ] Refactor `pptx_protector.py` untuk menggunakan `PresidioEngine`
- [ ] Unified detection interface untuk semua file types

**Expected Outcome:**
- Konsistensi deteksi di semua format file
- Leverage Presidio's built-in recognizers
- Support untuk custom recognizers Indonesia

---

### 2. Improved Indonesian NER dengan spaCy

**Priority:** High  
**Effort:** High  
**Status:** Research

**Deskripsi:**
Deteksi nama orang Indonesia masih lemah. spaCy model `en_core_web_sm` tidak optimal untuk bahasa Indonesia.

**Tasks:**
- [ ] Evaluasi model spaCy untuk Indonesian (jika ada)
- [ ] Evaluasi alternatif: IndoBERT, Indonesian NER models
- [ ] Train custom NER model untuk nama Indonesia
- [ ] Integrasi dengan Presidio sebagai custom recognizer

**Options:**
1. **IndoNLP/IndoBERT** - Pre-trained Indonesian NLP models
2. **Stanza Indonesian** - Stanford NLP dengan support Indonesian
3. **Custom Dictionary** - Daftar nama Indonesia umum + pattern matching

**Expected Outcome:**
- Akurasi deteksi nama Indonesia >90%
- Mengurangi false negatives pada nama lokal

---

### 3. Context-Aware Detection

**Priority:** Medium  
**Effort:** High  
**Status:** Planned

**Deskripsi:**
Deteksi saat ini tidak mempertimbangkan konteks. Angka "3201234567890001" bisa NIK atau bisa nomor lain.

**Tasks:**
- [ ] Implementasi context analysis (kata sebelum/sesudah)
- [ ] Keyword proximity detection (e.g., "NIK:", "Nama:", "No. Telp:")
- [ ] Column header analysis untuk Excel/CSV
- [ ] Paragraph/slide title analysis untuk DOCX/PPTX

**Context Signals:**
- Label/header: "NIK", "Nama Lengkap", "Alamat", "No. HP"
- Proximity to keywords: "Pasien", "Karyawan", "Pelanggan"
- Document type hints: medical records, HR documents

**Expected Outcome:**
- Reduced false positives
- Higher confidence scores

---

### 4. Indonesian-Specific Recognizers Enhancement

**Priority:** High  
**Effort:** Medium  
**Status:** In Progress

**Deskripsi:**
Recognizers Indonesia (`id_nik.py`, `id_npwp.py`, `id_kk.py`, `id_phone.py`) perlu diperkuat.

**Tasks:**
- [ ] NIK: Validasi kode wilayah (provinsi, kota/kabupaten)
- [ ] NIK: Validasi tanggal lahir embedded
- [ ] NPWP: Validasi format baru (2024) vs format lama
- [ ] KK: Validasi kode wilayah
- [ ] Phone: Support lebih banyak format (+62, 08xx, 628xx)
- [ ] Add: BPJS Number recognizer
- [ ] Add: SIM (Driving License) recognizer
- [ ] Add: Passport Indonesia recognizer

**Expected Outcome:**
- Validasi checksum/format yang lebih ketat
- Mengurangi false positives

---

### 5. Confidence Scoring & Threshold

**Priority:** Medium  
**Effort:** Medium  
**Status:** Planned

**Deskripsi:**
Memberikan confidence score untuk setiap deteksi dan allow user to set threshold.

**Tasks:**
- [ ] Implement confidence scoring (0.0 - 1.0)
- [ ] UI untuk set minimum confidence threshold
- [ ] Show confidence in preview dialog
- [ ] Different colors for high/medium/low confidence

**Scoring Factors:**
- Pattern match strength
- Context signals present
- Checksum validation pass
- Format exactness

**Expected Outcome:**
- User bisa filter deteksi berdasarkan confidence
- Reduce noise dari low-confidence matches

---

### 6. Custom Terms / Deny List

**Priority:** Medium  
**Effort:** Low  
**Status:** Planned

**Deskripsi:**
Allow user to define custom terms yang harus selalu diproteksi atau di-ignore.

**Tasks:**
- [ ] UI untuk manage custom terms per project
- [ ] "Always protect" list (e.g., specific names, codes)
- [ ] "Never protect" list (e.g., company name, product names)
- [ ] Import/export custom terms

**Expected Outcome:**
- Flexibility untuk use case spesifik
- Reduce repeated manual corrections

---

### 7. Learning from User Corrections

**Priority:** Low  
**Effort:** High  
**Status:** Future

**Deskripsi:**
Belajar dari koreksi user untuk improve future detections.

**Tasks:**
- [ ] Track user corrections (selected/deselected entities)
- [ ] Store correction patterns locally
- [ ] Apply learned patterns to new detections
- [ ] Optional: export anonymized patterns untuk improvement

**Expected Outcome:**
- Deteksi semakin akurat seiring penggunaan
- Personalized per user/organization

---

### 8. Multi-Language Support

**Priority:** Low  
**Effort:** High  
**Status:** Future

**Deskripsi:**
Support deteksi PII dalam bahasa lain selain Indonesia dan English.

**Tasks:**
- [ ] Language detection
- [ ] Configurable language per project
- [ ] Malaysia: MyKad, phone formats
- [ ] Singapore: NRIC, phone formats
- [ ] General: Multi-language NER

---

## 📊 Priority Matrix

| Item | Priority | Effort | Impact |
|------|----------|--------|--------|
| Presidio Integration | High | Medium | High |
| Indonesian NER | High | High | High |
| ID Recognizers Enhancement | High | Medium | High |
| Context-Aware Detection | Medium | High | High |
| Confidence Scoring | Medium | Medium | Medium |
| Custom Terms | Medium | Low | Medium |
| User Learning | Low | High | Medium |
| Multi-Language | Low | High | Low |

---

## 🗓️ Roadmap

### v0.3.0 (Next)
- [ ] Presidio Integration untuk semua file types
- [ ] Enhanced Indonesian recognizers (NIK, NPWP validation)
- [ ] Confidence scoring basic

### v0.4.0
- [ ] Context-aware detection
- [ ] Custom terms management
- [ ] Improved NER untuk nama Indonesia

### v0.5.0
- [ ] User correction learning (local)
- [ ] Advanced confidence scoring
- [ ] Performance optimization

### v1.0.0
- [ ] Production-ready accuracy
- [ ] Full Indonesian PII coverage
- [ ] Multi-language foundation

---

## 📝 Notes

- Semua improvement harus backward compatible dengan existing projects
- Accuracy vs Performance trade-off harus dipertimbangkan
- User privacy: tidak ada data yang dikirim ke server eksternal
- Testing dengan real-world Indonesian documents diperlukan

---

*Last updated: 2024*
