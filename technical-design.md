# Technical Design
## SandiRaksa — Local Privacy Gateway for AI

**Document:** `Technical design.md`  
**Status:** Draft for Development  
**Architecture:** Local-first modular desktop application  
**Primary Language:** Python  
**GUI:** PySide6 / Qt Widgets  
**Packaging:** Nuitka standalone + native installer per OS  
**Supported MVP formats:** CSV, XLSX, DOCX, PPTX  
**Network model:** Core document processing is offline/local-only.

---

# 1. Purpose

This document defines the proposed technical architecture for a desktop application that protects sensitive information in documents before the documents are shared with external/public AI systems.

The application performs all document inspection and treatment locally.

The system supports two protection modes:

1. **Reversible pseudonymization/tokenization** — default.
2. **Non-reversible treatment** — optional.

A user may create multiple projects, close them, reopen them later, and add more files. Each project maintains its own privacy policy, custom confidential terms, history, and token namespace.

---

# 2. Key Technical Decisions

## TD-001 — Python as the Core Language

Use Python because the hard part of this product is:

- NLP/PII detection;
- Office document parsing;
- OOXML manipulation;
- custom entity recognition;
- encryption/mapping;
- testing many document edge cases.

Packaging complexity is treated as a release-engineering problem rather than a reason to rebuild the privacy/NLP stack in Go.

---

## TD-002 — PySide6 for Desktop UI

Use PySide6 / Qt Widgets.

Reasons:

- mature native desktop UI toolkit;
- Windows/macOS/Linux;
- official Qt Python binding;
- good support for drag-and-drop, tables, dialogs, progress UI, accessibility, and OS integration;
- can be packaged with Nuitka.

Qt Widgets is preferred over QML for MVP because the UI is form/table/workflow oriented rather than animation-heavy.

---

## TD-003 — Nuitka Standalone Distribution

Use Nuitka in **standalone** mode for production artifacts.

Do not optimize for a one-file executable in MVP.

Reason:

- the application contains Qt libraries;
- NLP assets may be large;
- recognizer/model files are external data assets;
- one-file mode introduces temporary extraction behavior;
- standalone builds are easier to debug and validate.

Production packaging:

```text
Windows -> standalone app -> signed installer
macOS   -> .app bundle -> signed/notarized DMG
Linux   -> standalone app -> AppImage
```

Build separately on native target OS runners.

---

## TD-004 — Project-Scoped Privacy Boundary

Every project has its own:

- UUID;
- policy;
- profile;
- custom rules;
- file records;
- operation records;
- token namespace;
- reversible mapping vault;
- deterministic pseudonym secret.

Never use a single global identity-to-token database by default.

---

## TD-005 — Reversible Mode Default ON

New projects:

```text
reversible_enabled = true
```

When ON:

```text
original value
   ->
stable project token
   +
encrypted mapping
```

When OFF:

- do not persist original values for restore;
- produce redacted/replaced/generalized output;
- optional stable pseudonym IDs may be generated from a project HMAC secret.

---

## TD-006 — Local-Only Intelligence

No public AI/API dependency.

Base detection stack:

```text
Presidio
+ regex/rules
+ context
+ validation/checksum
+ spaCy local NLP
+ custom Indonesian recognizers
+ user custom confidential rules
```

No runtime cloud NER calls.

---

# 3. High-Level Architecture

```text
┌──────────────────────────────────────────────────────┐
│                    PySide6 GUI                       │
│                                                      │
│ Projects | Files | Review | Results | Restore       │
│ Settings | Help | About                              │
└───────────────────────┬──────────────────────────────┘
                        │
                 Application Services
                        │
    ┌───────────────────┼────────────────────┐
    │                   │                    │
    ▼                   ▼                    ▼
Project Service    Protection Service   Restore Service
    │                   │                    │
    └──────────────┬────┴──────────────┬────┘
                   │                   │
                   ▼                   ▼
         Document Abstraction     Token/Vault
                   │                   │
       ┌───────────┼──────────┐        │
       │           │          │        │
       ▼           ▼          ▼        ▼
      CSV         XLSX       DOCX     Crypto
                              PPTX     SQLite
       │           │          │        Keyring
       └───────────┼──────────┘
                   ▼
             Detection Engine
                   │
        ┌──────────┼────────────┐
        ▼          ▼            ▼
     Presidio    Rules       Local NLP
        │          │            │
        └──────────┼────────────┘
                   ▼
              Findings Model
```

---

# 4. Proposed Repository Structure

```text
sandiraksa/
├── pyproject.toml
├── uv.lock / requirements.lock
├── README.md
├── requirements.md
├── Technical design.md
├── LICENSE
├── THIRD_PARTY_NOTICES.md
│
├── src/
│   └── sandiraksa/
│       ├── __init__.py
│       ├── __main__.py
│       ├── version.py
│       │
│       ├── app/
│       │   ├── application.py
│       │   ├── commands.py
│       │   └── events.py
│       │
│       ├── ui/
│       │   ├── main_window.py
│       │   ├── project_list.py
│       │   ├── project_view.py
│       │   ├── file_drop.py
│       │   ├── scan_progress.py
│       │   ├── findings_review.py
│       │   ├── results_view.py
│       │   ├── restore_view.py
│       │   ├── project_settings.py
│       │   ├── help_dialog.py
│       │   ├── about_dialog.py
│       │   └── widgets/
│       │
│       ├── domain/
│       │   ├── project.py
│       │   ├── file_record.py
│       │   ├── operation.py
│       │   ├── finding.py
│       │   ├── treatment.py
│       │   ├── token.py
│       │   ├── policy.py
│       │   └── profile.py
│       │
│       ├── detection/
│       │   ├── engine.py
│       │   ├── presidio_engine.py
│       │   ├── entity_types.py
│       │   ├── context.py
│       │   ├── recognizers/
│       │   │   ├── id_nik.py
│       │   │   ├── id_npwp.py
│       │   │   ├── id_kk.py
│       │   │   ├── id_phone.py
│       │   │   ├── bank_account.py
│       │   │   ├── financial.py
│       │   │   └── custom_terms.py
│       │   └── nlp/
│       │       ├── base.py
│       │       ├── spacy_engine.py
│       │       └── enhanced_model.py
│       │
│       ├── documents/
│       │   ├── base.py
│       │   ├── registry.py
│       │   ├── csv_handler.py
│       │   ├── xlsx_handler.py
│       │   ├── docx_handler.py
│       │   ├── pptx_handler.py
│       │   └── ooxml/
│       │       ├── package.py
│       │       ├── text_map.py
│       │       ├── xml_parts.py
│       │       └── safe_xml.py
│       │
│       ├── protection/
│       │   ├── pipeline.py
│       │   ├── tokenizer.py
│       │   ├── masker.py
│       │   ├── redactor.py
│       │   ├── generalizer.py
│       │   ├── consistency.py
│       │   └── rescan.py
│       │
│       ├── restore/
│       │   ├── pipeline.py
│       │   ├── token_parser.py
│       │   ├── validator.py
│       │   └── restorer.py
│       │
│       ├── storage/
│       │   ├── database.py
│       │   ├── migrations/
│       │   ├── repositories.py
│       │   ├── vault.py
│       │   ├── key_store.py
│       │   └── paths.py
│       │
│       ├── security/
│       │   ├── crypto.py
│       │   ├── hashing.py
│       │   ├── tempfiles.py
│       │   ├── logging_filter.py
│       │   └── file_validation.py
│       │
│       ├── profiles/
│       │   ├── standard_pii.yaml
│       │   ├── hr.yaml
│       │   ├── customer.yaml
│       │   ├── legal.yaml
│       │   ├── ma.yaml
│       │   └── banking.yaml
│       │
│       ├── config/
│       │   ├── settings.py
│       │   └── product.toml
│       │
│       └── resources/
│           ├── icons/
│           ├── help/
│           ├── licenses/
│           └── nlp/
│
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── regression_documents/
│   ├── security/
│   └── packaged_smoke/
│
├── scripts/
│   ├── build_windows.py
│   ├── build_macos.py
│   ├── build_linux.py
│   └── generate_notices.py
│
└── .github/
    └── workflows/
        ├── test.yml
        └── release.yml
```

---

# 5. Application State and Project Lifecycle

## 5.1 Application Lifecycle

