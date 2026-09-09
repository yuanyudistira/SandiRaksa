# Technical Design — SandiRaksa PII Detection Accuracy Improvement

**Product:** SandiRaksa  
**Target:** v0.3.x–v1.0  
**Status:** Proposed for Development  
**Scope:** TXT, DOCX, PPTX, CSV, XLSX  
**Constraint:** 100% local processing; no public/cloud AI or remote NLP inference.

---

## 1. Executive Summary

SandiRaksa v0.2.0 currently has inconsistent detection behavior across formats:

```text
CSV / XLSX -> Presidio-based detection
TXT / DOCX / PPTX -> regex-centric/manual detection
```

The proposed improvement does **not** begin with adding a larger NER model.

For DOCX and PPTX, the first technical priority is to ensure that the detector receives **logical text as the user reads it**, rather than fragments as Office stores them internally.

Example:

```text
Visible:
Nama: Satria Putra Yudistira

Internal DOCX:
Run 1: "Nama: "
Run 2: "Sat"
Run 3: "ria Put"
Run 4: "ra Yudistira"
```

If detection is performed per run, regex and NER can both fail.

Required processing order:

```text
Correct extraction
    ->
Logical text reconstruction
    ->
Structural/spatial context
    ->
Unified detection
    ->
Indonesian validators
    ->
Local Indonesian NER
    ->
Context/confidence fusion
    ->
User review
    ->
Protection
    ->
Leakage re-scan
```

---

## 2. Design Goals

The new architecture MUST:

1. Use one unified detection interface for all supported formats.
2. Separate document parsing from PII detection.
3. Reconstruct logical text across DOCX/PPTX runs.
4. Preserve mappings from logical character offsets back to source document nodes.
5. Use file structure as context.
6. Use Presidio as a recognizer orchestration layer.
7. Support Indonesian-specific recognizers.
8. Support a pluggable local NER provider.
9. Run fully offline.
10. Keep detection and document mutation independently testable.
11. Measure accuracy per entity and per format.
12. Re-scan protected output.
13. Preserve backward compatibility with existing projects/history.

---

## 3. Target Architecture

```text
                    +---------------------+
TXT ---------------->                     |
DOCX --------------->   Document Adapter  |
PPTX --------------->                     |
XLSX --------------->                     |
CSV ---------------->                     |
                    +----------+----------+
                               |
                               v
                    Logical Text Segments
                               |
                               v
              +--------------------------------+
              | Unified Detection Pipeline     |
              |                                |
              | Custom Terms                   |
              | Structured Validators          |
              | Presidio Built-ins             |
              | Indonesian Recognizers         |
              | Local Indonesian NER           |
              | Context Scorer                 |
              | Negative Evidence              |
              | Overlap Resolver               |
              | Confidence Classification      |
              +---------------+----------------+
                              |
                              v
                           Findings
                              |
                 +------------+-------------+
                 |                          |
                 v                          v
             Span Mapper                 Review UI
                 |
                 v
          Protector / Writer
                 |
                 v
          Leakage Re-Scan
```

---

## 4. Separation of Responsibilities

### 4.1 Document Adapter

Document adapters MUST NOT determine whether content is PII.

Responsibilities:

```text
extract
reconstruct
add document context
map logical offsets
apply approved replacements
save
validate
```

Recommended adapters:

```text
TxtDocumentAdapter
DocxDocumentAdapter
PptxDocumentAdapter
CsvDocumentAdapter
XlsxDocumentAdapter
```

### 4.2 Detection Engine

```python
class DetectionEngine(Protocol):
    def analyze(
        self,
        segment: "LogicalSegment",
        policy: "DetectionPolicy",
    ) -> list["Finding"]:
        ...
```

Detection MUST be file-format agnostic.

---

## 5. Core Data Model

### 5.1 LogicalSegment

```python
class LogicalSegment(BaseModel):
    id: str
    text: str

    file_id: str
    file_type: str
    location: "DocumentLocation"

    previous_text: str | None = None
    next_text: str | None = None
    heading: str | None = None

    table_headers: list[str] = []
    row_headers: list[str] = []

    slide_title: str | None = None
    nearby_labels: list[str] = []

    document_hints: list[str] = []

    char_map: list["CharMapEntry"]
```

