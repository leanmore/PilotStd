"""file_index 启动校验的批量删除保护（2026-11-11 事故回归）。

事故证据：远程日志 `app.log.9` 2026-11-11 21:41:42
`file_index 启动校验完成（延迟 5.0s），清理 820 条失效记录`——容器挂载未就绪时，
validate_paths 把全部索引判失效并删除。修复后：高缺失比例 → 跳过删除 + WARNING。
"""

from __future__ import annotations

import threading

import pytest

from pilotstd.core.db import Database
from pilotstd.core.file_index import FileIndexRepository, _is_mass_delete_anomaly


def _make_repo(tmp_path) -> tuple[FileIndexRepository, Database, str]:
    db_path = str(tmp_path / "fi.db")
    db = Database(db_path)  # 跑迁移链，file_index 结构与生产一致（schema 一致性门禁要求）
    repo = object.__new__(FileIndexRepository)
    repo._db = db
    repo._stop_event = threading.Event()
    repo._validation_complete = threading.Event()
    return repo, db, db_path


def _insert(db: Database, paths: list[str]) -> None:
    for i, path in enumerate(paths):
        db.execute("INSERT INTO file_index (id, file_path) VALUES (?, ?)", (i + 1, path))


def _count(db: Database) -> int:
    return db.fetchone("SELECT COUNT(*) AS c FROM file_index")["c"]


def test_mass_missing_skips_delete(tmp_path):
    repo, db, _ = _make_repo(tmp_path)
    _insert(db, [f"/standards/missing-{i}.pdf" for i in range(60)])
    assert repo.validate_paths() == 0
    assert _count(db) == 60
    db.close()


def test_partial_missing_deletes_only_missing(tmp_path):
    repo, db, _ = _make_repo(tmp_path)
    real = []
    for i in range(55):
        path = tmp_path / f"real-{i}.pdf"
        path.write_text("x", encoding="utf-8")
        real.append(str(path))
    missing = [f"/standards/missing-{i}.pdf" for i in range(5)]
    _insert(db, real + missing)
    assert repo.validate_paths() == 5
    assert _count(db) == 55
    db.close()


def test_small_index_all_missing_still_deletes(tmp_path):
    repo, db, _ = _make_repo(tmp_path)
    _insert(db, [f"/standards/missing-{i}.pdf" for i in range(10)])
    assert repo.validate_paths() == 10
    assert _count(db) == 0
    db.close()


@pytest.mark.parametrize(
    ("total", "missing", "expected"),
    [(100, 90, True), (100, 95, True), (100, 50, False), (49, 49, False), (50, 45, True)],
)
def test_guard_thresholds(total, missing, expected):
    assert _is_mass_delete_anomaly(total, missing) is expected
