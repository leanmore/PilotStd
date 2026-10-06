"""通知聚合 B1 的失败明细链路测试：渲染快照、分段边界、落库 JSON 往返、分组键两条路径。

为什么单独成文件：该链路横跨"采集 payload → 构建器渲染 → 渠道分段 → 落库"四层，
原先分散在 stage1x/stage2b 各用例里只覆盖单层；本文件用**真实标准号格式**与
**中文错误类型**做端到端断言（需求①："失败要说明各自总数 + 标准号 + 标准名"）。
"""

from __future__ import annotations

from pathlib import Path

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


def test_failed_items_grouped_with_counts() -> None:
    """需求①口径：按「失败类型 × 标准号 × 标准名」**归并计数**，同组合只出一行 + 总数列。

    这是需求原文的硬要求（"各自总数有多少"）；若退化成"一条失败一行"，批量导入时会刷出成百上千行。
    """
    items = [
        {"standard_number": "GB/T 1234-2020", "standard_name": "甲", "error_type": "not_found"},
        {"standard_number": "GB/T 1234-2020", "standard_name": "甲", "error_type": "not_found"},
        {"standard_number": "GB/T 1234-2020", "standard_name": "甲", "error_type": "not_found"},
        {"standard_number": "GB 9999-2020", "standard_name": "乙", "error_type": "timeout"},
    ]
    block = build_failed_items_block({"failed_items": items})
    assert block is not None
    # 组数 = 2（不是 4 行）；total = 失败条数总和 = 4
    assert len(block.items) == 2
    assert block.total == 4
    # 条数多的组合排在前
    top = block.items[0]
    assert top["standard_number"] == "GB/T 1234-2020"
    assert top["count"] == "3"
    assert top["error_type"] == t("notification.error_type.not_found")
    assert block.items[1]["count"] == "1"


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


# ── 五、批次键（E1/E2）：入口生成 + 分发层搬运（源码级契约，防回归）───────────────


def test_download_batch_generates_batch_key_and_passes_it() -> None:
    """一次批量下载 = 一个批次：键在 `download_batch` 入口生成一次，并透传到完成通知。

    用源码级断言（与 `test_notification_e2e.py` 的契约表同思路）：这三行是"批次键不丢"的最小不变量，
    任何重构只要漏掉其一，①批次路径就会静默退化为 ②（用户看到的就不是"整批一条"）。
    """
    src = (Path(__file__).resolve().parents[1] / "pilotstd" / "download" / "engine.py").read_text(
        encoding="utf-8"
    )
    assert '_ensure_batch_key("dl")' in src, "批次键必须在入口取用（优先共用导入上下文键）"
    assert 'self._notify_download_complete(notification_mgr, stats, _batch_key)' in src, "批次键必须透传"
    assert '"correlation_id": correlation_id' in src, "批次键必须进 payload（供分发层搬运）"


def test_batch_scope_shares_one_key_across_stages() -> None:
    """需求①"一次导入 = 一个批次"：导入作用域内，各阶段取到**同一个**批次键。

    注意：`ensure_batch_key` 会把键**记住在当前上下文**，因此其它用例先跑过就可能留下一个键 ⇒
    这里用**相对断言**（进入作用域取到新键、退出后恢复到进入前的值），不假设"初始必为空"。
    """
    from pilotstd.core.notification.batch import batch_scope, current_batch_key, ensure_batch_key

    before = current_batch_key()
    with batch_scope("imp") as key:
        assert key.startswith("imp-")
        assert key != before, "作用域必须给出新键（否则会与其它导入串批次）"
        # 查询/下载/规范化/存档四阶段的生产者都必须拿到同一个键 ⇒ 才会被聚合器收敛成一条
        assert {ensure_batch_key(p) for p in ("qry", "dl", "norm", "arch")} == {key}
    assert current_batch_key() == before, "退出作用域必须复位到进入前的值（避免串批次）"


def test_dispatcher_carries_batch_key_into_message() -> None:
    """分发层把 payload 的 `correlation_id` 搬到 `NotificationMessage`（空值＝非批次路径）。"""
    src = (
        Path(__file__).resolve().parents[1] / "pilotstd" / "core" / "notification" / "_dispatcher.py"
    ).read_text(encoding="utf-8")
    assert 'msg.correlation_id = str(event_data.get("correlation_id") or "")' in src