The detector reads `text` plus context.

The writer uses `char_map`.

### 5.2 DocumentLocation

```python
class DocumentLocation(BaseModel):
    component: str

    page: int | None = None
    slide: int | None = None
    sheet: str | None = None
    cell: str | None = None

    paragraph_index: int | None = None
    table_index: int | None = None
    shape_id: str | None = None
```

### 5.3 CharMapEntry

```python
class CharMapEntry(BaseModel):
    logical_start: int
    logical_end: int

    source_component_id: str
    source_start: int
    source_end: int
```

Purpose:

```text
Logical finding:
start=6, end=28

->

DOCX Run 2 + Run 3 + Run 4
```

---

## 6. DOCX Logical Text Reconstruction

### 6.1 Mandatory Rule

Primary detection MUST NOT run independently on each Word run.

### 6.2 Algorithm

For each logical paragraph/text container:

1. Enumerate text-bearing runs/nodes.
2. Concatenate visible text.
3. Build `char_map`.
4. Add paragraph/document context.
5. Run detection on reconstructed text.
6. Convert finding spans back to source runs.
7. Apply token/replacement to affected characters only.
8. Preserve unaffected formatting.
9. Re-open and validate the generated DOCX.

Pseudo-code:

```python
logical = ""
char_map = []

for run in runs:
    start = len(logical)
    logical += run.text
    end = len(logical)

    char_map.append(
        CharMapEntry(
            logical_start=start,
            logical_end=end,
            source_component_id=run.id,
            source_start=0,
            source_end=len(run.text),
        )
    )
```

### 6.3 DOCX Context

Attach where available:

```text
nearest heading
previous paragraph
next paragraph
table header
section title
paragraph style
header/footer context
comment context
```

Example:

```text
Heading: Data Karyawan
Paragraph: NIK: 3271051708990001
```

The heading becomes positive document context.

---

## 7. PPTX Reconstruction and Spatial Context

### 7.1 Mandatory Rule

Primary detection MUST NOT run independently per PowerPoint run.

### 7.2 Reconstruction

Reconstruct logical text for:

```text
text frame
paragraph
table cell
title placeholder
notes
```

using the same offset mapping concept as DOCX.

### 7.3 Spatial Context

PowerPoint often expresses meaning spatially:

```text
[NIK]        [3271051708990001]
[Nama]       [Satria Putra]
```

Create:

```python
class SpatialContextResolver:
    def get_nearby_labels(
        self,
        current_shape: "ShapeInfo",
        slide_shapes: list["ShapeInfo"],
    ) -> list[str]:
        ...
```

Shape information:

```text
left
top
width
height
center_x
center_y
```

Candidate labels SHOULD be scored using:

```text
horizontal distance
vertical distance
same baseline
left adjacency
top adjacency
font emphasis
short label-like text
shape type
```

Output:

```python
segment.nearby_labels = ["NIK"]
segment.slide_title = "Data Pasien"
```

---

## 8. TXT Segmentation

Do not process a large TXT as one unbounded string.

Default segmentation:

```text
current paragraph
+ previous paragraph as context
+ next paragraph as context
```

Recognize key/value structures:

```text
Nama: Satria Putra
NIK: 327105...
Alamat: Bogor
```

Common separators:

```text
:
=
|
tab
```

The left-hand key becomes structural context.

---

## 9. XLSX / CSV Context

Existing Presidio functionality should be retained behind the unified interface.

Context sources:

```text
column header
row header
sheet name
table name
neighboring labels
```

Example:

```text
Column header: NIK
Cell value: 3271051708990001
```

has significantly stronger evidence than a standalone 16-digit value.

Large-file batching rules from the existing SandiRaksa technical design remain applicable.

---

## 10. Unified Detection Pipeline

Recommended order:

```text
1. Always Protect exact terms
2. Structured identifier candidates
3. Strong regex recognizers
4. Presidio built-in recognizers
5. Indonesian custom recognizers
6. Local Indonesian NER
7. Positive context scoring
8. Negative evidence
9. Overlap resolution
10. Confidence classification
```

