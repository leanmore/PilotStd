# tests/integration/test_monitor_archive_e2e.py
"""技术债 #30 端到端：monitor 的 `_on_file` 真归档 + 计数口径。

与单元测试的区别：不 mock 管理器，而是用「真遍历目录 + 真解析 + 真搬文件 +
真写 `file_index`」的替身（只实现 monitor 用到的那一面），验证三件事：
① 合规文件**真的**被搬出 inbox 并写进索引；② 计数按真实归档结果记 success；
③ 不合规文件留在 inbox 且记 failed（不再谎报成功）。
"""

from __future__ import annotations

import contextlib
import os
import shutil
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from pilotstd.core.db import Database  # noqa: E402
from pilotstd.core.file_index import FileIndexRepository  # noqa: E402
from pilotstd.monitor.scheduler import FileMonitorScheduler  # noqa: E402
from pilotstd.organizer.industry_lookup import build_code_mapping  # noqa: E402
from pilotstd.scan.parser import StandardParser  # noqa: E402

_PDF_BYTES = b"%PDF-1.4 fake standard full text"


class _RealArchiveMgr:
    """真扫目录 + 真解析 + 真归档 + 真写索引的管理器替身。

    `scan_directory` 与门面同口径：遍历目录 → 用 `StandardParser` 解析文件名 →
    把 `source_path` 指回真实文件（monitor 只给它一个目录，解析源就是文件名本身）。
    """

    def __init__(self, db, dst_dir: Path):
        self._parser = StandardParser(build_code_mapping())
        self._repo = FileIndexRepository(db)
        self._dst_dir = dst_dir
        self.moved: list[str] = []
        self.source_roots: list[str] = []

    def scan_directory(self, root_path: str):
        parsed = []
        for f in sorted(Path(root_path).glob("*.pdf")):
            info = self._parser.parse(f.name)
            if info:
                info.source_path = str(f)
                info.raw_filename = f.name
                parsed.append(info)
        return parsed

    def archive_standards(self, parsed_list, word_source_root=None):
        self.source_roots.append(str(word_source_root))
        for item in parsed_list:
            self._dst_dir.mkdir(parents=True, exist_ok=True)
            dst = str(self._dst_dir / Path(item.source_path).name)
            shutil.move(item.source_path, dst)
            self.moved.append(item.source_path)
            self._repo.upsert(
                file_path=dst,
                logical_code=item.logical_code,
                number=item.number,
                year=item.year,
                std_name="测试标准",
                status="现行",
            )
        return {"moved": len(parsed_list), "failed": 0, "details": []}


def _counts(mock_stats) -> dict[str, int]:
    out: dict[str, int] = {}
    for c in mock_stats.increment.call_args_list:
        out[c.args[0]] = out.get(c.args[0], 0) + 1
    return out


@contextlib.contextmanager
def _run_on_file(mgr, path: str, tmp_path: Path):
    """真实 DB + 真实管理器替身跑一次 `_on_file`，返回 (stats, 真实数据库)。"""
    db_path = str(tmp_path / "monitor.db")
    Database(db_path).close()
    db = Database(db_path)
    real_mgr = _RealArchiveMgr(db, tmp_path / "library") if mgr is None else mgr
    scheduler = FileMonitorScheduler(manager=real_mgr)
    stats = MagicMock()
    with patch(
        "pilotstd.monitor.scheduler.get_config", return_value={"auto_archive": True}
    ), patch("pilotstd.monitor.scheduler.get_monitor_stats", return_value=stats):
        scheduler._on_file(path)
    try:
        yield stats, db
    finally:
        db.close()


@pytest.mark.integration
class TestMonitorArchiveEndToEnd:
    def test_valid_file_is_archived_and_counted_success(self, tmp_path):
        """合规文件：搬出 inbox + 真写 file_index（可用真查询命中）+ success=1。"""
        inbox = tmp_path / "inbox"
        inbox.mkdir()
        src = inbox / "GB 19001-2020 质量管理体系.pdf"
        src.write_bytes(_PDF_BYTES)

        with _run_on_file(None, str(src), tmp_path) as (stats, db):
            assert not src.exists(), "归档后源文件必须离开 inbox"
            rows = db.fetchall("SELECT file_path, logical_code, number, year FROM file_index")
            assert len(rows) == 1, rows
            assert rows[0]["logical_code"] == "GB"
            assert (rows[0]["number"], rows[0]["year"]) == (19001, 2020)
            assert Path(rows[0]["file_path"]).read_bytes() == _PDF_BYTES

        assert _counts(stats) == {"processed": 1, "success": 1}, _counts(stats)

    def test_archive_gets_inbox_dir_as_source_root(self, tmp_path):
        """契约：`word_source_root` 必须是 inbox 目录（organizer 据此镜像 Word 相对路径）。"""
        inbox = tmp_path / "inbox"
        inbox.mkdir()
        src = inbox / "GB 19001-2020 质量管理体系.pdf"
        src.write_bytes(_PDF_BYTES)

        db_path = str(tmp_path / "monitor.db")
        Database(db_path).close()
        db = Database(db_path)
        try:
            mgr = _RealArchiveMgr(db, tmp_path / "library")
            scheduler = FileMonitorScheduler(manager=mgr)
            with patch(
                "pilotstd.monitor.scheduler.get_config",
                return_value={"auto_archive": True},
            ), patch("pilotstd.monitor.scheduler.get_monitor_stats", return_value=MagicMock()):
                scheduler._on_file(str(src))
            assert mgr.source_roots == [str(inbox)], mgr.source_roots
        finally:
            db.close()

    def test_unparsable_file_stays_in_inbox_and_counts_failed(self, tmp_path):
        """场景 3：不合规文件（解析不出标准号）→ 留在 inbox + failed=1，不记 success。"""
        inbox = tmp_path / "inbox"
        inbox.mkdir()
        src = inbox / "scan_0001.pdf"
        src.write_bytes(_PDF_BYTES)

        with _run_on_file(None, str(src), tmp_path) as (stats, db):
            assert src.exists(), "解析失败的文件不得被搬走"
            assert db.fetchall("SELECT * FROM file_index") == []

        assert _counts(stats) == {"processed": 1, "failed": 1}, _counts(stats)

    def test_auto_archive_disabled_does_not_touch_inbox(self, tmp_path):
        """`auto_archive=false` 时确实什么都不做（含计数）——开关不再是"名不副实"。"""
        inbox = tmp_path / "inbox"
        inbox.mkdir()
        src = inbox / "GB 19001-2020 质量管理体系.pdf"
        src.write_bytes(_PDF_BYTES)

        db_path = str(tmp_path / "monitor.db")
        Database(db_path).close()
        db = Database(db_path)
        try:
            mgr = _RealArchiveMgr(db, tmp_path / "library")
            scheduler = FileMonitorScheduler(manager=mgr)
            stats = MagicMock()
            with patch(
                "pilotstd.monitor.scheduler.get_config",
                return_value={"auto_archive": False},
            ), patch("pilotstd.monitor.scheduler.get_monitor_stats", return_value=stats):
                scheduler._on_file(str(src))
            assert src.exists() and not mgr.moved
            stats.increment.assert_not_called()
        finally:
            db.close()
