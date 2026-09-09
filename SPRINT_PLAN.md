# SandiRaksa Sprint Implementation Plan

**Based on:** Technical Design PII Improvement & BACKLOG.md Analysis  
**Created:** September 2026  
**Target:** v0.3.0 → v1.0.0

---

## 📊 Gap Analysis: BACKLOG vs Technical Design

| BACKLOG Item | Technical Design Enhancement |
|--------------|------------------------------|
| Presidio Integration | ✅ Tetap P0, tapi harus via unified interface |
| Indonesian NER | ✅ Ditambah: ONNX, lazy loading, batching strategy |
| Context-Aware Detection | ✅ Diperjelas: Lexical, Structural, Spatial, Document-level |
| ID Recognizers Enhancement | ✅ Lebih detail: structural + semantic validation |
| Confidence Scoring | ✅ Diperjelas: High/Medium/Low bands, bukan raw score |
| Custom Terms | ⬆️ **Naik dari Medium ke P0** |
| **NEW: DOCX/PPTX Split-Run** | 🆕 **Critical Issue tidak ada di BACKLOG** |
| **NEW: LogicalSegment/CharMap** | 🆕 **Core architecture baru** |
| **NEW: Document Adapters** | 🆕 **Separation of concerns** |
| **NEW: 4-Layer Testing** | 🆕 **Extraction, Detection, Protection, Leakage** |

---

## 🏃 Sprint Overview

```
Sprint 1 (2 weeks): Foundation - LogicalSegment & Document Adapters
Sprint 2 (2 weeks): DOCX/PPTX Reconstruction  
Sprint 3 (2 weeks): Unified Detection Engine & Presidio Integration
Sprint 4 (2 weeks): Indonesian Recognizers Enhancement
Sprint 5 (2 weeks): Context Engine & Custom Terms
Sprint 6 (2 weeks): Local Indonesian NER
Sprint 7 (2 weeks): Confidence, Explainability & Polish
Sprint 8 (2 weeks): Accuracy Hardening & v1.0 Release Prep
```

---

## 🔵 Sprint 1: Foundation - Core Data Models

**Duration:** 2 weeks  
**Goal:** Establish core architecture for logical text handling

### Tasks

#### 1.1 LogicalSegment Model
**File:** `src/sandiraksa/documents/logical_segment.py`

```python
# Implement LogicalSegment dengan:
- id, text, file_id, file_type
- location: DocumentLocation
- previous_text, next_text, heading (context)
- table_headers, row_headers
- slide_title, nearby_labels
- document_hints
- char_map: list[CharMapEntry]
```

**Effort:** 3 days  
**Dependencies:** None

#### 1.2 CharMapEntry Model
**File:** `src/sandiraksa/documents/char_map.py`

```python
# Implement CharMapEntry untuk offset mapping:
- logical_start, logical_end
- source_component_id
- source_start, source_end
```

**Effort:** 2 days  
**Dependencies:** None

#### 1.3 DocumentLocation Model
**File:** `src/sandiraksa/documents/location.py`

```python
# Implement DocumentLocation:
- component (body, header, footer, etc.)
- page, slide, sheet, cell
- paragraph_index, table_index, shape_id
```

**Effort:** 2 days  
**Dependencies:** None

#### 1.4 Base Document Adapter Protocol
**File:** `src/sandiraksa/documents/base.py`

```python
class DocumentAdapter(Protocol):
    def extract(self, file_path) -> list[LogicalSegment]: ...
    def apply_replacements(self, file_path, replacements) -> None: ...
    def validate(self, file_path) -> bool: ...
```

**Effort:** 3 days  
**Dependencies:** 1.1, 1.2, 1.3

### Sprint 1 Deliverables
- [ ] `logical_segment.py` dengan full model
- [ ] `char_map.py` dengan CharMapEntry
- [ ] `location.py` dengan DocumentLocation
- [ ] `base.py` dengan DocumentAdapter Protocol
- [ ] Unit tests untuk semua models
- [ ] Documentation

### Definition of Done
- Semua models terimplementasi dengan Pydantic/dataclass
- Unit tests coverage >90%
- Type hints lengkap

---

## 🔵 Sprint 2: DOCX/PPTX Logical Reconstruction

