# tests/test_migrate_v54.py — v54 迁移测试
# v54: favorite_downloads 补 user_id/standard_no/standard_name 列 + 回填存量
# 以实测 v44 表结构为基准（favorite_id/record_id/status/...，无 user_id 等列）

import os
import shutil
import sys
import tempfile
import unittest

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

if "SUPERUSER" not in os.environ:
    os.environ["SUPERUSER"] = "testadmin"


class TestMigrateV54(unittest.TestCase):
    """验证 v54 迁移：补列 + 回填存量 + 幂等 + 列名探测。"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="pilotstd_v54_")
        self.db_path = os.path.join(self.tmpdir, "test.db")
        from pilotstd.core.db import Database
        self.db = Database(self.db_path)

    def tearDown(self):
        self.db.close()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _cols(self, table: str) -> set[str]:
        return {r["name"] for r in self.db.fetchall(f"PRAGMA table_info({table})")}

    def _drop_v54_cols(self) -> None:
        """模拟 v53 状态：移除 v54 新增的三列（SQLite ≥3.35 支持 DROP COLUMN）。"""
        self.db.execute("ALTER TABLE favorite_downloads DROP COLUMN user_id")
        self.db.execute("ALTER TABLE favorite_downloads DROP COLUMN standard_no")
        self.db.execute("ALTER TABLE favorite_downloads DROP COLUMN standard_name")

    def _seed_legacy_rows(self) -> None:
        """构造 v53 存量数据：user_favorites 2 条 + favorite_downloads 2 条（无新列）。"""
        import sqlite3
        raw = sqlite3.connect(self.db_path)
        try:
            raw.execute(
                "INSERT INTO announcement_record"
                " (source_site, pid, announce_no, standard_number, std_name, fetched_at)"
                " VALUES ('ahbz', 'p1', 'A-1', 'GB/T 1001', '标准甲', '2026-06-01')"
            )
            raw.execute(
                "INSERT INTO announcement_record"
                " (source_site, pid, announce_no, standard_number, std_name, fetched_at)"
                " VALUES ('ahbz', 'p2', 'A-2', 'GB/T 1002', '标准乙', '2026-06-02')"
            )
            rec1 = raw.execute("SELECT id FROM announcement_record WHERE standard_number='GB/T 1001'").fetchone()[0]
            rec2 = raw.execute("SELECT id FROM announcement_record WHERE standard_number='GB/T 1002'").fetchone()[0]
            raw.execute(
                "INSERT INTO user_favorites (user_id, record_id, status, created_at, updated_at)"
                " VALUES (1, ?, 'pending', datetime('now'), datetime('now'))", (rec1,)
            )
            raw.execute(
                "INSERT INTO user_favorites (user_id, record_id, status, created_at, updated_at)"
                " VALUES (2, ?, 'pending', datetime('now'), datetime('now'))", (rec2,)
            )
            fav1 = raw.execute("SELECT id FROM user_favorites WHERE user_id=1 AND record_id=?", (rec1,)).fetchone()[0]
            fav2 = raw.execute("SELECT id FROM user_favorites WHERE user_id=2 AND record_id=?", (rec2,)).fetchone()[0]
            raw.execute(
                "INSERT INTO favorite_downloads (favorite_id, record_id, status, created_at, updated_at)"
                " VALUES (?, ?, 'pending', datetime('now'), datetime('now'))", (fav1, rec1)
            )
            raw.execute(
                "INSERT INTO favorite_downloads (favorite_id, record_id, status, created_at, updated_at)"
                " VALUES (?, ?, 'pending', datetime('now'), datetime('now'))", (fav2, rec2)
            )
            raw.commit()
        finally:
            raw.close()

    def _run_v54(self) -> None:
        from pilotstd.core.db._migrate_v54 import _migrate_v54_favorite_downloads_columns
        _migrate_v54_favorite_downloads_columns(self.db)

    # ── 用例 1：完整迁移链已包含 v54（列存在）──

    def test_v54_columns_exist_after_full_chain(self):
        cols = self._cols("favorite_downloads")
        for c in ("user_id", "standard_no", "standard_name"):
            self.assertIn(c, cols, f"v54 迁移后 favorite_downloads 应包含 {c} 列")

    # ── 用例 2：补列 + 存量回填 ──

    def test_v54_backfills_legacy_rows(self):
        self._drop_v54_cols()
        self._seed_legacy_rows()
        self._run_v54()

        # 列已补
        cols = self._cols("favorite_downloads")
        for c in ("user_id", "standard_no", "standard_name"):
            self.assertIn(c, cols)

        # 回填验证：user_id / standard_no / standard_name 正确
        rows = self.db.fetchall(
            "SELECT fd.user_id, fd.standard_no, fd.standard_name, fd.record_id"
            " FROM favorite_downloads fd ORDER BY fd.id"
        )
        self.assertEqual(len(rows), 2)
        # 第一条：user 1 + GB/T 1001 + 标准甲
        r1 = next(r for r in rows if r["user_id"] == 1)
        self.assertEqual(r1["standard_no"], "GB/T 1001")
        self.assertEqual(r1["standard_name"], "标准甲")
        # 第二条：user 2 + GB/T 1002 + 标准乙
        r2 = next(r for r in rows if r["user_id"] == 2)
        self.assertEqual(r2["standard_no"], "GB/T 1002")
        self.assertEqual(r2["standard_name"], "标准乙")

    # ── 用例 3：幂等（跑两次不报错、不重复）──

    def test_v54_idempotent(self):
        self._drop_v54_cols()
        self._seed_legacy_rows()
        self._run_v54()
        self._run_v54()  # 第二次运行
        count = self.db.fetchone("SELECT COUNT(*) AS cnt FROM favorite_downloads")["cnt"]
        self.assertEqual(count, 2, "幂等：重复运行不产生重复回填")

    # ── 用例 4：无存量数据时零副作用 ──

    def test_v54_empty_db_noop(self):
        self._drop_v54_cols()
        self._run_v54()
        cols = self._cols("favorite_downloads")
        for c in ("user_id", "standard_no", "standard_name"):
            self.assertIn(c, cols)


if __name__ == "__main__":
    unittest.main()
