# tests/test_date_reminder.py
"""date_reminder.py 单元测试 — 覆盖所有公开函数和内部分支。"""

import unittest
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from pilotstd.tasks.date_reminder import (
    _REMIND_DAYS,
    _fetch_due_records,
    _process_record,
    _target_dates,
    run_date_reminder,
)


class TestTargetDates(unittest.TestCase):
    """_target_dates 测试。"""

    def test_returns_dict_with_correct_keys(self):
        result = _target_dates()
        for d in _REMIND_DAYS:
            self.assertIn(d, result)

    def test_values_are_iso_format(self):
        result = _target_dates()
        today = date.today()
        for d in _REMIND_DAYS:
            expected = (today + timedelta(days=d)).isoformat()
            self.assertEqual(result[d], expected)

    def test_zero_days_is_today(self):
        result = _target_dates()
        self.assertEqual(result[0], date.today().isoformat())


class TestFetchDueRecords(unittest.TestCase):
    """_fetch_due_records 测试。"""

    def test_constructs_sql_with_placeholders(self):
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_db.execute.return_value = mock_cursor

        _fetch_due_records(mock_db)

        mock_db.execute.assert_called_once()
        sql = str(mock_db.execute.call_args[0][0])
        self.assertIn("FROM announcement_record", sql)
        self.assertIn("implement_date", sql)
        self.assertIn("expiry_date", sql)
        self.assertIn("superseded_by", sql)

    def test_params_count_matches_sql_placeholders(self):
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_db.execute.return_value = mock_cursor

        _fetch_due_records(mock_db)

        sql = str(mock_db.execute.call_args[0][0])
        params = mock_db.execute.call_args[0][1]
        # 参数个数必须等于 SQL 中 ? 占位符个数（自动计数，防止未来占位符增减时测试假通过）
        self.assertEqual(len(params), sql.count("?"))

    def test_returns_records(self):
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        expected_records = [{"id": 1, "standard_number": "GB/T 1.1"}]
        mock_cursor.fetchall.return_value = expected_records
        mock_db.execute.return_value = mock_cursor

        result = _fetch_due_records(mock_db)
        self.assertEqual(result, expected_records)


