# Product Requirements Document (PRD)
## SandiRaksa — Local Privacy Gateway for AI

**Document:** `requirements.md`  
**Status:** Draft for Development  
**Target Release:** MVP / v1  
**Primary Platforms:** Windows, macOS, Linux  
**Application Type:** Standalone desktop application  
**Processing Model:** Local-only; no public AI/API required  
**Primary Use Case:** Protect sensitive information before documents are sent to public AI systems, with optional reversible pseudonymization/tokenization and local restoration afterward.

---

## 1. Product Summary

The product is a standalone desktop privacy tool that allows users to:

1. Create and manage multiple privacy projects.
2. Add one or more files to a project.
3. Scan files locally for Personally Identifiable Information (PII) and other sensitive/confidential information.
4. Add user-defined confidential terms and protection rules.
5. Review detected sensitive data before treatment.
6. Produce protected copies of the files suitable for use with public AI tools.
7. Optionally preserve a local encrypted mapping so protected values can be restored later.
8. Import files returned by an external AI system and restore protected values locally.
9. Keep project metadata, treatment history, policies, file records, and mapping history locally.
10. Re-open a project later and add more files while maintaining project-level consistency.

The application itself MUST NOT upload documents or document contents to any public AI, cloud PII service, analytics provider, or remote processing service.

---

## 2. Product Positioning

Recommended positioning:

> **Local Privacy Gateway for Public AI**

The application protects documents locally before users share them with services such as public AI assistants.

The product SHOULD avoid claiming that reversible treatment creates "true anonymization."

Terminology:

- **De-identification:** umbrella term for reducing the ability to identify a person or confidential entity.
- **Pseudonymization / Tokenization:** replacement of sensitive values with tokens while preserving a mapping that can restore the original values.
- **Irreversible protection:** redaction, masking, generalization, non-reversible replacement, or other treatment without a restoration mapping.
- **PII:** information that directly or indirectly identifies a person.
- **Sensitive business information:** confidential information that may not be PII, such as client names, project codenames, transaction values, pricing, margin, M&A targets, internal product names, or supplier information.
- **Quasi-identifier:** an attribute that may not identify someone alone but can contribute to re-identification when combined with other attributes.

The UI MAY use a simple user-facing phrase such as **Protect sensitive data**, while technical logs and documentation SHOULD use the more precise terms above.

---

## 3. Product Goals

### 3.1 Primary Goals

The MVP MUST:

- Work without requiring Python, Microsoft Office, or a local AI server to be installed by the end user.
- Process supported documents locally.
- Support multiple saved projects.
- Allow projects to be closed and reopened.
- Allow new files to be added to existing projects.
- Detect common PII.
- Detect user-defined confidential data.
- Support project-level protection policies.
- Preserve referential consistency within a project where appropriate.
- Support reversible protection by default.
- Allow reversible protection to be disabled.
- Store reversible mappings securely and locally.
- Never store raw document contents in logs.
- Provide a review stage before protected output is generated.
- Re-scan protected output before export.
- Validate restoration before producing restored output.
- Provide simple Help and About screens.
- Provide configurable support/contact and donation links.
- Be distributable as a standalone application on Windows, macOS, and Linux.

### 3.2 Secondary Goals

The MVP SHOULD:

- Work well with both English and Indonesian documents.
- Support Indonesian-specific identifiers.
- Minimize formatting/layout changes.
- Preserve document structure and non-sensitive content.
- Explain why an item was detected.
- Support reusable Privacy Profiles.
- Provide a clear local-processing/privacy status to the user.
- Provide operation audit/history without retaining unnecessary raw data.
- Provide deterministic project-level tokens.

---

## 4. Explicit Non-Goals for MVP

The MVP WILL NOT:

- Send files to public AI services.
- Include a ChatGPT/Claude/Gemini API integration.
- Automatically submit protected files to any external AI.
- Restore data if reversible mode was disabled for the relevant operation.
- Guarantee that all possible sensitive data is detected.
- Claim regulatory compliance solely because the tool is used.
- Provide OCR for images or scanned PDFs.
- Process legacy binary Office formats `.doc`, `.xls`, or `.ppt`.
- Fully support arbitrary PDF round-trip editing.
- Inspect sensitive text embedded inside raster images.
- Perform aggressive fuzzy restoration when tokens are modified.
- Keep a global identity mapping across all projects.
- Store original source files inside the project database by default.
- Perform background telemetry or automatic document-content crash reporting.

---

## 5. Supported File Formats

### 5.1 MVP

Required:

- `.csv`
- `.xlsx`
- `.docx`
- `.pptx`
- `.txt` (recommended low-cost addition)

Optional if implementation is low risk:

- `.xlsm` with strict preservation rules and tests; macros MUST NOT be executed.

### 5.2 Future

Potential future support:

- PDF
- scanned PDF
- images with OCR
- `.doc`
- `.xls`
- `.ppt`
- OpenDocument formats
- email formats
- ZIP/container batch processing

