"""monitor/ 模块高价值单元测试 — ROI 定向覆盖 7 个业务函数。
================================================================
跳过的透传/胶水代码（0 测试——ROI 为零）:
  - __init__.py: 纯重导出
  - config._db(), _get_db(), get_config(), set_config(): DB I/O
  - config.MonitorStats._flush(), flush_and_close(): DB I/O
  - config.get_monitor_stats(): 简单单例
  - handler.on_created/on_modified/on_moved: 纯委托 _handle
  - scheduler.get_scheduler(): 简单单例
  - scheduler.start/stop/_run: watchdog/线程生命周期 → E2E 范围
================================================================
"""

import os
import threading
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest

from pilotstd.monitor.config import MonitorStats
from pilotstd.monitor.handler import StandardFileHandler
from pilotstd.monitor.scheduler import (
    FileMonitorScheduler,
    resolve_monitor_config,
)

# ── 共享 fixtures ──


@pytest.fixture
def scheduler():
    s = FileMonitorScheduler()
    s._mgr = MagicMock()
    s._mgr.scan_directory.return_value = [MagicMock()]
    return s


# ════════════════════════════════════════════════════════════
# 1. resolve_monitor_config — 三级回退链
# ════════════════════════════════════════════════════════════


class TestResolveMonitorConfig:
    def test_env_var_wins_over_all(self):
        cfg = {"watch_path": "/db/path", "delay_seconds": 10, "recursive": False}
        with patch.dict(os.environ, {"PILOTSTD_STORAGE_INBOX_DIR": "/env/path"}):
            result = resolve_monitor_config(cfg)
        assert result["watch_path"] == "/env/path"
        assert result["delay_seconds"] == 10

    def test_db_value_when_env_missing(self):
        cfg = {"watch_path": "/db/path", "delay_seconds": 8, "recursive": True}
        with patch.dict(os.environ, {}, clear=True):
            result = resolve_monitor_config(cfg)
        assert result["watch_path"] == "/db/path"

    def test_fallback_to_default(self):
        cfg = {}
        with patch.dict(os.environ, {}, clear=True):
            result = resolve_monitor_config(cfg)
        assert result["watch_path"] == "/tmp/pilotstd-inbox"
        assert result["delay_seconds"] == 5
        assert result["recursive"] is True

    def test_cfg_none_calls_get_config(self):
        with patch(
            "pilotstd.monitor.scheduler.get_config",
            return_value={"watch_path": "/from/db", "delay_seconds": 3, "recursive": False},
        ), patch.dict(os.environ, {}, clear=True):
            result = resolve_monitor_config(None)
        assert result["watch_path"] == "/from/db"

    def test_env_empty_string_uses_cfg(self):
        cfg = {"watch_path": "/cfg/path"}
        with patch.dict(os.environ, {"PILOTSTD_STORAGE_INBOX_DIR": ""}):
            result = resolve_monitor_config(cfg)
        assert result["watch_path"] == "/cfg/path"


# ════════════════════════════════════════════════════════════
# 2. MonitorStats — _ensure_date + increment
# ════════════════════════════════════════════════════════════


class TestMonitorStatsEnsureDate:
    def test_first_call_initializes_date(self):
        stats = MonitorStats()
        assert stats._stats_date == date.today().isoformat()

    def test_same_day_no_flush(self):
        stats = MonitorStats()
        stats._stats = {"processed": 5, "success": 3, "failed": 2}
        stats._dirty = True

        with patch.object(stats, "_flush") as mock_flush:
            stats._ensure_date()

        mock_flush.assert_not_called()
        assert stats._stats == {"processed": 5, "success": 3, "failed": 2}

    def test_date_changed_triggers_flush_and_reset(self):
        stats = MonitorStats()
        stats._stats = {"processed": 10, "success": 8, "failed": 2}
        stats._dirty = True
        stats._stats_date = (date.today() - timedelta(days=1)).isoformat()

        with patch.object(stats, "_flush") as mock_flush:
            stats._ensure_date()

        mock_flush.assert_called_once()
        assert stats._stats == {"processed": 0, "success": 0, "failed": 0}
        assert stats._stats_date == date.today().isoformat()
        assert stats._dirty is False


