"""Tests for the file organizer."""

import tempfile
import json
from pathlib import Path

from src.core.config import AppConfig
from src.core.models import FileInfo, FileCategory, FileType
from src.core.organizer import FileOrganizer


def make_temp_file(directory: Path, name: str, content: str = "test") -> FileInfo:
    """Create a real temp file and return FileInfo."""
    file_path = directory / name
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content)
    fi = FileInfo(path=file_path)
    fi.category = FileCategory.GENERAL_DOCUMENT
    fi.confidence = 0.8
    return fi


def test_plan_sets_destinations():
    with tempfile.TemporaryDirectory() as tmpdir:
        src = Path(tmpdir) / "source"
        out = Path(tmpdir) / "output"
        src.mkdir()
        out.mkdir()

        fi = make_temp_file(src, "test.pdf")
        fi.category = FileCategory.BANK_STATEMENT

        config = AppConfig()
        organizer = FileOrganizer(config)
        organizer.plan([fi], out)

        assert fi.destination is not None
        assert "Bank Statements" in str(fi.destination)
        assert fi.destination.name == "test.pdf"


def test_plan_handles_name_conflict():
    with tempfile.TemporaryDirectory() as tmpdir:
        src = Path(tmpdir) / "source"
        out = Path(tmpdir) / "output"
        src.mkdir()
        out.mkdir()

        fi1 = make_temp_file(src, "doc.pdf")
        fi2 = make_temp_file(src / "sub", "doc.pdf", content="different")

        fi1.category = FileCategory.GENERAL_DOCUMENT
        fi2.category = FileCategory.GENERAL_DOCUMENT

        config = AppConfig()
        organizer = FileOrganizer(config)
        organizer.plan([fi1, fi2], out)

        assert fi1.destination != fi2.destination
        assert "doc (1).pdf" in str(fi2.destination)


def test_dry_run_doesnt_move():
    with tempfile.TemporaryDirectory() as tmpdir:
        src = Path(tmpdir) / "source"
        out = Path(tmpdir) / "output"
        src.mkdir()
        out.mkdir()

        fi = make_temp_file(src, "test.pdf")
        fi.category = FileCategory.INVOICE

        config = AppConfig(dry_run=True)
        organizer = FileOrganizer(config)
        organizer.plan([fi], out)
        result = organizer.execute([fi])

        # File should still be at original location
        assert fi.path.exists()
        assert result.moved_files == 1
        assert len(result.manifest) == 1


def test_actual_move():
    with tempfile.TemporaryDirectory() as tmpdir:
        src = Path(tmpdir) / "source"
        out = Path(tmpdir) / "output"
        src.mkdir()
        out.mkdir()

        fi = make_temp_file(src, "test.pdf")
        fi.category = FileCategory.INVOICE
        original_path = fi.path

        config = AppConfig(dry_run=False)
        organizer = FileOrganizer(config)
        organizer.plan([fi], out)
        result = organizer.execute([fi])

        # File should be moved
        assert not original_path.exists()
        assert fi.destination.exists()
        assert result.moved_files == 1


def test_skip_duplicates():
    with tempfile.TemporaryDirectory() as tmpdir:
        src = Path(tmpdir) / "source"
        out = Path(tmpdir) / "output"
        src.mkdir()
        out.mkdir()

        fi = make_temp_file(src, "test.pdf")
        fi.category = FileCategory.INVOICE
        fi.is_duplicate = True

        config = AppConfig(dry_run=True)
        organizer = FileOrganizer(config)
        organizer.plan([fi], out)
        result = organizer.execute([fi])

        assert result.duplicates_found == 1
        assert result.moved_files == 0
