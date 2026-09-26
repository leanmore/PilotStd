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
    _get_standard_type,
    _safe_filename,
    download_to_inbox,
)


class TestSafeFilename:
    def test_replaces_illegal_chars(self):
        result = _safe_filename("GB/T:1234*2020", "abc123")
        assert result == "GBT_1234_2020_abc123.pdf"

    def test_normal_standard_number(self):
        result = _safe_filename("GB/T 1234-2020", "xyz789")
        assert result == "GBT 1234-2020_xyz789.pdf"


class TestFavoriteArchiveError:
    def test_is_exception(self):
        err = FavoriteArchiveError("test error")
        assert isinstance(err, Exception)
        assert str(err) == "test error"


class TestGetStandardType:
    """A 修复：类别闸的数据来源（favorite_downloads.standard_type）。"""

    def test_returns_type(self):
        db = MagicMock()
        db.fetchone.return_value = {"standard_type": "NationalStd"}
        assert _get_standard_type(1, db) == "NationalStd"

    def test_missing_returns_empty(self):
        db = MagicMock()
        db.fetchone.return_value = None
        assert _get_standard_type(1, db) == ""


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


# === Added for favorite_download coverage boost (L29-30, L51-66, L103-116) ===


from pilotstd.tasks.favorite_download import (
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


# ── download_to_inbox 主流程（A 修复后契约）──


class TestDownloadToInboxMainFlow:
    """A 修复后的主流程：类别闸 → hcno 取用 → 适配器取字节 → inbox 归档轮询。

    与修复前的差别：下载不再来自"缓存里的 download_url + 裸 requests.get"，
    而是 DownloadEngine.fetch_bytes（经 std_gov→openstd_download 适配器）。
    """

    @staticmethod
    def _query_result(hcno: str = "ABC123", adopted: bool = False):
        return MagicMock(hcno=hcno, is_adopted=adopted)

    _UNSET = object()

    def _run(self, db, mgr, tmp_path, find, query_result=_UNSET):
        """统一打桩后跑一次 download_to_inbox，返回 (sleep_mock, notify_failed_mock)。

        query_result 默认给一个含 hcno 的查询结果；显式传 None 表示"缓存与现场查询都取不到"。
        """
        from contextlib import ExitStack

        if query_result is self._UNSET:
            query_result = self._query_result()
        with ExitStack() as stack:
            stack.enter_context(
                patch("pilotstd.tasks.favorite_download.Database", return_value=db)
            )
            stack.enter_context(
                patch("pilotstd.tasks.favorite_download.get_db_path", return_value=":memory:")
            )
            if isinstance(find, list):
                stack.enter_context(
                    patch(
                        "pilotstd.tasks.favorite_download._find_in_file_index",
                        side_effect=find,
                    )
                )
            else:
                stack.enter_context(
                    patch(
                        "pilotstd.tasks.favorite_download._find_in_file_index",
                        return_value=find,
                    )
                )
            stack.enter_context(
                patch(
                    "pilotstd.tasks.favorite_download._get_inbox_dir",
                    return_value=tmp_path / "tmp" / "inbox",
                )
            )
            stack.enter_context(
                patch(
                    "pilotstd.tasks.favorite_download._load_cached_query_result",
                    return_value=query_result,
                )
            )
            stack.enter_context(
                patch("pilotstd.manager.facade.StandardManager", return_value=mgr)
            )
            stack.enter_context(
                patch("pilotstd.tasks.favorite_download._notify_download_started")
            )
            stack.enter_context(
                patch("pilotstd.tasks.favorite_download._notify_download_complete")
            )
            notify_failed = stack.enter_context(
                patch("pilotstd.tasks.favorite_download._notify_download_failed")
            )
            sleep_mock = stack.enter_context(patch("time.sleep"))
            download_to_inbox(1, 100, 999)
        return sleep_mock, notify_failed

    @staticmethod
    def _db(standard_number: str = "GB/T 1-2020", std_type: str = "NationalStd"):
        db = MagicMock()
        db.execute.return_value.fetchone.side_effect = [
            {"standard_number": standard_number},
        ]
        db.fetchone.return_value = {"standard_type": std_type}
        return db

    def test_download_phase_updates_status_chain(self, tmp_path):
        """正常路径：downloading → archiving → done。"""
        db = self._db()
        mgr = MagicMock()
        mgr.download_engine.fetch_bytes.return_value = (b"pdf data", "")

        self._run(db, mgr, tmp_path, find=[None, "/found/path.pdf"])

        status_updates = [
            c.args[0] for c in db.execute.call_args_list
            if "UPDATE favorite_downloads SET status" in str(c.args[0])
        ]
        assert len(status_updates) >= 3
        assert any("done" in s for s in status_updates)

    def test_polling_loop_finds_file_on_second_check(self, tmp_path):
        """轮询循环：第2次检查找到文件 → sleep 2 次后置 done。"""
        db = self._db()
        mgr = MagicMock()
        mgr.download_engine.fetch_bytes.return_value = (b"pdf data", "")

        sleep_mock, _ = self._run(db, mgr, tmp_path, find=[None, None, "/found/path.pdf"])

        assert sleep_mock.call_count == 2
        done_updates = [c for c in db.execute.call_args_list if "done" in str(c.args[0])]
        assert len(done_updates) >= 1

    def test_polling_loop_timeout_updates_failed(self, tmp_path):
        """轮询超时（30 次都未找到）→ 更新状态为 failed（归档超时）。"""
        db = self._db()
        mgr = MagicMock()
        mgr.download_engine.fetch_bytes.return_value = (b"pdf data", "")

        self._run(db, mgr, tmp_path, find=None)

        timeout_updates = [
            c for c in db.execute.call_args_list if "归档超时" in str(c.args)
        ]
        assert len(timeout_updates) == 1

    # ── 技术债 #29：归档阶段由链路自己触发（不再只等周期机制）──

    def test_archive_step_is_triggered_with_inbox_file(self, tmp_path):
        """场景 1：下载落 inbox 后，链路应调用归档器（解析文件名 + source_path 指向 inbox 文件）。"""
        db = self._db()
        mgr = MagicMock()
        mgr.download_engine.fetch_bytes.return_value = (b"pdf data", "")

        self._run(db, mgr, tmp_path, find=[None, "/lib/found.pdf"])

        mgr.archive_standards.assert_called_once()
        # 必须用规范标准号解析（不能用被 _safe_filename 转义过的 inbox 文件名）
        mgr.parse_standard_number.assert_called_once_with("GB/T 1-2020")
        parsed_list = mgr.archive_standards.call_args.args[0]
        assert len(parsed_list) == 1
        inbox_file = Path(parsed_list[0].source_path)
        assert inbox_file.parent.name == "inbox", inbox_file
        assert inbox_file.suffix == ".pdf"
        # 归档器被调用后，索引命中 → done
        assert any("done" in str(c.args[0]) for c in db.execute.call_args_list)

    def test_archive_error_is_reported_in_timeout_message(self, tmp_path):
        """场景 3：归档器始终未登记索引 → 超时失败，且把归档错误带进 error_message。"""
        db = self._db()
        mgr = MagicMock()
        mgr.download_engine.fetch_bytes.return_value = (b"pdf data", "")
        mgr.archive_standards.side_effect = RuntimeError("organizer down")

        self._run(db, mgr, tmp_path, find=None)

        timeout_updates = [c for c in db.execute.call_args_list if "归档超时" in str(c.args)]
        assert len(timeout_updates) == 1
        assert "文件未被归档器登记进索引" in str(timeout_updates[0].args)
        assert "organizer down" in str(timeout_updates[0].args)

    def test_unparsable_filename_is_reported(self, tmp_path):
        """文件名无法解析 → 不调用归档器，超时文案说明原因（而不是含糊的\"未处理\"）。"""
        db = self._db()
        mgr = MagicMock()
        mgr.download_engine.fetch_bytes.return_value = (b"pdf data", "")
        mgr.parse_standard_number.return_value = None

        self._run(db, mgr, tmp_path, find=None)

        mgr.archive_standards.assert_not_called()
        timeout_updates = [c for c in db.execute.call_args_list if "归档超时" in str(c.args)]
        assert "标准号无法解析" in str(timeout_updates[0].args)

    def test_index_already_has_file_skips_download_and_archive(self, tmp_path):
        """场景 2：索引里已有该文件 → 复用现有文件，直接 done，不重新下载、也不调归档器。"""
        db = self._db()
        mgr = MagicMock()

        self._run(db, mgr, tmp_path, find="/lib/existing.pdf")

        mgr.download_engine.fetch_bytes.assert_not_called()
        mgr.archive_standards.assert_not_called()
        assert any("done" in str(c.args[0]) for c in db.execute.call_args_list)

    def test_no_hcno_raises_favorite_error(self, tmp_path):
        """缓存未命中且现场查询无 hcno → 失败，且不得进入下载阶段。"""
        db = self._db()
        mgr = MagicMock()
        mgr.query_by_numbers.return_value = ([], None)

        self._run(db, mgr, tmp_path, find=None, query_result=None)

        failed_updates = [c for c in db.execute.call_args_list if "failed" in str(c.args[0])]
        assert len(failed_updates) >= 1
        mgr.download_engine.fetch_bytes.assert_not_called()

    def test_download_fails_notifies_and_updates_failed(self, tmp_path):
        """下载失败 → 仅 1 条 download_failed 通知 + 状态 failed。"""
        db = self._db()
        mgr = MagicMock()
        mgr.download_engine.fetch_bytes.return_value = (None, "connection refused")

        _, notify = self._run(db, mgr, tmp_path, find=None)

        notify.assert_called_once()
        call_args = notify.call_args[0]
        assert call_args[0] == 100
        assert call_args[1] == "GB/T 1-2020"
        assert "下载失败" in call_args[2]
        assert call_args[3] == 1
        failed_updates = [c for c in db.execute.call_args_list if "failed" in str(c.args[0])]
        assert len(failed_updates) >= 1

    def test_category_gate_blocks_non_national(self, tmp_path):
        """类别闸：行标在取 hcno 之前就被拒绝，且属**业务终态**（FavoriteSkip）。

        P1（2026-09-21）：终态不写 failed、不发 download_failed，由链路置 abandoned
        并只通知一次（见 tests/test_favorite_chain_processor.py::test_skip_mode_marks_terminal_without_retries）。
        """
        from pilotstd.tasks.favorite_download import FavoriteSkip

        db = self._db(standard_number="HB 1-2020", std_type="IndustryStd")
        mgr = MagicMock()

        with pytest.raises(FavoriteSkip, match="非国标标准"):
            self._run(db, mgr, tmp_path, find=None)

        mgr.query_by_numbers.assert_not_called()
        mgr.download_engine.fetch_bytes.assert_not_called()


