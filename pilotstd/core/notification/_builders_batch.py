# pilotstd/core/notification/_builders_batch.py
# 通知消息构建器混入(批次/查询/下载) — 从 _message_builders.py 提取

from pilotstd.i18n import _

from .blocks import (
    KeyValueBlock,
    ListBlock,
    NotificationBlock,
    TextBlock,
)
from .channel import NotificationMessage


class _BatchBuildersMixin:
    """批次/查询/下载消息构建方法集合。"""

    def _build_check_batch_complete_message(self, data: dict) -> NotificationMessage:
        """构建批量检查完成的通知消息。"""
        total = data.get("total", 0)
        changed = data.get("changed", 0)
        expired = data.get("expired", 0)
        soon = data.get("soon", 0)
        blocks: list[NotificationBlock] = []
        if changed == 0:
            blocks.append(TextBlock(text=_("本次检查未发现状态变更")))
        blocks.extend(
            [
                KeyValueBlock(key=_("检查总数"), value=str(total)),
                KeyValueBlock(key=_("状态变更"), value=str(changed)),
                KeyValueBlock(key=_("已过期"), value=str(expired)),
                KeyValueBlock(key=_("即将过期"), value=str(soon)),
            ]
        )
        return NotificationMessage(
            title=_("标准检查完成"),
            blocks=blocks,
            level="info",
            event_type="check_batch_complete",
            icon="pi pi-check-circle",
        )

    def _build_announcement_fetch_complete_message(self, data: dict) -> NotificationMessage:
        """构建公告拉取完成的通知消息。"""
        blocks: list[NotificationBlock] = [KeyValueBlock(key=_("新增公告"), value=str(data.get("new_count", 0)))]
        if data.get("source"):
            blocks.append(TextBlock(text=_("来源：{s}").format(s=data["source"])))
        return NotificationMessage(
            title=_("公告拉取完成"),
            blocks=blocks,
            level="info",
            event_type="announcement_fetch_complete",
            icon="pi pi-megaphone",
        )

    # ── 备份/同步事件 ──

    def _build_batch_download_complete_message(self, data: dict) -> NotificationMessage:
        success = data.get("success", 0)
        failed = data.get("failed", 0)
        skipped = data.get("skipped", 0)
        blocks: list[NotificationBlock] = [
            KeyValueBlock(key=_("成功"), value=str(success)),
            KeyValueBlock(key=_("失败"), value=str(failed)),
            KeyValueBlock(key=_("跳过"), value=str(skipped)),
        ]
        # 有失败时升级为 warning 级别，引导用户查看详情
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

    # ── 扫描/有效性检查事件 ──

    def _build_batch_query_summary_message(self, data: dict) -> NotificationMessage:
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
        # 根据命中率决定通知级别：全命中=info，有待确认=warning
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

    def _build_auto_query_complete_message(self, data: dict) -> NotificationMessage:
        changed = data.get("changed", 0)
        total = data.get("total", 0)
        # 定时查询结果：区分有/无变更两套消息
        if changed > 0:
            text = _("定时查询完成：共检查 {total} 条，{changed} 条状态变更").format(total=total, changed=changed)
        else:
            text = _("定时查询完成：共检查 {total} 条，无状态变更").format(total=total)
        blocks: list[NotificationBlock] = [TextBlock(text=text)]
        return NotificationMessage(
            title=_("定时查询完成"),
            blocks=blocks,
            level="info",
            event_type="auto_query_complete",
            icon="pi pi-clock",
        )

    def _build_auto_scan_failed_message(self, data: dict) -> NotificationMessage:
        """构建自动扫描失败的通知消息。"""
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
