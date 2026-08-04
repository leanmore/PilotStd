# pilotstd/core/notification/_builders_batch.py
# 通知消息构建器(批次/查询/下载) — 原 _BatchBuildersMixin，现为模块级纯函数
#
# 每个 _build_*_message(data) 函数签名一致：接收 dict → 返回 NotificationMessage。
# level 决策内聚在构建器内部（如 failed > 0 → warning）。
# 设计原则：方法签名即文档，每个事件独立构建避免参数爆炸。

from pilotstd.i18n import _

from .blocks import (
    KeyValueBlock,
    ListBlock,
    NotificationBlock,
    TextBlock,
)
from .channel import NotificationMessage


def _build_announcement_fetch_complete_message(data: dict) -> NotificationMessage:
    """原 Mixin 方法，现为模块级纯函数。"""
    blocks: list[NotificationBlock] = [KeyValueBlock(key=_("新增公告"), value=str(data.get("count", 0)))]
    if data.get("source"):
        blocks.append(TextBlock(text=_("来源：{s}").format(s=data["source"])))
    return NotificationMessage(
        title=_("公告拉取完成"),
        blocks=blocks,
        level="info",
        event_type="announcement_fetch_complete",
        icon="pi pi-megaphone",
    )


def _build_batch_download_complete_message(data: dict) -> NotificationMessage:
    """原 Mixin 方法，现为模块级纯函数。"""
    success = data.get("success", 0)
    failed = data.get("failed", 0)
    skipped = data.get("skipped", 0)
    # 根据失败数决定消息级别：有失败 → warning，否则 info
    blocks: list[NotificationBlock] = [
        KeyValueBlock(key=_("成功"), value=str(success)),
        KeyValueBlock(key=_("失败"), value=str(failed)),
        KeyValueBlock(key=_("跳过"), value=str(skipped)),
    ]
    if failed == 0:
        return NotificationMessage(
            title=_("批量下载完成"),
            blocks=blocks,
            level="info",
            event_type="batch_download_complete",
            icon="pi pi-download",
        )
    return NotificationMessage(
        title=_("批量下载完成（有失败）"),
        blocks=blocks,
        level="warning",
        event_type="batch_download_complete",
        icon="pi pi-download",
    )


def _build_batch_query_summary_message(data: dict) -> NotificationMessage:
    """原 Mixin 方法，现为模块级纯函数。"""
    total = data.get("total", 0)
    found = data.get("found", 0)
    pending = data.get("pending", 0)
    results = data.get("results", [])
    n = len(results) if results else total
    blocks: list[NotificationBlock] = [TextBlock(text=_("查询完成，共 {n} 条结果").format(n=n))]
    if results:
        items = [{"number": r["number"], "name": r.get("name", "")} for r in results]
        blocks.append(
            ListBlock(
                title=_("查询结果"),
                items=items,
                total=n,
            )
        )
    if pending > 0:
        level = "warning"
    elif found == total:
        level = "info"
    else:
        level = "info"
    return NotificationMessage(
        title=_("标准查询完成"),
        blocks=blocks,
        level=level,
        event_type="batch_query_summary",
        icon="pi pi-search",
    )


def _build_auto_scan_failed_message(data: dict) -> NotificationMessage:
    """原 Mixin 方法，现为模块级纯函数。"""
    blocks: list[NotificationBlock] = [TextBlock(text=_("路径：{p}").format(p=data.get("path", "")))]
    if data.get("error"):
        blocks.append(TextBlock(text=_("错误：{e}").format(e=data["error"])))
    return NotificationMessage(
        title=_("自动扫描失败"),
        blocks=blocks,
        level="error",
        event_type="auto_scan_failed",
        icon="pi pi-exclamation-triangle",
    )


def _build_download_failed_message(data: dict) -> NotificationMessage:
    """原 Mixin 方法，现为模块级纯函数。"""
    blocks: list[NotificationBlock] = [
        TextBlock(text=_("标准号：{s}").format(s=data.get("standard_number", ""))),
        TextBlock(text=_("错误：{e}").format(e=data.get("error", _("未知错误")))),
    ]
    return NotificationMessage(
        title=_("收藏下载失败"),
        blocks=blocks,
        level="error",
        event_type="download_failed",
        icon="pi pi-download",
    )


def _build_archive_abandoned_message(data: dict) -> NotificationMessage:
    """原 Mixin 方法，现为模块级纯函数。"""
    blocks: list[NotificationBlock] = [
        TextBlock(text=_("标准信息：{s}").format(s=data.get("standard_info", ""))),
        TextBlock(text=_("错误：{e}").format(e=data.get("error", _("未知错误")))),
    ]
    return NotificationMessage(
        title=_("归档任务放弃"),
        blocks=blocks,
        level="error",
        event_type="archive_abandoned",
        icon="pi pi-folder-open",
    )


def _build_normalize_complete_message(data: dict) -> NotificationMessage:
    """原 Mixin 方法，现为模块级纯函数。"""
    total = data.get("total", 0)
    success = data.get("success", total)
    failed = data.get("failed", 0)
    blocks: list[NotificationBlock] = [
        TextBlock(
            text=_("共 {total} 条标准，成功 {success} 条，失败 {failed} 条").format(
                total=total, success=success, failed=failed
            )
        ),
    ]
    return NotificationMessage(
        title=_("规范化完成"),
        blocks=blocks,
        level="info",
        event_type="normalize_complete",
        icon="pi pi-check-square",
    )


