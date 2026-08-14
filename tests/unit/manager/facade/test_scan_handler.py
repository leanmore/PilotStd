"""_scan.py (ScanHandler) 覆盖率补齐 — 目标: 0% → 95%+"""

from unittest.mock import MagicMock, patch

import pytest

from pilotstd.manager.facade._scan import ScanHandler

# ── Fixtures ──


@pytest.fixture
def mock_core():
    core = MagicMock()
    core.scanner = MagicMock()
    core.parser = MagicMock()
    core.notification_mgr = MagicMock()
    core.last_skipped_dirs = []
    core.parsed_results = []
    core.file_index = MagicMock()
    core.cfg = MagicMock()
    core.db = MagicMock()
    core._file_watcher = None
    core.scheduled_svc = MagicMock()
    return core


@pytest.fixture
def handler(mock_core):
    return ScanHandler(mock_core)


def _make_file(filename: str, full_path: str = ""):
    """构造模拟的扫描文件对象。"""
    f = MagicMock()
    f.filename = filename
    f.full_path = full_path or f"/fake/root/{filename}"
    return f


def _make_scan_result(files: list, skipped_dirs: list = None):
    """构造模拟的扫描结果对象。"""
    r = MagicMock()
    r.files = files
    r.skipped_dirs = skipped_dirs or []
    return r


# ════════════════════════════════════════════════════════════
# T1: scan_directory 基础路径
# ════════════════════════════════════════════════════════════


class TestScanDirectory:
    def test_happy_path_parses_and_dedupes(self, handler, mock_core):
        """正常扫描 → 解析去重 + 扩展名统计 + 通知。"""
        f1 = _make_file("GB_T_1234-2020.pdf")
        f2 = _make_file("GB_T_1234-2020.pdf")  # 同名重复 → 去重
        f3 = _make_file("SH_T_56-2021.doc")

        scan_result = _make_scan_result([f1, f2, f3])
        mock_core.scanner.scan.return_value = scan_result

        parsed_info = MagicMock()
        parsed_info.logical_code = "GB/T"
        parsed_info.number = 1234
        parsed_info.year = 2020
        parsed_info.part = None
        # f1 → parsed; f2 → dup; f3 → parsed
        mock_core.parser.parse.side_effect = [
            parsed_info,
            parsed_info,  # f2 same parse result → dup
            MagicMock(logical_code="SH/T", number=56, year=2021, part=None),
        ]

        result = handler.scan_directory("/fake/root")

        assert len(result) == 2
        mock_core.notification_mgr.send_event.assert_any_call(
            "scan_complete", {"count": 2, "failed": 0}
        )

    def test_empty_directory_sends_scan_empty(self, handler, mock_core):
        """空目录 → scan_empty 通知。"""
        mock_core.scanner.scan.return_value = _make_scan_result([])

        result = handler.scan_directory("/empty")
        assert result == []
        mock_core.notification_mgr.send_event.assert_called_with("scan_empty", {})

    def test_notification_manager_none_no_crash(self, handler, mock_core):
        """notification_mgr=None → 不发送通知，不崩溃。"""
        mock_core.notification_mgr = None
        mock_core.scanner.scan.return_value = _make_scan_result([])

        result = handler.scan_directory("/root")
        assert result == []

    def test_notification_exception_caught(self, handler, mock_core):
        """send_event 抛异常 → 捕获继续。"""
        mock_core.notification_mgr.send_event.side_effect = RuntimeError("boom")
        mock_core.scanner.scan.return_value = _make_scan_result(
            [_make_file("GB_T_1-2020.pdf")]
        )
        parsed = MagicMock(logical_code="GB/T", number=1, year=2020, part=None)
        mock_core.parser.parse.return_value = parsed

        result = handler.scan_directory("/root")
        assert len(result) == 1  # 即使通知失败，扫描结果不受影响

    def test_stores_last_skipped_dirs(self, handler, mock_core):
        """scan 返回的 skipped_dirs → 存入 core.last_skipped_dirs。"""
        mock_core.scanner.scan.return_value = _make_scan_result(
            [], skipped_dirs=["/skip1", "/skip2"]
        )
        handler.scan_directory("/root")
        assert mock_core.last_skipped_dirs == ["/skip1", "/skip2"]

    def test_extension_stats_counted(self, handler, mock_core):
        """扩展名统计被正确写入 result.ext_stats。"""
        f1 = _make_file("a.pdf")
        f2 = _make_file("b.docx")
        f3 = _make_file("c.txt")

        scan_result = _make_scan_result([f1, f2, f3])
        mock_core.scanner.scan.return_value = scan_result
        mock_core.parser.parse.side_effect = [
            MagicMock(logical_code="GB/T", number=1, year=2020, part=None),
            MagicMock(logical_code="GB/T", number=2, year=2020, part=None),
            MagicMock(logical_code="GB/T", number=3, year=2020, part=None),
        ]

        handler.scan_directory("/root")
        ext_stats = scan_result.ext_stats
        assert ext_stats["pdf"] == 1
        assert ext_stats["docx"] == 1
        assert ext_stats["other"] == 1

    def test_cache_invalidation_called(self, handler, mock_core):
        """扫描后 → CacheManager.invalidate_by_source 被调用。"""
        mock_core.scanner.scan.return_value = _make_scan_result([])
        mock_cache = MagicMock()

        with patch(
            "pilotstd.core.cache_manager.CacheManager", return_value=mock_cache
        ), patch(
            "pilotstd.core.cache_manager.DataSource"
        ):
            handler.scan_directory("/root")

        mock_cache.invalidate_by_source.assert_called_once()

    def test_cache_invalidation_import_error_caught(self, handler, mock_core):
        """CacheManager 导入失败 → 捕获继续（L82-83）。"""
        mock_core.scanner.scan.return_value = _make_scan_result([])

        real_import = __import__

        def mock_import(name, *args, **kwargs):
            if name == "pilotstd.core.cache_manager":
                raise ImportError("no cache manager")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            result = handler.scan_directory("/root")

        assert result == []

    def test_no_files_but_parsed_list_cleared(self, handler, mock_core):
        """无文件时 parsed_results 被清空。"""
        mock_core.scanner.scan.return_value = _make_scan_result([])
        result = handler.scan_directory("/root")
        assert result == []
        assert mock_core.parsed_results == []


