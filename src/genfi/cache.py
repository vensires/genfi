"""SQLite cache for tracking generated icons and skipping unchanged folders."""

import hashlib
import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)


class IconCache:
    """Track which folders have been processed and when."""

    def __init__(self, cache_dir: Path):
        self.db_path = cache_dir / "genfi_cache.db"
        cache_dir.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            try:
                conn.execute("SELECT media_hash, media_count FROM folders LIMIT 1")
            except sqlite3.OperationalError:
                conn.execute("DROP TABLE IF EXISTS folders")
                conn.execute("""
                    CREATE TABLE folders (
                        path TEXT PRIMARY KEY,
                        icon_path TEXT NOT NULL,
                        folder_mtime REAL NOT NULL,
                        media_hash TEXT NOT NULL,
                        media_count INTEGER NOT NULL
                    )
                """)
                logging.info("Cache schema recreated")

    def needs_update(self, folder: Path, videos: list[Path], images: list[Path]) -> bool:
        """Return True if the folder needs icon regeneration."""
        try:
            folder_mtime = folder.stat().st_mtime
        except OSError:
            return True

        media_hash = _hash_media(videos + images)
        media_count = len(videos) + len(images)

        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT folder_mtime, media_hash, media_count FROM folders WHERE path = ?",
                (str(folder),),
            ).fetchone()

            if row is None:
                return True

            return row[0] != folder_mtime or row[1] != media_hash or row[2] != media_count

    def record(self, folder: Path, icon_path: Path, videos: list[Path], images: list[Path]):
        """Record that a folder has been processed."""
        try:
            folder_mtime = folder.stat().st_mtime
        except OSError:
            folder_mtime = 0.0

        media_hash = _hash_media(videos + images)
        media_count = len(videos) + len(images)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO folders
                   (path, icon_path, folder_mtime, media_hash, media_count)
                   VALUES (?, ?, ?, ?, ?)""",
                (str(folder), str(icon_path), folder_mtime, media_hash, media_count),
            )

    def get_all(self) -> list[tuple[str, str]]:
        """Return list of (folder_path, icon_path) for all cached entries."""
        with sqlite3.connect(self.db_path) as conn:
            return conn.execute("SELECT path, icon_path FROM folders").fetchall()

    def remove(self, folder: Path):
        """Remove cache entry for a folder."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM folders WHERE path = ?", (str(folder),))

    def clear(self):
        """Remove all cache entries."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM folders")


def _hash_media(paths: list[Path]) -> str:
    """Create a hash from file stats to detect changes."""
    parts = []
    for p in paths:
        try:
            st = p.stat()
            parts.append(f"{p.name}:{st.st_mtime}:{st.st_size}")
        except OSError:
            parts.append(f"{p.name}:0:0")
    return hashlib.sha256("".join(parts).encode()).hexdigest()[:16]
