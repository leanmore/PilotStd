"""下载/批量下载族事件构建器（T-41/5 从 `_builders_batch.py` 拆出，守 G-010）。

**职责**：`batch_download_complete` / `download_failed` / `download_started` / `download_complete`
四条事件的构建器。**依赖**：共享助手 `_builders_common`（单向，无环）。
"""

from __future__ import annotations

from pilotstd.i18n import t

from ._builders_common import _make_link, _std_type_text
from ._format_utils import translate_error_message
from .blocks import (
    NotificationBlock,
    TextBlock,
)
from .channel import NotificationMessage


# 批量下载收尾汇总：成功/失败/跳过三计数 + 前 5 条非成功明细（信息不丢，又不至于长消息）。
def _build_batch_download_complete_message(data: dict) -> NotificationMessage:
    """批量下载完成（标题 + 统计行 + 可选明细预览）。

    details：非成功项明细（收藏链运行汇总传入），最多展示 5 条 —— 汇总只有计数时
    用户无法知道"哪条失败了"，明细是这批通知里唯一可执行的信息。
    """
    success = data.get("success", 0)
    failed = data.get("failed", 0)
    skipped = data.get("skipped", 0)
    stats = t("notification.download.batch_download_complete.body.stats").format(
        success=success, failed=failed, skipped=skipped
    )
    title_key = (
        "notification.download.batch_download_complete.title.success"
        if failed == 0
        else "notification.download.batch_download_complete.title.with_failure"
    )
    blocks: list[NotificationBlock] = [TextBlock(text=stats)]
    details = [str(d) for d in (data.get("details") or []) if d][:5]
    if details:
        blocks.append(TextBlock(text="\n".join(details)))
    return NotificationMessage(
        title=t(title_key),
        blocks=blocks,
        level="info" if failed == 0 else "warning",
        event_type="batch_download_complete",
        icon="pi pi-download",
    )


# 单条下载失败：带标准号与错误（错误经 `translate_error_message` 归一，便于用户按提示处理）。
def _build_download_failed_message(data: dict) -> NotificationMessage:
    """原 Mixin 方法，现为模块级纯函数。"""
    std_no = data.get("standard_number", "")
    blocks: list[NotificationBlock] = []
    if std_no:
        blocks.append(TextBlock(text=t("notification.common.std_no").format(s=std_no)))
    std_name = data.get("standard_name", "")
    if std_name:
        blocks.append(TextBlock(text=t("notification.common.std_name").format(s=std_name)))
    std_type_text = _std_type_text(data.get("standard_type", ""))
    if std_type_text:
        blocks.append(TextBlock(text=t("notification.common.std_type").format(t=std_type_text)))
    # 错误信息经翻译映射统一口径（业务消息映射），避免技术细节直出
    blocks.append(
        TextBlock(text=t("notification.common.error").format(e=translate_error_message(data.get("error", ""))))
    )
    return NotificationMessage(
        title=t("notification.download.download_failed.title"),
        blocks=blocks,
        level="error",
        standard_number=std_no or None,
        event_type="download_failed",
        link=_make_link(std_no) if std_no else None,
        icon="pi pi-download",
    )


# 下载开始：给用户「流程已启动」的即时反馈（含预期下载日期）。
def _build_download_started_message(data: dict) -> NotificationMessage:
    """下载开始事件构建器：告知用户标准文件开始自动下载。

    cron 处理器扫描到待下载收藏并调用 download_to_inbox 时触发，
    表明下载流程已进入执行阶段（区别于收藏时的排队阶段）。
    """
    std_no = data.get("standard_number", "")
    blocks: list[NotificationBlock] = [TextBlock(text=t("notification.common.std_no").format(s=std_no))]
    # 下载开始仅告知执行阶段，不承诺成功结果（成败由完成/失败事件分别表达）
    return NotificationMessage(
        title=t("notification.download.download_started.title"),
        blocks=blocks,
        level="info",
        standard_number=std_no or None,
        event_type="download_started",
        link=_make_link(std_no) if std_no else None,
        icon="pi pi-download",
    )


# 单条下载完成：附落库路径与标准信息，便于用户直接定位文件。
def _build_download_complete_message(data: dict) -> NotificationMessage:
    """下载完成事件构建器：告知用户标准文件已下载并归档。

    文件落盘并进入标准库 file_index 后触发；local_path 为归档后
    的实际存储路径，便于用户直接定位文件。
    """
    std_no = data.get("standard_number", "")
    local_path = data.get("local_path", "")
    blocks: list[NotificationBlock] = []
    if std_no:
        blocks.append(TextBlock(text=t("notification.common.std_no").format(s=std_no)))
    std_name = data.get("standard_name", "")
    if std_name:
        blocks.append(TextBlock(text=t("notification.common.std_name").format(s=std_name)))
    std_type_text = _std_type_text(data.get("standard_type", ""))
    if std_type_text:
        blocks.append(TextBlock(text=t("notification.common.std_type").format(t=std_type_text)))
    # 文件已归档到标准库，附上实际路径便于用户直接定位
    if local_path:
        blocks.append(TextBlock(text=t("notification.download.download_complete.body.file_path").format(p=local_path)))
    return NotificationMessage(
        title=t("notification.download.download_complete.title"),
        blocks=blocks,
        level="info",
        standard_number=std_no or None,
        event_type="download_complete",
        link=_make_link(std_no) if std_no else None,
        icon="pi pi-check-circle",
    )