Unsupported files MUST be rejected safely with a clear explanation.

---

## 6. Core User Model

The application is organized around **Projects**.

A project is the boundary for:

- project metadata;
- protection policy;
- privacy profile;
- custom confidential terms;
- file history;
- operation history;
- token namespace;
- reversible mapping vault;
- non-reversible deterministic pseudonym key;
- retention settings.

Mappings MUST NOT be shared between projects by default.

Example:

```text
Project: Acquisition Garuda
├── Project metadata
├── Protection policy
├── Custom confidential terms
├── Files
│   ├── management.pptx
│   ├── model.xlsx
│   └── diligence.docx
├── Operation history
└── Encrypted token vault
```

---

## 6.1 Product Branding and Language

### Product Name

The official product name is:

```text
SandiRaksa
```

The product name MUST NOT be translated.

Recommended public-facing taglines:

**Bahasa Indonesia**

> SandiRaksa — Lindungi Data Sebelum Berbagi ke AI

**English**

> SandiRaksa — Local Privacy Gateway for AI

### Default UI Language

The default application interface MUST be **Bahasa Indonesia**.

English MUST be available as the second supported UI language.

Users MUST be able to change language through:

```text
Pengaturan -> Bahasa
```

or in English:

```text
Settings -> Language
```

The selected language MUST be persisted locally.

### Localization Architecture

All user-facing strings MUST come from localization/translation resources.

User-facing strings MUST NOT be hard-coded throughout application logic.

The initial supported locales are:

```text
id-ID
en-US
```

The architecture SHOULD allow additional locales in future releases without changing core business logic.

### Internal Technical Language

The following MUST remain English internally:

- source code;
- class/function/module names;
- database table/column names;
- internal entity identifiers;
- structured log field names;
- technical documentation;
- build configuration;
- automated test identifiers.

Examples:

```text
PERSON
EMAIL
PHONE_NUMBER
REVERSIBLE
PROJECT_ID
BUSINESS_CONFIDENTIAL
```

The UI localization layer maps these stable internal identifiers to user-facing labels.

### User-Facing Terminology

Preferred Bahasa Indonesia labels:

| Internal / English | Bahasa Indonesia UI |
|---|---|
| Project | Proyek |
| New Project | Proyek Baru |
| Add Files | Tambah File |
| Settings | Pengaturan |
| Help | Bantuan |
| About | Tentang SandiRaksa |
| Contact Support | Hubungi Kami |
| Documentation | Dokumentasi |
| Donate | Dukung Pengembangan |
| Protection Profile | Profil Perlindungan |
| Reversible Protection | Perlindungan Reversibel |
| Personal Data | Data Pribadi |
| Financial Data | Data Finansial |
| Business Confidential | Rahasia Bisnis |
| Custom Confidential | Rahasia Khusus |
| Scan & Review | Pindai & Tinjau |
| Protect Files | Lindungi File |
| Restore Protected Data | Pulihkan Data Terlindungi |
| Ready | Siap |
| Ready with warnings | Siap dengan peringatan |
| Review required | Perlu ditinjau |

Do not force translations for commonly understood technical terms when the translation would reduce clarity.

Examples that MAY remain unchanged:

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

### Reversible Protection Wording

The primary UI MUST use:

```text
Perlindungan Reversibel
```

instead of technical phrases such as:

```text
Reversible Anonymization
```

Suggested help text:

> Data sensitif diganti dengan kode sementara dan dapat dikembalikan ke nilai asli menggunakan pemetaan terenkripsi yang disimpan secara lokal.

When disabled, the UI MUST clearly explain:

> Data yang telah dilindungi tidak dapat dikembalikan secara otomatis ke nilai asli.

### Help and About Localization

Help content MUST be available offline in:

- Bahasa Indonesia;
- English.

The About screen MUST show the name:

```text
SandiRaksa
```

and MUST NOT translate or alter the brand name.

The donation/support action SHOULD use the more professional user-facing label:

```text
Dukung Pengembangan
```

with an optional secondary explanation that contributions/donations support continued SandiRaksa development.

---

## 7. Functional Requirements

### FR-001 — Project List

The application MUST show a home/project screen containing:

- project name;
- optional description;
- date created;
- last opened/updated date;
- number of files;
- reversible protection status/default;
- privacy profile;
- project status.

User actions:

- Create Project
- Open Project
- Rename Project
- Duplicate Project Settings (without mapping unless explicitly requested)
- Archive Project
- Delete Project
- Export project settings (no raw mapping by default)

Deleting a project containing reversible mapping MUST show a clear warning that restoration capability may be lost.

---

### FR-002 — Create Project

Required fields:

- Project name

Optional fields:

- Description
- Privacy Profile
- Reversible Protection: default **ON**
- Mapping retention policy
- Remember source file locations: default **OFF**
- Default output folder
- Custom confidential terms
- Protection categories

Project IDs MUST be generated internally and MUST NOT depend on the project name.

