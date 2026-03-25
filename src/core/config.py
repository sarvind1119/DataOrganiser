"""Application configuration and settings."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path

CONFIG_DIR = Path.home() / ".data_organiser"
CONFIG_FILE = CONFIG_DIR / "config.json"
MANIFEST_DIR = CONFIG_DIR / "manifests"

# Directories to always skip during scanning
SKIP_DIRS = {
    "$Recycle.Bin", "System Volume Information", "Windows", "Program Files",
    "Program Files (x86)", "ProgramData", "AppData", "node_modules",
    ".git", ".svn", "__pycache__", ".venv", "venv", "env",
    ".conda", ".cache", ".npm", ".yarn", "Recovery",
}

# Files to always skip
SKIP_FILES = {
    "desktop.ini", "thumbs.db", ".ds_store", "ntuser.dat",
}

# Max file size for content extraction (50MB)
MAX_EXTRACT_SIZE = 50 * 1024 * 1024

# Ollama settings
DEFAULT_OLLAMA_MODEL = "gemma3:latest"
OLLAMA_HOST = "http://localhost:11434"


@dataclass
class AppConfig:
    """Application configuration."""

    ollama_model: str = DEFAULT_OLLAMA_MODEL
    ollama_host: str = OLLAMA_HOST
    max_extract_size: int = MAX_EXTRACT_SIZE
    skip_dirs: set[str] = field(default_factory=lambda: set(SKIP_DIRS))
    skip_files: set[str] = field(default_factory=lambda: set(SKIP_FILES))
    use_llm: bool = True
    dry_run: bool = True  # Default to dry-run for safety
    detect_duplicates: bool = True
    custom_rules: list[dict] = field(default_factory=list)
    last_scan_dir: str = ""
    last_output_dir: str = ""

    def save(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        data = asdict(self)
        data["skip_dirs"] = list(data["skip_dirs"])
        data["skip_files"] = list(data["skip_files"])
        CONFIG_FILE.write_text(json.dumps(data, indent=2))

    @classmethod
    def load(cls) -> "AppConfig":
        if CONFIG_FILE.exists():
            try:
                data = json.loads(CONFIG_FILE.read_text())
                data["skip_dirs"] = set(data.get("skip_dirs", SKIP_DIRS))
                data["skip_files"] = set(data.get("skip_files", SKIP_FILES))
                return cls(**data)
            except (json.JSONDecodeError, TypeError):
                pass
        return cls()