class TestMonitorStatsIncrement:
    def test_existing_key_increments(self):
        stats = MonitorStats()
        stats.increment("processed")
        assert stats._stats["processed"] == 1
        assert stats._dirty is True

    def test_unknown_key_ignored(self):
        stats = MonitorStats()
        stats.increment("nonexistent_key")
        assert stats._dirty is False

    def test_multiple_increments_accumulate(self):
        stats = MonitorStats()
        for _ in range(5):
            stats.increment("success")
        assert stats._stats["success"] == 5

    def test_thread_safety_accumulates_correctly(self):
        stats = MonitorStats()

        def worker():
            for _ in range(100):
                stats.increment("processed")

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert stats._stats["processed"] == 400

    def test_get_today_stats_returns_copy(self):
        stats = MonitorStats()
        stats.increment("processed")
        s = stats.get_today_stats()
        s["processed"] = 999
        assert stats._stats["processed"] == 1


# ════════════════════════════════════════════════════════════
# 3. StandardFileHandler._should_handle
# ════════════════════════════════════════════════════════════


class TestShouldHandle:
    @pytest.fixture
    def handler(self):
        return StandardFileHandler(callback=lambda p: None)

    _DEFAULT_CFG = {
        "file_patterns": [".pdf", ".docx", ".doc"],
        "ignore_patterns": ["~$", ".tmp", ".swp"],
    }

    def test_allowed_extension_returns_true(self, handler):
        with patch(
            "pilotstd.monitor.handler.get_config", return_value=self._DEFAULT_CFG
        ):
            assert handler._should_handle("/path/doc.pdf") is True

    def test_disallowed_extension_returns_false(self, handler):
        with patch(
            "pilotstd.monitor.handler.get_config", return_value=self._DEFAULT_CFG
        ):
            assert handler._should_handle("/path/file.txt") is False

    def test_dotfile_returns_false(self, handler):
        with patch(
            "pilotstd.monitor.handler.get_config", return_value=self._DEFAULT_CFG
        ):
            assert handler._should_handle("/path/.hidden.pdf") is False

    def test_ignore_pattern_matched_returns_false(self, handler):
        with patch(
            "pilotstd.monitor.handler.get_config", return_value=self._DEFAULT_CFG
        ):
            assert handler._should_handle("/path/~$temp.docx") is False

    def test_tmp_file_ignored(self, handler):
        with patch(
            "pilotstd.monitor.handler.get_config", return_value=self._DEFAULT_CFG
        ):
            assert handler._should_handle("/path/report.tmp") is False

    def test_chinese_filename_allowed(self, handler):
        with patch(
            "pilotstd.monitor.handler.get_config",
            return_value={"file_patterns": [".pdf"], "ignore_patterns": []},
        ):
            assert handler._should_handle("/path/标准文件.pdf") is True


# ════════════════════════════════════════════════════════════
# 4. StandardFileHandler._handle — 去重 + Timer
# ════════════════════════════════════════════════════════════


class TestHandle:
    @pytest.fixture
    def handler(self):
        return StandardFileHandler(callback=lambda p: None, delay_seconds=5)

    def test_new_file_adds_to_pending_and_starts_timer(self, handler):
        with patch.object(handler, "_should_handle", return_value=True), patch(
            "pilotstd.monitor.handler.threading.Timer"
        ) as mock_timer, patch("pilotstd.monitor.handler.time.sleep"):
            handler._handle("/path/new.pdf")

        assert "/path/new.pdf" in handler._pending
        mock_timer.assert_called_once()

    def test_duplicate_file_skipped(self, handler):
        handler._pending["/path/new.pdf"] = 1234567890.0

        with patch.object(handler, "_should_handle", return_value=True), patch(
            "pilotstd.monitor.handler.threading.Timer"
        ) as mock_timer:
            handler._handle("/path/new.pdf")

        mock_timer.assert_not_called()

    def test_should_handle_false_skips(self, handler):
        with patch.object(handler, "_should_handle", return_value=False), patch(
            "pilotstd.monitor.handler.threading.Timer"
        ) as mock_timer:
            handler._handle("/path/ignore.txt")

        mock_timer.assert_not_called()
        assert "/path/ignore.txt" not in handler._pending


