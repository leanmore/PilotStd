# 模块：项目/核心//__构建器脚本
# 通知消息构建器聚合模块—原，现为模块级函数重导出
# ::401—本文件仅做重导出，由外部模块消费
# 消费者：管理器脚本通过本文件导入33个__*函数

from ._builders_batch import (
    _build_announce_fetch_summary_message,
    _build_announcement_fetch_complete_message,
    _build_archive_abandoned_message,
    _build_archive_failed_message,
    _build_auto_scan_failed_message,
    _build_batch_download_complete_message,
    _build_batch_query_summary_message,
    _build_date_reminder_message,
    _build_download_complete_message,
    _build_download_failed_message,
    _build_download_started_message,
    _build_expire_standard_moved_message,
    _build_favorite_created_message,
    _build_normalize_complete_message,
    _build_normalize_failed_message,
    _build_query_empty_message,
    _build_query_failed_message,
    _build_replacement_not_found_message,
    _build_scan_complete_message,
    _build_scan_empty_message,
)
from ._builders_system import (
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
from ._builders_validity import (
    _build_standard_first_registered_message,
    _build_standard_status_changed_message,
    _build_validity_batch_report_message,
    _build_validity_round_summary_message,
    _build_validity_standard_failed_message,
    _build_validity_system_failed_message,
    _make_link,
)
