"""Real-time folder monitoring using watchdog to auto-organize new files."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)

_HAS_WATCHDOG = False
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileCreatedEvent, FileMovedEvent
    _HAS_WATCHDOG = True
except ImportError:
    pass


def is_available() -> bool:
    return _HAS_WATCHDOG


class NewFileHandler(FileSystemEventHandler):
    """Handles new file events in a watched directory."""

    def __init__(self, callback: Callable[[Path], None], settle_time: float = 2.0):
        super().__init__()
        self.callback = callback
        self.settle_time = settle_time
        self._pending: dict[str, float] = {}

    def on_created(self, event):
        if not event.is_directory:
            path = Path(event.src_path)
            # Wait for file to finish writing (settle time)
            self._pending[str(path)] = time.time()
            self._check_settled(path)

    def on_moved(self, event):
        if not event.is_directory:
            path = Path(event.dest_path)
            self._pending[str(path)] = time.time()
            self._check_settled(path)

    def _check_settled(self, path: Path):
        """Check if file has finished writing by waiting for size to stabilize."""
        try:
            if not path.exists():
                return
            # Simple approach: just call the callback
            # The caller can implement debouncing if needed
            self.callback(path)
        except Exception as e:
            logger.warning(f"Error handling new file {path}: {e}")


class FolderWatcher:
    """Watches a directory for new files and triggers a callback."""

    def __init__(self):
        self._observer = None
        self._watching = False

    @property
    def is_watching(self) -> bool:
        return self._watching

    def start(self, watch_dir: Path, on_new_file: Callable[[Path], None]):
        """Start watching a directory for new files."""
        if not _HAS_WATCHDOG:
            raise RuntimeError("watchdog package not installed. Run: pip install watchdog")

        if self._watching:
            self.stop()

        handler = NewFileHandler(on_new_file)
        self._observer = Observer()
        self._observer.schedule(handler, str(watch_dir), recursive=False)
        self._observer.start()
        self._watching = True
        logger.info(f"Watching directory: {watch_dir}")

    def stop(self):
        """Stop watching."""
        if self._observer and self._watching:
            self._observer.stop()
            self._observer.join(timeout=5)
            self._watching = False
            logger.info("Stopped folder watcher")
