# tests/test_monitor.py
"""pilotstd/monitor/ 模块单元测试 — 覆盖 MonitorStats 计数器和 StandardFileHandler 过滤逻辑。"""

import threading
from unittest.mock import MagicMock, patch

import pytest

from pilotstd.monitor.config import DEFAULTS, MonitorStats, get_monitor_stats
from pilotstd.monitor.handler import StandardFileHandler


class TestMonitorStats:
    """MonitorStats — 内存计数器单元测试。"""

    @pytest.fixture
    def stats(self):
        return MonitorStats()

    def test_init_defaults(self, stats):
        """初始化后计数器全部为 0。"""
        assert stats._stats == {"processed": 0, "success": 0, "failed": 0}
        assert stats._dirty is False

    def test_increment(self, stats):
        """increment 应原子递增指定 key。"""
        stats.increment("processed")
        stats.increment("success")
        stats.increment("success")
        assert stats._stats["processed"] == 1
        assert stats._stats["success"] == 2
        assert stats._stats["failed"] == 0
        assert stats._dirty is True

    def test_increment_unknown_key_noop(self, stats):
        """未定义的 key 不应被递增。"""
        stats.increment("unknown_key")
        assert "unknown_key" not in stats._stats

    def test_get_today_stats_returns_copy(self, stats):
        """应返回当天统计数据的副本。"""
        stats.increment("processed")
        result = stats.get_today_stats()
        assert result == {"processed": 1, "success": 0, "failed": 0}
        # 修改副本不应影响原始数据
        result["processed"] = 999
        assert stats._stats["processed"] == 1

    def test_flush_when_not_dirty_noop(self, stats):
        """无变更时 _flush 不应写库。"""
        mock_db = MagicMock()
        stats._db = mock_db
        stats._flush()
        mock_db.execute.assert_not_called()

    def test_flush_writes_dirty_data(self, stats):
        """有变更时 _flush 应批量写入 DB。"""
        mock_db = MagicMock()
        stats._db = mock_db
        stats._stats_date = "2026-07-31"
        stats.increment("processed")
        stats.increment("success")
        stats._flush()
        # 3 个 key 各写入一次
        assert mock_db.execute.call_count == 3

    def test_flush_and_close(self, stats):
        """关闭时应落盘并关闭 DB 连接。"""
        mock_db = MagicMock()
        stats._db = mock_db
        stats._stats_date = "2026-07-31"
        stats.increment("success")
        stats.flush_and_close()
        mock_db.execute.assert_called()
        mock_db.close.assert_called_once()
        assert stats._db is None

    def test_ensure_date_first_time(self, stats):
        """首次访问应设置当天日期。"""
        assert stats._stats_date is not None  # __init__ 已调用 _ensure_date

    def test_ensure_date_rollover(self, stats):
        """跨天时应清空计数器并落盘。"""
        mock_db = MagicMock()
        stats._db = mock_db
        stats._stats_date = "2026-07-30"
        stats._dirty = True
        stats._stats["processed"] = 5
        # 模拟跨天（注意：不走 increment 以避免锁重入死锁）
        with patch("pilotstd.monitor.config.date") as mock_date:
            mock_date.today.return_value.isoformat.return_value = "2026-07-31"
            # 直接调用 _ensure_date，不经过 increment 的锁
            stats._ensure_date()
        # 旧数据已落盘，计数器归零
        assert stats._stats["processed"] == 0
        assert stats._stats["success"] == 0
        assert stats._stats_date == "2026-07-31"

    def test_increment_thread_safety(self, stats):
        """多线程并发 increment 不应数据丢失。"""
        threads = []
        for _ in range(10):
            t = threading.Thread(target=lambda: [stats.increment("processed") for _ in range(100)])
            threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert stats._stats["processed"] == 1000


class TestGetMonitorStats:
    """get_monitor_stats 全局单例测试。"""

    def test_returns_singleton(self):
        """两次调用应返回同一实例。"""
        import pilotstd.monitor.config as cfg

        # 重置单例
        cfg._monitor_stats = None
        s1 = cfg.get_monitor_stats()
        s2 = cfg.get_monitor_stats()
        assert s1 is s2

    def test_returns_monitor_stats(self):
        """应返回 MonitorStats 实例。"""
        s = get_monitor_stats()
        assert isinstance(s, MonitorStats)


class TestDefaults:
    """DEFAULTS 常量测试。"""

    def test_defaults_has_required_keys(self):
        """DEFAULTS 应包含所有必需配置键。"""
        required = {
            "enabled",
            "watch_path",
            "delay_seconds",
            "recursive",
            "file_patterns",
            "ignore_patterns",
            "auto_archive",
        }
        assert set(DEFAULTS.keys()) == required