Suggested implementation:

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

---

## 11. Presidio Role

Presidio SHOULD serve as the recognition/orchestration layer for:

```text
built-in recognizers
custom recognizers
pattern recognizers
context support
NER result integration
decision tracing
```

Do not tightly couple Office document mutation to Presidio's plain-text anonymizer.

Required separation:

```text
Document Adapter
    ->
LogicalSegment
    ->
Presidio / Recognizers
    ->
Finding
    ->
TreatmentPlan
    ->
Document Adapter Writer
```

---

## 12. Indonesian Structured Recognizers

Required/updated recognizers:

```text
ID_NIK
ID_NPWP
ID_KK
ID_PHONE
ID_BPJS_CANDIDATE
ID_SIM_CANDIDATE
ID_PASSPORT_CANDIDATE
BANK_ACCOUNT_CANDIDATE
```

Each recognizer SHOULD combine:

```text
candidate pattern
+
structural validation
+
semantic validation
+
positive context
+
negative context
```

---

## 13. NIK Recognizer

Do NOT use:

```text
16 digits -> NIK
```

Required pipeline:

```text
16 digits
  ->
regional code structure
  ->
date-of-birth structure
  ->
female-day adjustment handling
  ->
sequence structure
  ->
context evidence
```

Use the terms:

```text
structural validation
semantic validation
```

Do not describe this as checksum validation unless an actual checksum algorithm is used.

Example evidence model:

```text
16-digit structure                    positive
valid regional structure             positive
plausible DOB component              positive
near "NIK"/"KTP"                     strong positive
HR/patient/customer context          positive

near "Invoice Number"                negative
near "Order ID"                      negative
near "SKU"                           negative
```

Weights MUST be calibrated using SandiRaksa test data.

---

## 14. NPWP Recognizer

Support:

```text
legacy 15-digit NPWP
current 16-digit NPWP
NIK-as-NPWP context
formatted variants
unformatted variants
```

Positive context:

```text
NPWP
Nomor Pokok Wajib Pajak
Tax ID
TIN
```

A generic 16-digit number MUST NOT automatically become NPWP.

---

## 15. Indonesian Phone Recognition

Recommended dependency:

```text
phonenumbers
```

Pipeline:

```text
candidate extraction
    ->
phonenumbers.parse(candidate, "ID")
    ->
is_possible_number
    ->
is_valid_number
    ->
context score
```

Support:

```text
+62...
62...
08...
spaces
dashes
parentheses where valid
```

Phone normalization and display formatting MUST remain separate.

---

## 16. PERSON Detection Strategy

Indonesian PERSON detection should combine:

```text
local NER
+
context
+
project custom terms
```

A static name dictionary MUST NOT be the primary PERSON detector.

Counter-example:

```text
PT Budi Makmur
```

The presence of `Budi` does not automatically make it PERSON.

---

## 17. Local NER Provider

Create a model abstraction:

```python
class LocalNERProvider(Protocol):
    def predict(
        self,
        texts: list[str],
    ) -> list[list["NERPrediction"]]:
        ...
```

This allows the team to benchmark/replace:

```text
IndoBERT
IndoRoBERTa
multilingual token-classification model
future custom model
```

without changing the rest of SandiRaksa.

---

## 18. NER Model Selection

Do NOT choose the production model from public benchmark claims alone.

Benchmark against the SandiRaksa Indonesian corpus.

Minimum metrics:

```text
PERSON precision
PERSON recall
PERSON F1

ORG precision/recall/F1
LOCATION precision/recall/F1

cold start
warm inference
CPU usage
peak RAM
model size
installer impact
license
```

GPU MUST NOT be required.

---

## 19. ONNX Runtime Production Deployment

Recommended architecture:

```text
Research / training:
Transformers + PyTorch

Production:
Tokenizer
+
ONNX Runtime
+
optimized/quantized model
```

Reason:

```text
smaller production runtime
lower memory
CPU-friendly inference
simpler packaging than shipping full PyTorch
```

Suggested resources:

