"""静默吞错第 2 批：适配器状态 / 文件索引 / 缓存统计（体检 D-8/D-9）。

覆盖 11 处此前无痕迹的失败：
- AdapterManager：健康读取、frozen_until 解析、全量健康读取；
- FileIndexQuery：状态统计返回全 0；
- FileIndexRepository：close_all、延迟查询、启动校验、路径查询；
- CacheManager：dbstat / pragma / 行数估算三级回退的 debug 痕迹。
"""

from __future__ import annotations

import logging
import threading
from unittest.mock import MagicMock


def test_adapter_health_read_failure_logs(caplog) -> None:
    from pilotstd.manager.adapter_manager import AdapterManager

    db = MagicMock()
    db.fetchone.side_effect = RuntimeError("db down")
    mgr = AdapterManager(db, None, None)
    with caplog.at_level(logging.WARNING, logger="pilotstd.manager.adapter_manager"):
        status = mgr.get_adapter_status("std_gov")
    assert status["status"] == "normal"
    assert "adapter health read failed" in caplog.text


def test_invalid_frozen_until_logs(caplog) -> None:
    from pilotstd.manager.adapter_manager import AdapterManager

    db = MagicMock()
    db.fetchone.return_value = {"frozen_until": "not-a-date", "freeze_count": 0, "fail_streak": 0}
    mgr = AdapterManager(db, None, None)
    with caplog.at_level(logging.WARNING, logger="pilotstd.manager.adapter_manager"):
        status = mgr.get_adapter_status("std_gov")
    assert status["status"] == "normal"
    assert "invalid frozen_until" in caplog.text


def test_get_all_health_failure_logs_and_returns_empty(caplog) -> None:
    from pilotstd.manager.adapter_manager import AdapterManager

    db = MagicMock()
    db.fetchall.side_effect = RuntimeError("db down")
    mgr = AdapterManager(db, None, None)
    with caplog.at_level(logging.WARNING, logger="pilotstd.manager.adapter_manager"):
        assert mgr.get_all_health() == []
    assert "get_all_health failed" in caplog.text


def test_file_index_status_stats_failure_logs_zeros(caplog) -> None:
    from pilotstd.core._file_index_query import FileIndexQuery

    db = MagicMock()
    db.fetchall.side_effect = RuntimeError("db down")
    query = FileIndexQuery(db)
    with caplog.at_level(logging.WARNING, logger="pilotstd.core._file_index_query"):
        assert query.get_status_stats() == {"current": 0, "expired": 0, "pending": 0, "upcoming": 0}
    assert "get_status_stats failed" in caplog.text


def _bare_file_index(db) -> "object":
    from pilotstd.core.file_index import FileIndexRepository

    repo = object.__new__(FileIndexRepository)
    repo._db = db
    repo._stop_event = threading.Event()
    repo._validation_complete = threading.Event()
    return repo


def test_validate_paths_query_failure_logs_and_returns_zero(caplog) -> None:
    db = MagicMock()
    db.fetchall.side_effect = RuntimeError("db down")
    repo = _bare_file_index(db)
    with caplog.at_level(logging.WARNING, logger="pilotstd.core.file_index"):
        assert repo.validate_paths() == 0
    assert "validate_paths query failed" in caplog.text


def test_file_index_stop_logs_close_failure(caplog) -> None:
    db = MagicMock()
    db.close_all.side_effect = RuntimeError("close boom")
    repo = _bare_file_index(db)
    repo._validation_thread = None
    with caplog.at_level(logging.DEBUG, logger="pilotstd.core.file_index"):
        repo.stop()
    assert "close_all failed during stop" in caplog.text


def test_cache_database_size_fallback_logs(caplog) -> None:
    from pilotstd.core.cache_manager import CacheManager

    db = MagicMock()
    db.fetchone.side_effect = RuntimeError("no dbstat")
    cache = object.__new__(CacheManager)
    cache._db = db
    with caplog.at_level(logging.DEBUG, logger="pilotstd.core.cache_manager"):
        size = cache.get_total_size_mb()
    assert size >= 0
    assert "dbstat size probe failed" in caplog.text
