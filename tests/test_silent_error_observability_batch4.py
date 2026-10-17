"""静默吞错第 4 批：文件工具 / 连接关闭 / 路由埋点（体检 D-8）。

- `hash_file_content`：getsize/读取失败原直接返回 ""（等于"该文件没有指纹"）；
- `Database.close/close_all`：连接关闭失败被 pass（连接泄漏不可见）；
- `router_v2_metrics`：埋点写盘/入队失败被 pass（"没有决策日志"无法归因）。
"""

from __future__ import annotations

import logging
import threading
from unittest.mock import MagicMock


def test_hash_file_content_missing_path_logs(caplog) -> None:
    from pilotstd.core.file_utils import hash_file_content

    with caplog.at_level(logging.DEBUG, logger="pilotstd.core.file_utils"):
        assert hash_file_content("/definitely/not/here.pdf") == ""
    assert "getsize failed" in caplog.text


def test_hash_file_content_unreadable_path_logs(tmp_path, caplog) -> None:
    from pilotstd.core.file_utils import hash_file_content

    directory = tmp_path / "a_directory"
    directory.mkdir()
    with caplog.at_level(logging.DEBUG, logger="pilotstd.core.file_utils"):
        assert hash_file_content(str(directory)) == ""
    assert "read failed" in caplog.text


def test_database_close_failure_logs(caplog) -> None:
    from pilotstd.core.db.database import Database

    db = object.__new__(Database)
    db._local = threading.local()
    conn = MagicMock()
    conn.close.side_effect = RuntimeError("close boom")
    db._local.conn = conn

    with caplog.at_level(logging.DEBUG, logger="pilotstd.db"):
        db.close()
    assert "close connection failed" in caplog.text


def test_database_close_all_failure_logs(caplog) -> None:
    from pilotstd.core.db.database import Database

    db = object.__new__(Database)
    db._local = threading.local()
    conn = MagicMock()
    conn.close.side_effect = RuntimeError("close boom")
    db._all_conns = [conn]

    with caplog.at_level(logging.DEBUG, logger="pilotstd.db"):
        db.close_all()
    assert "close_all connection failed" in caplog.text


def test_record_decision_enqueue_failure_logs(monkeypatch, caplog) -> None:
    from pilotstd.query.routing import router_v2_metrics as metrics

    monkeypatch.setattr(metrics, "_start_writer", lambda: None)

    class _BrokenQueue:
        def put(self, item) -> None:
            raise RuntimeError("queue full")

    monkeypatch.setattr(metrics, "_queue", _BrokenQueue())

    with caplog.at_level(logging.DEBUG, logger="pilotstd.query.routing.router_v2_metrics"):
        metrics.record_decision({"query": "x"})
    assert "router metrics enqueue failed" in caplog.text