```text
resources/nlp/id_ner/
├── model.onnx
├── tokenizer.json
├── tokenizer_config.json
├── labels.json
├── model_metadata.json
└── LICENSE
```

---

## 20. NER Lazy Loading and Batching

The NER model MUST NOT load during normal app startup.

Load only when:

```text
scan starts
+
active policy requires NER
```

Batch inference MUST be used.

Do not run transformer inference:

```text
per run
per PowerPoint shape
per Excel cell
```

Batch constraints SHOULD consider:

```text
number of texts
number of tokens
character count
available RAM
```

---

## 21. Context Engine

Context is divided into four classes:

### 21.1 Lexical

Examples:

```text
Nama
Nama Lengkap
NIK
KTP
NPWP
Alamat
No. HP
Telepon
Pasien
Karyawan
Pelanggan
```

### 21.2 Structural

Examples:

```text
Excel column header
Word heading
table header
TXT key/value label
PowerPoint title
```

### 21.3 Spatial

PowerPoint:

```text
label immediately left
label immediately above
same baseline
nearby shape
```

### 21.4 Document-Level

Examples:

```text
HR
payroll
medical
banking
customer list
legal
M&A
```

Document-level hints may come from:

```text
project protection profile
sheet names
document headings
slide titles
```

They SHOULD influence, not override, strong evidence.

---

## 22. Negative Evidence

Negative evidence is required to reduce false positives.

Example:

```text
3271051708990001
```

Possible evidence:

```text
near "NIK"             -> positive
near "Invoice Number"  -> negative
near "Order ID"        -> negative
near "Serial Number"   -> negative
```

The scorer MUST retain evidence for explainability.

---

## 23. Finding / Evidence Model

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
    confidence_band: str

    detector: str
    evidence: list[ConfidenceEvidence]

    location: DocumentLocation
```

Do not persist raw sensitive text unless required by the encrypted reversible mapping design.

---

## 24. Confidence UI

Do NOT initially present:

```text
Confidence: 87%
```

unless the score has been calibrated as a probability.

MVP UI:

```text
High
Medium
Low
```

Internal score may remain 0.0–1.0.

---

## 25. Scan Modes

Do not expose an unrestricted threshold slider as the primary UX.

Recommended modes:

```text
Strict
Balanced
```

### Strict

Optimize recall.

Recommended for:

```text
HR
medical
financial
legal
customer data
```

### Balanced

Reduce review noise while preserving strong critical-PII detection.

For critical PII:

> recall is more important than precision.

False positive:

```text
extra review
```

False negative:

```text
possible sensitive-data leakage
```

---

## 26. Overlap Resolver

Example:

```text
satria@example.com
```

may be detected as:

```text
EMAIL
PERSON substring
URL/domain-like entity
```

Suggested precedence:

```text
user Always Protect exact rule
>
validated structured identifier
>
strong composite PII
>
NER
>
generic regex
```

Overlapping treatments MUST be resolved before document mutation.

---

## 27. Custom Terms — Raise Priority

Custom terms SHOULD move to P0 for the next release.

Per project:

```text
Always Protect
Never Protect
```

Examples:

```text
Always Protect:
Project Garuda
PT Target Acquisition
Dr. Satria Yudistira

Never Protect:
SandiRaksa
OpenAI
Microsoft
```

Rules MUST:

```text
be local
be encrypted at rest
work across all supported formats
```

---

## 28. User-Correction Learning

Do NOT implement automatic online model fine-tuning.

Near-term design:

```text
user correction
    ->
optional rule suggestion
    ->
user approves
    ->
project rule
```

Examples:

```text
Repeatedly protect "Project Phoenix"
-> suggest Always Protect

Repeatedly allow "SandiRaksa"
-> suggest Never Protect
```

Never silently learn an exclusion rule because that could reduce privacy protection.

---

## 29. Explainability

Review UI SHOULD show:

```text
entity type
confidence band
why detected
positive evidence
negative evidence
detector source
```

Example:

```text
3271051708990001

Detected as:
NIK

Confidence:
High

Evidence:
✓ compatible 16-digit structure
✓ regional structure valid
✓ DOB component plausible
✓ label "NIK" found nearby

