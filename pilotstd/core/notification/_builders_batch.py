# 模块：项目/核心//_构建器_脚本
# 通知消息构建器(批次/查询/下载)—原_，现为模块级纯函数
# 分隔
# 每个__*_()函数签名一致：接收→返回。
# 决策内聚在构建器内部（如>0→）。
# 设计原则：方法签名即文档，每个事件独立构建避免参数爆炸。
# 模板重写（批次2）：统一"标准号/名称/类型"行结构；错误经翻译映射；
# 标准号不再依赖发送层追加（telegram.py 去重），由构建器正文完整承载。

import os
from datetime import date, timedelta

from pilotstd.i18n import t

from ._format_utils import translate_error_message
from .blocks import (
    KeyValueBlock,
    ListBlock,
    NotificationBlock,
    TextBlock,
)
from .channel import NotificationMessage

# 标准类型 → i18n 键（favorite/download 模板共用）。
# 只存键、渲染时取 t()：模块级直接求值会把语言固化在 import 时刻，
# 运行时 set_language 后标准类型名不会跟着变。
_STD_TYPE_LABEL_KEYS = {
    "NationalStd": "notification.common.std_type.national",
    "IndustryStd": "notification.common.std_type.industry",
    "LocalStd": "notification.common.std_type.local",
}


def _std_type_text(standard_type: str) -> str:
    """标准类型标签（未知类型返回空串，模板中省略该行）。"""
    key = _STD_TYPE_LABEL_KEYS.get(standard_type or "")
    return t(key) if key else ""


def _expected_download_date(publish_date: str) -> str:
    """预计自动下载日期 = 发布日期 + 冷却期天数。

    冷却期与收藏下载链同源（ARCHIVE_COOLDOWN_DAYS 环境变量，默认 28），
    避免双源漂移；日期无法解析时返回空串（模板回退为通用提示）。
    """
    if not publish_date:
        return ""
    try:
        d = date.fromisoformat(str(publish_date)[:10])
        cooldown = int(os.environ.get("ARCHIVE_COOLDOWN_DAYS", "28"))
        return (d + timedelta(days=cooldown)).isoformat()
    except (ValueError, TypeError):
        return ""


def _make_link(standard_number: str | None) -> str | None:
    """根据标准号生成跳转链接（与 _builders_system 同款，避免跨模块依赖）。

    链接用于站内跳转到标准详情页；标准号为空时返回 None（消息不含跳转）。
    """
    return f"/standards/{standard_number}" if standard_number else None


def _build_announcement_fetch_complete_message(data: dict) -> NotificationMessage:
    """原 Mixin 方法，现为模块级纯函数。

    模板：来源单独成行 → "新增公告：N；其中国标：G，行标：H，地标：D"
    → 新增公告标题明细（有则逐行 "• {title}"）。
    """
    blocks: list[NotificationBlock] = []
    if data.get("source"):
        blocks.append(
            TextBlock(
                text=t("notification.announce.announcement_fetch_complete.body.source").format(s=data["source"])
            )
        )
    summary = t("notification.announce.announcement_fetch_complete.body.summary").format(
        n=data.get("count", 0),
        g=data.get("gb_count", 0),
        h=data.get("hb_count", 0),
        d=data.get("db_count", 0),
    )
    blocks.append(TextBlock(text=summary))
    announcements = data.get("announcements") or []
    titles = [a.get("title", "") for a in announcements if a.get("title")]
    if titles:
        # 明细仅在本次确有新增公告时出现（列表头 + 逐行 "• {title}"）
        blocks.append(
            TextBlock(text=t("notification.announce.announcement_fetch_complete.body.list_header"))
        )
        item_key = "notification.announce.announcement_fetch_complete.body.item"
        blocks.append(TextBlock(text="\n".join(t(item_key).format(t=tt) for tt in titles)))
    return NotificationMessage(
        title=t("notification.announce.announcement_fetch_complete.title"),
        blocks=blocks,
        level="info",
        event_type="announcement_fetch_complete",
        icon="pi pi-megaphone",
    )


