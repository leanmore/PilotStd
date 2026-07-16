# tests/test_validity_checker_full.py
# ValidityChecker 单元测试 — 覆盖所有方法和分支路径
# 使用 unittest.TestCase + MagicMock，不依赖 pytest fixture

import unittest
from unittest.mock import MagicMock, patch

from pilotstd.core.validity_checker import (
    ValidityChecker,
    _sample_due_standards,
    _process_validity_batch,
    _finalize_validity_round,
    run_validity_check,
)


# ════════════════════════════════════════════════════════════════════
# 辅助：构造带 __getitem__ 的 mock fetchone/fetchall 返回值
# ════════════════════════════════════════════════════════════════════

def _row(**kwargs):
    """构造模拟行（支持 dict 式访问和 .get()）。"""
    m = MagicMock()
    m.__getitem__.side_effect = kwargs.__getitem__
    m.get.side_effect = kwargs.get
    return m


def _rows(*dicts):
    """构造模拟 fetchall 返回值列表。"""
    return [_row(**d) for d in dicts]


# ════════════════════════════════════════════════════════════════════
# TestInitAndEnsureColumn: __init__ + _ensure_last_changed_at_column
# ════════════════════════════════════════════════════════════════════

class TestInitAndEnsureColumn(unittest.TestCase):
    """覆盖 __init__ 中的 _ensure_last_changed_at_column 三种分支。"""

    def test_table_exists_with_column(self):
        """表已存在且已有 last_changed_at 列 → 不执行 ALTER。"""
        mock_db = MagicMock()
        mock_db.fetchall.return_value = _rows(
            {"name": "id"},
            {"name": "standard_number"},
            {"name": "last_changed_at"},
        )
        checker = ValidityChecker(mock_db)
        mock_db.fetchall.assert_called_once()
        mock_db.execute.assert_not_called()
        self.assertIsNotNone(checker)

    def test_table_exists_without_column(self):
        """表已存在但缺少 last_changed_at 列 → 执行 ALTER TABLE + UPDATE。"""
        mock_db = MagicMock()
        mock_db.fetchall.return_value = _rows(
            {"name": "id"},
            {"name": "standard_number"},
        )
        checker = ValidityChecker(mock_db)
        mock_db.fetchall.assert_called_once()
        self.assertEqual(mock_db.execute.call_count, 2)
        first_sql = mock_db.execute.call_args_list[0][0][0]
        self.assertIn("ALTER TABLE", first_sql)
        second_sql = mock_db.execute.call_args_list[1][0][0]
        self.assertIn("UPDATE", second_sql)
        self.assertIsNotNone(checker)

    def test_pragma_raises_exception(self):
        """PRAGMA 查询抛异常 → 记录警告，不中断初始化。"""
        mock_db = MagicMock()
        mock_db.fetchall.side_effect = Exception("no such table")
        checker = ValidityChecker(mock_db)
        mock_db.fetchall.assert_called_once()
        mock_db.execute.assert_not_called()
        self.assertIsNotNone(checker)


# ════════════════════════════════════════════════════════════════════
# TestRegisterNewStandard
# ════════════════════════════════════════════════════════════════════

class TestRegisterNewStandard(unittest.TestCase):
    """覆盖 register_new_standard：新标准/已存在/带通知/通知异常。"""

    def setUp(self):
        self.mock_db = MagicMock()
        # __init__ 中会调用 PRAGMA，让 fetchall 返回含 last_changed_at 的列
        self.mock_db.fetchall.return_value = _rows(
            {"name": "id"}, {"name": "standard_number"}, {"name": "last_changed_at"}
        )

    def test_new_standard_insert(self):
        """标准号不存在 → INSERT 新记录。"""
        self.mock_db.fetchone.return_value = None
        checker = ValidityChecker(self.mock_db)
        # 重置 mock 历史，清除 __init__ 调用的记录
        self.mock_db.reset_mock()
        checker.register_new_standard("GB/T 12345")
        self.mock_db.fetchone.assert_called_once()
        self.mock_db.execute.assert_called_once()
        sql_text = self.mock_db.execute.call_args[0][0]
        self.assertIn("INSERT INTO standard_validity", sql_text)

    def test_existing_standard_skip(self):
        """标准号已存在 → 直接返回，不 INSERT。"""
        self.mock_db.fetchone.return_value = _row(id=1)
        checker = ValidityChecker(self.mock_db)
        self.mock_db.reset_mock()
        checker.register_new_standard("GB/T 12345")
        self.mock_db.fetchone.assert_called_once()
        self.mock_db.execute.assert_not_called()

    def test_with_notification_mgr(self):
        """带 notification_mgr → send_event('standard_first_registered') 被调用。"""
        self.mock_db.fetchone.return_value = None
        notif_mgr = MagicMock()
        checker = ValidityChecker(self.mock_db)
        self.mock_db.reset_mock()
        checker.register_new_standard("GB/T 12345", notification_mgr=notif_mgr)
        notif_mgr.send_event.assert_called_once_with(
            "standard_first_registered",
            {"standard_number": "GB/T 12345"},
        )

    def test_notification_mgr_raises(self):
        """notification_mgr.send_event 抛异常 → 被捕获，不影响 INSERT。"""
        self.mock_db.fetchone.return_value = None
        notif_mgr = MagicMock()
        notif_mgr.send_event.side_effect = RuntimeError("send failed")
        checker = ValidityChecker(self.mock_db)
        self.mock_db.reset_mock()
        # 不应抛异常
        checker.register_new_standard("GB/T 12345", notification_mgr=notif_mgr)
        self.mock_db.execute.assert_called_once()


# ════════════════════════════════════════════════════════════════════
# TestUpdateStatus
# ════════════════════════════════════════════════════════════════════