---

### FR-003 — Reopen Existing Project

A user MUST be able to close the application and later reopen a project.

Upon reopen, the application MUST restore:

- project settings;
- privacy profile;
- custom rules;
- file history;
- operation history;
- token namespace;
- encrypted reversible mapping, if enabled;
- project-level consistency state.

The application MUST NOT require original files to reopen a project.

---

### FR-004 — Add Files to Existing Project

Users MUST be able to add new files at any time.

When files are added later:

- existing project rules MUST apply;
- existing reversible tokens SHOULD be reused for the same detected value;
- non-reversible deterministic project tokens SHOULD be stable when that treatment mode is selected;
- new mappings MUST be added to the project vault;
- previous output files MUST not be modified automatically.

---

### FR-005 — File Import

Input methods:

- Drag and drop
- File picker
- Multi-file selection
- Add Files from within an existing project

The import screen MUST display:

- filename;
- format;
- size;
- file status;
- validation result.

The application MUST NOT modify original input files in place.

---

### FR-006 — File Safety Validation

Before processing, the application MUST:

- validate extension and actual container structure;
- reject malformed/unsupported files;
- enforce configurable maximum file size;
- protect XML parsing against unsafe entity expansion/resource attacks;
- never execute macros, scripts, embedded binaries, or external links;
- treat input files as untrusted content.

---

### FR-007 — Sensitive Data Detection

The detection engine MUST support at least:

#### Personal Data

- PERSON
- EMAIL
- PHONE_NUMBER
- ADDRESS
- DATE_OF_BIRTH
- LOCATION
- URL where considered sensitive
- IP_ADDRESS

#### Indonesian Identifiers

Implementation SHALL provide custom recognizers for Indonesian patterns where feasible:

- NIK
- NPWP
- No. KK
- BPJS number candidates
- passport number candidates
- phone/mobile numbers
- Indonesian postal/address context

Pattern-only identifiers MUST use contextual validation where possible to reduce false positives.

#### Financial / Account Data

- CREDIT_CARD
- BANK_ACCOUNT candidate
- IBAN where applicable
- account/customer/employee identifiers where configured
- compensation/salary patterns
- transaction values when policy enables them

#### Business Confidential

- organization/client names;
- supplier names;
- project codenames;
- product codenames;
- pricing;
- margin;
- revenue;
- valuation;
- EBITDA/financial metrics;
- transaction values;
- internal IDs;
- custom keywords/phrases.

Not every category can be recognized reliably without user rules. The UI MUST communicate uncertainty.

---

### FR-008 — Detection Methods

Detection SHOULD combine:

1. Exact match / deny-list.
2. Regular expression recognizers.
3. Checksum or structural validation where available.
4. Context-sensitive rules.
5. Named Entity Recognition (NER) using local-only models.
6. Project custom confidential terms.
7. Privacy-profile-specific rules.
8. File-format metadata inspection.

No remote recognizer may be enabled in the production desktop build.

---

### FR-009 — Detection Confidence

Each detection MUST include:

- entity type;
- source file;
- source location;
- confidence score or detection class;
- detection method;
- preview/context with minimal necessary surrounding content;
- treatment status.

Suggested UI bands:

- Critical / Exact
- High
- Medium
- Low

Confidence values MUST NOT be presented as a guarantee of safety.

---

### FR-010 — Explain Detection

For a selected detection, the UI SHOULD show a user-friendly explanation.

Example:

```text
Detected: 0812-3456-7890
Type: PHONE_NUMBER
Confidence: High

Why:
- Matches Indonesian mobile-number pattern
- Appears near "Tel:"
- Length is valid
```

Raw sensitive data MUST only be displayed when necessary for the local review screen.

---

### FR-011 — User Review

Before treatment, the user MUST be able to:

- Protect
- Ignore / Allow
- Change entity type
- Change treatment
- Apply decision to identical values
- Apply rule to current file
- Apply rule to current project

The UI SHOULD support bulk actions by entity type.

---

### FR-012 — Custom Confidential Data

User MUST be able to define confidential values/patterns.

Examples:

- client names;
- project names;
- internal codenames;
- supplier names;
- employee IDs;
- transaction names;
- technology/product names.

Required controls:

- Add exact value
- Add case-insensitive exact value
- Add phrase
- Optional regex for advanced users
- Entity/category label
- Default treatment
- Allow-list exceptions

Natural-language policy input is a future enhancement, not an MVP dependency.

---

### FR-013 — Privacy Profiles

Built-in profiles SHOULD include:

- Standard PII
- HR Confidential
- Customer Data
- Legal Documents
- M&A / Due Diligence
- Banking / Financial
- Custom

A profile defines:

- enabled entity categories;
- default confidence thresholds;
- default treatments;
- metadata cleanup rules;
- file component coverage requirements;
- review strictness.

Users MUST be able to create project-specific custom profiles.

---

### FR-014 — Reversible Protection

Reversible protection MUST be **ON by default** for new projects.

