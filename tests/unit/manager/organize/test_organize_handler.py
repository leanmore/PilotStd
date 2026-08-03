"""_organize.py (OrganizeHandler) 覆盖率补齐 — 目标: 27% → 90%+"""

import json
import logging
import warnings
import pytest
from unittest.mock import MagicMock, patch

from pilotstd.manager.facade._organize import OrganizeHandler
from pilotstd.core.notification import EVENT_ARCHIVE_COMPLETE
from pilotstd.models import ParsedStdInfo


# ── Fixtures ──


@pytest.fixture
def handler(mock_core):
    return OrganizeHandler(mock_core)


def _make_parsed(**kwargs) -> ParsedStdInfo:
    """快速构造 ParsedStdInfo，默认值可被 kwargs 覆盖。"""
    defaults = dict(
        raw_filename="test.pdf",
        logical_code="GB",
        number=1,
        year=2020,
        std_name="",
        source_path="",
        found_name="",
    )
    defaults.update(kwargs)
    return ParsedStdInfo(**defaults)


# ════════════════════════════════════════════════════════════
# _backfill_std_name
# ════════════════════════════════════════════════════════════

class TestBackfillStdName:
    def test_already_has_name_no_db_call(self, handler):
        """已有 std_name → 直接返回，不查 DB。"""
        p = _make_parsed(std_name="已有名称")
        result = handler._backfill_std_name(p)
        assert result.std_name == "已有名称"
        handler._core.db.fetchone.assert_not_called()

    def test_backfill_from_found_name(self, handler):
        """found_name 非空 → 直接回填，不查 DB。"""
        p = _make_parsed(found_name="  来自搜索的名称  ")
        result = handler._backfill_std_name(p)
        assert result.std_name == "来自搜索的名称"
        handler._core.db.fetchone.assert_not_called()

    def test_cache_hit_json_string(self, handler):
        """缓存命中（JSON 字符串）→ 解析并回填。"""
        p = _make_parsed(year=2020)
        cache_data = json.dumps({"standard_name": "缓存标准名"})
        handler._core.db.fetchone.return_value = {"result_json": cache_data}

        result = handler._backfill_std_name(p)
        assert result.std_name == "缓存标准名"
        handler._core.db.fetchone.assert_called_once()

    def test_cache_hit_dict_value(self, handler):
        """缓存命中（dict 值，非字符串）→ 直接读取。"""
        p = _make_parsed(year=2020)
        handler._core.db.fetchone.return_value = {
            "result_json": {"standard_name": "字典名称"}
        }
        result = handler._backfill_std_name(p)
        assert result.std_name == "字典名称"

    def test_cache_miss_returns_unchanged(self, handler):
        """缓存未命中 → std_name 保持空。"""
        p = _make_parsed(year=2020)
        handler._core.db.fetchone.return_value = None
        result = handler._backfill_std_name(p)
        assert result.std_name == ""

    def test_json_decode_error_ignored(self, handler):
        """JSON 解析失败 → 安全忽略。"""
        p = _make_parsed(year=2020)
        handler._core.db.fetchone.return_value = {"result_json": "{invalid json"}
        result = handler._backfill_std_name(p)
        assert result.std_name == ""

    def test_db_exception_returns_unchanged(self, handler):
        """DB 查询抛异常 → 安全忽略，返回原对象。"""
        p = _make_parsed(year=2020)
        handler._core.db.fetchone.side_effect = RuntimeError("DB connection lost")
        result = handler._backfill_std_name(p)
        assert result.std_name == ""


# ════════════════════════════════════════════════════════════
# archive_standards
# ════════════════════════════════════════════════════════════

