# 模块：项目/核心//_构建器_脚本
# 通知消息构建器(有效性检查)—原_，现为模块级纯函数

from pilotstd.i18n import t

from ._format_utils import translate_error_message
from .blocks import (
    ListBlock,
    NotificationBlock,
    StatusChangeBlock,
    TextBlock,
)
from .channel import NotificationMessage


def _make_link(standard_number: str | None) -> str | None:
    """根据标准号生成跳转链接。"""
    return f"/standards/{standard_number}" if standard_number else None


def _build_standard_status_changed_message(data: dict) -> NotificationMessage:
    """原 Mixin 方法，现为模块级纯函数。

    Step 1（v1.1）：standard_expired 已合并入本事件——is_expired=True 时
    沿用原"标准已废止"模板语义（error 级别 + 变更时间行），替代原独立事件。
    """
    std_no = data.get("standard_number", "")
    old_status = data.get("old_status", "")
    new_status = data.get("new_status", "")
    is_expired = data.get("is_expired", False)
    blocks: list[NotificationBlock] = [
        StatusChangeBlock(label=std_no, old_value=old_status, new_value=new_status)
    ]
    # 废止类通知用级别+红色图标，强调紧急性；并保留原 standard_expired 的变更时间行
    if is_expired:
        title = t("notification.validity.standard_status_changed.title.expired")
        level = "error"
        icon = "pi pi-times-circle"
        if data.get("changed_at"):
            blocks.append(TextBlock(text=t("notification.common.changed_at").format(t=data["changed_at"])))
    else:
        title = t("notification.validity.standard_status_changed.title.normal")
        # 新状态为"已废止"时降级为，否则
        level = "warning" if new_status == t("notification.common.abolished") else "info"
        icon = "pi pi-refresh"
    return NotificationMessage(
        title=title,
        blocks=blocks,
        level=level,
        standard_number=std_no,
        event_type="standard_status_changed",
        link=_make_link(std_no),
        icon=icon,
        changed_at=data.get("changed_at", ""),
    )


def _build_standard_first_registered_message(data: dict) -> NotificationMessage:
    """原 Mixin 方法，现为模块级纯函数。"""
    standards = data.get("standards", [])
    # 兼容旧版单条调用：无列表时用_/构造
    if not standards:
        std_no = data.get("standard_number", "")
        name = data.get("name", "")
        if std_no:
            standards = [{"number": std_no, "name": name}]
    n = len(standards)
    blocks: list[NotificationBlock] = [
        TextBlock(text=t("notification.validity.standard_first_registered.body.count").format(n=n))
    ]
    if standards:
        blocks.append(
            ListBlock(
                title=t("notification.validity.standard_first_registered.body.list_header"),
                items=[{"number": s["number"], "name": s.get("name", "")} for s in standards],
                total=n,
                detail_url=data.get("detail_url"),
            )
        )
    if data.get("elapsed_ms"):
        blocks.append(
            TextBlock(
                text=t("notification.validity.standard_first_registered.body.elapsed").format(ms=data["elapsed_ms"])
            )
        )
    return NotificationMessage(
        title=t("notification.validity.standard_first_registered.title"),
        blocks=blocks,
        level="info",
        standard_number=data.get("standard_number"),
        event_type="standard_first_registered",
        link=_make_link(data.get("standard_number")),
        icon="pi pi-star",
    )


# __和_查询_保留函数定义但不再注册到__用户界面
# 原因：定时任务由新版通知管道处理后，不再通过旧版构建器生成桌面

# ── 批量检查/公告事件 ──


