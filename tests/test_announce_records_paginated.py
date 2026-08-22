# tests/test_announce_records_paginated.py — 公告记录分页端点测试（Phase 1）
# 使用真实 Database（迁移链生成 Schema）+ 直接调用 handler（与 test_announce_detail.py 同模式）

import os
import shutil
import sys
import tempfile
import time
import unittest
from unittest.mock import MagicMock

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

if "SUPERUSER" not in os.environ:
    os.environ["SUPERUSER"] = "testadmin"


class TestAnnounceRecordsPaginated(unittest.TestCase):
    """验证 /api/announcements/{announce_no}/records 分页行为与性能。

    数据：1030 条记录（standard_number 倒序插入，验证 ORDER BY ASC 生效）。
    """

    ANNOUNCE_NO = "ANNOUNCE-2026-001"
    TOTAL = 1030

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "test.db")

        from pilotstd.core.db import Database

        self.db = Database(self.db_path)

        # 倒序插入：standard_number 从 GB/T 9999 → GB/T 8970，确保排序可验证
        rows = [
            (
                "ahbz",
                "pid-001",
                self.ANNOUNCE_NO,
                i + 1,
                f"GB/T {9999 - i}",
                f"标准名称{i + 1}",
                "2026-06-15",
            )
            for i in range(self.TOTAL)
        ]
        self.db.executemany(
            "INSERT INTO announcement_record"
            " (source_site, pid, announce_no, row_index, standard_number, std_name, fetched_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            rows,
        )

    def tearDown(self):
        self.db.close()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _mgr(self):
        mgr = MagicMock()
        mgr.db = self.db
        return mgr

    def _call(self, page=1, page_size=50):
        from docker.api.announce_detail import get_announcement_records_paginated

        return get_announcement_records_paginated(
            self.ANNOUNCE_NO, page=page, page_size=page_size, mgr=self._mgr()
        )

    # ── 单元测试：分页语义 ─────────────────────────────────────

    def test_page1_returns_first_50_sorted(self):
        result = self._call(page=1, page_size=50)
        self.assertEqual(result["page"], 1)
        self.assertEqual(result["pageSize"], 50)
        self.assertEqual(result["total"], self.TOTAL)
        self.assertEqual(len(result["items"]), 50)
        self.assertTrue(result["hasMore"])
        # 排序断言：standard_number 升序（GB/T 8970 起）
        stds = [i["standard_number"] for i in result["items"]]
        self.assertEqual(stds, sorted(stds))
        self.assertEqual(stds[0], "GB/T 8970")

    def test_middle_page_returns_50(self):
        result = self._call(page=10, page_size=50)
        self.assertEqual(result["page"], 10)
        self.assertEqual(len(result["items"]), 50)
        self.assertTrue(result["hasMore"])

    def test_last_page_has_more_false(self):
        # 1030 = 20*50 + 30 → 第 21 页为最后一页，30 条
        result = self._call(page=21, page_size=50)
        self.assertEqual(len(result["items"]), 30)
        self.assertFalse(result["hasMore"])

    def test_page_size_boundary_one(self):
        result = self._call(page=1, page_size=1)
        self.assertEqual(len(result["items"]), 1)
        self.assertTrue(result["hasMore"])

    def test_page_beyond_range_returns_empty(self):
        result = self._call(page=9999, page_size=50)
        self.assertEqual(result["items"], [])
        self.assertFalse(result["hasMore"])

    def test_invalid_params_raise_422(self):
        from fastapi import HTTPException

        from docker.api.announce_detail import get_announcement_records_paginated

        with self.assertRaises(HTTPException) as ctx:
            get_announcement_records_paginated(
                self.ANNOUNCE_NO, page=0, page_size=50, mgr=self._mgr()
            )
        self.assertEqual(ctx.exception.status_code, 422)
        with self.assertRaises(HTTPException) as ctx:
            get_announcement_records_paginated(
                self.ANNOUNCE_NO, page=1, page_size=201, mgr=self._mgr()
            )
        self.assertEqual(ctx.exception.status_code, 422)

    def test_empty_announce_no_returns_zero(self):
        from docker.api.announce_detail import get_announcement_records_paginated

        result = get_announcement_records_paginated(
            "NONEXISTENT", page=1, page_size=50, mgr=self._mgr()
        )
        self.assertEqual(result["total"], 0)
        self.assertEqual(result["items"], [])
        self.assertFalse(result["hasMore"])

    # ── 索引迁移验证 ───────────────────────────────────────────

    def test_pagination_composite_index_created(self):
        """迁移 v53 应创建 (announce_no, standard_number) 复合索引。"""
        indexes = {
            r["name"] for r in self.db.fetchall("PRAGMA index_list(announcement_record)")
        }
        self.assertIn("idx_announcement_record_announce_no_std", indexes)

    # ── 性能验证（前置确认：COUNT 与分页查询 < 50ms）──────────────

    def test_paginated_query_performance_under_50ms(self):
        """1030 条数据下，单次分页请求（COUNT + 页查询）< 50ms。"""
        # 预热（索引/页缓存）
        self._call(page=1, page_size=50)
        t0 = time.perf_counter()
        for _ in range(5):
            self._call(page=2, page_size=50)
        elapsed_ms = (time.perf_counter() - t0) * 1000 / 5
        self.assertLess(
            elapsed_ms, 50, f"分页查询平均耗时 {elapsed_ms:.1f}ms，超过 50ms 阈值"
        )


if __name__ == "__main__":
    unittest.main()
