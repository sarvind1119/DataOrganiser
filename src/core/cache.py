"""SQLite-based classification cache to avoid re-classifying unchanged files."""

from __future__ import annotations

import sqlite3
import logging
from pathlib import Path

from src.core.config import CONFIG_DIR
from src.core.models import FileCategory, FileInfo

logger = logging.getLogger(__name__)

CACHE_DB = CONFIG_DIR / "classification_cache.db"


class ClassificationCache:
    """Cache classification results keyed by file path + size + mtime."""

    def __init__(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(CACHE_DB))
        self._create_table()

    def _create_table(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS cache (
                file_path TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                modified_time REAL NOT NULL,
                category TEXT NOT NULL,
                confidence REAL NOT NULL,
                PRIMARY KEY (file_path, file_size, modified_time)
            )
        """)
        self.conn.commit()

    def get(self, fi: FileInfo) -> tuple[FileCategory, float] | None:
        """Look up cached classification. Returns None if not found or stale."""
        cursor = self.conn.execute(
            "SELECT category, confidence FROM cache "
            "WHERE file_path = ? AND file_size = ? AND modified_time = ?",
            (str(fi.path), fi.size_bytes, fi.modified_time),
        )
        row = cursor.fetchone()
        if row:
            try:
                category = FileCategory(row[0])
                return category, row[1]
            except ValueError:
                return None
        return None

    def put(self, fi: FileInfo):
        """Store classification result in cache."""
        if fi.category is None:
            return
        self.conn.execute(
            "INSERT OR REPLACE INTO cache (file_path, file_size, modified_time, category, confidence) "
            "VALUES (?, ?, ?, ?, ?)",
            (str(fi.path), fi.size_bytes, fi.modified_time, fi.category.value, fi.confidence),
        )
        self.conn.commit()

    def clear(self):
        """Clear entire cache."""
        self.conn.execute("DELETE FROM cache")
        self.conn.commit()
        logger.info("Classification cache cleared")

    def stats(self) -> dict:
        """Return cache statistics."""
        cursor = self.conn.execute("SELECT COUNT(*) FROM cache")
        total = cursor.fetchone()[0]
        return {"total_entries": total, "db_path": str(CACHE_DB)}

    def close(self):
        self.conn.close()
