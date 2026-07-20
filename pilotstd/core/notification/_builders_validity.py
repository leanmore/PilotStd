# pilotstd/core/notification/_builders_validity.py
# 通知消息构建器混入(有效性检查) — 从 _message_builders.py 提取

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


class _ValidityBuildersMixin:
    """有效性检查消息构建方法集合。"""

    def _build_standard_status_changed_message(self, data: dict) -> NotificationMessage:
        std_no = data.get("standard_number", "")
        old_status = data.get("old_status", "")
        new_status = data.get("new_status", "")
        is_expired = data.get("is_expired", False)
        blocks: list[NotificationBlock] = [StatusChangeBlock(label=std_no, old_value=old_status, new_value=new_status)]
        # 废止类通知用 error 级别 + 红色图标，强调紧急性
        if is_expired:
            title = _("[废止] 标准已废止")
            level = "error"
            icon = "pi pi-times-circle"
        else:
            title = _("标准状态变更")
            # 新状态为"已废止"时降级为 warning，否则 info
            level = "warning" if new_status == _("已废止") else "info"
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

    def _build_standard_expired_message(self, data: dict) -> NotificationMessage:
        """构建标准已废止的通知消息。"""
        std_no = data.get("standard_number", "")
        blocks: list[NotificationBlock] = [
            StatusChangeBlock(
                label=std_no,
                old_value=data.get("old_status", ""),
                new_value=_("已废止"),
            )
        ]
        if data.get("changed_at"):
            blocks.append(TextBlock(text=_("变更时间：{t}").format(t=data["changed_at"])))
        return NotificationMessage(
            title=_("标准已废止"),
            blocks=blocks,
            level="error",
            standard_number=std_no,
            event_type="standard_expired",
            link=_make_link(std_no),
            icon="pi pi-times-circle",
        )

    def _build_standard_first_registered_message(self, data: dict) -> NotificationMessage:
        """构建新标准首次登记的通知消息。"""
        standards = data.get("standards", [])
        # 兼容旧版单条调用：无 standards 列表时用 standard_number/name 构造
        if not standards:
            std_no = data.get("standard_number", "")
            name = data.get("name", "")
            if std_no:
                standards = [{"number": std_no, "name": name}]
        n = len(standards)
        blocks: list[NotificationBlock] = [TextBlock(text=_("共 {n} 条标准完成首次登记").format(n=n))]
        if standards:
            blocks.append(
                ListBlock(
                    title=_("登记标准清单"),
                    items=[{"number": s["number"], "name": s.get("name", "")} for s in standards],
                    total=n,
                    detail_url=data.get("detail_url"),
                )
            )
        if data.get("elapsed_ms"):
            blocks.append(TextBlock(text=_("窗口耗时：{ms}ms").format(ms=data["elapsed_ms"])))
        return NotificationMessage(
            title=_("新标准首次登记"),
            blocks=blocks,
            level="info",
            standard_number=data.get("standard_number"),
            event_type="standard_first_registered",
            link=_make_link(data.get("standard_number")),
            icon="pi pi-star",
        )

    # check_batch_complete 和 auto_query_complete 保留函数定义但不再注册到 _EVENT_BUILDERS
    # 原因：定时任务由新版通知管道处理后，不再通过旧版构建器生成桌面 toast

    # ── 批量检查/公告事件 ──

    def _build_validity_batch_report_message(self, data: dict) -> NotificationMessage:
        count = data.get("count", 0)
        changed = data.get("changed", 0)
        failed = data.get("failed", 0)
        # 中间进度通知：无实际数据时不显示统计
        if count == 0 and changed == 0 and failed == 0:
            return NotificationMessage(
                title=_("开始有效性检查"),
                blocks=[TextBlock(text=_("开始有效性检查"))],
                level="info",
                event_type="validity_batch_report",
                icon="pi pi-chart-bar",
            )
        blocks: list[NotificationBlock] = [
            KeyValueBlock(key=_("检查总数"), value=str(count)),
            KeyValueBlock(key=_("变更数"), value=str(changed)),
            KeyValueBlock(key=_("失败数"), value=str(failed)),
        ]
        if data.get("adapter_status"):
            blocks.append(TextBlock(text=_("适配器状态：{s}").format(s=data["adapter_status"])))
        # 有变更或失败时升级为 warning
        level = "warning" if (changed > 0 or failed > 0) else "info"
        return NotificationMessage(
            title=_("有效性批量报告"),
            blocks=blocks,
            level=level,
            event_type="validity_batch_report",
            icon="pi pi-chart-bar",
        )

    def _build_validity_round_summary_message(self, data: dict) -> NotificationMessage:
        """构建有效性轮次汇总——统计数据 + 可选变更明细列表。"""
        round_num = data.get("round", 0)
        total_checks = data.get("total_checks", 0)
        total_changes = data.get("total_changes", 0)
        total_failures = data.get("total_failures", 0)
        change_list = data.get("change_list", [])
        blocks: list[NotificationBlock] = [
            KeyValueBlock(key=_("轮次"), value=str(round_num)),
            KeyValueBlock(key=_("检查总数"), value=str(total_checks)),
            KeyValueBlock(key=_("变更数"), value=str(total_changes)),
            KeyValueBlock(key=_("失败数"), value=str(total_failures)),
        ]
        if change_list:
            items = [{"detail": c} for c in change_list]
            blocks.append(
                ListBlock(
                    title=_("变更详情"),
                    items=items,
                    total=total_changes,
                )
            )
        title = _("第 {round} 轮有效性汇总报告").format(round=round_num)
        return NotificationMessage(
            title=title,
            blocks=blocks,
            level="info",
            event_type="validity_round_summary",
            icon="pi pi-list",
        )

    def _build_validity_standard_failed_message(self, data: dict) -> NotificationMessage:
        """构建单条标准有效性检查失败的通知消息。"""
        std_no = data.get("standard_number", "")
        blocks: list[NotificationBlock] = [TextBlock(text=_("标准号：{n}").format(n=std_no))]
        if data.get("error"):
            blocks.append(TextBlock(text=_("错误：{e}").format(e=data["error"])))
        return NotificationMessage(
            title=_("标准有效性检查失败"),
            blocks=blocks,
            level="error",
            standard_number=std_no,
            event_type="validity_standard_failed",
            link=_make_link(std_no),
            icon="pi pi-exclamation-circle",
        )

    def _build_validity_system_failed_message(self, data: dict) -> NotificationMessage:
        """构建有效性检查系统级失败的通知消息。"""
        blocks: list[NotificationBlock] = [TextBlock(text=data.get("error", _("未知系统错误")))]
        if data.get("context"):
            blocks.append(TextBlock(text=_("上下文：{c}").format(c=data["context"])))
        return NotificationMessage(
            title=_("有效性检查系统级失败"),
            blocks=blocks,
            level="error",
            event_type="validity_system_failed",
            icon="pi pi-times",
        )
