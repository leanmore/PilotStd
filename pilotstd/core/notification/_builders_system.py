# 模块：项目/核心//_构建器_脚本
# 通知消息构建器(系统/备份/错误)—原_，现为模块级纯函数
# 分隔
# 覆盖事件：归档完成、自动备份、公告检查、镜像更新、可信、异常、
# 任务失败、公告抓取失败、配额耗尽。每个构建器独立返回。

import logging

from pilotstd.i18n import _

from ._format_utils import translate_error_message
from .blocks import (
    KeyValueBlock,
    NotificationBlock,
    TextBlock,
)
from .channel import NotificationMessage

logger = logging.getLogger(__name__)

# 定时任务 job_id → 中文名映射（task_execution_failed 模板，批次2）
_TASK_NAME_MAP = {
    "auto_announce": _("公告自动更新"),
    "auto_scan": _("自动扫描"),
    "auto_backup": _("自动备份"),
    "auto_archive_retry": _("收藏下载重试"),
    "auto_health_check": _("健康检查"),
    "date_reminder": _("日期提醒"),
    "validity_check": _("时效性检查"),
    "notification_cleanup": _("通知日志清理"),
    "release_suppressed": _("静音补发"),
}


def _make_link(standard_number: str | None) -> str | None:
    """根据标准号生成跳转链接。"""
    return f"/standards/{standard_number}" if standard_number else None


def _build_archive_complete_message(data: dict) -> NotificationMessage:
    """原 Mixin 方法，现为模块级纯函数。

    模板：已归档：N 个文件 → 分类统计（国标：N 条，行业细分：N 条…）
    → 归档目录逐行（• {dir}）。
    """
    count = data.get("count", 0)
    blocks: list[NotificationBlock] = [TextBlock(text=_("已归档：{n} 个文件").format(n=count))]
    # 分类统计（C-2：发送点已用 classify_std_code 聚合，label 即中文分类名）
    category_stats = data.get("category_stats") or {}
    if category_stats:
        summary = "，".join(_("{label}：{n} 条").format(label=k, n=v) for k, v in category_stats.items())
        blocks.append(TextBlock(text=summary))
    # 归档目录逐行（发送点从 organizer 明细提取的目标目录）
    directories = data.get("directories") or []
    if directories:
        blocks.append(TextBlock(text=_("归档目录：")))
        blocks.append(TextBlock(text="\n".join(_("• {d}").format(d=d) for d in directories)))
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
    """原 Mixin 方法，现为模块级纯函数。

    模板：来源单独成行 → 统计折叠为一行（消除零结果逐行罗列）：
    "公告总数：N，国标：G，行标：H，地标：D，涉及标准：S"
    """
    source = data.get("source", "")
    blocks: list[NotificationBlock] = []
    # 来源信息追加到消息块头部（定时/手动路径均携带）
    if source:
        blocks.append(TextBlock(text=_("来源：{s}").format(s=source)))
    summary = _("公告总数：{t}，国标：{g}，行标：{h}，地标：{d}，涉及标准：{s}").format(
        t=data.get("total_announcements", 0),
        g=data.get("gb_count", 0),
        h=data.get("hb_count", 0),
        d=data.get("db_count", 0),
        s=data.get("total_standards", 0),
    )
    blocks.append(TextBlock(text=summary))
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
    # 正常路径：上面错误分支已提前返回，此处安全重建 blocks
    # 模板：镜像版本：v旧 → v新；版本号缺失时回退 digest 前 12 位
    old_digest = data.get("old_digest", "")
    new_digest = data.get("new_digest", "")
    old_ver = data.get("old_version") or (old_digest[:12] if old_digest else "")
    new_ver = data.get("new_version") or (new_digest[:12] if new_digest else "")
    blocks: list[NotificationBlock] = [
        TextBlock(text=_("镜像版本：{old} → {new}").format(old=old_ver, new=new_ver)),
    ]
    if not old_digest or not new_digest:
        logger.debug("image_update_available: old_digest or new_digest is empty")
    if data.get("release_notes"):
        blocks.append(TextBlock(text=_("更新内容：{n}").format(n=data["release_notes"])))
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
    """原 Mixin 方法，现为模块级纯函数。

    模板：任务：{中文名} / 错误：{翻译后错误} / 系统将在下次调度时自动重试。
    任务名经 job_id → 中文映射，错误经翻译映射（C-3）。
    """
    raw_task = data.get("task_name", _("未知任务"))
    task_name = _TASK_NAME_MAP.get(raw_task, raw_task)
    blocks: list[NotificationBlock] = [
        TextBlock(text=_("任务：{t}").format(t=task_name)),
        TextBlock(text=_("错误：{e}").format(e=translate_error_message(data.get("error", "")))),
        TextBlock(text=_("系统将在下次调度时自动重试")),
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