def _agg() -> NotificationAggregator:
    return NotificationAggregator(lambda _m, _ch: None, window_seconds=999.0)


def test_group_key_daily_user_activity_converges_without_entity() -> None:
    """需求②：日常动作（`user_activity`）按收敛类成组、**不带实体** ⇒ 时间窗内合成一条。

    公告拉取 / 收藏 都归 `user_activity`；若键里带 `target_id`，同类不同条目会各发一条
    （正是需求②要消除的"短时间内连发多条"）。信息不丢由 Z-21 的"全量块保留"保证。
    """
    agg = _agg()

    def _daily(event_type: str, target: str) -> NotificationMessage:
        return NotificationMessage(
            title="t", event_type=event_type, notify_event="user_activity", target_id=target
        )

    a = _daily("announcement_fetch_complete", "std-a")
    b = _daily("announcement_check_complete", "std-b")
    c = _daily("favorite_created", "std-c")
    keys = {agg._group_key(m) for m in (a, b, c)}
    assert len(keys) == 1, "同类日常动作必须落进同一组（否则会连发多条）"
    assert agg._group_entity(next(iter(keys))) == ""
    # 反例对照：任务终局类仍保留实体维度（不同对象的结果不应混为一条）
    t1 = NotificationMessage(title="t", event_type="download_complete", notify_event="task_result", target_id="std-a")
    t2 = NotificationMessage(title="t", event_type="download_complete", notify_event="task_result", target_id="std-b")
    assert agg._group_key(t1) != agg._group_key(t2)


def test_group_key_daily_bucket_covers_all_three_scenarios() -> None:
    """需求②三场景（公告拉取 / 收藏 / 收藏转下载）必须落进**同一个"日常桶"** ⇒ 窗口内合成一条。

    前两者 `notify_event == "user_activity"`；第三者是收藏链的下载事件（`task_kind == "favorite_download"`，
    类别属 `task_*`）——若按类别分组就会各发一条，正是需求②要消除的连发。
    """
    agg = _agg()
    announcement = NotificationMessage(
        title="t", event_type="announcement_fetch_complete", notify_event="user_activity", target_id="std-a"
    )
    favorite = NotificationMessage(
        title="t", event_type="favorite_created", notify_event="user_activity", target_id="std-b"
    )
    # 收藏转下载：类别属 task_result，但 task_kind 标示它属于收藏链 ⇒ 必须与上面两者同桶
    favorite_download = NotificationMessage(
        title="t", event_type="download_complete", notify_event="task_result", target_id="std-c"
    )
    favorite_download.task_kind = "favorite_download"
    keys = {agg._group_key(m) for m in (announcement, favorite, favorite_download)}
    assert len(keys) == 1, "需求②三场景必须同组（否则仍会连发多条）"
    assert agg._group_entity(next(iter(keys))) == ""


def test_group_key_v1_mode_restores_legacy_behavior(monkeypatch) -> None:
    """P1 灰度开关：`NOTIFY_AGG_KEY=v1` ⇒ 回到旧键（`event_type × target_id`，无模式前缀）。

    这是"已改行为可回滚"的证据；同时校验**非法值/未设置 = v2**（确定性优先，不静默换语义）。
    """
    from pilotstd.core.notification.aggregate_buffer import agg_key_mode

    agg = _agg()
    msg = NotificationMessage(title="t", event_type="scan_complete", notify_event="task_result", target_id="std-a")

    monkeypatch.setenv("NOTIFY_AGG_KEY", "v1")
    assert agg_key_mode() == "v1"
    key_v1 = agg._group_key(msg)
    assert key_v1.startswith("scan_complete"), "v1 必须是旧键形态（事件类型开头）"
    assert key_v1 == "scan_complete\u001fstd-a"
    assert agg._events_in_group(key_v1) == {"scan_complete"}, "v1 下键还原仍要能取回事件类型"

    monkeypatch.setenv("NOTIFY_AGG_KEY", "v2")
    assert agg._group_key(msg).startswith("2\u001f"), "v2 为分层键（模式前缀 2）"

    monkeypatch.setenv("NOTIFY_AGG_KEY", "写错了")
    assert agg_key_mode() == "v2", "非法值必须回退 v2"

    monkeypatch.delenv("NOTIFY_AGG_KEY", raising=False)
    assert agg_key_mode() == "v2", "未设置时默认 v2"


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
