# tests/test_delivery_health.py
"""通知投递健康度告警（P0）。

## 缺陷背景（生产实测，32 天窗口）

`notification_log` 实测 1,148 条中 **629 条发送失败（54.8%）**，其中 599 条是
Telegram 限流。而这一切**用户完全不可见**——通知系统自己坏了，只能靠人偶然发现。
最糟的一周（2026-09-14~09-20）每天失败 25~151 条，**持续 7 天无人知晓**，
而那正是"收藏集中下载失败、61 条被永久冻结"的窗口。

## 修复后的契约

1. **双触发**：连败（渠道彻底不通）**或**窗口失败率超阈（渠道在丢消息）；
2. **连败优先**：两者同时成立时只报连败，不发两条；
3. **冷启动保护**：样本数不足时不判失败率（避免刚启动就误报）；
4. **告警去重**：同一（渠道 + 原因）在冷却期内只报一次；
5. **不走环**：告警投递期间的结果**不计入健康度**（否则告警失败会触发新告警）；
6. **走旁路**：告警发给**除故障渠道外**的渠道（故障渠道很可能就是问题本身）；
7. **实时**：告警 `bypass_aggregation=True`，不等聚合窗口。
"""

from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pilotstd.core.config.defaults import FACTORY_DEFAULTS  # noqa: E402
from pilotstd.core.notification.delivery_health import (  # noqa: E402
    REASON_CONSECUTIVE,
    REASON_RATE,
    NotificationDeliveryHealth,
)


class _FakeClock:
    """假时钟：避免测试真的睡 1 小时。"""

    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += seconds


def _health(**kw) -> NotificationDeliveryHealth:
    base = dict(
        rate_threshold=0.5,
        min_samples=10,
        consecutive_threshold=5,
        window_seconds=3600.0,
        alert_cooldown_seconds=3600.0,
    )
    base.update(kw)
    h = NotificationDeliveryHealth(**base)
    h.set_clock(_FakeClock())
    return h


class TestRecordAndSnapshot(unittest.TestCase):
    def test_counts_success_and_failure(self):
        h = _health()
        for ok in (True, True, False):
            h.record("telegram", ok)
        self.assertEqual(h.snapshot("telegram"), (3, 1))
        self.assertEqual(h.consecutive("telegram"), 1)

    def test_consecutive_resets_on_success(self):
        h = _health()
        for _ in range(4):
            h.record("telegram", False)
        self.assertEqual(h.consecutive("telegram"), 4)
        h.record("telegram", True)
        self.assertEqual(h.consecutive("telegram"), 0)

    def test_unknown_channel_is_zero(self):
        h = _health()
        self.assertEqual(h.snapshot("nope"), (0, 0))
        self.assertEqual(h.consecutive("nope"), 0)
        self.assertIsNone(h.evaluate("nope"))

    def test_blank_channel_ignored(self):
        h = _health()
        h.record("", False)
        self.assertEqual(h.snapshot(""), (0, 0))

    def test_channels_are_independent(self):
        h = _health()
        for _ in range(6):
            h.record("telegram", False)
        h.record("wechat", True)
        self.assertEqual(h.snapshot("telegram"), (6, 6))
        self.assertEqual(h.snapshot("wechat"), (1, 0))

    def test_window_rolls_off_old_records(self):
        """超窗记录不计入统计（否则"失败率"永不下降）。"""
        h = _health(window_seconds=100.0)
        clock: _FakeClock = h._now  # type: ignore[assignment]
        for _ in range(20):
            h.record("telegram", False)
        self.assertEqual(h.snapshot("telegram"), (20, 20))
        clock.advance(101)
        self.assertEqual(h.snapshot("telegram"), (0, 0))