**Duration:** 2 weeks  
**Goal:** Solve the split-run problem

### Tasks

#### 2.1 TxtDocumentAdapter
**File:** `src/sandiraksa/documents/txt_adapter.py`

```python
# Migrate existing txt_handler.py ke adapter pattern
# Implement paragraph segmentation
# Key/value detection (Nama: xxx, NIK: xxx)
```

**Effort:** 3 days  
**Dependencies:** Sprint 1

#### 2.2 DocxDocumentAdapter - Extraction
**File:** `src/sandiraksa/documents/docx_adapter.py`

```python
# Critical: Reconstruct logical text across runs
# Algorithm:
# 1. Enumerate text-bearing runs/nodes
# 2. Concatenate visible text
# 3. Build char_map
# 4. Add paragraph/document context
```

**Effort:** 5 days  
**Dependencies:** Sprint 1

#### 2.3 DocxDocumentAdapter - Context
```python
# Attach context:
# - nearest heading
# - previous/next paragraph  
# - table headers
# - section title
# - paragraph style
```

**Effort:** 3 days  
**Dependencies:** 2.2

#### 2.4 PptxDocumentAdapter - Extraction
**File:** `src/sandiraksa/documents/pptx_adapter.py`

```python
# Reconstruct logical text for:
# - text frame, paragraph, table cell
# - title placeholder, notes
# Using same char_map concept as DOCX
```

**Effort:** 4 days  
**Dependencies:** Sprint 1

#### 2.5 PPTX Spatial Context Resolver
**File:** `src/sandiraksa/documents/spatial_resolver.py`

```python
class SpatialContextResolver:
    def get_nearby_labels(
        self,
        current_shape: ShapeInfo,
        slide_shapes: list[ShapeInfo],
    ) -> list[str]:
        # Calculate horizontal/vertical distance
        # Same baseline detection
        # Label-like text identification
```

**Effort:** 4 days  
**Dependencies:** 2.4

### Sprint 2 Deliverables
- [ ] `txt_adapter.py` - migrated
- [ ] `docx_adapter.py` - with run reconstruction
- [ ] `pptx_adapter.py` - with run reconstruction
- [ ] `spatial_resolver.py` - for PPTX
- [ ] DOCX split-run test fixtures (10+ cases)
- [ ] PPTX split-run test fixtures (10+ cases)

### Test Fixtures Required

**DOCX:**
```
- name_split_across_runs.docx
- bold_italic_boundary.docx
- hyperlink_boundary.docx
- table_cells.docx
- headers_footers.docx
- text_boxes.docx
```

**PPTX:**
```
- split_runs.pptx
- title_body.pptx
- label_value_shapes.pptx
- tables.pptx
- grouped_shapes.pptx
- notes.pptx
```

### Definition of Done
- DOCX: "Satria Putra" split across 3 runs → detected as single PERSON
- PPTX: Label "NIK" adjacent to value → context attached
- All test fixtures pass

---

## 🔵 Sprint 3: Unified Detection Engine

**Duration:** 2 weeks  
**Goal:** Single detection interface for all formats

### Tasks

#### 3.1 Detection Engine Protocol
**File:** `src/sandiraksa/detection/engine.py`

```python
class DetectionEngine(Protocol):
    def analyze(
        self,
        segment: LogicalSegment,
        policy: DetectionPolicy,
    ) -> list[Finding]: ...
```

**Effort:** 2 days  
**Dependencies:** Sprint 1, Sprint 2

#### 3.2 Finding & Evidence Models
**File:** `src/sandiraksa/detection/finding.py`

```python
class ConfidenceEvidence(BaseModel):
    source: str
    weight: float
    reason_code: str

class Finding(BaseModel):
    id: str
    entity_type: str
    start: int
    end: int
    raw_score: float
    confidence_band: str  # High/Medium/Low
    detector: str
    evidence: list[ConfidenceEvidence]
    location: DocumentLocation
```

**Effort:** 2 days  
**Dependencies:** Sprint 1

#### 3.3 Unified Detection Pipeline
**File:** `src/sandiraksa/detection/pipeline.py`

