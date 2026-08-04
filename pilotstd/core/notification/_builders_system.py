# 模块：项目/核心//_构建器_脚本
# 通知消息构建器(系统/备份/错误)—原_，现为模块级纯函数
# 分隔
# 覆盖事件：归档完成、自动备份、公告检查、镜像更新、可信、异常、
# 任务失败、公告抓取失败、配额耗尽。每个构建器独立返回。

import logging

from pilotstd.i18n import _

from .blocks import (
    KeyValueBlock,
    ListBlock,
    NotificationBlock,
    StatusChangeBlock,
    TextBlock,
)
from .channel import NotificationMessage

logger = logging.getLogger(__name__)


def _make_link(standard_number: str | None) -> str | None:
    """根据标准号生成跳转链接。"""
    return f"/standards/{standard_number}" if standard_number else None


def _build_archive_complete_message(data: dict) -> NotificationMessage:
    """原 Mixin 方法，现为模块级纯函数。"""
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


def _build_auto_backup_message(data: dict) -> NotificationMessage:
    """原 Mixin 方法，现为模块级纯函数。"""
    success = data.get("success", False)
    path = data.get("backup_path", "")
    size = data.get("size_mb", "")
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


def _build_announcement_check_complete_message(data: dict) -> NotificationMessage:
    """原 Mixin 方法，现为模块级纯函数。"""
    source = data.get("source", "")
    blocks: list[NotificationBlock] = []
    # 来源信息追加到消息块头部
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
    failures = data.get("failures", 0)
    total = data.get("total_announcements", 0)
    if failures > 0 and total == 0:
        level = "error"
    elif failures > 0:
        level = "warning"
    else:
        level = "info"
    return NotificationMessage(
        title=_("公告检查完成"),
        blocks=blocks,
        level=level,
        event_type="announcement_check_complete",
        icon="pi pi-check-circle",
    )


def _build_fallback_message(event_type: str, data: dict) -> NotificationMessage:
    """原 Mixin 方法，现为模块级纯函数。"""
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


def _build_image_update_available_message(data: dict) -> NotificationMessage:
    """原 Mixin 方法，现为模块级纯函数。"""
    if data.get("error"):
        blocks: list[NotificationBlock] = [TextBlock(text=_("镜像检查失败：{e}").format(e=data["error"]))]
        return NotificationMessage(
            title=_("镜像更新检查失败"),
            blocks=blocks,
            level="error",
            event_type="image_update_available",
            icon="pi pi-cloud-upload",
        )
    blocks: list[NotificationBlock] = [
        StatusChangeBlock(
            label=_("镜像版本"),
            old_value=data.get("old_digest", ""),
            new_value=data.get("new_digest", ""),
        )
    ]
    old_digest = data.get("old_digest", "")
    new_digest = data.get("new_digest", "")
    if not old_digest or not new_digest:
        logger.debug("image_update_available: old_digest or new_digest is empty")
    if data.get("release_notes"):
        blocks.append(TextBlock(text=data["release_notes"]))
    return NotificationMessage(
        title=_("镜像更新可用"),
        blocks=blocks,
        level="info",
        event_type="image_update_available",
        icon="pi pi-cloud-upload",
    )


def _build_trust_ip_update_message(data: dict) -> NotificationMessage:
    """原 Mixin 方法，现为模块级纯函数。"""
    title = data.get("title", "可信 IP 状态")
    text = data.get("body", "")
    blocks: list[NotificationBlock] = [TextBlock(text=text)]
    extra_keys = [k for k in ("ip", "update_time", "status") if data.get(k)]
    # 有额外键值对信息时追加锁
    for k in extra_keys:
        blocks.append(KeyValueBlock(key=k, value=str(data[k])))
    level = "warning" if "失败" in title else "info"
    return NotificationMessage(
        title=title,
        blocks=blocks,
        level=level,
        event_type="trust_ip_update",
        icon="pi pi-shield",
    )


def _build_worker_error_message(data: dict) -> NotificationMessage:
    """原 Mixin 方法，现为模块级纯函数。"""
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


def _build_task_execution_failed_message(data: dict) -> NotificationMessage:
    """原 Mixin 方法，现为模块级纯函数。"""
    task_name = data.get("task_name", _("未知任务"))
    error = data.get("error", _("未知错误"))
    blocks: list[NotificationBlock] = [
        TextBlock(text=_("{task_name} 执行失败：{error}").format(task_name=task_name, error=error)),
    ]
    return NotificationMessage(
        title=_("定时任务执行失败"),
        blocks=blocks,
        level="error",
        event_type="task_execution_failed",
        icon="pi pi-clock",
    )


def _build_announcement_fetch_failed_message(data: dict) -> NotificationMessage:
    """原 Mixin 方法，现为模块级纯函数。"""
    source = data.get("source", _("未知来源"))
    error = data.get("error", _("未知错误"))
    return NotificationMessage(
        title=_("公告抓取失败"),
        blocks=[TextBlock(text=_("{source} 抓取失败：{error}").format(source=source, error=error))],
        level="error",
        event_type="announcement_fetch_failed",
        icon="pi pi-megaphone",
    )


def _build_quota_exhausted_message(data: dict) -> NotificationMessage:
    """原 Mixin 方法，现为模块级纯函数。"""
    site_name = data.get("site_name", _("未知站点"))
    quota_limit = data.get("quota_limit", "0")
    reset_time = data.get("reset_time", _("明日 0:00"))
    return NotificationMessage(
        title=_("适配器日配额已耗尽"),
        blocks=[
            TextBlock(
                text=_("{site_name} 今日配额已用完（限额 {quota_limit}），将于 {reset_time} 重置").format(
                    site_name=site_name, quota_limit=quota_limit, reset_time=reset_time
                )
            )
        ],
        level="warning",
        event_type="quota_exhausted",
        icon="pi pi-exclamation-triangle",
    )
