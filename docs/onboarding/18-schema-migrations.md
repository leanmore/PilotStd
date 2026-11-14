# 18 · 全表 Schema 与迁移清单

> 来源：`C:\Temp\pilotstd_live_logs\prebatch.bak` 的 `sqlite_master` / `PRAGMA table_info`，2026-11-07 只读实测。
> 当前 schema **v76**；迁移可解析业务表 **43 张**；SQLite 实测业务表 **45 张**（P2-04，含 2 张迁移解析不到的运行时表）；迁移模块 **32 个 `_migrate*.py`**（另有 `migrations.py` / `_migration_checksum.py` 两个基础设施文件）。

## 一、表清单（旧快照 41 个表；当前以迁移解析/SQLite 实测为准）

| # | 表 | 列 |
|---|---|---|
| 1 | `_schema_version` | version:INTEGER<br>checksum:TEXT |
| 2 | `adapter_state` | adapter_name:TEXT<br>request_count:INTEGER<br>daily_count:INTEGER<br>daily_date:TEXT<br>cooldown_until:REAL<br>consecutive_errors:INTEGER<br>active_url:TEXT<br>total_queries:INTEGER<br>successful_queries:INTEGER<br>avg_response_time:REAL<br>total_response_time:REAL<br>cooldown_count:INTEGER<br>last_cooldown_reason:TEXT<br>last_cooldown_at:TEXT<br>freeze_count:INTEGER<br>first_freeze_time:TEXT<br>frozen_until:TEXT<br>fail_streak:INTEGER<br>updated_at:TEXT<br>last_health_check:TIMESTAMP<br>health_status:TEXT |
| 3 | `announcement_match` | id:INTEGER<br>standard_number:TEXT<br>source_site:TEXT<br>result_json:TEXT<br>cached_at:TEXT<br>expires_at:TEXT |
| 4 | `announcement_record` | id:INTEGER<br>source_site:TEXT<br>pid:TEXT<br>announce_no:TEXT<br>standard_number:TEXT<br>std_name:TEXT<br>publish_date:TEXT<br>fetched_at:TEXT<br>matched:INTEGER<br>source_version:TEXT<br>data_state:TEXT<br>last_accessed_at:TEXT<br>announcement_title:TEXT<br>standard_count:INTEGER<br>announcement_id:INTEGER<br>row_index:INTEGER<br>implement_date:TEXT<br>expiry_date:TEXT<br>superseded_by:TEXT<br>status:TEXT<br>confidence:REAL<br>raw_text:TEXT<br>parser_engine:TEXT<br>approved_by:INTEGER<br>approved_at:TEXT<br>updated_at:TEXT<br>source_type:TEXT<br>standard_type:TEXT<br>final_name:TEXT<br>language:TEXT<br>foreign_name:TEXT |
| 5 | `announcements` | id:INTEGER<br>source_site:TEXT<br>pid:TEXT<br>announce_no:TEXT<br>title:TEXT<br>publish_date:TEXT<br>source_url:TEXT<br>attachment_url:TEXT<br>raw_data:TEXT<br>created_at:TEXT<br>updated_at:TEXT<br>parse_status:TEXT |
| 6 | `announcements_raw_backup` | id:INT<br>announce_no:TEXT<br>raw_data:TEXT |
| 7 | `api_keys` | id:INTEGER<br>key_id:TEXT<br>key_hash:TEXT<br>description:TEXT<br>scopes:TEXT<br>created_at:TEXT<br>expires_at:TEXT<br>last_used_at:TEXT<br>is_active:INTEGER<br>created_by:TEXT |
| 8 | `app_preferences` | key:TEXT<br>value:TEXT<br>updated_at:TEXT |
| 9 | `audit_logs` | id:INTEGER<br>user_id:INTEGER<br>action:TEXT<br>resource:TEXT<br>detail:TEXT<br>timestamp:TEXT |
| 10 | `batch_state` | batch_id:TEXT<br>status:TEXT<br>total_items:INTEGER<br>completed_items:INTEGER<br>failed_items:INTEGER<br>overflow_pool:TEXT<br>adapter_quota_snapshot:TEXT<br>created_at:TEXT<br>updated_at:TEXT |
| 11 | `cache_config` | id:INTEGER<br>config_key:TEXT<br>config_value:TEXT<br>updated_at:TEXT |
| 12 | `daily_quota` | site_name:TEXT<br>query_date:TEXT<br>count:INTEGER |
| 13 | `data_source_versions` | id:INTEGER<br>source_name:TEXT<br>version:TEXT<br>updated_at:TEXT |
| 14 | `date_reminder_log` | id:INTEGER<br>user_id:INTEGER<br>record_id:INTEGER<br>remind_type:TEXT<br>days_before:INTEGER<br>sent_at:TEXT |
| 15 | `download_queue` | id:INTEGER<br>standard_number:TEXT<br>standard_name:TEXT<br>publish_date:TEXT<br>expected_available:TEXT<br>created_at:TEXT<br>retry_count:INTEGER<br>status:TEXT<br>standard_type:TEXT |
| 16 | `favorite_downloads` | id:INTEGER<br>favorite_id:INTEGER<br>record_id:INTEGER<br>status:TEXT<br>local_path:TEXT<br>error_message:TEXT<br>retry_count:INTEGER<br>last_attempt:TEXT<br>created_at:TEXT<br>updated_at:TEXT<br>user_id:INTEGER<br>standard_no:TEXT<br>standard_name:TEXT<br>standard_type:TEXT |
| 17 | `fetch_checkpoint` | id:INTEGER<br>source_site:TEXT<br>last_fetched_at:TEXT<br>last_notice_date:TEXT |
| 18 | `fetch_failures` | id:INTEGER<br>task_type:TEXT<br>source_site:TEXT<br>since_date:TEXT<br>error_message:TEXT<br>retry_count:INTEGER<br>last_retry_at:TEXT<br>resolved:BOOLEAN<br>created_at:TEXT |
| 19 | `fetch_locks` | lock_key:TEXT<br>locked_at:TEXT<br>locked_by:TEXT |
| 20 | `fetch_task` | id:TEXT<br>task_type:TEXT<br>status:TEXT<br>progress:INTEGER<br>result_data:TEXT<br>error_msg:TEXT<br>created_at:TIMESTAMP<br>updated_at:TIMESTAMP |
| 21 | `file_index` | id:INTEGER<br>file_path:TEXT<br>logical_code:TEXT<br>number:INTEGER<br>year:INTEGER<br>part:INTEGER<br>std_name:TEXT<br>file_hash:TEXT<br>status:TEXT<br>scanned_at:TEXT<br>last_checked:TEXT<br>raw_number:TEXT<br>source_version:TEXT<br>data_state:TEXT<br>last_accessed_at:TEXT |
| 22 | `login_attempts` | ip:TEXT<br>attempt_time:REAL |
| 23 | `monitor_stats` | id:INTEGER<br>stat_key:TEXT<br>stat_value:INTEGER<br>stat_date:TEXT<br>updated_at:TEXT |
| 24 | `notification_log` | id:INTEGER<br>event_type:TEXT<br>channel:TEXT<br>title:TEXT<br>body:TEXT<br>standard_number:TEXT<br>status:TEXT<br>error_msg:TEXT<br>sent_at:TEXT<br>is_read:INTEGER<br>aggregated_count:INTEGER<br>link:TEXT<br>icon:TEXT<br>message_id:TEXT<br>correlation_id:TEXT<br>delivery_status:TEXT<br>ack_status:TEXT<br>task_id:TEXT<br>notify_event:TEXT<br>content_type:TEXT<br>task_context:TEXT<br>actions:TEXT<br>callback_data:TEXT<br>attachments:TEXT<br>channel_message_ids:TEXT<br>task_kind:TEXT<br>failed_items:TEXT<br>user_id:INTEGER |
| 25 | `notification_policy` | id:INTEGER<br>user_id:INTEGER<br>channel:TEXT<br>enabled:INTEGER<br>events:TEXT<br>created_at:TEXT<br>updated_at:TEXT<br>event_classes:TEXT |
| 26 | `notification_queue` | id:INTEGER<br>event_type:TEXT<br>event_data:TEXT<br>status:TEXT<br>scheduled_time:TEXT<br>error_msg:TEXT<br>created_at:TEXT<br>user_id:INTEGER |
| 27 | `pending_lookup` | id:INTEGER<br>standard_number:TEXT<br>std_name:TEXT<br>found_name:TEXT<br>found_number:TEXT<br>match_status:TEXT<br>effect_status:TEXT<br>score:INTEGER<br>source_site:TEXT<br>file_path:TEXT<br>source_name:TEXT<br>final_name:TEXT<br>reason:TEXT<br>status:TEXT<br>created_at:TEXT<br>resolved_at:TEXT<br>requery_count:INTEGER |
| 28 | `pipeline_runs` | id:INTEGER<br>run_id:TEXT<br>current_step:TEXT<br>status:TEXT<br>progress:INTEGER<br>step_results:TEXT<br>error_message:TEXT<br>created_at:TEXT<br>updated_at:TEXT |
| 29 | `query_metrics` | id:INTEGER<br>batch_id:TEXT<br>metric_key:TEXT<br>metric_value:INTEGER<br>recorded_at:TEXT |
| 30 | `scheduler_lock` | id:INTEGER<br>pid:INTEGER<br>started_at:TEXT<br>heartbeat_at:TEXT |
| 31 | `standard_info_cache` | id:INTEGER<br>standard_number:TEXT<br>source_site:TEXT<br>result_json:TEXT<br>cached_at:TEXT<br>source:TEXT<br>status_history:TEXT<br>source_version:TEXT<br>data_state:TEXT<br>last_accessed_at:TEXT |
| 32 | `standard_validity` | id:INTEGER<br>standard_number:TEXT<br>status:TEXT<br>last_checked_at:TEXT<br>next_check_at:TEXT<br>last_status:TEXT<br>last_status_updated_at:TEXT<br>check_count:INTEGER<br>created_at:TEXT<br>updated_at:TEXT<br>source_version:TEXT<br>data_state:TEXT<br>last_accessed_at:TEXT<br>last_changed_at:TEXT |
| 33 | `standards` | id:INTEGER<br>sha256:TEXT<br>code:TEXT<br>name:TEXT<br>size:INTEGER<br>scan_status:TEXT<br>local_path:TEXT<br>created_at:DATETIME<br>updated_at:DATETIME |
| 34 | `task_execution_history` | id:INTEGER<br>task_name:TEXT<br>status:TEXT<br>error_message:TEXT<br>started_at:TEXT<br>finished_at:TEXT<br>duration_ms:INTEGER<br>created_at:TEXT |
| 35 | `task_queue` | id:INTEGER<br>task_id:TEXT<br>task_type:TEXT<br>status:TEXT<br>total_items:INTEGER<br>completed_items:INTEGER<br>failed_items:INTEGER<br>created_at:TEXT<br>updated_at:TEXT<br>result_json:TEXT<br>error_log:TEXT<br>retry_count:INTEGER<br>max_retries:INTEGER<br>timeout_seconds:INTEGER<br>started_at:TEXT<br>finished_at:TEXT<br>priority:INTEGER<br>queue_name:TEXT |
| 36 | `user_credentials` | id:INTEGER<br>user_id:INTEGER<br>channel:TEXT<br>credentials:TEXT<br>created_at:TEXT<br>updated_at:TEXT |
| 37 | `user_favorites` | id:INTEGER<br>user_id:INTEGER<br>record_id:INTEGER<br>status:TEXT<br>local_path:TEXT<br>error_message:TEXT<br>created_at:TEXT<br>updated_at:TEXT<br>publish_date:TEXT<br>standard_type:TEXT<br>standard_number:TEXT |
| 38 | `user_layouts` | id:INTEGER<br>user_id:INTEGER<br>layout_key:TEXT<br>layout_data:TEXT<br>updated_at:TEXT |
| 39 | `user_preferences` | id:INTEGER<br>user_id:INTEGER<br>preference_key:TEXT<br>preference_value:TEXT<br>created_at:TEXT<br>updated_at:TEXT |
| 40 | `user_settings` | id:INTEGER<br>user_id:INTEGER<br>settings:JSON<br>updated_at:DATETIME |
| 41 | `users` | id:INTEGER<br>username:TEXT<br>password_hash:TEXT<br>salt:TEXT<br>role:TEXT<br>must_change_password:INTEGER<br>created_at:TEXT |