```python
class UnifiedDetectionEngine:
    def analyze(self, segment, policy):
        candidates = []
        candidates += self.custom_terms.analyze(segment)
        candidates += self.structured.analyze(segment)
        candidates += self.presidio.analyze(segment)
        candidates += self.local_ner.analyze(segment)
        
        candidates = self.context.score(segment, candidates)
        candidates = self.overlap.resolve(candidates)
        return self.confidence.classify(candidates)
```

**Effort:** 5 days  
**Dependencies:** 3.1, 3.2

#### 3.4 Presidio Integration untuk TXT/DOCX/PPTX
**File:** Update `src/sandiraksa/detection/presidio_engine.py`

```python
# Route TXT, DOCX, PPTX through Presidio
# Accept LogicalSegment as input
# Return standardized Finding objects
```

**Effort:** 4 days  
**Dependencies:** 3.3

#### 3.5 Overlap Resolver
**File:** `src/sandiraksa/detection/overlap.py`

```python
# Precedence:
# 1. user Always Protect exact rule
# 2. validated structured identifier
# 3. strong composite PII
# 4. NER
# 5. generic regex
```

**Effort:** 3 days  
**Dependencies:** 3.3

#### 3.6 CSV/XLSX Migration
**Files:** Update `csv_adapter.py`, `xlsx_adapter.py`

```python
# Route existing CSV/XLSX through unified interface
# Maintain backward compatibility
```

**Effort:** 3 days  
**Dependencies:** 3.3, 3.4

### Sprint 3 Deliverables
- [ ] `engine.py` - Detection Protocol
- [ ] `finding.py` - Finding & Evidence models
- [ ] `pipeline.py` - UnifiedDetectionEngine
- [ ] `overlap.py` - Overlap resolver
- [ ] Updated `presidio_engine.py`
- [ ] Detection tests (format-agnostic)

### Definition of Done
- All 5 formats (TXT, DOCX, PPTX, CSV, XLSX) use UnifiedDetectionEngine
- Detection tests work with LogicalSegment directly (no files needed)
- Overlap resolution working

---

## 🔵 Sprint 4: Indonesian Recognizers Enhancement

**Duration:** 2 weeks  
**Goal:** Robust Indonesian PII detection

### Tasks

#### 4.1 Enhanced NIK Recognizer
**File:** `src/sandiraksa/detection/recognizers/id_nik.py`

```python
# Pipeline:
# 16 digits
#   -> regional code structure validation
#   -> DOB structure validation  
#   -> female-day adjustment handling
#   -> sequence structure
#   -> context evidence

# Validation:
# - Valid province codes (11-94)
# - Valid city/district codes
# - Plausible DOB (not future, not >120 years old)
```

**Effort:** 4 days  
**Dependencies:** Sprint 3

#### 4.2 Enhanced NPWP Recognizer
**File:** `src/sandiraksa/detection/recognizers/id_npwp.py`

```python
# Support:
# - Legacy 15-digit NPWP
# - Current 16-digit NPWP
# - NIK-as-NPWP context
# - Formatted variants (XX.XXX.XXX.X-XXX.XXX)
# - Unformatted variants

# Context:
# - "NPWP", "Nomor Pokok Wajib Pajak", "Tax ID"
```

**Effort:** 3 days  
**Dependencies:** Sprint 3

#### 4.3 Enhanced KK Recognizer
**File:** `src/sandiraksa/detection/recognizers/id_kk.py`

```python
# Validasi kode wilayah sama seperti NIK
# 16 digits
# Context: "KK", "Kartu Keluarga", "No. KK"
```

**Effort:** 2 days  
**Dependencies:** Sprint 3

#### 4.4 Indonesian Phone with phonenumbers
**File:** `src/sandiraksa/detection/recognizers/id_phone.py`

```python
import phonenumbers

# Pipeline:
# candidate extraction
#   -> phonenumbers.parse(candidate, "ID")
#   -> is_possible_number
#   -> is_valid_number
#   -> context score

# Support: +62, 62, 08xx, 628xx, spaces, dashes
```

**Effort:** 3 days  
**Dependencies:** Sprint 3

#### 4.5 New: BPJS Recognizer
**File:** `src/sandiraksa/detection/recognizers/id_bpjs.py`

