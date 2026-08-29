# tests/test_aggregate_buffer.py
# 测试 NotificationAggregator（服务端通知渠道聚合）：
# - 分组聚合 (event_type + target_id)
# - 双重触发（定时器 + 数量阈值）
# - _build_summary 标准化摘要（基于 blocks 渲染，单条全文/多条统计）
# - push() 便捷入口
# - shutdown 刷新残留
# - L5 契约防线：blocks 保留、body 回退、空消息兜底、Builder 契约校验

import time
import unittest
from unittest.mock import MagicMock

from pilotstd.core.notification.aggregate_buffer import NotificationAggregator
from pilotstd.core.notification.blocks import KeyValueBlock, TextBlock
from pilotstd.core.notification.channel import NotificationMessage
from pilotstd.core.notification.manager import NotificationManager
from pilotstd.core.notification.renderer import TelegramRenderer


def _make_msg(
    title: str = "测试",
    body: str = "",
    blocks=None,
    level: str = "info",
    status: str = "",
    event_type: str = "test",
    elapsed_ms: int = 0,
) -> NotificationMessage:
    """构造测试消息的便捷函数。"""
    return NotificationMessage(
        title=title,
        body=body,
        blocks=blocks or [],
        level=level,
        status=status,
        event_type=event_type,
        elapsed_ms=elapsed_ms,
    )


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
        self.assertIn("（5 条）", merged_msg.body)

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

    # ── _build_summary 摘要 ──

    def test_build_summary_single_item_with_body(self) -> None:
        """单条消息（无 blocks、有 body）保持原样。"""
        msg = _make_msg(title="测试", body="hello")
        entries: list = [(msg, [], time.monotonic())]
        result = self.agg._build_summary(entries)
        self.assertEqual(result, "hello")

    def test_build_summary_single_item_renders_blocks(self) -> None:
        """单条消息（有 blocks）基于 blocks 渲染生成全文摘要。"""
        msg = _make_msg(title="归档完成", blocks=[TextBlock(text="已归档 3 个目录")])
        entries: list = [(msg, [], time.monotonic())]
        result = self.agg._build_summary(entries)
        self.assertIn("归档完成", result)
        self.assertIn("已归档 3 个目录", result)

    def test_build_summary_multiple_items_statistics(self) -> None:
        """多条消息生成统计头 + 每条首行。"""
        now = time.monotonic()
        entries: list = [
            (_make_msg(title="任务A", body="file_a.txt", status="success"), [], now),
            (_make_msg(title="任务B", body="file_b.txt", status="failure"), [], now + 0.1),
        ]
        result = self.agg._build_summary(entries)
        self.assertIn("📦 聚合通知（2 条）", result)
        self.assertIn("file_a.txt", result)
        self.assertIn("file_b.txt", result)

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
        msg = _make_msg(title="测试", body="hello")
        result = self.agg.enqueue(msg, [])
        self.assertFalse(result)

    def test_enqueue_returns_true_for_bypass(self) -> None:
        """bypass 事件直接发送返回 True。"""
        agg = NotificationAggregator(
            sender_func=self.sender,
            bypass_events={"test"},
        )
        msg = _make_msg(title="测试", body="hello")
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

    # ── flush 手动刷新 ──

    def test_flush_sends_buffered_entries(self):
        """flush() 立即发送缓冲中的条目。"""
        agg = NotificationAggregator(
            sender_func=self.sender,
            window_seconds=999.0,
        )
        agg.push(event_type="test", title="T", content="c")
        agg.flush("test")
        self.assertEqual(len(self.calls), 1)
        agg.shutdown()

    def test_flush_empty_buffer_noop(self):
        """flush() 空缓冲不崩溃。"""
        self.agg.flush("no_such_event")
        self.assertEqual(len(self.calls), 0)

    def test_flush_all_multiple_groups(self):
        """flush_all() 刷新所有分组。"""
        agg = NotificationAggregator(
            sender_func=self.sender,
            window_seconds=999.0,
        )
        agg.push(event_type="a", title="A", content="1")
        agg.push(event_type="b", title="B", content="2")
        agg.flush_all()
        self.assertEqual(len(self.calls), 2)
        agg.shutdown()

    # ── 注册格式化器 ──

    def test_registered_formatter_used_in_send_merged(self):
        """注册的自定义格式化器在 _send_merged 中被调用。"""
        agg = NotificationAggregator(
            sender_func=self.sender,
            window_seconds=999.0,
            batch_size=2,
        )
        agg.register_formatter("test", lambda _et, _entries, count: f"CUSTOM:{count}")
        agg.push(event_type="test", title="T", content="c1")
        agg.push(event_type="test", title="T", content="c2")
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.calls[0][0].body, "CUSTOM:2")
        agg.shutdown()

    # ── _on_timer 窗口满路径 ──

    def test_on_timer_full_window_flushes(self):
        """_on_timer 在超过 MAX_WINDOW_SECONDS 时强制发送。"""
        agg = NotificationAggregator(
            sender_func=self.sender,
            window_seconds=0.1,
        )
        agg.push(event_type="test", title="T", content="c")
        # 手动把窗口开始时间调到远超 MAX_WINDOW_SECONDS
        agg._window_start["test"] = time.monotonic() - 301
        agg._on_timer("test")
        self.assertEqual(len(self.calls), 1)
        agg.shutdown()


