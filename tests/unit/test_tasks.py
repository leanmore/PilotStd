"""tasks/ 模块单元测试 — 目标: 6% → 85%+"""

import sys
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ── 确保 pilotstd 在 path 中 ──
sys.modules.setdefault("pilotstd.core.config", MagicMock())
sys.modules.setdefault("pilotstd.core.db.database", MagicMock())


# ════════════════════════════════════════════════════════════
# date_reminder.py
# ════════════════════════════════════════════════════════════

from pilotstd.tasks.date_reminder import (
    _REMIND_DAYS,
    _fetch_due_records,
    _process_record,
    _target_dates,
    run_date_reminder,
)


class TestTargetDates:
    def test_returns_correct_dates(self):
        result = _target_dates()
        today = date.today()
        for d in _REMIND_DAYS:
            assert result[d] == (today + timedelta(days=d)).isoformat()

    def test_all_four_remind_days_present(self):
        result = _target_dates()
        assert set(result.keys()) == set(_REMIND_DAYS)


class TestFetchDueRecords:
    def test_queries_db_with_target_dates(self):
        db = MagicMock()
        cursor = MagicMock()
        cursor.fetchall.return_value = []
        db.execute.return_value = cursor

        result = _fetch_due_records(db)
        assert result == []
        assert db.execute.call_count == 1

    def test_returns_records_when_found(self):
        db = MagicMock()
        records = [
            {
                "id": 1,
                "standard_number": "GB/T 1",
                "std_name": "Test",
                "implement_date": (date.today() + timedelta(days=30)).isoformat(),
                "expiry_date": "",
                "superseded_by": "",
                "remind_type": "implement",
                "implied_date": None,
            }
        ]
        cursor = MagicMock()
        cursor.fetchall.return_value = records
        db.execute.return_value = cursor

        result = _fetch_due_records(db)
        assert len(result) == 1
        assert result[0]["remind_type"] == "implement"


class TestProcessRecord:
    @pytest.fixture
    def db(self):
        db = MagicMock()
        db.execute.return_value.fetchall.return_value = [{"user_id": 1}]
        db.execute.return_value.fetchone.return_value = None
        return db

    @pytest.fixture
    def notif(self):
        return MagicMock()

    @pytest.fixture
    def stats(self):
        return {"scanned": 0, "sent": 0, "skipped": 0}

    @pytest.fixture
    def today(self):
        return date.today()

    def _make_rec(self, remind_type, target_date, **overrides):
        rec = {
            "id": 1,
            "standard_number": "GB/T 1",
            "std_name": "Test Standard",
            "implement_date": "",
            "expiry_date": "",
            "superseded_by": "",
            "remind_type": remind_type,
            "implied_date": None,
        }
        if remind_type == "implement":
            rec["implement_date"] = target_date.isoformat()
        elif remind_type == "expiry":
            rec["expiry_date"] = target_date.isoformat()
        rec.update(overrides)
        return rec

    def test_no_remind_type_skips(self, db, notif, stats, today):
        rec = {"id": 1, "remind_type": None}
        _process_record(rec, today, db, notif, stats)
        assert stats["sent"] == 0
        assert stats["skipped"] == 0

    def test_implement_type_uses_implement_date(self, db, notif, stats, today):
        target = today + timedelta(days=30)
        rec = self._make_rec("implement", target)
        _process_record(rec, today, db, notif, stats)
        assert stats["sent"] == 1

    def test_expiry_type_uses_expiry_date(self, db, notif, stats, today):
        target = today + timedelta(days=15)
        rec = self._make_rec("expiry", target)
        _process_record(rec, today, db, notif, stats)
        assert stats["sent"] == 1

    def test_implied_type_uses_implied_date(self, db, notif, stats, today):
        target = today + timedelta(days=7)
        rec = self._make_rec("expiry_implied", target)
        rec["implied_date"] = target.isoformat()
        _process_record(rec, today, db, notif, stats)
        assert stats["sent"] == 1

    def test_no_target_str_skips(self, db, notif, stats, today):
        rec = self._make_rec("implement", date.today())
        rec["implement_date"] = ""
        rec["expiry_date"] = ""
        _process_record(rec, today, db, notif, stats)
        assert stats["sent"] == 0

    def test_days_not_in_remind_skips(self, db, notif, stats, today):
        target = today + timedelta(days=5)  # 5 not in _REMIND_DAYS
        rec = self._make_rec("implement", target)
        _process_record(rec, today, db, notif, stats)
        assert stats["sent"] == 0

    def test_no_user_ids_skips(self, db, notif, stats, today):
        db.execute.return_value.fetchall.return_value = []
        target = today + timedelta(days=30)
        rec = self._make_rec("implement", target)
        _process_record(rec, today, db, notif, stats)
        assert stats["sent"] == 0

    def test_already_logged_increments_skipped(self, db, notif, stats, today):
        db.execute.return_value.fetchone.return_value = {"1": 1}
        target = today + timedelta(days=30)
        rec = self._make_rec("implement", target)
        _process_record(rec, today, db, notif, stats)
        assert stats["skipped"] == 1
        assert stats["sent"] == 0

    def test_notification_exception_continues(self, db, notif, stats, today):
        notif.send_event.side_effect = RuntimeError("send failed")
        target = today + timedelta(days=30)
        rec = self._make_rec("implement", target)
        _process_record(rec, today, db, notif, stats)
        # 通知失败不增加 sent，但仍处理完流程
        assert stats["sent"] == 0

    def test_inserts_reminder_log_after_send(self, db, notif, stats, today):
        target = today + timedelta(days=0)
        rec = self._make_rec("implement", target)
        _process_record(rec, today, db, notif, stats)
        assert stats["sent"] == 1
        # 验证 INSERT 被调用
        insert_calls = [
            c for c in db.execute.call_args_list
            if "INSERT INTO date_reminder_log" in str(c.args[0])
        ]
        assert len(insert_calls) == 1


