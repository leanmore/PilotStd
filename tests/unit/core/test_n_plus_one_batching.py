"""N+1 / 目录遍历修复的回归用例（方向 C 深度扫描，2026-11-25）。

1. `archive_reconcile`：目录树只走**一遍**（原实现每个丢失文件 rglob 一次）；
2. `PendingService.query_local_cache`：按批 IN 预取（原实现每个标准 1~2 次点查）。
"""

from __future__ import annotations

import json
from pathlib import Path

from pilotstd.core.archive_reconcile import reconcile_archive
from pilotstd.core.db import Database
from pilotstd.manager.pending_service import PendingService


def _insert_file(db: Database, path: str) -> None:
    db.execute(
        "INSERT INTO file_index (file_path, logical_code, number, year, part, std_name, status)"
        " VALUES (?, 'GB/T', 1, 2020, -1, '测试标准', '现行')",
        (path,),
    )


class TestReconcileSingleWalk:
    def test_multiple_missing_files_repaired_in_one_walk(self, tmp_path) -> None:
        """同一文件名出现在过期目录时，多条悬空路径都应回填（索引一次建好）。"""
        db = Database(str(tmp_path / "db.sqlite"))
        root = tmp_path / "standards"
        expire = root / "过期作废"
        (expire / "sub").mkdir(parents=True)
        moved_a = expire / "sub" / "GBT 9-2020.pdf"
        moved_b = expire / "GBT 10-2020.pdf"
        moved_a.write_bytes(b"%PDF-1.7")
        moved_b.write_bytes(b"%PDF-1.7")
        # 两条悬空路径文件名不同（file_path 有 UNIQUE 约束，不能同时回填到同一文件）
        _insert_file(db, str(root / "dir0" / "GBT 9-2020.pdf"))
        _insert_file(db, str(root / "dir1" / "GBT 10-2020.pdf"))

        stats = reconcile_archive(db, str(root))
        assert stats["repaired"] == 2
        rows = db.fetchall("SELECT file_path FROM file_index ORDER BY file_path")
        assert rows[0]["file_path"] == str(moved_b)
        assert rows[1]["file_path"] == str(moved_a)
        db.close()

    def test_directory_tree_walked_once(self, tmp_path, monkeypatch) -> None:
        """`rglob` 只被调用 1 次（原实现：丢失 N 条 → N+1 次全树遍历）。"""
        db = Database(str(tmp_path / "db.sqlite"))
        root = tmp_path / "standards"
        expire = root / "过期作废"
        expire.mkdir(parents=True)
        (expire / "a.pdf").write_bytes(b"%PDF-1.7")
        for i in range(5):
            _insert_file(db, str(root / f"d{i}" / "missing.pdf"))

        calls = {"n": 0}
        real_rglob = Path.rglob

        def counting_rglob(self, pattern: str):  # noqa: ANN001
            calls["n"] += 1
            return real_rglob(self, pattern)

        monkeypatch.setattr(Path, "rglob", counting_rglob)
        stats = reconcile_archive(db, str(root))
        assert stats["missing"] == 5
        assert calls["n"] == 1, f"目录树应只遍历一次，实际 {calls['n']} 次"
        db.close()


class TestQueryLocalCacheBatched:
    def _service(self, tmp_path) -> tuple[PendingService, Database]:
        db = Database(str(tmp_path / "db.sqlite"))
        return PendingService(db, None), db

    def test_batched_lookup_returns_same_results(self, tmp_path) -> None:
        svc, db = self._service(tmp_path)
        for i in range(5):
            db.execute(
                "INSERT INTO standard_info_cache"
                " (standard_number, source_site, result_json, cached_at, source)"
                " VALUES (?, ?, ?, ?, ?)",
                (f"GB/T {i}-2020", "std_gov", json.dumps({"standard_name": f"名{i}"}), "2026-01-01", "network"),
            )

        class Parsed:
            def __init__(self, num: str):
                self._num = num

            def get_full_number(self) -> str:
                return self._num

        items = [Parsed(f"GB/T {i}-2020") for i in range(5)] + [Parsed("GB/T 999-2020")]
        results = svc.query_local_cache(items)
        assert len(results) == 6
        by_idx = {i: r for i, r in results}
        assert by_idx[0].standard_name == "名0"
        assert by_idx[4].standard_name == "名4"
        assert by_idx[5].standard_number == "GB/T 999-2020"
        db.close()

    def test_query_count_is_constant_not_per_item(self, tmp_path) -> None:
        """6 条标准只应发 2 次查询（每表 1 次 IN），而不是 12 次点查。"""
        svc, db = self._service(tmp_path)
        calls = {"n": 0}
        real_fetchall = db.fetchall

        def counting_fetchall(sql: str, params=None):  # noqa: ANN001
            if "IN (" in sql:
                calls["n"] += 1
            return real_fetchall(sql, params)

        db.fetchall = counting_fetchall  # type: ignore[method-assign]

        class Parsed:
            def __init__(self, num: str):
                self._num = num

            def get_full_number(self) -> str:
                return self._num

        svc.query_local_cache([Parsed(f"GB/T {i}-2020") for i in range(6)])
        assert calls["n"] == 2, f"应为每表 1 次（共 2 次），实际 {calls['n']}"
        db.close()