```python
# 13-digit BPJS number
# Context: "BPJS", "No. BPJS Kesehatan"
```

**Effort:** 2 days  
**Dependencies:** Sprint 3

#### 4.6 New: SIM Recognizer
**File:** `src/sandiraksa/detection/recognizers/id_sim.py`

```python
# SIM (Driving License) number pattern
# 12-14 digits
# Context: "SIM", "Surat Izin Mengemudi"
```

**Effort:** 2 days  
**Dependencies:** Sprint 3

#### 4.7 New: Passport Recognizer
**File:** `src/sandiraksa/detection/recognizers/id_passport.py`

```python
# Indonesian passport: A1234567
# 1 letter + 7 digits
# Context: "Passport", "Paspor"
```

**Effort:** 2 days  
**Dependencies:** Sprint 3

### Sprint 4 Deliverables
- [ ] Enhanced `id_nik.py` with regional/DOB validation
- [ ] Enhanced `id_npwp.py` with format variants
- [ ] Enhanced `id_kk.py` with validation
- [ ] Enhanced `id_phone.py` with phonenumbers
- [ ] New `id_bpjs.py`
- [ ] New `id_sim.py`
- [ ] New `id_passport.py`
- [ ] Test cases untuk setiap recognizer

### Definition of Done
- NIK: Regional code validation working
- NPWP: Legacy & new format supported
- Phone: phonenumbers library integrated
- False positive rate reduced >50% dari baseline

---

## 🔵 Sprint 5: Context Engine & Custom Terms

**Duration:** 2 weeks  
**Goal:** Context-aware detection & user customization

### Tasks

#### 5.1 Lexical Context
**File:** `src/sandiraksa/detection/context/lexical.py`

```python
# Indonesian keywords:
POSITIVE_KEYWORDS = [
    "Nama", "Nama Lengkap", "NIK", "KTP", "NPWP",
    "Alamat", "No. HP", "Telepon", "Pasien", 
    "Karyawan", "Pelanggan", "Nasabah", "Company", "perusahaan", "vendor", "supplier"
]

NEGATIVE_KEYWORDS = [
    "Invoice Number", "Order ID", "SKU", 
    "Serial Number", "Reference"
]
```

**Effort:** 3 days  
**Dependencies:** Sprint 3

#### 5.2 Structural Context
**File:** `src/sandiraksa/detection/context/structural.py`

```python
# Extract context from:
# - Excel column headers
# - Word headings
# - Table headers
# - TXT key/value labels
# - PowerPoint titles
```

**Effort:** 3 days  
**Dependencies:** Sprint 2

#### 5.3 Spatial Context
**File:** `src/sandiraksa/detection/context/spatial.py`

```python
# PowerPoint spatial analysis (dari Sprint 2)
# Integration dengan context scoring
```

**Effort:** 2 days  
**Dependencies:** Sprint 2 (2.5)

#### 5.4 Document-Level Context
**File:** `src/sandiraksa/detection/context/document.py`

```python
# Document type hints:
# - HR documents
# - Medical records
# - Banking documents
# - Customer lists
# - Legal documents

# Detect from: sheet names, headings, titles
```

**Effort:** 3 days  
**Dependencies:** Sprint 2

#### 5.5 Context Scorer
**File:** `src/sandiraksa/detection/context/scorer.py`

```python
class ContextScorer:
    def score(
        self, 
        segment: LogicalSegment, 
        candidates: list[Finding]
    ) -> list[Finding]:
        # Apply positive/negative evidence
        # Weight calibration
        # Return scored findings
```

**Effort:** 4 days  
**Dependencies:** 5.1, 5.2, 5.3, 5.4

#### 5.6 Custom Terms Manager
**File:** `src/sandiraksa/detection/recognizers/custom_terms.py`

```python
class CustomTermsManager:
    def __init__(self, project_id: str):
        self.always_protect: set[str] = set()
        self.never_protect: set[str] = set()
    
    def add_always_protect(self, term: str): ...
    def add_never_protect(self, term: str): ...
    def analyze(self, segment: LogicalSegment) -> list[Finding]: ...
    def should_exclude(self, finding: Finding) -> bool: ...
    
    def save(self): ...  # Encrypted local storage
    def load(self): ...
```

