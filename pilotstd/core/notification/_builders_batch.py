# pilotstd/core/notification/_builders_batch.py
# 通知消息构建器混入(批次/查询/下载) — 从 _message_builders.py 提取
# 为何每个事件一个独立构建方法：各事件字段差异大，统一工厂会导致参数爆炸；
# 方法签名即文档（IDE 可精确跳转）；level 决策内聚在构建器中（failed>0→error）

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

    def _build_announcement_fetch_complete_message(self, data: dict) -> NotificationMessage:
        """构建公告拉取完成的通知消息。"""
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

    def _build_download_failed_message(self, data: dict) -> NotificationMessage:
        """构建单个下载失败的通知消息。"""
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

    def _build_archive_abandoned_message(self, data: dict) -> NotificationMessage:
        """构建归档放弃（重试耗尽）的通知消息。"""
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

    def _build_normalize_complete_message(self, data: dict) -> NotificationMessage:
        """构建规范化完成的通知消息。"""
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

    def _build_scan_complete_message(self, data: dict) -> NotificationMessage:
        """构建扫描完成的通知消息。"""
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

    def _build_date_reminder_message(self, data: dict) -> NotificationMessage:
        """构建标准实施日期提醒的通知消息。"""
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

    def _build_scan_empty_message(self, data: dict) -> NotificationMessage:
        """构建扫描完成（无新文件）的通知消息。"""
        return NotificationMessage(
            title=_("扫描完成"),
            blocks=[TextBlock(text=_("未发现新文件"))],
            level="info",
            event_type="scan_empty",
            icon="pi pi-search",
        )

    def _build_query_failed_message(self, data: dict) -> NotificationMessage:
        """构建单条标准查询失败的通知消息。"""
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

    def _build_query_empty_message(self, data: dict) -> NotificationMessage:
        """构建查询完成（全部未命中）的通知消息。"""
        total = data.get("total", 0)
        return NotificationMessage(
            title=_("查询完成"),
            blocks=[TextBlock(text=_("共 {total} 条标准，全部未命中").format(total=total))],
            level="warning",
            event_type="query_empty",
            icon="pi pi-search",
        )

    def _build_archive_failed_message(self, data: dict) -> NotificationMessage:
        """构建归档失败的通知消息。"""
        count = data.get("count", 0)
        error = data.get("error", _("未知错误"))
        return NotificationMessage(
            title=_("归档失败"),
            blocks=[TextBlock(text=_("{count} 条标准归档失败：{error}").format(count=count, error=error))],
            level="error",
            event_type="archive_failed",
            icon="pi pi-folder-open",
        )

    def _build_normalize_failed_message(self, data: dict) -> NotificationMessage:
        """构建规范化失败的通知消息。"""
        total = data.get("total", 0)
        error = data.get("error", _("未知错误"))
        return NotificationMessage(
            title=_("规范化失败"),
            blocks=[TextBlock(text=_("{total} 条标准规范化失败：{error}").format(total=total, error=error))],
            level="error",
            event_type="normalize_failed",
            icon="pi pi-check-square",
        )

    def _build_expire_standard_moved_message(self, data: dict) -> NotificationMessage:
        """构建废止标准移入过期作废的通知消息。"""
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

    def _build_replacement_not_found_message(self, data: dict) -> NotificationMessage:
        """构建替代标准查找失败的通知消息。"""
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
