"""
Database Connection Manager and SQLite Persistence Provider.
Ensures thread-safe, local, WAL-mode relational state storage.
"""

import contextlib
import logging
import os
import sqlite3
import threading
from pathlib import Path
from typing import Any, Dict, Generator, Optional

from config.settings import settings
from src.persistence.exceptions import PersistenceError

logger = logging.getLogger("MRPL.Persistence.Database")


class DatabaseManager:
    """
    Thread-safe SQLite Database Manager for MRPL AI Workbench.
    Enforces local WAL mode, foreign keys, connection pooling/context, and transaction boundaries.
    """

    CURRENT_SCHEMA_VERSION = 2


    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.db_path = Path(db_path or settings.AGENT_DATABASE_PATH).resolve()
        self._lock = threading.Lock()
        self._local = threading.local()

        # Ensure parent directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize_database()

    def get_raw_connection(self) -> sqlite3.Connection:
        """
        Create a configured, thread-local SQLite connection with dict row factory.
        """
        if not hasattr(self._local, "connection") or self._local.connection is None:
            conn = sqlite3.connect(
                str(self.db_path),
                timeout=30.0,
                check_same_thread=False,
            )
            conn.row_factory = sqlite3.Row
            # Enable WAL mode and foreign keys for performance and safety
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA foreign_keys=ON;")
            self._local.connection = conn
        return self._local.connection

    @contextlib.contextmanager
    def transaction(self) -> Generator[sqlite3.Connection, None, None]:
        """
        Context manager providing atomic transaction execution.
        """
        conn = self.get_raw_connection()
        with self._lock:
            try:
                conn.execute("BEGIN IMMEDIATE;")
                yield conn
                conn.commit()
            except Exception as exc:
                conn.rollback()
                logger.error(f"Database transaction error, rolling back: {exc}")
                raise PersistenceError(f"Database transaction failed: {str(exc)}") from exc

    def initialize_database(self) -> None:
        """
        Initialize database schema tables, indexes, and version tracking if missing.
        """
        conn = self.get_raw_connection()
        with self._lock:
            try:
                # 1. Version tracking table
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS schema_info (
                        version INTEGER PRIMARY KEY,
                        installed_at TEXT NOT NULL
                    );
                    """
                )

                # 2. Check current version
                cursor = conn.execute("SELECT MAX(version) as ver FROM schema_info;")
                row = cursor.fetchone()
                current_ver = row["ver"] if row and row["ver"] is not None else 0

                if current_ver < self.CURRENT_SCHEMA_VERSION:
                    from src.persistence.migrations import run_migrations
                    run_migrations(conn, current_ver, self.CURRENT_SCHEMA_VERSION)
                    conn.commit()
            except Exception as exc:
                conn.rollback()
                logger.error(f"Failed to initialize database schema: {exc}", exc_info=True)
                raise PersistenceError(f"Database schema initialization failed: {exc}") from exc

    def get_database_status(self) -> Dict[str, Any]:
        """
        Retrieve sanitized database status telemetry.
        """

    def get_status(self) -> Dict[str, Any]:
        """
        Retrieve sanitized persistence telemetry.
        """
        size_bytes = 0
        if self.db_path.exists():
            size_bytes = self.db_path.stat().st_size

        return {
            "enabled": settings.AGENT_PERSISTENCE_ENABLED,
            "provider": "SQLite",
            "status": "healthy" if self.db_path.exists() else "not_created",
            "database_name": self.db_path.name,
            "database_size_mb": round(size_bytes / (1024 * 1024), 2),
            "schema_version": self.CURRENT_SCHEMA_VERSION,
            "wal_mode": True,
        }


# Singleton Provider
_db_manager_instance: Optional[DatabaseManager] = None


def get_db_manager() -> DatabaseManager:
    """Singleton getter for DatabaseManager."""
    global _db_manager_instance
    if _db_manager_instance is None:
        _db_manager_instance = DatabaseManager()
    return _db_manager_instance