**Effort:** 4 days  
**Dependencies:** Sprint 3

#### 5.7 Custom Terms UI Integration
**Files:** UI components

```python
# Per project:
# - Always Protect list management
# - Never Protect list management
# - Import/export functionality
```

**Effort:** 4 days  
**Dependencies:** 5.6

### Sprint 5 Deliverables
- [ ] `context/lexical.py`
- [ ] `context/structural.py`
- [ ] `context/spatial.py`
- [ ] `context/document.py`
- [ ] `context/scorer.py`
- [ ] `custom_terms.py` enhanced
- [ ] Custom Terms UI
- [ ] Context scoring tests

### Definition of Done
- Context scoring integrated dalam pipeline
- Custom Terms working per project
- "NIK: 327105..." gets higher confidence than standalone "327105..."

---

## 🔵 Sprint 6: Local Indonesian NER

**Duration:** 2 weeks  
**Goal:** Indonesian PERSON/ORG/LOC detection

### Tasks

#### 6.1 NER Provider Protocol
**File:** `src/sandiraksa/detection/ner/base.py`

```python
class LocalNERProvider(Protocol):
    def predict(
        self,
        texts: list[str],
    ) -> list[list[NERPrediction]]: ...

class NERPrediction(BaseModel):
    start: int
    end: int
    entity_type: str  # PERSON, ORG, LOC
    score: float
```

**Effort:** 2 days  
**Dependencies:** Sprint 3

#### 6.2 Model Benchmarking
```python
# Benchmark candidates against SandiRaksa corpus:
# - IndoBERT
# - IndoRoBERTa  
# - Multilingual models

# Metrics:
# - PERSON precision/recall/F1
# - Cold start time
# - Warm inference time
# - CPU usage, peak RAM
# - Model size
```

**Effort:** 5 days  
**Dependencies:** 6.1

#### 6.3 ONNX Export & Optimization
**File:** `src/sandiraksa/detection/ner/onnx_provider.py`

```python
# Export selected model to ONNX
# Quantization for smaller size
# CPU-optimized inference

# Resources structure:
# resources/nlp/id_ner/
# ├── model.onnx
# ├── tokenizer.json
# ├── tokenizer_config.json
# ├── labels.json
# └── model_metadata.json
```

**Effort:** 4 days  
**Dependencies:** 6.2

#### 6.4 Lazy Loading Implementation
**File:** `src/sandiraksa/detection/ner/loader.py`

```python
class NERModelLoader:
    _model = None
    
    @classmethod
    def get_model(cls):
        if cls._model is None:
            cls._model = cls._load_model()
        return cls._model
    
    # Only load when:
    # - scan starts
    # - active policy requires NER
```

**Effort:** 2 days  
**Dependencies:** 6.3

#### 6.5 Batch Inference
**File:** `src/sandiraksa/detection/ner/batch.py`

```python
class NERBatchProcessor:
    def process_segments(
        self,
        segments: list[LogicalSegment],
        batch_size: int = 32,
    ) -> dict[str, list[NERPrediction]]:
        # Batch by token count
        # Memory-aware batching
        # Return mapped to segment IDs
```

**Effort:** 3 days  
**Dependencies:** 6.3, 6.4

#### 6.6 Presidio NER Integration
**File:** Update `presidio_engine.py`

```python
# Integrate LocalNERProvider dengan Presidio
# sebagai custom recognizer
```

**Effort:** 3 days  
**Dependencies:** 6.5

### Sprint 6 Deliverables
- [ ] `ner/base.py` - Protocol
- [ ] `ner/onnx_provider.py` - ONNX runtime
- [ ] `ner/loader.py` - Lazy loading
- [ ] `ner/batch.py` - Batch processing
- [ ] Model benchmark report
- [ ] Selected model packaged
- [ ] NER integration tests

### Definition of Done
- Indonesian PERSON detection F1 >0.8
- Model loads only when needed
- Inference <500ms for typical document
- No GPU required

---

## 🔵 Sprint 7: Confidence & Explainability

**Duration:** 2 weeks  
**Goal:** User-friendly confidence display & explanation

### Tasks