class TestUpdateStatus(unittest.TestCase):
    """覆盖 update_status：状态变更/不变/新记录/通知/通知异常。"""

    def setUp(self):
        self.mock_db = MagicMock()
        self.mock_db.fetchall.return_value = _rows(
            {"name": "id"}, {"name": "standard_number"}, {"name": "last_changed_at"}
        )
        self.checker = ValidityChecker(self.mock_db)
        self.mock_db.reset_mock()

    @patch("pilotstd.core.config.ConfigManager")
    def test_status_changed(self, mock_cm_cls):
        """现有记录，状态变更 → UPDATE 含 last_changed_at + 通知发送。"""
        mock_cm = MagicMock()
        mock_cm.get.return_value = 4
        mock_cm_cls.return_value = mock_cm

        self.mock_db.fetchone.return_value = _row(status="现行", check_count=1)
        notif_mgr = MagicMock()

        self.checker.update_status("GB/T 12345", "已废止", notification_mgr=notif_mgr)

        # 验证 UPDATE 被执行，且含 last_changed_at
        self.mock_db.execute.assert_called_once()
        sql_text = self.mock_db.execute.call_args[0][0]
        self.assertIn("UPDATE", sql_text)
        self.assertIn("last_changed_at", sql_text)

        # 验证通知发送，is_expired=True
        notif_mgr.send_event.assert_called_once()
        args = notif_mgr.send_event.call_args[0]
        self.assertEqual(args[0], "standard_status_changed")
        self.assertEqual(args[1]["standard_number"], "GB/T 12345")
        self.assertEqual(args[1]["old_status"], "现行")
        self.assertEqual(args[1]["new_status"], "已废止")
        self.assertTrue(args[1]["is_expired"])

    @patch("pilotstd.core.config.ConfigManager")
    def test_status_unchanged(self, mock_cm_cls):
        """现有记录，状态不变 → UPDATE 不含 last_changed_at，无通知发送。"""
        mock_cm = MagicMock()
        mock_cm.get.return_value = 4
        mock_cm_cls.return_value = mock_cm

        self.mock_db.fetchone.return_value = _row(status="现行", check_count=1)
        notif_mgr = MagicMock()

        self.checker.update_status("GB/T 12345", "现行", notification_mgr=notif_mgr)

        sql_text = self.mock_db.execute.call_args[0][0]
        self.assertIn("UPDATE", sql_text)
        self.assertNotIn("last_changed_at", sql_text)
        notif_mgr.send_event.assert_not_called()

    @patch("pilotstd.core.config.ConfigManager")
    def test_new_record_insert(self, mock_cm_cls):
        """标准号不在表中 → INSERT 新记录。"""
        mock_cm = MagicMock()
        mock_cm.get.return_value = 4
        mock_cm_cls.return_value = mock_cm

        self.mock_db.fetchone.return_value = None

        self.checker.update_status("GB/T 99999", "现行")

        sql_text = self.mock_db.execute.call_args[0][0]
        self.assertIn("INSERT INTO", sql_text)

    @patch("pilotstd.core.config.ConfigManager")
    def test_notification_raises_on_update(self, mock_cm_cls):
        """状态变更但通知抛异常 → 被捕获，UPDATE 仍执行。"""
        mock_cm = MagicMock()
        mock_cm.get.return_value = 4
        mock_cm_cls.return_value = mock_cm

        self.mock_db.fetchone.return_value = _row(status="现行", check_count=1)
        notif_mgr = MagicMock()
        notif_mgr.send_event.side_effect = RuntimeError("send failed")

        # 不应抛异常
        self.checker.update_status("GB/T 12345", "已废止", notification_mgr=notif_mgr)
        self.mock_db.execute.assert_called_once()

    @patch("pilotstd.core.config.ConfigManager")
    def test_no_notification_mgr(self, mock_cm_cls):
        """notification_mgr=None → 不发送通知，UPDATE 正常执行。"""
        mock_cm = MagicMock()
        mock_cm.get.return_value = 4
        mock_cm_cls.return_value = mock_cm

        self.mock_db.fetchone.return_value = _row(status="现行", check_count=1)

        self.checker.update_status("GB/T 12345", "已废止", notification_mgr=None)
        self.mock_db.execute.assert_called_once()


# ════════════════════════════════════════════════════════════════════
# TestGetDueStandards
# ════════════════════════════════════════════════════════════════════

class TestGetDueStandards(unittest.TestCase):
    """覆盖 get_due_standards：有结果/空结果。"""

    def setUp(self):
        self.mock_db = MagicMock()
        self.mock_db.fetchall.return_value = _rows(
            {"name": "id"}, {"name": "standard_number"}, {"name": "last_changed_at"}
        )
        self.checker = ValidityChecker(self.mock_db)
        self.mock_db.reset_mock()

    def test_has_results(self):
        """有到期标准 → 返回标准号列表。"""
        self.mock_db.fetchall.return_value = _rows(
            {"standard_number": "GB/T 1"},
            {"standard_number": "GB/T 2"},
        )
        result = self.checker.get_due_standards()
        self.assertEqual(result, ["GB/T 1", "GB/T 2"])

    def test_no_results(self):
        """无到期标准 → 返回空列表。"""
        self.mock_db.fetchall.return_value = []
        result = self.checker.get_due_standards()
        self.assertEqual(result, [])


# ════════════════════════════════════════════════════════════════════
# TestCountDueStandards
# ════════════════════════════════════════════════════════════════════