Negative evidence:
none
```

---

## 30. Testing Strategy

Tests MUST be split into four independent layers:

```text
1. Extraction
2. Detection
3. Protection
4. Leakage
```

This is critical.

If:

```text
"Satria Putra" is missed
```

the team must know whether the failure came from:

```text
document parser
or
PII detector
```

---

## 31. Extraction Tests

### DOCX Fixtures

Required cases:

```text
name split across runs
bold/italic boundary
hyperlink boundary
table cells
headers/footers
comments where supported
text boxes where supported
mixed language
```

Example:

```text
Run 1: "Sat"
Run 2: "ria "
Run 3: "Putra"

Expected logical text:
"Satria Putra"
```

### PPTX Fixtures

Required cases:

```text
split runs
title + body
label/value in separate shapes
tables
grouped shapes
notes
hidden slides
chart text where supported
```

---

## 32. Detection Tests

Detection tests SHOULD accept `LogicalSegment` directly.

Example:

```python
segment = LogicalSegment(
    text="3271051708990001",
    nearby_labels=["NIK"],
    ...
)
```

Expected:

```text
entity = ID_NIK
confidence = High
```

No DOCX/PPTX file is needed for this test.

---

## 33. Protection Tests

Given:

```text
logical span start=6 end=28
```

verify:

```text
correct source runs modified
unaffected formatting preserved
token inserted once
document opens successfully
```

---

## 34. Leakage Tests

Required end-to-end pipeline:

```text
original
   ->
protect
   ->
re-open output
   ->
re-extract
   ->
