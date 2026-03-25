# Data Organiser - Project Walkthrough

## 1. Problem Statement

> "The average user has thousands of files scattered across Downloads, Desktop, and Documents with no logical structure. Finding a specific bank statement, Aadhaar scan, or college certificate means manually digging through hundreds of files."

### The Pain Points
- Files dumped in Downloads with cryptic names like `DoPT IntimationLetter.pdf_1769058675.pdf`
- WhatsApp images named `IMG-20240115-WA0012.jpg` mixed with camera photos
- Duplicate files wasting disk space
- Sensitive documents (Aadhaar, PAN, bank statements) sitting unprotected alongside random files
- No quick way to find "that one PDF from last year"

### The Goal
Build an **intelligent, offline, cross-platform file organizer** that:
1. Scans any directory the user chooses
2. Reads file content (not just extensions) to understand what each file IS
3. Automatically categorizes into meaningful folders
4. Handles duplicates, naming conflicts, and provides undo safety

---

## 2. Requirements Gathering

### Functional Requirements

| # | Requirement | Priority |
|---|-------------|----------|
| F1 | Scan any user-selected directory recursively | Must Have |
| F2 | Classify files by type (PDF, image, video, etc.) | Must Have |
| F3 | Classify files by content/category (bank statement vs study notes) | Must Have |
| F4 | Create organized folder structure automatically | Must Have |
| F5 | Detect and skip duplicate files | Must Have |
| F6 | Dry-run mode (preview before moving) | Must Have |
| F7 | Undo support (reverse any organization) | Must Have |
| F8 | Handle naming conflicts (e.g., two files named `doc.pdf`) | Must Have |
| F9 | Desktop GUI for non-technical users | Must Have |
| F10 | AI/LLM-based classification for ambiguous documents | Should Have |
| F11 | Detect Indian identity documents (Aadhaar, PAN, etc.) | Should Have |
| F12 | Detect WhatsApp media vs camera photos vs screenshots | Should Have |
| F13 | User-configurable settings (model, skip dirs, etc.) | Should Have |
| F14 | Progress tracking with cancellation support | Should Have |

### Non-Functional Requirements

| # | Requirement | Decision |
|---|-------------|----------|
| NF1 | Must work offline (no paid APIs) | Use local Ollama LLM + rule-based fallback |
| NF2 | Cross-platform (Windows, macOS, Linux) | Python + PyQt6 |
| NF3 | Handle large directories (10,000+ files) | Background threads, streaming scan |
| NF4 | No data loss risk | Dry-run default, undo manifests, move (not delete) |
| NF5 | Modular and extensible | Plugin-style classifiers, separated concerns |
| NF6 | Minimal resource usage without LLM | Rule-based classifier uses zero GPU/RAM overhead |

### Target User Profile
- **Primary**: Indian students/professionals with personal laptops
- **Technical level**: Non-technical (must work with just "Browse → Scan → Organize")
- **Common files**: Aadhaar scans, PAN cards, bank statements, college marksheets, WhatsApp photos, downloaded PDFs, salary slips
- **Languages in documents**: English + Hindi (Devanagari script support)

---

## 3. Design Decisions

### Decision 1: Two-Stage Classification Pipeline

**Problem**: Pure LLM classification is slow (~2-5 seconds per file). Pure rule-based misses nuanced documents.

**Solution**: Hybrid approach
```
File → Rule-Based Classifier (fast, pattern matching)
         ↓
    confidence >= 80%? → Done ✓
         ↓ No
    LLM Classifier (Ollama) → Done ✓
         ↓ LLM unavailable
    Use rule-based result as-is → Done ✓
```

**Why this works**:
- 70-80% of files are classifiable by filename/path patterns alone (WhatsApp naming, DCIM folders, file extensions)
- LLM is only invoked for the remaining 20-30% ambiguous documents
- App works perfectly fine without LLM installed

### Decision 2: Rule-Based Classifier Design

The rule classifier uses three layers, checked in priority order:

**Layer 1 - Path/Filename Patterns** (highest confidence):
```python
# WhatsApp: IMG-20240115-WA0012.jpg or path contains "whatsapp"
# Screenshots: filename contains "screenshot", "snip", "capture"
# Camera: DCIM folder or IMG_/DSC_ prefix
# Resume: filename contains "resume", "cv", "biodata"
```