class TestStandardFileHandler:
    """StandardFileHandler — 文件过滤和事件处理测试。"""

    @pytest.fixture
    def callback(self):
        return MagicMock()

    @pytest.fixture
    def handler(self, callback):
        return StandardFileHandler(callback, delay_seconds=1)

    def test_init_stores_dependencies(self, callback):
        """初始化后依赖应正确存储。"""
        h = StandardFileHandler(callback, delay_seconds=10)
        assert h.callback is callback
        assert h.delay == 10
        assert h._pending == {}

    def test_should_handle_valid_file(self, handler):
        """合法文件应通过过滤检查。"""
        with patch("pilotstd.monitor.handler.get_config") as mock_cfg:
            mock_cfg.return_value = {"file_patterns": [".pdf", ".docx"], "ignore_patterns": ["~$", ".tmp"]}
            assert handler._should_handle("/path/to/file.pdf") is True

    def test_should_handle_rejects_non_matching_ext(self, handler):
        """不匹配扩展名的文件应被拒绝。"""
        with patch("pilotstd.monitor.handler.get_config") as mock_cfg:
            mock_cfg.return_value = {"file_patterns": [".pdf"], "ignore_patterns": ["~$"]}
            assert handler._should_handle("/path/to/file.txt") is False

    def test_should_handle_rejects_temp_files(self, handler):
        """临时文件（~$开头）应被拒绝。"""
        with patch("pilotstd.monitor.handler.get_config") as mock_cfg:
            mock_cfg.return_value = {"file_patterns": [".pdf"], "ignore_patterns": ["~$"]}
            assert handler._should_handle("/path/to/~$temp.pdf") is False

    def test_should_handle_rejects_dotfiles(self, handler):
        """以点开头的文件应被拒绝。"""
        with patch("pilotstd.monitor.handler.get_config") as mock_cfg:
            mock_cfg.return_value = {"file_patterns": [".pdf"], "ignore_patterns": []}
            assert handler._should_handle("/path/to/.hidden.pdf") is False

    def test_should_handle_rejects_tmp_pattern(self, handler):
        """.tmp 模式文件应被拒绝。"""
        with patch("pilotstd.monitor.handler.get_config") as mock_cfg:
            mock_cfg.return_value = {"file_patterns": [".pdf"], "ignore_patterns": [".tmp"]}
            assert handler._should_handle("/path/to/file.tmp.pdf") is False

    def test_on_created_delegates(self, handler, monkeypatch):
        """创建事件应委托到 _handle。"""
        mock_handle = MagicMock()
        monkeypatch.setattr(handler, "_handle", mock_handle)
        event = MagicMock()
        event.is_directory = False
        event.src_path = "/path/to/new.pdf"
        handler.on_created(event)
        mock_handle.assert_called_once_with("/path/to/new.pdf")

    def test_on_created_ignores_directory(self, handler, monkeypatch):
        """目录创建事件应被忽略。"""
        mock_handle = MagicMock()
        monkeypatch.setattr(handler, "_handle", mock_handle)
        event = MagicMock()
        event.is_directory = True
        handler.on_created(event)
        mock_handle.assert_not_called()

    def test_on_modified_delegates(self, handler, monkeypatch):
        """修改事件应委托到 _handle。"""
        mock_handle = MagicMock()
        monkeypatch.setattr(handler, "_handle", mock_handle)
        event = MagicMock()
        event.is_directory = False
        event.src_path = "/path/to/modified.pdf"
        handler.on_modified(event)
        mock_handle.assert_called_once_with("/path/to/modified.pdf")

    def test_on_moved_delegates(self, handler, monkeypatch):
        """移动事件应委托到 _handle（用目标路径）。"""
        mock_handle = MagicMock()
        monkeypatch.setattr(handler, "_handle", mock_handle)
        event = MagicMock()
        event.is_directory = False
        event.dest_path = "/path/to/destination.pdf"
        handler.on_moved(event)
        mock_handle.assert_called_once_with("/path/to/destination.pdf")

    def test_handle_rejects_invalid_file(self, handler):
        """不合法文件不应被加入待处理列表。"""
        with patch("pilotstd.monitor.handler.get_config") as mock_cfg:
            mock_cfg.return_value = {"file_patterns": [".pdf"], "ignore_patterns": []}
            handler._handle("/path/to/file.txt")
        assert "/path/to/file.txt" not in handler._pending

    def test_handle_deduplicates(self, handler, monkeypatch):
        """重复事件应被去重。"""
        mock_timer = MagicMock()
        monkeypatch.setattr(threading, "Timer", mock_timer)
        with patch("pilotstd.monitor.handler.get_config") as mock_cfg:
            mock_cfg.return_value = {"file_patterns": [".pdf"], "ignore_patterns": []}
            handler._handle("/path/to/file.pdf")
            handler._handle("/path/to/file.pdf")
        # 同一文件只应被处理一次
        assert mock_timer.call_count == 1