class TestCountDueStandards(unittest.TestCase):
    """覆盖 count_due_standards：有/无/零。"""

    def setUp(self):
        self.mock_db = MagicMock()
        self.mock_db.fetchall.return_value = _rows(
            {"name": "id"}, {"name": "standard_number"}, {"name": "last_changed_at"}
        )
        self.checker = ValidityChecker(self.mock_db)
        self.mock_db.reset_mock()

    def test_has_due(self):
        """有到期标准 → 返回数量。"""
        self.mock_db.fetchone.return_value = _row(cnt=42)
        result = self.checker.count_due_standards()
        self.assertEqual(result, 42)

    def test_no_due_fetchone_none(self):
        """fetchone 返回 None → 返回 0。"""
        self.mock_db.fetchone.return_value = None
        result = self.checker.count_due_standards()
        self.assertEqual(result, 0)

    def test_cnt_zero(self):
        """fetchone 返回 cnt=0。"""
        self.mock_db.fetchone.return_value = _row(cnt=0)
        result = self.checker.count_due_standards()
        self.assertEqual(result, 0)


# ════════════════════════════════════════════════════════════════════
# TestGetDueStandardsRandom
# ════════════════════════════════════════════════════════════════════

class TestGetDueStandardsRandom(unittest.TestCase):
    """覆盖 get_due_standards_random：有结果/空/limit 传递。"""

    def setUp(self):
        self.mock_db = MagicMock()
        self.mock_db.fetchall.return_value = _rows(
            {"name": "id"}, {"name": "standard_number"}, {"name": "last_changed_at"}
        )
        self.checker = ValidityChecker(self.mock_db)
        self.mock_db.reset_mock()

    def test_has_results(self):
        """有到期标准 → 返回列表。"""
        self.mock_db.fetchall.return_value = _rows(
            {"standard_number": "GB/T 1"},
            {"standard_number": "GB/T 2"},
        )
        result = self.checker.get_due_standards_random(2)
        self.assertEqual(len(result), 2)

    def test_empty(self):
        """无到期标准 → 返回空列表。"""
        self.mock_db.fetchall.return_value = []
        result = self.checker.get_due_standards_random(10)
        self.assertEqual(result, [])

    def test_limit_applied_in_sql(self):
        """SQL 中使用 LIMIT 子句。"""
        self.mock_db.fetchall.return_value = _rows({"standard_number": "GB/T 1"})
        self.checker.get_due_standards_random(5)
        sql_text = self.mock_db.fetchall.call_args[0][0]
        self.assertIn("LIMIT", sql_text)


# ════════════════════════════════════════════════════════════════════
# TestRandomSlice
# ════════════════════════════════════════════════════════════════════

class TestRandomSlice(unittest.TestCase):
    """覆盖 random_slice 静态方法：空列表/正常切片/同周一致/不同周/小批量/不改原列表。"""

    def test_empty_list(self):
        """空列表 → 返回空列表。"""
        result = ValidityChecker.random_slice([], 1)
        self.assertEqual(result, [])

    def test_normal_slice(self):
        """正常列表 → 返回切片子集。"""
        candidates = [f"GB/T {i}" for i in range(200)]
        result = ValidityChecker.random_slice(candidates, 3)
        # 结果不超过默认 batch_size=50
        self.assertLessEqual(len(result), 50)
        self.assertGreater(len(result), 0)

    def test_consistent_same_week(self):
        """同周号 → 结果一致（固定种子）。"""
        candidates = [f"GB/T {i}" for i in range(200)]
        r1 = ValidityChecker.random_slice(candidates, 3)
        r2 = ValidityChecker.random_slice(candidates, 3)
        self.assertEqual(r1, r2)

    def test_different_weeks(self):
        """不同周号 → 结果大概率不同。"""
        candidates = [f"GB/T {i}" for i in range(200)]
        r1 = ValidityChecker.random_slice(candidates, 1)
        r2 = ValidityChecker.random_slice(candidates, 2)
        self.assertNotEqual(r1, r2)

    def test_original_not_modified(self):
        """原列表不被修改。"""
        candidates = [f"GB/T {i}" for i in range(10)]
        original = list(candidates)
        ValidityChecker.random_slice(candidates, 5)
        self.assertEqual(candidates, original)

    def test_small_candidates(self):
        """候选少于 batch_size → 全部返回。"""
        candidates = ["GB/T 1", "GB/T 2", "GB/T 3"]
        result = ValidityChecker.random_slice(candidates, 0)
        self.assertEqual(len(result), 3)

    def test_custom_batch_size(self):
        """自定义 batch_size。"""
        candidates = [f"STD-{i}" for i in range(100)]
        result = ValidityChecker.random_slice(candidates, 27, batch_size=25)
        self.assertLessEqual(len(result), 25)
        self.assertGreater(len(result), 0)


# ════════════════════════════════════════════════════════════════════
# TestCheckStandard
# ════════════════════════════════════════════════════════════════════

