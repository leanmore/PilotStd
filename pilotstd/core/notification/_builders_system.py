# pilotstd/core/notification/_builders_system.py
# 通知消息构建器混入(系统/备份/错误) — 从 _message_builders.py 提取

from pilotstd.i18n import _

from .blocks import (
    KeyValueBlock,
    ListBlock,
    NotificationBlock,
    StatusChangeBlock,
    TextBlock,
)
from .channel import NotificationMessage


def _make_link(standard_number: str | None) -> str | None:
    """根据标准号生成跳转链接。"""
    return f"/standards/{standard_number}" if standard_number else None


class _SystemBuildersMixin:
    """系统/备份/错误消息构建方法集合。"""

    def _build_archive_complete_message(self, data: dict) -> NotificationMessage:
        """构建归档完成通知——成功展示目录清单，空归档展示提示文本。"""
        count = data.get("count", 0)
        directories = data.get("directories", [])
        blocks: list[NotificationBlock]
        if count == 0:
            blocks = [TextBlock(text=_("未归档任何目录（所有目标均为空或已归档）"))]
        else:
            blocks = [TextBlock(text=_("已归档 {count} 个目录").format(count=count))]
            if directories:
                blocks.append(
                    ListBlock(
                        title=_("归档目录清单"),
                        items=[{"name": d} for d in directories],
                        total=count,
                        detail_url=_make_link(data.get("standard_number")),
                    )
                )
        return NotificationMessage(
            title=_("归档完成"),
            blocks=blocks,
            level="info",
            standard_number=data.get("standard_number"),
            event_type="archive_complete",
            link=_make_link(data.get("standard_number")),
            icon="pi pi-folder-open",
            status=data.get("status", ""),
            target_id=data.get("target_id", ""),
            elapsed_ms=data.get("elapsed_ms", 0),
        )

    # ── 标准状态变更事件 ──

    def _build_auto_backup_message(self, data: dict) -> NotificationMessage:
        success = data.get("success", False)
        path = data.get("path", "")
        size = data.get("size", "")
        # 成功和失败走不同消息模板，便于用户快速识别状态
        if success:
            blocks: list[NotificationBlock] = [
                KeyValueBlock(key=_("备份路径"), value=path),
                KeyValueBlock(key=_("文件大小"), value=size),
            ]
            return NotificationMessage(
                title=_("自动备份成功"),
                blocks=blocks,
                level="info",
                event_type="auto_backup",
                icon="pi pi-database",
            )
        blocks = [TextBlock(text=_("备份失败：{err}").format(err=data.get("error", _("未知错误"))))]
        return NotificationMessage(
            title=_("自动备份失败"),
            blocks=blocks,
            level="error",
            event_type="auto_backup",
            icon="pi pi-database",
        )

    def _build_announcement_check_complete_message(self, data: dict) -> NotificationMessage:
        """构建公告检查完成通知——分来源/公告数量/涉及标准三层展示。"""
        source = data.get("source", "")
        blocks: list[NotificationBlock] = []
        if source:
            blocks.append(TextBlock(text=_("来源：{s}").format(s=source)))
        blocks.extend(
            [
                KeyValueBlock(key=_("公告总数"), value=str(data.get("total_announcements", 0))),
                KeyValueBlock(key=_("国标"), value=str(data.get("gb_count", 0))),
                KeyValueBlock(key=_("行标"), value=str(data.get("hb_count", 0))),
                KeyValueBlock(key=_("地标"), value=str(data.get("db_count", 0))),
                KeyValueBlock(key=_("涉及标准"), value=str(data.get("total_standards", 0))),
            ]
        )
        if data.get("failures", 0) > 0:
            blocks.append(TextBlock(text=_("注意：{n} 个站点检查失败").format(n=data["failures"])))
        return NotificationMessage(
            title=_("公告检查完成"),
            blocks=blocks,
            level="info",
            event_type="announcement_check_complete",
            icon="pi pi-check-circle",
        )

    # ── 下载事件 ──

    def _build_fallback_message(self, event_type: str, data: dict) -> NotificationMessage:
        """构建未知事件类型的兜底通知消息。"""
        blocks: list[NotificationBlock] = [
            TextBlock(text=_("事件类型：{t}").format(t=data.get("event_type", "unknown")))
        ]
        if data:
            blocks.append(TextBlock(text=str(data)))
        return NotificationMessage(
            title=event_type,
            blocks=blocks,
            level="info",
            event_type=event_type,
            icon="pi pi-bell",
        )

    # ── 2026-07-01 新增事件 ──

    def _build_image_update_available_message(self, data: dict) -> NotificationMessage:
        """构建镜像更新可用的通知消息。"""
        blocks: list[NotificationBlock] = [
            StatusChangeBlock(
                label=_("镜像版本"),
                old_value=data.get("old_version", ""),
                new_value=data.get("new_version", ""),
            )
        ]
        if data.get("release_notes"):
            blocks.append(TextBlock(text=data["release_notes"]))
        return NotificationMessage(
            title=_("镜像更新可用"),
            blocks=blocks,
            level="info",
            event_type="image_update_available",
            icon="pi pi-cloud-upload",
        )

    # ── 查询/汇总事件 ──

    def _build_trust_ip_update_message(self, data: dict) -> NotificationMessage:
        title = data.get("title", "可信 IP 状态")
        text = data.get("body", "")
        blocks: list[NotificationBlock] = [TextBlock(text=text)]
        # 有额外的键值对信息（如 IP 地址、更新时间）时追加 KeyValueBlock
        extra_keys = [k for k in ("ip", "update_time", "status") if data.get(k)]
        for k in extra_keys:
            blocks.append(KeyValueBlock(key=k, value=str(data[k])))
        # "失败"关键词触发 warning 级别，提醒运维介入
        level = "warning" if "失败" in title else "info"
        return NotificationMessage(
            title=title,
            blocks=blocks,
            level=level,
            event_type="trust_ip_update",
            icon="pi pi-shield",
        )

    def _build_worker_error_message(self, data: dict) -> NotificationMessage:
        """构建后台工作线程异常的通知消息。"""
        worker = data.get("worker", "未知")
        error = data.get("error", "")
        blocks: list[NotificationBlock] = [
            TextBlock(text=_("{worker} 工作线程异常").format(worker=worker)),
        ]
        if error:
            blocks.append(TextBlock(text=_("错误：{error}").format(error=error)))
        if data.get("traceback"):
            blocks.append(TextBlock(text=data["traceback"]))
        return NotificationMessage(
            title=_("后台任务异常"),
            blocks=blocks,
            level="error",
            event_type="worker_error",
            icon="pi pi-cog",
        )