# ════════════════════════════════════════════════════════════
# T2: scan_directory_stream
# ════════════════════════════════════════════════════════════


class TestScanDirectoryStream:
    def test_stream_with_progress_and_batch(self, handler, mock_core):
        """流式扫描 — on_progress + on_batch 回调。"""
        files = [_make_file(f"doc_{i}.pdf") for i in range(25)]
        mock_core.scanner.scan.return_value = _make_scan_result(files)
        mock_core.parser.parse.side_effect = [
            MagicMock(logical_code="GB/T", number=i, year=2020, part=None)
            for i in range(25)
        ]
        on_progress = MagicMock()
        on_batch = MagicMock()

        result = handler.scan_directory_stream(
            "/root", on_progress=on_progress, on_batch=on_batch
        )

        assert len(result) == 25
        assert on_progress.call_count == 25
        # 20 items → batch, then 5 remaining → batch
        assert on_batch.call_count == 2

    def test_stream_no_callbacks_works(self, handler, mock_core):
        """无回调 → 正常扫描不崩溃。"""
        mock_core.scanner.scan.return_value = _make_scan_result([_make_file("a.pdf")])
        mock_core.parser.parse.return_value = MagicMock(
            logical_code="GB/T", number=1, year=2020, part=None
        )

        result = handler.scan_directory_stream("/root")
        assert len(result) == 1

    def test_stream_empty_result(self, handler, mock_core):
        """空结果 → 返回空列表 + scan_empty 通知。"""
        mock_core.scanner.scan.return_value = _make_scan_result([])

        result = handler.scan_directory_stream("/root")
        assert result == []
        mock_core.notification_mgr.send_event.assert_called_with("scan_empty", {})

    def test_stream_notification_exception_caught(self, handler, mock_core):
        """流式通知抛异常 → 捕获继续。"""
        mock_core.notification_mgr.send_event.side_effect = RuntimeError("boom")
        mock_core.scanner.scan.return_value = _make_scan_result(
            [_make_file("a.pdf")]
        )
        mock_core.parser.parse.return_value = MagicMock(
            logical_code="GB/T", number=1, year=2020, part=None
        )

        result = handler.scan_directory_stream("/root")
        assert len(result) == 1

    def test_stream_dedup_logs_when_duplicates(self, handler, mock_core, caplog):
        """流式扫描有重复 → dup_count 日志（L114, L126）。"""
        import logging

        caplog.set_level(logging.INFO)
        # 两个同名文件 → 第二个触发去重
        mock_core.scanner.scan.return_value = _make_scan_result(
            [_make_file("a.pdf"), _make_file("a.pdf")]
        )
        info = MagicMock(logical_code="GB/T", number=1, year=2020, part=None)
        mock_core.parser.parse.return_value = info

        result = handler.scan_directory_stream("/root")
        assert len(result) == 1
        assert any("去重" in rec.message for rec in caplog.records)


# ════════════════════════════════════════════════════════════
# T3: scan_and_index
# ════════════════════════════════════════════════════════════


