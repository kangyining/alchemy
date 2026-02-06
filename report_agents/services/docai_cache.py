"""Persistent cache for Document AI results to minimize costs."""

import hashlib
import json
import logging
import sqlite3
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Persistent location for cross-session caching
CACHE_DB_PATH = Path("/tmp/report_agents/docai_global_cache.db")


class DocAICache:
    """Manages a persistent SQLite cache for Document AI results."""

    def __init__(self, db_path: Path = CACHE_DB_PATH):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _init_schema(self) -> None:
        """Initialize the cache table."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS docai_cache (
                    content_hash TEXT PRIMARY KEY,
                    parsed_result_json TEXT NOT NULL,
                    mime_type TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    @staticmethod
    def compute_hash(content: bytes) -> str:
        """Compute SHA-256 hash of document content."""
        return hashlib.sha256(content).hexdigest()

    def get(self, content: bytes) -> Optional[dict[str, Any]]:
        """Retrieve cached result if content hash exists."""
        content_hash = self.compute_hash(content)
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT parsed_result_json FROM docai_cache WHERE content_hash = ?",
                (content_hash,)
            )
            row = cursor.fetchone()
            if row:
                logger.info("DocAI Cache HIT for hash %s...", content_hash[:10])
                return json.loads(row["parsed_result_json"])
        return None

    def set(self, content: bytes, result: dict[str, Any], mime_type: str = "") -> None:
        """Store Document AI result in cache."""
        content_hash = self.compute_hash(content)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO docai_cache (content_hash, parsed_result_json, mime_type)
                VALUES (?, ?, ?)
            """,
                (content_hash, json.dumps(result), mime_type)
            )
            conn.commit()
        logger.info("DocAI Cache STORE for hash %s...", content_hash[:10])


# Global singleton for easy access
_global_cache = None


def get_docai_cache() -> DocAICache:
    global _global_cache
    if _global_cache is None:
        _global_cache = DocAICache()
    return _global_cache
