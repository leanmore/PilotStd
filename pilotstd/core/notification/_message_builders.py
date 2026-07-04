# pilotstd/core/notification/_message_builders.py
# 通知消息构建器混入 — 从 manager.py 提取

from pilotstd.i18n import _

from .channel import NotificationMessage


def _make_link(standard_number: str | None) -> str | None:
    """根据标准号生成跳转链接。"""
    return f"/standards/{standard_number}" if standard_number else None


class MessageBuildersMixin:
    """事件消息构建器方法集合（混入 NotificationManager）。"""

    def _build_archive_complete_message(self, data: dict) -> NotificationMessage:
        count = data.get("count", 0)
        directories = data.get("directories", [])
        if count == 0:
            body = _("未归档任何目录（所有目标均为空或已归档）")
        else:
            dirs_preview = "、".join(directories[:3])
            if len(directories) > 3:
                body = _("已归档 {count} 个目录：{preview} 等").format(count=count, preview=dirs_preview)
            else:
                body = _("已归档 {count} 个目录：{preview}").format(count=count, preview=dirs_preview)
        return NotificationMessage(
            title=_("归档完成"),
            body=body,
            level="info",
            standard_number=data.get("standard_number"),
            event_type="archive_complete",
            link=_make_link(data.get("standard_number")),
            icon="pi pi-folder-open",
        )

    def _build_standard_status_changed_message(self, data: dict) -> NotificationMessage:
        std_no = data.get("standard_number", "")
        old_status = data.get("old_status", "")
        new_status = data.get("new_status", "")
        level = "warning" if new_status == _("已废止") else "info"
        return NotificationMessage(
            title=_("标准状态变更"),
            body=_("{std_no} 状态变更：{old} → {new}").format(std_no=std_no, old=old_status, new=new_status),
            level=level,
            standard_number=std_no,
            event_type="standard_status_changed",
            link=_make_link(std_no),
            icon="pi pi-refresh",
        )

    def _build_standard_expired_message(self, data: dict) -> NotificationMessage:
        std_no = data.get("standard_number", "")
        return NotificationMessage(
            title=_("标准已废止"),
            body=_("{std_no} 状态变更为已废止").format(std_no=std_no),
            level="error",
            standard_number=std_no,
            event_type="standard_expired",
            link=_make_link(std_no),
            icon="pi pi-times-circle",
        )

    def _build_standard_first_registered_message(self, data: dict) -> NotificationMessage:
        std_no = data.get("standard_number", "")
        return NotificationMessage(
            title=_("新标准首次登记"),
            body=_("{std_no} - {name}").format(std_no=std_no, name=data.get("name", "")),
            level="info",
            standard_number=std_no,
            event_type="standard_first_registered",
            link=_make_link(std_no),
            icon="pi pi-star",
        )

    # check_batch_complete 和 auto_query_complete 保留函数定义但不再注册到 _EVENT_BUILDERS

    def _build_check_batch_complete_message(self, data: dict) -> NotificationMessage:
        total = data.get("total", 0)
        changed = data.get("changed", 0)
        expired = data.get("expired", 0)
        soon = data.get("soon", 0)
        if changed:
            body = _("标准检查完成：共 {total} 条，变更 {changed} 条，过期 {expired} 条，即将过期 {soon} 条").format(
                total=total, changed=changed, expired=expired, soon=soon
            )
        else:
            body = _("标准检查完成：共 {total} 条，无变更").format(total=total)
        return NotificationMessage(
            title=_("标准检查完成"),
            body=body,
            level="info",
            event_type="check_batch_complete",
            icon="pi pi-check-circle",
        )

    def _build_announcement_fetch_complete_message(self, data: dict) -> NotificationMessage:
        return NotificationMessage(
            title=_("公告拉取完成"),
            body=_("新增 {count} 条公告").format(count=data.get("count", 0)),
            level="info",
            event_type="announcement_fetch_complete",
            icon="pi pi-megaphone",
        )

    def _build_auto_backup_message(self, data: dict) -> NotificationMessage:
        success = data.get("success", False)
        path = data.get("path", "")
        size_mb = data.get("size_mb", 0)
        error = data.get("error", "")
        if success:
            return NotificationMessage(
                title=_("自动备份成功"),
                body=_("数据库已备份至：{path}（{size_mb:.1f} MB）").format(path=path, size_mb=size_mb),
                level="info",
                event_type="auto_backup",
                icon="pi pi-database",
            )
        return NotificationMessage(
            title=_("自动备份失败"),
            body=_("{error}").format(error=error),
            level="error",
            event_type="auto_backup",
            icon="pi pi-database",
        )

    def _build_announcement_check_complete_message(self, data: dict) -> NotificationMessage:
        failures = data.get("failures", 0)
        new_count = data.get("new_count", 0)
        total = data.get("total", 0)
        if failures == 0:
            return NotificationMessage(
                title=_("公告检查完成"),
                body=_("共 {total} 条公告，新增 {new_count} 条").format(total=total, new_count=new_count),
                level="info",
                event_type="announcement_check_complete",
                icon="pi pi-check-circle",
            )
        return NotificationMessage(
            title=_("公告检查完成（有失败）"),
            body=_("共 {total} 条公告，新增 {new_count} 条，{failures} 个站点检查失败").format(
                total=total, new_count=new_count, failures=failures
            ),
            level="warning",
            event_type="announcement_check_complete",
            icon="pi pi-exclamation-triangle",
        )

    def _build_batch_download_complete_message(self, data: dict) -> NotificationMessage:
        success = data.get("success", 0)
        failed = data.get("failed", 0)
        skipped = data.get("skipped", 0)
        if failed == 0:
            return NotificationMessage(
                title=_("批量下载完成"),
                body=_("成功 {success} 条，跳过 {skipped} 条").format(success=success, skipped=skipped),
                level="info",
                event_type="batch_download_complete",
                icon="pi pi-download",
            )
        return NotificationMessage(
            title=_("批量下载完成（有失败）"),
            body=_("成功 {success} 条，失败 {failed} 条，跳过 {skipped} 条").format(
                success=success, failed=failed, skipped=skipped
            ),
            level="warning",
            event_type="batch_download_complete",
            icon="pi pi-download",
        )

    def _build_auto_scan_failed_message(self, data: dict) -> NotificationMessage:
        return NotificationMessage(
            title=_("自动扫描失败"),
            body=_("{path}：{error}").format(path=data.get("path", ""), error=data.get("error", "")),
            level="error",
            event_type="auto_scan_failed",
            icon="pi pi-exclamation-triangle",
        )

    def _build_validity_batch_report_message(self, data: dict) -> NotificationMessage:
        count = data.get("count", 0)
        changed = data.get("changed", 0)
        failed = data.get("failed", 0)
        adapters = data.get("adapters", {})
        summary = ", ".join([f"{k}: {v.get('status', '未知')}" for k, v in adapters.items()])
        if adapters:
            body = _("共 {count} 条标准，变更 {changed} 条，失败 {failed} 条，适配器状态：{summary}").format(
                count=count, changed=changed, failed=failed, summary=summary
            )
        else:
            body = _("共 {count} 条标准，变更 {changed} 条，失败 {failed} 条").format(
                count=count, changed=changed, failed=failed
            )
        level = "warning" if (changed > 0 or failed > 0) else "info"
        return NotificationMessage(
            title=_("有效性批量报告"),
            body=body,
            level=level,
            event_type="validity_batch_report",
            icon="pi pi-chart-bar",
        )

    def _build_validity_round_summary_message(self, data: dict) -> NotificationMessage:
        round_num = data.get("round", 0)
        total_checks = data.get("total_checks", 0)
        total_changes = data.get("total_changes", 0)
        total_failures = data.get("total_failures", 0)
        change_list = data.get("change_list", [])
        if len(change_list) > 5:
            changes_preview = "、".join(change_list[:5]) + _(" 等 {n} 项").format(n=len(change_list))
        else:
            changes_preview = "、".join(change_list) if change_list else _("无变更")
        body = _(
            "第 {round} 轮：检查 {total_checks} 条，变更 {total_changes} 条，"
            "失败 {total_failures} 条，变更详情：{changes}"
        ).format(
            round=round_num,
            total_checks=total_checks,
            total_changes=total_changes,
            total_failures=total_failures,
            changes=changes_preview,
        )
        return NotificationMessage(
            title=_("有效性轮次汇总"),
            body=body,
            level="info",
            event_type="validity_round_summary",
            icon="pi pi-list",
        )

    def _build_validity_standard_failed_message(self, data: dict) -> NotificationMessage:
        std_no = data.get("standard_number", "")
        return NotificationMessage(
            title=_("标准有效性检查失败"),
            body=_("{std_no}：{error}").format(std_no=std_no, error=data.get("error", "")),
            level="error",
            standard_number=std_no,
            event_type="validity_standard_failed",
            link=_make_link(std_no),
            icon="pi pi-exclamation-circle",
        )

    def _build_validity_system_failed_message(self, data: dict) -> NotificationMessage:
        return NotificationMessage(
            title=_("有效性检查系统级失败"),
            body=_("{error}").format(error=data.get("error", "")),
            level="error",
            event_type="validity_system_failed",
            icon="pi pi-times",
        )

    def _build_fallback_message(self, event_type: str, data: dict) -> NotificationMessage:
        return NotificationMessage(
            title=event_type,
            body=str(data),
            level="info",
            event_type=event_type,
            icon="pi pi-bell",
        )

    # ── 2026-07-01 新增事件 ──

    def _build_image_update_available_message(self, data: dict) -> NotificationMessage:
        return NotificationMessage(
            title=_("镜像更新可用"),
            body=_("检测到新版本镜像，当前 {old} → 新版本 {new}").format(
                old=data.get("old_digest", "")[:12], new=data.get("new_digest", "")[:12]
            ),
            level="info",
            event_type="image_update_available",
            icon="pi pi-cloud-upload",
        )

    def _build_batch_query_summary_message(self, data: dict) -> NotificationMessage:
        total = data.get("total", 0)
        found = data.get("found", 0)
        pending = data.get("pending", 0)
        if found == total:
            body = _("标准查询完成：共 {total} 条，全部找到").format(total=total)
            level = "info"
        elif pending > 0:
            body = _("标准查询完成：共 {total} 条，找到 {found} 条，{pending} 条待确认").format(
                total=total, found=found, pending=pending
            )
            level = "warning"
        else:
            body = _("标准查询完成：共 {total} 条，找到 {found} 条").format(total=total, found=found)
            level = "info"
        return NotificationMessage(
            title=_("标准查询完成"),
            body=body,
            level=level,
            event_type="batch_query_summary",
            icon="pi pi-search",
        )

    def _build_auto_query_complete_message(self, data: dict) -> NotificationMessage:
        changed = data.get("changed", 0)
        total = data.get("total", 0)
        if changed > 0:
            body = _("定时查询完成：共检查 {total} 条，{changed} 条状态变更").format(total=total, changed=changed)
        else:
            body = _("定时查询完成：共检查 {total} 条，无状态变更").format(total=total)
        return NotificationMessage(
            title=_("定时查询完成"),
            body=body,
            level="info",
            event_type="auto_query_complete",
            icon="pi pi-clock",
        )

    def _build_trust_ip_update_message(self, data: dict) -> NotificationMessage:
        title = data.get("title", "可信 IP 状态")
        body = data.get("body", "")
        level = "warning" if "失败" in title else "info"
        return NotificationMessage(
            title=title,
            body=body,
            level=level,
            event_type="trust_ip_update",
            icon="pi pi-shield",
        )

    def _build_worker_error_message(self, data: dict) -> NotificationMessage:
        worker = data.get("worker", "未知")
        error = data.get("error", "")
        return NotificationMessage(
            title=_("后台任务异常"),
            body=_("{worker} 工作线程异常：{error}").format(worker=worker, error=error),
            level="error",
            event_type="worker_error",
            icon="pi pi-cog",
        )