def _build_scan_complete_message(data: dict) -> NotificationMessage:
    """原 Mixin 方法，现为模块级纯函数。"""
    count = data.get("count", 0)
    failed = data.get("failed", 0)
    blocks: list[NotificationBlock] = [
        TextBlock(text=_("新增 {count} 个文件，{failed} 个文件解析失败").format(count=count, failed=failed)),
    ]
    return NotificationMessage(
        title=_("扫描完成"),
        blocks=blocks,
        level="info" if count > 0 else "warning",
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
            text=_("{standard_number} {std_name} 距离实施日期还有 {days_before} 天（{remind_type}）").format(
                standard_number=std_no, std_name=name, days_before=days, remind_type=remind_type
            )
        ),
    ]
    return NotificationMessage(
        title=_("标准实施日期提醒"),
        blocks=blocks,
        level="info",
        event_type="date_reminder",
        icon="pi pi-calendar",
    )


def _build_scan_empty_message(data: dict) -> NotificationMessage:
    """原 Mixin 方法，现为模块级纯函数。"""
    return NotificationMessage(
        title=_("扫描完成"),
        blocks=[TextBlock(text=_("未发现新文件"))],
        level="info",
        event_type="scan_empty",
        icon="pi pi-search",
    )


def _build_query_failed_message(data: dict) -> NotificationMessage:
    """原 Mixin 方法，现为模块级纯函数。"""
    std_no = data.get("standard_number", "")
    error = data.get("error", _("未知错误"))
    blocks: list[NotificationBlock] = [
        TextBlock(text=_("{standard_number} 查询失败：{error}").format(standard_number=std_no, error=error)),
    ]
    return NotificationMessage(
        title=_("标准查询失败"),
        blocks=blocks,
        level="error",
        event_type="query_failed",
        icon="pi pi-search",
    )


def _build_query_empty_message(data: dict) -> NotificationMessage:
    """原 Mixin 方法，现为模块级纯函数。"""
    total = data.get("total", 0)
    return NotificationMessage(
        title=_("查询完成"),
        blocks=[TextBlock(text=_("共 {total} 条标准，全部未命中").format(total=total))],
        level="warning",
        event_type="query_empty",
        icon="pi pi-search",
    )


def _build_archive_failed_message(data: dict) -> NotificationMessage:
    """原 Mixin 方法，现为模块级纯函数。"""
    count = data.get("count", 0)
    error = data.get("error", _("未知错误"))
    return NotificationMessage(
        title=_("归档失败"),
        blocks=[TextBlock(text=_("{count} 条标准归档失败：{error}").format(count=count, error=error))],
        level="error",
        event_type="archive_failed",
        icon="pi pi-folder-open",
    )


def _build_normalize_failed_message(data: dict) -> NotificationMessage:
    """原 Mixin 方法，现为模块级纯函数。"""
    total = data.get("total", 0)
    error = data.get("error", _("未知错误"))
    return NotificationMessage(
        title=_("规范化失败"),
        blocks=[TextBlock(text=_("{total} 条标准规范化失败：{error}").format(total=total, error=error))],
        level="error",
        event_type="normalize_failed",
        icon="pi pi-check-square",
    )


def _build_expire_standard_moved_message(data: dict) -> NotificationMessage:
    """原 Mixin 方法，现为模块级纯函数。"""
    std_no = data.get("standard_number", "")
    target = data.get("target_path", "")
    return NotificationMessage(
        title=_("废止标准已移入过期作废"),
        blocks=[
            TextBlock(
                text=_("{standard_number} 已移入过期作废目录：{target_path}").format(
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
        text = _("{standard_number} 的替代标准未找到，已搜索：{sources_str}").format(
            standard_number=std_no, sources_str=sources_str
        )
    else:
        text = _("{standard_number} 的替代标准未找到，未配置搜索源").format(standard_number=std_no)
    return NotificationMessage(
        title=_("替代标准查找失败"),
        blocks=[TextBlock(text=text)],
        level="warning",
        event_type="replacement_not_found",
        icon="pi pi-question-circle",
    )


def _build_announce_fetch_summary_message(data: dict) -> NotificationMessage:
    """原 Mixin 方法，现为模块级纯函数。"""
    adapters = data.get("adapters", [])
    total = data.get("total_count", 0)
    has_error = data.get("has_error", False)
    # 最多展示 10 个适配器，超过部分显示摘要

    MAX_ADAPTER_DISPLAY = 10
    # 总计块 + 适配器明细（最多 10 个）
    blocks: list[NotificationBlock] = [KeyValueBlock(key=_("总计"), value=str(total))]

    display_adapters = adapters[:MAX_ADAPTER_DISPLAY]
    for a in display_adapters:
        if a["status"] == "success":
            status_text = _("{count} 条").format(count=a["count"])
        else:
            status_text = _("失败: {error}").format(error=a.get("error_msg", _("未知错误")))
        blocks.append(KeyValueBlock(key=a["name"], value=status_text))

    if len(adapters) > MAX_ADAPTER_DISPLAY:
        blocks.append(
            KeyValueBlock(
                key=_("其他"),
                value=_("等共 {total} 个适配器").format(total=len(adapters)),
            )
        )

    title = _("公告抓取完成") if not has_error else _("公告抓取完成（有异常）")
    level = "info" if not has_error else "warning"

    return NotificationMessage(
        title=title,
        blocks=blocks,
        level=level,
        event_type="announce_fetch_summary",
        icon="pi pi-megaphone",
    )
