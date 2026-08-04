# tests/unit/core/notification/test_message_builders_snapshot.py
"""Phase 0/1 行为快照测试 — 通知模块 3 个 Builder 的全部方法。

Phase 0 测试 Mixin 类 → Phase 1 测试模块级纯函数（零回归）。
每个方法 ≥1 正常用例 + ≥1 边界/空值用例。
"""

from __future__ import annotations

import pytest

from pilotstd.core.notification._builders_validity import (
    _build_standard_expired_message,
    _build_standard_first_registered_message,
    _build_standard_status_changed_message,
    _build_validity_batch_report_message,
    _build_validity_round_summary_message,
    _build_validity_standard_failed_message,
    _build_validity_system_failed_message,
)
from pilotstd.core.notification._builders_system import (
    _build_announcement_check_complete_message,
    _build_announcement_fetch_failed_message,
    _build_archive_complete_message,
    _build_auto_backup_message,
    _build_fallback_message,
    _build_image_update_available_message,
    _build_quota_exhausted_message,
    _build_task_execution_failed_message,
    _build_trust_ip_update_message,
    _build_worker_error_message,
)
from pilotstd.core.notification._builders_batch import (
    _build_announce_fetch_summary_message,
    _build_announcement_fetch_complete_message,
    _build_archive_abandoned_message,
    _build_archive_failed_message,
    _build_auto_scan_failed_message,
    _build_batch_download_complete_message,
    _build_batch_query_summary_message,
    _build_date_reminder_message,
    _build_download_failed_message,
    _build_expire_standard_moved_message,
    _build_normalize_complete_message,
    _build_normalize_failed_message,
    _build_query_empty_message,
    _build_query_failed_message,
    _build_replacement_not_found_message,
    _build_scan_complete_message,
    _build_scan_empty_message,
)
from pilotstd.core.notification.channel import NotificationMessage
from pilotstd.core.notification.blocks import (
    KeyValueBlock,
    ListBlock,
    StatusChangeBlock,
    TextBlock,
)


# ══════════════════════════════════════════════════════════════
# _builders_validity.py（7 函数）
# ══════════════════════════════════════════════════════════════