class TestThresholds(unittest.TestCase):
    def test_no_alert_below_consecutive_threshold(self):
        h = _health(consecutive_threshold=5)
        for _ in range(4):
            h.record("telegram", False)
        self.assertIsNone(h.evaluate("telegram"))

    def test_consecutive_threshold_triggers(self):
        """★ 连败达阈值 → 告警（渠道彻底不通的先兆）。"""
        h = _health(consecutive_threshold=5, min_samples=1000)
        for _ in range(5):
            h.record("telegram", False)
        verdict = h.evaluate("telegram")
        self.assertIsNotNone(verdict)
        assert verdict is not None
        reason, samples, failures = verdict
        self.assertEqual(reason, REASON_CONSECUTIVE)
        self.assertEqual(samples, 5)
        self.assertEqual(failures, 5)

    def test_rate_threshold_triggers_when_samples_enough(self):
        """★ 失败率超阈 → 告警（渠道在丢消息，如限流）。"""
        h = _health(consecutive_threshold=999, rate_threshold=0.5, min_samples=10)
        for _ in range(6):
            h.record("telegram", True)
        for _ in range(6):
            h.record("telegram", False)
        verdict = h.evaluate("telegram")
        self.assertIsNotNone(verdict)
        assert verdict is not None
        reason, samples, failures = verdict
        self.assertEqual(reason, REASON_RATE)
        self.assertEqual(samples, 12)
        self.assertEqual(failures, 6)

    def test_rate_needs_min_samples(self):
        """★ 冷启动保护：样本不足时不判失败率（避免刚启动就误报）。"""
        h = _health(consecutive_threshold=999, rate_threshold=0.5, min_samples=10)
        for _ in range(5):
            h.record("telegram", False)
        self.assertIsNone(h.evaluate("telegram"), "样本 5 < 下限 10，不应判失败率")

    def test_consecutive_takes_precedence_over_rate(self):
        """★ 两者同时成立 → 只报连败（不发两条）。"""
        h = _health(consecutive_threshold=5, rate_threshold=0.5, min_samples=10)
        for _ in range(20):
            h.record("telegram", False)
        verdict = h.evaluate("telegram")
        assert verdict is not None
        self.assertEqual(verdict[0], REASON_CONSECUTIVE)

    def test_below_rate_threshold_no_alert(self):
        h = _health(consecutive_threshold=999, rate_threshold=0.5, min_samples=10)
        for _ in range(8):
            h.record("telegram", True)
        for _ in range(2):
            h.record("telegram", False)
        self.assertIsNone(h.evaluate("telegram"), "失败率 20% < 50%，不应告警")


class TestCooldown(unittest.TestCase):
    def test_same_reason_not_repeated_within_cooldown(self):
        """★ 告警去重：冷却期内同一（渠道+原因）只报一次（避免风暴）。"""
        h = _health(consecutive_threshold=5, alert_cooldown_seconds=3600)
        clock: _FakeClock = h._now  # type: ignore[assignment]
        for _ in range(5):
            h.record("telegram", False)
        self.assertIsNotNone(h.evaluate("telegram"))
        for _ in range(5):
            h.record("telegram", False)
        self.assertIsNone(h.evaluate("telegram"), "冷却期内不应重复告警")
        clock.advance(3601)
        self.assertIsNotNone(h.evaluate("telegram"), "冷却期过后应可再次告警")

    def test_different_reasons_have_independent_cooldown(self):
        h = _health(
            consecutive_threshold=5, rate_threshold=0.5, min_samples=10,
            alert_cooldown_seconds=3600,
        )
        for _ in range(5):
            h.record("telegram", False)
        first = h.evaluate("telegram")
        assert first is not None
        self.assertEqual(first[0], REASON_CONSECUTIVE)
        # 让连败清零但失败率仍高 → 应可报 rate（原因不同，冷却独立）
        for _ in range(20):
            h.record("telegram", True)
        for _ in range(20):
            h.record("telegram", False)
        h.record("telegram", True)
        second = h.evaluate("telegram")
        self.assertIsNotNone(second, "不同原因应各有独立冷却")
        assert second is not None
        self.assertEqual(second[0], REASON_RATE)

    def test_channels_have_independent_cooldown(self):
        h = _health(consecutive_threshold=5, alert_cooldown_seconds=3600)
        for _ in range(5):
            h.record("telegram", False)
        for _ in range(5):
            h.record("wechat", False)
        self.assertIsNotNone(h.evaluate("telegram"))
        self.assertIsNotNone(h.evaluate("wechat"), "渠道之间冷却应互不影响")


