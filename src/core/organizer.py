"""File organizer - moves/copies files into organized folder structure with undo support."""

from __future__ import annotations

import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Callable

from src.core.config import AppConfig, MANIFEST_DIR
from src.core.models import FileCategory, FileInfo, OrganizeResult

logger = logging.getLogger(__name__)


class FileOrganizer:
    """Organizes files into a clean folder structure with undo support."""

    def __init__(self, config: AppConfig):
        self.config = config

    def plan(
        self,
        files: list[FileInfo],
        output_dir: Path,
    ) -> list[FileInfo]:
        """
        Plan the organization without moving any files.
        Sets destination path on each FileInfo.
        Returns the list with destinations set.
        """
        used_names: dict[Path, set[str]] = {}

        for fi in files:
            if fi.is_duplicate:
                continue

            # Build destination path from category
            category_path = output_dir / fi.category.value

            # Resolve naming conflicts
            dest_name = self._unique_name(fi.name, category_path, used_names)
            fi.destination = category_path / dest_name

        return files

    def execute(
        self,
        files: list[FileInfo],
        progress_callback: Callable[[int, int, str], None] | None = None,
    ) -> OrganizeResult:
        """
        Execute the file organization (move files to destinations).
        Requires plan() to have been called first.
        """
        result = OrganizeResult(total_files=len(files))
        movable = [fi for fi in files if fi.destination and not fi.is_duplicate]

        for i, fi in enumerate(movable):
            if progress_callback and i % 10 == 0:
                progress_callback(i, len(movable), f"Moving: {fi.name}")

            try:
                # Create destination directory
                fi.destination.parent.mkdir(parents=True, exist_ok=True)

                if self.config.dry_run:
                    result.moved_files += 1
                    result.manifest.append({
                        "source": str(fi.path),
                        "destination": str(fi.destination),
                        "category": fi.category.value,
                        "confidence": fi.confidence,
                    })
                else:
                    # Actually move the file
                    shutil.move(str(fi.path), str(fi.destination))
                    result.moved_files += 1
                    result.manifest.append({
                        "source": str(fi.path),
                        "destination": str(fi.destination),
                        "category": fi.category.value,
                        "confidence": fi.confidence,
                    })

            except (OSError, shutil.Error) as e:
                error_msg = f"Failed to move {fi.path}: {e}"
                logger.error(error_msg)
                result.errors.append(error_msg)
                result.skipped_files += 1

        # Count duplicates
        result.duplicates_found = sum(1 for fi in files if fi.is_duplicate)
        result.skipped_files += result.duplicates_found

        # Save manifest for undo
        if result.manifest and not self.config.dry_run:
            self._save_manifest(result.manifest)

        if progress_callback:
            progress_callback(len(movable), len(movable), "Organization complete")

        return result

    def undo(self, manifest_path: Path) -> tuple[int, list[str]]:
        """
        Undo a previous organization using its manifest file.
        Returns (files_restored, errors).
        """
        try:
            manifest = json.loads(manifest_path.read_text())
        except (json.JSONDecodeError, OSError) as e:
            return 0, [f"Failed to read manifest: {e}"]

        restored = 0
        errors = []

        for entry in reversed(manifest):
            src = Path(entry["destination"])
            dst = Path(entry["source"])

            if not src.exists():
                errors.append(f"File not found: {src}")
                continue

            try:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(src), str(dst))
                restored += 1
            except (OSError, shutil.Error) as e:
                errors.append(f"Failed to restore {src}: {e}")

        # Clean up empty directories left behind
        if manifest:
            first_dest = Path(manifest[0]["destination"])
            self._cleanup_empty_dirs(first_dest.parent)

        return restored, errors

    def get_manifests(self) -> list[Path]:
        """List all available undo manifests, newest first."""
        MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
        manifests = sorted(MANIFEST_DIR.glob("manifest_*.json"), reverse=True)
        return manifests

    def _save_manifest(self, manifest: list[dict]):
        """Save manifest to disk for undo support."""
        MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = MANIFEST_DIR / f"manifest_{timestamp}.json"
        path.write_text(json.dumps(manifest, indent=2))
        logger.info(f"Manifest saved to {path}")

    def _unique_name(
        self, name: str, directory: Path, used: dict[Path, set[str]]
    ) -> str:
        """Generate a unique filename within a directory."""
        if directory not in used:
            used[directory] = set()
            # Also check existing files on disk
            if directory.exists():
                used[directory] = {f.name.lower() for f in directory.iterdir()}

        base = Path(name).stem
        ext = Path(name).suffix
        candidate = name

        counter = 1
        while candidate.lower() in used[directory]:
            candidate = f"{base} ({counter}){ext}"
            counter += 1

        used[directory].add(candidate.lower())
        return candidate

    def _cleanup_empty_dirs(self, directory: Path):
        """Remove empty directories recursively (bottom-up)."""
        try:
            for child in directory.iterdir():
                if child.is_dir():
                    self._cleanup_empty_dirs(child)

            if directory.is_dir() and not any(directory.iterdir()):
                directory.rmdir()
        except (OSError, PermissionError):
            pass
