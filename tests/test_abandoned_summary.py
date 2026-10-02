# tests/test_abandoned_summary.py
"""收藏「已放弃」告终汇总（P0 修复）。

## 背景

`abandoned` 是**终态**：调度只捡 `pending`/`failed`（`favorite_chain_processor.py`），
故系统**永远不会再自动重试**。而原先该状态被并进 `batch_download_complete` 的
`failed` 计数里，用户看不出"哪些已彻底放弃、需要人工介入"。

生产实测（见 `docs/reference/diagnosis-favorite-download-failures.md`）：
105 条收藏中 **99 条 abandoned**，其中 61 条因会话层缺陷被永久冻结
（`last_attempt` 全为 2026-09-20），而用户直到自己去收藏页才发现。

## 修复后的契约

1. **告终汇总独立成事件** `favorite_abandoned_summary`（不再被并进 failed 计数）；
2. 载荷含：`total`（放弃总数）、`reasons`（原因分类 → 条数）、
   `retryable`（其中重试有效的条数）、`details`（示例明细）；
3. **仅在 `abandoned` 非空时发送**——无放弃则不额外产生噪声；
4. 原因分类需区分「重试有效」（临时性）与「重试无效」（永久性），
   因为两者的用户处置方式完全相反。
"""

from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pilotstd.core.config.defaults import FACTORY_DEFAULTS  # noqa: E402
from pilotstd.core.notification.blocks import ListBlock, TextBlock  # noqa: E402
from pilotstd.core.notification.events import ALL_EVENT_KEYS  # noqa: E402
from pilotstd.i18n import set_language  # noqa: E402
from pilotstd.services.favorite_chain_processor import (  # noqa: E402
    _classify_abandon_reason,
    _notify_abandoned_summary,
)


class TestClassifyAbandonReason(unittest.TestCase):
    """原因分类与「重试是否有效」判定（基于生产实测的 error_message 取值）。

    分类返回**类别 key**（由构建器翻译成文案）——与
    `_format_utils.translate_error_message` 同一约定：分类层不写死中文。
    """

    def test_copyright_is_permanent(self):
        """版权受限 → 永久，重试无效（与其它类别处置相反）。"""
        from pilotstd.download.engine import ADOPTED_SKIP_MESSAGE

        label, retryable = _classify_abandon_reason(f"{ADOPTED_SKIP_MESSAGE}: GB/T 7584.1-2026")
        self.assertEqual(label, "copyright")
        self.assertFalse(retryable, "版权受限必须判为「重试无效」")

    def test_session_defect_is_retryable(self):
        """会话层缺陷（已修复）→ 重试有效。"""
        label, retryable = _classify_abandon_reason("'super' object has no attribute 'request'")
        self.assertEqual(label, "session_defect")
        self.assertTrue(retryable)

    def test_old_link_impl_is_retryable(self):
        label, retryable = _classify_abandon_reason("无法获取下载链接: GB/T 47914-2026")
        self.assertEqual(label, "legacy_link")
        self.assertTrue(retryable)

    def test_db_race_is_retryable(self):
        label, retryable = _classify_abandon_reason("数据库操作失败")
        self.assertEqual(label, "db_race")
        self.assertTrue(retryable)

    def test_archive_timeout_is_retryable(self):
        label, retryable = _classify_abandon_reason("归档超时：文件未被扫描器处理")
        self.assertEqual(label, "archive_timeout")
        self.assertTrue(retryable)

    def test_network_timeout_is_retryable(self):
        label, retryable = _classify_abandon_reason("Telegram 发送异常: The read operation timed out")
        self.assertEqual(label, "network")
        self.assertTrue(retryable)

    def test_unknown_falls_back_to_other(self):
        """未知原因保守判为「可重试」（宁可建议用户重试，也不要误判为永久）。"""
        label, retryable = _classify_abandon_reason("某个未见过的新错误")
        self.assertEqual(label, "other")
        self.assertTrue(retryable)

    def test_empty_error_does_not_crash(self):
        label, retryable = _classify_abandon_reason("")
        self.assertEqual(label, "other")
        self.assertTrue(retryable)

    def test_all_labels_are_machine_keys_not_chinese(self):
        """★ 类别必须是**机器 key**（不含中文），文案由构建器翻译。

        判别力：把分类改回返回中文标签 → 本用例 FAIL。
        """

        samples = [
            "",
            "某错误",
            "'super' object has no attribute 'request'",
            "无法获取下载链接: X",
            "数据库操作失败",
            "归档超时：x",
            "采标标准，版权受限，自动跳过",
            "Telegram 发送异常: timed out",
        ]
        for s in samples:
            label, _ = _classify_abandon_reason(s)
            self.assertNotRegex(label, r"[\u4e00-\u9fff]", f"{s!r} → 类别含中文：{label!r}")
            self.assertRegex(label, r"^[a-z_]+$", f"{s!r} → 类别不是机器 key：{label!r}")