class TestConfigDefaults(unittest.TestCase):
    """配置齐全性：缺键会让功能静默失效（回退值）或不可调。"""

    def test_all_keys_present(self):
        for key in (
            "notification.delivery_health_enabled",
            "notification.delivery_health_consecutive_threshold",
            "notification.delivery_health_rate_threshold",
            "notification.delivery_health_min_samples",
            "notification.delivery_health_window_seconds",
            "notification.delivery_health_alert_cooldown_seconds",
        ):
            self.assertIn(key, FACTORY_DEFAULTS, f"缺配置键 {key}")

    def test_sane_defaults(self):
        self.assertIs(FACTORY_DEFAULTS["notification.delivery_health_enabled"], True)
        self.assertGreaterEqual(
            FACTORY_DEFAULTS["notification.delivery_health_consecutive_threshold"], 2
        )
        self.assertTrue(0 < FACTORY_DEFAULTS["notification.delivery_health_rate_threshold"] <= 1)
        self.assertGreaterEqual(FACTORY_DEFAULTS["notification.delivery_health_min_samples"], 2)
        self.assertGreater(
            FACTORY_DEFAULTS["notification.delivery_health_window_seconds"], 0
        )
        self.assertGreater(
            FACTORY_DEFAULTS["notification.delivery_health_alert_cooldown_seconds"], 0
        )

    def test_default_channel_rule_present(self):
        """★ 缺此项会让告警"注册了但发不出去"。"""
        key = "notification.rules.notification_delivery_failed"
        self.assertIn(key, FACTORY_DEFAULTS)
        self.assertTrue(FACTORY_DEFAULTS[key])

    def test_event_registered(self):
        from pilotstd.core.notification.events import ALL_EVENT_KEYS

        self.assertIn("notification_delivery_failed", ALL_EVENT_KEYS)

    def test_topic_registered_for_trilingual_grouping(self):
        """★ 缺此项会让同一告警在三语下分裂成不同聚合分组。"""
        from pilotstd.core.notification_aggregator import _TOPIC_BY_EVENT

        self.assertIn("notification_delivery_failed", _TOPIC_BY_EVENT)