# ════════════════════════════════════════════════════════════
# 5. FileMonitorScheduler._on_file
# ════════════════════════════════════════════════════════════


class TestOnFile:
    def test_auto_archive_enabled_calls_manager(self, scheduler):
        with patch(
            "pilotstd.monitor.scheduler.get_config",
            return_value={"auto_archive": True},
        ), patch(
            "pilotstd.monitor.scheduler.get_monitor_stats",
            return_value=MagicMock(),
        ):
            scheduler._on_file("/inbox/test.pdf")

        scheduler._mgr.scan_directory.assert_called_once()

    def test_auto_archive_disabled_skips(self, scheduler):
        with patch(
            "pilotstd.monitor.scheduler.get_config",
            return_value={"auto_archive": False},
        ), patch(
            "pilotstd.monitor.scheduler.get_monitor_stats",
            return_value=MagicMock(),
        ):
            scheduler._on_file("/inbox/test.pdf")

        scheduler._mgr.scan_directory.assert_not_called()

    def test_manager_exception_increments_failed(self, scheduler):
        scheduler._mgr.scan_directory.side_effect = RuntimeError("scan boom")
        mock_stats = MagicMock()

        with patch(
            "pilotstd.monitor.scheduler.get_config",
            return_value={"auto_archive": True},
        ), patch(
            "pilotstd.monitor.scheduler.get_monitor_stats",
            return_value=mock_stats,
        ):
            scheduler._on_file("/inbox/bad.pdf")

        mock_stats.increment.assert_any_call("processed")
        mock_stats.increment.assert_any_call("failed")

    def test_manager_none_lazy_loads(self, scheduler):
        scheduler._mgr = None
        mock_mgr = MagicMock()
        mock_mgr.scan_directory.return_value = [MagicMock()]

        with patch(
            "pilotstd.monitor.scheduler.get_config",
            return_value={"auto_archive": True},
        ), patch(
            "pilotstd.monitor.scheduler.get_monitor_stats",
            return_value=MagicMock(),
        ), patch(
            "pilotstd.manager.facade.StandardManager", return_value=mock_mgr
        ):
            scheduler._on_file("/inbox/test.pdf")

        assert scheduler._mgr is mock_mgr

    def test_scan_empty_no_success_increment(self, scheduler):
        scheduler._mgr.scan_directory.return_value = []
        mock_stats = MagicMock()

        with patch(
            "pilotstd.monitor.scheduler.get_config",
            return_value={"auto_archive": True},
        ), patch(
            "pilotstd.monitor.scheduler.get_monitor_stats",
            return_value=mock_stats,
        ):
            scheduler._on_file("/inbox/empty.pdf")

        success_calls = [
            c for c in mock_stats.increment.call_args_list
            if c.args[0] == "success"
        ]
        assert len(success_calls) == 0

    # ── 技术债 #30：计数口径必须反映**真实归档结果** ──

    def _run_on_file(self, scheduler, archive_result, path="/inbox/GB_T 1-2020.pdf"):
        """跑一次 _on_file，返回 stats mock 与 archive_standards mock。"""
        scheduler._mgr.scan_directory.return_value = [MagicMock()]
        scheduler._mgr.archive_standards.return_value = archive_result
        mock_stats = MagicMock()
        with patch(
            "pilotstd.monitor.scheduler.get_config",
            return_value={"auto_archive": True},
        ), patch(
            "pilotstd.monitor.scheduler.get_monitor_stats",
            return_value=mock_stats,
        ):
            scheduler._on_file(path)
        return mock_stats, scheduler._mgr.archive_standards

    @staticmethod
    def _counts(mock_stats) -> dict:
        out: dict[str, int] = {}
        for c in mock_stats.increment.call_args_list:
            out[c.args[0]] = out.get(c.args[0], 0) + 1
        return out

    def test_real_archive_increments_success(self, scheduler):
        """场景 2：文件真被归档（moved>0）→ success 增加。"""
        mock_stats, _ = self._run_on_file(scheduler, {"moved": 1, "failed": 0})

        assert self._counts(mock_stats) == {"processed": 1, "success": 1}

    def test_nothing_moved_does_not_increment_success(self, scheduler):
        """场景 1：解析到了但一条都没搬（源文件已不在/目标已存在）→ 不计 success。"""
        mock_stats, _ = self._run_on_file(
            scheduler, {"moved": 0, "failed": 0, "skipped_source": 1}
        )

        assert self._counts(mock_stats) == {"processed": 1}

    def test_unparsable_file_increments_failed(self, scheduler):
        """场景 3：文件不合规（解析不出标准号）→ failed 增加，且不调归档。"""
        scheduler._mgr.scan_directory.return_value = []
        mock_stats = MagicMock()
        with patch(
            "pilotstd.monitor.scheduler.get_config",
            return_value={"auto_archive": True},
        ), patch(
            "pilotstd.monitor.scheduler.get_monitor_stats",
            return_value=mock_stats,
        ):
            scheduler._on_file("/inbox/scan_0001.pdf")

        assert self._counts(mock_stats) == {"processed": 1, "failed": 1}
        scheduler._mgr.archive_standards.assert_not_called()

    def test_organizer_reported_failure_increments_failed(self, scheduler):
        """归档器返回 failed>0（真搬不动）→ failed 增加，不记 success。"""
        mock_stats, _ = self._run_on_file(
            scheduler, {"moved": 0, "failed": 2, "details": ["磁盘只读"]}
        )

        assert self._counts(mock_stats) == {"processed": 1, "failed": 1}

    def test_archive_receives_inbox_dir_as_word_source_root(self, scheduler):
        """契约：word_source_root 必须是 inbox 目录（organizer 据此镜像 Word 相对路径）。"""
        _, archive = self._run_on_file(
            scheduler, {"moved": 1}, path="/inbox/sub/GB_T 1-2020.pdf"
        )

        assert archive.call_args.kwargs["word_source_root"] == "/inbox/sub"
        assert archive.call_args.args[0] is scheduler._mgr.scan_directory.return_value