class TestValidityBuildersSnapshot:

    # ── _build_standard_status_changed_message ──

    def test_status_changed_normal(self):
        msg = _build_standard_status_changed_message({
            "standard_number": "GB/T 123-2024",
            "old_status": "现行",
            "new_status": "即将实施",
            "is_expired": False,
            "changed_at": "2024-06-01",
        })
        assert isinstance(msg, NotificationMessage)
        assert msg.event_type == "standard_status_changed"
        assert msg.level == "info"
        assert msg.standard_number == "GB/T 123-2024"
        assert msg.icon == "pi pi-refresh"
        assert any(isinstance(b, StatusChangeBlock) for b in msg.blocks)

    def test_status_changed_expired(self):
        msg = _build_standard_status_changed_message({
            "standard_number": "GB/T 456-2019",
            "old_status": "现行",
            "new_status": "已废止",
            "is_expired": True,
        })
        assert msg.level == "error"
        assert msg.icon == "pi pi-times-circle"

    def test_status_changed_empty_fields(self):
        msg = _build_standard_status_changed_message({
            "standard_number": "",
            "old_status": "",
            "new_status": "",
            "is_expired": False,
        })
        assert isinstance(msg, NotificationMessage)
        assert msg.standard_number == ""

    # ── _build_standard_expired_message ──

    def test_expired_normal(self):
        msg = _build_standard_expired_message({
            "standard_number": "GB/T 789-2010",
            "old_status": "现行",
            "changed_at": "2023-12-01",
        })
        assert msg.level == "error"
        assert msg.event_type == "standard_expired"
        assert msg.icon == "pi pi-times-circle"
        assert any(isinstance(b, StatusChangeBlock) for b in msg.blocks)

    def test_expired_no_changed_at(self):
        msg = _build_standard_expired_message({
            "standard_number": "GB/T 789-2010",
            "old_status": "现行",
        })
        assert isinstance(msg, NotificationMessage)
        assert msg.level == "error"

    # ── _build_standard_first_registered_message ──

    def test_first_registered_with_standards_list(self):
        msg = _build_standard_first_registered_message({
            "standards": [
                {"number": "GB/T 100-2024", "name": "测试标准A"},
                {"number": "GB/T 200-2024", "name": "测试标准B"},
            ],
            "elapsed_ms": 1500,
        })
        assert msg.level == "info"
        assert msg.event_type == "standard_first_registered"
        assert msg.icon == "pi pi-star"
        assert any(isinstance(b, ListBlock) for b in msg.blocks)
        assert any(isinstance(b, TextBlock) and "1500" in b.text for b in msg.blocks)

    def test_first_registered_legacy_single(self):
        msg = _build_standard_first_registered_message({
            "standard_number": "GB/T 300-2024",
            "name": "旧版单条",
        })
        assert isinstance(msg, NotificationMessage)
        assert msg.event_type == "standard_first_registered"

    def test_first_registered_empty_list(self):
        msg = _build_standard_first_registered_message({
            "standards": [],
        })
        assert isinstance(msg, NotificationMessage)
        assert not any(isinstance(b, ListBlock) for b in msg.blocks)

    # ── _build_validity_batch_report_message ──

    def test_validity_batch_report_normal(self):
        msg = _build_validity_batch_report_message({
            "count": 100,
            "changed": 5,
            "failed": 2,
            "adapter_status": "正常",
        })
        assert msg.event_type == "validity_batch_report"
        assert msg.level == "warning"
        assert msg.icon == "pi pi-chart-bar"
        assert any(
            isinstance(b, KeyValueBlock) and b.key == "检查总数" for b in msg.blocks
        )

    def test_validity_batch_report_zero(self):
        msg = _build_validity_batch_report_message({
            "count": 0,
            "changed": 0,
            "failed": 0,
        })
        assert msg.level == "info"

    def test_validity_batch_report_no_change(self):
        msg = _build_validity_batch_report_message({
            "count": 50,
            "changed": 0,
            "failed": 0,
        })
        assert msg.level == "info"

    # ── _build_validity_round_summary_message ──

    def test_validity_round_summary_with_changes(self):
        msg = _build_validity_round_summary_message({
            "round": 3,
            "total_checks": 200,
            "total_changes": 10,
            "total_failures": 3,
            "change_list": ["GB/T 1 → 已废止", "GB/T 2 → 即将实施"],
        })
        assert msg.event_type == "validity_round_summary"
        assert msg.icon == "pi pi-list"
        assert any(isinstance(b, ListBlock) for b in msg.blocks)

    def test_validity_round_summary_empty_changes(self):
        msg = _build_validity_round_summary_message({
            "round": 1,
            "total_checks": 0,
            "total_changes": 0,
            "total_failures": 0,
            "change_list": [],
        })
        assert isinstance(msg, NotificationMessage)
        assert not any(isinstance(b, ListBlock) for b in msg.blocks)

    # ── _build_validity_standard_failed_message ──

    def test_validity_standard_failed_normal(self):
        msg = _build_validity_standard_failed_message({
            "standard_number": "GB/T 999-2024",
            "error": "连接超时",
        })
        assert msg.level == "error"
        assert msg.event_type == "validity_standard_failed"
        assert msg.icon == "pi pi-exclamation-circle"
        assert msg.standard_number == "GB/T 999-2024"

    def test_validity_standard_failed_no_error(self):
        msg = _build_validity_standard_failed_message({
            "standard_number": "GB/T 999-2024",
        })
        assert isinstance(msg, NotificationMessage)
        assert len(msg.blocks) == 1

    # ── _build_validity_system_failed_message ──

    def test_validity_system_failed_normal(self):
        msg = _build_validity_system_failed_message({
            "error": "数据库连接失败",
            "context": "有效性检查第2轮",
        })
        assert msg.level == "error"
        assert msg.event_type == "validity_system_failed"
        assert msg.icon == "pi pi-times"
        assert any("数据库连接失败" in b.text for b in msg.blocks if isinstance(b, TextBlock))

    def test_validity_system_failed_no_error(self):
        msg = _build_validity_system_failed_message({})
        assert isinstance(msg, NotificationMessage)
        assert msg.level == "error"


# ══════════════════════════════════════════════════════════════
# _builders_system.py（10 函数）
# ══════════════════════════════════════════════════════════════

