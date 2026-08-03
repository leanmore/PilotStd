"""集成测试: FileIndexRepository upsert / validate_paths / stop 信号。"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from pilotstd.core.db.database import Database
from pilotstd.core.file_index import FileIndexRepository


@pytest.fixture
def repo(tmp_path: Path) -> FileIndexRepository:
    db = Database(str(tmp_path / "test.db"))
    r = FileIndexRepository(db)
    yield r
    # stop() 内部已调用 db.close_all()，此处不再重复关闭
    r.stop()


class TestUpsert:
    def test_upsert_insert_and_update(self, repo: FileIndexRepository, tmp_path: Path):
        fp = str(tmp_path / "GB_T50001-2014.pdf")
        Path(fp).write_bytes(b"fake-pdf-content")

        # 首次插入 — number/year 为 int，与源码签名一致
        repo.upsert(
            file_path=fp,
            logical_code="GB",
            number=50001,
            year=2014,
            file_hash="abc123",
        )
        rec = repo.get(fp)
        assert rec is not None
        assert rec["logical_code"] == "GB"
        assert rec["number"] == 50001
        assert rec["file_hash"] == "abc123"

        # 更新同路径 — hash 变更，记录数不变
        repo.upsert(
            file_path=fp,
            logical_code="GB",
            number=50001,
            year=2014,
            file_hash="def456",
        )
        rec = repo.get(fp)
        assert rec["file_hash"] == "def456"
        assert repo.count() == 1


class TestValidation:
    def test_validation_removes_missing_files(self, repo: FileIndexRepository, tmp_path: Path):
        fp = str(tmp_path / "gone.pdf")
        Path(fp).write_bytes(b"x")
        repo.upsert(file_path=fp, logical_code="X", number=1, year=2020, file_hash="h1")
        assert repo.count() == 1

        os.remove(fp)
        removed = repo.validate_paths()

        assert isinstance(removed, int)
        assert removed == 1
        assert repo.get(fp) is None
        assert repo.count() == 0

    def test_validation_keeps_existing_files(self, repo: FileIndexRepository, tmp_path: Path):
        fp = str(tmp_path / "alive.pdf")
        Path(fp).write_bytes(b"y")
        repo.upsert(file_path=fp, logical_code="Y", number=2, year=2021, file_hash="h2")

        removed = repo.validate_paths()

        assert removed == 0
        after = repo.get(fp)
        assert after is not None
        # validate_paths 成功后 _validation_complete 应被设置
        assert repo.is_validation_complete is True

    def test_validation_respects_stop_signal(self, repo: FileIndexRepository, tmp_path: Path):
        """stop() 后 validate_paths 立即返回 0，线程不再存活。"""
        for i in range(200):
            fp = str(tmp_path / f"std_{i}.pdf")
            Path(fp).write_bytes(b"z")
            repo.upsert(file_path=fp, logical_code="Z", number=i, year=2022, file_hash=f"h{i}")

        repo.stop()

        # stop 后 validate_paths 应因 _stop_event 直接返回 0
        removed = repo.validate_paths()
        assert removed == 0

        # 核心断言：线程已退出，不依赖计时
        thread = repo._validation_thread
        if thread is not None:
            assert not thread.is_alive(), "stop() 后校验线程仍然存活"

        # _validation_complete 应在 stop() 中被设置
        assert repo.is_validation_complete is True