class TestNotifyAbandonedSummary(unittest.TestCase):
    """告终汇总的发送行为。"""

    def _run(self, abandoned: list[str]) -> MagicMock:
        mgr = MagicMock()
        with patch("pilotstd.manager.facade.StandardManager") as sm:
            sm.return_value.notification_mgr = mgr
            _notify_abandoned_summary(abandoned)
        return mgr

    def test_not_sent_when_no_abandoned(self):
        """★ 无放弃 → **不发**（避免又多一条日常噪声）。"""
        mgr = self._run([])
        self.assertFalse(mgr.send_event.called, "无放弃时不应发送告终汇总")

    def test_sent_once_with_aggregated_payload(self):
        """★ 有放弃 → 发 1 条，载荷含总数/原因分类/可重试数/示例。"""
        mgr = self._run(
            [
                "'super' object has no attribute 'request'",
                "'super' object has no attribute 'request'",
                "无法获取下载链接: GB/T 1-2020",
                "采标标准，版权受限，自动跳过: GB/T 2-2020",
            ]
        )
        self.assertTrue(mgr.send_event.called)
        self.assertEqual(mgr.send_event.call_count, 1, "多条放弃必须合并为 1 条通知")
        args, kwargs = mgr.send_event.call_args
        self.assertEqual(args[0], "favorite_abandoned_summary")
        payload = args[1]
        self.assertEqual(payload["total"], 4)
        self.assertEqual(sum(payload["reasons"].values()), 4, "原因分类计数之和应等于总数")
        self.assertEqual(payload["retryable"], 3, "3 条临时性 + 1 条版权受限")
        self.assertLessEqual(len(payload["details"]), 5)

    def test_reasons_are_classified_not_raw(self):
        """原因必须是**分类标签**，不是原始错误串（否则汇总不可读）。"""
        mgr = self._run(["'super' object has no attribute 'request'"] * 3)
        payload = mgr.send_event.call_args[0][1]
        for label in payload["reasons"]:
            self.assertNotIn("super", label, f"原因未分类：{label!r}")

    def test_send_failure_does_not_raise(self):
        """★ 通知失败不得影响链路（静默记日志）。"""
        mgr = MagicMock()
        mgr.send_event.side_effect = RuntimeError("boom")
        with patch("pilotstd.manager.facade.StandardManager") as sm:
            sm.return_value.notification_mgr = mgr
            _notify_abandoned_summary(["某错误"])  # 不应抛异常

    def test_details_capped_at_five(self):
        mgr = self._run([f"错误{i}" for i in range(20)])
        payload = mgr.send_event.call_args[0][1]
        self.assertEqual(payload["total"], 20)
        self.assertLessEqual(len(payload["details"]), 5)