```text
Launch
  ->
Initialize local config
  ->
Open metadata database
  ->
Initialize OS key store adapter
  ->
Load project list
  ->
User opens/creates project
```

No NLP model needs to be loaded until a scan starts.

This reduces startup time.

---

## 5.2 Project Lifecycle

```text
Create Project
   ->
Generate project UUID
   ->
Generate project crypto/pseudonym secrets
   ->
Save metadata
   ->
Add files
   ->
Scan
   ->
Review
   ->
Protect
   ->
Save mappings/history
   ->
Close Project

Later:

Open Project
   ->
Unlock project secrets
   ->
Load policy/history
   ->
Add more files
   ->
Reuse project token namespace
```

---

# 6. Storage Model

Use two storage layers:

1. SQLite for structural/application metadata.
2. Authenticated encrypted fields/blobs for sensitive metadata and reversible mappings.

Use `platformdirs` to determine OS-specific data locations.

Example:

### Windows

```text
%LOCALAPPDATA%/<Company>/SandiRaksa/
```

### macOS

```text
~/Library/Application Support/SandiRaksa/
```

### Linux

```text
~/.local/share/SandiRaksa/
```

---

# 7. Database Schema

SQLite is sufficient for MVP.

Enable:

```sql
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;
```

Use explicit migrations.

---

## 7.1 projects

```sql
CREATE TABLE projects (
    id TEXT PRIMARY KEY,
    name_enc BLOB NOT NULL,
    description_enc BLOB,
    profile_id TEXT NOT NULL,
    reversible_default INTEGER NOT NULL DEFAULT 1,
    remember_source_paths INTEGER NOT NULL DEFAULT 0,
    retention_policy TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_opened_at TEXT,
    schema_version INTEGER NOT NULL
);
```

---

## 7.2 files

```sql
CREATE TABLE files (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    filename_enc BLOB NOT NULL,
    source_path_enc BLOB,
    extension TEXT NOT NULL,
    file_size INTEGER,
    source_sha256 TEXT,
    latest_output_sha256 TEXT,
    added_at TEXT NOT NULL,
    last_processed_at TEXT,
    status TEXT NOT NULL,
    FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
);
```

`source_path_enc` MUST be null unless the user has enabled remembering source locations.

---

## 7.3 operations

```sql
CREATE TABLE operations (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    file_id TEXT,
    operation_type TEXT NOT NULL,
    reversible INTEGER NOT NULL,
    profile_id TEXT,
    app_version TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    status TEXT NOT NULL,
    findings_total INTEGER NOT NULL DEFAULT 0,
    treated_total INTEGER NOT NULL DEFAULT 0,
    ignored_total INTEGER NOT NULL DEFAULT 0,
    residual_total INTEGER NOT NULL DEFAULT 0,
    warnings_json TEXT,
    source_sha256 TEXT,
    output_sha256 TEXT,
    FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
);
```

No original values in `warnings_json`.

---

## 7.4 custom_rules

```sql
CREATE TABLE custom_rules (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    rule_type TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    pattern_enc BLOB NOT NULL,
    case_sensitive INTEGER NOT NULL DEFAULT 0,
    treatment TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
);
```

Even custom keywords should be encrypted because a project codename can itself be confidential.

---

## 7.5 token_mappings

```sql
CREATE TABLE token_mappings (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    token TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    normalized_hmac TEXT NOT NULL,
    original_value_enc BLOB NOT NULL,
    created_at TEXT NOT NULL,
    last_used_at TEXT NOT NULL,
    expires_at TEXT,
    UNIQUE(project_id, token),
    UNIQUE(project_id, entity_type, normalized_hmac),
    FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
);
```

`normalized_hmac` is a keyed HMAC of normalized value.

It is used for lookup without storing plaintext normalization.

Do NOT use a plain SHA-256 of names or email addresses because low-entropy values can be dictionary attacked.

---

# 8. Key Management

## 8.1 Key Hierarchy

Recommended:

```text
OS Key Store
   |
   +-- Application Master Key (AMK)
             |
             +-- derive/wrap Project Key A
             +-- derive/wrap Project Key B
             +-- derive/wrap Project Key C
```

Alternative implementation:

- generate one random project encryption key;
- wrap/encrypt it with the Application Master Key;
- store only wrapped project key in SQLite.

Never store raw project keys in SQLite.

---

## 8.2 OS Key Store

Use `keyring`.

Backends:

- Windows Credential Manager
- macOS Keychain
- Linux Secret Service/keyring where available

Linux environments without a secure keyring MUST be detected.

Do not silently fall back to plaintext key storage.

Fallback options:

1. Require user password to derive key.
2. Warn that secure key storage is unavailable.
3. Disable persistent reversible mapping until secure storage is configured.

---

# 9. Encryption Design

Use `cryptography`.

Preferred primitive:

```text
AES-256-GCM
```

Each encrypted value:

```text
version
nonce
ciphertext
authentication tag
```

Use a fresh random nonce for every encryption operation.

Use Additional Authenticated Data (AAD).

Example AAD:

```text
project_id | table | row_id | field_name
```

This prevents encrypted values from being moved between records without detection.

---

## 9.1 Crypto Record Example

Logical representation:

```json
{
  "v": 1,
  "alg": "AES-256-GCM",
  "nonce": "...",
  "ciphertext": "..."
}
```

The encoding may be binary rather than JSON in SQLite.

---

# 10. Token Design

## 10.1 Token Format

Recommended grammar:

```regex
\[\[(?<type>[A-Z][A-Z0-9_]{1,31})_(?<id>[A-F0-9]{6,16})\]\]
```

Examples:

```text
[[PERSON_7F31A2]]
[[EMAIL_C83719]]
[[ORG_91DC44]]
[[NIK_A3187F]]
[[CONFIDENTIAL_117A3F]]
```

Do not use sequential IDs such as:

```text
PERSON_001
PERSON_002
```

unless an explicit profile requires human-readable pseudonyms.

---

## 10.2 Token Generation

Input:

```text
project_id
entity_type
normalized_value
```

Process:

```text
normalized_value
  ->
HMAC(project_pseudonym_key, entity_type || normalized_value)
  ->
take sufficient identifier bytes
  ->
render token
```

Collision check MUST be performed against existing project mappings.

If collision occurs, extend the token ID length.

---

## 10.3 Value Normalization

Normalization is entity-specific.

Examples:

Email:

```text
trim
lowercase domain
preserve/normalize local part according to policy
```

Phone:

```text
remove formatting
normalize country code where confidently known
```

Person:

```text
trim
collapse whitespace
Unicode normalization
casefold for lookup
```

Do not over-normalize if it could merge distinct entities.

Store the original exact display value encrypted.

---

# 11. Reversible and Non-Reversible State

## 11.1 Reversible Mode

```text
Detected value
   ->
lookup normalized HMAC
   ->
existing token?
   | yes -> reuse
   | no  -> create new token + encrypted original
   ->
replace in document
```

---

## 11.2 Non-Reversible Deterministic Mode

For a deterministic project pseudonym without restoration:

```text
Detected value
   ->
HMAC(project pseudonym key, normalized value)
   ->
[[PERSON_7F31A2]]
```

Do NOT store original value.

This preserves consistency within the project while preventing direct reverse lookup.

Important:

This is not proof of formal anonymization. Low-entropy values may still be guessable by an attacker with sufficient auxiliary information.

---

## 11.3 Redaction Mode

```text
John Smith -> [REDACTED]
```

No mapping.

---

# 12. Detection Architecture

Define a common interface:

```python
class Detector(Protocol):
    def analyze(
        self,
        text: str,
        context: DetectionContext,
    ) -> list[Finding]:
        ...
```

---

## 12.1 Finding Model

Suggested model:

```python
class Finding(BaseModel):
    id: UUID
    entity_type: str
    start: int
    end: int
    score: float | None
    confidence_band: str
    detector: str
    reason_codes: list[str]
    file_id: UUID
    location: DocumentLocation
    text_hash: str
```

Avoid persisting raw finding text after the review/operation unless required for a reversible mapping.

---

# 13. Presidio Integration

Use:

```text
presidio-analyzer
presidio-anonymizer
```

The Analyzer is used for:

- recognizer registry;
- regex recognizers;
- context;
- NER integration;
- confidence/scoring;
- custom recognizers.