class TestProcessRecord(unittest.TestCase):
    """_process_record 全部分支覆盖。"""

    def setUp(self):
        self.mock_db = MagicMock()
        self.mock_nm = MagicMock()
        self.today = date(2026, 8, 1)
        self.base_rec = {
            "id": 1,
            "standard_number": "GB/T 1.1",
            "std_name": "测试标准",
            "implement_date": "2026-08-01",
            "expiry_date": "",
            "superseded_by": "",
            "remind_type": "implement",
        }

    # ── remind_type 分支 ──

    def test_remind_type_none_returns_early(self):
        rec = {**self.base_rec, "remind_type": None}
        stats = {"scanned": 0, "sent": 0, "skipped": 0}
        _process_record(rec, self.today, self.mock_db, self.mock_nm, stats)
        self.assertEqual(stats["sent"], 0)
        self.assertEqual(stats["skipped"], 0)

    def test_remind_type_empty_string_returns_early(self):
        rec = {**self.base_rec, "remind_type": ""}
        stats = {"scanned": 0, "sent": 0, "skipped": 0}
        _process_record(rec, self.today, self.mock_db, self.mock_nm, stats)
        self.assertEqual(stats["sent"], 0)

    # ── implement 类型 ──

    def test_implement_type(self):
        stats = {"scanned": 0, "sent": 0, "skipped": 0}
        # 模拟有用户关注
        mock_cursor1 = MagicMock()
        mock_cursor1.fetchall.return_value = [{"user_id": 1}]
        # 模拟去重：未发送过
        mock_cursor2 = MagicMock()
        mock_cursor2.fetchone.return_value = None
        # 插入日志
        mock_cursor3 = MagicMock()
        self.mock_db.execute.side_effect = [mock_cursor1, mock_cursor2, mock_cursor3]

        _process_record(self.base_rec, self.today, self.mock_db, self.mock_nm, stats)
        self.assertEqual(stats["sent"], 1)

    # ── expiry 类型 ──

    def test_expiry_type(self):
        rec = {
            **self.base_rec,
            "remind_type": "expiry",
            "expiry_date": "2026-08-16",  # 15 days after Aug 1 → days_before=15
            "implement_date": "",
        }
        stats = {"scanned": 0, "sent": 0, "skipped": 0}

        mock_cursor1 = MagicMock()
        mock_cursor1.fetchall.return_value = [{"user_id": 2}]
        mock_cursor2 = MagicMock()
        mock_cursor2.fetchone.return_value = None
        mock_cursor3 = MagicMock()
        self.mock_db.execute.side_effect = [mock_cursor1, mock_cursor2, mock_cursor3]

        _process_record(rec, self.today, self.mock_db, self.mock_nm, stats)
        self.assertEqual(stats["sent"], 1)

    # ── implied 类型 ──

    def test_implied_type_uses_implied_date(self):
        today = date(2026, 7, 22)  # 8 days before 2026-07-30 → 不符合 _REMIND_DAYS
        rec = {
            **self.base_rec,
            "remind_type": "expiry_implied",
            "implement_date": "2026-07-30",
            "expiry_date": "",
            "implied_date": "2026-07-30",
        }
        stats = {"scanned": 0, "sent": 0, "skipped": 0}
        _process_record(rec, today, self.mock_db, self.mock_nm, stats)
        # days_before = 8, not in [30,15,7,0] → 跳过
        self.assertEqual(stats["sent"], 0)

    def test_implied_type_falls_back_to_implement_date(self):
        today = date(2026, 7, 25)  # 5 days before → not in REMIND_DAYS
        rec = {
            **self.base_rec,
            "remind_type": "expiry_implied",
            "implement_date": "2026-07-30",
            "expiry_date": "",
            "implied_date": None,
        }
        stats = {"scanned": 0, "sent": 0, "skipped": 0}
        _process_record(rec, today, self.mock_db, self.mock_nm, stats)
        self.assertEqual(stats["sent"], 0)

    # ── target_str 为 None ──

    def test_target_str_none_returns_early(self):
        rec = {
            **self.base_rec,
            "remind_type": "implement",
            "implement_date": "",
        }
        stats = {"scanned": 0, "sent": 0, "skipped": 0}
        _process_record(rec, self.today, self.mock_db, self.mock_nm, stats)
        self.assertEqual(stats["sent"], 0)

    # ── days_before 不在 REMIND_DAYS ──

    def test_days_before_not_in_remind_days(self):
        rec = {
            **self.base_rec,
            "remind_type": "implement",
            "implement_date": "2026-06-01",  # 61 days before Aug 1 → not in [30,15,7,0]
        }
        stats = {"scanned": 0, "sent": 0, "skipped": 0}
        _process_record(rec, self.today, self.mock_db, self.mock_nm, stats)
        self.assertEqual(stats["sent"], 0)

    # ── 无关注用户 ──

    def test_no_following_users_returns_early(self):
        stats = {"scanned": 0, "sent": 0, "skipped": 0}
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        self.mock_db.execute.return_value = mock_cursor

        _process_record(self.base_rec, self.today, self.mock_db, self.mock_nm, stats)
        self.assertEqual(stats["sent"], 0)

    # ── 去重：已发送过 ──

    def test_already_sent_skips(self):
        stats = {"scanned": 0, "sent": 0, "skipped": 0}
        mock_cursor1 = MagicMock()
        mock_cursor1.fetchall.return_value = [{"user_id": 1}]
        mock_cursor2 = MagicMock()
        mock_cursor2.fetchone.return_value = {"1": 1}  # 已有记录
        self.mock_db.execute.side_effect = [mock_cursor1, mock_cursor2]

        _process_record(self.base_rec, self.today, self.mock_db, self.mock_nm, stats)
        self.assertEqual(stats["skipped"], 1)
        self.assertEqual(stats["sent"], 0)

    # ── 多用户 ──

    def test_multiple_users_each_sent(self):
        stats = {"scanned": 0, "sent": 0, "skipped": 0}
        mock_cursor1 = MagicMock()
        mock_cursor1.fetchall.return_value = [{"user_id": 1}, {"user_id": 2}]
        # 每个用户两次查询：去重 + 插入日志
        mock_results = [mock_cursor1]
        for _ in range(4):  # 2 users * (1 dedup + 1 insert)
            mc = MagicMock()
            mc.fetchone.return_value = None
            mock_results.append(mc)
        self.mock_db.execute.side_effect = mock_results

        _process_record(self.base_rec, self.today, self.mock_db, self.mock_nm, stats)
        self.assertEqual(stats["sent"], 2)

    # ── 通知发送异常 ──

    def test_notification_exception_logged_and_continues(self):
        stats = {"scanned": 0, "sent": 0, "skipped": 0}
        mock_cursor1 = MagicMock()
        mock_cursor1.fetchall.return_value = [{"user_id": 1}]
        mock_cursor2 = MagicMock()
        mock_cursor2.fetchone.return_value = None
        self.mock_db.execute.side_effect = [mock_cursor1, mock_cursor2]
        self.mock_nm.send_event.side_effect = RuntimeError("通知失败")

        # 不应抛出异常
        _process_record(self.base_rec, self.today, self.mock_db, self.mock_nm, stats)
        # sent 未增加（因为异常在 continue 之前，stats["sent"] 未递增）
        self.assertEqual(stats["sent"], 0)

    # ── 插入日志 ──

    def test_inserts_date_reminder_log(self):
        stats = {"scanned": 0, "sent": 0, "skipped": 0}
        mock_cursor1 = MagicMock()
        mock_cursor1.fetchall.return_value = [{"user_id": 1}]
        mock_cursor2 = MagicMock()
        mock_cursor2.fetchone.return_value = None
        mock_cursor3 = MagicMock()
        self.mock_db.execute.side_effect = [mock_cursor1, mock_cursor2, mock_cursor3]

        _process_record(self.base_rec, self.today, self.mock_db, self.mock_nm, stats)

        insert_calls = [
            c for c in self.mock_db.execute.call_args_list
            if "INSERT INTO date_reminder_log" in str(c[0][0])
        ]
        self.assertEqual(len(insert_calls), 1)