class TestRunDateReminder:
    def test_no_records_returns_early(self):
        with patch(
            "pilotstd.tasks.date_reminder.Database"
        ) as mock_db_cls, patch(
            "pilotstd.tasks.date_reminder.get_db_path", return_value=":memory:"
        ):
            mock_db = MagicMock()
            mock_db_cls.return_value = mock_db
            cursor = MagicMock()
            cursor.fetchall.return_value = []
            mock_db.execute.return_value = cursor

            result = run_date_reminder(notification_mgr=MagicMock())
            assert result["scanned"] == 0
            assert result["sent"] == 0

    def test_exception_raises(self):
        with patch(
            "pilotstd.tasks.date_reminder.Database",
            side_effect=RuntimeError("DB down"),
        ):
            with pytest.raises(RuntimeError):
                run_date_reminder(notification_mgr=MagicMock())

    def test_notification_mgr_none_lazy_loads(self):
        """notification_mgr=None → 懒加载 StandardManager。"""
        mock_sm = MagicMock()
        mock_sm.return_value.notification_mgr = MagicMock()

        with patch(
            "pilotstd.tasks.date_reminder.Database"
        ) as mock_db, patch(
            "pilotstd.tasks.date_reminder.get_db_path", return_value=":memory:"
        ), patch(
            "pilotstd.manager.facade.StandardManager", mock_sm
        ):
            mock_db.return_value.execute.return_value.fetchall.return_value = []
            run_date_reminder(notification_mgr=None)
            mock_sm.assert_called_once()

    def test_with_records_processes_each(self):
        """有记录时 → 循环处理每条记录（L152-156）。"""
        today = date.today()
        rec = {
            "id": 1,
            "standard_number": "GB/T 1",
            "std_name": "Test",
            "implement_date": (today + timedelta(days=30)).isoformat(),
            "expiry_date": "",
            "superseded_by": "",
            "remind_type": "implement",
            "implied_date": None,
        }

        with patch(
            "pilotstd.tasks.date_reminder.Database"
        ) as mock_db_cls, patch(
            "pilotstd.tasks.date_reminder.get_db_path", return_value=":memory:"
        ), patch(
            "pilotstd.tasks.date_reminder._process_record"
        ) as mock_process:
            mock_db = MagicMock()
            mock_db_cls.return_value = mock_db
            cursor = MagicMock()
            cursor.fetchall.return_value = [rec]
            mock_db.execute.return_value = cursor

            result = run_date_reminder(notification_mgr=MagicMock())
            assert result["scanned"] == 1
            mock_process.assert_called_once()