The product SHOULD define its own treatment abstraction rather than tightly coupling all file transformations to Presidio's plain-text anonymizer.

Reason:

Office processing needs location-aware modifications inside structured document components.

Concept:

```text
Document Handler
    ->
Extract Text Segments
    ->
Presidio / detectors
    ->
Findings
    ->
Review decisions
    ->
Treatment Plan
    ->
Document Handler applies edits
```

---

# 14. Indonesian Recognizers

Create project-owned recognizers.

Candidate recognizers:

- `ID_NIK`
- `ID_NPWP`
- `ID_KK`
- `ID_PHONE`
- `ID_PASSPORT_CANDIDATE`
- `ID_BPJS_CANDIDATE`
- `BANK_ACCOUNT_CANDIDATE`

Each recognizer SHOULD combine:

```text
pattern
+ length validation
+ contextual keywords
+ invalidation rules
+ optional checksum/semantic structure
```

Never treat a regex match as certainty where no reliable validation exists.

---

# 15. Business Confidential Detection

PII frameworks do not solve all confidentiality use cases.

Build a dedicated layer:

```text
Custom Confidential Engine
```

Sources:

- exact phrase dictionary;
- case-insensitive terms;
- regex;
- allow-list;
- privacy-profile rules;
- manually confirmed entities.

Examples:

```text
Project Garuda
PT Target Acquisition
Supplier X
Formula Falcon
Client ABC
```

User-confirmed custom values SHOULD persist encrypted in project rules.

---

# 16. Local NLP Strategy

## 16.1 MVP

Use spaCy through Presidio for baseline NER.

Do not include a heavyweight transformer framework by default until benchmarked.

Goals:

- PERSON
- ORG
- GPE/LOCATION

English support can use a bundled spaCy model.

Indonesian accuracy MUST be measured separately.

---

## 16.2 Enhanced Indonesian/Multilingual Model

Create an abstraction so a future local model can use:

- ONNX Runtime;
- a lightweight transformer runtime;
- Presidio TransformersNlpEngine if package-size trade-offs are acceptable.

Do not make the base application depend on PyTorch unless justified by measured accuracy benefit.

Model acceptance gate:

```text
Precision
Recall
F1
RAM
Cold start
Scan throughput
Disk size
Cross-OS compatibility
License
```

All model assets must be vendored/bundled at build time.

---

# 17. Document Abstraction Layer

Document handlers MUST expose text as logical segments.

Example:

```python
class DocumentHandler(ABC):

    def inspect(self, path: Path) -> DocumentInventory:
        ...

    def extract_segments(self) -> Iterable[TextSegment]:
        ...

    def apply_treatments(
        self,
        treatments: list[Treatment],
        output_path: Path
    ) -> ApplyResult:
        ...

    def validate_output(self, output_path: Path) -> ValidationResult:
        ...
```

---

## 17.1 TextSegment

```python
class TextSegment(BaseModel):
    segment_id: str
    location: DocumentLocation
    text: str
    editable: bool
    component_type: str
    metadata: dict[str, Any]
```

A segment MUST provide enough information for safe round-trip editing.

---

# 18. OOXML Strategy

`.xlsx`, `.docx`, and `.pptx` are ZIP/OPC packages containing XML and binary parts.

Do not rely only on high-level libraries.

Use a hybrid architecture:

```text
High-level library
  +
low-level OOXML package inspection
```

High-level:

- openpyxl
- python-docx
- python-pptx

Low-level:

- zipfile
- lxml
- defusedxml-compatible safe parsing

Purpose:

- inspect unsupported text-bearing parts;
- preserve relationships;
- handle text split across runs;
- scan metadata;
- detect hidden content;
- validate package integrity.

---

# 19. Text Across Runs

Office text is often split across XML runs.

Visible text:

```text
John Smith
```

may internally be:

```xml
<w:r><w:t>Jo</w:t></w:r>
<w:r><w:t>hn </w:t></w:r>
<w:r><w:t>Smith</w:t></w:r>
```

Naive per-run scanning will miss the entity.

Required algorithm:

1. Reconstruct logical paragraph/text-container string.
2. Build an offset map from logical characters to source XML nodes/runs.
3. Run detection on reconstructed text.
4. Convert finding offsets back to run ranges.
5. Apply token into the first affected editable run.
6. Remove affected characters from subsequent runs.
7. Preserve unaffected run formatting.
8. Reconstruct and validate document.

This is a critical architecture requirement.

---

# 20. CSV Handler

Use Python `csv`.

Pipeline:

```text
detect encoding
  ->
detect/confirm delimiter
  ->
read rows
  ->
treat cell text
  ->
write with equivalent dialect
  ->
re-open
  ->
re-scan
```

Do not convert CSV to pandas DataFrame solely for processing.

Large files SHOULD stream row-by-row, but project-level consistency mapping remains available.

CSV injection consideration:

The application does not evaluate formulas, but it SHOULD preserve or optionally neutralize dangerous spreadsheet-formula prefixes when a future export mode requires it. This is separate from PII treatment.

---

# 21. XLSX Handler

## 21.2 XLSX Large-Workbook Strategy

The XLSX handler must support two distinct modes:

```text
SCAN MODE
- iterative/read-only where possible
- minimal memory
- no mutation

TREATMENT MODE
- mutable high-level model when safe
- targeted OOXML fallback for scale/preservation when required
```

The handler MUST expose workload metadata to the scheduler before full processing.

For large workbooks:

- iterate worksheet rows;
- build bounded `TextSegment` batches;
- invoke detection in batches;
- release plaintext batches promptly;
- record progress by worksheet/batch;
- do not load unrelated worksheets into duplicated structures;
- do not build a DataFrame representation;
- do not parallelize multiple large workbooks by default.

High-level mutable loading is acceptable only when benchmark/resource policy determines that it is safe.


Use `openpyxl` plus OOXML fallback.

Inventory MUST detect:

- worksheet list;
- visible/hidden/veryHidden states;
- shared strings;
- inline strings;
- comments;
- hyperlinks;
- formulas;
- defined names;
- charts;
- core/custom properties where accessible;
- external relationships;
- VBA presence for `.xlsm` if supported.

Never evaluate formulas.

---

## 21.1 XLSX Treatment Rules

Simple string cell:

- replace in cell value.

Rich text / unsupported content:

- use low-level OOXML transformation or mark as unsupported.

Formula:

- do not blindly replace arbitrary substrings inside formulas.
- scan string literals and relevant formula metadata separately.
- only modify when a parser-safe treatment exists.

Hidden sheets:

- always scan;
- never assume "hidden" means irrelevant.

---

# 22. DOCX Handler

Use `python-docx` plus OOXML fallback.

Inventory:

- body paragraphs;
- tables;
- headers;
- footers;
- comments;
- hyperlinks;
- text boxes where reachable;
- core properties;
- custom properties where supported;
- footnotes/endnotes via OOXML inspection.

Treat logical paragraph text across runs.

Preserve:

- styles;
- fonts;
- formatting;
- numbering;
- relationships;
- images;
- sections.

---

# 23. PPTX Handler

Use `python-pptx` plus OOXML fallback.

Inventory:

- slides;
- hidden slides;
- shapes;
- grouped shapes;
- placeholders;
- tables;
- notes;
- comments if present/accessible;
- chart text;
- hyperlinks;
- core properties.

Treatment:

- scan each logical text frame;
- rebuild offsets across runs;
- apply token without flattening all formatting where possible.

Do not OCR pictures in MVP.

---

# 24. Unsupported Component Handling

Every document inspection returns:

```python
class CoverageItem(BaseModel):
    component: str
    status: Literal["scanned", "partially_scanned", "not_scanned"]
    reason: str | None
```

Example:

```text
Body text              scanned
Speaker notes          scanned
Images                  not_scanned: OCR not enabled
Embedded OLE object     not_scanned: unsupported
```

If a policy requires a component that is not scanned:

```text
status = REVIEW_REQUIRED
```

Do not report Ready.

---

# 25. Protection Pipeline

```text
Input file
   |
   v
Validate
   |
   v
Inventory
   |
   v
Extract logical text segments
   |
   v
Detect entities
   |
   v
Merge/resolve overlapping findings
   |
   v
Apply project/user review decisions
   |
   v
Create Treatment Plan
   |
   v
Create/update project tokens
   |
   v
Write protected output
   |
   v
Re-open output
   |
   v
Structural validation
   |
   v
Leakage re-scan
   |
   v
Persist operation history
   |
   v
Ready / Ready with warnings / Review required
```

