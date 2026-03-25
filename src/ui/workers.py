"""Background worker threads for non-blocking GUI operations."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

from src.core.config import AppConfig
from src.core.models import FileInfo, OrganizeResult
from src.core.scanner import FileScanner
from src.core.organizer import FileOrganizer
from src.classifiers.pipeline import ClassificationPipeline


class ScanWorker(QThread):
    """Background worker for scanning files."""

    progress = pyqtSignal(int, str)       # (count, current_file)
    finished = pyqtSignal(list)            # list[FileInfo]
    error = pyqtSignal(str)

    def __init__(self, scan_dir: Path, config: AppConfig):
        super().__init__()
        self.scan_dir = scan_dir
        self.config = config
        self.scanner = FileScanner(config)

    def run(self):
        try:
            files = self.scanner.scan(self.scan_dir, self._on_progress)
            self.finished.emit(files)
        except Exception as e:
            self.error.emit(str(e))

    def cancel(self):
        self.scanner.cancel()

    def _on_progress(self, count: int, current: str):
        self.progress.emit(count, current)


class ClassifyWorker(QThread):
    """Background worker for classifying files."""

    progress = pyqtSignal(int, int, str)   # (current, total, status)
    finished = pyqtSignal(list)            # list[FileInfo]
    error = pyqtSignal(str)

    def __init__(self, files: list[FileInfo], config: AppConfig):
        super().__init__()
        self.files = files
        self.config = config

    def run(self):
        try:
            pipeline = ClassificationPipeline(self.config)
            classified = pipeline.classify_files(self.files, self._on_progress)
            self.finished.emit(classified)
        except Exception as e:
            self.error.emit(str(e))

    def _on_progress(self, current: int, total: int, status: str):
        self.progress.emit(current, total, status)


class OrganizeWorker(QThread):
    """Background worker for moving/organizing files."""

    progress = pyqtSignal(int, int, str)   # (current, total, status)
    finished = pyqtSignal(object)          # OrganizeResult
    error = pyqtSignal(str)

    def __init__(self, files: list[FileInfo], output_dir: Path, config: AppConfig):
        super().__init__()
        self.files = files
        self.output_dir = output_dir
        self.config = config

    def run(self):
        try:
            organizer = FileOrganizer(self.config)
            organizer.plan(self.files, self.output_dir)
            result = organizer.execute(self.files, self._on_progress)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))

    def _on_progress(self, current: int, total: int, status: str):
        self.progress.emit(current, total, status)