The user MUST be able to disable it:

- at project creation;
- in project settings for future operations;
- optionally per export/treatment operation.

When reversible protection is ON:

- sensitive values are replaced with stable project-scoped tokens;
- original values are stored only in an encrypted local mapping;
- restoration is possible when tokens remain intact.

Example token syntax:

```text
[[PERSON_7F31A2]]
[[ORG_91DC44]]
[[EMAIL_C83719]]
[[ACCOUNT_E1820]]
[[CONFIDENTIAL_117A3F]]
```

Tokens SHOULD:

- be visually distinguishable;
- be unlikely to occur naturally;
- include category;
- use non-sequential opaque IDs;
- remain stable for the same entity within a project;
- avoid embedding the original value.

---

### FR-015 — Non-Reversible Protection

When reversible protection is OFF:

- the application MUST NOT persist original values for restoration;
- the UI MUST clearly state that restoration will not be possible;
- the Restore feature MUST not be offered for that operation.

Available non-reversible treatments MAY include:

- Redact: `[REDACTED]`
- Category replace: `[PERSON]`
- Partial mask
- Generalize
- Project-scoped deterministic pseudonym token generated without storing original plaintext mapping

The product MUST NOT imply that non-reversible replacement automatically guarantees formal anonymization.

---

### FR-016 — Treatment Selection

Supported treatment methods:

- reversible tokenization;
- category replacement;
- redaction;
- partial masking;
- generalization where rules exist;
- deterministic pseudonymization;
- keep/allow.

Default for reversible mode:

- tokenization.

Default for irreversible mode:

- category replacement or redaction, depending on profile.

---

### FR-017 — Referential Consistency

Within a project:

```text
John Smith
```

SHOULD map to the same project token every time when the same entity value and category are identified.

Consistency MUST apply across:

- multiple files;
- files added later;
- repeated processing operations.

Tokens MUST NOT be globally stable across unrelated projects.

---

### FR-018 — Protected Output

The application MUST produce new files, not overwrite originals.

Default naming:

```text
proposal.docx -> proposal_protected.docx
model.xlsx -> model_protected.xlsx
deck.pptx -> deck_protected.pptx
```

The user MAY change the suffix or destination folder.

Protected outputs MUST preserve document usability as much as technically feasible.

---

### FR-019 — Final Leakage Re-Scan

Before protected output is marked ready:

1. Generate protected document.
2. Re-open generated output using a clean parser pass.
3. Re-run enabled sensitive-data detection.
4. Compare findings with policy.
5. Report residual findings.

If high-confidence or exact confidential values remain:

- export SHOULD be blocked by default;
- user may review and override with explicit confirmation if policy allows.

The result MUST state one of:

- Ready
- Ready with warnings
- Review required
- Failed

The application MUST NOT display an absolute "100% safe" guarantee.

---

### FR-020 — Restore Workflow

The Restore workflow MUST allow users to:

1. Open a project.
2. Choose **Restore Protected Data**.
3. Select one or more files returned from an external AI workflow.
4. Scan for known project tokens.
5. Validate token integrity.
6. Preview restoration summary.
7. Restore known tokens.
8. Save restored copy as a new file.

Default output example:

```text
analysis_from_ai.docx
-> analysis_from_ai_restored.docx
```

---

### FR-021 — Restore Validation

Before restoration, the application MUST report:

- known tokens found;
- unknown tokens;
- malformed tokens;
- expected tokens where traceable;
- missing tokens where traceable;
- duplicate/unexpected occurrences;
- suspicious edits.

Example:

```text
Known tokens found:       124
Unknown tokens:             0
Modified/malformed:         2
Missing expected tokens:    1
```

The application MUST NOT use aggressive fuzzy replacement automatically.

Unknown or modified tokens MUST remain unchanged unless the user resolves them manually.

---

### FR-022 — History

Each project MUST keep a local history of operations.

History records SHOULD include:

- timestamp;
- application version;
- operation type;
- source filename;
- source file fingerprint/hash;
- output filename;
- output file fingerprint/hash;
- reversible mode;
- profile/policy;
- entities detected by category;
- entities treated;
- entities ignored;
- warnings;
- restoration status;
- leakage re-scan result.

History MUST NOT store complete raw file contents.

---

### FR-023 — Mapping Retention

User MUST be able to configure mapping retention:

- Until manually deleted
- 7 days
- 30 days
- 90 days
- Custom
- Delete when project is deleted

Optional future mode:

- Session only

When a mapping expires:

- its encrypted values and required restoration key material MUST be deleted;
- the UI MUST state that restoration is no longer possible.

---

### FR-024 — Project Metadata

Saved project metadata MAY include:

- project ID;
- encrypted display name;
- encrypted description;
- created/updated timestamps;
- privacy profile;
- reversible default;
- retention settings;
- output settings;
- encrypted filenames;
- encrypted source paths only if user enables "Remember source location";
- file fingerprints;
- operation metadata;
- application/schema version.

