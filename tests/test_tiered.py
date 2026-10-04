"""阶段 B3：Docker 侧分档节流（长阶段 60 秒/主题）+ 耗时埋点。

设计依据：02-framework-update.md §三（分档策略）与 §四 W3 行「分档策略需在两端一致」；
03-impl-design-D.md §1.2 B 行验收「长阶段 60 秒节流」；裁决「耗时落 notification_log.task_context」。
"""

from datetime import datetime, timedelta
from types import SimpleNamespace

from pilotstd.core.notification import tiered
from pilotstd.core.notification._dispatcher import _throttled, do_send
from pilotstd.core.notification.channel import NotificationMessage

NOW = 1_700_000_000.0


class TestTieredThrottle:
    def test_long_stage_same_topic_throttled_within_window(self):
        throttle = tiered.TieredThrottle()
        assert throttle.admit("scan", True, NOW) is True
        assert throttle.admit("scan", True, NOW + 59) is False
        assert throttle.admit("scan", True, NOW + 61) is True

    def test_different_topics_are_independent(self):
        throttle = tiered.TieredThrottle()
        assert throttle.admit("scan", True, NOW) is True
        assert throttle.admit("download", True, NOW + 1) is True

    def test_short_stage_never_throttled(self):
        throttle = tiered.TieredThrottle()
        for offset in (0, 1, 2, 3):
            assert throttle.admit("scan", False, NOW + offset) is True

    def test_empty_topic_never_throttled(self):
        throttle = tiered.TieredThrottle()
        assert throttle.admit("", True, NOW) is True
        assert throttle.admit("", True, NOW + 1) is True

    def test_window_default_matches_w3_constant(self):
        """两端一致：Docker 侧与 Windows 端 W3 共用同一常量值。"""
        from pilotstd.platform.notify import NotifyService

        assert NotifyService.LONG_STAGE_WINDOW == tiered.LONG_STAGE_THROTTLE_SECONDS
        assert tiered.LONG_STAGE_THROTTLE_SECONDS > 30.0  # 必须 > 桌面熔断窗口


class TestTierOf:
    def test_threshold_is_30_seconds(self):
        assert tiered.tier_of(29_999.0) == "short"
        assert tiered.tier_of(30_000.0) == "long"

    def test_upgrade_only_never_downgrade(self):
        """§3.5 #7：运行期只允许升档——声明为长即使实测很短也仍算长。"""
        assert tiered.tier_of(1_000.0, declared_long=True) == "long"

    def test_unknown_elapsed_defaults_short(self):
        assert tiered.tier_of(None) == "short"


class TestContext:
    def test_build_context_preserves_business_keys(self):
        context = tiered.build_context({"biz": 1, "other": "x"}, 45_000.0)
        assert context["biz"] == 1 and context["other"] == "x"
        assert context[tiered.CONTEXT_ELAPSED_KEY] == 45_000.0
        assert context[tiered.CONTEXT_TIER_KEY] == "long"

    def test_build_context_without_elapsed_only_sets_tier(self):
        context = tiered.build_context(None, None)
        assert tiered.CONTEXT_ELAPSED_KEY not in context
        assert context[tiered.CONTEXT_TIER_KEY] == "short"

    def test_parse_elapsed_round_trip(self):
        context = tiered.build_context({}, 12_345.6)
        assert tiered.parse_elapsed_ms(context) == 12_345.6
        assert tiered.parse_elapsed_ms({}) is None
        assert tiered.parse_elapsed_ms(None) is None


class TestSwitch:
    def test_enabled_by_default(self):
        assert tiered.is_enabled(SimpleNamespace(get=lambda k, d=None: d)) is True

    def test_rollback_values_disable(self):
        for raw in ("false", "0", "off", "v0", "no", False):
            config = SimpleNamespace(get=lambda k, d=None, _raw=raw: _raw)
            assert tiered.is_enabled(config) is False, raw

    def test_config_without_get_is_enabled(self):
        assert tiered.is_enabled(object()) is True


class _Host:
    """最小管理器替身：`_throttled` 只需要 `_cfg` 与节流器槽位。"""

    def __init__(self, enabled: bool = True):
        self._cfg = SimpleNamespace(get=lambda k, d=None: enabled)
        self._enabled = True
        self._local_sink = None


def _msg(target_id: str = "scan", elapsed_ms: float | None = 45_000.0) -> NotificationMessage:
    context = {"stage_elapsed_ms": elapsed_ms} if elapsed_ms is not None else {}
    return NotificationMessage(
        title="标题", body="正文", event_type="scan_complete", target_id=target_id, task_context=context
    )


class TestDispatcherIntegration:
    def test_long_stage_second_send_is_throttled(self):
        host = _Host()
        assert _throttled(host, _msg()) is False
        assert _throttled(host, _msg()) is True

    def test_short_stage_never_throttled(self):
        host = _Host()
        assert _throttled(host, _msg(elapsed_ms=1_000.0)) is False
        assert _throttled(host, _msg(elapsed_ms=1_000.0)) is False

    def test_switch_off_disables_throttling(self):
        host = _Host(enabled=False)
        assert _throttled(host, _msg()) is False
        assert _throttled(host, _msg()) is False

    def test_do_send_returns_early_when_throttled(self):
        """被节流时不得进入聚合/发送（用替身确认未调用静音判断）。"""
        calls: list[str] = []

        class _Host2(_Host):
            def _is_quiet_hours(self) -> bool:
                calls.append("quiet")
                return False

        host = _Host2()
        assert _throttled(host, _msg()) is False
        assert _throttled(host, _msg()) is True
        do_send(host, _msg(), ["telegram"])  # 第二次：应被节流提前返回
        assert calls == [], "被节流时不应进入后续流程"


class _Db:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self, sql, params=()):  # noqa: ARG002 - 契约签名
        return self._rows


class TestStageContextProbe:
    def _ops(self, rows):
        """以 manager 替身构造（`_db` 是只读属性，代理到 `self._mgr._db`）。"""
        from pilotstd.core.notification._manager_ops import NotificationOps

        return NotificationOps(SimpleNamespace(_db=_Db(rows)))

    def test_elapsed_computed_from_previous_row(self):
        prev = datetime.now() - timedelta(seconds=45)
        ops = self._ops([{"sent_at": prev.isoformat()}])
        context = ops._with_stage_context("task-1", {"biz": 1})
        assert context["biz"] == 1
        assert context[tiered.CONTEXT_TIER_KEY] == "long"
        assert context[tiered.CONTEXT_ELAPSED_KEY] >= 44_000.0

    def test_first_event_has_no_elapsed_key(self):
        ops = self._ops([])
        context = ops._with_stage_context("task-1", None)
        assert tiered.CONTEXT_ELAPSED_KEY not in context
        assert context[tiered.CONTEXT_TIER_KEY] == "short"

    def test_missing_task_id_skips_elapsed(self):
        ops = self._ops([{"sent_at": datetime.now().isoformat()}])
        context = ops._with_stage_context("", None)
        assert tiered.CONTEXT_ELAPSED_KEY not in context

    def test_probe_failure_does_not_break_logging(self):
        class _Bad:
            def fetchall(self, sql, params=()):  # noqa: ARG002 - 契约签名
                raise RuntimeError("db down")

        from pilotstd.core.notification._manager_ops import NotificationOps

        ops = NotificationOps(SimpleNamespace(_db=_Bad()))
        context = ops._with_stage_context("task-1", {"biz": 2})
        assert context["biz"] == 2  # 埋点失败不影响通知主流程