## 一-补：deprecated / 只写未读列（P2-01 方案 B，2026-11-11）

以下列**不删**，保留 schema 兼容；代码不读或只写未读。若未来确认永久废弃，再评估 v77 迁移（需维护窗口，当前不做）。

| 表.列 | 状态 | 说明 |
|---|---|---|
| `announcement_record.approved_by` | deprecated | 仅迁移/DDL；无审批流读取 |
| `api_keys.created_by` | deprecated | 仅 DDL；API Key 创建人未展示 |
| `fetch_checkpoint.since_date_override` | deprecated | 仅 DDL；增量日期由 checkpoint/回看计算 |
| `fetch_failures.last_retry_at` | deprecated | 仅 DDL；重试时间未写未读 |
| `query_metrics.recorded_at` | deprecated | 仅 DDL 默认值；指标按 batch_id/时间查询 |
| `standard_validity.last_status_updated_at` | 只写未读 | `ValidityChecker` 写入；无 API/UI 读取 |
| `validity_check_log.previous_status` | 只写未读 | 病历写入；`validity_check_log` 无生产读取方（见 P2-01）；**整表只写不读**——将来要诊断出口请新增只读 API（带鉴权），不要直接查表；v0.19x 仍无读路径则评估降级为归档表；**降级必须新增迁移（v77+）改表，不得改 v76 源码**（P-106 checksum：改旧迁移会让所有已升级库启动即 `DatabaseError`）；迁移源码受保护、注释不可改，故口径记在此处 |

