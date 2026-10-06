"""阶段 4 · P6 · 4d：**类别层契约一致性**（门禁级保护，防"层清单与映射漂移"）。

为什么需要它：4b 把"通知层级结构签名"（类别清单 + 事件→类别映射）放进了渠道元数据负载，
并让它进入 `spec_hash`。**若两边（前端拿到的负载 / 后端映射表）出现漂移**，会出现：
前端按旧类别勾选、后端按新类别判定 ⇒ "订阅了却不生效"或"没订阅却收到"，且**不会报错**。
本文件把这条契约钉死（三处同源 + 每类都有来源 + 哈希对层结构敏感）。

> 与既有门禁的分工：G-045（`audit_notification_coverage.py`）校验事件级四维度；
> 本文件校验**层级结构**这一新维度（4d 的第一个增量；脚本侧维度扩展另行排期）。
"""

from __future__ import annotations

import collections
import json

from pilotstd.core.notification.channel_spec import spec_hash, spec_payload
from pilotstd.core.notification.mapping import EVENT_MAPPINGS, NOTIFY_EVENTS


def test_payload_layers_match_mapping_exactly() -> None:
    """三处同源：前端负载的类别清单与映射表**同序同集**，事件→类别映射**逐项相等**。"""
    payload = spec_payload()
    assert payload["notify_events"] == list(NOTIFY_EVENTS), "类别清单必须与 mapping.NOTIFY_EVENTS 同序同集"
    expected_map = {key: entry.notify_event for key, entry in sorted(EVENT_MAPPINGS.items())}
    assert payload["event_class_map"] == expected_map, "事件→类别映射必须与 EVENT_MAPPINGS 完全一致"


def test_every_class_has_at_least_one_event_except_manual_test() -> None:
    """每类至少有一个事件承接；`manual_test` 例外（设计如此：仅测试端点用，无业务事件）。"""
    counts = collections.Counter(entry.notify_event for entry in EVENT_MAPPINGS.values())
    for cls in NOTIFY_EVENTS:
        if cls == "manual_test":
            assert counts.get(cls, 0) == 0, "manual_test 不得承接业务事件（设计约束）"
        else:
            assert counts.get(cls, 0) >= 1, f"类别 {cls} 没有任何事件承接（类别层会永远收不到通知）"


def test_map_values_subset_of_classes() -> None:
    """映射值必须落在类别清单内（错值会让前端类别层勾选失效）。"""
    assert set(EVENT_MAPPINGS[k].notify_event for k in EVENT_MAPPINGS) <= set(NOTIFY_EVENTS)


def test_spec_hash_is_sensitive_to_layer_structure() -> None:
    """`spec_hash` 对**层级结构**敏感：增删一个类别或改一个映射 ⇒ 哈希必变。

    这是 4b"扩 spec_hash"裁定的守门断言：哈希若不随层结构变化，前端内容级缓存就不会失效，
    新层将永远不被初始化（前端看不到类别层）。
    """
    payload = spec_payload()
    base = spec_hash(payload)

    fewer = json.loads(json.dumps(payload))
    fewer["notify_events"] = fewer["notify_events"][:-1]
    assert spec_hash(fewer) != base, "删掉一个类别后哈希必须变化"

    remapped = json.loads(json.dumps(payload))
    first_key = next(iter(remapped["event_class_map"]))
    remapped["event_class_map"][first_key] = "manual_test"
    assert spec_hash(remapped) != base, "改一个事件→类别映射后哈希必须变化"
