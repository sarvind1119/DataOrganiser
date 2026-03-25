src/
├── core/
│   ├── models.py        # FileInfo, FileCategory (30+ categories), FileType, hash-based dedup
│   ├── config.py        # AppConfig with JSON persistence, skip lists, Ollama settings
│   ├── scanner.py       # Recursive directory walker with cancellation support
│   └── organizer.py     # Move engine with dry-run, undo manifests, naming conflict resolution
├── classifiers/
│   ├── rule_based.py    # Pattern matching: Aadhaar, PAN, bank statements, WhatsApp, etc.
│   ├── llm_classifier.py # Ollama integration with structured JSON prompting
│   └── pipeline.py      # Two-stage: rule-based first, LLM for ambiguous files
├── ui/
│   ├── main_window.py   # Full PyQt6 GUI: tree view, tabs, stats, undo, settings
│   └── workers.py       # QThread workers for non-blocking scan/classify/organize
└── utils/
    └── extractors.py    # PDF (PyMuPDF), DOCX, XLSX, PPTX, text, image EXIF extraction