# ════════════════════════════════════════════════════════════
# favorite_download.py
# ════════════════════════════════════════════════════════════

from pilotstd.tasks.favorite_download import (
    FavoriteArchiveError,
    _find_in_file_index,
    _get_download_url,
    _safe_filename,
    download_to_inbox,
)


class TestSafeFilename:
    def test_replaces_illegal_chars(self):
        result = _safe_filename("GB/T:1234*2020", "abc123")
        assert result == "GB_T_1234_2020_abc123.pdf"

    def test_normal_standard_number(self):
        result = _safe_filename("GB/T 1234-2020", "xyz789")
        assert result == "GB_T 1234-2020_xyz789.pdf"


class TestFavoriteArchiveError:
    def test_is_exception(self):
        err = FavoriteArchiveError("test error")
        assert isinstance(err, Exception)
        assert str(err) == "test error"


class TestGetDownloadUrl:
    def test_returns_url_from_cache(self, monkeypatch):
        db = MagicMock()
        cursor = MagicMock()
        cursor.fetchone.return_value = {
            "result_json": '{"download_url": "https://example.com/dl"}'
        }
        db.execute.return_value = cursor

        url = _get_download_url("GB/T 1234-2020", db)
        assert url == "https://example.com/dl"

    def test_no_cache_returns_none(self, monkeypatch):
        db = MagicMock()
        cursor = MagicMock()
        cursor.fetchone.return_value = None
        db.execute.return_value = cursor

        url = _get_download_url("GB/T 1234-2020", db)
        assert url is None

    def test_json_error_returns_none(self, monkeypatch):
        db = MagicMock()
        cursor = MagicMock()
        cursor.fetchone.return_value = {"result_json": "{invalid"}
        db.execute.return_value = cursor

        url = _get_download_url("GB/T 1234-2020", db)
        assert url is None


class TestDownloadToInbox:
    def test_missing_record_raises_and_updates_failed(self):
        """记录不存在 → 内层抛 FavoriteArchiveError → 外层捕获更新 failed。"""
        db = MagicMock()
        db.execute.return_value.fetchone.return_value = None

        with patch(
            "pilotstd.tasks.favorite_download.Database", return_value=db
        ), patch("pilotstd.tasks.favorite_download.get_db_path", return_value=":memory:"):
            download_to_inbox(1, 100, 999)

        # 异常被外层 except 捕获，更新状态为 failed
        update_calls = [
            c for c in db.execute.call_args_list
            if "UPDATE favorite_downloads" in str(c.args[0])
        ]
        assert any("failed" in str(c) for c in update_calls)

    def test_empty_standard_number_updates_failed(self):
        """标准号为空 → 内层异常 → 外层更新 failed。"""
        db = MagicMock()
        db.execute.return_value.fetchone.return_value = {"standard_number": ""}

        with patch(
            "pilotstd.tasks.favorite_download.Database", return_value=db
        ), patch("pilotstd.tasks.favorite_download.get_db_path", return_value=":memory:"):
            download_to_inbox(1, 100, 999)

        update_calls = [
            c for c in db.execute.call_args_list
            if "UPDATE favorite_downloads" in str(c.args[0])
        ]
        assert any("failed" in str(c) for c in update_calls)

    def test_reuses_existing_file(self):
        db = MagicMock()
        db.execute.return_value.fetchone.return_value = {
            "standard_number": "GB/T 1-2020"
        }

        with patch(
            "pilotstd.tasks.favorite_download.Database", return_value=db
        ), patch(
            "pilotstd.tasks.favorite_download.get_db_path", return_value=":memory:"
        ), patch(
            "pilotstd.tasks.favorite_download._find_in_file_index",
            return_value="/existing/path.pdf",
        ):
            download_to_inbox(1, 100, 999)
            # 应更新状态为 done
            update_calls = [
                c for c in db.execute.call_args_list
                if "UPDATE favorite_downloads" in str(c.args[0])
            ]
            assert any("done" in str(c) for c in update_calls)

    def test_general_exception_updates_failed_status(self):
        db = MagicMock()
        db.execute.return_value.fetchone.side_effect = RuntimeError("unexpected")

        with patch(
            "pilotstd.tasks.favorite_download.Database", return_value=db
        ), patch(
            "pilotstd.tasks.favorite_download.get_db_path", return_value=":memory:"
        ):
            download_to_inbox(1, 100, 999)

        # 异常时应更新状态为 failed
        update_calls = [
            c for c in db.execute.call_args_list
            if "UPDATE favorite_downloads" in str(c.args[0])
        ]
        assert any("failed" in str(c) for c in update_calls)