# ═══════════════════════════════════════════════════════════════════════════
# Step 2c（v1.1）：聚合合并行为验收（全量事件接入聚合器后的核心路径）
# ═══════════════════════════════════════════════════════════════════════════


class TestStep2AggregateMerge(unittest.TestCase):
    """Step 2c 阻塞项：同类型合并 / 异类型隔离 / 窗口超时直出。"""

    def setUp(self) -> None:
        self.calls: list[tuple] = []
        self.sender = MagicMock(side_effect=lambda msg, ch: self.calls.append((msg, ch)))
        # 短窗口（语义同生产 5 秒窗口，测试加速）
        self.agg = NotificationAggregator(
            sender_func=self.sender,
            window_seconds=0.1,
            batch_size=50,
        )

    def tearDown(self) -> None:
        self.agg.shutdown()

    def test_same_type_within_window_merges(self) -> None:
        """窗口内 6 条同类型事件 → 1 条聚合消息：前 5 条明细 + "… 等 6 条"。"""
        for i in range(6):
            self.agg.push(
                event_type="scan_complete",
                title="扫描完成",
                content=f"已扫描 {i} 个文件",
                level="info",
            )
            time.sleep(0.01)  # 10ms 间隔，远小于窗口

        time.sleep(0.3)  # 等待窗口到期
        self.assertEqual(len(self.calls), 1)
        merged_msg, _ = self.calls[0]
        self.assertEqual(merged_msg.aggregated_count, 6)
        # 明细截断：5 条明细 + "等 6 条" 尾注，不逐条罗列全部 6 条
        self.assertEqual(merged_msg.body.count("• "), 5)
        self.assertIn("等 6 条", merged_msg.body)

    def test_different_types_not_merged(self) -> None:
        """同窗口内不同类型事件 → 分别输出，不跨类型合并。"""
        self.agg.push(event_type="scan_complete", title="扫描完成", content="文件 1")
        self.agg.push(event_type="archive_complete", title="归档完成", content="目录 1")
        self.agg.flush_all()

        self.assertEqual(len(self.calls), 2)
        event_types = sorted(c[0].event_type for c in self.calls)
        self.assertEqual(event_types, ["archive_complete", "scan_complete"])
        self.assertEqual(self.calls[0][0].aggregated_count, 1)
        self.assertEqual(self.calls[1][0].aggregated_count, 1)

    def test_window_timeout_flush(self) -> None:
        """单条事件超过窗口无后续 → 定时器到期自动 flush 直出。"""
        self.agg.push(event_type="task_execution_failed", title="任务失败", content="worker 崩溃")

        time.sleep(0.3)  # 超过 0.1s 窗口
        self.assertEqual(len(self.calls), 1)
        msg, _ = self.calls[0]
        self.assertEqual(msg.event_type, "task_execution_failed")
        self.assertEqual(msg.aggregated_count, 1)  # 单条直出


