# 模块：项目/核心//_构建器_任务结果脚本
# 通知消息构建器（扫描/查询/归档/规范化/公告抓取/日期提醒）——从 _builders_batch.py 拆出
"""任务结果类通知的构建器（纯函数，无副作用）。

拆出原因（G-010 文件规模治理）：_builders_batch.py 有效行 477 进入警告区；
本块 10 个构建器（scan/query/archive/normalize/announce_fetch/date_reminder）
与原文件其余部分**无任何共享的模块级符号**（AST 实测），因此可整体搬移而
不产生反向依赖，也不改变任何渲染结果。

约定：每个 _build_xxx(data) 接收事件载荷、返回 NotificationMessage；签名即文档，
新增事件时在本文件末尾追加，勿再堆回 _builders_batch.py。
"""

# 分组依据：按消息在链路里的语义阶段排序（扫描 → 查询 → 归档/规范化 → 状态迁移 → 公告抓取），
# 定位模板时先按阶段缩小范围；与 _builders_batch.py 的「下载/收藏」阶段互补，两者合起来
# 覆盖全部任务类通知。顺序本身无副作用（管理器按事件名查表，不依赖定义顺序）。
from pilotstd.i18n import t

from ._format_utils import translate_error_message
from .blocks import (
    KeyValueBlock,
    NotificationBlock,
    TextBlock,
)
from .channel import NotificationMessage


def _build_scan_complete_message(data: dict) -> NotificationMessage:
    """原 Mixin 方法，现为模块级纯函数。

    模板：已扫描：N 个文件，成功：S 个，失败：F 个；有失败明细时
    追加"失败文件："节（• 路径 — 原因）。
    """
    total = data.get("total", 0)
    success = data.get("success", data.get("count", 0))
    failed = data.get("failed", 0)
    blocks: list[NotificationBlock] = [
        TextBlock(text=t("notification.scan.scan_complete.body.stats").format(t=total, s=success, f=failed)),
    ]
    failed_files = data.get("failed_files") or []
    if failed_files:
        # 失败文件逐行展示（模板："• {path} — {reason}"）
        blocks.append(TextBlock(text=t("notification.scan.scan_complete.body.failed_header")))
        lines = [
            t("notification.scan.scan_complete.body.failed_item").format(
                path=ff.get("path", ""), reason=ff.get("reason") or t("notification.common.unknown_reason")
            )
            for ff in failed_files
            if ff.get("path")
        ]
        if lines:
            blocks.append(TextBlock(text="\n".join(lines)))
    return NotificationMessage(
        title=t("notification.scan.scan_complete.title"),
        blocks=blocks,
        level="warning" if failed > 0 else "info",
        event_type="scan_complete",
        icon="pi pi-search",
    )


def _build_date_reminder_message(data: dict) -> NotificationMessage:
    """原 Mixin 方法，现为模块级纯函数。"""
    std_no = data.get("standard_number", "")
    name = data.get("std_name", "")
    days = data.get("days_before", 0)
    remind_type = data.get("remind_type", "")
    blocks: list[NotificationBlock] = [
        TextBlock(
            text=t("notification.validity.date_reminder.body").format(
                standard_number=std_no, std_name=name, days_before=days, remind_type=remind_type
            )
        ),
    ]
    return NotificationMessage(
        title=t("notification.validity.date_reminder.title"),
        blocks=blocks,
        level="info",
        event_type="date_reminder",
        icon="pi pi-calendar",
    )


def _build_scan_empty_message(data: dict) -> NotificationMessage:
    """原 Mixin 方法，现为模块级纯函数。"""
    return NotificationMessage(
        title=t("notification.scan.scan_empty.title"),
        blocks=[TextBlock(text=t("notification.scan.scan_empty.body"))],
        level="info",
        event_type="scan_empty",
        icon="pi pi-search",
    )


# ── 查询 ──
def _build_query_failed_message(data: dict) -> NotificationMessage:
    """原 Mixin 方法，现为模块级纯函数。"""
    std_no = data.get("standard_number", "")
    error = data.get("error", t("notification.common.unknown_error"))
    blocks: list[NotificationBlock] = [
        TextBlock(
            text=t("notification.query.query_failed.body").format(standard_number=std_no, error=error)
        ),
    ]
    return NotificationMessage(
        title=t("notification.query.query_failed.title"),
        blocks=blocks,
        level="error",
        event_type="query_failed",
        icon="pi pi-search",
    )


def _build_query_empty_message(data: dict) -> NotificationMessage:
    """原 Mixin 方法，现为模块级纯函数。"""
    total = data.get("total", 0)
    return NotificationMessage(
        title=t("notification.query.query_empty.title"),
        blocks=[TextBlock(text=t("notification.query.query_empty.body").format(total=total))],
        level="warning",
        event_type="query_empty",
        icon="pi pi-search",
    )