class TestSystemBuildersSnapshot:

    # ── _build_archive_complete_message ──

    def test_archive_complete_with_dirs(self):
        msg = _build_archive_complete_message({
            "count": 3,
            "directories": ["dir_a", "dir_b", "dir_c"],
            "standard_number": "GB/T 1-2024",
        })
        assert msg.event_type == "archive_complete"
        assert msg.level == "info"
        assert msg.icon == "pi pi-folder-open"
        assert any(isinstance(b, ListBlock) for b in msg.blocks)

    def test_archive_complete_empty(self):
        msg = _build_archive_complete_message({
            "count": 0,
            "directories": [],
        })
        assert isinstance(msg, NotificationMessage)
        assert not any(isinstance(b, ListBlock) for b in msg.blocks)

    # ── _build_auto_backup_message ──

    def test_auto_backup_success(self):
        msg = _build_auto_backup_message({
            "success": True,
            "backup_path": "/backups/2024.db",
            "size_mb": "15.3",
        })
        assert msg.level == "info"
        assert msg.event_type == "auto_backup"
        assert msg.icon == "pi pi-database"
        assert any(isinstance(b, KeyValueBlock) for b in msg.blocks)

    def test_auto_backup_failure(self):
        msg = _build_auto_backup_message({
            "success": False,
            "error": "磁盘空间不足",
        })
        assert msg.level == "error"
        assert any(isinstance(b, TextBlock) for b in msg.blocks)

    # ── _build_announcement_check_complete_message ──

    def test_announcement_check_complete_success(self):
        msg = _build_announcement_check_complete_message({
            "source": "std_gov",
            "total_announcements": 50,
            "gb_count": 30,
            "hb_count": 15,
            "db_count": 5,
            "total_standards": 120,
            "failures": 0,
        })
        assert msg.level == "info"
        assert msg.event_type == "announcement_check_complete"

    def test_announcement_check_all_failed(self):
        msg = _build_announcement_check_complete_message({
            "total_announcements": 0,
            "gb_count": 0,
            "hb_count": 0,
            "db_count": 0,
            "total_standards": 0,
            "failures": 5,
        })
        assert msg.level == "error"

    def test_announcement_check_partial_fail(self):
        msg = _build_announcement_check_complete_message({
            "total_announcements": 30,
            "gb_count": 20,
            "hb_count": 8,
            "db_count": 2,
            "total_standards": 60,
            "failures": 1,
        })
        assert msg.level == "warning"

    # ── _build_fallback_message ──

    def test_fallback_normal(self):
        msg = _build_fallback_message("custom_event", {
            "event_type": "custom_event",
            "extra_field": "value",
        })
        assert msg.level == "info"
        assert msg.icon == "pi pi-bell"
        assert msg.title == "custom_event"

    def test_fallback_empty_data(self):
        msg = _build_fallback_message("unknown", {})
        assert isinstance(msg, NotificationMessage)

    # ── _build_image_update_available_message ──

    def test_image_update_normal(self):
        msg = _build_image_update_available_message({
            "old_digest": "sha256:abc123",
            "new_digest": "sha256:def456",
            "release_notes": "修复若干 Bug",
        })
        assert msg.level == "info"
        assert msg.event_type == "image_update_available"
        assert "sha256:abc123" in msg.blocks[0].old_value

    def test_image_update_error(self):
        msg = _build_image_update_available_message({
            "error": "网络不可达",
        })
        assert msg.level == "error"

    # ── _build_trust_ip_update_message ──

    def test_trust_ip_update_normal(self):
        msg = _build_trust_ip_update_message({
            "title": "可信 IP 状态变更",
            "body": "IP 地址已更新",
            "ip": "192.168.1.1",
            "update_time": "2024-06-01 12:00",
            "status": "active",
        })
        assert msg.event_type == "trust_ip_update"
        assert any(isinstance(b, KeyValueBlock) for b in msg.blocks)

    def test_trust_ip_update_failure_keyword(self):
        msg = _build_trust_ip_update_message({
            "title": "可信 IP 更新失败",
            "body": "连接超时",
        })
        assert msg.level == "warning"

    # ── _build_worker_error_message ──

    def test_worker_error_with_traceback(self):
        msg = _build_worker_error_message({
            "worker": "ScanWorker",
            "error": "文件读取失败",
            "traceback": "Traceback (most recent call last):\n  ...",
        })
        assert msg.level == "error"
        assert msg.event_type == "worker_error"
        assert msg.icon == "pi pi-cog"
        assert any(isinstance(b, TextBlock) and "ScanWorker" in b.text for b in msg.blocks)

    def test_worker_error_minimal(self):
        msg = _build_worker_error_message({
            "worker": "",
            "error": "",
        })
        assert isinstance(msg, NotificationMessage)
        assert msg.level == "error"

    # ── _build_task_execution_failed_message ──

    def test_task_execution_failed(self):
        msg = _build_task_execution_failed_message({
            "task_name": "定时公告检查",
            "error": "网络超时",
        })
        assert msg.level == "error"
        assert msg.event_type == "task_execution_failed"

    # ── _build_announcement_fetch_failed_message ──

    def test_announcement_fetch_failed(self):
        msg = _build_announcement_fetch_failed_message({
            "source": "std_gov",
            "error": "403 Forbidden",
        })
        assert msg.level == "error"
        assert msg.event_type == "announcement_fetch_failed"

    # ── _build_quota_exhausted_message ──

    def test_quota_exhausted(self):
        msg = _build_quota_exhausted_message({
            "site_name": "ahbz",
            "quota_limit": "1000",
            "reset_time": "明日 0:00",
        })
        assert msg.level == "warning"
        assert msg.event_type == "quota_exhausted"