#### 7.1 Confidence Classifier
**File:** `src/sandiraksa/detection/confidence.py`

```python
class ConfidenceClassifier:
    def classify(
        self, 
        findings: list[Finding]
    ) -> list[Finding]:
        for finding in findings:
            score = finding.raw_score
            
            if score >= 0.8:
                finding.confidence_band = "High"
            elif score >= 0.5:
                finding.confidence_band = "Medium"
            else:
                finding.confidence_band = "Low"
        
        return findings
```

**Effort:** 2 days  
**Dependencies:** Sprint 3

#### 7.2 Scan Modes
**File:** `src/sandiraksa/detection/modes.py`

```python
class ScanMode(Enum):
    STRICT = "strict"      # Optimize recall
    BALANCED = "balanced"  # Reduce noise

# Strict: HR, medical, financial, legal
# Balanced: General documents
```

**Effort:** 2 days  
**Dependencies:** 7.1

#### 7.3 Evidence Display
**File:** UI components

```python
# Show per finding:
# - Entity type
# - Confidence band (High/Medium/Low)
# - Why detected
# - Positive evidence list
# - Negative evidence list  
# - Detector source
```

**Effort:** 4 days  
**Dependencies:** 7.1

#### 7.4 Confidence Filtering UI
**File:** UI components

```python
# User can filter by:
# - Confidence band
# - Entity type
# - Show/hide low confidence
```

**Effort:** 3 days  
**Dependencies:** 7.3

#### 7.5 Protection Writer Updates
**Files:** All protectors

```python
# Apply protection dari Finding
# Use CharMap untuk map back to source
# Preserve formatting
# Output validation
```

**Effort:** 4 days  
**Dependencies:** Sprint 2, Sprint 3

#### 7.6 Leakage Re-Scan
**File:** `src/sandiraksa/protection/rescan.py`

```python
class LeakageScanner:
    def scan(self, protected_file: Path) -> list[Finding]:
        # Re-open protected output
        # Re-extract
        # Re-detect
        # Report any remaining PII
```

**Effort:** 3 days  
**Dependencies:** 7.5

### Sprint 7 Deliverables
- [ ] `confidence.py` - Classifier
- [ ] `modes.py` - Scan modes
- [ ] Evidence display UI
- [ ] Confidence filtering UI
- [ ] Updated protectors
- [ ] `rescan.py` - Leakage scanner
- [ ] End-to-end tests

### Definition of Done
- High/Medium/Low confidence shown in UI
- Evidence visible for each finding
- Leakage re-scan passing
- No protected PII leaking in output

---

## 🔵 Sprint 8: Accuracy Hardening & Release

**Duration:** 2 weeks  
**Goal:** Production-ready v1.0

### Tasks

#### 8.1 Benchmark Corpus Creation
**File:** `tests/accuracy/corpus/`

```python
# Synthetic benchmark covering:
# - HR, Payroll, Hospital, Banking
# - Legal, Customer List, CV
# - Invoice, M&A, Corporate PPT, TXT

# Indonesian name coverage:
# - Javanese, Sundanese, Batak, Minang
# - Balinese, Papuan, Chinese-Indonesian
# - Arabic-influenced names
# - Titles (Dr., Ir., etc.)

# Negative examples:
# - PT Budi Makmur
# - CV Putra Jaya
# - Jalan Sudirman
```

**Effort:** 5 days  
**Dependencies:** All previous sprints

#### 8.2 Accuracy Metrics Implementation
**File:** `tests/accuracy/metrics.py`

```python
# Measure per entity, per format:
# - Precision
# - Recall
# - F1
# - False positives
# - False negatives

# Example output:
# | Entity | Format | Precision | Recall | F1 |
# | PERSON | DOCX   | 0.85      | 0.90   | 0.87 |
# | NIK    | PPTX   | 0.95      | 0.98   | 0.96 |
```

**Effort:** 3 days  
**Dependencies:** 8.1

#### 8.3 Release Gates
**File:** `tests/accuracy/gates.py`

```python
# Critical PII release gates:
# - NIK: F1 >= 0.95
# - NPWP: F1 >= 0.90
# - EMAIL: F1 >= 0.95
# - PHONE: F1 >= 0.90
# - PERSON: F1 >= 0.80
```

