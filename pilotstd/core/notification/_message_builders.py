# pilotstd/core/notification/_message_builders.py
# 通知消息构建器混入 — 从 manager.py 提取

from pilotstd.i18n import _

from .channel import NotificationMessage


class MessageBuildersMixin:
    """事件消息构建器方法集合（混入 NotificationManager）。"""

    def _build_archive_complete_message(self, data: dict) -> NotificationMessage:
        """归档完成通知"""
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
        )

    def _build_standard_status_changed_message(self, data: dict) -> NotificationMessage:
        """标准状态变更通知"""
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
        )

    def _build_standard_expired_message(self, data: dict) -> NotificationMessage:
        """标准过期通知（已废止）"""
        std_no = data.get("standard_number", "")
        return NotificationMessage(
            title=_("标准已废止"),
            body=_("{std_no} 状态变更为已废止").format(std_no=std_no),
            level="error",
            standard_number=std_no,
            event_type="standard_expired",
        )

    def _build_standard_first_registered_message(self, data: dict) -> NotificationMessage:
        """标准首次登记通知"""
        std_no = data.get("standard_number", "")
        name = data.get("name", "")
        return NotificationMessage(
            title=_("新标准首次登记"),
            body=_("{std_no} - {name}").format(std_no=std_no, name=name),
            level="info",
            standard_number=std_no,
            event_type="standard_first_registered",
        )

    def _build_check_batch_complete_message(self, data: dict) -> NotificationMessage:
        """批次检查完成通知"""
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
            title=_("标准检查完成"), body=body, level="info", standard_number=None, event_type="check_batch_complete"
        )

    def _build_announcement_fetch_complete_message(self, data: dict) -> NotificationMessage:
        """公告拉取完成通知"""
        return NotificationMessage(
            title=_("公告拉取完成"),
            body=_("新增 {count} 条公告").format(count=data.get("count", 0)),
            level="info",
            standard_number=None,
            event_type="announcement_fetch_complete",
        )

    def _build_auto_backup_message(self, data: dict) -> NotificationMessage:
        """自动备份通知（含成功/失败子分支）"""
        success = data.get("success", False)
        path = data.get("path", "")
        size_mb = data.get("size_mb", 0)
        error = data.get("error", "")
        if success:
            return NotificationMessage(
                title=_("自动备份成功"),
                body=_("数据库已备份至：{path}（{size_mb:.1f} MB）").format(path=path, size_mb=size_mb),
                level="info",
                standard_number=None,
                event_type="auto_backup",
            )
        return NotificationMessage(
            title=_("自动备份失败"),
            body=_("{error}").format(error=error),
            level="error",
            standard_number=None,
            event_type="auto_backup",
        )

    def _build_announcement_check_complete_message(self, data: dict) -> NotificationMessage:
        """公告检查完成通知（含失败子分支）"""
        failures = data.get("failures", 0)
        new_count = data.get("new_count", 0)
        total = data.get("total", 0)
        if failures == 0:
            return NotificationMessage(
                title=_("公告检查完成"),
                body=_("共 {total} 条公告，新增 {new_count} 条").format(total=total, new_count=new_count),
                level="info",
                standard_number=None,
                event_type="announcement_check_complete",
            )
        return NotificationMessage(
            title=_("公告检查完成（有失败）"),
            body=_("共 {total} 条公告，新增 {new_count} 条，{failures} 个站点检查失败").format(
                total=total, new_count=new_count, failures=failures
            ),
            level="warning",
            standard_number=None,
            event_type="announcement_check_complete",
        )

    def _build_batch_download_complete_message(self, data: dict) -> NotificationMessage:
        """批量下载完成通知（含失败子分支）"""
        success = data.get("success", 0)
        failed = data.get("failed", 0)
        skipped = data.get("skipped", 0)
        if failed == 0:
            return NotificationMessage(
                title=_("批量下载完成"),
                body=_("成功 {success} 条，跳过 {skipped} 条").format(success=success, skipped=skipped),
                level="info",
                standard_number=None,
                event_type="batch_download_complete",
            )
        return NotificationMessage(
            title=_("批量下载完成（有失败）"),
            body=_("成功 {success} 条，失败 {failed} 条，跳过 {skipped} 条").format(
                success=success, failed=failed, skipped=skipped
            ),
            level="warning",
            standard_number=None,
            event_type="batch_download_complete",
        )

    def _build_auto_scan_failed_message(self, data: dict) -> NotificationMessage:
        """自动扫描失败通知"""
        return NotificationMessage(
            title=_("自动扫描失败"),
            body=_("{path}：{error}").format(path=data.get("path", ""), error=data.get("error", "")),
            level="error",
            standard_number=None,
            event_type="auto_scan_failed",
        )

    def _build_validity_batch_report_message(self, data: dict) -> NotificationMessage:
        """有效性批量报告通知（含适配器汇总 + level 条件判断）"""
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
            title=_("有效性批量报告"), body=body, level=level, standard_number=None, event_type="validity_batch_report"
        )

    def _build_validity_round_summary_message(self, data: dict) -> NotificationMessage:
        """有效性轮次汇总通知（含变更列表截断）"""
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
            standard_number=None,
            event_type="validity_round_summary",
        )

    def _build_validity_standard_failed_message(self, data: dict) -> NotificationMessage:
        """有效性检查单条失败通知"""
        return NotificationMessage(
            title=_("标准有效性检查失败"),
            body=_("{std_no}：{error}").format(std_no=data.get("standard_number", ""), error=data.get("error", "")),
            level="error",
            standard_number=data.get("standard_number"),
            event_type="validity_standard_failed",
        )

    def _build_validity_system_failed_message(self, data: dict) -> NotificationMessage:
        """有效性检查系统级失败通知"""
        return NotificationMessage(
            title=_("有效性检查系统级失败"),
            body=_("{error}").format(error=data.get("error", "")),
            level="error",
            standard_number=None,
            event_type="validity_system_failed",
        )

    def _build_fallback_message(self, event_type: str, data: dict) -> NotificationMessage:
        """回退消息"""
        return NotificationMessage(
            title=event_type, body=str(data), level="info", standard_number=None, event_type=event_type
        )

    # ── 以下为 2026-07-01 新增事件 ──

    def _build_image_update_available_message(self, data: dict) -> NotificationMessage:
        """镜像更新可用通知"""
        return NotificationMessage(
            title=_("镜像更新可用"),
            body=_("检测到新版本镜像，当前 {old} → 新版本 {new}").format(
                old=data.get("old_digest", "")[:12], new=data.get("new_digest", "")[:12]),
            level="info", standard_number=None, event_type="image_update_available")

    def _build_batch_query_summary_message(self, data: dict) -> NotificationMessage:
        """批量查询完成汇总通知"""
        total = data.get("total", 0)
        found = data.get("found", 0)
        pending = data.get("pending", 0)
        if found == total:
            body = _("标准查询完成：共 {total} 条，全部找到").format(total=total)
            level = "info"
        elif pending > 0:
            body = _("标准查询完成：共 {total} 条，找到 {found} 条，{pending} 条待确认").format(
                total=total, found=found, pending=pending)
            level = "warning"
        else:
            body = _("标准查询完成：共 {total} 条，找到 {found} 条").format(total=total, found=found)
            level = "info"
        return NotificationMessage(
            title=_("标准查询完成"), body=body, level=level,
            standard_number=None, event_type="batch_query_summary")

    def _build_auto_query_complete_message(self, data: dict) -> NotificationMessage:
        """定时自动查询完成通知"""
        changed = data.get("changed", 0)
        total = data.get("total", 0)
        if changed > 0:
            body = _("定时查询完成：共检查 {total} 条，{changed} 条状态变更").format(total=total, changed=changed)
            level = "info"
        else:
            body = _("定时查询完成：共检查 {total} 条，无状态变更").format(total=total)
            level = "info"
        return NotificationMessage(
            title=_("定时查询完成"), body=body, level=level,
            standard_number=None, event_type="auto_query_complete")

    def _build_trust_ip_update_message(self, data: dict) -> NotificationMessage:
        """可信 IP 更新通知（企业微信 IP 变更）。"""
        title = data.get("title", "可信 IP 状态")
        body = data.get("body", "")
        level = "warning" if "失败" in title else "info"
        return NotificationMessage(
            title=title, body=body, level=level,
            standard_number=None, event_type="trust_ip_update")

    def _build_worker_error_message(self, data: dict) -> NotificationMessage:
        """Worker 异常通知"""
        worker = data.get("worker", "未知")
        error = data.get("error", "")
        return NotificationMessage(
            title=_("后台任务异常"),
            body=_("{worker} 工作线程异常：{error}").format(worker=worker, error=error),
            level="error", standard_number=None, event_type="worker_error")