**Layer 2 - Content Keyword Matching** (medium confidence):
```python
# Aadhaar: "unique identification" + "aadhaar" + 12-digit number pattern
# PAN: 5-letter-4-digit-1-letter pattern + "permanent account number"
# Bank Statement: "account statement" + "opening balance" + "debit" + "credit" (3+ matches)
# Salary Slip: "basic salary" + "gross salary" + "provident fund" + "HRA" (3+ matches)
```

**Layer 3 - File Type Fallback** (lowest confidence):
```python
# .exe → Software (70%)
# .epub → eBook (70%)
# .jpg → Personal Photo (40%)  ← low confidence, LLM should verify
# .pdf → General Document (30%) ← low confidence, needs content analysis
```

### Decision 3: Indian Document Detection Rules

Each Indian document type has specific regex + keyword combinations:

| Document | Detection Patterns | Confidence |
|----------|-------------------|------------|
| **Aadhaar** | `\d{4}\s?\d{4}\s?\d{4}` + "aadhaar"/"uidai"/"आधार" (2+ matches) | 90% |
| **PAN Card** | `[A-Z]{5}\d{4}[A-Z]` + "permanent account number"/"income tax" (2+ matches) | 90% |
| **Passport** | "passport" + "republic of india" + "date of expiry" | 85% |
| **Driving License** | "driving licence" + "class of vehicle"/"blood group" | 85% |
| **Voter ID** | "election commission" + "electors photo" | 85% |
| **Bank Statement** | 3+ of: "account statement", "opening balance", "transaction", "debit", "credit", "IFSC" | 85% |
| **Salary Slip** | 3+ of: "basic salary", "gross salary", "net pay", "HRA", "provident fund", "employee id" | 85% |
| **Tax Document** | 2+ of: "income tax", "form 16", "form 26as", "ITR", "assessment year", "TDS" | 85% |
| **Marksheet** | 3+ of: "marksheet", "marks obtained", "semester", "CGPA", "roll number", "university" | 85% |

### Decision 4: Duplicate Detection Strategy

**Problem**: Computing full file hash (MD5/SHA) for every file is slow for large files.

**Solution**: Two-phase dedup
```
Phase 1: Group by file size
  → Only files with identical sizes could be duplicates
  → Eliminates 90%+ of comparisons

Phase 2: Partial hash (first 8KB + last 8KB + file size)
  → Fast even for multi-GB video files
  → Catches 99.9% of duplicates without reading entire file
```

### Decision 5: Folder Structure

Category enum values directly map to folder paths:
```
Output Directory/
├── Identity Documents/
│   ├── Aadhaar/
│   ├── PAN Card/
│   ├── Passport/
│   ├── Voter ID/
│   └── Driving License/
├── Financial/
│   ├── Bank Statements/
│   ├── Tax Documents/
│   ├── Invoices & Receipts/
│   ├── Salary Slips/
│   └── Insurance/
├── Education/
│   ├── Study Material/
│   ├── Certificates/
│   ├── Marksheets/
│   └── Resume & CV/
├── Work/
│   ├── Official Letters/
│   ├── Contracts & Agreements/
│   ├── Reports/
│   ├── Presentations/
│   └── Spreadsheets/
├── Media/
│   ├── Personal Photos/
│   ├── WhatsApp/
│   ├── Camera Photos/
│   ├── Screenshots/
│   ├── Videos/
│   └── Music/
├── Documents/
│   ├── eBooks/
│   └── General/
├── Developer/
│   └── Code/
├── Archives/
├── Software & Installers/
└── Other/
```

### Decision 6: Safety-First Design

| Risk | Mitigation |
|------|------------|
| Accidental file loss | Dry-run enabled by default |
| User wants to undo | JSON manifest saved for every operation |
| Name collision at destination | Auto-rename: `doc.pdf` → `doc (1).pdf` → `doc (2).pdf` |
| System files moved | Skip list: `$Recycle.Bin`, `Windows`, `Program Files`, `AppData`, etc. |
| Hidden files moved | Skip dotfiles/dot-directories by default |
| Large file stalls extraction | 50MB extraction limit, 10-page PDF limit |
| App freezes during scan | All heavy work runs in QThread background workers |

---

