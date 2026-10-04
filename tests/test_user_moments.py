"""阶段 C：用户时刻清单（第二 SSOT）与「用户时刻 × 事件」双向闭包。

设计依据：[00-framework.md](../../docs/plans/notification-system-design/00-framework.md) §1.1（36 时刻）
与 §七 裁决 1/2/3；[02-framework-update.md](../../docs/plans/notification-system-design/02-framework-update.md) §一 #2
（"用户时刻清单做第二 SSOT：进代码、41 事件必须映射、**有断言校验**"）。
"""

from pilotstd.core.notification.event_spec import EVENT_SPECS
from pilotstd.core.notification.user_moments import (
    DECLARED_MOMENTS_WITHOUT_EVENT,
    SECONDARY_EVENTS,
    USER_MOMENTS,
    all_attributable_events,
    events_claimed_by_moments,
    events_without_moment,
    moments_without_event,
    unknown_event_keys,
)

# Windows 专属事件不计入 Docker 侧闭包（00-framework §1.2："41 − Windows 专属 worker_error"）
WINDOWS_ONLY_EVENTS = {"worker_error"}


def _docker_event_keys() -> set[str]:
    return {spec.key for spec in EVENT_SPECS} - WINDOWS_ONLY_EVENTS


class TestMomentList:
    def test_moment_count_is_36(self):
        """Docker 侧用户时刻 = 36（00-framework §1.2）。"""
        assert len(USER_MOMENTS) == 36

    def test_moment_numbers_unique_and_positive(self):
        numbers = [m.no for m in USER_MOMENTS]
        assert len(numbers) == len(set(numbers))
        assert all(n > 0 for n in numbers)

    def test_every_moment_has_user_language_name(self):
        for moment in USER_MOMENTS:
            assert moment.name.strip(), moment.no
            # 优先级闭集取自 §1.1 的**实际取值**：文档中 #15 写作「可关」（疑为「可选」笔误），
            # 这里按原文接受并显式列出——不静默改写文档数据，差异留给文档侧修正。
            assert moment.priority in ("必发", "应发", "可选", "可关"), (moment.no, moment.priority)


class TestBidirectionalClosure:
    """双向闭包：时刻 → 事件、事件 → 时刻，两个方向都必须闭合（例外需显式声明）。"""

    def test_moments_without_event_match_declared(self):
        assert moments_without_event() == list(DECLARED_MOMENTS_WITHOUT_EVENT)

    def test_no_event_is_unattributable(self):
        """事件到时刻方向：不存在既非承接、也非次要、也非声明冗余的事件。"""
        assert events_without_moment(_docker_event_keys()) == []

    def test_secondary_events_are_declared_and_real(self):
        """次要事件（重复 5 + 粒度错配 7 + 同刻补充 1）必须真实存在且被显式声明。"""
        keys = {spec.key for spec in EVENT_SPECS}
        assert len(SECONDARY_EVENTS) == 13
        assert set(SECONDARY_EVENTS) <= keys
        assert all_attributable_events() <= keys

    def test_no_unknown_event_keys_in_moment_table(self):
        """时刻表引用的每个键都必须真实存在（防拼写/下线残留）。"""
        assert unknown_event_keys(_docker_event_keys()) == []

    def test_claimed_events_are_subset_of_specs(self):
        assert events_claimed_by_moments() <= {spec.key for spec in EVENT_SPECS}


class TestSubscriptionHandling:
    """阶段 E：多余事件默认不订阅、重复事件订阅层只留其一（裁决 1/2 均采 (b)）。"""

    def test_redundant_events_not_subscribed_by_default(self):
        by_key = {spec.key: spec for spec in EVENT_SPECS}
        for key in ("standard_first_registered", "normalize_complete", "download_started"):
            assert not list(by_key[key].default_channels), f"{key} 不应默认订阅"

    def test_events_kept_in_specs(self):
        """"保留事件"：默认不订阅 ≠ 下线，事件仍在 SSOT 中（e2e 契约与三语文案保留）。"""
        keys = {spec.key for spec in EVENT_SPECS}
        for key in ("standard_first_registered", "normalize_complete", "download_started"):
            assert key in keys

    def test_query_empty_not_subscribed_by_default(self):
        """未出现在 §1.1「承接事件」列的重复事件：取消默认订阅（同刻只留其一）。"""
        by_key = {spec.key: spec for spec in EVENT_SPECS}
        assert not list(by_key["query_empty"].default_channels)

    def test_defaults_derive_from_specs(self):
        """默认订阅落点由 spec 派生（`defaults.py` 从 EVENT_SPECS 生成），非第二份清单。"""
        import os

        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(root, "pilotstd/core/config/defaults.py"), encoding="utf-8") as fh:
            src = fh.read()
        assert "notification.rules." in src and "EVENT_SPECS" in src