class TestArchiveStandards:
    def test_happy_path_calls_organize_and_sends_event(self, handler):
        """正常归档 → organizer_svc.organize + EVENT_ARCHIVE_COMPLETE。"""
        items = [_make_parsed(std_name="已填充")]
        handler._core.organizer_svc.organize.return_value = {
            "moved": 2, "failed": 0
        }

        result = handler.archive_standards(parsed_list=items)

        handler._core.organizer_svc.organize.assert_called_once_with(
            items, None, overwrite=False
        )
        handler._core.notification_mgr.send_event.assert_any_call(
            EVENT_ARCHIVE_COMPLETE, {"count": 2}
        )
        assert result["moved"] == 2

    def test_backfill_counter_logged(self, handler, caplog):
        """回填计数 → 日志输出。"""
        caplog.set_level(logging.INFO, logger="pilotstd.manager.facade._organize")

        p1 = _make_parsed(std_name="", found_name="回填名")
        p2 = _make_parsed(std_name="已有")
        handler._core.organizer_svc.organize.return_value = {
            "moved": 0, "failed": 0
        }

        handler.archive_standards(parsed_list=[p1, p2])
        assert any("回填" in rec.message for rec in caplog.records)

    def test_expired_standard_triggers_expire_event(self, handler):
        """废止标准 → expire_standard_moved 事件。"""
        p = _make_parsed(
            effect_status="废止", source_path="/src/expired.pdf"
        )
        handler._core.organizer_svc.organize.return_value = {
            "moved": 1, "failed": 0
        }

        handler.archive_standards(parsed_list=[p])

        handler._core.notification_mgr.send_event.assert_any_call(
            "expire_standard_moved",
            {"standard_number": "GB 1-2020", "target_path": "/src/expired.pdf"},
        )

    def test_no_notification_mgr_no_crash(self, handler):
        """notification_mgr=None → 不崩溃。"""
        handler._core.notification_mgr = None
        items = [_make_parsed()]
        handler._core.organizer_svc.organize.return_value = {
            "moved": 1, "failed": 0
        }

        result = handler.archive_standards(parsed_list=items)
        assert result["moved"] == 1

    def test_validity_checker_exception_caught(self, handler):
        """validity_checker.register_new_standard 异常 → 捕获继续。"""
        handler._core.validity_checker.register_new_standard.side_effect = (
            RuntimeError("checker boom")
        )
        items = [_make_parsed()]
        handler._core.organizer_svc.organize.return_value = {
            "moved": 1, "failed": 0
        }

        result = handler.archive_standards(parsed_list=items)
        assert result["moved"] == 1

    def test_no_moved_skips_expire_event(self, handler):
        """moved=0 → 不触发废止事件，但仍发 ARCHIVE_COMPLETE。"""
        p = _make_parsed(effect_status="废止")
        handler._core.organizer_svc.organize.return_value = {
            "moved": 0, "failed": 0
        }

        handler.archive_standards(parsed_list=[p])

        expire_calls = [
            c
            for c in handler._core.notification_mgr.send_event.call_args_list
            if c.args[0] == "expire_standard_moved"
        ]
        assert len(expire_calls) == 0
        handler._core.notification_mgr.send_event.assert_any_call(
            EVENT_ARCHIVE_COMPLETE, {"count": 0}
        )


# ════════════════════════════════════════════════════════════
# organize (deprecated) + organize_stream (deprecated)
# ════════════════════════════════════════════════════════════

class TestDeprecatedMethods:
    def test_organize_emits_deprecation_warning(self, handler):
        """organize() → DeprecationWarning。"""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            handler.organize(parsed_list=[])
            assert any(
                issubclass(x.category, DeprecationWarning) for x in w
            )

    def test_organize_stream_calls_organize_per_item(self, handler):
        """organize_stream() → 逐条调用 organize + on_progress。"""
        items = [_make_parsed()]
        handler._core.organizer_svc.organize.return_value = {
            "moved": 1, "failed": 0
        }

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            progress = MagicMock()
            on_result = MagicMock()
            result = handler.organize_stream(
                parsed_list=items,
                on_progress=progress,
                on_result=on_result,
            )

        assert any(
            issubclass(x.category, DeprecationWarning) for x in w
        )
        assert result["moved"] == 1
        progress.assert_called_once_with(1, 1)
        on_result.assert_called_once()

    def test_organize_stream_exception_counts_failed(self, handler):
        """organize_stream 中 organize 抛异常 → failed += 1。"""
        items = [_make_parsed()]
        handler._core.organizer_svc.organize.side_effect = RuntimeError("boom")

        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            on_result = MagicMock()
            result = handler.organize_stream(
                parsed_list=items, on_result=on_result
            )

        assert result["failed"] == 1
        on_result.assert_called_with(0, "归档失败")


# ════════════════════════════════════════════════════════════
# organize_files / expire_files
# ════════════════════════════════════════════════════════════