## 4. Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    PyQt6 Desktop GUI                     │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────┐  │
│  │File Tree │ │ Details  │ │  Stats   │ │ Settings  │  │
│  │ Preview  │ │  Panel   │ │Dashboard │ │ & Undo    │  │
│  └──────────┘ └──────────┘ └──────────┘ └───────────┘  │
├─────────────────────────────────────────────────────────┤
│              QThread Background Workers                  │
│  ┌──────────┐ ┌───────────┐ ┌───────────────────────┐  │
│  │  Scan    │ │ Classify  │ │      Organize         │  │
│  │ Worker   │ │  Worker   │ │       Worker          │  │
│  └──────────┘ └───────────┘ └───────────────────────┘  │
├─────────────────────────────────────────────────────────┤
│                    Core Engine                           │
│  ┌──────────┐ ┌───────────────────────┐ ┌───────────┐  │
│  │ Scanner  │ │ Classification        │ │ Organizer │  │
│  │          │ │ Pipeline              │ │           │  │
│  │• Walk    │ │ ┌─────────┐ ┌──────┐  │ │• Plan     │  │
│  │  dirs    │ │ │Rule-    │→│ LLM  │  │ │• Execute  │  │
│  │• Filter  │ │ │Based    │ │(opt) │  │ │• Undo     │  │
│  │• Dedup   │ │ └─────────┘ └──────┘  │ │• Manifest │  │
│  └──────────┘ └───────────────────────┘ └───────────┘  │
├─────────────────────────────────────────────────────────┤
│                 Text Extractors                          │
│  ┌──────┐ ┌──────┐ ┌───────┐ ┌──────┐ ┌─────────────┐  │
│  │ PDF  │ │ DOCX │ │ XLSX  │ │ PPTX │ │Image (EXIF) │  │
│  │PyMuPD│ │python│ │openpyx│ │python│ │  Pillow     │  │
│  └──────┘ └──────┘ └───────┘ └──────┘ └─────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### Data Flow

```
User selects directory
        │
        ▼
   ┌─────────┐
   │  SCAN   │ → Walk directory tree, skip system dirs
   │         │ → Create FileInfo for each file (name, size, type, timestamps)
   │         │ → Detect duplicates (size grouping → partial hash)
   └────┬────┘
        │ list[FileInfo]
        ▼
  ┌──────────┐
  │ CLASSIFY │ → Extract text content (PDF, DOCX, XLSX, PPTX)
  │          │ → Extract image metadata (EXIF)
  │          │ → Rule-based classification (patterns + keywords)
  │          │ → If confidence < 80% AND LLM available:
  │          │     → Send to Ollama for AI classification
  │          │ → Set category + confidence on each FileInfo
  └────┬─────┘
       │ list[FileInfo] with categories
       ▼
  ┌──────────┐
  │ PREVIEW  │ → Show tree view grouped by category
  │          │ → Color-code by confidence (green/yellow/red)
  │          │ → Show statistics dashboard
  │          │ → User reviews and adjusts if needed
  └────┬─────┘
       │ User clicks "Organize"
       ▼
  ┌──────────┐
  │ ORGANIZE │ → Plan: compute destination paths, resolve name conflicts
  │          │ → If dry-run: show what WOULD happen, stop
  │          │ → If real: move files, save undo manifest
  │          │ → Report: X moved, Y duplicates skipped, Z errors
  └──────────┘
```

---

## 5. Tech Stack

| Component | Technology | Why |
|-----------|-----------|-----|
| Language | Python 3.10+ | Cross-platform, rich ecosystem, easy to read |
| GUI Framework | PyQt6 | Native look, professional widgets, mature |
| PDF Extraction | PyMuPDF (pymupdf) | Fastest Python PDF library, handles scanned PDFs |
| Word Extraction | python-docx | Standard .docx reader |
| Excel Extraction | openpyxl | Reads .xlsx without Excel installed |
| PowerPoint Extraction | python-pptx | Reads .pptx slides and text |
| Image Metadata | Pillow (PIL) | EXIF data for camera/screenshot detection |
| Text Encoding | chardet | Auto-detect encoding for non-UTF8 text files |
| AI Classification | Ollama (local LLM) | Free, offline, runs Llama 3.2 / Phi-3 locally |
| Hashing | hashlib (stdlib) | MD5 partial hash for fast duplicate detection |
| File Operations | shutil (stdlib) | Cross-platform file move/copy |
| Config Storage | JSON (stdlib) | Simple, human-readable settings persistence |
| Testing | pytest | Standard Python testing framework |

---

## 6. Module Breakdown

### `src/core/models.py` — Data Models
- **FileCategory** enum: 30+ categories organized into Identity, Financial, Education, Work, Media, etc.
- **FileType** enum: PDF, Word, Excel, PowerPoint, Image, Video, Audio, Code, Archive, etc.
- **EXTENSION_MAP**: Maps 80+ file extensions to FileType
- **FileInfo** dataclass: Holds everything about a file (path, type, category, confidence, hash, destination)
- **OrganizeResult** dataclass: Summary of an organize operation