**Effort:** 2 days  
**Dependencies:** 8.2

#### 8.4 Performance Regression Tests
**File:** `tests/performance/`

```python
# Benchmark on:
# - Windows x64 CPU
# - macOS Apple Silicon CPU
# - Linux x64 CPU

# Metrics:
# - Cold model load time
# - Warm inference time
# - texts/sec, tokens/sec
# - Peak RAM
```

**Effort:** 3 days  
**Dependencies:** Sprint 6

#### 8.5 Backward Compatibility Tests
**File:** `tests/compatibility/`

```python
# Verify:
# - Existing projects readable
# - Existing mapping vault unchanged
# - Operation history preserved
# - Old protected files not reprocessed
```

**Effort:** 2 days  
**Dependencies:** All sprints

#### 8.6 Documentation & Release
```
# Update:
# - README.md
# - CHANGELOG.md
# - User documentation
# - API documentation

# Release:
# - Version bump to v1.0.0
# - Release notes
# - Installer testing
```

**Effort:** 4 days  
**Dependencies:** All tasks

### Sprint 8 Deliverables
- [ ] Benchmark corpus (100+ test cases)
- [ ] Accuracy metrics automation
- [ ] Release gates passing
- [ ] Performance benchmarks
- [ ] Backward compatibility verified
- [ ] Documentation complete
- [ ] v1.0.0 release

### Definition of Done
- All release gates passing
- No regression from v0.2.0
- Existing projects work
- Documentation complete

---

## 📅 Timeline Summary

```
Sprint 1: Foundation          | Week 1-2   | v0.3.0-alpha
Sprint 2: DOCX/PPTX           | Week 3-4   | v0.3.0-alpha
Sprint 3: Unified Detection   | Week 5-6   | v0.3.0-beta
Sprint 4: ID Recognizers      | Week 7-8   | v0.3.1
Sprint 5: Context & Custom    | Week 9-10  | v0.4.0
Sprint 6: Indonesian NER      | Week 11-12 | v0.4.0
Sprint 7: Confidence & Polish | Week 13-14 | v0.5.0
Sprint 8: Accuracy & Release  | Week 15-16 | v1.0.0
```

**Total Duration:** ~4 months

---

## 🎯 Release Milestones

### v0.3.0 (Sprint 1-3)
- [x] LogicalSegment implemented
- [x] CharMap implemented
- [x] Document Adapters (TXT, DOCX, PPTX, CSV, XLSX)
- [x] DOCX/PPTX split-run reconstruction
- [x] Unified DetectionEngine
- [x] Presidio for all formats
- [x] Extraction & detection tests independent

### v0.3.1 (Sprint 4)
- [ ] Enhanced NIK recognizer
- [ ] Enhanced NPWP recognizer
- [ ] phonenumbers integration
- [ ] New: BPJS, SIM, Passport recognizers

### v0.4.0 (Sprint 5-6)
- [ ] Context engine (lexical, structural, spatial)
- [ ] Custom Terms per project
- [ ] Local Indonesian NER
- [ ] ONNX optimized model

### v0.5.0 (Sprint 7)
- [ ] High/Medium/Low confidence
- [ ] Strict/Balanced scan modes
- [ ] Evidence explainability
- [ ] Leakage re-scan

### v1.0.0 (Sprint 8)
- [ ] Versioned benchmark corpus
- [ ] Entity-level metrics
- [ ] Release gates passing
- [ ] Production-ready accuracy
- [ ] Full documentation

---

## ⚠️ Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| NER model size too large | Installer bloat | ONNX quantization, lazy loading |
| DOCX edge cases | Detection failures | Comprehensive test fixtures |
| Performance regression | Slow scans | Batch inference, profiling |
| Indonesian NER accuracy | User trust | Benchmark-driven selection |
| Breaking changes | Existing users | Backward compatibility tests |

---

## 📝 Notes

- Setiap sprint harus backward compatible
- Testing adalah critical path - jangan skip
- NER model selection berdasarkan benchmark, bukan reputasi
- No cloud/remote inference - privacy first
- UI changes should be incremental

---

*Created from BACKLOG.md + Technical20-20PII20Improvement.md analysis*
*September 2026*