---

# 26. Overlapping Finding Resolution

Example:

```text
satria@example.com
```

may be detected as:

- EMAIL
- PERSON substring
- DOMAIN/URL-like component

Use deterministic precedence.

Suggested:

```text
exact identifier
> validated structured identifier
> user custom exact confidential
> high-confidence composite entity
> generic NER entity
> low-confidence pattern
```

Never create nested conflicting replacements.

Store reasons for resolution.

---

# 27. Review Decisions

User decisions form a Treatment Plan.

Example:

```python
class ReviewDecision(BaseModel):
    finding_id: UUID
    action: Literal[
        "protect",
        "allow",
        "change_type",
        "change_treatment"
    ]
    entity_type: str | None
    treatment: str | None
    scope: Literal[
        "occurrence",
        "same_value_file",
        "same_value_project"
    ]
```

If `same_value_project`, persist encrypted project rule/allow rule as appropriate.

---

# 28. Leakage Re-Scan

After output creation:

1. Open output independently.
2. Rebuild inventory.
3. Re-extract text.
4. Run exact search for protected originals only while originals are available in secure in-memory/vault context.
5. Run full enabled detection engine.
6. Check metadata.
7. Check user custom confidential terms.
8. Create residual findings.

This second pass MUST NOT assume the first transformation succeeded.

---

# 29. Restoration Architecture

Input:

- project;
- external/AI-returned document;
- project token vault.

Process:

```text
Open returned file
   ->
extract token-like strings
   ->
parse strict token grammar
   ->
lookup project mapping
   ->
classify
      known
      unknown
      malformed
      modified
   ->
show validation
   ->
apply exact replacements
   ->
save restored copy
   ->
re-open/validate
```

---

# 30. No Aggressive Fuzzy Restoration

Do not automatically infer:

```text
[PERSON 7F31A2]
```

is the same as:

```text
[[PERSON_7F31A2]]
```

unless a future explicitly reviewed feature is implemented.

Reason:

wrong restoration can insert private data into the wrong location.

MVP:

- strict exact token matching;
- manual conflict resolution.

---

# 31. Restore Audit

Restore result:

```python
class RestoreReport(BaseModel):
    known_tokens: int
    unknown_tokens: int
    malformed_tokens: int
    restored_occurrences: int
    missing_expected_tokens: int | None
    output_sha256: str
    warnings: list[str]
```

Do not include original PII in the report by default.

---

# 32. Project History

History is metadata, not document backup.

Persist:

- operation type;
- internal file ID;
- encrypted filename;
- hashes;
- counts;
- warnings;
- app version;
- policy/profile;
- time;
- reversible flag.

Do not persist:

- extracted full text;
- complete original files;
- complete protected files;
- plaintext entity list.

---

# 33. File Fingerprints

Use SHA-256 for integrity/fingerprinting:

```text
source_sha256
protected_sha256
restored_sha256
```

Purpose:

- identify exact file versions;
- tie history to outputs;
- detect accidental reprocessing;
- aid restore validation.

SHA-256 is for file fingerprints, not password/key derivation.

---

# 34. Project Reopen and New Files

When an existing project receives a new file:

```text
new finding
  ->
normalize
  ->
HMAC lookup
  ->
existing project mapping?
    yes -> reuse token
    no  -> create token
```

This preserves project-level referential consistency.

Existing output files are not automatically updated.

---

# 35. Privacy Profiles

Store profiles as version-controlled YAML or TOML bundled with app.

Example:

```yaml
id: ma_due_diligence
name: M&A / Due Diligence
version: 1

entities:
  PERSON:
    enabled: true
    treatment: token
  EMAIL:
    enabled: true
    treatment: token
  ORG:
    enabled: true
    treatment: token
  VALUATION:
    enabled: true
    treatment: token
  EBITDA:
    enabled: true
    treatment: token

metadata:
  remove_author: true
  remove_last_modified_by: true

review:
  block_on_high_residual: true
```

Project overrides are stored separately.

---

# 36. Help System

Bundle offline help files in application resources.

Suggested format:

```text
Markdown -> rendered HTML
```

Topics:

```text
getting-started.md
projects.md
protection.md
reversible.md
restore.md
supported-files.md
limitations.md
privacy.md
troubleshooting.md
```

No remote page is required for basic help.

---

# 37. About Dialog and External Links

About data should be build-configured.

Example `product.toml`:

```toml
[product]
name = "SandiRaksa"
company = "<CompanyName>"
support_email = "support@example.com"
support_url = "https://example.com/support"
documentation_url = "https://example.com/docs"
privacy_url = "https://example.com/privacy"
donation_url = "https://example.com/donate"
release_url = "https://example.com/download"
```

Use `QDesktopServices.openUrl()` only after the user clicks a link.

Never append:

- project ID;
- filename;
- document name;
- token;
- PII;
- diagnostic data

to outgoing URLs.

---

# 38. Threading and Responsiveness

Never run scanning on the GUI thread.

Recommended:

- `QThreadPool` / `QRunnable`;
- worker processes for CPU-heavy NLP if needed;
- cancellation token;
- progress events.

Architecture:

```text
GUI
 |
 +-- scan request
        |
        v
   worker service
        |
        +-- progress events -> GUI
        +-- findings -> GUI
```

PySide objects must follow Qt thread-affinity rules.

---

# 39. Memory Handling

Sensitive values will exist in Python memory during processing.

Python cannot guarantee deterministic memory zeroization for immutable strings.

Therefore:

- minimize lifetime;
- avoid global caches;
- avoid unnecessary copies;
- do not retain extracted text after operation;
- keep decrypted mapping scope narrow;
- clear data structures promptly;
- document this limitation honestly.

Do not claim cryptographic secure memory erasure from standard CPython.

---

# 40. Temporary Files

Use `tempfile` under user-specific temp directories.

Rules:

- random names;
- no sensitive value in filename;
- cleanup on success;
- best-effort cleanup on crash/startup;
- do not place decrypted vault exports in temp;
- one operation per temp workspace.

At application startup, stale temp workspaces created by the app MAY be cleaned after ownership/signature validation.

---

# 41. Logging Architecture

Use standard `logging` or structured logging adapter.

Add a mandatory `PIIRedactionFilter`.

Log fields:

```text
event
operation_id
project_internal_id
file_internal_id
component
duration
counts
error_code
```

Never log:

```text
raw text
entity value
filename unless encrypted/non-sensitive setting explicitly allows
full source path
document excerpt
mapping
```

---

# 42. Exception Handling

Internal exception:

```python
DocumentProcessingError(
    code="DOCX_UNSUPPORTED_PART",
    file_id=...,
    component="word/embeddings/..."
)
```

UI message:

```text
This document contains an embedded component that could not be fully inspected.
Review is required before sharing the output.
```

Do not expose stack traces by default.

---

# 43. Network Policy

Core engine should have no runtime dependency on network services.

Production application:

- no cloud AI client;
- no remote Presidio service;
- no model auto-download;
- no telemetry by default;
- no document-content crash reporting;
- no update polling in MVP.

User-initiated Help/About links may open a browser.

Recommended automated test:

- run core integration tests with outbound sockets blocked/monkey-patched;
- verify complete protect/restore workflow succeeds offline.

This is a test aid, not a security sandbox.

---

# 44. XML Security

OOXML is XML-based and input must be considered hostile.

Requirements:

- disable external entity resolution;
- prevent unsafe DTD processing;
- use `defusedxml` where compatible;
- apply ZIP bomb limits;
- limit extracted entry count;
- limit decompressed package size;
- validate path traversal (`../`) inside ZIP;
- reject suspicious archive structures.

`openpyxl` documentation explicitly recommends `defusedxml` for protection against XML expansion attacks; this should be treated as a required security dependency where applicable.

---

# 45. ZIP/OOXML Bomb Protection

Before extracting OOXML:

Check:

```text
number of entries
compressed size
declared uncompressed size
compression ratio
path traversal
duplicate suspicious entries
```

Set limits in config.

Example defaults must be benchmarked, not hardcoded blindly.

