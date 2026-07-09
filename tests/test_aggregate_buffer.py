# tests/test_aggregate_buffer.py
# 测试 NotificationAggregator（服务端通知渠道聚合）：
# - 分组聚合 (event_type + target_id)
# - 双重触发（定时器 + 数量阈值）
# - format_summary 格式化
# - push() 便捷入口
# - shutdown 刷新残留

import time
import unittest
from unittest.mock import MagicMock

from pilotstd.core.notification.aggregate_buffer import NotificationAggregator
from pilotstd.core.notification.channel import NotificationMessage


class TestNotificationAggregator(unittest.TestCase):
    """服务端通知聚合器测试。"""

    def setUp(self) -> None:
        self.calls: list[tuple] = []
        self.sender = MagicMock(side_effect=lambda msg, ch: self.calls.append((msg, ch)))
        self.agg = NotificationAggregator(
            sender_func=self.sender,
            window_seconds=0.1,
            batch_size=20,
        )

    def tearDown(self) -> None:
        self.agg.shutdown()

    # ── 快速入队 5 条 → 只触发 1 次发送 ──

    def test_rapid_5_pushes_triggers_1_callback(self) -> None:
        """1 秒内连续 push 5 条同类型消息，窗口到期后只触发 1 次发送。"""
        for i in range(5):
            self.agg.push(
                event_type="archive_complete",
                title="归档完成",
                content=f"已归档目录 {i}",
                level="info",
            )
            time.sleep(0.01)  # 10ms 间隔，远小于窗口

        # 等待窗口到期（0.1s + buffer）
        time.sleep(0.3)
        self.agg.shutdown()

        self.assertEqual(len(self.calls), 1)
        merged_msg, channels = self.calls[0]
        self.assertEqual(merged_msg.aggregated_count, 5)
        self.assertIn("📦", merged_msg.body)
        self.assertIn("共 5 条", merged_msg.body)

    # ── bypass 事件直接发送不聚合 ──

    def test_bypass_events_send_immediately(self) -> None:
        """绕过列表中的事件直接回调，不入队。"""
        agg = NotificationAggregator(
            sender_func=self.sender,
            window_seconds=10.0,
            bypass_events={"worker_error"},
        )
        agg.push(event_type="worker_error", title="后台任务异常", content="worker 崩溃")
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.calls[0][0].event_type, "worker_error")
        agg.shutdown()

    # ── 数量阈值触发立即发送 ──

    def test_batch_size_triggers_immediate_flush(self) -> None:
        """达到 batch_size 时立即发送，不等定时器。"""
        agg = NotificationAggregator(
            sender_func=self.sender,
            window_seconds=999.0,  # 定时器很远
            batch_size=3,
        )
        for i in range(3):
            agg.push(event_type="test", title="测试", content=f"消息 {i}")
        # 第3条应触发立即发送
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.calls[0][0].aggregated_count, 3)
        agg.shutdown()

    # ── target_id 分组 ──

    def test_same_event_type_merged_after_shutdown(self) -> None:
        """同事件类型消息（即使不同 target_id）在 shutdown 时合并。"""
        for i in range(2):
            self.agg.push(
                event_type="archive_complete",
                title="归档完成",
                content=f"task_a 消息 {i}",
                target_id="task_a",
            )
        for i in range(3):
            self.agg.push(
                event_type="archive_complete",
                title="归档完成",
                content=f"task_b 消息 {i}",
                target_id="task_b",
            )
        self.agg.shutdown()
        # 按 event_type 分组，全部合并为一条
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.calls[0][0].aggregated_count, 5)

    # ── format_summary ──

    def test_format_summary_single_item(self) -> None:
        """单条消息保持原样。"""
        msg = NotificationMessage(title="测试", body="hello", event_type="test")
        entries = [(msg, [], time.monotonic())]
        result = self.agg.format_summary("test", entries)
        self.assertEqual(result, "hello")

    def test_format_summary_with_success_failure(self) -> None:
        """多条带 status 的消息生成成功/失败统计。"""
        now = time.monotonic()
        entries = [
            (NotificationMessage(title="任务", body="file_a.txt", status="success", event_type="test"), [], now),
            (NotificationMessage(title="任务", body="file_b.txt", status="success", event_type="test"), [], now + 0.1),
            (NotificationMessage(title="任务", body="file_c.txt", status="failure", event_type="test"), [], now + 0.2),
            (NotificationMessage(title="任务", body="file_d.txt", status="", event_type="test"), [], now + 0.3),
        ]
        result = self.agg.format_summary("test", entries)
        self.assertIn("✅ 成功：2 条", result)
        self.assertIn("❌ 失败：1 条", result)
        self.assertIn("file_c.txt", result)
        self.assertIn("📋 其他：1 条", result)

    def test_format_summary_worst_level(self) -> None:
        """聚合后级别取所有条目中最严重的。"""
        now = time.monotonic()
        entries = [
            (NotificationMessage(title="任务", body="ok", level="info", event_type="test"), [], now),
            (NotificationMessage(title="任务", body="warn", level="warning", event_type="test"), [], now + 0.1),
            (NotificationMessage(title="任务", body="err", level="error", event_type="test"), [], now + 0.2),
        ]
        # Trigger batch send immediately
        agg = NotificationAggregator(sender_func=self.sender, window_seconds=999.0, batch_size=3)
        for msg, ch, _ in entries:
            agg.enqueue(msg, ch)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.calls[0][0].level, "error")
        agg.shutdown()

    # ── shutdown 刷新残留 ──

    def test_shutdown_flushes_remaining(self) -> None:
        """关闭前未到期的缓冲消息在 shutdown 时被刷新。"""
        agg = NotificationAggregator(
            sender_func=self.sender,
            window_seconds=999.0,  # 很长，定时器不会触发
        )
        agg.push(event_type="test", title="测试", content="未到期的消息")
        # 不等待定时器，直接 shutdown
        agg.shutdown()
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.calls[0][0].body, "未到期的消息")

    # ── enqueue 返回 False（入队） vs True（bypass） ──

    def test_enqueue_returns_false_for_buffered(self) -> None:
        """普通事件入队返回 False。"""
        msg = NotificationMessage(title="测试", body="hello", event_type="test")
        result = self.agg.enqueue(msg, [])
        self.assertFalse(result)

    def test_enqueue_returns_true_for_bypass(self) -> None:
        """bypass 事件直接发送返回 True。"""
        agg = NotificationAggregator(
            sender_func=self.sender,
            bypass_events={"test"},
        )
        msg = NotificationMessage(title="测试", body="hello", event_type="test")
        result = agg.enqueue(msg, [])
        self.assertTrue(result)
        agg.shutdown()

    # ── push 便捷入口 ──

    def test_push_creates_message_and_enqueues(self) -> None:
        """push() 自动包装 NotificationMessage 并入队。"""
        self.agg.push(
            event_type="archive_complete",
            title="归档完成",
            content="已归档 5 个文件",
            level="info",
            status="success",
            elapsed_ms=150,
        )
        time.sleep(0.3)
        self.agg.shutdown()
        self.assertEqual(len(self.calls), 1)
        msg, _ = self.calls[0]
        self.assertEqual(msg.title, "归档完成")
        self.assertEqual(msg.aggregated_count, 1)
