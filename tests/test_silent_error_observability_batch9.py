"""静默吞错第 9 批：锁清理 / 回滚 / 缓存 JSON / 在线校验回退（体检 D-8）。

- 迁移锁删除失败原 pass（锁残留不可见）；
- SQL 失败后的 rollback 失败原 pass（二次失败被吞）；
- 文件索引缓存 JSON 非法原 pass（回填静默失效）；
- `validity_checker` 在线查询失败原 pass（静默回落历史对比）。
"""

from __future__ import annotations

import logging
import sqlite3
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


@pytest.fixture()
def db(tmp_path):
    from pilotstd.core.db import Database

    database = Database(str(tmp_path / "batch9.db"))
    yield database
    database.close()


def test_rollback_failure_logs(db, caplog) -> None:
    from pilotstd.core.db import DatabaseError

    conn = MagicMock()
    conn.execute.side_effect = sqlite3.OperationalError("disk I/O error")
    conn.rollback.side_effect = RuntimeError("rollback broke")
    db._get_conn = lambda: conn

    with caplog.at_level(logging.DEBUG, logger="pilotstd.db"):
        with pytest.raises(DatabaseError):
            db.execute("UPDATE t SET x=1")
    assert "rollback failed" in caplog.text


def test_release_migration_lock_failure_logs(db, monkeypatch, caplog) -> None:
    db._migration_lock_path = str(__import__("pathlib").Path("no-such-dir") / "lock")

    with caplog.at_level(logging.DEBUG, logger="pilotstd.db"):
        db._release_migration_lock()
    assert "remove migration lock failed" in caplog.text


def test_cached_json_invalid_logs(caplog) -> None:
    from pilotstd.core._file_index_query import FileIndexQuery

    info = SimpleNamespace(effect_status="", found_name="", is_adopted=False, match_status="", std_name="")
    with caplog.at_level(logging.DEBUG, logger="pilotstd.core._file_index_query"):
        FileIndexQuery._apply_cache_result("{bad json", info)
    assert "cached parsed JSON invalid" in caplog.text