Project metadata MUST remain local.

---

### FR-025 — Original File Retention

Default behavior:

- do not copy original files into application storage;
- do not keep raw document snapshots;
- do not place original content in logs;
- do not store extracted full text after operation completion.

Temporary extraction files MUST be cleaned after processing.

---

### FR-026 — Secure Mapping Vault

When reversible mode is enabled:

- original sensitive values MUST be encrypted at rest;
- authenticated encryption MUST be used;
- encryption keys MUST NOT be stored as plaintext beside the vault;
- OS credential/key storage SHOULD be used;
- mappings MUST be project-scoped;
- sensitive plaintext SHOULD only exist in process memory for the minimum necessary duration.

---

### FR-027 — Local-Only Processing

Document processing MUST NOT require internet access.

Core processing MUST NOT:

- upload documents;
- call public AI APIs;
- call cloud NER/PII APIs;
- send telemetry;
- send document content in crash reports;
- download NLP models at runtime without explicit user action.

Bundled production models and recognizers MUST be available offline.

---

### FR-028 — External Links

Help/About MAY contain:

- support email;
- support website;
- documentation URL;
- donation URL;
- release/download website.

These links MUST:

- be configurable at build time or application configuration;
- open only after explicit user action;
- use the operating system default browser/email client;
- never include document data, project names, file names, tokens, or PII in the URL.

Suggested configuration keys:

```text
APP_SUPPORT_EMAIL
APP_SUPPORT_URL
APP_DOCUMENTATION_URL
APP_DONATION_URL
APP_PRIVACY_URL
APP_RELEASE_URL
```

---

## 8. Format-Specific Requirements

### 8.1 CSV

MUST:

- detect encoding;
- preserve delimiter and quoting where feasible;
- process cell values;
- preserve row/column count;
- preserve headers unless treated;
- support large files using streaming/chunked processing where possible;
- not evaluate formulas or spreadsheet expressions.

---

### 8.2 XLSX

MUST inspect, where technically supported:

- visible sheets;
- hidden sheets;
- very-hidden sheets;
- normal cell text;
- shared strings;
- inline strings;
- formulas containing string literals where safe;
- comments/notes;
- hyperlinks/display text;
- defined names;
- chart text where accessible;
- workbook/document properties.

MUST NOT execute:

- macros;
- external links;
- formulas;
- embedded code.

The application MUST report document areas that were not fully inspectable.

Preservation of formulas, styles, charts, and relationships is a critical test requirement.

---

### 8.3 DOCX

MUST inspect, where technically supported:

- paragraphs;
- text runs;
- tables;
- headers;
- footers;
- comments;
- hyperlinks;
- document core properties;
- supported text-bearing OOXML parts.

SHOULD inspect:

- footnotes/endnotes where present;
- text boxes/drawing text through OOXML fallback;
- custom properties.

The processor MUST preserve formatting and relationships as much as possible.

---

### 8.4 PPTX

MUST inspect, where technically supported:

- visible slides;
- hidden slides;
- text boxes;
- placeholders;
- tables;
- notes slides;
- comments where accessible;
- chart titles/labels where accessible;
- hyperlinks/display text;
- document core properties;
- grouped shapes where text is present.

The application MUST preserve presentation package integrity.

Images are not OCR-scanned in MVP.

---

## 9. Metadata Treatment

Each privacy profile MUST define metadata handling.

Recommended default:

- remove/blank author;
- remove last-modified-by where supported;
- sanitize title/subject/keywords if detected;
- sanitize comments;
- sanitize custom properties where supported;
- preserve required application/package metadata.

Metadata cleanup MUST be included in the final leakage re-scan.

---

## 10. User Interface Requirements

### 10.0 Language Behavior

The primary/default UI shown on first launch MUST be Bahasa Indonesia unless a future installer or OS-locale policy explicitly overrides this requirement.

English is selectable at any time from Settings.

All screenshots, mockups, and examples in this requirements document are illustrative; development MUST use the localized labels defined in Section 6.1.

### 10.1 Design Principles

The UI MUST be:

- simple;
- non-technical by default;
- clear about local processing;
- explicit about irreversible actions;
- usable without reading technical documentation;
- responsive during scanning;
- keyboard navigable where practical;
- clear about warnings and incomplete coverage.

Avoid unnecessary dashboards.

---

### 10.2 Primary Screens

#### Screen A — Projects

```text
Projects

[ + New Project ]

Acquisition Garuda
Updated today
3 files
Reversible protection: ON
[Open]

HR Review
Updated 4 days ago
12 files
Reversible protection: OFF
[Open]
```

#### Screen B — Project

```text
Acquisition Garuda

Protection: Reversible ON
Profile: M&A / Due Diligence

[ + Add Files ] [Project Settings]

Files
- management.pptx
- model.xlsx
- diligence.docx

[Scan & Review]
```

#### Screen C — Scan Progress

```text
Scanning locally...

model.xlsx
████████████████░░ 82%

No document content is being uploaded.
```