---

# 46. Macros and Active Content

For any macro-enabled future support:

- never execute macros;
- preserve macros only when explicitly supported/tested;
- mark presence in privacy report;
- scan metadata/text components independently.

MVP may reject `.xlsm` to reduce risk.

---

# 47. Dependency Strategy

Use `pyproject.toml`.

Recommended environment manager:

- `uv` or standard pip + locked requirements.

Release MUST use exact pins/lock file.

Example dependency groups:

```toml
[project]
dependencies = [
  "PySide6",
  "presidio-analyzer",
  "presidio-anonymizer",
  "spacy",
  "openpyxl",
  "python-docx",
  "python-pptx",
  "lxml",
  "defusedxml",
  "cryptography",
  "keyring",
  "platformdirs",
  "pydantic",
  "charset-normalizer",
]

[project.optional-dependencies]
dev = [
  "pytest",
  "pytest-cov",
  "hypothesis",
  "ruff",
  "mypy",
]
build = [
  "Nuitka",
]
```

Exact versions belong in the release lock file, not permanently in this design document.

---

# 48. Why No pandas in Base MVP

Pandas is useful but not required for the core design.

Avoiding it:

- reduces package size;
- reduces native dependency surface;
- simplifies Nuitka packaging;
- avoids unnecessary DataFrame copies of sensitive data.

Use it later only if a concrete feature justifies it.

---

# 49. Why No PyTorch in Base MVP

PyTorch significantly increases:

- distribution size;
- build complexity;
- startup time;
- architecture-specific dependencies.

Base MVP uses lighter local detection.

An enhanced model can be added after benchmark.

---

# 50. Testing Strategy

Testing is a primary engineering deliverable.

## 50.1 Unit Tests

- token grammar;
- HMAC consistency;
- collision handling;
- crypto encrypt/decrypt;
- tamper rejection;
- normalizers;
- recognizers;
- overlap resolution;
- custom rules;
- retention;
- database migrations.

---

## 50.2 Document Regression Tests

Maintain sanitized synthetic fixtures for:

### XLSX

- visible sheet
- hidden sheet
- veryHidden sheet
- shared strings
- formulas
- comments
- hyperlinks
- chart labels
- metadata

### DOCX

- split runs
- tables
- headers/footers
- comments
- hyperlinks
- text boxes
- metadata

### PPTX

- split runs
- notes
- hidden slides
- grouped shapes
- tables
- chart text
- hyperlinks
- metadata

Fixtures MUST not contain real customer PII.

---

## 50.3 Round-Trip Tests

For reversible mode:

```text
original
  ->
protect
  ->
restore
```

Assertions:

- expected sensitive values restored;
- untouched content unchanged;
- file opens;
- package relationships valid;
- no token remains unless expected.

Byte-identical output is not required because OOXML serialization may change non-semantic details.

Semantic/document integrity is required.

---

## 50.4 Leakage Tests

Test known sensitive values that appear in:

- visible text;
- hidden sheet;
- notes;
- comments;
- metadata;
- split runs.

Protected output must not contain them in covered components.

---

## 50.5 Offline Test

Run a full operation with:

- network unavailable;
- DNS unavailable;
- no model cache outside application resources.

Result must succeed.

---

## 50.6 Packaged Smoke Tests

Test actual installer/build artifact, not only source execution.

Tests:

- start application;
- create project;
- add sample file;
- scan;
- protect;
- close;
- reopen project;
- restore file;
- open Help/About;
- uninstall/cleanup.

---

# 51. CI Pipeline

Recommended GitHub Actions or equivalent.

```text
Pull Request
   ->
lint
   ->
type check
   ->
unit tests
   ->
integration tests
   ->
document regression tests
```

Release tag:

```text
tag vX.Y.Z
   |
   +--> Windows native runner
   |      -> build
   |      -> smoke test
   |      -> sign
   |      -> installer
   |
   +--> macOS arm64 runner
   |      -> build .app
   |      -> test
   |      -> codesign
   |      -> notarize
   |      -> DMG
   |
   +--> macOS x64 runner
   |      -> build/test/sign/notarize
   |
   +--> Linux x64 runner
          -> build
          -> smoke test
          -> AppImage
```

Do not assume a Windows-built executable can be used as the macOS/Linux artifact.

---

# 52. Nuitka Build Strategy

Development sequence:

```text
python source
   ->
Nuitka standalone
   ->
test standalone folder
   ->
create installer
```

Do not debug dependency issues first in one-file mode.

Example conceptual command:

```bash
python -m nuitka \
  --mode=standalone \
  --enable-plugin=pyside6 \
  --include-package-data=sandiraksa \
  src/sandiraksa/__main__.py
```

Actual flags MUST be maintained in build scripts/config and tested per OS.

NLP model/resource directories must be explicitly included.

---

# 53. Windows Distribution

Target MVP:

```text
Windows 10/11 x64
```

Artifact:

```text
SandiRaksa-Setup-x64.exe
```

Installer behavior:

- install under standard user/program location;
- create Start Menu shortcut;
- optional desktop shortcut;
- register uninstall;
- install app resources/models;
- do not require administrator rights unless necessary.

Signing:

- Authenticode/code-signing certificate;
- sign binaries and installer.

Future:

- ARM64 after dependency validation.

---

# 54. macOS Distribution

Targets:

```text
Apple Silicon arm64
Intel x86_64
```

Prefer separate builds unless universal binary testing is proven reliable.

Artifacts:

```text
SandiRaksa-macOS-arm64.dmg
SandiRaksa-macOS-x64.dmg
```

Requirements:

- `.app` bundle;
- Developer ID Application signing;
- hardened runtime as applicable;
- notarization;
- staple notarization ticket where applicable.

Test on clean supported macOS versions.

---

# 55. Linux Distribution

Primary:

```text
x86_64 AppImage
```

Future:

- arm64 AppImage;
- `.deb`;
- Flatpak.

Linux keyring behavior varies. Test:

- GNOME Secret Service;
- KDE-compatible environments;
- minimal/no-keyring environments.

If secure key storage is unavailable, reversible persistence must not silently degrade to plaintext.

---

# 56. Update Strategy

MVP:

- no automatic update polling;
- About screen shows version;
- user can click **Check for Updates** to open configured release page in browser.

Future:

- signed update manifests;
- explicit opt-in;
- no document data transmitted.

This preserves the simplest local-only privacy promise.

---

# 57. Code Signing and Supply Chain

Release process SHOULD:

- sign git tags;
- pin GitHub Action versions by trusted release/SHA where appropriate;
- lock Python dependencies;
- scan dependencies;
- produce SBOM;
- generate SHA-256 checksums;
- sign Windows/macOS artifacts;
- publish third-party notices.

Build secrets must exist only in protected release environments.

---

# 58. License Review

Before commercial/public release, review licenses for:

- PySide6 / Qt;
- Presidio;
- spaCy/model assets;
- openpyxl;
- python-docx;
- python-pptx;
- lxml;
- cryptography;
- Nuitka;
- any bundled NER model.

Model licenses must be reviewed independently from runtime library licenses.

---

# 59. Privacy Report Data Model

Example:

```python
class PrivacyReport(BaseModel):
    operation_id: UUID
    files_scanned: int
    findings_by_type: dict[str, int]
    protected_count: int
    ignored_count: int
    residual_count: int
    component_coverage: list[CoverageItem]
    metadata_status: str
    reversible: bool
    status: str
    warnings: list[str]
```

No raw entity values by default.

---

# 60. Status Model

Use explicit states:

```text
NEW
VALIDATING
SCANNING
REVIEW_REQUIRED
READY_TO_PROTECT
PROTECTING
VALIDATING_OUTPUT
READY
READY_WITH_WARNINGS
FAILED
RESTORING
RESTORED
```

Persist only stable operation states.

---

# 61. Atomic Writes

Never write directly over source.

For outputs:

```text
target.tmp
  ->
write
  ->
fsync where appropriate
  ->
validate
  ->
atomic rename to final target
```

If validation fails:

- remove temp output;
- keep original untouched.

Vault updates should use transactions.

---

# 62. Retention Job

Retention is evaluated:

- when project opens;
- when project closes;
- on application startup;
- via explicit "Clean expired mappings".

No background daemon is required.

Expired mapping:

