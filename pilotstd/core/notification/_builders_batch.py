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

from pilotstd.i18n import _

from ._format_utils import translate_error_message
from .blocks import (
    KeyValueBlock,
    ListBlock,
    NotificationBlock,
    TextBlock,
)
from .channel import NotificationMessage

# 标准类型 → 中文标签（favorite/download 模板共用）
_STD_TYPE_LABEL = {
    "NationalStd": _("国家标准"),
    "IndustryStd": _("行业标准"),
    "LocalStd": _("地方标准"),
}


def _std_type_text(standard_type: str) -> str:
    """标准类型标签（未知类型返回空串，模板中省略该行）。"""
    return _STD_TYPE_LABEL.get(standard_type or "", "")


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
        blocks.append(TextBlock(text=_("来源：{s}").format(s=data["source"])))
    summary = _("新增公告：{n}；其中国标：{g}，行标：{h}，地标：{d}").format(
        n=data.get("count", 0),
        g=data.get("gb_count", 0),
        h=data.get("hb_count", 0),
        d=data.get("db_count", 0),
    )
    blocks.append(TextBlock(text=summary))
    announcements = data.get("announcements") or []
    titles = [a.get("title", "") for a in announcements if a.get("title")]
    if titles:
        # 公告标题逐行展示（模板："• {title}"）
        blocks.append(TextBlock(text="\n".join(_("• {t}").format(t=t) for t in titles)))
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
    # 根据失败数决定消息级别：有失败→，否则
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
    std_no = data.get("standard_number", "")
    blocks: list[NotificationBlock] = []
    if std_no:
        blocks.append(TextBlock(text=_("标准号：{s}").format(s=std_no)))
    std_name = data.get("standard_name", "")
    if std_name:
        blocks.append(TextBlock(text=_("名称：{s}").format(s=std_name)))
    std_type_text = _std_type_text(data.get("standard_type", ""))
    if std_type_text:
        blocks.append(TextBlock(text=_("类型：{t}").format(t=std_type_text)))
    # 错误信息经翻译映射统一口径（C-3），避免技术细节直出
    blocks.append(TextBlock(text=_("错误：{e}").format(e=translate_error_message(data.get("error", "")))))
    return NotificationMessage(
        title=_("收藏下载失败"),
        blocks=blocks,
        level="error",
        event_type="download_failed",
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
        blocks.append(TextBlock(text=_("标准号：{s}").format(s=std_no)))
    if std_name:
        blocks.append(TextBlock(text=_("名称：{s}").format(s=std_name)))
    std_type_text = _std_type_text(standard_type)
    if std_type_text:
        blocks.append(TextBlock(text=_("类型：{t}").format(t=std_type_text)))
    # 明确告知排队语义：给出预计下载日期（publish_date + 冷却期），
    # 日期不可得时回退通用提示，避免用户误判时效
    expected = _expected_download_date(publish_date)
    if expected:
        blocks.append(TextBlock(text=_("已加入下载队列，预计 {date} 自动下载归档").format(date=expected)))
    else:
        blocks.append(TextBlock(text=_("已加入下载队列，冷却期过后自动下载归档")))
    return NotificationMessage(
        title=_("收藏成功"),
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
    blocks: list[NotificationBlock] = [TextBlock(text=_("标准号：{s}").format(s=std_no))]
    # 下载开始仅告知执行阶段，不承诺成功结果（成败由完成/失败事件分别表达）
    return NotificationMessage(
        title=_("开始下载"),
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
        blocks.append(TextBlock(text=_("标准号：{s}").format(s=std_no)))
    std_name = data.get("standard_name", "")
    if std_name:
        blocks.append(TextBlock(text=_("名称：{s}").format(s=std_name)))
    std_type_text = _std_type_text(data.get("standard_type", ""))
    if std_type_text:
        blocks.append(TextBlock(text=_("类型：{t}").format(t=std_type_text)))
    # 文件已归档到标准库，附上实际路径便于用户直接定位
    if local_path:
        blocks.append(TextBlock(text=_("文件位置：{p}").format(p=local_path)))
    return NotificationMessage(
        title=_("下载归档完成"),
        blocks=blocks,
        level="info",
        standard_number=std_no or None,
        event_type="download_complete",
        link=_make_link(std_no) if std_no else None,
        icon="pi pi-check-circle",
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
    """原 Mixin 方法，现为模块级纯函数。

    模板：已扫描：N 个文件，成功：S 个，失败：F 个；有失败明细时
    追加"失败文件："节（• 路径 — 原因）。
    """
    total = data.get("total", 0)
    success = data.get("success", data.get("count", 0))
    failed = data.get("failed", 0)
    blocks: list[NotificationBlock] = [
        TextBlock(text=_("已扫描：{t} 个文件，成功：{s} 个，失败：{f} 个").format(t=total, s=success, f=failed)),
    ]
    failed_files = data.get("failed_files") or []
    if failed_files:
        # 失败文件逐行展示（模板："• {path} — {reason}"）
        blocks.append(TextBlock(text=_("失败文件：")))
        lines = [
            _("• {path} — {reason}").format(
                path=ff.get("path", ""), reason=ff.get("reason") or _("未知原因")
            )
            for ff in failed_files
            if ff.get("path")
        ]
        if lines:
            blocks.append(TextBlock(text="\n".join(lines)))
    return NotificationMessage(
        title=_("扫描完成"),
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