class TestCheckStandard(unittest.TestCase):
    """覆盖 check_standard：L1 命中/L2 命中/L3 命中/全部未命中。"""

    def setUp(self):
        self.mock_db = MagicMock()
        self.mock_db.fetchall.return_value = _rows(
            {"name": "id"}, {"name": "standard_number"}, {"name": "last_changed_at"}
        )
        self.checker = ValidityChecker(self.mock_db)
        self.mock_db.reset_mock()

    # ── L1 命中 ──

    def test_l1_hit_announcement_match(self):
        """L1: announcement_match 表命中 → 返回 status='现行'。"""
        self.mock_db.fetchone.return_value = _row(
            std_name="GB/T 12345 某某标准",
            publish_date="2020-01-01",
        )
        result = self.checker.check_standard("GB/T 12345")
        self.assertIsNotNone(result)
        self.assertEqual(result["status"], "现行")
        self.assertIsNone(result["previous"])

    def test_l1_hit_announcement_record(self):
        """L1: announcement_match 未命中，announcement_record 命中 → 返回废止。"""
        self.mock_db.fetchone.side_effect = [
            None,
            _row(std_name="GB/T 12345 被代替标准", publish_date="2019-01-01"),
        ]
        result = self.checker.check_standard("GB/T 12345")
        self.assertIsNotNone(result)
        self.assertEqual(result["status"], "已废止")

    def test_l1_exception_falls_to_l2(self):
        """L1 查询抛异常 → 抑制后继续 L2。"""
        self.mock_db.fetchone.side_effect = [
            Exception("table missing"),  # announcement_match 异常
            Exception("table missing"),  # announcement_record 异常
            _row(status="现行", last_status=None),  # L3 fallback
        ]
        mock_qe = MagicMock()
        result = self.checker.check_standard("GB/T 12345", query_engine=mock_qe)
        self.assertIsNotNone(result)

    # ── L2 命中 ──

    @patch("pilotstd.core.std_utils.parse_std_number")
    def test_l2_hit_query_engine(self, mock_parse):
        """L1 未命中 → L2 query_engine 返回 is_found=True → 返回状态。"""
        self.mock_db.fetchone.return_value = None
        mock_parse.return_value = {"code": "GB", "number": "12345", "year": 2020}

        from pilotstd.query.models import QueryResult

        mock_result = MagicMock()
        mock_result.is_found.return_value = True
        mock_result.status = "现行"
        mock_qe = MagicMock()
        mock_qe.query_standards.return_value = [mock_result]

        result = self.checker.check_standard("GB/T 12345", query_engine=mock_qe)
        self.assertIsNotNone(result)
        self.assertEqual(result["status"], "现行")

    @patch("pilotstd.core.std_utils.parse_std_number")
    def test_l2_parse_failed_falls_to_l3(self, mock_parse):
        """L2 parse_std_number 返回 None → 落到 L3。"""
        self.mock_db.fetchone.side_effect = [
            None,
            None,
            _row(status="现行", last_status=None),
        ]
        mock_parse.return_value = None
        mock_qe = MagicMock()

        result = self.checker.check_standard("INVALID", query_engine=mock_qe)
        self.assertIsNotNone(result)
        self.assertEqual(result["status"], "现行")

    @patch("pilotstd.core.std_utils.parse_std_number")
    def test_l2_result_not_found_falls_to_l3(self, mock_parse):
        """L2 is_found()=False → 落到 L3。"""
        self.mock_db.fetchone.side_effect = [
            None,
            None,
            _row(status="未知", last_status=None),
        ]
        mock_parse.return_value = {"code": "GB", "number": "12345", "year": 2020}

        # 使用 MagicMock 替代 QueryResult，避免参数名不匹配
        mock_result = MagicMock()
        mock_result.is_found.return_value = False
        mock_qe = MagicMock()
        mock_qe.query_standards.return_value = [mock_result]

        result = self.checker.check_standard("GB/T 12345", query_engine=mock_qe)
        self.assertIsNotNone(result)
        self.assertEqual(result["status"], "未知")

    @patch("pilotstd.core.std_utils.parse_std_number")
    def test_l2_query_engine_raises_falls_to_l3(self, mock_parse):
        """L2 query_engine 抛异常 → 抑制，落到 L3。"""
        self.mock_db.fetchone.side_effect = [
            None,
            None,
            _row(status="现行", last_status=None),
        ]
        mock_parse.return_value = {"code": "GB", "number": "12345", "year": 2020}
        mock_qe = MagicMock()
        mock_qe.query_standards.side_effect = RuntimeError("network error")

        result = self.checker.check_standard("GB/T 12345", query_engine=mock_qe)
        self.assertIsNotNone(result)
        self.assertEqual(result["status"], "现行")

    # ── L3 命中 ──

    def test_l3_hit_standard_validity(self):
        """L1/L2 未命中 → L3 standard_validity 有记录 → 返回 last_status。"""
        self.mock_db.fetchone.side_effect = [
            None,
            None,
            _row(status="现行", last_status="已废止"),
        ]
        result = self.checker.check_standard("GB/T 99999")
        self.assertIsNotNone(result)
        self.assertEqual(result["status"], "现行")
        self.assertEqual(result["previous"], "已废止")

    # ── 全部未命中 ──

    def test_all_miss(self):
        """三级全部未命中 → 返回 None。"""
        self.mock_db.fetchone.return_value = None
        result = self.checker.check_standard("NONEXISTENT")
        self.assertIsNone(result)

    def test_no_query_engine_skips_l2(self):
        """无 query_engine → 跳过 L2，直接走 L3。"""
        self.mock_db.fetchone.side_effect = [
            None,
            None,
            _row(status="现行", last_status=None),
        ]
        result = self.checker.check_standard("GB/T 99999")
        self.assertIsNotNone(result)
        self.assertEqual(result["status"], "现行")


# ════════════════════════════════════════════════════════════════════
# TestDetermineStatus
# ════════════════════════════════════════════════════════════════════

