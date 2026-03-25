"""Tests for core models."""

import tempfile
from pathlib import Path

from src.core.models import FileInfo, FileType, FileCategory, EXTENSION_MAP


def test_extension_mapping():
    """Test that common extensions map to correct file types."""
    assert EXTENSION_MAP[".pdf"] == FileType.PDF
    assert EXTENSION_MAP[".docx"] == FileType.WORD
    assert EXTENSION_MAP[".xlsx"] == FileType.EXCEL
    assert EXTENSION_MAP[".jpg"] == FileType.IMAGE
    assert EXTENSION_MAP[".mp4"] == FileType.VIDEO
    assert EXTENSION_MAP[".py"] == FileType.CODE
    assert EXTENSION_MAP[".zip"] == FileType.ARCHIVE


def test_file_info_auto_fields():
    """Test that FileInfo auto-populates fields from path."""
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"test content")
        path = Path(f.name)

    fi = FileInfo(path=path)
    assert fi.name == path.name
    assert fi.extension == ".pdf"
    assert fi.file_type == FileType.PDF
    assert fi.size_bytes > 0

    path.unlink()


def test_file_info_hash():
    """Test duplicate detection hash."""
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        f.write(b"identical content for hashing test")
        path1 = Path(f.name)

    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        f.write(b"identical content for hashing test")
        path2 = Path(f.name)

    fi1 = FileInfo(path=path1)
    fi2 = FileInfo(path=path2)

    h1 = fi1.compute_hash()
    h2 = fi2.compute_hash()

    assert h1 == h2
    assert len(h1) == 32  # MD5 hex length

    path1.unlink()
    path2.unlink()


def test_file_info_different_content():
    """Test that different files produce different hashes."""
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        f.write(b"content A")
        path1 = Path(f.name)

    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        f.write(b"content B")
        path2 = Path(f.name)

    fi1 = FileInfo(path=path1)
    fi2 = FileInfo(path=path2)

    assert fi1.compute_hash() != fi2.compute_hash()

    path1.unlink()
    path2.unlink()