### `src/core/config.py` — Configuration
- **AppConfig** dataclass: All settings (Ollama model, skip dirs, dry-run flag, etc.)
- Persists to `~/.data_organiser/config.json`
- Default skip list: `$Recycle.Bin`, `Windows`, `Program Files`, `node_modules`, `.git`, etc.

### `src/core/scanner.py` — File Scanner
- Recursive directory walker with cancellation support
- Respects skip lists for directories and files
- Progress callback for UI updates (every 50 files)
- Duplicate detection: size-first grouping → partial MD5 hash

### `src/utils/extractors.py` — Text Extraction
- Graceful degradation: each library is optional, checked at import time
- `extract_text()`: Routes to correct extractor based on FileType
- `extract_image_metadata()`: EXIF data (camera model, GPS, dimensions)
- PDF: First 10 pages via PyMuPDF
- DOCX: All paragraphs
- XLSX: Sheet names + first 20 rows
- PPTX: First 15 slides, all text shapes
- Text: UTF-8 with chardet fallback

### `src/classifiers/rule_based.py` — Pattern Classifier
- Three classification layers: path patterns → content keywords → file type fallback
- Indian document detection with regex (Aadhaar 12-digit, PAN format, etc.)
- WhatsApp media detection (WA naming convention + path)
- Financial document keywords (bank statement, salary slip, invoice)
- Education keywords (marksheet, certificate, study material)
- Returns (category, confidence) tuple

### `src/classifiers/llm_classifier.py` — AI Classifier
- Sends filename + content excerpt to local Ollama LLM
- Structured JSON prompt → parses `{"category": "...", "confidence": 0.0-1.0}`
- Handles missing `ollama` package, server down, model not pulled
- Temperature 0.1 for deterministic classification

### `src/classifiers/pipeline.py` — Classification Pipeline
- Orchestrates rule-based → LLM two-stage flow
- Extracts text and metadata before classification
- LLM only called when rule-based confidence < 80%
- Progress callback for UI updates

### `src/core/organizer.py` — File Organizer
- `plan()`: Computes destinations, resolves naming conflicts
- `execute()`: Moves files (or simulates in dry-run mode)
- `undo()`: Reads manifest JSON, moves files back to original locations
- Manifest saved to `~/.data_organiser/manifests/manifest_YYYYMMDD_HHMMSS.json`
- Cleans up empty directories after undo

### `src/ui/workers.py` — Background Threads
- `ScanWorker`: Scans directory in QThread
- `ClassifyWorker`: Classifies files in QThread
- `OrganizeWorker`: Moves files in QThread
- All emit progress signals for UI updates

### `src/ui/main_window.py` — GUI
- Directory selection (source + output)
- File tree grouped by category with confidence color-coding
- File details panel (path, size, type, content preview, metadata)
- Statistics dashboard (by category, by type, confidence distribution)
- Settings tab (LLM toggle, model selection, dry-run, dedup, library status)
- Undo history tab (list manifests, restore operations)
- Three-step action flow: Scan → Classify → Organize
- Custom stylesheet with modern color palette

---

## 7. LLM Prompt Engineering

### Classification Prompt (sent to Ollama)

```
You are a document classifier. Classify the following document
based on its filename and content excerpt.

Filename: {filename}
Content (first ~2000 chars):
---
{content}
---

Classify into EXACTLY ONE of these categories:
- aadhaar (Indian Aadhaar card)
- pan_card (Indian PAN card)
- passport
- voter_id
- driving_license
- bank_statement
- tax_document (ITR, Form 16, TDS)
- invoice (bills, receipts, payment confirmations)
- salary_slip (payslip, salary statement)
- insurance (insurance policy, claim)
- study_material (notes, textbook, lecture, assignment)
- certificate (course certificate, achievement, diploma)
- marksheet (exam results, grades)
- resume (CV, biodata)
- official_letter (formal correspondence)
- contract (agreement, terms)
- report (business report, analysis)
- general_document (anything else)
- other

Respond with ONLY a JSON object: {"category": "<label>", "confidence": <0.0-1.0>}
No explanation.
```

