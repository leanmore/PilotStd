# 模块：项目/核心//_构建器_脚本
# 通知消息构建器(系统/备份/错误)—原_，现为模块级纯函数
# 分隔
# 覆盖事件：归档完成、自动备份、公告检查、镜像更新、可信、异常、
# 任务失败、公告抓取失败、配额耗尽。每个构建器独立返回。

import logging

from pilotstd.i18n import t

from ._format_utils import translate_error_message
from .blocks import (
    KeyValueBlock,
    NotificationBlock,
    TextBlock,
)
from .channel import NotificationMessage

# ── 安全族构建器（实现在 `_builders_system_security.py`；T-41/5 (2/2) 拆分，此处**再导出**）──
# `__all__` 必须收录再导出名：否则 `ruff --fix` 会按「未使用」删除它们（已两次实测）。
__all__ = [
    "_TASK_NAME_KEY_MAP",
    "_build_announcement_check_complete_message",
    "_build_announcement_fetch_failed_message",
    "_build_archive_complete_message",
    "_build_auto_backup_message",
    "_build_desktop_toast_message",
    "_build_fallback_message",
    "_build_image_update_available_message",
    "_build_quota_exhausted_message",
    "_build_task_execution_failed_message",
    "_build_trust_ip_update_message",
    "_build_worker_error_message",
    "_make_link",
    "_build_notification_credential_changed_message",
    "_build_security_password_changed_message",
    "_build_security_token_refreshed_message",
    "_build_security_login_failed_message",
]

from ._builders_system_security import (  # noqa: E402
    _build_notification_credential_changed_message,
    _build_security_login_failed_message,
    _build_security_password_changed_message,
    _build_security_token_refreshed_message,
)

logger = logging.getLogger(__name__)

