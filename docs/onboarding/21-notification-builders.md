# 21 · 通知事件 builder / payload 明细（44 事件）

> 来源：`EventSpec.builder_ref` / `payload_keys` / `trigger_file`，2026-11-07。
> 渠道矩阵见 `16-notification-matrix.md`；本表补“谁构建、吃什么 payload、从哪触发”。

| # | 事件 | builder | payload 关键字段 | trigger |
|---|---|---|---|---|
| 1 | `standard_status_changed` | `_build_standard_status_changed_message` | changed_at, is_expired, new_standard, new_standard_name, new_status, old_status, standard_name, standard_number | `pilotstd/core/validity_checker.py` |
| 2 | `standard_first_registered` | `_build_standard_first_registered_message` | detail_url, elapsed_ms, name, standard_number, standards | `pilotstd/core/validity_checker.py` |
| 3 | `validity_batch_report` | `_build_validity_batch_report_message` | adapter_status, changed, count, failed | `pilotstd/core/_validity_pipeline.py` |
| 4 | `validity_round_summary` | `_build_validity_round_summary_message` | change_list, round, total_changes, total_checks, total_failures | `pilotstd/core/_validity_pipeline.py` |
| 5 | `validity_standard_failed` | `_build_validity_standard_failed_message` | error, standard_name, standard_number | `pilotstd/core/_validity_pipeline.py` |
| 6 | `validity_system_failed` | `_build_validity_system_failed_message` | error | `pilotstd/core/_validity_pipeline.py` |
| 7 | `date_reminder` | `_build_date_reminder_message` | days_before, remind_type, standard_number, std_name | `pilotstd/tasks/date_reminder.py` |
| 8 | `scan_complete` | `_build_scan_complete_message` | count, failed | `pilotstd/manager/facade/_scan.py` |
| 9 | `scan_empty` | `_build_scan_empty_message` | — | `pilotstd/manager/facade/_scan.py` |
| 10 | `auto_scan_failed` | `_build_auto_scan_failed_message` | error, path | `pilotstd/manager/facade/_scan.py` |
| 11 | `batch_query_summary` | `_build_batch_query_summary_message` | failed_items, found, pending, results, total | `pilotstd/manager/facade/_query_subsystem.py` |
| 12 | `query_failed` | `_build_query_failed_message` | error, standard_name, standard_number | `pilotstd/manager/facade/_query_subsystem.py` |
| 13 | `query_empty` | `_build_query_empty_message` | total | `pilotstd/manager/facade/_query_subsystem.py` |
| 14 | `batch_download_complete` | `_build_batch_download_complete_message` | failed, failed_items, skipped, success | `pilotstd/download/engine.py` |
| 15 | `download_failed` | `_build_download_failed_message` | error, standard_name, standard_number | `pilotstd/tasks/favorite_download.py` |
| 16 | `normalize_complete` | `_build_normalize_complete_message` | failed, failed_items, success, total | `pilotstd/manager/facade/_organize.py` |
| 17 | `normalize_failed` | `_build_normalize_failed_message` | error, total | `pilotstd/manager/facade/_organize.py` |
| 18 | `archive_complete` | `_build_archive_complete_message` | category_stats, count, directories, failed_items | `pilotstd/manager/facade/_organize.py` |
| 19 | `archive_failed` | `_build_archive_failed_message` | count, error | `pilotstd/manager/organize/organizer.py` |
| 20 | `archive_abandoned` | `_build_archive_abandoned_message` | error, standard_info | `pilotstd/services/favorite_chain_processor.py` |
| 21 | `expire_standard_moved` | `_build_expire_standard_moved_message` | standard_name, standard_number, target_path | `pilotstd/manager/facade/_organize.py` |
| 22 | `replacement_not_found` | `_build_replacement_not_found_message` | searched_sources, standard_name, standard_number | `pilotstd/manager/classifier.py` |
| 23 | `announcement_fetch_complete` | `_build_announcement_fetch_complete_message` | count, source | `docker/api/announce.py` |
| 24 | `announcement_check_complete` | `_build_announcement_check_complete_message` | db_count, failures, gb_count, hb_count, source, total_announcements, total_standards | `pilotstd/announce/notifier.py` |
| 25 | `announcement_fetch_failed` | `_build_announcement_fetch_failed_message` | error, source | `pilotstd/announce/notifier.py` |
| 26 | `announce_fetch_summary` | `_build_announce_fetch_summary_message` | adapters, has_error, total_count | `pilotstd/announce/notifier.py` |
| 27 | `auto_backup` | `_build_auto_backup_message` | backup_path, error, size_mb, success | `docker/scheduler.py` |
| 28 | `image_update_available` | `_build_image_update_available_message` | error, new_digest, old_digest, release_notes | `docker/api/system.py` |
| 29 | `trust_ip_update` | `_build_trust_ip_update_message` | body, ip, status, title, update_time | `pilotstd/manager/wechat_ip_service.py` |
| 30 | `worker_error` | `_build_worker_error_message` | error, traceback, worker | `pilotstd/ui/pending_query_dialog.py` |
| 31 | `task_execution_failed` | `_build_task_execution_failed_message` | error, task_name | `docker/scheduler.py` |
| 32 | `quota_exhausted` | `_build_quota_exhausted_message` | quota_limit, reset_time, site_name | `pilotstd/query/daily_quota.py` |
| 33 | `notification_delivery_failed` | `_build_notification_delivery_failed_message` | channel, consecutive, failures, reason, samples | `pilotstd/core/notification/manager.py` |
| 34 | `desktop_toast` | `_build_desktop_toast_message` | — | `pilotstd/core/notification_aggregator.py` |
| 35 | `favorite_created` | `_build_favorite_created_message` | record_id, standard_name, standard_no, user_id | `docker/api/favorites.py` |
| 36 | `task_progress` | `_build_task_progress_message` | completed, elapsed_minutes, percent, step, task_id, task_name, total | `pilotstd/core/notification/progress_reporter.py` |
| 37 | `download_started` | `_build_download_started_message` | favorite_id, standard_name, standard_number, user_id | `pilotstd/tasks/favorite_download.py` |
| 38 | `download_complete` | `_build_download_complete_message` | favorite_id, local_path, standard_name, standard_number, status, user_id | `pilotstd/tasks/favorite_download.py` |
| 39 | `favorite_abandoned_summary` | `_build_favorite_abandoned_summary_message` | details, reasons, retryable, total | `pilotstd/services/favorite_chain_processor.py` |
| 40 | `notification_credential_changed` | `_build_notification_credential_changed_message` | changed_keys, from_ip, rules_changed, services | `docker/api/notification_config.py` |
| 41 | `security_password_changed` | `_build_security_password_changed_message` | from_ip, sessions_revoked, user_id | `docker/api/users.py` |
| 42 | `security_token_refreshed` | `_build_security_token_refreshed_message` | db_synced, from_ip, rotated_at | `docker/api/settings.py` |
| 43 | `security_login_failed` | `_build_security_login_failed_message` | failures, from_ip, username, window_seconds | `docker/auth.py` |
| 44 | `auto_pipeline_summary` | `_build_auto_pipeline_summary_message` | download_success, organize_moved, query_found, scan | `pilotstd/manager/facade/_auto.py` |

## 说明

- builder 只负责“消息长什么样”，不负责渠道/策略；
- payload 是 builder 读取的契约字段，缺字段会走 builder 的默认/空值；
- `verify` 列（e2e/manual）仍保留在 EventSpec，未在本表展开。