> 裁决：P2-01 选 B——**不删列**，只标 deprecated；删列需 v77 迁移 + 维护窗口，未来确认“永久废弃”再评估。

## 二、迁移模块（32 个文件 / 76 个版本）

| # | 文件 | 注册版本 | 说明 |
|---|---|---|---|
| 1 | `_migrate_v16_v49.py` | 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 38, 41, 42, 43, 45, 46, 47, 48, 49 | 创建 standard_validity 表，记录标准号的有效性状态及检查周期。 |
| 2 | `_migrate_v2_v15.py` | （文件内组合/循环注册） | 创建 file_index 表及其哈希和编码索引，用于本地文件索引。 |
| 3 | `_migrate_v31_plus.py` | （文件内组合/循环注册） | 监控统计从 cache_config 剥离到独立表 monitor_stats。 |
| 4 | `_migrate_v37_plus.py` | （文件内组合/循环注册） | v37: 通知渠道配置按用户隔离。 |
| 5 | `_migrate_v44.py` | 44 | 创建 favorite_downloads 表 + 迁移归档状态数据 + 清理 user_favorites。 |
| 6 | `_migrate_v50.py` | （文件内组合/循环注册） | 兜底补建 user_preferences 表，修复部分实例跳过 v22/v49 导致表缺失。 |
| 7 | `_migrate_v51.py` | （文件内组合/循环注册） | 为 adapter_state 表新增健康检查字段。 |
| 8 | `_migrate_v52.py` | （文件内组合/循环注册） | CREATE TABLE IF NOT EXISTS user_favorites ( |
| 9 | `_migrate_v53.py` | （文件内组合/循环注册） | 为 announcement_record 添加复合索引以优化分页查询（幂等）。 |
| 10 | `_migrate_v54.py` | 54 | 补 favorite_downloads 列 + 回填存量（幂等，可重复执行）。 |
| 11 | `_migrate_v55.py` | 55 | 推进 schema 版本至 55，为凭据指纹校验做准备（幂等空操作）。 |
| 12 | `_migrate_v56.py` | 56 | 幂等补齐缓存/索引表的版本化三列（缺失才 ALTER，失败记录日志）。 |
| 13 | `_migrate_v57.py` | 57 | PRAGMA 检查列是否存在（幂等 DDL 前提）。 |
| 14 | `_migrate_v58_ensure_app_preferences.py` | 58 | 幂等补建 app_preferences 表并写入 announce_since_date 默认值。 |
| 15 | `_migrate_v59_ensure_favorite_retry_columns.py` | 59 | 幂等补全 user_favorites.last_archive_attempt / archive_retry_count。 |
| 16 | `_migrate_v60_drop_favorite_retry_columns.py` | 60 | 删除 user_favorites.last_archive_attempt / archive_retry_count（幂等，可重复执行）。 |
| 17 | `_migrate_v61_enum_status_defaults.py` | 61 | 从建表 DDL 中取出 `column ... DEFAULT <literal>` 的字面量（无则 None）。 |
| 18 | `_migrate_v62_notification_log_identity.py` | 62 | notification_log 追加 4 个通知身份列（幂等；列已存在则跳过）。 |
| 19 | `_migrate_v63_notification_log_task_view.py` | 63 | notification_log 追加 4 个任务视角列（幂等；列已存在则跳过）。 |
| 20 | `_migrate_v64_notification_log_interactive.py` | 64 | notification_log 追加 4 个交互能力列（幂等；列已存在则跳过）。 |
| 21 | `_migrate_v65_notification_log_task_kind.py` | 65 | notification_log 追加 task_kind 列（幂等；列已存在则跳过）。 |
| 22 | `_migrate_v66_announcement_record_final_name.py` | 66 | announcement_record 补 final_name 列 + 从 pending_lookup 回填（幂等）。 |
| 23 | `_migrate_v67_notification_log_failed_items.py` | 67 | notification_log 补 failed_items 列（TEXT 存 JSON，默认 '[]'；探测式幂等）。 |
| 24 | `_migrate_v68_notification_policy_event_classes.py` | 68 | notification_policy 补 `event_classes` 列（TEXT 存 JSON，默认 '[]'；探测式幂等）。 |
| 25 | `_migrate_v69_reheal_notification_credentials.py` | 69 | 自愈通知渠道凭据：标记说"已迁移"但 DB 里缺渠道时，从 config.json 重做一次。 |
| 26 | `_migrate_v70_announcement_record_language.py` | 70 | 为 announcement_record 增加 language / foreign_name，并把唯一键扩展为含语种。 |
| 27 | `_migrate_v71_notification_user_id.py` | 71 | 为 notification_log / notification_queue 增加 user_id（A-21 数据模型层）。 |
| 28 | `_migrate_v72_announcement_dedupe.py` | 72 | v72：把 `announcement_record.standard_number` 归一化到全项目唯一实现的口径，并重算 |
| 29 | `_migrate_v73_normalize_timestamps.py` | 73 | v73：把历史表中的裸时间字符串规范为 ISO 8601 带时区偏移量。 |
| 30 | `_migrate_v74_repair_validity_keys.py` | 74 | v74：修复 standard_validity 前导空格/缺代号畸形键；冲突合并、无匹配保留、幂等。 |
| 31 | `_migrate_v75_validity_queue.py` | 75 | v75：补建 validity_check_queue（选中文件检查队列）。 |

## 三、迁移链要点

- `_schema_version` 记录 `version` + `checksum`；迁移函数源码受 P-106 约束，不可改已执行迁移。
- 迁移文件不是“一版一个文件”：`_migrate_v16_v49.py` 一个文件注册了多个版本；按版本号看，不按文件数看。
- 最近六项：v70 language/foreign_name；v71 notification user_id；v72 公告标准号归一化；v73 时间字符串 ISO 化；v74 validity 畸形键修复；v75 选中文件检查队列。
- 新增迁移必须带幂等/断言/回滚说明；生产执行前先 dry-run + 备份。

## 四、与文档的关系

- 本文是“表/迁移清单”；字段语义/读写方见 `04-data-model.md`。
- 任何 Schema 变更都要同步 `docs/architecture.md`（AGENTS §8.2）并跑 `generate_capabilities.py`。
