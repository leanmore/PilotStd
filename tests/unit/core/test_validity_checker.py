"""validity_checker.py — 纯逻辑函数 + mockable 管线全覆盖。

跳过: get_due_standards/count_due_standards/get_due_standards_random/get_status_summary（纯 DB 查询）
跳过: _ensure_last_changed_at_column（DB 迁移 DDL）
"""

from unittest.mock import MagicMock, patch

import pytest

from pilotstd.core.validity_checker import ValidityChecker


@pytest.fixture
def db():
    db = MagicMock()
    db.fetchone.return_value = None
    db.fetchall.return_value = []
    return db


@pytest.fixture
def checker(db):
    return ValidityChecker(db)


# ════════════════════════════════════════════════════════════
# _determine_status — 纯关键字匹配
# ════════════════════════════════════════════════════════════

class TestDetermineStatus:
    def test_abolished_keyword(self, checker):
        r = checker._determine_status("GB 1", {"std_name": "GB 1（废止）"})
        assert r["status"] == "已废止"

    def test_withdrawn_keyword(self, checker):
        r = checker._determine_status("GB 2", {"std_name": "GB 2 Withdrawn"})
        assert r["status"] == "已废止"

    def test_obsolete_keyword(self, checker):
        r = checker._determine_status("GB 3", {"std_name": "GB 3 Obsolete"})
        assert r["status"] == "已废止"

    def test_current_standard(self, checker):
        r = checker._determine_status("GB 4", {"std_name": "GB 4 现行标准"})
        assert r["status"] == "现行"

    def test_empty_name_returns_none(self, checker):
        r = checker._determine_status("GB 5", {"std_name": ""})
        assert r is None

    def test_no_std_name_returns_none(self, checker):
        r = checker._determine_status("GB 6", {})
        assert r is None


# ════════════════════════════════════════════════════════════
# random_slice — 纯算法（static method）
# ════════════════════════════════════════════════════════════

class TestRandomSlice:
    def test_empty_returns_empty(self):
        assert ValidityChecker.random_slice([], 1) == []

    def test_deterministic_same_week(self):
        candidates = [str(i) for i in range(100)]
        s1 = ValidityChecker.random_slice(candidates, 42)
        s2 = ValidityChecker.random_slice(candidates, 42)
        assert s1 == s2

    def test_different_weeks_different(self):
        candidates = [str(i) for i in range(100)]
        s1 = ValidityChecker.random_slice(candidates, 1)
        s2 = ValidityChecker.random_slice(candidates, 99)
        assert s1 != s2

    def test_does_not_modify_original(self):
        candidates = ["a", "b", "c"]
        original = list(candidates)
        ValidityChecker.random_slice(candidates, 1)
        assert candidates == original


# ════════════════════════════════════════════════════════════
# register_new_standard — mock DB
# ════════════════════════════════════════════════════════════

class TestRegisterNewStandard:
    def test_inserts_when_not_existing(self, checker, db):
        db.fetchone.return_value = None
        db.reset_mock()
        checker.register_new_standard("GB/T 1-2020")
        insert_calls = [
            c for c in db.execute.call_args_list if "INSERT" in str(c.args[0])
        ]
        assert len(insert_calls) == 1

    def test_skips_when_existing(self, checker, db):
        db.fetchone.return_value = {"id": 1}
        db.reset_mock()
        checker.register_new_standard("GB/T 1-2020")
        insert_calls = [
            c for c in db.execute.call_args_list if "INSERT" in str(c.args[0])
        ]
        assert len(insert_calls) == 0

    def test_sends_event_when_notif_mgr_present(self, checker, db):
        db.fetchone.return_value = None
        notif = MagicMock()
        checker.register_new_standard("GB/T 1-2020", notification_mgr=notif)
        notif.send_event.assert_called_once()

    def test_notif_exception_caught(self, checker, db):
        db.fetchone.return_value = None
        notif = MagicMock()
        notif.send_event.side_effect = RuntimeError("boom")
        checker.register_new_standard("GB/T 1-2020", notification_mgr=notif)