re-detect
```

Expected:

```text
protected original value absent
expected token present
document structurally valid
```

---

## 35. SandiRaksa Indonesian Benchmark Corpus

Create a versioned synthetic benchmark covering:

```text
HR
Payroll
Hospital
Banking
Legal
Customer List
CV
Invoice
M&A
Corporate PPT
TXT export
```

Do not use uncontrolled real customer PII.

---

## 36. Indonesian Name Coverage

Include representative patterns:

```text
one-word names
two-word names
three/four-word names
Javanese
Sundanese
Batak
Minang
Balinese
Papuan
Chinese-Indonesian
Arabic-influenced Indonesian names
professional titles
academic titles
```

Include negative examples:

```text
PT Budi Makmur
CV Putra Jaya
Jalan Sudirman
Bank Mandiri
```

The benchmark must test whether organizational names containing person-like words are handled correctly.

---

## 37. Ground Truth Format

Recommended JSONL:

```json
{
  "id": "case_0001",
  "text": "Nama: Satria Putra Yudistira",
  "entities": [
    {
      "start": 6,
      "end": 28,
      "type": "PERSON"
    }
  ],
  "context": {
    "heading": "Data Karyawan"
  }
}
```

Document extraction fixtures SHOULD store expected logical segments separately.

---

## 38. Accuracy Metrics

Do not use one generic "accuracy" number.

Measure:

```text
precision
recall
F1
false positives
false negatives
```

by:

```text
entity
file type
document domain
```

Example:

| Entity | Format | Precision | Recall | F1 |
|---|---|---:|---:|---:|
| PERSON | DOCX | TBD | TBD | TBD |
| PERSON | PPTX | TBD | TBD | TBD |
| NIK | TXT | TBD | TBD | TBD |
| NIK | PPTX | TBD | TBD | TBD |
| NPWP | XLSX | TBD | TBD | TBD |

This separates parser problems from model problems.

---

## 39. Release Accuracy Policy

Critical PII release gates SHOULD focus especially on false negatives.

Recommended critical categories:

```text
NIK
NPWP
EMAIL
PHONE
BANK_ACCOUNT
PERSON
```

Exact release targets MUST be established after the benchmark corpus is stable.

Do not promise ">90% accuracy" without defining:

```text
which entity
which metric
which dataset
which file format
which domain
```

---

## 40. Performance Requirements

Accuracy improvements MUST preserve the existing large-file architecture.

Requirements:

```text
NER batch inference
lazy model loading
no transformer inference per run/cell
resource-aware worker scheduling
cancellable scan
responsive GUI
bounded memory
```

Benchmark NER on:

```text
Windows x64 CPU
macOS Apple Silicon CPU
Linux x64 CPU
```

Measure:

```text
cold model load
warm inference
texts/sec
tokens/sec
peak RAM
model size
installer-size increase
```

GPU MUST NOT be required.

---

## 41. Privacy / Security

Prohibited:

```text
Hugging Face hosted inference
cloud NLP endpoints
remote Presidio
public LLM calls
document upload
telemetry containing document text
```

Production model assets MUST run locally.

Any model download/update feature added later must be explicit and must never upload user content.

---

## 42. Model Versioning

Each detection operation SHOULD record:

```text
detector version
recognizer-rules version
NER model version
context-engine version
policy version
```

Example:

```python
DetectionMetadata(
    detector_version="0.4.0",
    ner_model_version="id-ner-1",
    recognizer_rules_version="id-rules-3",
    context_engine_version="ctx-2",
)
```

This enables reproducibility and regression analysis.

---

## 43. Backward Compatibility

Existing SandiRaksa projects MUST remain readable.

Migration policy:

```text
existing mapping vault -> unchanged
existing operation history -> unchanged
old protected files -> not silently reprocessed
new scans -> use new detection version
```

Operation history retains the detector/model version used at the time.

---

## 44. Suggested Repository Structure

```text
src/sandiraksa/
├── detection/
│   ├── engine.py
│   ├── pipeline.py
│   ├── overlap.py
│   ├── confidence.py
│   ├── context/
│   │   ├── lexical.py
│   │   ├── structural.py
│   │   ├── spatial.py
│   │   └── document.py
│   ├── recognizers/
│   │   ├── id_nik.py
│   │   ├── id_npwp.py
│   │   ├── id_kk.py
│   │   ├── id_phone.py
│   │   ├── id_bpjs.py
│   │   ├── id_sim.py
│   │   ├── id_passport.py
│   │   └── custom_terms.py
│   └── ner/
│       ├── base.py
│       ├── onnx_provider.py
│       ├── tokenizer.py
│       └── labels.py
├── documents/
│   ├── base.py
│   ├── logical_segment.py
│   ├── char_map.py
│   ├── txt_adapter.py
│   ├── docx_adapter.py
│   ├── pptx_adapter.py
│   ├── csv_adapter.py
│   └── xlsx_adapter.py
└── tests/
    ├── extraction/
    ├── detection/
    ├── protection/
    ├── leakage/
    └── accuracy/
