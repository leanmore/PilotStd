"""CI run 1066 的两处回归（2026-10-17/18 跨日）。

1. `watcher._handle_new_or_modified` 在哈希计算抛 OSError 时不得再抛
   `UnboundLocalError`（日志不能引用尚未绑定的 file_hash）；
2. `file_index.clear_stale` 的 last_checked 必须按**本地日期**刷新
   （原 UTC 在本地 00:00–08:00 会写成前一天）。
"""

from __future__ import annotations

import logging
import threading
from datetime import date
from unittest.mock import MagicMock


def test_watcher_oserror_does_not_raise_unbound(monkeypatch, caplog) -> None:
    from pilotstd.scan.watcher import FileWatchHandler

    handler = object.__new__(FileWatchHandler)
    handler._should_skip = lambda path: False
    handler._parser = MagicMock()
    handler._file_index = MagicMock()

    def broken_hash(path: str) -> str:
        raise OSError("permission denied")

    monkeypatch.setattr("pilotstd.core.file_utils.hash_file_content", broken_hash)

    with caplog.at_level(logging.DEBUG, logger="pilotstd.scan.watcher"):
        handler._handle_new_or_modified("C:/tmp/x.pdf")  # 不应抛

    assert "watcher index file failed" in caplog.text


def test_clear_stale_refreshes_to_local_today(tmp_path, caplog) -> None:
    from pilotstd.core.db import Database
    from pilotstd.core.file_index import FileIndexRepository

    db = Database(str(tmp_path / "idx.db"))
    repo = object.__new__(FileIndexRepository)
    repo._db = db
    repo._stop_event = threading.Event()
    repo._validation_complete = threading.Event()

    target = tmp_path / "real.pdf"
    target.write_bytes(b"x")
    db.execute(
        "INSERT INTO file_index (file_path, logical_code, number, year, last_checked)"
        " VALUES (?, 'GB', 5, 2020, date('now', '-10 days'))",
        (str(target),),
    )

    assert repo.clear_stale() == 0
    row = db.fetchone("SELECT last_checked FROM file_index WHERE file_path = ?", (str(target),))
    assert row is not None
    assert row["last_checked"] == date.today().isoformat()
    db.close()
