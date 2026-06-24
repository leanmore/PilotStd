# tests/test_validity_checker.py
"""标准时效性检查模块单元测试"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest

import pytest

from pilotstd.core.db import Database
from pilotstd.core.validity_checker import ValidityChecker


class TestValidityChecker(unittest.TestCase):
    @pytest.fixture(autouse=True)
    def _setup_db(self, shared_db):
        self.db: Database = shared_db
        # 创建表（模拟迁移 v16）
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS standard_validity_status (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                standard_number TEXT NOT NULL UNIQUE,
                status TEXT NOT NULL DEFAULT '未知',
                last_checked_at TEXT,
                next_check_at TEXT,
                last_status TEXT,
                last_status_updated_at TEXT,
                check_count INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.db.execute("CREATE INDEX IF NOT EXISTS idx_validity_next_check ON standard_validity_status(next_check_at)")
        self.db.execute("CREATE INDEX IF NOT EXISTS idx_validity_standard ON standard_validity_status(standard_number)")
        self.checker = ValidityChecker(self.db)

    def tearDown(self):
        self.db.execute("DELETE FROM standard_validity_status")

    # ── register_new_standard ──

    def test_register_new_standard(self):
        self.checker.register_new_standard("GB 1-2020")
        row = self.db.fetchone(
            "SELECT status, next_check_at FROM standard_validity_status WHERE standard_number=?",
            ("GB 1-2020",),
        )
        self.assertIsNotNone(row)
        self.assertEqual(row["status"], "未知")
        self.assertIsNotNone(row["next_check_at"])

    def test_register_duplicate_noop(self):
        self.checker.register_new_standard("GB 1-2020")
        self.checker.register_new_standard("GB 1-2020")
        rows = self.db.fetchall(
            "SELECT id FROM standard_validity_status WHERE standard_number=?",
            ("GB 1-2020",),
        )
        self.assertEqual(len(rows), 1)

    # ── update_status ──

    def test_update_status_new(self):
        self.checker.update_status("GB 2-2020", "现行")
        row = self.db.fetchone(
            "SELECT status, check_count FROM standard_validity_status WHERE standard_number=?",
            ("GB 2-2020",),
        )
        self.assertEqual(row["status"], "现行")
        self.assertEqual(row["check_count"], 1)

    def test_update_status_existing(self):
        self.checker.register_new_standard("GB 3-2020")
        self.checker.update_status("GB 3-2020", "已废止")
        row = self.db.fetchone(
            "SELECT status, last_status, check_count FROM standard_validity_status WHERE standard_number=?",
            ("GB 3-2020",),
        )
        self.assertEqual(row["status"], "已废止")
        self.assertEqual(row["last_status"], "未知")
        self.assertEqual(row["check_count"], 1)

    # ── get_weekly_batch ──

    def test_weekly_batch_empty(self):
        batch = self.checker.get_weekly_batch(0)
        self.assertEqual(batch, [])

    def test_weekly_batch_random_slice(self):
        # 注册 200 条标准
        for i in range(200):
            self.checker.register_new_standard(f"GB {i + 1}-2020")
        # 第 0 周取 50 条
        w0 = self.checker.get_weekly_batch(0, batch_size=50)
        self.assertEqual(len(w0), 50)
        # 第 1 周取 50 条，不应与第 0 周完全重叠
        w1 = self.checker.get_weekly_batch(1, batch_size=50)
        self.assertEqual(len(w1), 50)
        # 四周覆盖验证：第 0-3 周合计应接近 200
        all_w = set()
        for w in range(4):
            all_w.update(self.checker.get_weekly_batch(w, batch_size=50))
        self.assertGreaterEqual(len(all_w), 100)  # 随机切片至少覆盖 50%

    def test_weekly_batch_deterministic(self):
        for i in range(100):
            self.checker.register_new_standard(f"GB {i + 1}-2020")
        w0_a = self.checker.get_weekly_batch(0, batch_size=50)
        w0_b = self.checker.get_weekly_batch(0, batch_size=50)
        self.assertEqual(w0_a, w0_b)

    # ── check_standard ──

    def test_check_standard_l3_history(self):
        self.checker.update_status("GB 5-2020", "现行")
        result = self.checker.check_standard("GB 5-2020")
        self.assertIsNotNone(result)
        self.assertEqual(result["status"], "现行")

    # ── get_status_summary ──

    def test_status_summary(self):
        self.checker.update_status("GB A-2020", "现行")
        self.checker.update_status("GB B-2020", "现行")
        self.checker.update_status("GB C-2020", "已废止")
        summary = self.checker.get_status_summary()
        self.assertEqual(summary.get("现行"), 2)
        self.assertEqual(summary.get("已废止"), 1)