class TestDetermineStatus(unittest.TestCase):
    """覆盖 _determine_status：6 种废止关键词/现行/空名称/None名称。"""

    def setUp(self):
        mock_db = MagicMock()
        mock_db.fetchall.return_value = _rows(
            {"name": "id"}, {"name": "standard_number"}, {"name": "last_changed_at"}
        )
        self.checker = ValidityChecker(mock_db)

    def test_keyword_fei_zhi(self):
        r = self.checker._determine_status("GB/T 1", {"std_name": "关于废止某某标准"})
        self.assertEqual(r["status"], "已废止")

    def test_keyword_zuo_fei(self):
        r = self.checker._determine_status("GB/T 1", {"std_name": "某某标准 已作废"})
        self.assertEqual(r["status"], "已废止")

    def test_keyword_bei_dai_ti(self):
        r = self.checker._determine_status("GB/T 1", {"std_name": "被代替 GB/T 12345"})
        self.assertEqual(r["status"], "已废止")

    def test_keyword_abolished(self):
        r = self.checker._determine_status("BS 1", {"std_name": "Standard (abolished)"})
        self.assertEqual(r["status"], "已废止")

    def test_keyword_withdrawn(self):
        r = self.checker._determine_status("ISO 1", {"std_name": "Withdrawn standard"})
        self.assertEqual(r["status"], "已废止")

    def test_keyword_obsolete(self):
        r = self.checker._determine_status("ISO 1", {"std_name": "Obsolete standard"})
        self.assertEqual(r["status"], "已废止")

    def test_name_no_keyword_active(self):
        r = self.checker._determine_status("GB/T 1", {"std_name": "国家标准"})
        self.assertEqual(r["status"], "现行")

    def test_empty_name_none(self):
        r = self.checker._determine_status("GB/T 1", {"std_name": ""})
        self.assertIsNone(r)

    def test_missing_std_name_key(self):
        r = self.checker._determine_status("GB/T 1", {})
        self.assertIsNone(r)

    def test_none_std_name(self):
        r = self.checker._determine_status("GB/T 1", {"std_name": None})
        self.assertIsNone(r)

    def test_case_insensitive_obsolete(self):
        """大小写不敏感：OBSOLETE 也命中。"""
        r = self.checker._determine_status("ISO 1", {"std_name": "OBSOLETE STANDARD"})
        self.assertEqual(r["status"], "已废止")


# ════════════════════════════════════════════════════════════════════
# TestGetStatusSummary
# ════════════════════════════════════════════════════════════════════

class TestGetStatusSummary(unittest.TestCase):
    """覆盖 get_status_summary：有数据/空数据。"""

    def setUp(self):
        self.mock_db = MagicMock()
        self.mock_db.fetchall.return_value = _rows(
            {"name": "id"}, {"name": "standard_number"}, {"name": "last_changed_at"}
        )
        self.checker = ValidityChecker(self.mock_db)
        self.mock_db.reset_mock()

    def test_has_results(self):
        self.mock_db.fetchall.return_value = _rows(
            {"status": "现行", "cnt": 100},
            {"status": "已废止", "cnt": 20},
        )
        result = self.checker.get_status_summary()
        self.assertEqual(result, {"现行": 100, "已废止": 20})

    def test_no_results(self):
        self.mock_db.fetchall.return_value = []
        result = self.checker.get_status_summary()
        self.assertEqual(result, {})


# ════════════════════════════════════════════════════════════════════
# 模块级函数测试
# ════════════════════════════════════════════════════════════════════

class TestSampleDueStandards(unittest.TestCase):
    """覆盖 _sample_due_standards：无到期/有到期/最小采样数。"""

    def test_no_due(self):
        mock_checker = MagicMock()
        mock_checker.count_due_standards.return_value = 0
        candidates, size = _sample_due_standards(mock_checker, 25)
        self.assertEqual(candidates, [])
        self.assertEqual(size, 0)
        mock_checker.get_due_standards_random.assert_not_called()

    def test_has_due(self):
        mock_checker = MagicMock()
        mock_checker.count_due_standards.return_value = 100
        mock_checker.get_due_standards_random.return_value = ["GB/T 1", "GB/T 2"]
        candidates, size = _sample_due_standards(mock_checker, 25)
        self.assertEqual(len(candidates), 2)
        self.assertEqual(size, 25)  # ceil(100 * 25 / 100) = 25

    def test_sample_size_min_one(self):
        """比例结果小于 1 → 至少取 1 条。"""
        mock_checker = MagicMock()
        mock_checker.count_due_standards.return_value = 2
        mock_checker.get_due_standards_random.return_value = ["GB/T 1"]
        candidates, size = _sample_due_standards(mock_checker, 1)
        self.assertEqual(size, 1)  # max(1, ceil(2 * 1/100)) = 1