### Why This Prompt Works
1. **Structured output**: Forces JSON response, easy to parse programmatically
2. **Category descriptions**: Brief hints prevent LLM confusion between similar categories
3. **Both filename + content**: Some files have descriptive names, others don't
4. **Content truncation**: Only first ~2000 chars sent — keeps latency low
5. **Temperature 0.1**: Near-deterministic output, same file → same classification
6. **"No explanation"**: Prevents verbose responses, just the JSON

---

## 8. Key Implementation Details

### Naming Conflict Resolution
```python
def _unique_name(self, name, directory, used):
    # Track used names per directory (including existing files on disk)
    # "doc.pdf" → "doc (1).pdf" → "doc (2).pdf"
    base = Path(name).stem     # "doc"
    ext = Path(name).suffix    # ".pdf"
    candidate = name
    counter = 1
    while candidate.lower() in used[directory]:
        candidate = f"{base} ({counter}){ext}"
        counter += 1
    used[directory].add(candidate.lower())
    return candidate
```

### Partial Hash for Fast Dedup
```python
def compute_hash(self):
    hasher = hashlib.md5()
    with open(self.path, "rb") as f:
        head = f.read(8192)           # First 8KB
        hasher.update(head)
        if self.size_bytes > 16384:
            f.seek(-8192, os.SEEK_END)
            tail = f.read(8192)       # Last 8KB
            hasher.update(tail)
        hasher.update(str(self.size_bytes).encode())  # Include size
    return hasher.hexdigest()
```

### Graceful Library Degradation
```python
_HAS_PYMUPDF = False
try:
    import pymupdf
    _HAS_PYMUPDF = True
except ImportError:
    try:
        import fitz  # older pymupdf
        _HAS_PYMUPDF = True
    except ImportError:
        pass

# Later in extract_text():
if not is_available:
    logger.info(f"Skipping extraction for {name} (missing library)")
    return ""
```

---

## 9. Testing Strategy

### What's Tested (19 tests)

**Model Tests** (`test_models.py`):
- Extension-to-FileType mapping correctness
- FileInfo auto-populates fields from path
- Identical files produce identical hashes
- Different files produce different hashes

**Classifier Tests** (`test_classifiers.py`):
- WhatsApp image detection (by filename pattern)
- Screenshot detection (by filename keyword)
- Resume detection (by filename keyword)
- Aadhaar detection (by content keywords)
- PAN card detection (by content regex + keywords)
- Bank statement detection (by content keywords)
- Salary slip detection (by content keywords)
- Study material detection (by content keywords)
- Executable → Software classification
- Unknown image falls back to low-confidence Personal Photo

**Organizer Tests** (`test_organizer.py`):
- Plan sets correct destination paths
- Name conflicts resolved with "(1)" suffix
- Dry-run doesn't move actual files
- Real move transfers files and removes originals
- Duplicates are skipped during organization

### Running Tests
```bash
python -m pytest tests/ -v
```

---

## 10. How to Use

### Prerequisites
```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

### Optional: Install Ollama for AI Classification
```bash
# Download Ollama from https://ollama.com
ollama pull llama3.2:3b
```

### Launch
```bash
python run.py
```

### Step-by-Step Workflow
1. **Browse Source** → Select the folder you want to organize (e.g., `Downloads`)
2. **Browse Output** → Select where organized files should go (e.g., `Documents/Organized`)
3. **Click "Scan"** → App finds all files, detects duplicates
4. **Click "Classify"** → Rule-based + AI classification runs
5. **Review** → Check the tree view, click files to see details
6. **Settings** → Ensure "Dry Run" is checked for first attempt
7. **Click "Organize"** → See preview of what would happen
8. **Uncheck Dry Run** → Click "Organize" again to actually move files
9. **Undo** → If needed, go to Undo History tab to reverse

---

## 11. Future Improvements

| Feature | Effort | Impact |
|---------|--------|--------|
| OCR for scanned PDFs (Tesseract) | Medium | High — many Indian docs are scanned images |
| Real-time folder monitoring (watchdog) | Low | Medium — auto-organize new downloads |
| SQLite cache for classification results | Low | Medium — avoid re-classifying unchanged files |
| Custom user rules UI (keyword → category) | Medium | High — personalization |
| Drag-and-drop category reassignment in GUI | Medium | High — manual correction |
| Batch processing progress (ETA display) | Low | Low — quality of life |
| Multi-language OCR (Hindi + English) | Medium | High — Indian document support |
| Thumbnail preview for images | Low | Medium — visual confirmation |
| Export organization report as CSV/PDF | Low | Low — documentation |
