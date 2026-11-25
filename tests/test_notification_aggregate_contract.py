"""通知聚合/日志/模板口径横切回归（D7/D8/D9 批次 9）。

证据背景（`docs/plans/2026-11-25-p1-notify-refresh.md` §4-D7/§4-D8/§4-D9）：

- **D7-1** `_send_merged()` 把「类别名」写进 `event_type`（日常桶键 `2␟daily␟u0` ⇒ 落库
  `event_type="daily"`，生产实证 `daily` 92 / `batch_summary` 1499 条），真实事件名丢失；
- **D7-2** 多条聚合摘要取 `render(msg).split("\\n")[0]`，未跳过级别前缀行 ⇒ 摘要首行退化为
  `⚠️ 警告`（生产实证 `notification_log` id=4619）；
- **D7-3** 日志接口 `_business_level(event_type)` 拿**真实事件名**与 `security_alert`/
  `task_failure` 这两个**类别名**比较 ⇒ 非聚合行恒 `info`；
- **D8** `normalize_failed` 正文写"2 条失败"但明细块只有 1 条（口径不一致）；
- **D9** `_links.attach_web_actions()` 的 `open_logs` 分支依赖 `message.failed_items`，但全库
  无构建器设置该字段 ⇒ 死路径，且 `notification_log.failed_items` 列恒空（失败明细端点失效）。
  本批**修复**（不删除）：把 payload 的 `failed_items` 在构建出口搬到消息字段，聚合时按条目合并。
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock

from pilotstd.core.notification._builders_task_results import (
    _build_normalize_failed_message,
)
from pilotstd.core.notification._links import attach_web_actions, with_failed_items
from pilotstd.core.notification.aggregate_buffer import NotificationAggregator
from pilotstd.core.notification.channel import NotificationMessage
from pilotstd.core.notification.manager import NotificationManager
from pilotstd.core.notification.renderer_base import level_prefix

BASE = "https://std.example.com"


class _Cfg:
    def __init__(self, value: str | None = BASE) -> None:
        self._v: dict[str, str] = {} if value is None else {"notification.web_base_url": value}

    def get(self, key: str, default=None):
        return self._v.get(key, default)


def _failed_item(number: str = "GB/T 1-2020") -> dict[str, str]:
    return {
        "standard_number": number,
        "standard_name": "甲",
        "error_type": "unknown",
        "error_message": "缺失",
    }


# ── D7-1：聚合消息保留真实 event_type ───────────────────────────────────────


def test_merged_message_keeps_real_event_type() -> None:
    """日常桶（`daily`）聚合后 `event_type` 必须是真实事件名，而不是类别名。"""
    callbacks: list[NotificationMessage] = []
    agg = NotificationAggregator(sender_func=lambda m, _ch: callbacks.append(m), window_seconds=999.0)
    msg = NotificationMessage(
        title="收藏成功", body="x", event_type="favorite_created", notify_event="user_activity"
    )
    agg.enqueue(msg, [])
    agg.flush_all()
    assert callbacks, "聚合后必须回调发送"
    assert callbacks[0].event_type == "favorite_created", (
        f"聚合把真实 event_type 改成了类别名: {callbacks[0].event_type!r}"
    )


# ── D7-2：多条摘要首行跳过级别前缀 ──────────────────────────────────────────


def test_multi_summary_first_line_skips_level_prefix() -> None:
    """多条聚合摘要的明细行取**内容首行**，不得退化为 `⚠️ 警告`。"""
    agg = NotificationAggregator(sender_func=MagicMock(), window_seconds=999.0)
    now = time.monotonic()
    entries = [
        (NotificationMessage(title="任务A", body="file_a.txt", level="warning"), [], now),
        (NotificationMessage(title="任务B", body="file_b.txt", level="warning"), [], now + 0.1),
    ]
    summary = agg._build_summary(entries)
    prefix = level_prefix("warning")
    assert prefix and prefix not in summary, f"摘要首行退化成了级别前缀: {summary!r}"
    assert "file_a.txt" in summary and "file_b.txt" in summary


# ── D7-3：日志接口 level 使用真实事件/类别口径 ──────────────────────────────


def test_log_business_level_uses_notify_event_or_declared_level() -> None:
    """非聚合行的 `event_type` 是真实事件名 ⇒ level 不能恒为 info。"""
    from docker.api.notification_logs import _business_level

    # 类别名映射（旧行 event_type 就是类别名时仍兼容）
    assert _business_level("security_alert") == "warning"
    assert _business_level("task_failure") == "error"
    # 新行：真实事件名 + notify_event 类别名
    assert _business_level("security_login_failed", "security_alert") == "warning"
    assert _business_level("download_failed", "task_failure") == "error"
    # 事件声明里级别唯一时用**真实级别**（比类别映射更准）
    assert _business_level("validity_standard_failed", "anomaly_alert") == "error"
    # 普通事件仍为 info
    assert _business_level("scan_complete", "task_result") == "info"


# ── D8：normalize_failed「失败条数」与明细口径一致 ─────────────────────────


def test_normalize_failed_body_count_matches_failed_items() -> None:
    """正文说"N 条失败"就必须与明细块条数一致（当前 producer 传的是批次总数）。"""
    payload = {"total": 2, "error": "boom", "failed_items": [_failed_item()]}
    msg = _build_normalize_failed_message(payload)
    body = msg.blocks[0].text
    assert "1 条" in body, f"正文应与明细条数一致（1 条），实测: {body!r}"
    assert "2 条" not in body, f"正文残留批次总数口径: {body!r}"
    detail = next((b for b in msg.blocks if getattr(b, "title", "")), None)
    assert detail is not None and detail.total == 1


# ── D9：failed_items 从 payload 到消息 → `open_logs` 可达 ──────────────────


def test_with_failed_items_copies_payload_and_enables_open_logs() -> None:
    """payload 的失败明细搬到消息字段后，站内入口应同时挂 `view_detail` + `open_logs`。"""
    msg = NotificationMessage(title="归档失败")
    with_failed_items(msg, {"failed_items": [_failed_item()]})
    assert msg.failed_items and msg.failed_items[0]["standard_number"] == "GB/T 1-2020"
    attach_web_actions(msg, _Cfg())
    assert [a.action for a in msg.actions] == ["view_detail", "open_logs"]


def test_with_failed_items_keeps_builder_set_field() -> None:
    """构建器已显式设置时不覆盖（去重/兼容）。"""
    msg = NotificationMessage(title="t")
    msg.failed_items = [_failed_item("GB/T 9-2020")]
    with_failed_items(msg, {"failed_items": [_failed_item("GB/T 1-2020")]})
    assert [i["standard_number"] for i in msg.failed_items] == ["GB/T 9-2020"]


def test_manager_build_message_attaches_failed_items() -> None:
    """构建出口（`manager._build_message`）是唯一入口 ⇒ 在此搬运可覆盖全部事件。"""
    mgr = NotificationManager.__new__(NotificationManager)
    mgr._EVENT_BUILDERS = {"normalize_failed": _build_normalize_failed_message}
    mgr._cfg = _Cfg(None)
    msg = mgr._build_message("normalize_failed", {"total": 1, "error": "x", "failed_items": [_failed_item()]})
    assert [i["standard_number"] for i in msg.failed_items] == ["GB/T 1-2020"]


def test_merged_message_carries_failed_items_union() -> None:
    """聚合消息必须带上各条目的失败明细（否则聚合路径的 `open_logs` 仍是死路径）。"""
    callbacks: list[NotificationMessage] = []
    agg = NotificationAggregator(sender_func=lambda m, _ch: callbacks.append(m), window_seconds=999.0)
    for i in range(2):
        msg = NotificationMessage(
            title="归档失败", body="x", event_type="archive_failed", notify_event="task_failure"
        )
        msg.failed_items = [_failed_item(f"GB/T {i}-2020")]
        agg.enqueue(msg, [])
    agg.flush_all()
    assert callbacks
    numbers = [i["standard_number"] for i in callbacks[0].failed_items]
    assert numbers == ["GB/T 0-2020", "GB/T 1-2020"], f"聚合后失败明细丢失: {numbers}"