class TestProcessValidityBatch(unittest.TestCase):
    """覆盖 _process_validity_batch：空/变更/不变更/异常/批量通知/无通知/通知异常。"""

    def setUp(self):
        self.mock_db = MagicMock()
        self.mock_notif = MagicMock()

    def test_empty_candidates(self):
        mock_checker = MagicMock()
        changed, changed_list, failed = _process_validity_batch(
            [], mock_checker, self.mock_db, self.mock_notif, 50, 5
        )
        self.assertEqual(changed, 0)
        self.assertEqual(changed_list, [])
        self.assertEqual(failed, [])

    def test_status_changed(self):
        mock_checker = MagicMock()
        mock_checker.check_standard.return_value = {"status": "已废止", "previous": "现行"}
        self.mock_db.fetchone.return_value = _row(status="现行")

        changed, changed_list, failed = _process_validity_batch(
            ["GB/T 1"], mock_checker, self.mock_db, self.mock_notif, 50, 5
        )
        self.assertEqual(changed, 1)
        self.assertEqual(changed_list, ["GB/T 1"])

    def test_status_unchanged(self):
        mock_checker = MagicMock()
        mock_checker.check_standard.return_value = {"status": "现行", "previous": None}
        self.mock_db.fetchone.return_value = _row(status="现行")

        changed, changed_list, failed = _process_validity_batch(
            ["GB/T 1"], mock_checker, self.mock_db, self.mock_notif, 50, 5
        )
        self.assertEqual(changed, 0)
        self.assertEqual(changed_list, [])

    def test_check_standard_returns_none(self):
        mock_checker = MagicMock()
        mock_checker.check_standard.return_value = None

        changed, _, _ = _process_validity_batch(
            ["GB/T 1"], mock_checker, self.mock_db, self.mock_notif, 50, 5
        )
        self.assertEqual(changed, 0)

    def test_exception_adds_failed(self):
        mock_checker = MagicMock()
        mock_checker.check_standard.side_effect = RuntimeError("boom")

        _, _, failed = _process_validity_batch(
            ["GB/T 1"], mock_checker, self.mock_db, self.mock_notif, 50, 5
        )
        self.assertEqual(len(failed), 1)
        self.assertEqual(failed[0]["standard"], "GB/T 1")
        self.assertIn("boom", failed[0]["error"])
        self.mock_notif.send_event.assert_called_once_with(
            "validity_standard_failed",
            {"standard_number": "GB/T 1", "error": "boom"},
        )

    def test_batch_notification_at_10_changes(self):
        """每累计 10 条变更 → 发送 validity_batch_report 通知。"""
        mock_checker = MagicMock()
        mock_checker.check_standard.return_value = {"status": "已废止", "previous": "现行"}
        self.mock_db.fetchone.return_value = _row(status="现行")

        candidates = [f"GB/T {i}" for i in range(12)]
        _process_validity_batch(
            candidates, mock_checker, self.mock_db, self.mock_notif, 50, 0
        )
        batch_calls = [
            c for c in self.mock_notif.send_event.call_args_list
            if c[0][0] == "validity_batch_report"
        ]
        self.assertGreaterEqual(len(batch_calls), 1)

    def test_no_notification_mgr(self):
        mock_checker = MagicMock()
        mock_checker.check_standard.return_value = {"status": "已废止", "previous": "现行"}
        self.mock_db.fetchone.return_value = _row(status="现行")

        changed, changed_list, _ = _process_validity_batch(
            ["GB/T 1"], mock_checker, self.mock_db, None, 50, 0
        )
        self.assertEqual(changed, 1)

    def test_notification_raises_in_loop(self):
        """循环内通知抛异常 → 被捕获，不影响后续。"""
        mock_checker = MagicMock()
        mock_checker.check_standard.side_effect = RuntimeError("boom")
        self.mock_notif.send_event.side_effect = RuntimeError("notif boom")

        # 不应抛异常
        _process_validity_batch(
            ["GB/T 1"], mock_checker, self.mock_db, self.mock_notif, 50, 0
        )

    def test_old_status_none_skips_change(self):
        """数据库无旧记录 (old_status=None) → 不计为变更。"""
        mock_checker = MagicMock()
        mock_checker.check_standard.return_value = {"status": "现行", "previous": None}
        self.mock_db.fetchone.return_value = None

        changed, changed_list, _ = _process_validity_batch(
            ["GB/T 1"], mock_checker, self.mock_db, self.mock_notif, 50, 0
        )
        self.assertEqual(changed, 0)
        self.assertEqual(changed_list, [])

    def test_batch_interval_sleep(self):
        """batch_size 间隔触发 sleep。"""
        import time
        mock_checker = MagicMock()
        mock_checker.check_standard.return_value = {"status": "现行", "previous": None}
        self.mock_db.fetchone.return_value = _row(status="现行")

        # 候选 3 条，batch_size=1 → i=1,2 时触发 2 次 sleep
        with patch.object(time, "sleep") as mock_sleep:
            _process_validity_batch(
                ["A", "B", "C"], mock_checker, self.mock_db, None, batch_size=1, batch_interval=2
            )
            self.assertEqual(mock_sleep.call_count, 2)


