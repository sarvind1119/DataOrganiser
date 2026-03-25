"""Background worker threads for non-blocking GUI operations."""

from __future__ import annotations

import time
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

from src.core.config import AppConfig
from src.core.models import FileInfo, OrganizeResult
from src.core.scanner import FileScanner
from src.core.organizer import FileOrganizer
from src.classifiers.pipeline import ClassificationPipeline


def _format_eta(seconds: float) -> str:
    """Format seconds into human-readable ETA."""
    if seconds < 60:
        return f"{int(seconds)}s"
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes}m {secs}s"


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
    """Background worker for classifying files with ETA tracking."""

    progress = pyqtSignal(int, int, str)   # (current, total, status)
    finished = pyqtSignal(list, int)       # (list[FileInfo], cache_hits)
    error = pyqtSignal(str)

    def __init__(self, files: list[FileInfo], config: AppConfig):
        super().__init__()
        self.files = files
        self.config = config
        self._start_time = 0.0

    def run(self):
        try:
            self._start_time = time.time()
            pipeline = ClassificationPipeline(self.config)
            classified = pipeline.classify_files(self.files, self._on_progress)
            self.finished.emit(classified, pipeline.cache_hits)
            pipeline.close()
        except Exception as e:
            self.error.emit(str(e))

    def _on_progress(self, current: int, total: int, status: str):
        # Calculate ETA
        elapsed = time.time() - self._start_time
        if current > 0 and total > 0:
            rate = elapsed / current
            remaining = rate * (total - current)
            eta = _format_eta(remaining)
            status = f"{status} | ETA: {eta}"
        self.progress.emit(current, total, status)


class OrganizeWorker(QThread):
    """Background worker for moving/organizing files with ETA tracking."""

    progress = pyqtSignal(int, int, str)   # (current, total, status)
    finished = pyqtSignal(object)          # OrganizeResult
    error = pyqtSignal(str)

    def __init__(self, files: list[FileInfo], output_dir: Path, config: AppConfig):
        super().__init__()
        self.files = files
        self.output_dir = output_dir
        self.config = config
        self._start_time = 0.0

    def run(self):
        try:
            self._start_time = time.time()
            organizer = FileOrganizer(self.config)
            organizer.plan(self.files, self.output_dir)
            result = organizer.execute(self.files, self._on_progress)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))

    def _on_progress(self, current: int, total: int, status: str):
        elapsed = time.time() - self._start_time
        if current > 0 and total > 0:
            rate = elapsed / current
            remaining = rate * (total - current)
            eta = _format_eta(remaining)
            status = f"{status} | ETA: {eta}"
        self.progress.emit(current, total, status)


class WatcherWorker(QThread):
    """Background worker for folder monitoring."""

    new_file = pyqtSignal(str)    # path of new file
    error = pyqtSignal(str)

    def __init__(self, watch_dir: Path):
        super().__init__()
        self.watch_dir = watch_dir
        self._watcher = None

    def run(self):
        try:
            from src.core.watcher import FolderWatcher
            self._watcher = FolderWatcher()
            self._watcher.start(self.watch_dir, self._on_new_file)
            # Keep thread alive while watching
            while self._watcher.is_watching:
                self.msleep(500)
        except Exception as e:
            self.error.emit(str(e))

    def _on_new_file(self, path: Path):
        self.new_file.emit(str(path))

    def stop_watching(self):
        if self._watcher:
            self._watcher.stop()
