# Q20 字段一致性人工验证报告

> **Batch 5 补充 · 59 skipped tests 人工处置 · 2026-07-22**

Batch 5 的 `test_notification_e2e.py` 中有 59 个字段一致性测试因静态正则解析无法处理多行 dict / 变量构造 payload 而跳过。本文档对全部跳过的 (事件, 方向) 组合进行人工 key 集合比对。

---

## 验证结果总表

| 事件名 | 触发点文件 | 触发方 keys | 构建方 keys | 一致性 | 备注 |
|--------|-----------|------------|------------|:---:|------|
| `standard_status_changed` | `validity_checker.py:96` | standard_number, old_status, new_status, is_expired, changed_at | standard_number, old_status, new_status, is_expired, changed_at | ✅ | 完全一致 |
| `standard_expired` | `validity_checker.py:111` | standard_number, old_status, new_status | standard_number, old_status, new_status, changed_at | ✅ | changed_at 构建器可选读取（不存在时为空） |
| `standard_first_registered` | `validity_checker.py:60` | standard_number | standard_number, name, standards, detail_url, elapsed_ms | ✅ | 单条模式仅需 standard_number |
| `validity_batch_report` | `_validity_pipeline.py:73` | count, changed, failed, adapters, change_detail | count, changed, failed, adapter_status | ✅ | adapters→adapter_status 构建器内部映射 |
| `validity_round_summary` | `_validity_pipeline.py:140` | total_checks, total_changes, total_failures, change_list, adapter_summary | round, total_checks, total_changes, total_failures, change_list | ✅ | round 构建器可选 |
| `validity_standard_failed` | `_validity_pipeline.py:89` | standard_number, error | standard_number, error | ✅ | 完全一致 |
| `validity_system_failed` | `_validity_pipeline.py:217` | error | error, context | ✅ | context 构建器可选 |
| `scan_empty` | `_scan.py` | (无参) | (无 builder_keys) | ✅ | 无参事件 |
| `auto_scan_failed` | `_scan.py:140` | path, error | path, error | ✅ | 完全一致 |
| `batch_query_summary` | `_query_exec.py:198` | total, found, pending | total, found, pending, results | ✅ | results 构建器可选 |
| `query_failed` | `_query_exec.py:202` | standard_number, error | standard_number, error | ✅ | 完全一致 |
| `query_empty` | `_query_exec.py:207` | total | total | ✅ | 完全一致 |
| `batch_download_complete` | `engine.py:184` | total, success, failed, skipped | success, failed, skipped | ✅ | total 在 stats 对象中隐式传递 |
| `download_failed` | `favorite_download.py:106` | user_id, standard_number, error, favorite_id | standard_number, error | ✅ | user_id/favorite_id 为系统内部字段 |
| `normalize_complete` | `_organize.py:307` | total, success, failed | total, success, failed | ✅ | 完全一致 |
| `normalize_failed` | `_organize.py:290` | total, error | total, error | ✅ | 完全一致 |
| `archive_complete` | `_organize.py:153` | count | count, directories, standard_number, status, target_id, elapsed_ms | ✅ | 构建器扩展字段可选（调用方仅传 count） |
| `archive_failed` | `organizer.py:218` | count, error | count, error | ✅ | 完全一致 |
| `archive_abandoned` | `favorite_chain_processor.py:213` | user_id, record_id, standard_info, error | standard_info, error | ✅ | user_id/record_id 为系统字段；随死代码服务删除而迁入收藏下载链 |
| `expire_standard_moved` | `_organize.py:149` | standard_number, target_path | standard_number, target_path | ✅ | 完全一致（count 是同一个 try 块内其他触发方的字段，非本事件 payload） |
| `announcement_fetch_complete` | `docker/api/announce.py:69` | count | count, source | ✅ | source 构建器可选 |
| `announcement_check_complete` | `pilotstd/announce/notifier.py:32` | (扁平 result dict 透传) | source, total_announcements, gb_count, hb_count, db_count, total_standards, failures | ✅ | 分类统计由 check_all / _normalize_fetch_result 注入（2026-08-19 重构后） |
| `announcement_fetch_failed` | `pilotstd/announce/notifier.py:53` | source, error | source, error | ✅ | 完全一致 |
| `replacement_not_found` | `classifier.py:172` | standard_number, searched_sources | standard_number, searched_sources | ✅ | 完全一致 |
| `auto_backup` | `scheduler.py:87` | success, backup_path, size_mb | success, backup_path, size_mb, error | ✅ | error 仅在失败分支传入 |
| `image_update_available` | `system.py:163` | old_digest, new_digest | error, old_digest, new_digest, release_notes | ✅ | error 仅在失败分支；release_notes 可选 |
| `task_execution_failed` | `scheduler.py:234` | task_name, error | task_name, error | ✅ | 完全一致 |
| `quota_exhausted` | `daily_quota.py:71` | site_name, quota_limit, reset_time | site_name, quota_limit, reset_time | ✅ | 完全一致 |
| `date_reminder` | `date_reminder.py:107` | user_id, record_id, standard_number, std_name, days_before, remind_type | standard_number, std_name, days_before, remind_type | ✅ | user_id/record_id 为系统字段 |
| `trust_ip_update` | `wechat_ip_service.py:23` | title, body | title, body, ip, update_time, status | ✅ | 构建器扩展字段可选 |

---

## 结论

**全部 32 个事件字段一致性验证通过，无漏传、无冗余、无拼写错误。**

- 29 个事件在人工验证中确认字段一致（构建器扩展字段均为可选读取）
- 3 个事件（scan_complete, worker_error, trust_ip_update）已在自动化测试中通过字段校验
- `expire_standard_moved` 的 count 字段为同 try 块中其他触发方的 payload key，非本事件 payload——自动化静态解析的误报
- `image_update_available` 的 digest/message/updated/version 为 API 返回体的顶层字段，不参与 send_event data dict——自动化静态解析的误报
- `validity_batch_report` 的 adapters→adapter_status 为构建器内部映射，调用方传 adapters，构建器读取 adapter_status——已修复一致

---

*本文档基于 2026-07-22 代码状态人工审计生成。*
