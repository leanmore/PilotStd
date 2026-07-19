# pilotstd/core/notification/_message_builders.py
# 通知消息构建器混入 — 从 manager.py 提取
# 每个 _build_*_message 方法负责将原始数据字典转换为标准化的 NotificationMessage

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
    # 前端使用 /standards/{number} 路由，此处生成对应链接
    return f"/standards/{standard_number}" if standard_number else None


class MessageBuildersMixin:
    """事件消息构建器方法集合（混入 NotificationManager）。"""

    # ── 归档事件 ──

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

    def _build_check_batch_complete_message(self, data: dict) -> NotificationMessage:
        """构建批量检查完成的通知消息。"""
        total = data.get("total", 0)
        changed = data.get("changed", 0)
        expired = data.get("expired", 0)
        soon = data.get("soon", 0)
        blocks: list[NotificationBlock] = []
        if changed == 0:
            blocks.append(TextBlock(text=_("本次检查未发现状态变更")))
        blocks.extend(
            [
                KeyValueBlock(key=_("检查总数"), value=str(total)),
                KeyValueBlock(key=_("状态变更"), value=str(changed)),
                KeyValueBlock(key=_("已过期"), value=str(expired)),
                KeyValueBlock(key=_("即将过期"), value=str(soon)),
            ]
        )
        return NotificationMessage(
            title=_("标准检查完成"),
            blocks=blocks,
            level="info",
            event_type="check_batch_complete",
            icon="pi pi-check-circle",
        )

    def _build_announcement_fetch_complete_message(self, data: dict) -> NotificationMessage:
        """构建公告拉取完成的通知消息。"""
        blocks: list[NotificationBlock] = [KeyValueBlock(key=_("新增公告"), value=str(data.get("new_count", 0)))]
        if data.get("source"):
            blocks.append(TextBlock(text=_("来源：{s}").format(s=data["source"])))
        return NotificationMessage(
            title=_("公告拉取完成"),
            blocks=blocks,
            level="info",
            event_type="announcement_fetch_complete",
            icon="pi pi-megaphone",
        )

    # ── 备份/同步事件 ──

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

    def _build_batch_download_complete_message(self, data: dict) -> NotificationMessage:
        success = data.get("success", 0)
        failed = data.get("failed", 0)
        skipped = data.get("skipped", 0)
        blocks: list[NotificationBlock] = [
            KeyValueBlock(key=_("成功"), value=str(success)),
            KeyValueBlock(key=_("失败"), value=str(failed)),
            KeyValueBlock(key=_("跳过"), value=str(skipped)),
        ]
        # 有失败时升级为 warning 级别，引导用户查看详情
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

    # ── 扫描/有效性检查事件 ──

    def _build_auto_scan_failed_message(self, data: dict) -> NotificationMessage:
        """构建自动扫描失败的通知消息。"""
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

    def _build_batch_query_summary_message(self, data: dict) -> NotificationMessage:
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
        # 根据命中率决定通知级别：全命中=info，有待确认=warning
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

    def _build_auto_query_complete_message(self, data: dict) -> NotificationMessage:
        changed = data.get("changed", 0)
        total = data.get("total", 0)
        # 定时查询结果：区分有/无变更两套消息
        if changed > 0:
            text = _("定时查询完成：共检查 {total} 条，{changed} 条状态变更").format(total=total, changed=changed)
        else:
            text = _("定时查询完成：共检查 {total} 条，无状态变更").format(total=total)
        blocks: list[NotificationBlock] = [TextBlock(text=text)]
        return NotificationMessage(
            title=_("定时查询完成"),
            blocks=blocks,
            level="info",
            event_type="auto_query_complete",
            icon="pi pi-clock",
        )

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
