"""File system scanner - walks directories and collects FileInfo objects."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable

from src.core.config import AppConfig
from src.core.models import FileInfo, EXTENSION_MAP, FileType

logger = logging.getLogger(__name__)


class FileScanner:
    """Scans directories and yields FileInfo objects."""

    def __init__(self, config: AppConfig):
        self.config = config
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def scan(
        self,
        root: Path,
        progress_callback: Callable[[int, str], None] | None = None,
    ) -> list[FileInfo]:
        """
        Scan a directory tree and return a list of FileInfo objects.

        Args:
            root: Directory to scan.
            progress_callback: Called with (count, current_file_path) for UI updates.
        """
        self._cancelled = False
        files: list[FileInfo] = []
        count = 0

        skip_dirs_lower = {d.lower() for d in self.config.skip_dirs}
        skip_files_lower = {f.lower() for f in self.config.skip_files}

        for item in self._walk(root, skip_dirs_lower):
            if self._cancelled:
                logger.info("Scan cancelled by user.")
                break

            if item.name.lower() in skip_files_lower:
                continue

            if item.is_file():
                try:
                    fi = FileInfo(path=item)
                    files.append(fi)
                    count += 1

                    if progress_callback and count % 50 == 0:
                        progress_callback(count, str(item))
                except (OSError, PermissionError) as e:
                    logger.warning(f"Cannot access {item}: {e}")

        if progress_callback:
            progress_callback(count, "Scan complete")

        logger.info(f"Scanned {count} files in {root}")
        return files

    def _walk(self, root: Path, skip_dirs_lower: set[str]):
        """Recursively walk directory, skipping configured dirs."""
        try:
            entries = sorted(root.iterdir(), key=lambda p: p.name.lower())
        except (PermissionError, OSError) as e:
            logger.warning(f"Cannot read directory {root}: {e}")
            return

        for entry in entries:
            if self._cancelled:
                return

            if entry.is_dir():
                if entry.name.lower() not in skip_dirs_lower and not entry.name.startswith("."):
                    yield from self._walk(entry, skip_dirs_lower)
            else:
                yield entry

    def find_duplicates(self, files: list[FileInfo]) -> dict[str, list[FileInfo]]:
        """
        Group files by hash to find duplicates.
        Only compares files with the same size first (optimization).
        """
        # Group by size first
        size_groups: dict[int, list[FileInfo]] = {}
        for fi in files:
            size_groups.setdefault(fi.size_bytes, []).append(fi)

        # Only hash files where size matches
        duplicates: dict[str, list[FileInfo]] = {}
        for size, group in size_groups.items():
            if len(group) < 2 or size == 0:
                continue

            for fi in group:
                h = fi.compute_hash()
                if h:
                    duplicates.setdefault(h, []).append(fi)

        # Filter to only actual duplicates
        return {h: group for h, group in duplicates.items() if len(group) > 1}