class TestBuilder(unittest.TestCase):
    """`_build_favorite_abandoned_summary_message` 的渲染与 i18n。"""

    def _build(self, **kw):
        from pilotstd.core.notification._builders_batch import (
            _build_favorite_abandoned_summary_message as f,
        )

        base = {"total": 5, "reasons": {"会话层缺陷（已修复）": 3, "版权受限（采标标准）": 2},
                "retryable": 3, "details": ["a", "b"]}
        base.update(kw)
        return f(base)

    def test_basic_shape(self):
        msg = self._build()
        self.assertEqual(msg.event_type, "favorite_abandoned_summary")
        self.assertEqual(msg.level, "warning", "放弃是需要处理的事，级别不应是 info")
        self.assertTrue(any(isinstance(b, TextBlock) for b in msg.blocks))
        self.assertTrue(any(isinstance(b, ListBlock) for b in msg.blocks))

    def test_title_zh(self):
        set_language("zh_CN")
        msg = self._build()
        self.assertEqual(msg.title, "收藏已放弃（不会再自动重试）")

    def test_title_en(self):
        set_language("en")
        try:
            msg = self._build()
            self.assertEqual(msg.title, "Favorites abandoned (no further retries)")
        finally:
            set_language("zh_CN")

    def test_renders_without_missing_keys(self):
        """★ 三语下渲染都不得出现未翻译的键名（缺键会 fail-loud 回显键）。"""
        from pilotstd.core.notification.renderer import MarkdownRenderer

        for loc in ("zh_CN", "en", "zh_TW"):
            set_language(loc)
            try:
                out = MarkdownRenderer().render(self._build())
                self.assertNotIn("notification.download", out, f"{loc}: 渲染出现未翻译键")
            finally:
                set_language("zh_CN")

    def test_advice_switches_on_retryable(self):
        """★ 建议随「是否有可重试项」切换（这是本事件的核心价值）。"""
        from pilotstd.core.notification.renderer import MarkdownRenderer

        set_language("zh_CN")
        with_retry = MarkdownRenderer().render(self._build(retryable=3))
        without = MarkdownRenderer().render(self._build(retryable=0, reasons={"版权受限（采标标准）": 5}))
        self.assertNotEqual(with_retry, without)
        self.assertIn("重新收藏", with_retry)
        self.assertIn("人工", without)

    def test_telegram_escapes_separator(self):
        """回归：新事件用 ListBlock，Telegram 的分隔符必须已转义（P0-② 的修复覆盖到本事件）。"""
        from pilotstd.core.notification.renderer import TelegramRenderer

        set_language("zh_CN")
        out = TelegramRenderer().render(self._build())
        for line in out.splitlines():
            if line.startswith("•"):
                self.assertNotIn(" | ", line, f"Telegram 输出含未转义分隔符：{line!r}")

    def test_zero_total_does_not_crash(self):
        msg = self._build(total=0, reasons={}, details=[])
        self.assertTrue(msg.title)


class TestRegistration(unittest.TestCase):
    """注册齐全性（缺任一项则该事件『注册了但发不出去』）。"""

    def test_event_registered(self):
        self.assertIn("favorite_abandoned_summary", ALL_EVENT_KEYS)

    def test_default_channel_rule_present(self):
        """★ 缺此项会让事件"注册了但发不出去"（策略表为空时找不到渠道）。"""
        self.assertIn(
            "notification.rules.favorite_abandoned_summary",
            FACTORY_DEFAULTS,
            "新事件必须登记默认渠道规则",
        )
        self.assertTrue(FACTORY_DEFAULTS["notification.rules.favorite_abandoned_summary"])

    def test_builder_registered_in_manager(self):
        from pilotstd.core.notification.manager import _build_favorite_abandoned_summary_message  # noqa: F401

    def test_i18n_keys_present_in_all_three_locales(self):
        import json
        from pathlib import Path

        root = Path(__file__).resolve().parent.parent
        prefix = "notification.download.favorite_abandoned_summary"
        for loc in ("zh_CN", "en", "zh_TW"):
            d = json.loads((root / "pilotstd" / "i18n" / f"{loc}.json").read_text(encoding="utf-8"))
            keys = [k for k in d if k.startswith(prefix)]
            self.assertGreaterEqual(len(keys), 8, f"{loc}: 文案键缺失（{len(keys)} 个）")
