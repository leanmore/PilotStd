"""集成测试: _FileIndexQueryMixin 写入后立即查询。"""
from __future__ import annotations

from pathlib import Path

import pytest

from pilotstd.core.db.database import Database
from pilotstd.core.file_index import FileIndexRepository


@pytest.fixture
def repo(tmp_path: Path) -> FileIndexRepository:
    db = Database(str(tmp_path / "query_test.db"))
    r = FileIndexRepository(db)
    yield r
    r.stop()


class TestQueryIntegration:
    def test_find_by_standard_after_upsert(self, repo: FileIndexRepository, tmp_path: Path):
        fp = str(tmp_path / "CJJ_37-2012.pdf")
        Path(fp).write_bytes(b"cjj37")
        repo.upsert(
            file_path=fp,
            logical_code="CJJ",
            number=37,
            year=2012,
            file_hash="hcjj",
        )

        results = repo.find_by_standard(logical_code="CJJ", number=37, year=2012)

        assert len(results) == 1
        assert results[0]["file_path"] == fp
        assert results[0]["logical_code"] == "CJJ"

    def test_query_returns_empty_for_nonexistent(self, repo: FileIndexRepository):
        assert repo.find_by_standard(logical_code="FAKE", number=99999, year=2099) == []
        assert repo.get("/nonexistent/path.pdf") is None
        assert repo.find_by_hash("no_such_hash") is None
