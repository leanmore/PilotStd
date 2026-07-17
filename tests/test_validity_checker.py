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
            CREATE TABLE IF NOT EXISTS standard_validity (
    id INTEGER,
    standard_number TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT '未知',
    last_checked_at TEXT,
    next_check_at TEXT,
    last_status TEXT,
    last_status_updated_at TEXT,
    check_count INTEGER DEFAULT 0,
    created_at TEXT DEFAULT 'CURRENT_TIMESTAMP',
    updated_at TEXT DEFAULT 'CURRENT_TIMESTAMP',
    source_version TEXT DEFAULT 'initial',
    data_state TEXT DEFAULT 'fresh',
    last_accessed_at TEXT
);""")
        self.db.execute("CREATE INDEX IF NOT EXISTS idx_validity_next_check ON standard_validity(next_check_at)")
        self.db.execute("CREATE INDEX IF NOT EXISTS idx_validity_standard ON standard_validity(standard_number)")
        self.checker = ValidityChecker(self.db)

    def tearDown(self):
        self.db.execute("DELETE FROM standard_validity")

    # ── register_new_standard ──

    def test_register_new_standard(self):
        self.checker.register_new_standard("GB 1-2020")
        row = self.db.fetchone(
            "SELECT status, next_check_at FROM standard_validity WHERE standard_number=?",
            ("GB 1-2020",),
        )
        self.assertIsNotNone(row)
        self.assertEqual(row["status"], "未知")
        self.assertIsNotNone(row["next_check_at"])

    def test_register_duplicate_noop(self):
        self.checker.register_new_standard("GB 1-2020")
        self.checker.register_new_standard("GB 1-2020")
        rows = self.db.fetchall(
            "SELECT id FROM standard_validity WHERE standard_number=?",
            ("GB 1-2020",),
        )
        self.assertEqual(len(rows), 1)

    # ── update_status ──

    def test_update_status_new(self):
        self.checker.update_status("GB 2-2020", "现行")
        row = self.db.fetchone(
            "SELECT status, check_count FROM standard_validity WHERE standard_number=?",
            ("GB 2-2020",),
        )
        self.assertEqual(row["status"], "现行")
        self.assertEqual(row["check_count"], 1)

    def test_update_status_existing(self):
        self.checker.register_new_standard("GB 3-2020")
        self.checker.update_status("GB 3-2020", "已废止")
        row = self.db.fetchone(
            "SELECT status, last_status, check_count FROM standard_validity WHERE standard_number=?",
            ("GB 3-2020",),
        )
        self.assertEqual(row["status"], "已废止")
        self.assertEqual(row["last_status"], "未知")
        self.assertEqual(row["check_count"], 1)

    # ── get_due_standards + random_slice ──

    def test_get_due_empty(self):
        due = self.checker.get_due_standards()
        self.assertEqual(due, [])

    def test_random_slice_deterministic(self):
        candidates = [f"GB {i}-2020" for i in range(200)]
        a = self.checker.random_slice(candidates, 0, batch_size=50)
        b = self.checker.random_slice(candidates, 0, batch_size=50)
        self.assertEqual(a, b)
        self.assertEqual(len(a), 50)

    def test_random_slice_covers_with_weeks(self):
        candidates = [f"GB {i}-2020" for i in range(200)]
        all_w = set()
        for w in range(4):
            all_w.update(self.checker.random_slice(candidates, w, batch_size=50))
        self.assertGreaterEqual(len(all_w), 100)  # 随机切片至少覆盖 50%

    # ── update_status with 28-day scheduling ──

    def test_update_status_sets_next_check(self):
        self.checker.update_status("GB X-2020", "现行")
        row = self.db.fetchone(
            "SELECT status, next_check_at, check_count FROM standard_validity WHERE standard_number=?",
            ("GB X-2020",),
        )
        self.assertEqual(row["status"], "现行")
        self.assertIsNotNone(row["next_check_at"])
        self.assertEqual(row["check_count"], 1)

    def test_update_status_change_records_last_status(self):
        self.checker.update_status("GB Y-2020", "现行")
        self.checker.update_status("GB Y-2020", "已废止")
        row = self.db.fetchone(
            "SELECT status, last_status, last_status_updated_at FROM standard_validity WHERE standard_number=?",
            ("GB Y-2020",),
        )
        self.assertEqual(row["status"], "已废止")
        self.assertEqual(row["last_status"], "现行")
        self.assertIsNotNone(row["last_status_updated_at"])

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
