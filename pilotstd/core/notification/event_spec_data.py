"""事件声明数据（T-41/1：从 `event_spec.py` 迁出，守 G-010）。

**为什么单独成模块**：42 条 `EventSpec(...)` 声明是纯数据，体量大且与"数据类/工厂/查询"无关；
混在一起会让 `event_spec.py` 逼近 G-010 的 500 有效行阻断线（实测曾达 486 行）。

**导入方向**：本模块 `from .event_spec import EventSpec` 取数据类；`event_spec.py` 在**声明原位置**
再导入本模块的 `EVENT_SPECS`（延迟导入）⇒ 无循环问题，且对外 API 不变
（`from .event_spec import EVENT_SPECS` 继续可用）。

**门禁解析源**：`scripts/_notification_spec_read.py` / `audit_notification_coverage.py` /
`_notification_spec_audit.py` 的 AST 解析入口已同步指向本模块（见 `EVENT_SPEC_SRC`）。
"""

from __future__ import annotations

from .event_spec import EventSpec

# ── 声明（41 条；按业务模块分组，分组与顺序对齐既有端到端契约，便于逐条比对）──

EVENT_SPECS: tuple[EventSpec, ...] = (
    # ── 时效性检查（6）──
    EventSpec(key="standard_status_changed", notify_event="schedule_reminder", content_type="status_change",
        task_kind="validity_check",
        builder_ref="pilotstd.core.notification._builders_validity:_build_standard_status_changed_message",
        i18n_category="notification.validity", default_channels=("wechat",), levels=("info", "warning", "error"),
        module_key="notification.module.validity", trigger_file="pilotstd/core/validity_checker.py",
        payload_keys=frozenset({"changed_at", "is_expired", "new_status", "old_status", "standard_number"}),
        security=False, branch_by=None, subscribable=True, aggregation="aggregate",

        verify="e2e",
        verify_reason="",
    ),
    EventSpec(key="standard_first_registered", notify_event="task_result", content_type="list",
        task_kind="validity_check",
        builder_ref="pilotstd.core.notification._builders_validity:_build_standard_first_registered_message",
        i18n_category="notification.validity", default_channels=(), levels=("info",),
        module_key="notification.module.validity", trigger_file="pilotstd/core/validity_checker.py",
        payload_keys=frozenset({"detail_url", "elapsed_ms", "name", "standard_number", "standards"}), security=False,
        branch_by=None, subscribable=True, aggregation="aggregate",

        verify="manual",
        verify_reason="real_chain_only",
    ),
    EventSpec(key="validity_batch_report", notify_event="batch_summary", content_type="list",
        task_kind="validity_check",
        builder_ref="pilotstd.core.notification._builders_validity:_build_validity_batch_report_message",
        i18n_category="notification.validity", default_channels=("wechat",), levels=("info", "warning"),
        module_key="notification.module.validity", trigger_file="pilotstd/core/_validity_pipeline.py",
        payload_keys=frozenset({"adapter_status", "changed", "count", "failed"}), security=False, branch_by=None,
        subscribable=True, aggregation="aggregate",

        verify="manual",
        verify_reason="real_chain_only",
    ),
    EventSpec(key="validity_round_summary", notify_event="batch_summary", content_type="list",
        task_kind="validity_check",
        builder_ref="pilotstd.core.notification._builders_validity:_build_validity_round_summary_message",
        i18n_category="notification.validity", default_channels=("wechat",), levels=("info",),
        module_key="notification.module.validity", trigger_file="pilotstd/core/_validity_pipeline.py",
        payload_keys=frozenset({"change_list", "round", "total_changes", "total_checks", "total_failures"}),
        security=False, branch_by=None, subscribable=True, aggregation="aggregate",

        verify="manual",
        verify_reason="real_chain_only",
    ),
    EventSpec(key="validity_standard_failed", notify_event="anomaly_alert", content_type="text",
        task_kind="validity_check",
        builder_ref="pilotstd.core.notification._builders_validity:_build_validity_standard_failed_message",
        i18n_category="notification.validity", default_channels=("wechat",), levels=("error",),
        module_key="notification.module.validity", trigger_file="pilotstd/core/_validity_pipeline.py",
        payload_keys=frozenset({"error", "standard_number"}), security=False, branch_by=None, subscribable=True,
        aggregation="aggregate",

        verify="manual",
        verify_reason="real_chain_only",
    ),
    EventSpec(key="validity_system_failed", notify_event="anomaly_alert", content_type="text",
        task_kind="validity_check",
        builder_ref="pilotstd.core.notification._builders_validity:_build_validity_system_failed_message",
        i18n_category="notification.validity", default_channels=("wechat",), levels=("error",),
        module_key="notification.module.validity", trigger_file="pilotstd/core/_validity_pipeline.py",
        payload_keys=frozenset({"error"}), security=False, branch_by=None, subscribable=True, aggregation="aggregate",

        verify="manual",
        verify_reason="chaos_condition",
    ),

    # ── 用户交互（1）──
    EventSpec(key="date_reminder", notify_event="schedule_reminder", content_type="field_list", task_kind="",
        builder_ref="pilotstd.core.notification._builders_task_results:_build_date_reminder_message",
        i18n_category="notification.validity", default_channels=("wechat",), levels=("info",),
        module_key="notification.module.interaction", trigger_file="pilotstd/tasks/date_reminder.py",
        payload_keys=frozenset({"days_before", "remind_type", "standard_number", "std_name"}), security=False,
        branch_by=None, subscribable=True, aggregation="aggregate",

        verify="manual",
        verify_reason="time_based",
    ),

    # ── 扫描/导入（3）──
    EventSpec(key="scan_complete", notify_event="task_result", content_type="list", task_kind="scan",
        builder_ref="pilotstd.core.notification._builders_task_results:_build_scan_complete_message",
        i18n_category="notification.scan", default_channels=(), levels=("info", "warning"),
        module_key="notification.module.scan", trigger_file="pilotstd/manager/facade/_scan.py",
        payload_keys=frozenset({"count", "failed"}), security=False, branch_by=None, subscribable=True,
        aggregation="aggregate",

        verify="e2e",
        verify_reason="",
    ),
    EventSpec(key="scan_empty", notify_event="task_result", content_type="text", task_kind="scan",
        builder_ref="pilotstd.core.notification._builders_task_results:_build_scan_empty_message",
        i18n_category="notification.scan", default_channels=(), levels=("info",),
        module_key="notification.module.scan", trigger_file="pilotstd/manager/facade/_scan.py",
        payload_keys=frozenset(), security=False, branch_by=None, subscribable=True, aggregation="aggregate",

        verify="e2e",
        verify_reason="",
    ),
    EventSpec(key="auto_scan_failed", notify_event="batch_summary", content_type="text", task_kind="scan",
        builder_ref="pilotstd.core.notification._builders_batch:_build_auto_scan_failed_message",
        i18n_category="notification.scan", default_channels=("wechat",), levels=("error",),
        module_key="notification.module.scan", trigger_file="pilotstd/manager/facade/_scan.py",
        payload_keys=frozenset({"error", "path"}), security=False, branch_by=None, subscribable=True,
        aggregation="aggregate",

        verify="manual",
        verify_reason="external_state",
    ),

    # ── 查询（3）──
    EventSpec(key="batch_query_summary", notify_event="batch_summary", content_type="list", task_kind="query",
        builder_ref="pilotstd.core.notification._builders_batch:_build_batch_query_summary_message",
        i18n_category="notification.query", default_channels=(), levels=("info", "warning"),
        module_key="notification.module.query", trigger_file="pilotstd/manager/facade/_query_subsystem.py",
        payload_keys=frozenset({"failed_items", "found", "pending", "results", "total"}), security=False,
        branch_by=None,
        subscribable=True, aggregation="aggregate",

        verify="e2e",
        verify_reason="",
    ),
    EventSpec(key="query_failed", notify_event="task_failure", content_type="text", task_kind="query",
        builder_ref="pilotstd.core.notification._builders_task_results:_build_query_failed_message",
        i18n_category="notification.query", default_channels=(), levels=("error",),
        module_key="notification.module.query", trigger_file="pilotstd/manager/facade/_query_subsystem.py",
        payload_keys=frozenset({"error", "standard_number"}), security=False, branch_by=None, subscribable=True,
        aggregation="aggregate",

        verify="e2e",
        verify_reason="",
    ),
    EventSpec(key="query_empty", notify_event="batch_summary", content_type="text", task_kind="query",
        builder_ref="pilotstd.core.notification._builders_task_results:_build_query_empty_message",
        i18n_category="notification.query", default_channels=(), levels=("warning",),
        module_key="notification.module.query", trigger_file="pilotstd/manager/facade/_query_subsystem.py",
        payload_keys=frozenset({"total"}), security=False, branch_by=None, subscribable=True,
        aggregation="aggregate",

        verify="manual",
        verify_reason="real_chain_only",
    ),

    # ── 下载（2）──
    EventSpec(key="batch_download_complete", notify_event="batch_summary", content_type="list",
        task_kind="favorite_download",
        builder_ref="pilotstd.core.notification._builders_batch_download:_build_batch_download_complete_message",
        i18n_category="notification.download", default_channels=("wechat",), levels=("info", "warning"),
        module_key="notification.module.download", trigger_file="pilotstd/download/engine.py",
        payload_keys=frozenset({"failed", "failed_items", "skipped", "success"}), security=False, branch_by=None,
        subscribable=True,
        aggregation="aggregate",

        verify="e2e",
        verify_reason="",
    ),
    EventSpec(key="download_failed", notify_event="task_failure", content_type="text",
        task_kind="favorite_download",
        builder_ref="pilotstd.core.notification._builders_batch_download:_build_download_failed_message",
        i18n_category="notification.download", default_channels=(), levels=("error",),
        module_key="notification.module.download", trigger_file="pilotstd/tasks/favorite_download.py",
        # 名称：载荷携带「当前最高可得阶段名」（③决策→②查询→①解析，见 core/name_resolution.py）。
        # 生产方 favorite_download.py::_fetch_std_meta 已按该链取值 ⇒ 此声明须与生产方同批，
        # 否则 tests/test_notification_e2e.py 的正向断言（builder ⊆ trigger）会失败。
        payload_keys=frozenset(
            {"error", "standard_name", "standard_number"}
        ), security=False, branch_by=None, subscribable=True,
        aggregation="aggregate",

        verify="e2e",
        verify_reason="",
    ),

    # ── 规范化（2）──
    EventSpec(key="normalize_complete", notify_event="batch_summary", content_type="text", task_kind="normalize",
        builder_ref="pilotstd.core.notification._builders_batch:_build_normalize_complete_message",
        i18n_category="notification.archive", default_channels=(), levels=("info",),
        module_key="notification.module.normalize", trigger_file="pilotstd/manager/facade/_organize.py",
        payload_keys=frozenset({"failed", "failed_items", "success", "total"}), security=False, branch_by=None,
        subscribable=True,
        aggregation="aggregate",

        verify="e2e",
        verify_reason="",
    ),
    EventSpec(key="normalize_failed", notify_event="task_failure", content_type="text", task_kind="normalize",
        builder_ref="pilotstd.core.notification._builders_task_results:_build_normalize_failed_message",
        i18n_category="notification.archive", default_channels=(), levels=("error",),
        module_key="notification.module.normalize", trigger_file="pilotstd/manager/facade/_organize.py",
        payload_keys=frozenset({"error", "total"}), security=False, branch_by=None, subscribable=True,
        aggregation="aggregate",

        verify="manual",
        verify_reason="real_chain_only",
    ),

    # ── 归档（3）──
    EventSpec(key="archive_complete", notify_event="batch_summary", content_type="list", task_kind="organize",
        builder_ref="pilotstd.core.notification._builders_system:_build_archive_complete_message",
        i18n_category="notification.archive", default_channels=("wechat",), levels=("info",),
        module_key="notification.module.archive", trigger_file="pilotstd/manager/facade/_organize.py",
        # 2026-10-05 B1-3：按**实现**对齐——`_organize.py::archive_standards` 实际只传
        # count / directories / category_stats（原声明的 elapsed_ms / standard_number / status / target_id 从未传入）；
        # 并追加 failed_items（批量导入失败明细，需求①）。
        payload_keys=frozenset({"category_stats", "count", "directories", "failed_items"}),
        security=False, branch_by=None, subscribable=True, aggregation="aggregate",

        verify="e2e",
        verify_reason="",
    ),
    EventSpec(key="archive_failed", notify_event="task_failure", content_type="text", task_kind="organize",
        builder_ref="pilotstd.core.notification._builders_task_results:_build_archive_failed_message",
        i18n_category="notification.archive", default_channels=(), levels=("error",),
        module_key="notification.module.archive", trigger_file="pilotstd/manager/organize/organizer.py",
        payload_keys=frozenset({"count", "error"}), security=False, branch_by=None, subscribable=True,
        aggregation="aggregate",

        verify="e2e",
        verify_reason="",
    ),
    EventSpec(key="archive_abandoned", notify_event="task_result", content_type="text",
        task_kind="favorite_download",
        builder_ref="pilotstd.core.notification._builders_batch:_build_archive_abandoned_message",
        i18n_category="notification.archive", default_channels=(), levels=("error",),
        module_key="notification.module.archive", trigger_file="pilotstd/services/favorite_chain_processor.py",
        payload_keys=frozenset({"error", "standard_info"}), security=False, branch_by=None, subscribable=True,
        aggregation="aggregate",

        verify="manual",
        verify_reason="data_condition",
    ),

    # ── 废止处理（2）──
    EventSpec(key="expire_standard_moved", notify_event="task_result", content_type="text", task_kind="organize",
        builder_ref="pilotstd.core.notification._builders_task_results:_build_expire_standard_moved_message",
        i18n_category="notification.validity", default_channels=(), levels=("info",),
        module_key="notification.module.expire", trigger_file="pilotstd/manager/facade/_organize.py",
        payload_keys=frozenset({"standard_number", "target_path"}), security=False, branch_by=None, subscribable=True,
        aggregation="aggregate",

        verify="manual",
        verify_reason="data_condition",
    ),
    EventSpec(key="replacement_not_found", notify_event="task_failure", content_type="text", task_kind="query",
        builder_ref="pilotstd.core.notification._builders_task_results:_build_replacement_not_found_message",
        i18n_category="notification.validity", default_channels=(), levels=("warning",),
        module_key="notification.module.expire", trigger_file="pilotstd/manager/classifier.py",
        payload_keys=frozenset({"searched_sources", "standard_number"}), security=False, branch_by=None,
        subscribable=True, aggregation="aggregate",

        verify="manual",
        verify_reason="data_condition",
    ),

    # ── 公告抓取（4）──
    EventSpec(key="announcement_fetch_complete", notify_event="user_activity", content_type="list",
        task_kind="announce_fetch",
        builder_ref="pilotstd.core.notification._builders_batch:_build_announcement_fetch_complete_message",
        i18n_category="notification.announce", default_channels=("wechat",), levels=("info",),
        module_key="notification.module.announce", trigger_file="docker/api/announce.py",
        payload_keys=frozenset({"count", "source"}), security=False, branch_by=None, subscribable=True,
        aggregation="aggregate",

        verify="manual",
        verify_reason="real_chain_only",
    ),
    EventSpec(key="announcement_check_complete", notify_event="user_activity", content_type="list",
        task_kind="announce_fetch",
        builder_ref="pilotstd.core.notification._builders_system:_build_announcement_check_complete_message",
        i18n_category="notification.announce", default_channels=("wechat",), levels=("info", "warning", "error"),
        module_key="notification.module.announce", trigger_file="pilotstd/announce/notifier.py",
        payload_keys=frozenset(
            {"db_count", "failures", "gb_count", "hb_count", "source", "total_announcements", "total_standards"}
        ),
         security=False, branch_by=None, subscribable=True, aggregation="aggregate",

        verify="manual",
        verify_reason="real_chain_only",
    ),
    EventSpec(key="announcement_fetch_failed", notify_event="user_activity", content_type="text",
        task_kind="announce_fetch",
        builder_ref="pilotstd.core.notification._builders_system:_build_announcement_fetch_failed_message",
        i18n_category="notification.announce", default_channels=(), levels=("error",),
        module_key="notification.module.announce", trigger_file="pilotstd/announce/notifier.py",
        payload_keys=frozenset({"error", "source"}), security=False, branch_by=None, subscribable=True,
        aggregation="aggregate",

        verify="manual",
        verify_reason="real_chain_only",
    ),
    EventSpec(key="announce_fetch_summary", notify_event="user_activity", content_type="list",
        task_kind="announce_fetch",
        builder_ref="pilotstd.core.notification._builders_task_results:_build_announce_fetch_summary_message",
        i18n_category="notification.announce", default_channels=(), levels=("info", "warning"),
        module_key="notification.module.announce", trigger_file="pilotstd/announce/notifier.py",
        payload_keys=frozenset({"adapters", "has_error", "total_count"}), security=False, branch_by=None,
        subscribable=True, aggregation="aggregate",

        verify="manual",
        verify_reason="real_chain_only",
    ),

    # ── 系统运维（7）──
    EventSpec(key="auto_backup", notify_event="anomaly_alert", content_type="field_list", task_kind="backup",
        builder_ref="pilotstd.core.notification._builders_system:_build_auto_backup_message",
        i18n_category="notification.system", default_channels=("wechat",), levels=("info", "error"),
        module_key="notification.module.system", trigger_file="docker/scheduler.py",
        payload_keys=frozenset({"backup_path", "error", "size_mb", "success"}), security=False, branch_by=None,
        subscribable=True, aggregation="aggregate",

        verify="manual",
        verify_reason="time_based",
    ),
    EventSpec(key="image_update_available", notify_event="anomaly_alert", content_type="text",
        task_kind="image_update",
        builder_ref="pilotstd.core.notification._builders_system:_build_image_update_available_message",
        i18n_category="notification.system", default_channels=(), levels=("info", "error"),
        module_key="notification.module.system", trigger_file="docker/api/system.py",
        payload_keys=frozenset({"error", "new_digest", "old_digest", "release_notes"}), security=False,
        branch_by=None, subscribable=True, aggregation="aggregate",

        verify="e2e",
        verify_reason="",
    ),
    EventSpec(key="trust_ip_update", notify_event="security_alert", content_type="field_list", task_kind="",
        builder_ref="pilotstd.core.notification._builders_system:_build_trust_ip_update_message",
        i18n_category="notification.system", default_channels=(), levels=("info", "warning"),
        module_key="notification.module.system", trigger_file="pilotstd/manager/wechat_ip_service.py",
        payload_keys=frozenset({"body", "ip", "status", "title", "update_time"}), security=False, branch_by=None,
        subscribable=True, aggregation="aggregate",

        verify="manual",
        verify_reason="external_event",
    ),
    EventSpec(key="worker_error", notify_event="anomaly_alert", content_type="text", task_kind="",
        builder_ref="pilotstd.core.notification._builders_system:_build_worker_error_message",
        i18n_category="notification.system", default_channels=(), levels=("error",),
        module_key="notification.module.system", trigger_file="pilotstd/ui/pending_query_dialog.py",
        payload_keys=frozenset({"error", "traceback", "worker"}), security=False, branch_by=None, subscribable=True,
        aggregation="aggregate",

        verify="ui_only",
        verify_reason="ui_only",
    ),
    EventSpec(key="task_execution_failed", notify_event="anomaly_alert", content_type="text", task_kind="",
        builder_ref="pilotstd.core.notification._builders_system:_build_task_execution_failed_message",
        i18n_category="notification.system", default_channels=(), levels=("error",),
        module_key="notification.module.system", trigger_file="docker/scheduler.py",
        payload_keys=frozenset({"error", "task_name"}), security=False, branch_by=None, subscribable=True,
        aggregation="aggregate",

        verify="e2e",
        verify_reason="",
    ),
    EventSpec(key="quota_exhausted", notify_event="anomaly_alert", content_type="text", task_kind="",
        builder_ref="pilotstd.core.notification._builders_system:_build_quota_exhausted_message",
        i18n_category="notification.system", default_channels=(), levels=("warning",),
        module_key="notification.module.system", trigger_file="pilotstd/query/daily_quota.py",
        payload_keys=frozenset({"quota_limit", "reset_time", "site_name"}), security=False, branch_by=None,
        subscribable=True, aggregation="aggregate",

        verify="manual",
        verify_reason="external_state",
    ),
    EventSpec(key="notification_delivery_failed", notify_event="system_health", content_type="text", task_kind="",
        builder_ref="pilotstd.core.notification._builders_batch:_build_notification_delivery_failed_message",
        i18n_category="notification.system", default_channels=("wechat",), levels=("error",),
        module_key="notification.module.system", trigger_file="pilotstd/core/notification/manager.py",
        payload_keys=frozenset({"channel", "consecutive", "failures", "reason", "samples"}), security=False,
        branch_by=None, subscribable=False, aggregation="aggregate",

        verify="manual",
        verify_reason="chaos_condition",
    ),

    # ── 平台层（1）──（阶段 4 · P6 · 4c：登记 `desktop_toast`，消除 G-045 盲区）
    # 与 `notification_delivery_failed` 同口径：归 `system_health`、`subscribable=False`（不进用户配置入口）、
    # `task_kind=""`（不是用户交办的任务）。**trigger_file 指向真实产出点**——桌面协调层的
    # `push(event_type="desktop_toast", ...)`（走 L2→L1 直构消息，**不经 `send_event`** ⇒ `payload_keys` 为空集，
    # 与 `scan_empty` 同例；声明非空键会让 G-045 的"触发方须提供该键"永远无法满足）。
    EventSpec(key="desktop_toast", notify_event="system_health", content_type="text", task_kind="",
        builder_ref="pilotstd.core.notification._builders_system:_build_desktop_toast_message",
        i18n_category="notification.system", default_channels=(), levels=("info", "warning", "error"),
        module_key="notification.module.system", trigger_file="pilotstd/core/notification_aggregator.py",
        payload_keys=frozenset(), security=False, branch_by=None, subscribable=False, aggregation="aggregate",

        verify="ui_only",
        verify_reason="ui_only",
    ),

    # ── 收藏链（4）──
    EventSpec(key="favorite_created", notify_event="user_activity", content_type="field_list",
        task_kind="favorite_download",
        builder_ref="pilotstd.core.notification._builders_batch:_build_favorite_created_message",
        i18n_category="notification.download", default_channels=(), levels=("info",),
        module_key="notification.module.favorite", trigger_file="docker/api/favorites.py",
        payload_keys=frozenset({"record_id", "standard_name", "standard_no", "user_id"}), security=False,
        branch_by=None, subscribable=True, aggregation="aggregate",

        verify="e2e",
        verify_reason="",
    ),
    EventSpec(key="download_started", notify_event="task_progress", content_type="field_list",
        task_kind="favorite_download",
        builder_ref="pilotstd.core.notification._builders_batch_download:_build_download_started_message",
        i18n_category="notification.download", default_channels=(), levels=("info",),
        module_key="notification.module.favorite", trigger_file="pilotstd/tasks/favorite_download.py",
        # 名称：同 download_failed——载荷带「最高可得阶段名」，与生产方 _fetch_std_meta 同批对齐。
        payload_keys=frozenset(
            {"favorite_id", "standard_name", "standard_number", "user_id"}
        ), security=False, branch_by=None,
        subscribable=True, aggregation="aggregate",

        verify="e2e",
        verify_reason="",
    ),
    EventSpec(key="download_complete", notify_event="task_result", content_type="field_list",
        task_kind="favorite_download",
        builder_ref="pilotstd.core.notification._builders_batch_download:_build_download_complete_message",
        i18n_category="notification.download", default_channels=(), levels=("info",),
        module_key="notification.module.favorite", trigger_file="pilotstd/tasks/favorite_download.py",
        payload_keys=frozenset(
            {"favorite_id", "local_path", "standard_name", "standard_number", "status", "user_id"}
        ), security=False,
        branch_by=None, subscribable=True, aggregation="aggregate",

        verify="e2e",
        verify_reason="",
    ),
    EventSpec(key="favorite_abandoned_summary", notify_event="user_activity", content_type="list",
        task_kind="favorite_download",
        builder_ref="pilotstd.core.notification._builders_batch:_build_favorite_abandoned_summary_message",
        i18n_category="notification.download", default_channels=("wechat",), levels=("warning",),
        module_key="notification.module.favorite", trigger_file="pilotstd/services/favorite_chain_processor.py",
        payload_keys=frozenset({"details", "reasons", "retryable", "total"}), security=False, branch_by=None,
        subscribable=False, aggregation="aggregate",

        verify="e2e",
        verify_reason="",
    ),

    # ── 安全告警（4）──
    EventSpec(key="notification_credential_changed", notify_event="security_alert", content_type="list", task_kind="",
        builder_ref="pilotstd.core.notification._builders_system_security:_build_notification_credential_changed_message",
        i18n_category="notification.system", default_channels=(), levels=("warning",),
        module_key="notification.module.security", trigger_file="docker/api/notification_config.py",
        payload_keys=frozenset({"changed_keys", "from_ip", "rules_changed", "services"}), security=True,
        branch_by=None, subscribable=False, aggregation="bypass",

        verify="manual",
        verify_reason="env_dependent",
    ),
    EventSpec(key="security_password_changed", notify_event="security_alert", content_type="list", task_kind="",
        builder_ref="pilotstd.core.notification._builders_system_security:_build_security_password_changed_message",
        i18n_category="notification.system", default_channels=(), levels=("warning",),
        module_key="notification.module.security", trigger_file="docker/api/users.py",
        payload_keys=frozenset({"from_ip", "sessions_revoked", "user_id"}), security=True, branch_by=None,
        subscribable=False, aggregation="bypass",

        verify="e2e",
        verify_reason="",
    ),
    EventSpec(key="security_token_refreshed", notify_event="security_alert", content_type="text", task_kind="",
        builder_ref="pilotstd.core.notification._builders_system_security:_build_security_token_refreshed_message",
        i18n_category="notification.system", default_channels=(), levels=("warning",),
        module_key="notification.module.security", trigger_file="docker/api/settings.py",
        payload_keys=frozenset({"db_synced", "from_ip", "rotated_at"}), security=True, branch_by=None,
        subscribable=False, aggregation="bypass",

        verify="manual",
        verify_reason="env_dependent",
    ),
    EventSpec(key="security_login_failed", notify_event="security_alert", content_type="field_list", task_kind="",
        builder_ref="pilotstd.core.notification._builders_system_security:_build_security_login_failed_message",
        i18n_category="notification.system", default_channels=("wechat",), levels=("warning",),
        module_key="notification.module.security", trigger_file="docker/auth.py",
        payload_keys=frozenset({"failures", "from_ip", "username", "window_seconds"}), security=True, branch_by=None,
        subscribable=False, aggregation="aggregate",

        verify="manual",
        verify_reason="env_dependent",
    ),
)