1. delete encrypted original values;
2. delete corresponding reverse mappings;
3. update project history;
4. mark prior reversible operations as no longer restorable.

---

# 63. Delete Project

Delete flow:

```text
Are you sure?
This project contains reversible mappings.
Deleting them may permanently remove the ability to restore protected files.
```

Require explicit confirmation.

Optional:

- Export non-sensitive privacy report before deletion.

Do not export plaintext mapping by default.

---

# 64. Backup/Export of Project

MVP recommendation:

Do not implement project export/import with mapping unless necessary.

Future secure format:

```text
.projectvault
```

containing encrypted:

- metadata;
- policy;
- history;
- mappings.

Protected with user-supplied passphrase using a strong KDF.

This feature has a high security burden and should not block MVP.

---

# 64.1 Product Branding and Localization Architecture

## Product Identity

Official product name:

```text
SandiRaksa
```

Brand name MUST remain identical in every locale.

Recommended public taglines:

```text
id-ID: SandiRaksa — Lindungi Data Sebelum Berbagi ke AI
en-US: SandiRaksa — Local Privacy Gateway for AI
```

---

## Supported Locales

MVP:

```text
id-ID
en-US
```

Default:

```text
id-ID
```

English is the secondary supported locale.

The user's selected locale is stored in local application settings.

---

## Qt Localization

Use Qt translation infrastructure.

Preferred implementation:

```text
source UI string key
    ->
Qt translation catalog/resource
    ->
localized display string
```

Acceptable mechanisms include:

- `QTranslator`;
- Qt `.ts` source translation files;
- compiled `.qm` translation resources.

Recommended structure:

```text
src/sandiraksa/resources/i18n/
├── sandiraksa_id_ID.ts
├── sandiraksa_id_ID.qm
├── sandiraksa_en_US.ts
└── sandiraksa_en_US.qm
```

English MAY serve as the source language internally, but the first-run/default rendered locale is Bahasa Indonesia.

All user-facing strings MUST use the translation layer.

Do not hard-code Bahasa Indonesia or English strings inside business-logic services.

---

## Stable Internal Identifiers

Internal entity and state identifiers stay English and locale-independent.

Examples:

```text
PERSON
EMAIL
PHONE_NUMBER
FINANCIAL
BUSINESS_CONFIDENTIAL

READY
READY_WITH_WARNINGS
REVIEW_REQUIRED

REVERSIBLE
NON_REVERSIBLE
```

Localization maps internal IDs to display labels.

Never persist translated display labels as database enum/state identifiers.

This prevents project databases from changing semantics when the user switches UI language.

---

## Recommended Bahasa Indonesia UI Labels

```text
Projects                    -> Proyek
New Project                 -> Proyek Baru
Add Files                   -> Tambah File
Project Settings            -> Pengaturan Proyek
Protection Profile          -> Profil Perlindungan
Reversible Protection       -> Perlindungan Reversibel
Scan & Review               -> Pindai & Tinjau
Protect Files               -> Lindungi File
Restore Protected Data      -> Pulihkan Data Terlindungi
Personal Data               -> Data Pribadi
Financial Data              -> Data Finansial
Business Confidential       -> Rahasia Bisnis
Custom Confidential         -> Rahasia Khusus
Settings                    -> Pengaturan
Help                        -> Bantuan
Documentation               -> Dokumentasi
Contact Support             -> Hubungi Kami
About                       -> Tentang SandiRaksa
Donate                      -> Dukung Pengembangan
```

Terms such as the following MAY remain unchanged where clearer:

```text
NIK
NPWP
Email
URL
IP Address
AI
CSV
Excel
Word
PowerPoint
EBITDA
```

---

## Reversible Protection UI Copy

Primary Indonesian term:

```text
Perlindungan Reversibel
```

Recommended explanatory text:

```text
Data sensitif diganti dengan kode sementara dan dapat
dikembalikan ke nilai asli menggunakan pemetaan terenkripsi
yang disimpan secara lokal.
```

When disabled:

```text
Data yang telah dilindungi tidak dapat dikembalikan
secara otomatis ke nilai asli.
```

Do not present the feature as "reversible anonymization" in the main UI.

---

## Help Content

Offline Help MUST have separate locale resources:

```text
resources/help/id-ID/
resources/help/en-US/
```

Example:

```text
resources/help/
├── id-ID/
│   ├── getting-started.md
│   ├── projects.md
│   ├── protection.md
│   ├── reversible.md
│   ├── restore.md
│   ├── supported-files.md
│   ├── limitations.md
│   └── troubleshooting.md
└── en-US/
    └── ...
```

---

## About / Support / Donation

About dialog title:

```text
Tentang SandiRaksa
```

English:

```text
About SandiRaksa
```

Recommended Indonesian support action:

```text
Dukung Pengembangan
```

The configured external URL can still point to any approved donation/sponsorship platform.

No project, file, PII, token, or diagnostic content may be appended to external links.

---

# 65. UI Architecture

Use a single `QMainWindow` with routed stacked pages.

Suggested navigation:

```text
Projects
Project
Review
Results
Restore
```

Global menu:

```text
File
Settings
Help
```

Help menu:

```text
Help
Documentation
Contact Support
About
Donate
```

Do not expose developer-centric terminology on primary screens.

---

# 66. Project Screen UX

Primary information:

```text
Project Name
Privacy Profile
Reversible Protection: ON/OFF
File list
Latest scan status
```

Primary buttons:

```text
Add Files
Scan & Review
Restore Returned Files
Project Settings
```

Avoid adding too many settings to the main screen.

---

# 67. Review UX

Recommended three-pane/table design:

```text
Filters
  |
  +-- category
  +-- file
  +-- confidence
  +-- status

Findings table:
Type | File | Location | Confidence | Action

Preview:
context + explanation
```

Bulk actions:

- protect all high-confidence;
- allow selected;
- change treatment;
- apply same-value project rule.

---

# 68. Help/About Security

"Copy Diagnostic Information" example:

Allowed:

```text
Product version
Build number
OS version
Architecture
Python runtime embedded version
Database schema version
NLP engine version
```

Excluded by default:

```text
Project names
File names
Paths
PII
Tokens
Custom terms
Document excerpts
Vault details
Encryption keys
```

---

# 69. Product Configuration

Use typed Pydantic config.

Sources:

1. bundled defaults;
2. product metadata;
3. local user settings;
4. project settings.

Do not allow environment variables to silently enable remote processing in production.

---

# 70. Settings

User settings MAY include:

- default output folder;
- default reversible mode;
- default privacy profile;
- retention default;
- UI language;
- theme;
- remember window layout;
- diagnostic logging level.

Do not include "send analytics" in MVP.

---

# 71. Localization

Architecture should permit:

```text
English
Bahasa Indonesia
```

Use Qt translation infrastructure or external resource dictionaries.

Entity type display names must be translated separately from internal IDs.

Internal IDs remain stable English-like constants.

---

# 71.1 Large File / Large Workbook Processing Architecture

SandiRaksa must support workbooks whose logical content is much larger than the compressed `.xlsx` file size.

Example:

```text
50 MB XLSX on disk
may represent
hundreds of MB or more of XML/text when expanded.
```

Therefore, all resource planning must use logical working-set estimates, not compressed file size alone.

---

## 71.1.1 Processing Model

Use a staged pipeline:

```text
Validate Package
    ->
Inventory Workbook
    ->
Estimate Workload
    ->
Choose Resource Plan
    ->
Stream / Iterate Worksheet Content
    ->
Build Detection Batches
    ->
Run Detection
    ->
Persist Minimal Finding Metadata
    ->
Release Batch Memory
    ->
User Review
    ->
Re-open / Mutable Treatment Pass
    ->
Write Protected Output
    ->
Re-open Output
    ->
Leakage Re-Scan
```

Scanning and mutation are intentionally separate.

---

## 71.1.2 Workload Estimator

Before a full scan, estimate:

- compressed file size;
- ZIP expanded-size total;
- worksheet count;
- shared string count;
- approximate used ranges;
- populated cell estimates;
- comment count;
- hyperlink count;
- chart count;
- hidden/very-hidden sheet count;
- formula count where cheaply discoverable.

Create:

