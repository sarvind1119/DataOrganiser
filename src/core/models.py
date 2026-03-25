"""Core data models for the file organizer."""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path


class FileCategory(Enum):
    """Top-level content categories for organized files."""

    # Indian document types
    AADHAAR = "Identity Documents/Aadhaar"
    PAN_CARD = "Identity Documents/PAN Card"
    PASSPORT = "Identity Documents/Passport"
    VOTER_ID = "Identity Documents/Voter ID"
    DRIVING_LICENSE = "Identity Documents/Driving License"

    # Financial
    BANK_STATEMENT = "Financial/Bank Statements"
    TAX_DOCUMENT = "Financial/Tax Documents"
    INVOICE = "Financial/Invoices & Receipts"
    SALARY_SLIP = "Financial/Salary Slips"
    INSURANCE = "Financial/Insurance"

    # Education
    STUDY_MATERIAL = "Education/Study Material"
    CERTIFICATE = "Education/Certificates"
    MARKSHEET = "Education/Marksheets"
    RESUME = "Education/Resume & CV"

    # Work / Official
    OFFICIAL_LETTER = "Work/Official Letters"
    CONTRACT = "Work/Contracts & Agreements"
    REPORT = "Work/Reports"
    PRESENTATION = "Work/Presentations"
    SPREADSHEET_DATA = "Work/Spreadsheets"

    # Media
    PERSONAL_PHOTO = "Media/Personal Photos"
    WHATSAPP_MEDIA = "Media/WhatsApp"
    CAMERA_PHOTO = "Media/Camera Photos"
    SCREENSHOT = "Media/Screenshots"
    VIDEO = "Media/Videos"
    MUSIC = "Media/Music"

    # Other
    EBOOK = "Documents/eBooks"
    GENERAL_DOCUMENT = "Documents/General"
    CODE = "Developer/Code"
    ARCHIVE = "Archives"
    SOFTWARE = "Software & Installers"
    OTHER = "Other"


class FileType(Enum):
    """File type classification based on extension."""

    PDF = "pdf"
    WORD = "word"
    EXCEL = "excel"
    POWERPOINT = "powerpoint"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    TEXT = "text"
    CODE = "code"
    ARCHIVE = "archive"
    EXECUTABLE = "executable"
    EBOOK = "ebook"
    OTHER = "other"