# ═══════════════════════════════════════════════════════════════════════
# L5 契约防线测试：聚合器正统重构验收场景
# ═══════════════════════════════════════════════════════════════════════


class TestAggregateContract(unittest.TestCase):
    """L5 验收：blocks 保留 / body 回退 / 空消息兜底 / Builder 契约校验。"""

    def setUp(self) -> None:
        self.calls: list[tuple] = []
        self.sender = MagicMock(side_effect=lambda msg, ch: self.calls.append((msg, ch)))
        # 短窗口：快速触发发送
        self.agg = NotificationAggregator(
            sender_func=self.sender,
            window_seconds=999.0,  # 不用定时器，直接 flush 控制
            batch_size=100,
        )

    def tearDown(self) -> None:
        self.agg.shutdown()

    def _send_now(self, entries: list) -> None:
        """直接调用 _send_merged 触发发送（绕过定时器）。"""
        self.agg._send_merged(entries[0][0].event_type, entries)

    # ── 场景 1：单条聚合（blocks 非空）→ 与直发渲染一致，blocks 未丢失 ──

    def test_single_item_blocks_preserved_and_renders_identical(self) -> None:
        """单条聚合：merged.blocks 保留第一条的 blocks，Telegram 渲染与直发一致。"""
        blocks = [TextBlock(text="标准号：GB/T 123-2024"), KeyValueBlock(key="状态", value="现行")]
        msg = _make_msg(title="标准状态变更", blocks=blocks, event_type="standard_status_changed")
        entries = [(msg, ["telegram"], time.monotonic())]

        self._send_now(entries)
        self.assertEqual(len(self.calls), 1)
        merged, channels = self.calls[0]

        # blocks 未丢失：与原始 blocks 相等（结构化相等）
        self.assertEqual(merged.blocks, msg.blocks)
        self.assertGreater(len(merged.blocks), 0)
        # 渲染结果与直发一致（同一 Telegram 渲染器）
        renderer = TelegramRenderer()
        self.assertEqual(renderer.render(merged), renderer.render(msg))

    # ── 场景 2：单条聚合（blocks 空，body 非空）→ 回退 body ──

    def test_single_item_body_fallback_when_no_blocks(self) -> None:
        """单条聚合：blocks 为空时摘要回退 body 文本。"""
        msg = _make_msg(title="公告拉取完成", body="新增公告: 12\n来源: 手动", event_type="announcement_fetch_complete")
        entries = [(msg, ["telegram"], time.monotonic())]

        self._send_now(entries)
        self.assertEqual(len(self.calls), 1)
        merged, _ = self.calls[0]

        self.assertEqual(merged.blocks, [])
        self.assertIn("新增公告: 12", merged.body)
        self.assertIn("来源: 手动", merged.body)

    # ── 场景 3：多条聚合（blocks 非空）→ blocks 保留 + 摘要含每条首行 ──

    def test_multiple_items_blocks_preserved_and_summary_has_each_first_line(self) -> None:
        """多条聚合：merged.blocks 保留首条骨架，摘要 body 包含每条渲染首行。"""
        now = time.monotonic()
        entries = [
            (
                _make_msg(
                    title="公告检查完成",
                    blocks=[KeyValueBlock(key="公告总数", value="12"), KeyValueBlock(key="国标", value="10")],
                    event_type="announcement_check_complete",
                ),
                ["telegram"],
                now,
            ),
            (
                _make_msg(
                    title="公告检查完成",
                    blocks=[KeyValueBlock(key="公告总数", value="8"), KeyValueBlock(key="国标", value="7")],
                    event_type="announcement_check_complete",
                ),
                ["telegram"],
                now + 0.1,
            ),
        ]

        self._send_now(entries)
        self.assertEqual(len(self.calls), 1)
        merged, _ = self.calls[0]

        # blocks 保留首条骨架
        self.assertEqual(merged.blocks, entries[0][0].blocks)
        self.assertGreater(len(merged.blocks), 0)
        self.assertEqual(merged.aggregated_count, 2)
        # 摘要包含统计头与每条渲染首行（渲染顺序：title 在前 → 首行即标题）
        self.assertIn("📦 聚合通知（2 条）", merged.body)
        self.assertEqual(merged.body.count("公告检查完成"), 2)  # 两条各自的首行

    # ── 场景 4：多条聚合（全空消息）→ 渲染兜底为占位文案，永不返回 "" ──

    def test_empty_messages_fallback_to_placeholder(self) -> None:
        """全空消息（无 blocks/body/title）聚合后渲染兜底为占位文案。"""
        now = time.monotonic()
        entries = [
            (_make_msg(title="", body="", blocks=[], event_type="broken_builder"), ["telegram"], now),
            (_make_msg(title="", body="", blocks=[], event_type="broken_builder"), ["telegram"], now + 0.1),
        ]

        self._send_now(entries)
        self.assertEqual(len(self.calls), 1)
        merged, _ = self.calls[0]

        # 摘要 body 非空：占位文案兜底
        self.assertTrue(merged.body.strip())
        self.assertIn("(通知内容为空)", merged.body)
        # 渲染结果也非空
        renderer = TelegramRenderer()
        self.assertNotEqual(renderer.render(merged), "")

    # ── 场景 5：Builder 契约校验 ──

    def test_validate_message_raises_for_empty_message(self) -> None:
        """全空 Message（无 blocks/body/title）触发 _validate_message 抛 ValueError。"""
        mgr = MagicMock(spec=NotificationManager)
        mgr._validate_message = NotificationManager._validate_message.__get__(mgr)  # 绑定实例方法
        empty_msg = _make_msg(title="", body="", blocks=[], event_type="broken_builder")

        with self.assertRaises(ValueError) as ctx:
            mgr._validate_message(empty_msg, "broken_builder")
        self.assertIn("empty Message", str(ctx.exception))
        self.assertIn("broken_builder", str(ctx.exception))

    def test_validate_message_passes_for_non_empty_message(self) -> None:
        """任一字段（blocks/body/title）非空即通过校验。"""
        mgr = MagicMock(spec=NotificationManager)
        mgr._validate_message = NotificationManager._validate_message.__get__(mgr)

        # 仅 title
        self.assertIsNone(mgr._validate_message(_make_msg(title="标题", body="", blocks=[]), "t"))
        # 仅 body
        self.assertIsNone(mgr._validate_message(_make_msg(title="", body="正文", blocks=[]), "b"))
        # 仅 blocks
        self.assertIsNone(mgr._validate_message(_make_msg(title="", body="", blocks=[TextBlock(text="x")]), "k"))
        # 纯空白 body 视为空
        with self.assertRaises(ValueError):
            mgr._validate_message(_make_msg(title="", body="   ", blocks=[]), "w")

    def test_send_event_skips_empty_message_with_error_log(self) -> None:
        """send_event 遇到空消息：不中断、跳过发送、记录 Error 日志。"""
        mgr = MagicMock(spec=NotificationManager)
        mgr._validate_message = NotificationManager._validate_message.__get__(mgr)
        mgr._user_id = 1
        mgr._enabled = True
        mgr._policy = MagicMock()
        mgr._policy.get_channels_for_event.return_value = ["telegram"]
        mgr._build_message = MagicMock(
            return_value=_make_msg(title="", body="", blocks=[], event_type="broken_builder")
        )
        mgr._do_send = MagicMock()
        mgr._broadcast_to_ws = MagicMock()

        with unittest.mock.patch("pilotstd.core.notification.manager.logger") as mock_logger:
            NotificationManager.send_event(mgr, "broken_builder", {})
            mock_logger.error.assert_called_once()
            # 校验失败 → 不进入发送
            mgr._do_send.assert_not_called()