```

---

## 45. Recommended Dependencies

Production/core:

```text
presidio-analyzer
phonenumbers
```

NER production candidate:

```text
onnxruntime
tokenizers
```

Research/training only:

```text
transformers
torch
optimum
```

Avoid shipping PyTorch in production unless benchmark results justify it.

---

## 46. Revised Roadmap

### v0.3.0 — Detection Foundation

**P0**

```text
[ ] LogicalSegment
[ ] CharMap
[ ] unified DetectionEngine
[ ] DOCX run reconstruction
[ ] PPTX run reconstruction
[ ] Presidio on TXT/DOCX/PPTX
[ ] CSV/XLSX routed through same interface
[ ] Custom Terms
[ ] extraction regression tests
[ ] detection regression tests
```

Exit criteria:

```text
All supported formats use the same DetectionEngine.
DOCX/PPTX split-run fixture corpus passes.
```

### v0.3.1 — Indonesian Structured PII

**P0/P1**

```text
[ ] Enhanced NIK recognizer
[ ] Enhanced NPWP recognizer
[ ] Enhanced KK recognizer
[ ] phonenumbers integration
[ ] positive context scoring
[ ] negative evidence
[ ] PPTX spatial resolver
[ ] DOCX structural context
[ ] XLSX/CSV header context
```

### v0.4.0 — Indonesian NER

**P1**

```text
[ ] benchmark candidate models
[ ] select production model
[ ] ONNX export
[ ] quantization
[ ] LocalNERProvider
[ ] batch inference
[ ] lazy loading
[ ] Presidio/custom NER integration
```

### v0.4.1 — Confidence & Explainability

```text
[ ] High/Medium/Low confidence
[ ] Strict/Balanced modes
[ ] evidence tracing
[ ] explainable preview
[ ] calibration framework
```

### v0.5.0 — Adaptive Local Rules

```text
[ ] correction tracking
[ ] Always Protect suggestion
[ ] Never Protect suggestion
[ ] project-scoped learned rules
```

No online fine-tuning.

### v1.0.0 — Accuracy Hardening

```text
[ ] versioned benchmark corpus
[ ] entity-level metrics
[ ] format-level metrics
[ ] false-negative release gates
[ ] performance regression gates
[ ] leakage regression gates
[ ] model/version reproducibility
```

---

## 47. Updated Priority Matrix

| Item | Priority | Impact |
|---|---:|---:|
| DOCX/PPTX logical reconstruction | P0 | Very High |
| Unified detection engine | P0 | Very High |
| Presidio all formats | P0 | High |
| Indonesian structured validators | P0 | Very High |
| Custom Terms | P0 | High |
| Context engine | P1 | Very High |
| Indonesian local NER | P1 | Very High |
| ONNX optimization | P1 | High |
| Confidence bands | P2 | Medium |
| Confidence calibration | P2 | Medium |
| Local correction rules | P2 | High |
| Online/fine-tune learning | P3 | Medium |
| Multi-language expansion | P3 | Low for current roadmap |

---

## 48. Anti-Patterns

The team MUST avoid:

```text
NER per Word run
NER per PowerPoint run
transformer inference per Excel cell
16 digits -> NIK without validation
raw recognizer score displayed as probability
silent Never Protect learning
remote inference
rewriting paragraph.text and destroying formatting
skipping unsupported/hidden content without reporting it
```

---

## 49. Acceptance Criteria

The improvement is technically successful when:

1. TXT, DOCX, PPTX, CSV, XLSX use a shared detection service.
2. DOCX PII detection works across split runs.
3. PPTX PII detection works across split runs.
4. PPTX nearby-label spatial context is available.
5. NIK uses structural/semantic/context validation.
6. NPWP supports relevant legacy/current formats.
7. Indonesian phone detection uses structural validation.
8. Custom Terms work across all supported formats.
9. Indonesian PERSON detection uses a benchmarked local NER provider.
10. NER runs without internet.
11. Production inference is CPU-capable.
12. High/Medium/Low confidence is available.
13. Detection reasons are available to UI.
14. Extraction and detection tests are independent.
15. Metrics are generated per entity and per format.
16. Critical PII false negatives are tracked.
17. Protected output is leakage re-scanned.
18. Existing projects remain backward compatible.
19. No document content is sent externally.
20. Scans remain bounded, responsive, and cancellable.

---

## 50. v0.3.0 Definition of Done

```text
[ ] LogicalSegment implemented
[ ] CharMap implemented
[ ] TXT adapter migrated
[ ] DOCX adapter migrated
[ ] PPTX adapter migrated
[ ] XLSX/CSV routed to unified engine
[ ] DOCX split-run tests pass
[ ] PPTX split-run tests pass
[ ] Presidio enabled for all supported formats
[ ] Custom Terms available per project
[ ] leakage tests pass
[ ] no cloud inference introduced
```

---

## 51. Engineering Invariants

> **The detector must receive text as the user logically reads it, not merely as the Office document internally stores it.**

> **No PII detector should own file-format-specific replacement logic.**

> **Accuracy must be measured against a versioned SandiRaksa Indonesian benchmark, not inferred from model reputation or public benchmark numbers alone.**

Final target flow:

```text
File
  ->
Document Adapter
  ->
Logical Text Reconstruction
  ->
Structural / Spatial Context
  ->
Custom Terms
  ->
Structured Indonesian Recognizers
  ->
Presidio Built-ins
  ->
Local Indonesian NER
  ->
Positive + Negative Context
  ->
Overlap Resolver
  ->
Confidence Band
  ->
User Review
  ->
Protection
  ->
Output Validation
  ->
Leakage Re-Scan
```