# ════════════════════════════════════════════════════════════
# 6. FileMonitorScheduler.get_status
# ════════════════════════════════════════════════════════════


class TestGetStatus:
    def test_aggregates_all_fields(self, scheduler):
        mock_stats = MagicMock()
        mock_stats.get_today_stats.return_value = {
            "processed": 10, "success": 8, "failed": 2
        }

        with patch(
            "pilotstd.monitor.scheduler.get_config",
            return_value={"enabled": True, "watch_path": "/watch", "delay_seconds": 3},
        ), patch(
            "pilotstd.monitor.scheduler.get_monitor_stats",
            return_value=mock_stats,
        ):
            status = scheduler.get_status()

        assert status["running"] is False
        assert status["enabled"] is True
        assert status["watch_path"] == "/watch"
        assert status["delay_seconds"] == 3
        assert status["processed_today"] == 10
        assert status["success_today"] == 8
        assert status["failed_today"] == 2

    def test_running_flag_reflects_state(self, scheduler):
        scheduler.running = True

        with patch(
            "pilotstd.monitor.scheduler.get_config",
            return_value={"enabled": True, "watch_path": "/w", "delay_seconds": 5},
        ), patch(
            "pilotstd.monitor.scheduler.get_monitor_stats",
            return_value=MagicMock(
                get_today_stats=MagicMock(
                    return_value={"processed": 0, "success": 0, "failed": 0}
                )
            ),
        ):
            status = scheduler.get_status()

        assert status["running"] is True