class TestManagerIntegration(unittest.TestCase):
    """接线契约：`_record_delivery` 的判定与告警投递。"""

    def _mgr(self, channels=("telegram", "wechat")):
        from pilotstd.core.notification.manager import NotificationManager

        mgr = NotificationManager.__new__(NotificationManager)
        mgr._channels = {c: MagicMock() for c in channels}
        mgr.delivery_health = _health(consecutive_threshold=3)
        mgr._sending_delivery_alert = False
        mgr._enabled = True
        # send_event 打桩：既记录调用，又真实走到 _send_now（模拟真实链路），
        # 以便验证"告警投递失败不会再触发新告警"的重入保护。
        mgr._send_now = MagicMock()
        # 注意：lambda 每次调用时读取 mgr._send_now，故测试里替换 _send_now 仍会生效
        mgr.send_event = MagicMock(side_effect=lambda *a, **kw: mgr._send_now(*a, **kw))
        return mgr

    def test_success_records_only(self):
        mgr = self._mgr()
        mgr._record_delivery("telegram", True)
        self.assertEqual(mgr.delivery_health.snapshot("telegram"), (1, 0))
        self.assertFalse(mgr._send_now.called)

    def test_below_threshold_does_not_alert(self):
        mgr = self._mgr()
        for _ in range(2):
            mgr._record_delivery("telegram", False)
        self.assertFalse(mgr._send_now.called, "未达阈值不应告警")

    def test_alert_on_threshold(self):
        """★ 达阈值 → 发告警（且**经过 send_event**，保证走统一出口）。"""
        mgr = self._mgr()
        for _ in range(3):
            mgr._record_delivery("telegram", False)
        self.assertTrue(mgr.send_event.called)
        self.assertEqual(mgr.send_event.call_args[0][0], "notification_delivery_failed")

    def test_alert_bypasses_aggregation(self):
        """★ 告警必须实时发（`bypass_aggregation=True`），不能等聚合窗口。"""
        mgr = self._mgr()
        for _ in range(3):
            mgr._record_delivery("telegram", False)
        _args, kwargs = mgr.send_event.call_args
        self.assertIs(kwargs.get("bypass_aggregation"), True)

    def test_alert_goes_to_other_channels(self):
        """★ 告警走**旁路**：发给除故障渠道外的渠道（故障渠道很可能就是问题本身）。"""
        mgr = self._mgr(channels=("telegram", "wechat"))
        for _ in range(3):
            mgr._record_delivery("telegram", False)
        _args, kwargs = mgr.send_event.call_args
        targets = kwargs.get("target_channels")
        self.assertIsNotNone(targets, "必须显式指定目标渠道（策略表无法表达『除某渠道外』）")
        self.assertIn("wechat", targets)
        self.assertNotIn("telegram", targets)

    def test_alert_falls_back_to_failing_channel_when_alone(self):
        """★ 无旁路时仍投向故障渠道——好过完全静默（会在通知日志留下痕迹）。"""
        mgr = self._mgr(channels=("telegram",))
        for _ in range(3):
            mgr._record_delivery("telegram", False)
        _args, kwargs = mgr.send_event.call_args
        self.assertEqual(kwargs.get("target_channels"), ["telegram"])

    def test_disabled_health_does_nothing(self):
        mgr = self._mgr()
        mgr.delivery_health = None
        for _ in range(10):
            mgr._record_delivery("telegram", False)
        self.assertFalse(mgr._send_now.called)

    def test_alert_payload_shape(self):
        mgr = self._mgr()
        for _ in range(3):
            mgr._record_delivery("telegram", False)
        args, _kwargs = mgr.send_event.call_args
        payload = args[1]
        self.assertEqual(payload["channel"], "telegram")
        self.assertEqual(payload["reason"], REASON_CONSECUTIVE)
        self.assertEqual(payload["consecutive"], 3)
        # 渲染出的正文须含渠道名、且不得出现未翻译键
        from pilotstd.core.notification._builders_batch import (
            _build_notification_delivery_failed_message,
        )

        msg = _build_notification_delivery_failed_message(payload)
        text = "\n".join(getattr(b, "text", "") for b in msg.blocks)
        self.assertIn("telegram", text)
        self.assertNotIn("notification.", text)

    def test_no_recursion_when_alert_also_fails(self):
        """★ 不回环：告警自身投递失败**不得**再次触发告警。

        构造真实的恶性循环场景：告警投递时**唯一渠道也失败**，
        且失败记录**立刻再次达标**（阈值=1）。若无重入保护，链条会无限展开。

        - 有保护：告警**恰好进入 1 次**（投递期间的结果被忽略）；
        - 无保护：告警投递 → 记录失败 → 再次达标 → 再次进入告警 → …… 无限递归
          （本用例会因 `enter` 远超 1 而 FAIL，或直接 RecursionError）。

        判别力：去掉 `_sending_delivery_alert` 判断 → 本用例 FAIL。
        """
        mgr = self._mgr(channels=("telegram",))
        # 阈值=1 且冷却=0：让"重入即可再次告警"，从而暴露缺少保护
        mgr.delivery_health = _health(consecutive_threshold=1, alert_cooldown_seconds=0.0)

        enter = {"n": 0}

        def _send_now(*_a, **_kw):
            # 模拟"告警自己也发不出去"：记录同一渠道失败（阈值=1 → 立刻再次达标）
            mgr._record_delivery("telegram", False)

        mgr._send_now.side_effect = _send_now

        original = mgr._send_delivery_alert

        def _counting(*a, **kw):
            enter["n"] += 1
            if enter["n"] > 5:  # 兜底：避免无保护时真的把栈打爆
                return None
            return original(*a, **kw)

        mgr._send_delivery_alert = _counting

        mgr._record_delivery("telegram", False)

        self.assertEqual(
            enter["n"], 1,
            f"告警只应进入 1 次，实际 {enter['n']} 次（重入保护失效 → 递归）",
        )

    def test_reentrancy_flag_is_set_during_alert(self):
        """★ 直接验证重入标志的语义：告警投递**期间**为真，结束后复位。"""
        mgr = self._mgr(channels=("telegram", "wechat"))
        seen: list = []

        def _send_now(*_a, **_kw):
            seen.append(mgr._sending_delivery_alert)

        mgr._send_now.side_effect = _send_now
        for _ in range(3):
            mgr._record_delivery("telegram", False)

        self.assertEqual(seen, [True], "告警投递期间标志必须为真")
        self.assertFalse(mgr._sending_delivery_alert, "投递结束后必须复位")

    def test_send_event_signature_accepts_target_override(self):
        """★ 契约：`send_event` 必须支持 target_channels 覆盖（旁路投递的正当能力）。"""
        import inspect

        from pilotstd.core.notification.manager import NotificationManager

        params = inspect.signature(NotificationManager.send_event).parameters
        self.assertIn("target_channels", params)
        self.assertIsNone(params["target_channels"].default)


if __name__ == "__main__":
    unittest.main()
