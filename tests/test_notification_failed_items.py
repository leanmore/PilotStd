"""通知聚合 B1 的失败明细链路测试：渲染快照、分段边界、落库 JSON 往返、分组键两条路径。

为什么单独成文件：该链路横跨"采集 payload → 构建器渲染 → 渠道分段 → 落库"四层，
原先分散在 stage1x/stage2b 各用例里只覆盖单层；本文件用**真实标准号格式**与
**中文错误类型**做端到端断言（需求①："失败要说明各自总数 + 标准号 + 标准名"）。
"""

from __future__ import annotations

from pilotstd.core.notification._builders_batch import (
    _ERROR_TYPE_KEYS,
    _build_normalize_complete_message,
    build_failed_items_block,
)
from pilotstd.core.notification._json_codec import dumps, loads_list
from pilotstd.core.notification.aggregate_buffer import NotificationAggregator
from pilotstd.core.notification.blocks import ListBlock, TextBlock
from pilotstd.core.notification.channel import NotificationMessage
from pilotstd.core.notification.renderer import CHANNEL_TEXT_LIMITS, split_for_channel
from pilotstd.i18n import t

_FAILED_ITEMS = [
    {
        "standard_number": "GB/T 1234-2020",
        "standard_name": "复合钢管超声检测方法",
        "error_type": "not_found",
        "error_message": "源文件不存在",
    },
    {
        "standard_number": "GB 12345-2020",
        "standard_name": "",  # 标准名缺失 ⇒ 渲染为 "-"
        "error_type": "timeout",
        "error_message": "下载超时 30s",
    },
]


def _failed_block_of(msg: NotificationMessage) -> ListBlock | None:
    for blk in msg.blocks:
        if isinstance(blk, ListBlock):
            return blk
    return None


# ── 一、渲染快照（构建器侧）───────────────────────────────────────────────────


def test_normalize_complete_renders_failed_items_block() -> None:
    """失败明细渲染为 ListBlock；4 列齐全、空标准名填 '-'、错误类型**已翻译为中文**。"""
    msg = _build_normalize_complete_message({"total": 130, "success": 128, "failed": 2, "failed_items": _FAILED_ITEMS})
    block = _failed_block_of(msg)
    assert block is not None, "有 failed_items 时必须产出列表块"
    assert block.total == 2
    row0, row1 = block.items
    # 真实标准号格式（项目内样例同款：GB/T 1234-2020 / GB 12345-2020）
    assert row0["standard_number"] == "GB/T 1234-2020"
    assert row0["standard_name"] == "复合钢管超声检测方法"
    # 取值翻译：不是枚举键本身，而是 i18n 文案
    assert row0["error_type"] == t("notification.error_type.not_found")
    assert row1["error_type"] == t("notification.error_type.timeout")
    # 空值口径：标准名缺失 ⇒ '-'
    assert row1["standard_name"] == "-"
    # 首个块仍是"总数"文本块（成功只报总数的口径未变）
    assert isinstance(msg.blocks[0], TextBlock)


def test_no_failed_items_means_no_block() -> None:
    """无失败明细时**不追加**块（零行为变更：老 payload 与小批量场景不受影响）。"""
    assert build_failed_items_block({}) is None
    assert build_failed_items_block({"failed_items": []}) is None
    msg = _build_normalize_complete_message({"total": 3, "success": 3, "failed": 0})
    assert _failed_block_of(msg) is None


def test_error_type_enum_is_closed_set() -> None:
    """枚举取值集合与 B1 裁定一致（新增取值必须同批登记 i18n，否则会退回 unknown 文案）。"""
    assert set(_ERROR_TYPE_KEYS) == {"not_found", "parse", "network", "timeout", "unknown"}
    unknown = build_failed_items_block({"failed_items": [{"error_type": "崩塌"}]})
    assert unknown is not None
    assert unknown.items[0]["error_type"] == t("notification.error_type.unknown")


# ── 二、分段边界（渠道侧）─────────────────────────────────────────────────────


def test_split_noop_when_within_limit() -> None:
    """未超限时原样返回单段（零行为变更）。"""
    assert split_for_channel("短消息", "telegram") == ["短消息"]


def test_split_boundary_and_no_information_loss() -> None:
    """超限必须切分：每段不超上限、段数正确、**信息零丢失**、第 2 段起带「续 N/M」。"""
    big = "\n".join(f"line-{i:04d} " + "x" * 70 for i in range(300))
    segs = split_for_channel(big, "telegram")
    limit, unit = CHANNEL_TEXT_LIMITS["telegram"]
    assert len(segs) > 1
    for seg in segs:
        assert len(seg) <= limit, "任何一段都不得超过渠道上限"
    assert "".join(segs).count("line-") == 300, "切分不得丢行"
    assert t("notification.segment.continued").split("{")[0] in segs[-1]


def test_split_byte_based_for_wecom() -> None:
    """企微是**字节**口径：按 UTF-8 字节数判定，逐字符累加不得切坏多字节字符。"""
    big = "\n".join("中文条目" + "ｘ" * 30 + f"-{i}" for i in range(200))
    segs = split_for_channel(big, "wecom")
    limit = CHANNEL_TEXT_LIMITS["wecom"][0]
    assert len(segs) > 1
    for seg in segs:
        assert len(seg.encode("utf-8")) <= limit
    assert "".join(segs).count("中文条目") == 200


def test_long_single_line_is_hard_cut_within_limit() -> None:
    """超长单行（无换行可切）也必须硬切到不超限。"""
    segs = split_for_channel("z" * 9000, "telegram")
    assert len(segs) >= 3
    assert all(len(s) <= CHANNEL_TEXT_LIMITS["telegram"][0] for s in segs)
    assert sum(s.count("z") for s in segs) == 9000


# ── 三、落库 JSON 往返（数据层）───────────────────────────────────────────────


def test_failed_items_json_roundtrip() -> None:
    """`failed_items` 经 `_json_codec` 往返后与原文一致（落库列是 TEXT 存 JSON）。"""
    text = dumps(_FAILED_ITEMS)
    assert isinstance(text, str) and text.startswith("[")
    assert loads_list(text) == _FAILED_ITEMS
    # 空清单口径：默认 '[]'（迁移 DEFAULT）也必须可解析
    assert loads_list("[]") == []


# ── 四、分组键两条路径（聚合器）──────────────────────────────────────────────


def _agg() -> NotificationAggregator:
    return NotificationAggregator(lambda _m, _ch: None, window_seconds=999.0)


def test_group_key_batch_path_and_daily_path() -> None:
    """①批次路径 = 批次 × 收敛类（不含实体）；②日常路径 = 收敛类 × 实体。"""
    agg = _agg()
    batch = NotificationMessage(title="t", event_type="normalize_complete", notify_event="batch_summary")
    batch.correlation_id = "imp-2026-10-05"
    batch.target_id = "std-a"
    other = NotificationMessage(title="t", event_type="normalize_complete", notify_event="batch_summary")
    other.correlation_id = "imp-2026-10-05"
    other.target_id = "std-b"
    daily = NotificationMessage(title="t", event_type="scan_complete", notify_event="task_result", target_id="std-a")

    k1, k2, k3 = agg._group_key(batch), agg._group_key(other), agg._group_key(daily)
    assert k1 == k2, "同批次内不同实体必须收敛为同组（明细走 payload.failed_items）"
    assert k1 != k3
    assert agg._events_in_group(k1) == {"batch_summary"}
    assert agg._group_entity(k1) == ""
    assert agg._events_in_group(k3) == {"task_result"}
    assert agg._group_entity(k3) == "std-a"