# 定时任务标识 → 多语言键（任务执行失败模板）。
# 只存键、渲染时再取翻译：模块级直接求值会把语言固化在导入时刻，
# 运行时切换语言后任务名不会跟着变。
_TASK_NAME_KEY_MAP = {
    "auto_announce": "notification.system.task_execution_failed.task.auto_announce",
    "auto_scan": "notification.system.task_execution_failed.task.auto_scan",
    "auto_backup": "notification.system.task_execution_failed.task.auto_backup",
    "auto_archive_retry": "notification.system.task_execution_failed.task.auto_archive_retry",
    "auto_health_check": "notification.system.task_execution_failed.task.auto_health_check",
    "date_reminder": "notification.system.task_execution_failed.task.date_reminder",
    "validity_check": "notification.system.task_execution_failed.task.validity_check",
    "notification_cleanup": "notification.system.task_execution_failed.task.notification_cleanup",
    "release_suppressed": "notification.system.task_execution_failed.task.release_suppressed",
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
    blocks: list[NotificationBlock] = [
        TextBlock(text=t("notification.archive.archive_complete.body.count").format(n=count))
    ]
    # 分类统计（发送点已用标准代号分类聚合，标签即中文分类名）
    category_stats = data.get("category_stats") or {}
    if category_stats:
        summary = "，".join(
            t("notification.archive.archive_complete.body.category_item").format(label=k, n=v)
            for k, v in category_stats.items()
        )
        blocks.append(TextBlock(text=summary))
    # 归档目录逐行（发送点从归档整理明细提取的目标目录）
    directories = data.get("directories") or []
    if directories:
        blocks.append(TextBlock(text=t("notification.archive.archive_complete.body.dir_header")))
        blocks.append(
            TextBlock(
                text="\n".join(
                    t("notification.archive.archive_complete.body.dir_item").format(d=d) for d in directories
                )
            )
        )
    # 2026-10-05 通知聚合 B1：失败明细渲染为列表块（与 normalize_complete 共用同一实现，
    # 保证两处口径一致：4 列、空值填 '-'、枚举取值先翻译、**不做行数截断**）。
    from ._builders_batch import build_failed_items_block

    failed_block = build_failed_items_block(data)
    if failed_block is not None:
        blocks.append(failed_block)
    return NotificationMessage(
        title=t("notification.archive.archive_complete.title"),
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
    """自动备份结果（4 段式：标题 + 元数据行（路径/大小）或错误行）。"""
    success = data.get("success", False)
    path = data.get("backup_path", "")
    size = data.get("size_mb", "")
    if success:
        blocks: list[NotificationBlock] = [
            KeyValueBlock(key=t("notification.system.auto_backup.body.path"), value=path),
            KeyValueBlock(key=t("notification.system.auto_backup.body.size"), value=size),
        ]
        return NotificationMessage(
            title=t("notification.system.auto_backup.title.success"),
            blocks=blocks,
            level="info",
            event_type="auto_backup",
            icon="pi pi-database",
        )
    blocks = [
        TextBlock(
            text=t("notification.system.auto_backup.body.error").format(
                err=data.get("error", t("notification.common.unknown_error"))
            )
        )
    ]
    return NotificationMessage(
        title=t("notification.system.auto_backup.title.failed"),
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
        blocks.append(TextBlock(text=t("notification.announce.announcement_check_complete.body.source").format(s=source)))
    summary = t("notification.announce.announcement_check_complete.body.summary").format(
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
        title=t("notification.announce.announcement_check_complete.title"),
        blocks=blocks,
        level=level,
        event_type="announcement_check_complete",
        icon="pi pi-check-circle",
    )


def _build_fallback_message(event_type: str, data: dict) -> NotificationMessage:
    """兜底构建器：未知事件类型（正常不触发，防御性）。"""
    blocks: list[NotificationBlock] = [
        TextBlock(text=t("notification.fallback.body.event_type").format(t=data.get("event_type", "unknown")))
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
        blocks: list[NotificationBlock] = [
            TextBlock(
                text=t("notification.system.image_update_available.body.error").format(e=data["error"])
            )
        ]
        return NotificationMessage(
            title=t("notification.system.image_update_available.title.error"),
            blocks=blocks,
            level="error",
            event_type="image_update_available",
            icon="pi pi-cloud-upload",
        )
    # 正常路径：上面错误分支已提前返回，此处安全重建 blocks
    # 模板：镜像版本：旧版 → 新版；版本号缺失时回退取镜像摘要前 12 位
    # （变量名用"消息块"避开错误分支的"块"变量，消除类型检查的重复定义告警）
    old_digest = data.get("old_digest", "")
    new_digest = data.get("new_digest", "")
    old_ver = data.get("old_version") or (old_digest[:12] if old_digest else "")
    new_ver = data.get("new_version") or (new_digest[:12] if new_digest else "")
    message_blocks: list[NotificationBlock] = [
        TextBlock(text=t("notification.system.image_update_available.body.version").format(old=old_ver, new=new_ver)),
    ]
    if not old_digest or not new_digest:
        logger.debug("image_update_available: old_digest or new_digest is empty")
    if data.get("release_notes"):
        message_blocks.append(
            TextBlock(
                text=t("notification.system.image_update_available.body.notes").format(n=data["release_notes"])
            )
        )
    return NotificationMessage(
        title=t("notification.system.image_update_available.title"),
        blocks=message_blocks,
        level="info",
        event_type="image_update_available",
        icon="pi pi-cloud-upload",
    )


def _build_trust_ip_update_message(data: dict) -> NotificationMessage:
    """可信 IP 更新状态（外部 title/body 直出，格式由发送方控制；P2 残留）。"""
    title = data.get("title", t("notification.system.trust_ip_update.title.default"))
    text = data.get("body", "")
    blocks: list[NotificationBlock] = [TextBlock(text=text)]
    extra_keys = [k for k in ("ip", "update_time", "status") if data.get(k)]
    # 有额外键值对信息时追加
    for k in extra_keys:
        blocks.append(KeyValueBlock(key=k, value=str(data[k])))
    # 级别按**机器可读**结果判定（T-39）：标题是展示文案，改文案不得改变通知级别
    level = "warning" if data.get("status", "") == "failed" else "info"
    return NotificationMessage(
        title=title,
        blocks=blocks,
        level=level,
        event_type="trust_ip_update",
        icon="pi pi-shield",
    )


def _build_worker_error_message(data: dict) -> NotificationMessage:
    """原 Mixin 方法，现为模块级纯函数。"""
    worker = data.get("worker", t("notification.common.unknown_worker"))
    error = data.get("error", "")
    blocks: list[NotificationBlock] = [
        TextBlock(text=t("notification.system.worker_error.body.worker").format(worker=worker)),
    ]
    if error:
        blocks.append(TextBlock(text=t("notification.common.error").format(e=error)))
    if data.get("traceback"):
        blocks.append(TextBlock(text=data["traceback"]))
    return NotificationMessage(
        title=t("notification.system.worker_error.title"),
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
    raw_task = data.get("task_name", t("notification.common.unknown_task"))
    key = _TASK_NAME_KEY_MAP.get(raw_task)
    task_name = t(key) if key else raw_task
    blocks: list[NotificationBlock] = [
        TextBlock(text=t("notification.system.task_execution_failed.body.task").format(t=task_name)),
        TextBlock(text=t("notification.common.error").format(e=translate_error_message(data.get("error", "")))),
        TextBlock(text=t("notification.system.task_execution_failed.body.retry")),
    ]
    return NotificationMessage(
        title=t("notification.system.task_execution_failed.title"),
        blocks=blocks,
        level="error",
        event_type="task_execution_failed",
        icon="pi pi-clock",
    )


def _build_announcement_fetch_failed_message(data: dict) -> NotificationMessage:
    """原 Mixin 方法，现为模块级纯函数。"""
    source = data.get("source", t("notification.common.unknown_source"))
    error = data.get("error", t("notification.common.unknown_error"))
    return NotificationMessage(
        title=t("notification.announce.announcement_fetch_failed.title"),
        blocks=[
            TextBlock(
                text=t("notification.announce.announcement_fetch_failed.body").format(source=source, error=error)
            )
        ],
        level="error",
        event_type="announcement_fetch_failed",
        icon="pi pi-megaphone",
    )


def _build_quota_exhausted_message(data: dict) -> NotificationMessage:
    """原 Mixin 方法，现为模块级纯函数。"""
    site_name = data.get("site_name", t("notification.common.unknown_site"))
    quota_limit = data.get("quota_limit", "0")
    reset_time = data.get("reset_time", t("notification.common.tomorrow_midnight"))
    return NotificationMessage(
        title=t("notification.system.quota_exhausted.title"),
        blocks=[
            TextBlock(
                text=t("notification.system.quota_exhausted.body").format(
                    site_name=site_name, quota_limit=quota_limit, reset_time=reset_time
                )
            )
        ],
        level="warning",
        event_type="quota_exhausted",
        icon="pi pi-exclamation-triangle",
    )


# ── 安全告警（第 2 批：安全与审计闭环）───────────────────────────────
# 这三个事件的投递不走 NotificationManager.send_event（聚合/静音会把凭证变更
# 告警推迟到新凭证落库之后），由 security_notifier 直连旧渠道同步发送。
# 构建器仍按统一契约产出 NotificationMessage，故载荷字段与调用方严格对齐。










def _build_desktop_toast_message(data: dict) -> NotificationMessage:
    """平台层：桌面弹层回显（阶段 4 · P6 · 4c 登记 `desktop_toast`）。

    **为什么单独有构建器**：登记前该事件"标题继承上游事件、无独立构建器与 i18n 键"，
    G-045 只能靠覆盖摘要显式声明"未覆盖"；正式登记后它必须与其它事件同规格（i18n 三语 + 构建器 + 触发文件）。

    **输入口径**：L2 桌面协调层直构消息（**不经 `send_event`**），故 `payload_keys` 为空集；
    但为了可测与可复用，这里按"事件数据字典"实现：优先取 `title` / `content`（L2 的实际字段名），
    缺失时回退 i18n 文案；`level` 决定严重度（默认 `info`）。**不静默吞空**（G-046）：
    `title` 与 `content` 都缺时给出兜底文案，而不是产出空标题。
    """
    # **空值守卫必须在"读取表达式本身"上**（G-046 的 [P2] missing_null_guard 是 AST 静态判定：
    # 只认 `data.get("f", DEFAULT)` / `data.get("f") or ...` / 直接 `str(data.get("f") ...)` 等形态；
    # 先赋值给局部变量再 `if not 变量:` **不被认作**守卫）。故此处与既有构建器同款三重保护。
    title = str(data.get("title", "") or "")
    if not title:
        title = t("notification.system.desktop_toast.title")
    content = str(data.get("content", "") or "")
    if not content:
        content = t("notification.system.desktop_toast.body")
    level = str(data.get("level", "") or "") or "info"
    blocks: list[NotificationBlock] = [TextBlock(text=content)]
    return NotificationMessage(
        title=title,
        blocks=blocks,
        level=level,
        event_type="desktop_toast",
        icon="pi pi-bell",
    )