class TestOrganizeAndExpireFiles:
    def test_organize_files_valid(self, handler, tmp_path):
        """有效文件 → 解析 + archive_standards。"""
        f1 = tmp_path / "GB_1234-2020.pdf"
        f1.touch()
        handler._core.parser.parse.return_value = _make_parsed(
            source_path=str(f1)
        )

        with patch.object(handler, "archive_standards") as mock_archive:
            handler.organize_files([str(f1)])

        mock_archive.assert_called_once()
        parsed_arg = mock_archive.call_args[0][0]
        assert len(parsed_arg) == 1

    def test_organize_files_skips_nonexistent(self, handler):
        """不存在的文件 → 跳过，不解析。"""
        result = handler.organize_files(["/no/such/file.pdf"])
        assert result["moved"] == 0
        handler._core.parser.parse.assert_not_called()

    def test_organize_files_no_valid_returns_empty(self, handler, tmp_path):
        """文件存在但解析失败 → 返回空结果。"""
        f1 = tmp_path / "unparseable.xyz"
        f1.touch()
        handler._core.parser.parse.return_value = None

        result = handler.organize_files([str(f1)])
        assert result["moved"] == 0
        assert "无有效文件" in str(result["details"])

    def test_expire_files_marks_status(self, handler, tmp_path):
        """expire_files → effect_status='废止'。"""
        f1 = tmp_path / "GB_9999-2019.pdf"
        f1.touch()
        handler._core.parser.parse.return_value = _make_parsed(
            source_path=str(f1)
        )

        handler.expire_files([str(f1)])

        parsed_arg = handler._core.organizer_svc.organize.call_args[0][0]
        assert parsed_arg[0].effect_status == "废止"

    def test_expire_files_no_valid(self, handler, tmp_path):
        """expire_files 无有效文件 → 返回空。"""
        f1 = tmp_path / "bad.xyz"
        f1.touch()
        handler._core.parser.parse.return_value = None

        result = handler.expire_files([str(f1)])
        assert result["moved"] == 0


# ════════════════════════════════════════════════════════════
# normalize_files_stream
# ════════════════════════════════════════════════════════════

class TestNormalizeFilesStream:
    def test_stream_progress_and_result(self, handler):
        """正常流 → on_progress 逐条调用，返回结果列表。"""
        items = [
            _make_parsed(number=i, std_name=f"标准{i}") for i in range(3)
        ]
        progress = MagicMock()

        with patch.object(
            handler, "_make_archive_filename", side_effect=lambda p: f"file_{p.number}.pdf"
        ), patch(
            "pilotstd.organizer.industry_lookup.get_folder_name",
            return_value="国标",
        ):
            result = handler.normalize_files_stream(
                items, on_progress=progress
            )

        assert len(result) == 3
        assert progress.call_count == 3

    def test_stream_batch_callback_at_50(self, handler):
        """>=50 条 → on_batch 被触发 2 次（50 + 剩余）。"""
        items = [
            _make_parsed(number=i, std_name=f"标准{i}") for i in range(55)
        ]
        batch_cb = MagicMock()

        with patch.object(
            handler, "_make_archive_filename", return_value="f.pdf"
        ), patch(
            "pilotstd.organizer.industry_lookup.get_folder_name",
            return_value="国标",
        ):
            result = handler.normalize_files_stream(
                items, on_batch=batch_cb
            )

        assert len(result) == 55
        assert batch_cb.call_count == 2

    def test_stream_exception_sends_normalize_failed(self, handler):
        """异常 → normalize_failed 事件 + 重新抛出。"""
        items = [_make_parsed()]

        with patch.object(
            handler,
            "_make_archive_filename",
            side_effect=RuntimeError("boom"),
        ):
            with pytest.raises(RuntimeError, match="boom"):
                handler.normalize_files_stream(items)

        handler._core.notification_mgr.send_event.assert_any_call(
            "normalize_failed", {"total": 1, "error": "boom"}
        )

    def test_stream_complete_event_sent(self, handler):
        """正常完成 → normalize_complete 事件。"""
        items = [_make_parsed(std_name="test")]

        with patch.object(
            handler, "_make_archive_filename", return_value="f.pdf"
        ), patch(
            "pilotstd.organizer.industry_lookup.get_folder_name",
            return_value="国标",
        ):
            handler.normalize_files_stream(items)

        handler._core.notification_mgr.send_event.assert_any_call(
            "normalize_complete", {"total": 1, "success": 1, "failed": 0}
        )