def _build_batch_download_complete_message(data: dict) -> NotificationMessage:
    """批量下载完成（4 段式：标题 + 统计行，无明细）。"""
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
    return NotificationMessage(
        title=t(title_key),
        blocks=[TextBlock(text=stats)],
        level="info" if failed == 0 else "warning",
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
    blocks: list[NotificationBlock] = [
        TextBlock(text=t("notification.query.batch_query_summary.body.total").format(n=n))
    ]
    if results:
        items = [{"number": r["number"], "name": r.get("name", "")} for r in results]
        blocks.append(
            ListBlock(
                title=t("notification.query.batch_query_summary.body.list_header"),
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
        title=t("notification.query.batch_query_summary.title"),
        blocks=blocks,
        level=level,
        event_type="batch_query_summary",
        icon="pi pi-search",
    )


def _build_auto_scan_failed_message(data: dict) -> NotificationMessage:
    """原 Mixin 方法，现为模块级纯函数。"""
    blocks: list[NotificationBlock] = [
        TextBlock(text=t("notification.scan.auto_scan_failed.body.path").format(p=data.get("path", "")))
    ]
    if data.get("error"):
        blocks.append(TextBlock(text=t("notification.common.error").format(e=data["error"])))
    return NotificationMessage(
        title=t("notification.scan.auto_scan_failed.title"),
        blocks=blocks,
        level="error",
        event_type="auto_scan_failed",
        icon="pi pi-exclamation-triangle",
    )


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
    # 错误信息经翻译映射统一口径（C-3），避免技术细节直出
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


def _build_favorite_created_message(data: dict) -> NotificationMessage:
    """收藏成功事件构建器：告知用户收藏已建立并进入下载队列。

    收藏动作本身立即成功，但文件下载要等冷却期后由 cron 触发，
    故消息明确给出预计下载日期（publish_date + 冷却期），避免用户误判时效。
    """
    std_no = data.get("standard_no", "")
    std_name = data.get("standard_name", "")
    standard_type = data.get("standard_type", "")
    publish_date = data.get("publish_date", "")
    blocks: list[NotificationBlock] = []
    # 标准号与名称非空时才展示，避免消息中出现空字段占位
    if std_no:
        blocks.append(TextBlock(text=t("notification.common.std_no").format(s=std_no)))
    if std_name:
        blocks.append(TextBlock(text=t("notification.common.std_name").format(s=std_name)))
    std_type_text = _std_type_text(standard_type)
    if std_type_text:
        blocks.append(TextBlock(text=t("notification.common.std_type").format(t=std_type_text)))
    # 明确告知排队语义：给出预计下载日期（publish_date + 冷却期），
    # 日期不可得时回退通用提示，避免用户误判时效
    expected = _expected_download_date(publish_date)
    if expected:
        blocks.append(
            TextBlock(
                text=t("notification.download.favorite_created.body.queue_with_date").format(date=expected)
            )
        )
    else:
        blocks.append(TextBlock(text=t("notification.download.favorite_created.body.queue_generic")))
    return NotificationMessage(
        title=t("notification.download.favorite_created.title"),
        blocks=blocks,
        level="info",
        standard_number=std_no or None,
        event_type="favorite_created",
        link=_make_link(std_no) if std_no else None,
        icon="pi pi-star",
    )


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


def _build_archive_abandoned_message(data: dict) -> NotificationMessage:
    """归档任务放弃（与 archive_failed 语义区分：本事件指单条收藏下载重试 7 次
    后放弃，面向用户告知该收藏不再自动重试；archive_failed 指批量归档失败汇总）。"""
    blocks: list[NotificationBlock] = [
        TextBlock(
            text=t("notification.archive.archive_abandoned.body.std_info").format(
                s=data.get("standard_info", "")
            )
        ),
        TextBlock(
            text=t("notification.common.error").format(
                e=data.get("error", t("notification.common.unknown_error"))
            )
        ),
    ]
    return NotificationMessage(
        title=t("notification.archive.archive_abandoned.title"),
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
            text=t("notification.archive.normalize_complete.body.stats").format(
                total=total, success=success, failed=failed
            )
        ),
    ]
    return NotificationMessage(
        title=t("notification.archive.normalize_complete.title"),
        blocks=blocks,
        level="info",
        event_type="normalize_complete",
        icon="pi pi-check-square",
    )


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
