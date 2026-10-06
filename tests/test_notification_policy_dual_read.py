"""阶段 4 · P6 · 4a 测试：`notification_policy` 的 `event_classes` 列与**双读**路径。

用户点名的关键路径（施工提醒 ①）：**必须显式覆盖"新字段为空 ⇒ 回退旧字段"**——
这条路径是第 1 层回滚开关（`NOTIFY_REDESIGN_STAGE=3`）的技术前提；若不测，回滚就只停留在文档描述。

覆盖：
1. `event_classes` 为空 ⇒ **回退 `events`**（旧行为原样：41 事件逐条匹配）；
2. `event_classes` 非空 ⇒ **只用类别层**（裁定 4 甲"新字段优先"）：即使 `events` 也含该事件，
   只要类别不匹配就**不订阅**（证明不是"并集"）；
3. `events` 为空且 `event_classes` 非空 ⇒ 类别层独立生效；
4. 坏 JSON / 非列表 / 非字符串元素 ⇒ 回退 `[]` 且不抛（防御式）；
5. `get_policies()` 两层原样返回；`save_policy()` 两层**互不覆盖**（传 None 不动该层）。
"""

from __future__ import annotations

from typing import Any

import pytest

from pilotstd.core.notification._policy import NotificationPolicyHelper, _loads_str_list, _notify_event_of


class _FakeDB:
    """极简内存替身：只实现 fetchall/fetchone/execute 三个被用到的接口。"""

    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows
        self.executed: list[tuple[str, tuple]] = []

    def fetchall(self, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        return [dict(r) for r in self.rows]

    def fetchone(self, sql: str, params: tuple = ()) -> dict[str, Any] | None:
        return None

    def execute(self, sql: str, params: tuple = ()) -> None:
        self.executed.append((sql, params))


class _FakeCfg:
    def get(self, key: str) -> Any:
        return None


def _row(**over: Any) -> dict[str, Any]:
    base = {
        "channel": "telegram",
        "events": "[]",
        "event_classes": "[]",
        "enabled": 1,
        "id": 1,
        "updated_at": "2026-10-05 10:00:00",
    }
    base.update(over)
    return base


@pytest.fixture()
def helper_factory():
    def _make(rows: list[dict[str, Any]]) -> tuple[NotificationPolicyHelper, _FakeDB]:
        db = _FakeDB(rows)
        return NotificationPolicyHelper(db, _FakeCfg()), db

    return _make


# ── ① 回退路径（用户点名的关键路径）─────────────────────────────────────────


def test_empty_event_classes_falls_back_to_events(helper_factory) -> None:
    """`event_classes` 为空 ⇒ 回退旧字段：`events` 命中即订阅（旧行为原样可用）。"""
    helper, _ = helper_factory([_row(events='["scan_complete"]', event_classes="[]")])
    assert helper.get_channels_for_event(1, "scan_complete") == ["telegram"]
    assert helper.get_channels_for_event(1, "download_complete") == []


def test_legacy_row_without_column_key_still_falls_back(helper_factory) -> None:
    """行里**没有** `event_classes` 键（未跑 v68 的库/替身）⇒ 也按"未设置类别"回退，不抛。"""
    row = _row(events='["scan_complete"]')
    row.pop("event_classes")
    helper, _ = helper_factory([row])
    assert helper.get_channels_for_event(1, "scan_complete") == ["telegram"]


# ── ② 新字段优先（非并集）───────────────────────────────────────────────────


def test_non_empty_event_classes_takes_priority_over_events(helper_factory) -> None:
    """`event_classes` 非空 ⇒ **只用类别层**：旧字段即使含该事件也不订阅（证明非并集）。"""
    # download_complete 属 task_result 类；类别层只订 task_failure ⇒ 不订阅
    helper, _ = helper_factory(
        [_row(events='["download_complete"]', event_classes='["task_failure"]')]
    )
    assert helper.get_channels_for_event(1, "download_complete") == []
    # 反向：类别层订 task_result ⇒ 订阅
    helper2, _ = helper_factory(
        [_row(events="[]", event_classes='["task_result"]')]
    )
    assert helper2.get_channels_for_event(1, "download_complete") == ["telegram"]


def test_class_layer_works_with_empty_events(helper_factory) -> None:
    """旧字段为空、类别层非空 ⇒ 类别层独立生效（高级层可留空）。"""
    helper, _ = helper_factory([_row(events="[]", event_classes='["batch_summary"]')])
    # archive_complete 属 batch_summary 类 ⇒ 命中类别层
    assert helper.get_channels_for_event(1, "archive_complete") == ["telegram"]


# ── ③ 防御式解析 ────────────────────────────────────────────────────────────


def test_loads_str_list_is_defensive() -> None:
    """坏输入一律回退 `[]`（空/None/非 JSON/非列表/含非字符串元素）。"""
    assert _loads_str_list("") == []
    assert _loads_str_list(None) == []
    assert _loads_str_list(123) == []
    assert _loads_str_list("{半截") == []
    assert _loads_str_list('{"a": 1}') == []
    assert _loads_str_list('["a", 1, null, "b"]') == ["a", "b"]


def test_helper_functions_are_defensive_for_unknown_event() -> None:
    """未知事件 ⇒ 类别为空串（不抛），且不会误命中类别层。"""
    assert _notify_event_of("完全不存在的业务事件") == ""
    assert _notify_event_of("scan_complete") != ""


def test_bad_json_row_does_not_break_whole_query(helper_factory) -> None:
    """单行坏 JSON 不让整表查询失效（仍返回可用的渠道）。"""
    helper, _ = helper_factory(
        [
            _row(channel="telegram", events="{坏", event_classes="[]"),
            _row(channel="wechat", events='["scan_complete"]', event_classes="[]"),
        ]
    )
    assert helper.get_channels_for_event(1, "scan_complete") == ["wechat"]


# ── ④ 读写两层接口 ──────────────────────────────────────────────────────────


def test_get_policies_returns_both_layers(helper_factory) -> None:
    """`get_policies()` 同时返回 `events` 与 `event_classes`（前端双层要用）。"""
    helper, _ = helper_factory(
        [_row(events='["scan_complete"]', event_classes='["batch_summary"]')]
    )
    policies = helper.get_policies(1)
    assert len(policies) == 1
    assert policies[0]["events"] == ["scan_complete"]
    assert policies[0]["event_classes"] == ["batch_summary"]


def test_save_policy_layers_do_not_overwrite_each_other(helper_factory) -> None:
    """`save_policy` 两层互不覆盖：只传 `event_classes` 时不得写 `events`。"""
    helper, db = helper_factory([])
    helper.save_policy(1, "telegram", None, None, event_classes=["task_result"])
    sqls = [sql for sql, _ in db.executed]
    assert any("INSERT" in sql and "event_classes" in sql for sql in sqls)
    # 插入语句必须同时给出两层的值（缺一层会让另一层被默认值覆盖）
    insert_params = [p for sql, p in db.executed if "INSERT" in sql][0]
    assert len(insert_params) == 5
    assert insert_params[3] == "[]"  # events 未传 ⇒ 空数组
    assert insert_params[4] == '["task_result"]'