def _build_validity_batch_report_message(data: dict) -> NotificationMessage:
    """原 Mixin 方法，现为模块级纯函数。

    模板：检查总数 → 变更/失败统计 → 变更详情 → 失败详情（逐行 "• 标准号 名称 — 原因"）。
    适配器状态行按 I-01 结论暂不展示（正确数据源为 adapter_mgr.get_all_status()，
    键名 adapter_status，模板不含该行）。
    """
    count = data.get("count", 0)
    changed = data.get("changed", 0)
    failed = data.get("failed", 0)
    # 中间进度通知：无实际数据时不显示统计
    if count == 0 and changed == 0 and failed == 0:
        return NotificationMessage(
            title=t("notification.validity.validity_batch_report.title.start"),
            blocks=[TextBlock(text=t("notification.validity.validity_batch_report.body.start"))],
            level="info",
            event_type="validity_batch_report",
            icon="pi pi-chart-bar",
        )
    blocks: list[NotificationBlock] = [
        TextBlock(text=t("notification.validity.validity_batch_report.body.total").format(n=count)),
        TextBlock(
            text=t("notification.validity.validity_batch_report.body.changed_failed").format(c=changed, f=failed)
        ),
    ]
    change_detail = data.get("change_detail") or []
    if change_detail:
        blocks.append(TextBlock(text=t("notification.validity.validity_batch_report.body.change_header")))
        lines = []
        for cd in change_detail:
            line = cd.get("standard", "")
            name = cd.get("name", "")
            if name:
                line += f" {name}"
            reason = cd.get("reason", "")
            if reason:
                line += t("notification.validity.validity_batch_report.body.change_reason").format(r=reason)
            lines.append(t("notification.validity.validity_batch_report.body.item").format(s=line))
        blocks.append(TextBlock(text="\n".join(lines)))
    failed_detail = data.get("failed_detail") or []
    if failed_detail:
        blocks.append(TextBlock(text=t("notification.validity.validity_batch_report.body.failed_header")))
        lines = []
        for fd in failed_detail:
            line = fd.get("standard", "")
            name = fd.get("name", "")
            if name:
                line += f" {name}"
            error = (fd.get("error") or "")[:100]
            if error:
                line += t("notification.validity.validity_batch_report.body.failed_error").format(e=error)
            lines.append(t("notification.validity.validity_batch_report.body.item").format(s=line))
        blocks.append(TextBlock(text="\n".join(lines)))
    # 有变更或失败时升级为
    level = "warning" if (changed > 0 or failed > 0) else "info"
    return NotificationMessage(
        title=t("notification.validity.validity_batch_report.title"),
        blocks=blocks,
        level=level,
        event_type="validity_batch_report",
        icon="pi pi-chart-bar",
    )


def _build_validity_round_summary_message(data: dict) -> NotificationMessage:
    """轮次汇总（4 段式：标题 + 统计行（，分隔）+ 变更明细（≤5 条截断））。"""
    round_num = data.get("round", 0)
    total_checks = data.get("total_checks", 0)
    total_changes = data.get("total_changes", 0)
    total_failures = data.get("total_failures", 0)
    change_list = data.get("change_list", [])
    stats = "，".join(
        [
            "{}：{}".format(t("notification.validity.validity_round_summary.body.round"), round_num),
            "{}：{}".format(t("notification.validity.validity_round_summary.body.total_checks"), total_checks),
            "{}：{}".format(t("notification.validity.validity_round_summary.body.total_changes"), total_changes),
            "{}：{}".format(t("notification.validity.validity_round_summary.body.total_failures"), total_failures),
        ]
    )
    blocks: list[NotificationBlock] = [TextBlock(text=stats)]
    if change_list:
        # 4 段式明细截断：最多展示 5 条，total 保留全量计数
        items = [{"detail": c} for c in change_list[:5]]
        blocks.append(
            ListBlock(
                title=t("notification.validity.validity_round_summary.body.list_header"),
                items=items,
                total=total_changes,
            )
        )
    title = t("notification.validity.validity_round_summary.title").format(round=round_num)
    return NotificationMessage(
        title=title,
        blocks=blocks,
        level="info",
        event_type="validity_round_summary",
        icon="pi pi-list",
    )


def _build_validity_standard_failed_message(data: dict) -> NotificationMessage:
    """原 Mixin 方法，现为模块级纯函数。"""
    std_no = data.get("standard_number", "")
    blocks: list[NotificationBlock] = [TextBlock(text=t("notification.common.std_no").format(s=std_no))]
    if data.get("error"):
        blocks.append(TextBlock(text=t("notification.common.error").format(e=data["error"])))
    return NotificationMessage(
        title=t("notification.validity.validity_standard_failed.title"),
        blocks=blocks,
        level="error",
        standard_number=std_no,
        event_type="validity_standard_failed",
        link=_make_link(std_no),
        icon="pi pi-exclamation-circle",
    )


def _build_validity_system_failed_message(data: dict) -> NotificationMessage:
    """有效性检查系统级失败（P1 修复：字段错位 + 异常直出）。

    仅展示翻译后的用户可读错误；详细堆栈由发送点写入系统日志，
    构建器不记录日志、不渲染 traceback（单一职责）。
    """
    friendly_error = translate_error_message(data.get("error", ""))
    blocks: list[NotificationBlock] = [
        TextBlock(text=t("notification.common.error").format(e=friendly_error)),
        TextBlock(text=t("notification.validity.validity_system_failed.body.hint")),
    ]
    return NotificationMessage(
        title=t("notification.validity.validity_system_failed.title"),
        blocks=blocks,
        level="error",
        event_type="validity_system_failed",
        icon="pi pi-times",
    )