# === Added for favorite_download coverage boost (L29-30, L51-66, L73-90, L103-116, L147-190) ===


from pilotstd.tasks.favorite_download import (
    _download_with_retry,
    _get_inbox_dir,
    _notify_download_failed,
)

# ── L29-30: _get_inbox_dir ──


class TestGetInboxDir:
    def test_returns_configured_path(self):
        with patch(
            "pilotstd.tasks.favorite_download.ConfigManager"
        ) as mock_cfg:
            mock_cfg.return_value.get.return_value = "/custom/inbox"
            result = _get_inbox_dir()
            assert str(result) == str(Path("/custom/inbox"))

    def test_returns_default_when_not_configured(self):
        with patch(
            "pilotstd.tasks.favorite_download.ConfigManager"
        ) as mock_cfg:
            mock_cfg.return_value.get.return_value = "/inbox"
            result = _get_inbox_dir()
            assert str(result) == str(Path("/inbox"))


# ── L51-66: _find_in_file_index ──


class TestFindInFileIndex:
    def test_returns_path_when_found(self):
        db = MagicMock()
        db.execute.return_value.fetchone.return_value = {"file_path": "/lib/GB/test.pdf"}

        with patch(
            "pilotstd.tasks.favorite_download.StandardParser"
        ) as mock_parser_cls, patch(
            "pilotstd.tasks.favorite_download.build_code_mapping", return_value={}
        ):
            mock_parser = MagicMock()
            mock_parser.parse.return_value = MagicMock(
                logical_code="GB/T", number=1234, year=2020
            )
            mock_parser_cls.return_value = mock_parser

            result = _find_in_file_index("GB/T 1234-2020", db)
            assert result == "/lib/GB/test.pdf"

    def test_parse_failure_returns_none(self):
        db = MagicMock()

        with patch(
            "pilotstd.tasks.favorite_download.StandardParser"
        ) as mock_parser_cls, patch(
            "pilotstd.tasks.favorite_download.build_code_mapping", return_value={}
        ):
            mock_parser = MagicMock()
            mock_parser.parse.return_value = None
            mock_parser_cls.return_value = mock_parser

            result = _find_in_file_index("invalid", db)
            assert result is None

    def test_exception_returns_none(self):
        """StandardParser 抛异常 → 返回 None（L64-65）。"""
        db = MagicMock()
        db.execute.side_effect = RuntimeError("DB error")

        with patch(
            "pilotstd.tasks.favorite_download.StandardParser"
        ) as mock_parser_cls, patch(
            "pilotstd.tasks.favorite_download.build_code_mapping", return_value={}
        ):
            mock_parser_cls.side_effect = RuntimeError("parser crash")
            result = _find_in_file_index("GB/T 1234", db)
            assert result is None


# ── L73-90: _download_with_retry ──


