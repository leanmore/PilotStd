"""B4：`database is locked` 的指数退避重试。"""

import sqlite3
from unittest.mock import MagicMock

import pytest

from pilotstd.core.db import Database, DatabaseError


def test_execute_retries_when_locked(tmp_path, monkeypatch):
    db = Database(str(tmp_path / "retry.db"))
    conn = MagicMock()
    cursor = MagicMock()
    conn.execute.side_effect = [
        sqlite3.OperationalError("database is locked"),
        sqlite3.OperationalError("database is locked"),
        cursor,
    ]
    monkeypatch.setattr(db, "_get_conn", lambda: conn)
    monkeypatch.setattr("pilotstd.core.db.database.time.sleep", lambda _s: None)
    assert db.execute("UPDATE t SET x=1") is cursor
    assert conn.execute.call_count == 3
    conn.commit.assert_called_once()
    db.close()


def test_execute_raises_after_retry_exhausted(tmp_path, monkeypatch):
    db = Database(str(tmp_path / "retry2.db"))
    conn = MagicMock()
    conn.execute.side_effect = sqlite3.OperationalError("database is locked")
    monkeypatch.setattr(db, "_get_conn", lambda: conn)
    monkeypatch.setattr("pilotstd.core.db.database.time.sleep", lambda _s: None)
    with pytest.raises(DatabaseError):
        db.execute("UPDATE t SET x=1")
    assert conn.execute.call_count == 3
    db.close()
