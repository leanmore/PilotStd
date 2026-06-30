# tests/test_notification_aggregator.py
# 测试 NotificationAggregator 聚合逻辑、30秒窗口、主题分组、暂停/恢复

import time
import unittest
from unittest.mock import patch

from pilotstd.core.notification_aggregator import NotificationAggregator


class TestNotificationAggregator(unittest.TestCase):
    """单例聚合器功能测试：劫持回调验证输出内容。"""

    def setUp(self) -> None:
        # 获取单例并重置内部状态
        self.agg = NotificationAggregator.__new__(NotificationAggregator)
        self.agg._init()
        # 劫持回调捕获输出
        self.calls: list[tuple[str, str, str]] = []
        self._capture = lambda t, b, level: self.calls.append((t, b, level))
        self.agg._on_show = self._capture
        # 禁用自动暂停的配置读取
        self.agg._paused = False
        self.agg._paused_until = None
        self.agg._warning_errors.clear()

    def tearDown(self) -> None:
        # 清理定时器，避免后台线程干扰后续测试
        if self.agg._timer:
            self.agg._timer.cancel()
        self.agg._buffer.clear()
        self.agg._warning_errors.clear()

    # ── 主题提取 ──

    def test_extract_topic_done_from_title(self) -> None:
        """包含"完成"关键词的标题归类为 done。"""
        topic = NotificationAggregator._extract_topic("扫描完成", "")
        assert topic == "done"

    def test_extract_topic_error_from_title(self) -> None:
        """包含"失败"关键词的标题归类为 error。"""
        topic = NotificationAggregator._extract_topic("下载失败", "")
        assert topic == "error"

    def test_extract_topic_scan_from_title(self) -> None:
        """包含"扫描"关键词的标题归类为 scan。"""
        topic = NotificationAggregator._extract_topic("扫描文件", "")
        assert topic == "scan"

    def test_extract_topic_fallback(self) -> None:
        """无关键词匹配则回退为 _ + 标题前8字符。"""
        topic = NotificationAggregator._extract_topic("例行维护", "")
        assert topic == "_例行维护"

    # ── 聚合逻辑 ──

    def test_should_show_always_returns_false(self) -> None:
        """should_show 总是返回 False，真实显示由定时器回调触发。"""
        result = self.agg.should_show("info", "测试标题", "测试内容")
        assert result is False

    def test_flush_single_item_unchanged(self) -> None:
        """单条通知直接透传，标题和级别不变。"""
        self.agg.should_show("info", "单条通知", "通知正文")
        self.agg._on_show = self._capture  # should_show 会覆盖 _on_show，flush 前恢复
        self.agg._flush()
        assert len(self.calls) == 1
        assert self.calls[0] == ("单条通知", "通知正文", "info")

    def test_flush_multiple_same_topic_merges(self) -> None:
        """同主题多条通知合并后标题含数量。"""
        self.agg.should_show("info", "下载GB 1.pdf", "略")
        self.agg.should_show("info", "下载GB 2.pdf", "略")
        self.agg._on_show = self._capture  # should_show 会覆盖 _on_show，flush 前恢复
        self.agg._flush()
        assert len(self.calls) == 1
        title, body, level = self.calls[0]
        assert "2" in title
        assert "download" in title

    def test_flush_error_items_merge_with_correct_level(self) -> None:
        """多条 error 主题通知合并后级别为 warning。"""
        self.agg.should_show("error", "连接失败", "err1")
        self.agg.should_show("error", "连接失败", "err2")
        self.agg._on_show = self._capture  # should_show 会覆盖 _on_show，flush 前恢复
        self.agg._flush()
        assert len(self.calls) == 1
        assert self.calls[0][2] == "warning"

    def test_flush_done_items_merge_correct_level(self) -> None:
        """多条 done 主题通知合并后级别强制为 info。"""
        self.agg.should_show("info", "扫描完成", "done1")
        self.agg.should_show("warning", "归档完成", "done2")
        self.agg._on_show = self._capture  # should_show 会覆盖 _on_show，flush 前恢复
        self.agg._flush()
        assert len(self.calls) == 1
        assert self.calls[0][2] == "info"

    # ── 暂停/恢复 ──

    def test_pause_state_default_false(self) -> None:
        """初始暂停状态为 False。"""
        state = self.agg.get_pause_state()
        assert state["is_paused"] is False
        assert state["remaining_seconds"] == 0

    @patch("pilotstd.core.notification_aggregator._COUNT_WINDOW", 99999)
    @patch("pilotstd.core.notification_aggregator._PAUSE_DURATION", 99999)
    def test_three_warnings_trigger_pause(self) -> None:
        """连续 3 条 warning/error 触发 5 分钟暂停，仅一条暂停通知。"""
        # 先发 2 条 error 通知（模拟已有 2 次警告）
        self.agg._warning_errors = [time.time(), time.time()]
        # 第 3 条 error 通过 should_show 入缓冲
        self.agg.should_show("error", "连接失败", "第3次错误")
        self.agg._on_show = self._capture  # should_show 会覆盖 _on_show，flush 前恢复
        self.agg._timer = None
        self.agg._flush()
        # 此时 paused 应为 True
        assert self.agg._paused is True
        assert self.calls  # 应有一条暂停通知
        title = self.calls[0][0]
        assert "暂停" in title

    def test_paused_notifications_blocked(self) -> None:
        """暂停期间 should_show 返回 False 且不追加到 buffer。"""
        self.agg._paused = True
        self.agg._paused_until = time.time() + 300
        buf_before = len(self.agg._buffer)
        result = self.agg.should_show("info", "测试", "内容")
        assert result is False
        assert len(self.agg._buffer) == buf_before  # 未追加

    def test_resume_clears_pause_state(self) -> None:
        """手动恢复后暂停状态清零。"""
        self.agg._paused = True
        self.agg._paused_until = time.time() + 300
        self.agg.resume()
        assert self.agg._paused is False
        assert self.agg._paused_until is None
        state = self.agg.get_pause_state()
        assert state["is_paused"] is False

    def test_pause_auto_recover_on_expiry(self) -> None:
        """暂停到期后自动恢复，should_show 将通知送入 buffer。"""
        self.agg._paused = True
        self.agg._paused_until = time.time() - 1  # 已过期
        result = self.agg.should_show("info", "恢复后通知", "内容")
        assert result is False  # 仍返回 False，但已入缓冲
        assert len(self.agg._buffer) == 1
        assert self.agg._paused is False

    # ── 边界 ──

    def test_flush_empty_buffer_noop(self) -> None:
        """空缓冲 flush 不触发回调。"""
        self.agg._buffer.clear()
        self.agg._on_show = self._capture  # should_show 会覆盖 _on_show，flush 前恢复
        self.agg._flush()
        assert len(self.calls) == 0

    def test_get_pause_state_with_remaining(self) -> None:
        """暂停中返回正确的剩余秒数。"""
        self.agg._paused = True
        self.agg._paused_until = time.time() + 60
        state = self.agg.get_pause_state()
        assert state["is_paused"] is True
        assert 0 <= state["remaining_seconds"] <= 60