#### Screen D — Review

```text
241 sensitive items found

Personal Data            63
Financial Data           91
Business Confidential    74
Custom                    13

[Review Details]
[Protect Files]
```

#### Screen E — Results

```text
Files Protected

proposal_protected.docx     Ready
model_protected.xlsx        Ready with warnings

[Open Output Folder]
[View Privacy Report]
[Restore Files Returned by AI]
```

---

### 10.3 Help Screen

Help MUST contain concise topics:

- What this application does
- How to create a project
- How to add files
- What sensitive data detection means
- Reversible vs non-reversible protection
- How to review findings
- How to use protected files with external AI
- How to restore returned files
- What the tool does not detect
- Supported file formats
- Privacy/local processing statement
- Troubleshooting
- Contact support

Help SHOULD work fully offline.

---

### 10.4 About Screen

About MUST show:

- product name;
- version;
- build number;
- operating system/platform;
- local processing statement;
- open-source third-party notices/licenses;
- support/contact;
- documentation link;
- privacy policy link;
- donation link;
- copyright/legal notice.

Suggested controls:

- **Contact Support**
- **Documentation**
- **Privacy**
- **Donate**
- **Copy Diagnostic Information**

Diagnostic information MUST NOT contain filenames, project names, tokens, PII, or document content by default.

---

## 11. Privacy Report

For each protection operation, the user SHOULD be able to view/export a privacy report containing:

```text
Files scanned:                    4
Sensitive entities detected:   241
Protected:                      233
Ignored by user:                  5
Residual warnings:                3

PERSON                            37
EMAIL                             22
PHONE                             11
NIK                                6
BUSINESS_CONFIDENTIAL            72
FINANCIAL                         93

Hidden sheets scanned:            4
Notes slides scanned:             7
Comments scanned:                18
Metadata treatment:        Complete

Network document uploads:         0

Status: REVIEW REQUIRED
```

Reports MUST NOT expose original sensitive values unless the user explicitly requests a detailed local report.

---

## 12. Security Requirements

### SR-001

All processing must be local.

### SR-002

No document content in logs.

### SR-003

No default telemetry.

### SR-004

No automatic cloud crash report containing application state or document data.

### SR-005

Use authenticated encryption for reversible mapping.

### SR-006

Use OS keychain/credential storage where available.

### SR-007

Temporary files MUST use user-specific secure temp directories and be deleted after processing.

### SR-008

Input files MUST be treated as untrusted.

### SR-009

XML parsers MUST be hardened against unsafe entity expansion/resource exhaustion.

### SR-010

Embedded macros/scripts MUST never be executed.

### SR-011

File and project names in local persistent storage SHOULD be encrypted where feasible because metadata itself can be sensitive.

### SR-012

The application MUST not claim "safe" when it could not inspect required components.

### SR-013

Restoration MUST fail closed for unknown/modified tokens.

### SR-014

Deleting reversible mapping MUST require confirmation.

### SR-015

Clipboard copying of original sensitive values SHOULD require explicit user action.

---

## 13. Performance Requirements

Initial targets for typical modern desktop hardware:

- Application launch: target < 5 seconds excluding first model warm-up.
- Project list load: target < 1 second for 100 projects.
- UI MUST remain responsive during processing.
- A 10 MB CSV/XLSX/DOCX/PPTX SHOULD process without blocking the UI thread.
- Processing SHOULD support cancellation.
- Large-file limits MUST be configurable.
- Memory usage SHOULD avoid loading all raw document text into duplicate in-memory copies where streaming is possible.

Performance is secondary to correctness and preservation.

---

## 14. Reliability Requirements

- Original files MUST never be modified in place.
- A failed treatment MUST not produce an output labeled Ready.
- Output must be re-opened/validated after creation.
- Operations SHOULD be transactional where possible.
- If the app crashes during vault update, previous valid vault state MUST remain recoverable.
- Project schema migrations MUST be versioned.
- File processors MUST have regression test corpora.

---

## 15. Accessibility and Usability

The application SHOULD:

- use clear status text in addition to color;
- avoid relying on red/green alone;
- support common keyboard navigation;
- provide tooltips for technical concepts;
- provide confirmation text for irreversible operations;
- provide progress and cancel controls;
- explain when detection confidence is uncertain.

---

## 16. Python Library Requirements

Exact versions MUST be pinned in a lock file at release time. The table below defines intended components, not permanent version pins.