class TestFinalizeValidityRound(unittest.TestCase):
    """覆盖 _finalize_validity_round 所有分支。"""

    def setUp(self):
        self.mock_config = MagicMock()
        self.mock_db = MagicMock()
        self.mock_notif = MagicMock()
        self.mock_adapter = MagicMock()

    def test_update_counters_false(self):
        result = _finalize_validity_round(
            self.mock_config, self.mock_db, [], [], [],
            self.mock_adapter, self.mock_notif, update_counters=False,
        )
        self.mock_config.set.assert_not_called()
        self.mock_config.save.assert_not_called()

    def test_adapter_raises(self):
        self.mock_adapter.get_all_status.side_effect = RuntimeError("boom")
        self.mock_config.get.return_value = 0
        self.mock_db.fetchone.return_value = _row(cnt=10)

        _finalize_validity_round(
            self.mock_config, self.mock_db, ["GB/T 1"], [], [],
            self.mock_adapter, None, update_counters=True,
        )
        self.mock_config.save.assert_called_once()

    def test_round_not_complete(self):
        """已检查数 < 总数 → 不设置 round_completed。"""
        self.mock_config.get.return_value = 0
        self.mock_db.fetchone.return_value = _row(cnt=100)

        _finalize_validity_round(
            self.mock_config, self.mock_db, ["GB/T 1"], [], [],
            None, None, update_counters=True,
        )
        completed_calls = [
            c for c in self.mock_config.set.call_args_list
            if c[0][0] == "validity.round_completed" and c[0][1] is True
        ]
        self.assertEqual(len(completed_calls), 0)

    def test_round_complete(self):
        """已检查数 >= 总数 → round_completed=True + round_count 递增。"""
        self.mock_config.get.side_effect = lambda key, default=0: {
            "validity.checked_count": 0,
            "validity.round_count": 0,
        }.get(key, default)

        self.mock_db.fetchone.side_effect = [
            _row(cnt=5),
        ]
        self.mock_db.fetchall.return_value = _rows()

        _finalize_validity_round(
            self.mock_config, self.mock_db,
            ["GB/T 1"] * 5, [], [],
            None, self.mock_notif, update_counters=True,
        )
        completed_calls = [
            c for c in self.mock_config.set.call_args_list
            if c[0][0] == "validity.round_completed"
        ]
        self.assertEqual(len(completed_calls), 1)
        self.assertTrue(completed_calls[0][0][1])

    def test_round_complete_with_notification(self):
        """轮次完成 → 发送 validity_round_summary。"""
        self.mock_config.get.side_effect = lambda key, default=0: {
            "validity.checked_count": 0,
            "validity.round_count": 2,
        }.get(key, default)
        self.mock_db.fetchone.side_effect = [
            _row(cnt=3),
        ]
        self.mock_db.fetchall.return_value = _rows(
            {"standard_number": "GB/T 1"},
            {"standard_number": "GB/T 2"},
        )
        self.mock_adapter.get_all_status.return_value = {"std_gov": "ok"}

        _finalize_validity_round(
            self.mock_config, self.mock_db,
            ["GB/T 1", "GB/T 2", "GB/T 3"],
            ["GB/T 1"], [],
            self.mock_adapter, self.mock_notif, update_counters=True,
        )
        self.mock_notif.send_event.assert_called_once()
        call_args = self.mock_notif.send_event.call_args[0]
        self.assertEqual(call_args[0], "validity_round_summary")
        self.assertEqual(call_args[1]["round"], 3)
        self.assertEqual(call_args[1]["total_checks"], 3)
        self.assertEqual(call_args[1]["total_changes"], 2)

    def test_db_total_fetch_fails(self):
        """查询总数抛异常 → 捕获，仍执行 save。"""
        self.mock_config.get.return_value = 0
        self.mock_db.fetchone.side_effect = RuntimeError("db error")

        _finalize_validity_round(
            self.mock_config, self.mock_db, ["GB/T 1"], [], [],
            None, None, update_counters=True,
        )
        self.mock_config.save.assert_called_once()

    def test_round_complete_notification_raises(self):
        """轮次完成通知抛异常 → 捕获，不影响 save。"""
        self.mock_config.get.side_effect = lambda key, default=0: {
            "validity.checked_count": 0,
            "validity.round_count": 0,
        }.get(key, default)
        self.mock_db.fetchone.side_effect = [
            _row(cnt=1),
        ]
        self.mock_db.fetchall.return_value = _rows({"standard_number": "GB/T 1"})
        self.mock_notif.send_event.side_effect = RuntimeError("notif boom")

        _finalize_validity_round(
            self.mock_config, self.mock_db,
            ["GB/T 1"], ["GB/T 1"], [],
            None, self.mock_notif, update_counters=True,
        )
        self.mock_config.save.assert_called_once()

    def test_no_adapter_mgr(self):
        self.mock_config.get.return_value = 0
        self.mock_db.fetchone.return_value = _row(cnt=10)

        adapters = _finalize_validity_round(
            self.mock_config, self.mock_db, ["GB/T 1"], [], [],
            None, None, update_counters=True,
        )
        self.assertEqual(adapters, {})

    def test_total_zero_skip_round_complete(self):
        """总数为 0 → 不触发轮次完成。"""
        self.mock_config.get.return_value = 0
        self.mock_db.fetchone.return_value = _row(cnt=0)

        _finalize_validity_round(
            self.mock_config, self.mock_db, ["GB/T 1"], [], [],
            None, None, update_counters=True,
        )
        completed_calls = [
            c for c in self.mock_config.set.call_args_list
            if c[0][0] == "validity.round_completed"
        ]
        self.assertEqual(len(completed_calls), 0)

    def test_total_fetchone_returns_none(self):
        """fetchone 返回 None → total=0，不触发轮次完成。"""
        self.mock_config.get.return_value = 0
        self.mock_db.fetchone.return_value = None

        _finalize_validity_round(
            self.mock_config, self.mock_db, ["GB/T 1"], [], [],
            None, None, update_counters=True,
        )
        completed_calls = [
            c for c in self.mock_config.set.call_args_list
            if c[0][0] == "validity.round_completed"
        ]
        self.assertEqual(len(completed_calls), 0)


# ════════════════════════════════════════════════════════════════════
# TestRunValidityCheck
# ════════════════════════════════════════════════════════════════════