class TestScanAndIndex:
    def test_happy_path(self, handler, mock_core):
        """正常 → 委托 scheduled_svc + 通知。"""
        mock_core.scheduled_svc.scan_and_index.return_value = {
            "indexed": 3,
            "skipped": 0,
            "failed": 0,
        }

        result = handler.scan_and_index()
        assert result["indexed"] == 3
        mock_core.notification_mgr.send_event.assert_any_call(
            "scan_complete", {"count": 3, "failed": 0}
        )

    def test_empty_result_sends_scan_empty(self, handler, mock_core):
        """indexed=0 + failed=0 → scan_empty。"""
        mock_core.scheduled_svc.scan_and_index.return_value = {
            "indexed": 0,
            "skipped": 0,
            "failed": 0,
        }

        handler.scan_and_index()
        mock_core.notification_mgr.send_event.assert_called_with("scan_empty", {})

    def test_scheduled_svc_exception_sends_auto_scan_failed(self, handler, mock_core):
        """scheduled_svc 异常 → auto_scan_failed 通知 + 返回兜底结果。"""
        mock_core.scheduled_svc.scan_and_index.side_effect = RuntimeError("DB error")

        result = handler.scan_and_index("/custom/path")
        assert result == {"indexed": 0, "skipped": 0, "failed": 1}
        mock_core.notification_mgr.send_event.assert_any_call(
            "auto_scan_failed",
            {"path": "/custom/path", "error": "DB error"},
        )

    def test_scheduled_svc_exception_no_notification_mgr(self, handler, mock_core):
        """异常 + notification_mgr=None → 不崩溃。"""
        mock_core.notification_mgr = None
        mock_core.scheduled_svc.scan_and_index.side_effect = RuntimeError("boom")

        result = handler.scan_and_index()
        assert result == {"indexed": 0, "skipped": 0, "failed": 1}

    def test_notification_exception_in_try_block(self, handler, mock_core):
        """正常路径通知抛异常 → 捕获继续。"""
        mock_core.scheduled_svc.scan_and_index.return_value = {
            "indexed": 5, "skipped": 0, "failed": 0,
        }
        mock_core.notification_mgr.send_event.side_effect = RuntimeError("notif boom")

        result = handler.scan_and_index()
        assert result["indexed"] == 5  # 不因通知异常中断

    def test_auto_scan_failed_notification_exception_caught(self, handler, mock_core):
        """异常路径通知也失败 → 双重捕获。"""
        mock_core.scheduled_svc.scan_and_index.side_effect = RuntimeError("DB down")
        mock_core.notification_mgr.send_event.side_effect = RuntimeError("notif down")

        result = handler.scan_and_index()
        assert result == {"indexed": 0, "skipped": 0, "failed": 1}


# ════════════════════════════════════════════════════════════
# T4: start_watching / stop_watching
# ════════════════════════════════════════════════════════════


class TestStartWatching:
    def test_creates_watcher_and_starts(self, handler, mock_core):
        """首次调用 → 创建 FileWatcher 并启动。"""
        mock_watcher = MagicMock()

        with patch(
            "pilotstd.scan.watcher.FileWatcher", return_value=mock_watcher
        ), patch(
            "pilotstd.manager.facade._scan.get_library_root", return_value="/lib"
        ):
            handler.start_watching(["/watch/path"])

        assert mock_core._file_watcher is mock_watcher
        mock_watcher.start.assert_called_once_with(["/watch/path"])

    def test_watcher_already_exists_noop(self, handler, mock_core):
        """watcher 已存在 → 不重复创建。"""
        mock_core._file_watcher = MagicMock()

        handler.start_watching()
        # 不应重新创建

    def test_import_error_handled(self, handler, mock_core, caplog):
        """watchdog 未安装 → ImportError 捕获 + warning。"""
        import logging

        caplog.set_level(logging.WARNING)

        with patch(
            "pilotstd.scan.watcher.FileWatcher",
            side_effect=ImportError("no watchdog"),
        ):
            handler.start_watching()

        assert any("watchdog" in rec.message.lower() for rec in caplog.records)

    def test_general_exception_handled(self, handler, mock_core, caplog):
        """一般异常 → 捕获 + warning。"""
        import logging

        caplog.set_level(logging.WARNING)

        with patch(
            "pilotstd.scan.watcher.FileWatcher",
            side_effect=RuntimeError("unexpected"),
        ):
            handler.start_watching()

        assert any("启动文件监控失败" in rec.message for rec in caplog.records)


class TestStopWatching:
    def test_stops_existing_watcher(self, handler, mock_core):
        """已有 watcher → 调用 stop + 置 None。"""
        mock_watcher = MagicMock()
        mock_core._file_watcher = mock_watcher

        handler.stop_watching()
        mock_watcher.stop.assert_called_once()
        assert mock_core._file_watcher is None

    def test_no_watcher_noop(self, handler, mock_core):
        """没有 watcher → 不崩溃。"""
        mock_core._file_watcher = None
        handler.stop_watching()


# ════════════════════════════════════════════════════════════
# T5: scan_stream 别名
# ════════════════════════════════════════════════════════════


class TestScanStream:
    def test_delegates_to_scan_directory_stream(self, handler, mock_core):
        """scan_stream → 委托到 scan_directory_stream。"""
        mock_core.scanner.scan.return_value = _make_scan_result([])

        result = handler.scan_stream("/root")
        assert result == []

    def test_passes_callbacks_through(self, handler, mock_core):
        """on_progress + on_batch → 透传到 scan_directory_stream。"""
        mock_core.scanner.scan.return_value = _make_scan_result([])
        on_progress = MagicMock()
        on_batch = MagicMock()

        handler.scan_stream("/root", on_progress=on_progress, on_batch=on_batch)
        # 验证委托调用成功（不抛异常）