| Purpose | Recommended library | Notes |
|---|---|---|
| Desktop GUI | `PySide6` | Official Qt for Python binding |
| PII orchestration | `presidio-analyzer` | Detection engine and recognizer registry |
| Treatment helpers | `presidio-anonymizer` | Operators may be reused/extended |
| NLP baseline | `spacy` | Local NLP engine; no runtime download |
| Excel | `openpyxl` | High-level XLSX handling |
| Word | `python-docx` | High-level DOCX handling |
| PowerPoint | `python-pptx` | High-level PPTX handling |
| OOXML/XML | `lxml` | Low-level OOXML fallback and structure preservation |
| Safer XML parsing | `defusedxml` | Required where compatible |
| Encryption | `cryptography` | AES-GCM / authenticated encryption |
| OS key storage | `keyring` | Windows Credential Manager/macOS Keychain/Linux supported backend |
| App directories | `platformdirs` | Cross-platform app-data/cache/config locations |
| Validation/config | `pydantic` | Typed models/config validation |
| CSV encoding | `charset-normalizer` | Encoding inference where needed |
| Packaging | `Nuitka` | Standalone compilation/distribution |
| Tests | `pytest` | Unit/integration tests |
| Property tests | `hypothesis` | Recommended for token/parser edge cases |
| Coverage | `pytest-cov` | Test coverage |
| Lint/format | `ruff` | Fast linting/format checks |
| Type checking | `mypy` or `pyright` | Team choice |

Standard-library components SHOULD be preferred where adequate:

- `sqlite3`
- `csv`
- `hashlib`
- `hmac`
- `secrets`
- `uuid`
- `json`
- `zipfile`
- `pathlib`
- `logging`
- `tempfile`
- `concurrent.futures`
- `multiprocessing`
- `tomllib` on supported Python versions

Avoid adding `pandas` to the MVP unless a concrete requirement justifies the binary-size and dependency cost.

Avoid bundling `torch` in the base MVP unless local NER benchmarks prove that it is necessary.

---

## 17. Local NLP / "Smart" Detection Requirement

The architecture MUST support pluggable local NLP.

MVP recommendation:

1. Presidio rule/pattern/context recognizers.
2. spaCy local engine for baseline PERSON/ORG/LOCATION recognition.
3. Indonesian custom recognizers.
4. Project custom exact/regex rules.
5. Benchmark an Indonesian or multilingual NER model separately.

A larger transformer/ONNX model MAY be introduced only after:

- precision/recall benchmark;
- memory benchmark;
- startup benchmark;
- package-size impact review;
- Windows/macOS/Linux compatibility test.

Production builds MUST bundle any required model files. They MUST NOT silently download models when a document is opened.

---

## 18. Distribution Requirements

End users MUST NOT need to install:

- Python;
- pip;
- project libraries;
- Qt;
- Microsoft Office.

Preferred release artifacts:

### Windows

- Windows x64 installer: `SandiRaksa-Setup-x64.exe`
- Code signed
- Start Menu shortcut
- Optional desktop shortcut
- Standard uninstall entry

Future:

- Windows ARM64 if dependency support is validated

### macOS

Separate builds are acceptable:

- Apple Silicon: `SandiRaksa-macOS-arm64.dmg`
- Intel: `SandiRaksa-macOS-x64.dmg`

Requirements:

- `.app` bundle
- Developer ID signing
- notarization
- DMG installer/distribution

### Linux

Primary:

- x86_64 AppImage

Possible additional packages:

- `.deb`
- arm64 AppImage
- Flatpak in future

Release SHOULD include SHA-256 checksums.

---

## 19. Build and Release Requirements

CI SHOULD use native runners per target platform.

Recommended matrix:

```text
Windows x64
macOS arm64
macOS x64
Linux x86_64
```

Each release build MUST:

1. Checkout tagged source.
2. Install approved Python version.
3. Install locked dependencies.
4. Run static checks.
5. Run unit tests.
6. Run document regression tests.
7. Run security tests.
8. Build Nuitka standalone application.
9. Run packaged-application smoke tests.
10. Create platform installer.
11. Sign/notarize as applicable.
12. Generate checksums.
13. Produce Software Bill of Materials (recommended).
14. Archive release artifacts.

A release MUST NOT be published if core document round-trip tests fail.

---

## 20. Versioning

Use Semantic Versioning:

```text
MAJOR.MINOR.PATCH
```

Examples:

- `0.1.0` internal alpha
- `0.5.0` public beta
- `1.0.0` stable MVP

The project database schema MUST have an independent schema version.

---

## 21. Logging

Allowed examples:

```text
INFO operation=scan file_id=...
INFO entity_type=PERSON confidence=0.96 location=slide:3
INFO protected_count=87
```

Forbidden:

```text
DEBUG detected="John Smith"
DEBUG NIK="..."
DEBUG cell_value="..."
```

Logs MUST use internal IDs rather than raw values.

---

## 22. Error Handling

User-facing errors MUST be actionable.

Examples:

- Unsupported file type
- File is corrupted
- Password-protected/encrypted Office file not supported
- Project vault unavailable
- Mapping key unavailable
- Token modified by external system
- Output validation failed
- Unsupported embedded object
- File too large
- Permission denied
- Output file already exists

Technical tracebacks MUST not be shown directly to normal users.

---

## 23. Threat Model — Minimum Scope

Threats to consider:

