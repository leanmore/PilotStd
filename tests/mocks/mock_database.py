# tests/mocks/mock_database.py — 可复用的内存 SQLite Database mock
"""支持 with 语句的内存数据库，兼容 Database 接口的关键方法。"""

from __future__ import annotations

import sqlite3
import threading
from typing import Any, Optional, Sequence


class MockDatabase:
    """内存 SQLite 数据库，兼容 pilotstd.core.db.Database 接口。

    用法:
        with MockDatabase() as db:
            db.execute("CREATE TABLE test (id INTEGER)")
            db.execute("INSERT INTO test VALUES (1)")
            rows = db.fetchall("SELECT * FROM test")
    """

    def __init__(self, init_sql: str | None = None) -> None:
        self._conn = sqlite3.connect(":memory:", check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._local = threading.local()
        if init_sql:
            self._conn.executescript(init_sql)

    def __enter__(self) -> MockDatabase:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    @property
    def _cursor(self) -> sqlite3.Cursor:
        if not hasattr(self._local, "cursor") or self._local.cursor is None:
            self._local.cursor = self._conn.cursor()
        return self._local.cursor

    def execute(self, sql: str, params: Sequence[Any] = ()) -> sqlite3.Cursor:
        cur = self._cursor
        cur.execute(sql, params)
        self._conn.commit()
        return cur

    def executemany(self, sql: str, seq: Sequence[Any]) -> sqlite3.Cursor:
        cur = self._cursor
        cur.executemany(sql, seq)
        self._conn.commit()
        return cur

    def fetchall(self, sql: str, params: Sequence[Any] = ()) -> list[dict[str, Any]]:
        cur = self._cursor
        cur.execute(sql, params)
        rows = cur.fetchall()
        return [dict(r) for r in rows]

    def fetchone(self, sql: str, params: Sequence[Any] = ()) -> Optional[dict[str, Any]]:
        cur = self._cursor
        cur.execute(sql, params)
        row = cur.fetchone()
        return dict(row) if row else None

    def close(self) -> None:
        if hasattr(self._local, "cursor") and self._local.cursor:
            self._local.cursor.close()
            self._local.cursor = None
        try:
            self._conn.close()
        except Exception:
            pass