# Extension to FileType mapping
EXTENSION_MAP: dict[str, FileType] = {
    # Documents
    ".pdf": FileType.PDF,
    ".doc": FileType.WORD, ".docx": FileType.WORD, ".odt": FileType.WORD, ".rtf": FileType.WORD,
    ".xls": FileType.EXCEL, ".xlsx": FileType.EXCEL, ".xlsm": FileType.EXCEL,
    ".csv": FileType.EXCEL, ".ods": FileType.EXCEL, ".tsv": FileType.EXCEL,
    ".ppt": FileType.POWERPOINT, ".pptx": FileType.POWERPOINT, ".odp": FileType.POWERPOINT,
    # Images
    ".jpg": FileType.IMAGE, ".jpeg": FileType.IMAGE, ".png": FileType.IMAGE,
    ".gif": FileType.IMAGE, ".bmp": FileType.IMAGE, ".svg": FileType.IMAGE,
    ".webp": FileType.IMAGE, ".tiff": FileType.IMAGE, ".tif": FileType.IMAGE,
    ".heic": FileType.IMAGE, ".heif": FileType.IMAGE, ".ico": FileType.IMAGE,
    # Video
    ".mp4": FileType.VIDEO, ".avi": FileType.VIDEO, ".mkv": FileType.VIDEO,
    ".mov": FileType.VIDEO, ".wmv": FileType.VIDEO, ".flv": FileType.VIDEO,
    ".webm": FileType.VIDEO, ".m4v": FileType.VIDEO, ".3gp": FileType.VIDEO,
    # Audio
    ".mp3": FileType.AUDIO, ".wav": FileType.AUDIO, ".flac": FileType.AUDIO,
    ".aac": FileType.AUDIO, ".ogg": FileType.AUDIO, ".wma": FileType.AUDIO,
    ".m4a": FileType.AUDIO, ".opus": FileType.AUDIO,
    # Text
    ".txt": FileType.TEXT, ".md": FileType.TEXT, ".log": FileType.TEXT,
    ".ini": FileType.TEXT, ".cfg": FileType.TEXT, ".conf": FileType.TEXT,
    # Code
    ".py": FileType.CODE, ".js": FileType.CODE, ".ts": FileType.CODE,
    ".java": FileType.CODE, ".cpp": FileType.CODE, ".c": FileType.CODE,
    ".h": FileType.CODE, ".cs": FileType.CODE, ".go": FileType.CODE,
    ".rs": FileType.CODE, ".rb": FileType.CODE, ".php": FileType.CODE,
    ".html": FileType.CODE, ".css": FileType.CODE, ".json": FileType.CODE,
    ".xml": FileType.CODE, ".yaml": FileType.CODE, ".yml": FileType.CODE,
    ".sql": FileType.CODE, ".sh": FileType.CODE, ".bat": FileType.CODE,
    ".jsx": FileType.CODE, ".tsx": FileType.CODE, ".vue": FileType.CODE,
    ".swift": FileType.CODE, ".kt": FileType.CODE, ".dart": FileType.CODE,
    # Archives
    ".zip": FileType.ARCHIVE, ".rar": FileType.ARCHIVE, ".7z": FileType.ARCHIVE,
    ".tar": FileType.ARCHIVE, ".gz": FileType.ARCHIVE, ".bz2": FileType.ARCHIVE,
    ".xz": FileType.ARCHIVE, ".tar.gz": FileType.ARCHIVE,
    # Executables / Installers
    ".exe": FileType.EXECUTABLE, ".msi": FileType.EXECUTABLE, ".dmg": FileType.EXECUTABLE,
    ".deb": FileType.EXECUTABLE, ".rpm": FileType.EXECUTABLE, ".apk": FileType.EXECUTABLE,
    ".appimage": FileType.EXECUTABLE, ".snap": FileType.EXECUTABLE,
    # eBooks
    ".epub": FileType.EBOOK, ".mobi": FileType.EBOOK, ".azw3": FileType.EBOOK,
}


@dataclass
class FileInfo:
    """Information about a single file to be organized."""

    path: Path
    name: str = ""
    extension: str = ""
    size_bytes: int = 0
    modified_time: datetime | None = None
    created_time: datetime | None = None
    file_type: FileType = FileType.OTHER
    category: FileCategory = FileCategory.OTHER
    confidence: float = 0.0
    content_preview: str = ""
    hash_md5: str = ""
    destination: Path | None = None
    is_duplicate: bool = False
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.name:
            self.name = self.path.name
        if not self.extension:
            self.extension = self.path.suffix.lower()
        if self.file_type == FileType.OTHER:
            self.file_type = EXTENSION_MAP.get(self.extension, FileType.OTHER)
        if self.size_bytes == 0 and self.path.exists():
            stat = self.path.stat()
            self.size_bytes = stat.st_size
            self.modified_time = datetime.fromtimestamp(stat.st_mtime)
            self.created_time = datetime.fromtimestamp(stat.st_ctime)

    def compute_hash(self) -> str:
        """Compute MD5 hash for duplicate detection. Reads first+last 8KB for speed."""
        if self.hash_md5:
            return self.hash_md5

        hasher = hashlib.md5()
        try:
            with open(self.path, "rb") as f:
                # Read first 8KB
                head = f.read(8192)
                hasher.update(head)
                # Seek to end - 8KB if file is large enough
                if self.size_bytes > 16384:
                    f.seek(-8192, os.SEEK_END)
                    tail = f.read(8192)
                    hasher.update(tail)
                # Include size for extra uniqueness
                hasher.update(str(self.size_bytes).encode())
        except (OSError, PermissionError):
            return ""

        self.hash_md5 = hasher.hexdigest()
        return self.hash_md5


@dataclass
class OrganizeResult:
    """Result of an organize operation."""

    total_files: int = 0
    moved_files: int = 0
    skipped_files: int = 0
    duplicates_found: int = 0
    errors: list[str] = field(default_factory=list)
    manifest: list[dict] = field(default_factory=list)  # For undo support
