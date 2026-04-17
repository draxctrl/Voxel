"""SQLite-based dictation history store for Voxel."""

from __future__ import annotations

import os
import platform
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path


def _default_db_path() -> str:
    """Return the platform-appropriate path for history.db."""
    system = platform.system()
    if system == "Windows":
        base = os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")
        return str(Path(base) / "Voxel" / "history.db")
    elif system == "Darwin":
        return str(Path.home() / "Library" / "Application Support" / "Voxel" / "history.db")
    else:
        config = os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")
        return str(Path(config) / "Voxel" / "history.db")


_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS dictations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    raw_text TEXT NOT NULL,
    cleaned_text TEXT NOT NULL,
    language TEXT DEFAULT 'en',
    duration_s REAL DEFAULT 0,
    word_count INTEGER DEFAULT 0,
    profile TEXT DEFAULT 'default'
)
"""


class HistoryStore:
    """Thread-safe SQLite store for dictation history."""

    def __init__(self, db_path: str | None = None) -> None:
        self._db_path = db_path or _default_db_path()
        os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute(_CREATE_TABLE)
        self._conn.commit()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add(
        self,
        raw_text: str,
        cleaned_text: str,
        language: str = "en",
        duration: float = 0.0,
        profile: str = "default",
    ) -> int:
        """Insert a dictation and return its id."""
        word_count = len(cleaned_text.split()) if cleaned_text.strip() else 0
        timestamp = datetime.now(timezone.utc).isoformat()
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO dictations (timestamp, raw_text, cleaned_text, language, duration_s, word_count, profile) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (timestamp, raw_text, cleaned_text, language, duration, word_count, profile),
            )
            self._conn.commit()
            return cur.lastrowid  # type: ignore[return-value]

    def search(self, query: str, limit: int = 100) -> list[dict]:
        """Search raw_text and cleaned_text using LIKE."""
        pattern = f"%{query}%"
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM dictations WHERE raw_text LIKE ? OR cleaned_text LIKE ? "
                "ORDER BY id DESC LIMIT ?",
                (pattern, pattern, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_recent(self, limit: int = 50) -> list[dict]:
        """Return the most recent dictations, newest first."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM dictations ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def delete(self, entry_id: int) -> None:
        """Delete a single dictation by id."""
        with self._lock:
            self._conn.execute("DELETE FROM dictations WHERE id = ?", (entry_id,))
            self._conn.commit()

    def clear_all(self) -> None:
        """Remove every dictation from the store."""
        with self._lock:
            self._conn.execute("DELETE FROM dictations")
            self._conn.commit()

    def get_last(self) -> dict | None:
        """Return the most recently added dictation, or None."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM dictations ORDER BY id DESC LIMIT 1"
            ).fetchone()
        return dict(row) if row else None

    def count(self) -> int:
        """Return the total number of stored dictations."""
        with self._lock:
            row = self._conn.execute("SELECT COUNT(*) FROM dictations").fetchone()
        return row[0]

    def total_words(self) -> int:
        """Return the sum of word_count across all dictations."""
        with self._lock:
            row = self._conn.execute("SELECT COALESCE(SUM(word_count), 0) FROM dictations").fetchone()
        return row[0]

    def total_duration(self) -> float:
        """Return the sum of duration_s across all dictations."""
        with self._lock:
            row = self._conn.execute("SELECT COALESCE(SUM(duration_s), 0.0) FROM dictations").fetchone()
        return row[0]

    def most_used_profile(self) -> str:
        """Return the profile name with the most dictations, or 'N/A'."""
        with self._lock:
            row = self._conn.execute(
                "SELECT profile FROM dictations GROUP BY profile ORDER BY COUNT(*) DESC LIMIT 1"
            ).fetchone()
        return row[0] if row else "N/A"

    def today_count(self) -> int:
        """Return the number of dictations recorded today (UTC)."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        with self._lock:
            row = self._conn.execute(
                "SELECT COUNT(*) FROM dictations WHERE timestamp LIKE ?",
                (f"{today}%",),
            ).fetchone()
        return row[0]

    def week_count(self) -> int:
        """Return the number of dictations recorded in the last 7 days."""
        from datetime import timedelta
        cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        with self._lock:
            row = self._conn.execute(
                "SELECT COUNT(*) FROM dictations WHERE timestamp >= ?",
                (cutoff,),
            ).fetchone()
        return row[0]