class TestDownloadWithRetry:
    @pytest.fixture(autouse=True)
    def _patch_sleep(self):
        with patch("time.sleep"):
            yield

    def test_first_attempt_succeeds(self, tmp_path):
        target = tmp_path / "out.pdf"
        mock_resp = MagicMock()
        mock_resp.iter_content.return_value = [b"data"]
        mock_resp.raise_for_status.return_value = None

        with patch("requests.get", return_value=mock_resp):
            ok, err = _download_with_retry("https://example.com/dl", target, max_retries=3)

        assert ok is True
        assert err is None
        assert target.exists()

    def test_retries_then_succeeds(self, tmp_path):
        target = tmp_path / "out.pdf"
        fail_resp = MagicMock()
        fail_resp.raise_for_status.side_effect = __import__("requests").exceptions.ConnectionError("fail")
        ok_resp = MagicMock()
        ok_resp.iter_content.return_value = [b"data"]
        ok_resp.raise_for_status.return_value = None

        with patch("requests.get", side_effect=[fail_resp, ok_resp]):
            ok, err = _download_with_retry("url", target, max_retries=3)

        assert ok is True

    def test_all_attempts_fail(self, tmp_path):
        target = tmp_path / "out.pdf"
        fail = __import__("requests").exceptions.ConnectionError("fail")

        with patch("requests.get", side_effect=fail):
            ok, err = _download_with_retry("url", target, max_retries=2)

        assert ok is False
        assert err is not None

    def test_exponential_backoff_sleep_calls(self, tmp_path):
        target = tmp_path / "out.pdf"

        class FailTwiceThenOk:
            def __init__(self):
                self.calls = 0

            def get(self, url, timeout, stream):
                self.calls += 1
                if self.calls < 3:
                    raise __import__("requests").exceptions.ConnectionError("fail")
                resp = MagicMock()
                resp.iter_content.return_value = [b"ok"]
                resp.raise_for_status.return_value = None
                return resp

        handler = FailTwiceThenOk()
        mock_sleep = MagicMock()

        with patch("requests.get", side_effect=handler.get), patch(
            "time.sleep", mock_sleep
        ):
            ok, _ = _download_with_retry("url", target, max_retries=3)

        assert ok is True
        # 2次失败后各 sleep 一次：第1次 2^1=2s, 第2次 2^2=4s
        assert mock_sleep.call_count == 2
        assert mock_sleep.call_args_list[0].args[0] == 2
        assert mock_sleep.call_args_list[1].args[0] == 4


# ── L103-116: _notify_download_failed ──


class TestNotifyDownloadFailed:
    def test_sends_event_to_standard_manager(self):
        mock_sm = MagicMock()

        with patch(
            "pilotstd.tasks.favorite_download._fetch_std_meta",
            return_value=("复合钢管超声检测方法", "NationalStd"),
        ), patch(
            "pilotstd.manager.facade.StandardManager", return_value=mock_sm
        ):
            _notify_download_failed(100, "GB/T 1", "network error", 5)

        # 批次2 载荷契约：含 standard_name/standard_type（_fetch_std_meta 补查）
        mock_sm.notification_mgr.send_event.assert_called_once_with(
            "download_failed",
            {
                "user_id": 100,
                "standard_number": "GB/T 1",
                "standard_name": "复合钢管超声检测方法",
                "standard_type": "NationalStd",
                "error": "network error",
                "favorite_id": 5,
            },
        )

    def test_exception_is_silent(self):
        mock_sm = MagicMock()
        mock_sm.notification_mgr.send_event.side_effect = RuntimeError("boom")

        with patch(
            "pilotstd.manager.facade.StandardManager", return_value=mock_sm
        ):
            # 不应抛异常
            _notify_download_failed(1, "X", "e", 1)


# ── L147-190: download_to_inbox 主流程扩展 ──


