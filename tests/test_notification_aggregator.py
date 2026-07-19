# tests/test_notification_aggregator.py
# 测试 NotificationAggregator 适配层：主题分组、聚合合并、暂停/恢复、新版转发

import time
import unittest
from unittest.mock import MagicMock, patch

from pilotstd.core.notification_aggregator import NotificationAggregator


class TestNotificationAggregator(unittest.TestCase):
    """单例聚合器适配层测试：验证对外 API 兼容 + 内部转发正确。"""

    def setUp(self) -> None:
        # 获取单例并重置内部状态
        self.agg = NotificationAggregator.__new__(NotificationAggregator)
        self.agg._init()
        # 劫持回调捕获输出
        self.calls: list[tuple[str, str, str]] = []
        self._capture = lambda t, b, level: self.calls.append((t, b, level))
        self.agg._on_show = self._capture
        # 禁用暂停
        self.agg._paused = False
        self.agg._paused_until = None
        self.agg._warning_errors.clear()

    def tearDown(self) -> None:
        self.agg._new.shutdown()
        self.agg._warning_errors.clear()

    def _flush_and_wait(self) -> None:
        """用 shutdown 刷新新版聚合器（取消 Timer→立即发送→等待回调）。"""
        self.agg._new.shutdown()
        time.sleep(0.05)

    # ── 主题提取（不变） ──

    def test_extract_topic_done_from_title(self) -> None:
        topic = NotificationAggregator._extract_topic("扫描完成", "")
        assert topic == "done"

    def test_extract_topic_error_from_title(self) -> None:
        topic = NotificationAggregator._extract_topic("下载失败", "")
        assert topic == "error"

    def test_extract_topic_scan_from_title(self) -> None:
        topic = NotificationAggregator._extract_topic("扫描文件", "")
        assert topic == "scan"

    def test_extract_topic_fallback(self) -> None:
        topic = NotificationAggregator._extract_topic("例行维护", "")
        assert topic == "_例行维护"

    # ── should_show 基础行为 ──

    def test_should_show_always_returns_false(self) -> None:
        result = self.agg.should_show("info", "测试标题", "测试内容")
        assert result is False

    # ── 聚合逻辑（新版 format_summary 输出） ──

    def test_single_item_passthrough(self) -> None:
        """单条通知直接透传，标题和级别不变。"""
        self.agg.should_show("info", "单条通知", "通知正文")
        self._flush_and_wait()
        assert len(self.calls) == 1
        assert self.calls[0][0] == "单条通知"
        assert self.calls[0][2] == "info"

    def test_multiple_same_topic_merges(self) -> None:
        """同主题多条通知合并为一条。"""
        self.agg.should_show("info", "下载GB 1.pdf", "略")
        self.agg.should_show("info", "下载GB 2.pdf", "略")
        self._flush_and_wait()
        assert len(self.calls) == 1
        _title, body, _level = self.calls[0]
        assert "2 条" in body

    def test_error_items_merge_with_worst_level(self) -> None:
        """多条 error 级别通知合并后取最严重级别。"""
        self.agg.should_show("error", "连接失败", "err1")
        self.agg.should_show("error", "连接失败", "err2")
        self._flush_and_wait()
        assert len(self.calls) == 1
        assert self.calls[0][2] == "error"

    def test_mixed_level_merges_to_worst(self) -> None:
        """混级通知合并后取最严重级别。"""
        self.agg.should_show("info", "扫描完成", "done1")
        self.agg.should_show("warning", "归档完成", "done2")
        self._flush_and_wait()
        assert len(self.calls) == 1
        assert self.calls[0][2] == "warning"

    def test_flush_empty_noop(self) -> None:
        """空缓冲 flush 不触发回调。"""
        self._flush_and_wait()
        assert len(self.calls) == 0

    # ── 暂停/恢复 ──

    def test_pause_state_default_false(self) -> None:
        state = self.agg.get_pause_state()
        assert state["is_paused"] is False
        assert state["remaining_seconds"] == 0

    @patch("pilotstd.core.notification_aggregator._COUNT_WINDOW", 99999)
    @patch("pilotstd.core.notification_aggregator._PAUSE_DURATION", 99999)
    def test_three_warnings_trigger_pause(self) -> None:
        """连续 3 条 warning/error 触发暂停。"""
        self.agg._warning_errors = [time.time(), time.time()]
        self.agg.should_show("error", "连接失败", "第3次错误")
        self._flush_and_wait()
        assert self.agg._paused is True
        assert self.calls
        assert "暂停" in self.calls[0][0]

    def test_paused_notifications_blocked(self) -> None:
        """暂停期间 should_show 不转发到新版聚合器。"""
        self.agg._paused = True
        self.agg._paused_until = time.time() + 300
        buf_before = sum(len(v) for v in self.agg._new._buffers.values())
        result = self.agg.should_show("info", "测试", "内容")
        assert result is False
        buf_after = sum(len(v) for v in self.agg._new._buffers.values())
        assert buf_after == buf_before

    def test_resume_clears_pause_state(self) -> None:
        self.agg._paused = True
        self.agg._paused_until = time.time() + 300
        self.agg.resume()
        assert self.agg._paused is False
        assert self.agg._paused_until is None

    def test_pause_auto_recover_on_expiry(self) -> None:
        """暂停到期后自动恢复，should_show 正常入队。"""
        self.agg._paused = True
        self.agg._paused_until = time.time() - 1
        self.agg.should_show("info", "恢复后通知", "内容")
        assert self.agg._paused is False
        assert sum(len(v) for v in self.agg._new._buffers.values()) == 1

    def test_get_pause_state_with_remaining(self) -> None:
        self.agg._paused = True
        self.agg._paused_until = time.time() + 60
        state = self.agg.get_pause_state()
        assert state["is_paused"] is True
        assert 0 <= state["remaining_seconds"] <= 60

    # ── 适配层转发 ──

    def test_should_show_forwards_to_new_aggregator(self) -> None:
        """should_show 正确调用了新版聚合器的 push 方法。"""
        self.agg._new.push = MagicMock()  # type: ignore[method-assign]
        self.agg.should_show("info", "扫描完成", "100 files", lambda t, b, _lv: None)
        self.agg._new.push.assert_called_once()
        kwargs = self.agg._new.push.call_args.kwargs
        assert kwargs["event_type"] == "desktop_toast"
        assert kwargs["target_id"] == "done"
        assert kwargs["status"] == "success"

    def test_error_level_maps_to_failure_status(self) -> None:
        """error 级别映射为 status='failure'。"""
        self.agg._new.push = MagicMock()  # type: ignore[method-assign]
        self.agg.should_show("error", "下载失败", "err", lambda t, b, _lv: None)
        kwargs = self.agg._new.push.call_args.kwargs
        assert kwargs["status"] == "failure"

    def test_shutdown_delegates_to_new_aggregator(self) -> None:
        """shutdown() 调用新版聚合器的 shutdown()。"""
        self.agg._new.shutdown = MagicMock()  # type: ignore[method-assign]
        self.agg.shutdown()
        self.agg._new.shutdown.assert_called_once()