# ════════════════════════════════════════════════════════════
# update_status — mock DB + ConfigManager
# ════════════════════════════════════════════════════════════

class TestUpdateStatus:
    def test_inserts_when_not_existing(self, checker, db):
        db.fetchone.return_value = None
        with patch(
            "pilotstd.core.config.ConfigManager"
        ) as mock_cfg:
            mock_cfg.return_value.get.return_value = 4
            checker.update_status("GB/T 1-2020", "现行")
        assert db.execute.call_count >= 1

    def test_updates_when_status_changed(self, checker, db):
        db.fetchone.return_value = {"status": "现行", "check_count": 0}
        with patch(
            "pilotstd.core.config.ConfigManager"
        ) as mock_cfg:
            mock_cfg.return_value.get.return_value = 4
            checker.update_status("GB/T 1-2020", "已废止")
        assert db.execute.call_count >= 1

    def test_updates_when_status_unchanged(self, checker, db):
        db.fetchone.return_value = {"status": "现行", "check_count": 0}
        with patch(
            "pilotstd.core.config.ConfigManager"
        ) as mock_cfg:
            mock_cfg.return_value.get.return_value = 4
            checker.update_status("GB/T 1-2020", "现行")
        assert db.execute.call_count >= 1

    def test_sends_status_changed_event(self, checker, db):
        db.fetchone.return_value = {"status": "现行", "check_count": 0}
        notif = MagicMock()
        with patch(
            "pilotstd.core.config.ConfigManager"
        ) as mock_cfg:
            mock_cfg.return_value.get.return_value = 4
            checker.update_status("GB/T 1-2020", "已废止", notification_mgr=notif)
        calls = [c.args[0] for c in notif.send_event.call_args_list]
        assert "standard_status_changed" in calls

    def test_expired_merged_into_status_changed(self, checker, db):
        """standard_expired 已合并：废止仅发 standard_status_changed（is_expired=True），不再发独立事件。"""
        db.fetchone.return_value = {"status": "现行", "check_count": 0}
        notif = MagicMock()
        with patch(
            "pilotstd.core.config.ConfigManager"
        ) as mock_cfg:
            mock_cfg.return_value.get.return_value = 4
            checker.update_status("GB/T 1-2020", "已废止", notification_mgr=notif)
        calls = [c.args[0] for c in notif.send_event.call_args_list]
        assert calls == ["standard_status_changed"]
        sent_data = notif.send_event.call_args_list[0][0][1]
        assert sent_data["is_expired"] is True
        assert sent_data["new_status"] == "已废止"


# ════════════════════════════════════════════════════════════
# check_standard — L1/L2/L3 管线
# ════════════════════════════════════════════════════════════

class TestCheckStandard:
    def test_l1_cache_hit(self, checker, db):
        db.fetchone.return_value = {"std_name": "GB 1 现行标准"}
        r = checker.check_standard("GB/T 1-2020")
        assert r["status"] == "现行"

    def test_l1_cache_abolished(self, checker, db):
        db.fetchone.return_value = {"std_name": "GB 1（废止）"}
        r = checker.check_standard("GB/T 1-2020")
        assert r["status"] == "已废止"

    def test_l1_exception_falls_to_l3(self, checker, db):
        db.fetchone.side_effect = [
            RuntimeError("L1 fail"),  # announcement_record
            {"status": "现行", "last_status": "已废止"},  # L3
        ]
        r = checker.check_standard("GB/T 1-2020")
        assert r["status"] == "现行"

    def test_l3_returns_history(self, checker, db):
        db.fetchone.side_effect = [
            None,  # announcement_record
            {"status": "已废止", "last_status": "现行"},  # L3
        ]
        r = checker.check_standard("GB/T 1-2020")
        assert r["status"] == "已废止"

    def test_all_levels_fail_returns_none(self, checker, db):
        db.fetchone.return_value = None
        r = checker.check_standard("GB/T 1-2020")
        assert r is None
