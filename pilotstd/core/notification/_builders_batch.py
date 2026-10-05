# 模块：项目/核心//_构建器_脚本
# 通知消息构建器(批次/查询/下载)—原_，现为模块级纯函数
# 分隔
# 每个__*_()函数签名一致：接收→返回。
# 决策内聚在构建器内部（如>0→）。
# 设计原则：方法签名即文档，每个事件独立构建避免参数爆炸。
# 模板重写（批次2）：统一"标准号/名称/类型"行结构；错误经翻译映射；
# 标准号不再依赖发送层追加（电报渠道去重），由构建器正文完整承载。

import os
from datetime import date, timedelta

from pilotstd.i18n import t

from ._format_utils import translate_error_message
from .blocks import (
    ListBlock,
    NotificationBlock,
    TextBlock,
)
from .channel import NotificationMessage

# 标准类型 → 多语言键（收藏/下载模板共用）。
# 只存键、渲染时再取翻译：模块级直接求值会把语言固化在导入时刻，
# 运行时切换语言后标准类型名不会跟着变。
_STD_TYPE_LABEL_KEYS = {
    "NationalStd": "notification.common.std_type.national",
    "IndustryStd": "notification.common.std_type.industry",
    "LocalStd": "notification.common.std_type.local",
}

# 收藏放弃的**类别 key → 文案键**。
# 分类在 `favorite_chain_processor._classify_abandon_reason` 里只产出 key（不写死中文），
# 语言在渲染时由此处决定；未知 key 原样回显，便于新类别上线前也能看出内容。
_ABANDON_REASON_KEYS = {
    "copyright": "notification.abandon_reason.copyright",
    "legacy_link": "notification.abandon_reason.legacy_link",
    "session_defect": "notification.abandon_reason.session_defect",
    "db_race": "notification.abandon_reason.db_race",
    "archive_timeout": "notification.abandon_reason.archive_timeout",
    "network": "notification.abandon_reason.network",
    "other": "notification.abandon_reason.other",
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


def _build_favorite_abandoned_summary_message(data: dict) -> NotificationMessage:
    """收藏告终汇总：**仅在实际发生放弃时**发送（P0 修复）。

    `abandoned` 是**终态**——调度只捡 `pending`/`failed`，故系统**永远不会再自动重试**。
    原先该状态被并进 `batch_download_complete` 的 `failed` 计数，用户看不出
    "哪些已经彻底放弃、需要人工介入"。本事件承担该告终语义。

    载荷：`total`（放弃总数）、`reasons`（原因分类 → 条数）、
    `retryable`（其中"重试有效"的条数，用于给出可执行建议）、`details`（示例明细）。
    """
    total = int(data.get("total", 0) or 0)
    reasons = data.get("reasons") or {}
    retryable = int(data.get("retryable", 0) or 0)
    details = [str(d) for d in (data.get("details") or []) if d][:5]

    blocks: list[NotificationBlock] = [
        TextBlock(
            text=t("notification.download.favorite_abandoned_summary.body.total").format(total=total)
        )
    ]

    # 原因分类：载荷里是**类别 key**（分类层不写死中文），此处翻译成文案再展示
    if reasons:
        items = [
            {
                "reason": t("notification.download.favorite_abandoned_summary.body.reason_label"),
                "count": t("notification.download.favorite_abandoned_summary.body.count_unit").format(
                    count=n
                ),
                "name": t(_ABANDON_REASON_KEYS[name]) if name in _ABANDON_REASON_KEYS else str(name),
            }
            for name, n in sorted(reasons.items(), key=lambda kv: -int(kv[1] or 0))[:5]
        ]
        blocks.append(
            ListBlock(
                title=t("notification.download.favorite_abandoned_summary.body.list_header"),
                items=items,
                total=len(reasons),
            )
        )

    # 操作建议：区分"重试有效"与"永久失败"，两者处置方式完全不同
    if retryable > 0:
        blocks.append(
            TextBlock(
                text=t("notification.download.favorite_abandoned_summary.body.advice_retryable").format(
                    retryable=retryable
                )
            )
        )
    else:
        blocks.append(
            TextBlock(
                text=t("notification.download.favorite_abandoned_summary.body.advice_permanent")
            )
        )

    if details:
        blocks.append(
            ListBlock(
                title=t("notification.download.favorite_abandoned_summary.body.detail_header"),
                items=[{"number": d} for d in details],
                total=total,
            )
        )

    return NotificationMessage(
        title=t("notification.download.favorite_abandoned_summary.title"),
        blocks=blocks,
        level="warning",
        event_type="favorite_abandoned_summary",
        icon="pi pi-exclamation-triangle",
    )


def _build_notification_delivery_failed_message(data: dict) -> NotificationMessage:
    """通知投递失败告警（P0）：**通知系统自身故障**时发出。

    这是"通知坏了没人知道"的唯一出口。载荷区分两种判据，因为处置方式不同：
    - `consecutive`：渠道**彻底不通**（连败）——通常 token 失效/网络断，需立即处理；
    - `rate`：渠道**在丢消息**（窗口失败率超阈）——通常是限流，可考虑降速或换渠道。

    `samples`/`failures` 给出统计依据，便于判断严重程度。
    """
    channel = str(data.get("channel", "") or "")
    reason = str(data.get("reason", "") or "")
    samples = int(data.get("samples", 0) or 0)
    failures = int(data.get("failures", 0) or 0)
    consecutive = int(data.get("consecutive", 0) or 0)

    if reason == "consecutive":
        body = t("notification.system.notification_delivery_failed.body.consecutive").format(
            channel=channel, consecutive=consecutive
        )
    else:
        percent = round(failures / samples * 100) if samples else 0
        body = t("notification.system.notification_delivery_failed.body.rate").format(
            channel=channel, failures=failures, samples=samples, percent=percent
        )

    blocks: list[NotificationBlock] = [
        TextBlock(text=body),
        TextBlock(text=t("notification.system.notification_delivery_failed.body.advice")),
    ]
    return NotificationMessage(
        title=t("notification.system.notification_delivery_failed.title").format(channel=channel),
        blocks=blocks,
        level="error",
        event_type="notification_delivery_failed",
        icon="pi pi-bell-slash",
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
    # 明确告知排队语义：给出预计下载日期（发布日期 + 冷却期），
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


# 失败明细的错误类型枚举 → i18n 键（**构建器侧先翻译再入块**）。
# 为什么在构建器侧翻译而不是渲染层：`error_type` 是**取值**（not_found/parse/…），
# 渲染层只负责把"字段名"翻译成列名（`renderer._LIST_FIELD_KEYS`）；取值不翻译就会把
# 内部枚举直接暴露给用户（渠道降级/G-040 场景同样要求中文可见文案）。
# 枚举口径（B1 裁定）：not_found / parse / network / timeout / unknown。
_ERROR_TYPE_KEYS: dict[str, str] = {
    "not_found": "notification.error_type.not_found",
    "parse": "notification.error_type.parse",
    "network": "notification.error_type.network",
    "timeout": "notification.error_type.timeout",
    "unknown": "notification.error_type.unknown",
}


def build_failed_items_block(data: dict) -> "ListBlock | None":
    """把 payload 的 `failed_items` 渲染为 `ListBlock`；无明细时返回 None（调用方不追加块）。

    · **不做行数截断**（`MAX_FAILED_ROWS` 作废，B1 裁定）：全部明细进同一块，
      超长交给渠道侧按"转义后字符数"分段；
    · 4 列口径固定：`standard_number` / `standard_name`（空 ⇒ `-`）/ `error_type`（枚举键 → 中文）/
      `error_message`（上游已截断 ≤120 字符，这里再兜一次）；
    · `total=len(items)` 让渲染层知道真实条数（`ListBlock.total` 语义见 blocks.py）。
    """
    items = data.get("failed_items") or []
    if not items:
        return None
    rows: list[dict[str, str]] = []
    for it in items:
        etype = str(it.get("error_type") or "unknown")
        rows.append(
            {
                "standard_number": str(it.get("standard_number") or "-"),
                "standard_name": str(it.get("standard_name") or "-"),
                "error_type": t(_ERROR_TYPE_KEYS.get(etype, "notification.error_type.unknown")),
                "error_message": str(it.get("error_message") or "-")[:120],
            }
        )
    return ListBlock(title=t("notification.failed_items.title"), items=rows, total=len(rows))


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
    # 2026-10-05 通知聚合 B1：失败明细（payload.failed_items）渲染为列表块。
    # 为什么在构建器而不是聚合器：构建器是"每条消息长什么样"的唯一出处；
    # 聚合器只负责把多条消息的 blocks **按到达序拼接**（Z-21），**不做行数截断**——
    # 超长由渠道侧按"转义后字符数"分段（见分段块）。
    failed_block = build_failed_items_block(data)
    if failed_block is not None:
        blocks.append(failed_block)
    return NotificationMessage(
        title=t("notification.archive.normalize_complete.title"),
        blocks=blocks,
        level="info",
        event_type="normalize_complete",
        icon="pi pi-check-square",
    )