```python
class WorkloadEstimate(BaseModel):
    file_size_bytes: int
    expanded_size_bytes: int | None
    worksheet_count: int
    estimated_populated_cells: int | None
    estimated_text_cells: int | None
    size_class: str
    recommended_batch_size: int
    recommended_file_concurrency: int
    requires_high_memory_fallback: bool
```

The estimator must be cheap relative to a full scan.

---

## 71.1.3 Large Workbook Size Classes

Initial scheduling classes:

```text
SMALL
<= 10 MB and <= 50k populated cells

MEDIUM
10–50 MB or 50k–500k populated cells

LARGE
50–200 MB or 500k–2M populated cells

VERY_LARGE
> 200 MB or > 2M populated cells
```

These are tuning defaults, not semantic limits.

---

## 71.1.4 XLSX Scan Mode

For the detection pass:

```python
openpyxl.load_workbook(
    path,
    read_only=True,
    data_only=False,
    keep_links=True,
)
```

or equivalent safe iterative access SHOULD be used when compatible with required coverage.

Important:

- `read_only=True` is for scanning/iteration, not final mutation.
- formula text should be preserved for analysis where relevant;
- no formulas are evaluated;
- external links are not followed.

If a required workbook component is not visible through the read-only high-level API, inspect its OOXML part separately.

---

## 71.1.5 Bounded Detection Batches

Never send one cell at a time through the full NLP stack if batching is possible.

Use:

```python
class DetectionBatch(BaseModel):
    batch_id: UUID
    segments: list[TextSegment]
    total_chars: int
```

Batch termination triggers SHOULD include:

```text
max segment count
max character count
max estimated memory
worksheet boundary when beneficial
cancellation request
```

Initial benchmark candidates:

```text
500–5,000 logical cells
or
250–2,000 text segments
or
~0.5–2 MB logical text per NLP batch
```

Actual defaults are benchmark-derived.

---

## 71.1.6 Cell-to-Segment Strategy

Do not concatenate an entire worksheet into one giant string.

Preferred:

```text
worksheet
  ->
row iterator
  ->
cell text
  ->
logical segments
  ->
bounded detection batch
```

Each segment maintains:

```text
sheet ID
cell coordinate
component type
offset mapping
```

This permits review and treatment without retaining entire-sheet plaintext.

---

## 71.1.7 Finding Persistence

After each batch:

1. convert raw detector output to `Finding`;
2. persist only required metadata;
3. if reversible treatment is not yet approved, do not persist plaintext unless necessary;
4. keep short-lived preview/context only in encrypted/transient review storage if needed;
5. release batch plaintext.

Do not maintain a global list containing all raw workbook cell strings.

---

## 71.1.8 Large Workbook Treatment Pass

The treatment pass may require a mutable workbook representation.

Options, in priority order:

### Option A — High-Level Mutable Workbook

Use normal `openpyxl` load when memory estimate is acceptable and feature preservation is validated.

### Option B — Targeted OOXML Mutation

For very large or feature-sensitive workbooks:

```text
original XLSX ZIP
   ->
copy untouched parts
   ->
modify only affected XML/string parts
   ->
rebuild ZIP package
```

This is technically more complex but can reduce memory and preserve unsupported workbook features.

The development team should not implement Option B prematurely for every workbook; introduce it when benchmarks or preservation tests justify it.

---

## 71.1.9 Shared Strings

Large XLSX files may use a shared string table.

The architecture must support:

- scanning shared-string-backed cells;
- mapping cell references to string indices;
- modifying shared strings carefully;
- avoiding an edit that unintentionally changes multiple cells when only one occurrence should be protected.

If one shared string is referenced by multiple cells but treatment decisions differ, the writer MUST create distinct string entries or use an equivalent safe representation.

This is a critical XLSX correctness case.

---

## 71.1.10 Resource-Aware Scheduler

Introduce:

```python
class ResourceScheduler:
    def plan(self, workloads: list[WorkloadEstimate]) -> WorkerPlan:
        ...
```

The scheduler considers:

- logical workload size;
- available RAM;
- CPU count;
- active NLP model;
- current worker load;
- number of large files.

Rules:

```text
Large/Very Large workbook:
    max concurrent file workers = 1 by default

Medium:
    limited concurrency

Small:
    may run concurrently within global limits
```

Do not derive concurrency from CPU count alone.

---

## 71.1.11 Memory Pressure Handling

The application SHOULD monitor process memory using a lightweight mechanism.

A dependency such as `psutil` MAY be added if cross-platform memory monitoring proves necessary.

If used, add it to the runtime dependency list and release lock file.

Resource response:

```text
memory warning
    ->
reduce future batch size
    ->
pause scheduling new files
    ->
allow current safe batch to complete
    ->
if still unsafe:
        cancel operation cleanly
```

Never kill the process abruptly as the normal resource-control strategy.

---

## 71.1.12 Progress Model

Progress events:

```python
class ProgressEvent(BaseModel):
    operation_id: UUID
    file_id: UUID
    phase: str
    component: str | None
    current: int | None
    total: int | None
    message_key: str
```

Example:

```text
Memindai model.xlsx
Sheet 7 dari 24
42,500 dari 120,000 baris
```

If exact total rows are expensive to calculate, use:

- worksheet progress;
- batches completed;
- indeterminate progress for unknown totals.

Do not perform a full expensive pre-scan only to calculate an exact progress percentage.

---

## 71.1.13 Cancellation

Cancellation token is checked:

- between worksheets;
- between row batches;
- before/after NLP batches;
- before output write;
- between re-scan batches.

Cancellation behavior:

```text
stop accepting new batches
wait for current atomic step
rollback DB transaction
clean temp output
mark operation CANCELLED
```

Vault mappings created only for a cancelled, uncommitted operation SHOULD be rolled back where possible.

---

## 71.1.14 Temporary Disk Use

Large OOXML manipulation may use temp disk to reduce RAM.

Permitted:

- app-owned temp ZIP copies;
- transformed XML parts;
- batch work files when strictly necessary.

Requirements:

- randomized filenames;
- user-specific temp directory;
- no sensitive plaintext in filenames;
- encrypted temp content when feasible;
- immediate cleanup after commit/failure;
- startup cleanup for verified stale app temp directories.

The application should prefer bounded disk usage over unbounded memory usage.

---

## 71.1.15 Multi-File Project Processing

A project may contain:

```text
20 XLSX files
10 DOCX files
5 PPTX files
```

Do not start all workers immediately.

Queue:

```text
Pending
  ->
Scheduler
  ->
Active workers
  ->
Completed / Failed / Cancelled
```

Token mapping remains project-consistent because all mapping writes go through the project `TokenVault` repository with transactional uniqueness constraints.

---

## 71.1.16 Large-File Error States

Add resource-specific codes:

```text
RESOURCE_MEMORY_LIMIT
RESOURCE_TEMP_DISK_LIMIT
WORKBOOK_TOO_LARGE_FOR_MUTABLE_MODE
WORKBOOK_REQUIRES_FALLBACK
WORKBOOK_UNSUPPORTED_FEATURE_AT_SCALE
OPERATION_CANCELLED
```

The UI must explain recovery options, for example:

```text
This workbook is too large for the current processing mode.
SandiRaksa can retry using a lower-memory mode.
```

where such a mode is implemented.

---

## 71.1.17 Benchmark Harness

Add:

```text
tests/performance/
```

Suggested structure:

```text
tests/performance/
├── generate_workbooks.py
├── benchmark_scan.py
├── benchmark_protect.py
├── benchmark_restore.py
├── benchmark_memory.py
└── baselines/
```

The benchmark generator should create synthetic files, not store large real confidential documents in the repository.

Collect:

```text
wall-clock duration
CPU time
peak RSS
temporary disk bytes
input size
expanded ZIP size
worksheet count
populated cells
findings count
output size
validation result
```

Store release baselines as JSON/CSV artifacts.

---

## 71.1.18 Performance Regression Gate

CI does not need to run the largest benchmark on every pull request.

Recommended:

```text
PR:
- small/medium performance smoke

Nightly:
- medium/large benchmark

Release candidate:
- complete performance corpus
```

Release gate examples:

- no >25% unexplained scan-time regression on baseline hardware;
- no >25% unexplained peak-memory regression;
- no document-integrity regression;
- no increase in missed covered entities due to optimization.

Thresholds must be calibrated after baseline measurements.

---

# 72. Performance Architecture