class TestRunDateReminder(unittest.TestCase):
    """run_date_reminder 主函数测试。"""

    @patch("pilotstd.tasks.date_reminder.Database")
    @patch("pilotstd.tasks.date_reminder.get_db_path")
    def test_empty_records_returns_early(self, mock_get_db_path, mock_db_cls):
        mock_db = MagicMock()
        mock_db_cls.return_value = mock_db
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_db.execute.return_value = mock_cursor

        mock_nm = MagicMock()
        result = run_date_reminder(mock_nm)

        self.assertEqual(result["scanned"], 0)
        self.assertEqual(result["sent"], 0)
        mock_db.close.assert_called_once()

    @patch("pilotstd.tasks.date_reminder._process_record")
    @patch("pilotstd.tasks.date_reminder.Database")
    @patch("pilotstd.tasks.date_reminder.get_db_path")
    def test_with_records_logs_completion(self, mock_get_db_path, mock_db_cls, mock_process):
        """有记录时完成处理后记录 info 日志（覆盖 line 156 logger.info）。"""
        mock_db = MagicMock()
        mock_db_cls.return_value = mock_db

        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {
                "id": 1,
                "standard_number": "GB/T 1.1",
                "std_name": "测试",
                "implement_date": (date.today() + timedelta(days=30)).isoformat(),
                "expiry_date": "",
                "superseded_by": "",
                "remind_type": "implement",
            }
        ]
        mock_db.execute.return_value = mock_cursor

        mock_nm = MagicMock()
        result = run_date_reminder(mock_nm)

        self.assertEqual(result["scanned"], 1)
        # _process_record 被调用了
        mock_process.assert_called_once()
        mock_db.close.assert_called_once()

    @patch("pilotstd.tasks.date_reminder.Database")
    @patch("pilotstd.tasks.date_reminder.get_db_path")
    def test_db_exception_raised(self, mock_get_db_path, mock_db_cls):
        mock_db_cls.side_effect = Exception("DB connection failed")

        mock_nm = MagicMock()
        with self.assertRaises(Exception):
            run_date_reminder(mock_nm)

    @patch("pilotstd.manager.facade.StandardManager")
    @patch("pilotstd.tasks.date_reminder.Database")
    @patch("pilotstd.tasks.date_reminder.get_db_path")
    def test_creates_standard_manager_when_notification_mgr_is_none(
        self, mock_get_db_path, mock_db_cls, mock_sm_cls
    ):
        mock_db = MagicMock()
        mock_db_cls.return_value = mock_db
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_db.execute.return_value = mock_cursor

        mock_sm = MagicMock()
        mock_sm.notification_mgr = MagicMock()
        mock_sm_cls.return_value = mock_sm

        run_date_reminder(None)

        mock_sm_cls.assert_called_once()
        mock_db.close.assert_called_once()

    @patch("pilotstd.tasks.date_reminder.Database")
    @patch("pilotstd.tasks.date_reminder.get_db_path")
    def test_db_close_called_even_on_exception(self, mock_get_db_path, mock_db_cls):
        mock_db = MagicMock()
        mock_db_cls.return_value = mock_db
        mock_db.execute.side_effect = Exception("SQL error")

        mock_nm = MagicMock()
        with self.assertRaises(Exception):
            run_date_reminder(mock_nm)

        mock_db.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