1. Accidental upload of PII to public AI.
2. Missed PII due to false negatives.
3. PII hidden in Office metadata/hidden sections.
4. Leakage through application logs.
5. Leakage through temporary files.
6. Theft of reversible mapping vault.
7. Theft of encryption key.
8. Malicious/corrupt OOXML input.
9. Token modification by external AI.
10. Re-identification through quasi-identifiers.
11. Sensitive project names/filenames in metadata storage.
12. Supply-chain compromise of dependencies/build artifacts.

The product reduces risk; it does not eliminate all re-identification risk.

---

## 24. Testing Acceptance Criteria

### Detection

- Known test corpus includes positive/negative samples.
- Indonesian identifiers have dedicated unit tests.
- Custom rules have exact/regex/context tests.
- False-positive and false-negative metrics are tracked.

### Reversibility

Given:

```text
Original -> Protect -> Restore
```

the restored sensitive values MUST match the originals for intact tokens.

### Referential Integrity

Same entity in the same project MUST map consistently according to policy.

Same entity in different projects MUST not be assumed to share a token.

### Document Integrity

For each supported format:

- file opens successfully after treatment;
- file opens successfully after restoration;
- core structure preserved;
- untouched content unchanged where expected;
- formulas/charts/relationships remain valid where supported.

### Security

- no raw sensitive value in logs;
- no network document upload;
- vault is unreadable without key;
- tampered encrypted records fail authentication;
- malformed token does not cause unsafe restore.

---

## 25. MVP Definition of Done

MVP is complete only when:

- multi-project lifecycle works;
- projects can be reopened;
- files can be added later;
- CSV/XLSX/DOCX/PPTX processing works on supported test corpus;
- reversible mode defaults ON;
- non-reversible mode works;
- encrypted project mapping works;
- restore workflow works;
- leakage re-scan works;
- Help and About exist;
- support/contact and donation links are configurable;
- application runs offline;
- packaged builds work without Python installed;
- Windows, macOS, Linux release artifacts pass smoke tests;
- privacy limitations are documented in-app;
- source and protected documents are never silently overwritten.

---

## 26. Recommended Delivery Phases

### Phase 0 — Core Prototype

- Project model
- CSV
- basic rules
- token mapping
- encrypted vault
- restore
- CLI/internal test harness

### Phase 1 — Structured MVP

- PySide6 GUI
- CSV + XLSX
- Presidio integration
- Indonesian recognizers
- review UI
- project history
- leakage re-scan

### Phase 2 — Office Documents

- DOCX
- PPTX
- notes/comments/metadata coverage
- low-level OOXML fallback
- regression corpus

### Phase 3 — Productization

- installers
- signing/notarization
- Help/About
- privacy profiles
- support/donation links
- release automation
- SBOM/third-party notices

### Phase 4 — Enhanced Local Intelligence

- benchmark Indonesian/multilingual NER
- optional ONNX model pack
- richer quasi-identifier detection
- advanced confidentiality policies

### Phase 5 — Future Formats

- PDF
- OCR
- images
- legacy Office
- enterprise policy packs

---

## 27. Success Metrics

Engineering:

- restoration correctness;
- document round-trip integrity;
- false-negative rate on maintained test corpus;
- false-positive rate;
- crash-free operations;
- package/install success across supported OSes.

User:

- time from file selection to protected output;
- percentage of detections accepted without manual correction;
- percentage of restoration operations without token conflicts;
- number of support incidents involving lost mappings;
- usability test completion rate.

Do not optimize adoption metrics at the expense of privacy accuracy.

---

## 28. Legal and User Communication

The product MUST include clear wording that:

- automated detection can miss sensitive information;
- users should review findings before sharing files externally;
- reversible tokens depend on preservation of the encrypted local mapping;
- non-reversible mode cannot be restored;
- de-identification does not automatically guarantee compliance with any law or policy;
- quasi-identifiers may still permit re-identification.

Third-party licenses and notices MUST be included in distribution.

---

## 29. External Configuration

The build/release system SHOULD provide a single product metadata configuration:

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

Actual values MUST be supplied by the product owner before release.

---

## 30. Official Technical References

- Presidio Analyzer: https://presidio.dataprivacystack.org/analyzer/
- Presidio Anonymizer: https://presidio.dataprivacystack.org/anonymizer/
- Qt for Python / PySide6: https://doc.qt.io/qtforpython-6/
- openpyxl: https://openpyxl.readthedocs.io/
- python-docx: https://python-docx.readthedocs.io/
- python-pptx: https://python-pptx.readthedocs.io/
- cryptography: https://cryptography.io/
- Nuitka: https://nuitka.net/user-documentation/

---

## 31. Final Product Principle

The product SHALL be designed around five principles:

```text
LOCAL
REVERSIBLE WHEN REQUESTED
AUDITABLE
DETERMINISTIC
NO DOCUMENT UPLOAD
```

The security value of the product depends more on detection coverage, document-format correctness, secure mapping storage, and honest leakage reporting than on visual UI complexity.