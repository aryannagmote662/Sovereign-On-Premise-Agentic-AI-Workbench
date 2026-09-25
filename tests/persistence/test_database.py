"""
Unit tests for DatabaseManager, connection pooling, and schema migrations.
"""

import sqlite3
import pytest
from src.persistence.database import DatabaseManager


def test_database_manager_initialization(tmp_path):
    db_file = tmp_path / "test_mrpl.db"
    db_mgr = DatabaseManager(db_path=db_file)

    assert db_file.exists()
    status = db_mgr.get_status()
    assert status["status"] == "healthy"
    assert status["schema_version"] == 2


def test_database_transaction_and_rollback(tmp_path):
    db_file = tmp_path / "test_tx.db"
    db_mgr = DatabaseManager(db_path=db_file)

    # Failed transaction rolls back
    with pytest.raises(Exception):
        with db_mgr.transaction() as conn:
            conn.execute(
                "INSERT INTO agent_tasks (task_id, user_id, session_id, task_type, title, query, status, risk_level, requires_approval, approval_status, created_at, updated_at) VALUES ('t1', 'u1', 's1', 'CHAT', 'title', 'query', 'CREATED', 'LOW', 0, 'NOT_REQUIRED', 'now', 'now');"
            )
            raise RuntimeError("Force rollback")

    # Verify record was not saved
    conn = db_mgr.get_raw_connection()
    row = conn.execute("SELECT * FROM agent_tasks WHERE task_id = 't1';").fetchone()
    assert row is None