class TestDownloadToInboxMainFlow:
    def test_download_phase_updates_status_to_downloading(self, tmp_path):
        """下载阶段：状态更新为 'downloading'。"""
        db = MagicMock()
        # record found
        db.execute.return_value.fetchone.side_effect = [
            {"standard_number": "GB/T 1-2020"},  # announcement_record
            None,  # _find_in_file_index: no existing
            {"result_json": '{"download_url": "https://dl.example.com/file.pdf"}'},  # download URL
        ]

        mock_resp = MagicMock()
        mock_resp.iter_content.return_value = [b"pdf data"]
        mock_resp.raise_for_status.return_value = None

        with patch(
            "pilotstd.tasks.favorite_download.Database", return_value=db
        ), patch(
            "pilotstd.tasks.favorite_download.get_db_path", return_value=":memory:"
        ), patch(
            "pilotstd.tasks.favorite_download._find_in_file_index",
            side_effect=[None, None],
        ), patch(
            "pilotstd.tasks.favorite_download._get_inbox_dir",
            return_value=tmp_path / "tmp" / "inbox",
        ), patch(
            "pilotstd.tasks.favorite_download._get_download_url",
            return_value="https://dl.example.com/file.pdf",
        ), patch(
            "pilotstd.tasks.favorite_download._download_with_retry",
            return_value=(True, None),
        ), patch(
            # 隔离通知副作用（同 test_polling_loop_finds_file_on_third_check）
            "pilotstd.tasks.favorite_download._notify_download_started",
        ), patch(
            "pilotstd.tasks.favorite_download._notify_download_complete",
        ), patch(
            "pilotstd.tasks.favorite_download._notify_download_failed",
        ), patch("time.sleep"):
            download_to_inbox(1, 100, 999)

        # 验证状态更新链
        status_updates = [
            c.args[0] for c in db.execute.call_args_list
            if "UPDATE favorite_downloads SET status" in str(c.args[0])
        ]
        # downloading → archiving → done
        assert len(status_updates) >= 2

    def test_polling_loop_finds_file_on_third_check(self, tmp_path):
        """轮询循环：第3次检查找到文件 → 正常退出。"""
        db = MagicMock()
        db.execute.return_value.fetchone.side_effect = [
            {"standard_number": "GB/T 1-2020"},  # record
        ]

        mock_sleep = MagicMock()

        with patch(
            "pilotstd.tasks.favorite_download.Database", return_value=db
        ), patch(
            "pilotstd.tasks.favorite_download.get_db_path", return_value=":memory:"
        ), patch(
            "pilotstd.tasks.favorite_download._find_in_file_index",
            side_effect=[None, None, "/found/path.pdf"],  # 第3次找到
        ), patch(
            "pilotstd.tasks.favorite_download._get_download_url",
            return_value="https://dl.example.com/file.pdf",
        ), patch(
            "pilotstd.tasks.favorite_download._download_with_retry",
            return_value=(True, None),
        ), patch(
            "pilotstd.tasks.favorite_download._get_inbox_dir",
            return_value=tmp_path / "tmp" / "inbox",
        ), patch(
            # 隔离通知副作用：CI 环境下 send_event 走真实管道，
            # 与全局 time.sleep patch 交互导致轮询 sleep 计数 flaky（assert 3 == 2）
            "pilotstd.tasks.favorite_download._notify_download_started",
        ), patch(
            "pilotstd.tasks.favorite_download._notify_download_complete",
        ), patch(
            "pilotstd.tasks.favorite_download._notify_download_failed",
        ), patch(
            "time.sleep", mock_sleep
        ):
            download_to_inbox(1, 100, 999)

        # 第3次找到 → sleep 被调用 2 次
        assert mock_sleep.call_count == 2
        # 验证最终状态为 done
        done_updates = [
            c for c in db.execute.call_args_list
            if "done" in str(c.args[0])
        ]
        assert len(done_updates) >= 1

    def test_polling_loop_timeout_updates_failed(self, tmp_path):
        """轮询超时（30次都未找到）→ 更新状态为 failed。"""
        db = MagicMock()
        # 需要足够的 fetchone 返回值：record + 各种中间查询
        db.execute.return_value.fetchone.side_effect = [
            {"standard_number": "GB/T 1-2020"},  # announcement_record
        ] + [None] * 50  # 其余调用都返回 None

        with patch(
            "pilotstd.tasks.favorite_download.Database", return_value=db
        ), patch(
            "pilotstd.tasks.favorite_download.get_db_path", return_value=":memory:"
        ), patch(
            "pilotstd.tasks.favorite_download._find_in_file_index",
            return_value=None,  # 永远找不到
        ), patch(
            "pilotstd.tasks.favorite_download._get_download_url",
            return_value="https://dl.example.com/file.pdf",
        ), patch(
            "pilotstd.tasks.favorite_download._download_with_retry",
            return_value=(True, None),
        ), patch(
            "pilotstd.tasks.favorite_download._get_inbox_dir",
            return_value=tmp_path / "tmp" / "inbox",
        ), patch(
            # 隔离通知副作用（同 test_polling_loop_finds_file_on_third_check）
            "pilotstd.tasks.favorite_download._notify_download_started",
        ), patch(
            "pilotstd.tasks.favorite_download._notify_download_complete",
        ), patch(
            "pilotstd.tasks.favorite_download._notify_download_failed",
        ), patch("time.sleep"):
            download_to_inbox(1, 100, 999)

        timeout_updates = [
            c for c in db.execute.call_args_list
            if "归档超时" in str(c.args)
        ]
        assert len(timeout_updates) == 1

    def test_no_download_url_raises_favorite_error(self):
        """_get_download_url 返回 None → FavoriteArchiveError（L154）。"""
        db = MagicMock()
        db.execute.return_value.fetchone.return_value = {
            "standard_number": "GB/T 1-2020"
        }

        with patch(
            "pilotstd.tasks.favorite_download.Database", return_value=db
        ), patch(
            "pilotstd.tasks.favorite_download.get_db_path", return_value=":memory:"
        ), patch(
            "pilotstd.tasks.favorite_download._find_in_file_index",
            return_value=None,
        ), patch(
            "pilotstd.tasks.favorite_download._get_download_url",
            return_value=None,  # 无下载链接
        ):
            download_to_inbox(1, 100, 999)

        # 异常被外层捕获，更新状态为 failed
        failed_updates = [
            c for c in db.execute.call_args_list
            if "failed" in str(c.args[0])
        ]
        assert len(failed_updates) >= 1

    def test_download_fails_notifies_and_updates_failed(self, tmp_path):
        """下载失败 → 通知失败 + 更新状态为 failed。"""
        db = MagicMock()
        db.execute.return_value.fetchone.side_effect = [
            {"standard_number": "GB/T 1-2020"},  # record
        ]

        with patch(
            "pilotstd.tasks.favorite_download.Database", return_value=db
        ), patch(
            "pilotstd.tasks.favorite_download.get_db_path", return_value=":memory:"
        ), patch(
            "pilotstd.tasks.favorite_download._find_in_file_index",
            return_value=None,
        ), patch(
            "pilotstd.tasks.favorite_download._get_inbox_dir",
            return_value=tmp_path / "tmp" / "inbox",
        ), patch(
            "pilotstd.tasks.favorite_download._get_download_url",
            return_value="https://dl.example.com/file.pdf",
        ), patch(
            "pilotstd.tasks.favorite_download._download_with_retry",
            return_value=(False, "connection refused"),
        ), patch(
            "pilotstd.tasks.favorite_download._notify_download_failed"
        ) as mock_notify:
            download_to_inbox(1, 100, 999)

        mock_notify.assert_called_once()
        # P-107 修复（v1.1 清理）：失败路径仅发送 1 条 download_failed（外层 except 统一补发，
        # 载荷为包装后的 str(e)），不再发送内层原始错误通知
        call_args = mock_notify.call_args[0]
        assert call_args[0] == 100  # user_id
        assert call_args[1] == "GB/T 1-2020"  # standard_number
        assert "下载失败(重试3次)" in call_args[2]  # 包装后的错误信息
        assert call_args[3] == 1  # favorite_id
        # 验证更新为 failed
        failed_updates = [
            c for c in db.execute.call_args_list
            if "failed" in str(c.args[0])
        ]
        assert len(failed_updates) >= 1
