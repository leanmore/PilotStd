# 模块：项目/核心//迁移脚本
# 迁移注册中心：各版本迁移拆分至独立模块，此处统一导入触发注册


from ._constants import migration
from ._migrate_v2_v15 import (  # noqa: F401 — 触发装饰器
    _migrate_v2_add_file_index,
    _migrate_v3_queue_and_pending,
    _migrate_v4_add_fetch_checkpoint,
    _migrate_v5_announcement_match,
    _migrate_v6_add_rotator_state,
    _migrate_v7_add_last_checked,
    _migrate_v8_drop_expires_at,
    _migrate_v9_add_requery_count,
    _migrate_v10_add_source_and_status_history,
    _migrate_v11_add_daily_limits,
    _migrate_v12_adapter_stats,
    _migrate_v13_adapter_stats_extend,
    _migrate_v14_api_keys,
    _migrate_v15_announcement_record,
)
from ._migrate_v16_v49 import (  # noqa: F401 — 触发注册
    _migrate_v16_standard_validity,
    _migrate_v17_notification_log,
    _migrate_v18_notification_fetch_task,
    _migrate_v19_users,
    _migrate_v20_announce_since_date,
    _migrate_v21_user_layouts,
    _migrate_v22_user_preferences,
    _migrate_v23_cache_system,
    _migrate_v24_task_queue,
    _migrate_v25_announcement_match_cache,
    _migrate_v26_pipeline_runs,
    _migrate_v27_notification_aggregation,
    _migrate_v28_notification_queue,
    _migrate_v29_announce_title_and_count,
    _migrate_v30_failure_tables,
    _migrate_v38_user_settings,
    _migrate_v41_file_index_raw_number,
    _migrate_v42_create_standards_table,
    _migrate_v43_batch_state_and_metrics,
    _migrate_v45_audit_logs,
    _migrate_v46_default_user_preferences,
    _migrate_v47_task_execution_history,
    _migrate_v48_ensure_preference_tables,
    _migrate_v49_rebuild_user_preferences,
)
from ._migrate_v50 import _migrate_v50_ensure_user_preferences  # noqa: F401 — 触发注册
from ._migrate_v51 import _migrate_v51_adapter_health_check  # noqa: F401 — 触发注册
from ._migrate_v52 import _migrate_v52_ensure_user_favorites_publish_date  # noqa: F401 — 触发注册
from ._migrate_v53 import _migrate_v53_announce_record_pagination_index  # noqa: F401 — 触发注册
from ._migrate_v54 import _migrate_v54_favorite_downloads_columns  # noqa: F401 — 触发注册
from ._migrate_v55 import _migrate_v55_credential_fingerprint_ready  # noqa: F401 — 触发注册

# ──2-15装饰器注册──
migration(2)(_migrate_v2_add_file_index)
migration(3)(_migrate_v3_queue_and_pending)
migration(4)(_migrate_v4_add_fetch_checkpoint)
migration(5)(_migrate_v5_announcement_match)
migration(6)(_migrate_v6_add_rotator_state)
migration(7)(_migrate_v7_add_last_checked)
migration(8)(_migrate_v8_drop_expires_at)
migration(9)(_migrate_v9_add_requery_count)
migration(10)(_migrate_v10_add_source_and_status_history)
migration(11)(_migrate_v11_add_daily_limits)
migration(12)(_migrate_v12_adapter_stats)
migration(13)(_migrate_v13_adapter_stats_extend)
migration(14)(_migrate_v14_api_keys)
migration(15)(_migrate_v15_announcement_record)


from ._migrate_v31_plus import (  # noqa: E402
    _migrate_v31_monitor_stats,
    _migrate_v32_cleanup_dead_tables,
    _migrate_v33_adapter_state,
    _migrate_v34_drop_old_adapter_tables,
    _migrate_v35_notification_policy,
    _migrate_v36_announcement_structure,
)

# 37-40迁移实现（拆分到独立模块）
from ._migrate_v37_plus import (  # noqa: E402
    _migrate_v37_user_notification_config,
    _migrate_v39_announcement_source_type,
    _migrate_v40_ensure_columns,
)

# 44迁移实现（拆分到独立模块）
from ._migrate_v44 import _migrate_v44_favorite_downloads  # noqa: E402, F401

migration(31)(_migrate_v31_monitor_stats)
migration(32)(_migrate_v32_cleanup_dead_tables)
migration(33)(_migrate_v33_adapter_state)
migration(34)(_migrate_v34_drop_old_adapter_tables)
migration(35)(_migrate_v35_notification_policy)
migration(36)(_migrate_v36_announcement_structure)
migration(37)(_migrate_v37_user_notification_config)
migration(39)(_migrate_v39_announcement_source_type)
migration(40)(_migrate_v40_ensure_columns)


# 45:审计日志表（版本三0多用户基础架构）
migration(50)(_migrate_v50_ensure_user_preferences)
migration(51)(_migrate_v51_adapter_health_check)
# 第五十二版兜底迁移拆分至独立模块，避免单文件超限
migration(52)(_migrate_v52_ensure_user_favorites_publish_date)
# 第五十三版分页索引迁移拆分至独立模块，避免单文件超限
migration(53)(_migrate_v53_announce_record_pagination_index)
# 第五十四版收藏链路补列迁移：函数自带注册装饰器，导入即完成注册（与分模块迁移同款）