# ══════════════════════════════════════════════════════════════
# _builders_batch.py（18 函数）
# ══════════════════════════════════════════════════════════════

class TestBatchBuildersSnapshot:

    # ── _build_announcement_fetch_complete_message ──

    def test_announcement_fetch_complete_with_source(self):
        msg = _build_announcement_fetch_complete_message({
            "count": 25,
            "source": "std_gov",
        })
        assert msg.event_type == "announcement_fetch_complete"
        assert msg.level == "info"
        assert any(isinstance(b, KeyValueBlock) for b in msg.blocks)

    def test_announcement_fetch_complete_no_source(self):
        msg = _build_announcement_fetch_complete_message({
            "count": 0,
        })
        assert isinstance(msg, NotificationMessage)
        assert len(msg.blocks) == 1

    # ── _build_batch_download_complete_message ──

    def test_batch_download_complete_all_success(self):
        msg = _build_batch_download_complete_message({
            "success": 10,
            "failed": 0,
            "skipped": 0,
        })
        assert msg.level == "info"
        assert msg.event_type == "batch_download_complete"

    def test_batch_download_complete_with_failures(self):
        msg = _build_batch_download_complete_message({
            "success": 8,
            "failed": 2,
            "skipped": 1,
        })
        assert msg.level == "warning"

    # ── _build_batch_query_summary_message ──

    def test_batch_query_summary_with_results(self):
        msg = _build_batch_query_summary_message({
            "total": 5,
            "found": 4,
            "pending": 1,
            "results": [
                {"number": "GB/T 1-2024", "name": "标准一"},
                {"number": "GB/T 2-2024", "name": "标准二"},
            ],
        })
        assert msg.event_type == "batch_query_summary"
        assert msg.level == "warning"
        assert any(isinstance(b, ListBlock) for b in msg.blocks)

    def test_batch_query_summary_no_results(self):
        msg = _build_batch_query_summary_message({
            "total": 0,
            "found": 0,
            "pending": 0,
        })
        assert isinstance(msg, NotificationMessage)
        assert msg.level == "info"

    def test_batch_query_summary_all_found(self):
        msg = _build_batch_query_summary_message({
            "total": 3,
            "found": 3,
            "pending": 0,
        })
        assert msg.level == "info"

    # ── _build_auto_scan_failed_message ──

    def test_auto_scan_failed_with_error(self):
        msg = _build_auto_scan_failed_message({
            "path": "/data/source",
            "error": "权限不足",
        })
        assert msg.level == "error"
        assert msg.event_type == "auto_scan_failed"

    def test_auto_scan_failed_no_error(self):
        msg = _build_auto_scan_failed_message({
            "path": "/data/source",
        })
        assert isinstance(msg, NotificationMessage)
        assert msg.level == "error"

    # ── _build_download_failed_message ──

    def test_download_failed(self):
        msg = _build_download_failed_message({
            "standard_number": "GB/T 555-2024",
            "error": "文件不存在",
        })
        assert msg.level == "error"
        assert msg.event_type == "download_failed"

    # ── _build_archive_abandoned_message ──

    def test_archive_abandoned(self):
        msg = _build_archive_abandoned_message({
            "standard_info": "GB/T 666-2024 标准说明",
            "error": "重试次数耗尽",
        })
        assert msg.level == "error"
        assert msg.event_type == "archive_abandoned"

    # ── _build_normalize_complete_message ──

    def test_normalize_complete(self):
        msg = _build_normalize_complete_message({
            "total": 50,
            "success": 48,
            "failed": 2,
        })
        assert msg.level == "info"
        assert msg.event_type == "normalize_complete"

    # ── _build_scan_complete_message ──

    def test_scan_complete_with_files(self):
        msg = _build_scan_complete_message({
            "count": 30,
            "failed": 2,
        })
        assert msg.level == "info"
        assert msg.event_type == "scan_complete"

    def test_scan_complete_empty(self):
        msg = _build_scan_complete_message({
            "count": 0,
            "failed": 0,
        })
        assert msg.level == "warning"

    # ── _build_date_reminder_message ──

    def test_date_reminder(self):
        msg = _build_date_reminder_message({
            "standard_number": "GB/T 777-2024",
            "std_name": "测试标准",
            "days_before": 30,
            "remind_type": "实施提醒",
        })
        assert msg.level == "info"
        assert msg.event_type == "date_reminder"

    # ── _build_scan_empty_message ──

    def test_scan_empty(self):
        msg = _build_scan_empty_message({})
        assert msg.level == "info"
        assert msg.event_type == "scan_empty"

    # ── _build_query_failed_message ──

    def test_query_failed(self):
        msg = _build_query_failed_message({
            "standard_number": "GB/T 888-2024",
            "error": "站点不可达",
        })
        assert msg.level == "error"
        assert msg.event_type == "query_failed"

    # ── _build_query_empty_message ──

    def test_query_empty(self):
        msg = _build_query_empty_message({
            "total": 10,
        })
        assert msg.level == "warning"
        assert msg.event_type == "query_empty"

    # ── _build_archive_failed_message ──

    def test_archive_failed(self):
        msg = _build_archive_failed_message({
            "count": 3,
            "error": "磁盘满",
        })
        assert msg.level == "error"
        assert msg.event_type == "archive_failed"

    # ── _build_normalize_failed_message ──

    def test_normalize_failed(self):
        msg = _build_normalize_failed_message({
            "total": 20,
            "error": "格式异常",
        })
        assert msg.level == "error"
        assert msg.event_type == "normalize_failed"

    # ── _build_expire_standard_moved_message ──

    def test_expire_standard_moved(self):
        msg = _build_expire_standard_moved_message({
            "standard_number": "GB/T 999-2010",
            "target_path": "/library/过期作废/GB_T 999-2010.pdf",
        })
        assert msg.level == "info"
        assert msg.event_type == "expire_standard_moved"

    # ── _build_replacement_not_found_message ──

    def test_replacement_not_found_with_sources(self):
        msg = _build_replacement_not_found_message({
            "standard_number": "GB/T 111-2015",
            "searched_sources": ["std_gov", "ahbz"],
        })
        assert msg.level == "warning"
        assert msg.event_type == "replacement_not_found"

    def test_replacement_not_found_no_sources(self):
        msg = _build_replacement_not_found_message({
            "standard_number": "GB/T 111-2015",
        })
        assert isinstance(msg, NotificationMessage)
        assert msg.level == "warning"

    # ── _build_announce_fetch_summary_message ──

    def test_announce_fetch_summary_success(self):
        msg = _build_announce_fetch_summary_message({
            "adapters": [
                {"name": "std_gov", "status": "success", "count": 30},
                {"name": "ahbz", "status": "success", "count": 15},
            ],
            "total_count": 45,
            "has_error": False,
        })
        assert msg.level == "info"
        assert msg.event_type == "announce_fetch_summary"

    def test_announce_fetch_summary_with_errors(self):
        msg = _build_announce_fetch_summary_message({
            "adapters": [
                {"name": "std_gov", "status": "failed", "count": 0, "error_msg": "超时"},
            ],
            "total_count": 0,
            "has_error": True,
        })
        assert msg.level == "warning"

    def test_announce_fetch_summary_many_adapters(self):
        adapters = [{"name": f"adapter_{i}", "status": "success", "count": i} for i in range(15)]
        msg = _build_announce_fetch_summary_message({
            "adapters": adapters,
            "total_count": 105,
            "has_error": False,
        })
        assert isinstance(msg, NotificationMessage)
        assert any(
            isinstance(b, KeyValueBlock) and "其他" in b.key
            for b in msg.blocks
        ) or any(
            isinstance(b, KeyValueBlock) and "等共" in b.value
            for b in msg.blocks
        )