Performance priorities for large structured documents:

1. bounded memory;
2. UI responsiveness;
3. deterministic correctness;
4. document integrity;
5. privacy coverage;
6. throughput.

The implementation MUST NOT trade detection coverage or document integrity for speed without explicitly reporting reduced coverage.


Optimization order:

1. correctness;
2. file integrity;
3. privacy coverage;
4. memory;
5. speed.

Potential optimizations:

- batch Presidio analysis;
- segment-level caching within one scan;
- stream CSV;
- lazy model load;
- skip untouched XML parts;
- multiprocessing for large independent files.

Do not cache raw extracted text on disk.

---

# 73. Cancellation

Long operations support cancel.

On cancel:

- stop new processing;
- clean temporary output;
- roll back incomplete vault transaction;
- mark operation `CANCELLED`;
- preserve original file.

---

# 74. Crash Recovery

At startup:

- detect operations left `PROCESSING`;
- mark `INTERRUPTED`;
- clean app-owned temp workspace;
- validate database;
- do not assume partial output is safe.

User may retry operation.

---

# 75. Database Migrations

Migration naming:

```text
001_initial.sql
002_add_retention.sql
003_encrypt_filename.sql
```

Rules:

- backup database before destructive migration;
- migrations idempotent where practical;
- migration tests from all supported historical schemas.

---

# 76. Security Testing

Required:

- AES-GCM tamper tests;
- wrong-key tests;
- keyring failure tests;
- ZIP path traversal tests;
- ZIP bomb limit tests;
- XXE/XML entity tests;
- malformed OOXML tests;
- malicious token syntax tests;
- log redaction tests;
- temp cleanup tests;
- offline/no-network tests.

---

# 77. False-Negative Management

A privacy tool must explicitly manage detection misses.

Design controls:

- privacy profiles;
- custom terms;
- exact-value detection;
- hidden-component scanning;
- final leakage re-scan;
- residual warnings;
- manual review;
- coverage report.

UI language:

Avoid:

```text
100% safe
All sensitive data removed
```

Prefer:

```text
No additional sensitive items were detected under the selected policy.
Review is recommended before sharing externally.
```

---

# 78. Model Evaluation Dataset

Maintain synthetic/internal benchmark data with:

- Indonesian names;
- international names;
- emails;
- phone numbers;
- Indonesian identifiers;
- addresses;
- companies;
- business codenames;
- financial amounts;
- ambiguous negatives.

Do not use real customer PII without a lawful, controlled data-governance process.

Track:

```text
precision
recall
F1
per-entity metrics
```

For privacy risk, false negatives need special attention.

---

# 79. Quasi-Identifier Strategy

MVP:

- detect obvious quasi-identifiers;
- warn when profile enables risk analysis;
- do not claim statistical anonymization.

Future:

- k-anonymity-style analysis for structured datasets;
- generalization recommendations;
- linkage-risk scoring.

This is a separate capability from token replacement.

---

# 80. API Boundaries for Future Evolution

Even though the product is standalone, use service interfaces.

Examples:

```python
class ProjectRepository(Protocol): ...
class DetectionService(Protocol): ...
class DocumentHandler(Protocol): ...
class TokenVault(Protocol): ...
class ProtectionService(Protocol): ...
class RestoreService(Protocol): ...
```

This permits future:

- CLI;
- enterprise desktop;
- local REST service;
- plugin model;
- managed on-prem server

without rewriting domain logic.

---

# 81. Proposed Initial Implementation Order

## Sprint Group 1 — Foundations

- repository;
- config;
- SQLite/migrations;
- project CRUD;
- crypto/keyring;
- token generation;
- basic CLI harness.

## Sprint Group 2 — CSV End-to-End

- CSV parser;
- recognizers;
- reversible protect;
- irreversible protect;
- restore;
- leakage re-scan;
- history.

## Sprint Group 3 — GUI

- Projects;
- New Project;
- Add Files;
- Scan Progress;
- Review;
- Result;
- Restore;
- Settings.

## Sprint Group 4 — XLSX

- workbook inventory;
- hidden sheets;
- cell treatment;
- comments;
- metadata;
- regression suite.

## Sprint Group 5 — DOCX

- paragraph reconstruction;
- runs;
- tables;
- headers/footers;
- comments;
- OOXML fallback.

## Sprint Group 6 — PPTX

- slides;
- hidden slides;
- text frames;
- notes;
- tables;
- OOXML fallback.

## Sprint Group 7 — Productization

- Help;
- About;
- contact;
- donation;
- license notices;
- installers;
- signing;
- release CI.

---

# 82. MVP Technical Exit Criteria

The development team may call the system MVP-complete only when:

1. It works on a clean supported OS without Python installed.
2. Multi-project persistence works.
3. Reversible mode defaults ON.
4. Reversible mapping survives app restart.
5. Existing project mappings are reused for later files.
6. Non-reversible mode stores no original mapping.
7. CSV/XLSX/DOCX/PPTX pass regression corpus.
8. Hidden/metadata coverage is reported.
9. Protected outputs are re-scanned.
10. Restore validates strict token integrity.
11. Unknown tokens do not trigger unsafe restoration.
12. No raw PII appears in logs.
13. Full workflow works offline.
14. Installer smoke tests pass.
15. Windows/macOS releases are signed/notarized as required for production.
16. Help/About/contact/donation UI is complete.
17. Third-party licenses are included.
18. The large-workbook performance corpus passes defined release gates.
19. Large XLSX processing remains responsive and cancellable.
20. Multiple large files are processed with bounded concurrency.
21. Peak memory and temporary disk usage are captured in release benchmarks.

---

# 83. Recommended Python Libraries

## Runtime

```text
PySide6
presidio-analyzer
presidio-anonymizer
spacy
openpyxl
python-docx
python-pptx
lxml
defusedxml
cryptography
keyring
platformdirs
pydantic
charset-normalizer
psutil (optional, if resource monitoring is enabled)
```

## Standard Library

```text
sqlite3
csv
zipfile
pathlib
hashlib
hmac
secrets
uuid
json
logging
tempfile
concurrent.futures
multiprocessing
tomllib
```

## Development

```text
pytest
pytest-cov
hypothesis
ruff
mypy or pyright
```

## Build

```text
Nuitka
```

Optional release tooling may include OS-specific signing/installer utilities.

---

# 84. Distribution Matrix

| OS | Arch | MVP | Artifact |
|---|---:|---:|---|
| Windows | x86_64 | Required | Signed `.exe` installer |
| Windows | arm64 | Future/optional | Installer |
| macOS | arm64 | Required | Signed/notarized `.dmg` |
| macOS | x86_64 | Required if Intel supported | Signed/notarized `.dmg` |
| Linux | x86_64 | Required | AppImage |
| Linux | arm64 | Future/optional | AppImage |

Minimum OS versions must be decided after dependency compatibility testing.

---

# 85. Why This Architecture

The competitive engineering challenge is not the GUI.

The critical challenges are:

```text
document coverage
+ false-negative control
+ structured round-trip editing
+ secure reversible mapping
+ project-level referential integrity
+ restoration correctness
+ honest residual-risk reporting
```

Therefore, architecture effort should be concentrated on parsers, test corpora, detection quality, and vault security rather than cosmetic complexity.

---

# 86. Official References

Presidio Analyzer:  
https://presidio.dataprivacystack.org/analyzer/

Presidio Anonymizer:  
https://presidio.dataprivacystack.org/anonymizer/

Qt for Python / PySide6:  
https://doc.qt.io/qtforpython-6/

Qt/PySide deployment:  
https://doc.qt.io/qtforpython-6/deployment/

Nuitka User Manual:  
https://nuitka.net/user-documentation/user-manual.html

Nuitka Use Cases:  
https://nuitka.net/user-documentation/use-cases.html

openpyxl:  
https://openpyxl.readthedocs.io/

python-docx:  
https://python-docx.readthedocs.io/

python-pptx:  
https://python-pptx.readthedocs.io/

cryptography:  
https://cryptography.io/

---

# 87. Final Technical Principle

The implementation must preserve the following invariant:

> **No protected output is considered ready merely because replacement ran successfully. It is ready only after the generated document is structurally validated, re-scanned under the selected policy, and any residual risk is reported to the user.**

That invariant should guide implementation decisions across every supported document format.