class TestRunValidityCheck(unittest.TestCase):
    """覆盖 run_validity_check 所有分支。"""

    @patch("pilotstd.core.validity_checker._process_validity_batch")
    @patch("pilotstd.core.validity_checker._finalize_validity_round")
    @patch("pilotstd.core.validity_checker._sample_due_standards")
    @patch("pilotstd.core.config.ConfigManager")
    def test_no_candidates(self, mock_cm_cls, mock_sample, mock_finalize, mock_process):
        """无候选 → 返回 ok=True, checked=0, changed=0。"""
        mock_cm = MagicMock()
        mock_cm.get.side_effect = lambda key, default: {
            "validity.check_ratio": 25,
            "validity.batch_size": 50,
            "validity.batch_interval": 5,
        }.get(key, default)
        mock_cm_cls.return_value = mock_cm
        mock_sample.return_value = ([], 0)

        result = run_validity_check(db=MagicMock(), update_counters=False)
        self.assertTrue(result["ok"])
        self.assertEqual(result["checked"], 0)
        self.assertEqual(result["changed"], 0)
        mock_process.assert_not_called()

    @patch("pilotstd.core.validity_checker._process_validity_batch")
    @patch("pilotstd.core.validity_checker._finalize_validity_round")
    @patch("pilotstd.core.validity_checker._sample_due_standards")
    @patch("pilotstd.core.config.ConfigManager")
    def test_with_candidates_success(
        self, mock_cm_cls, mock_sample, mock_finalize, mock_process,
    ):
        """有候选 → 完整流程成功，发送 validity_batch_report 通知。"""
        mock_cm = MagicMock()
        mock_cm.get.side_effect = lambda key, default: {
            "validity.check_ratio": 25,
            "validity.batch_size": 50,
            "validity.batch_interval": 5,
        }.get(key, default)
        mock_cm_cls.return_value = mock_cm
        mock_sample.return_value = (["GB/T 1", "GB/T 2"], 2)
        mock_process.return_value = (1, ["GB/T 1"], [])
        mock_finalize.return_value = {"std_gov": "ok"}

        notif_mgr = MagicMock()
        result = run_validity_check(
            notification_mgr=notif_mgr, db=MagicMock(), update_counters=True,
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["checked"], 2)
        self.assertEqual(result["changed"], 1)
        notif_mgr.send_event.assert_called_once()
        call_args = notif_mgr.send_event.call_args[0]
        self.assertEqual(call_args[0], "validity_batch_report")

    @patch("pilotstd.core.validity_checker._sample_due_standards")
    @patch("pilotstd.core.config.ConfigManager")
    def test_db_is_none_creates_new(self, mock_cm_cls, mock_sample):
        """db=None → 内部创建 Database 实例。"""
        mock_cm = MagicMock()
        mock_cm.get.side_effect = lambda key, default: {
            "validity.check_ratio": 25,
            "validity.batch_size": 50,
            "validity.batch_interval": 5,
        }.get(key, default)
        mock_cm_cls.return_value = mock_cm
        mock_sample.return_value = ([], 0)

        with patch("pilotstd.core.db.Database") as mock_db_cls:
            with patch("pilotstd.core.config.get_db_path") as mock_gdp:
                mock_gdp.return_value = "/fake/path.db"
                mock_db = MagicMock()
                mock_db_cls.return_value = mock_db

                result = run_validity_check()
                mock_db_cls.assert_called_once_with("/fake/path.db")
                self.assertTrue(result["ok"])

    @patch("pilotstd.core.validity_checker._sample_due_standards")
    @patch("pilotstd.core.config.ConfigManager")
    def test_exception_sends_notification(self, mock_cm_cls, mock_sample):
        """异常 → 返回 ok=False，发送 validity_system_failed。"""
        mock_cm = MagicMock()
        mock_cm.get.return_value = 25
        mock_cm_cls.return_value = mock_cm
        mock_sample.side_effect = RuntimeError("unexpected")

        notif_mgr = MagicMock()
        result = run_validity_check(notification_mgr=notif_mgr, db=MagicMock())
        self.assertFalse(result["ok"])
        self.assertIn("unexpected", result["error"])
        notif_mgr.send_event.assert_called_once()
        call_args = notif_mgr.send_event.call_args[0]
        self.assertEqual(call_args[0], "validity_system_failed")

    @patch("pilotstd.core.validity_checker._sample_due_standards")
    @patch("pilotstd.core.config.ConfigManager")
    def test_exception_no_notification_mgr(self, mock_cm_cls, mock_sample):
        """异常 + notification_mgr=None → 不尝试发通知。"""
        mock_cm = MagicMock()
        mock_cm.get.return_value = 25
        mock_cm_cls.return_value = mock_cm
        mock_sample.side_effect = RuntimeError("unexpected")

        result = run_validity_check(notification_mgr=None, db=MagicMock())
        self.assertFalse(result["ok"])

    @patch("pilotstd.core.validity_checker._sample_due_standards")
    @patch("pilotstd.core.config.ConfigManager")
    def test_exception_notification_raises(self, mock_cm_cls, mock_sample):
        """异常后通知也失败 → 不影响返回。"""
        mock_cm = MagicMock()
        mock_cm.get.return_value = 25
        mock_cm_cls.return_value = mock_cm
        mock_sample.side_effect = RuntimeError("unexpected")

        notif_mgr = MagicMock()
        notif_mgr.send_event.side_effect = RuntimeError("notif boom")

        result = run_validity_check(notification_mgr=notif_mgr, db=MagicMock())
        self.assertFalse(result["ok"])
        self.assertIn("unexpected", result["error"])

    @patch("pilotstd.core.validity_checker._process_validity_batch")
    @patch("pilotstd.core.validity_checker._finalize_validity_round")
    @patch("pilotstd.core.validity_checker._sample_due_standards")
    @patch("pilotstd.core.config.ConfigManager")
    def test_success_notification_raises(
        self, mock_cm_cls, mock_sample, mock_finalize, mock_process,
    ):
        """成功路径通知抛异常 → 被捕获，仍返回 ok=True。"""
        mock_cm = MagicMock()
        mock_cm.get.side_effect = lambda key, default: {
            "validity.check_ratio": 25,
            "validity.batch_size": 50,
            "validity.batch_interval": 5,
        }.get(key, default)
        mock_cm_cls.return_value = mock_cm
        mock_sample.return_value = (["GB/T 1"], 1)
        mock_process.return_value = (0, [], [])
        mock_finalize.return_value = {}

        notif_mgr = MagicMock()
        notif_mgr.send_event.side_effect = RuntimeError("notif boom")

        result = run_validity_check(notification_mgr=notif_mgr, db=MagicMock())
        self.assertTrue(result["ok"])
        self.assertEqual(result["checked"], 1)

    @patch("pilotstd.core.validity_checker._process_validity_batch")
    @patch("pilotstd.core.validity_checker._finalize_validity_round")
    @patch("pilotstd.core.validity_checker._sample_due_standards")
    @patch("pilotstd.core.config.ConfigManager")
    def test_with_adapter_mgr(
        self, mock_cm_cls, mock_sample, mock_finalize, mock_process,
    ):
        """adapter_mgr 传入 → 传递给 _finalize_validity_round。"""
        mock_cm = MagicMock()
        mock_cm.get.side_effect = lambda key, default: {
            "validity.check_ratio": 25,
            "validity.batch_size": 50,
            "validity.batch_interval": 5,
        }.get(key, default)
        mock_cm_cls.return_value = mock_cm
        mock_sample.return_value = (["GB/T 1"], 1)
        mock_process.return_value = (0, [], [])
        mock_finalize.return_value = {"std_gov": "ok"}

        adapter_mgr = MagicMock()
        result = run_validity_check(
            db=MagicMock(), adapter_mgr=adapter_mgr, update_counters=False,
        )
        self.assertTrue(result["ok"])
        mock_finalize.assert_called_once()
        self.assertEqual(mock_finalize.call_args[0][5], adapter_mgr)


if __name__ == "__main__":
    unittest.main()