# ── 归档 / 规范化（失败侧）──
def _build_archive_failed_message(data: dict) -> NotificationMessage:
    """归档失败汇总（与 archive_abandoned 语义区分：本事件指批量归档操作失败
    的汇总通知；archive_abandoned 指单条收藏下载重试 7 次后放弃）。"""
    count = data.get("count", 0)
    error = data.get("error", t("notification.common.unknown_error"))
    return NotificationMessage(
        title=t("notification.archive.archive_failed.title"),
        blocks=[TextBlock(text=t("notification.archive.archive_failed.body").format(count=count, error=error))],
        level="error",
        event_type="archive_failed",
        icon="pi pi-folder-open",
    )


def _build_normalize_failed_message(data: dict) -> NotificationMessage:
    """原 Mixin 方法，现为模块级纯函数。

    P1 修复：error 经翻译映射后再渲染，避免 raw Python 异常文本直出。
    """
    total = data.get("total", 0)
    friendly_error = translate_error_message(data.get("error", ""))
    return NotificationMessage(
        title=t("notification.archive.normalize_failed.title"),
        blocks=[
            TextBlock(
                text=t("notification.archive.normalize_failed.body").format(total=total, error=friendly_error)
            )
        ],
        level="error",
        event_type="normalize_failed",
        icon="pi pi-check-square",
    )


# ── 标准状态迁移：失效移出 / 被替代 ──
def _build_expire_standard_moved_message(data: dict) -> NotificationMessage:
    """原 Mixin 方法，现为模块级纯函数。"""
    std_no = data.get("standard_number", "")
    target = data.get("target_path", "")
    return NotificationMessage(
        title=t("notification.validity.expire_standard_moved.title"),
        blocks=[
            TextBlock(
                text=t("notification.validity.expire_standard_moved.body").format(
                    standard_number=std_no, target_path=target
                )
            )
        ],
        level="info",
        event_type="expire_standard_moved",
        icon="pi pi-folder-open",
    )


def _build_replacement_not_found_message(data: dict) -> NotificationMessage:
    """原 Mixin 方法，现为模块级纯函数。"""
    std_no = data.get("standard_number", "")
    sources = data.get("searched_sources", [])
    if sources:
        sources_str = ", ".join(str(s) for s in sources)
        text = t("notification.validity.replacement_not_found.body.with_sources").format(
            standard_number=std_no, sources_str=sources_str
        )
    else:
        text = t("notification.validity.replacement_not_found.body.no_sources").format(standard_number=std_no)
    return NotificationMessage(
        title=t("notification.validity.replacement_not_found.title"),
        blocks=[TextBlock(text=text)],
        level="warning",
        event_type="replacement_not_found",
        icon="pi pi-question-circle",
    )


# ── 公告抓取汇总 ──
def _build_announce_fetch_summary_message(data: dict) -> NotificationMessage:
    """公告抓取逐站汇总（4 段式：标题 + 总计统计行 + 适配器明细（≤5 条））。"""
    adapters = data.get("adapters", [])
    total = data.get("total_count", 0)
    has_error = data.get("has_error", False)
    # 明细截断阈值（4 段式规范：超过 5 条显示汇总提示）
    MAX_ADAPTER_DISPLAY = 5
    # 统计行 + 适配器明细（最多 5 个）
    blocks: list[NotificationBlock] = [
        KeyValueBlock(key=t("notification.announce.announce_fetch_summary.body.total"), value=str(total))
    ]

    display_adapters = adapters[:MAX_ADAPTER_DISPLAY]
    for a in display_adapters:
        if a["status"] == "success":
            status_text = t("notification.announce.announce_fetch_summary.body.adapter_count").format(count=a["count"])
        else:
            status_text = t("notification.announce.announce_fetch_summary.body.adapter_error").format(
                error=a.get("error_msg", t("notification.common.unknown_error"))
            )
        blocks.append(KeyValueBlock(key=a["name"], value=status_text))

    if len(adapters) > MAX_ADAPTER_DISPLAY:
        blocks.append(
            KeyValueBlock(
                key=t("notification.announce.announce_fetch_summary.body.others"),
                value=t("notification.announce.announce_fetch_summary.body.others_count").format(
                    total=len(adapters)
                ),
            )
        )

    title_key = (
        "notification.announce.announce_fetch_summary.title.normal"
        if not has_error
        else "notification.announce.announce_fetch_summary.title.with_error"
    )
    level = "info" if not has_error else "warning"

    return NotificationMessage(
        title=t(title_key),
        blocks=blocks,
        level=level,
        event_type="announce_fetch_summary",
        icon="pi pi-megaphone",
    )
