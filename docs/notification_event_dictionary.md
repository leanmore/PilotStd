# PilotStd 通知事件字典

> **Q20 Final · 32 Events · Generated: 2026-07-22**

本文档是 Q20 事件通知系统全量重构的最终产物，记录全部 32 个通知事件的标准化规格。

---

## 事件总览

| 模块 | 事件数 | 事件列表 |
|------|:---:|------|
| 时效性检查 | 7 | standard_status_changed, standard_expired, standard_first_registered, validity_batch_report, validity_round_summary, validity_standard_failed, validity_system_failed |
| 扫描/导入 | 3 | scan_complete, scan_empty, auto_scan_failed |
| 查询 | 3 | batch_query_summary, query_failed, query_empty |
| 下载 | 2 | batch_download_complete, download_failed |
| 规范化 | 2 | normalize_complete, normalize_failed |
| 归档 | 4 | archive_complete, archive_failed, archive_abandoned, expire_standard_moved |
| 公告抓取 | 3 | announcement_fetch_complete, announcement_check_complete, announcement_fetch_failed |
| 废止处理 | 2 | expire_standard_moved, replacement_not_found |
| 系统运维 | 5 | auto_backup, image_update_available, worker_error, task_execution_failed, quota_exhausted |
| 用户交互 | 1 | date_reminder |

---

## 完整事件字典

### 1. 时效性检查 (7)

| 事件名 | 触发时机 | 级别 | 聚合/bypass | 字段规格 | 互斥/备注 |
|--------|---------|------|:---:|---------|---------|
| `standard_status_changed` | 标准状态发生变更（如现行→废止） | info/warning/error | 聚合 | `{"standard_number": "str [必填]", "old_status": "str [必填]", "new_status": "str [必填]", "is_expired": "bool [可选]", "changed_at": "str [可选]"}` | is_expired=True 时标题升级为 error |
| `standard_expired` | 标准确认废止（与 status_changed 同时触发） | error | 聚合 | `{"standard_number": "str [必填]", "old_status": "str [必填]", "new_status": "str [必填]"}` | 与 standard_status_changed 同时触发 |
| `standard_first_registered` | 新标准首次入库登记 | info | 聚合 | `{"standard_number": "str [必填]", "name": "str [可选]", "standards": "list [条件: 批量登记时]", "elapsed_ms": "int [可选]"}` | 支持单条/批量两种模式 |
| `validity_batch_report` | 批量有效性检查进度/完成 | info/warning | 聚合 | `{"count": "int [必填]", "changed": "int [必填]", "failed": "int [必填]", "adapter_status": "str [可选]"}` | 检查过程中每 10 条发送一次进度 |
| `validity_round_summary` | 单轮有效性检查汇总 | info | 聚合 | `{"round": "int [可选]", "total_checks": "int [必填]", "total_changes": "int [必填]", "total_failures": "int [必填]", "change_list": "list[str] [可选]"}` | 每轮检查完成时发送 |
| `validity_standard_failed` | 单条标准有效性检查异常 | error | 聚合 | `{"standard_number": "str [必填]", "error": "str [必填]"}` | 适配器查询失败/超时 |
| `validity_system_failed` | 有效性检查系统级异常 | error | bypass | `{"error": "str [必填]", "context": "str [可选]"}` | 数据库断开等致命异常 |

### 2. 扫描/导入 (3)

| 事件名 | 触发时机 | 级别 | 聚合/bypass | 字段规格 | 互斥/备注 |
|--------|---------|------|:---:|---------|---------|
| `scan_complete` | 扫描完成且有结果 | info(w/结果)/warning(w/o结果) | 聚合 | `{"count": "int [必填]", "failed": "int [必填]"}` | **互斥: scan_empty** (count>0→complete, count=0→empty) |
| `scan_empty` | 扫描完成但无结果 | info | 聚合 | `{}` (无参) | **互斥: scan_complete** |
| `auto_scan_failed` | 定时扫描异常 | error | bypass | `{"path": "str [必填]", "error": "str [必填]"}` | 手动扫描异常不触发此事件 |

### 3. 查询 (3)

| 事件名 | 触发时机 | 级别 | 聚合/bypass | 字段规格 | 互斥/备注 |
|--------|---------|------|:---:|---------|---------|
| `batch_query_summary` | 批量查询完成且有命中 | info/warning | 聚合 | `{"total": "int [必填]", "found": "int [必填]", "pending": "int [必填]", "results": "list [可选]"}` | **互斥: query_empty** (found>0→summary, found=0→empty) |
| `query_failed` | 单条标准查询异常 | error | bypass | `{"standard_number": "str [必填]", "error": "str [必填]"}` | 最多报 5 条防轰炸 |
| `query_empty` | 批量查询完成但全部未命中 | warning | 聚合 | `{"total": "int [必填]"}` | **互斥: batch_query_summary** |

### 4. 下载 (2)

| 事件名 | 触发时机 | 级别 | 聚合/bypass | 字段规格 | 互斥/备注 |
|--------|---------|------|:---:|---------|---------|
| `batch_download_complete` | 批量下载全部完成；**收藏下载链每次运行结束时也发此事件作为运行汇总** | info(w/o失败)/warning(w/失败) | 聚合 | `{"total": "int [必填]", "success": "int [必填]", "failed": "int [必填]", "skipped": "int [必填]"}` | skipped 含采标+已存在两种跳过；收藏链按批汇总即用此事件（一次运行 1 条，替代逐条 started/failed/complete） |
| `download_failed` | 收藏下载单文件失败 | error | 聚合（代码 v1.1 起无 bypass） | `{"standard_number": "str [必填]", "error": "str [必填]"}` | 仅收藏定时下载触发；批量路径默认按批汇总，逐条发由 `notify_per_record=True` 或 `download_to_inbox(notify=True)` 触发 |

### 5. 规范化 (2)

| 事件名 | 触发时机 | 级别 | 聚合/bypass | 字段规格 | 互斥/备注 |
|--------|---------|------|:---:|---------|---------|
| `normalize_complete` | 批量规范化完成 | info | 聚合 | `{"total": "int [必填]", "success": "int [必填]", "failed": "int [必填]"}` | success = len(results) |
| `normalize_failed` | 规范化流程异常 | error | bypass | `{"total": "int [必填]", "error": "str [必填]"}` | 异常后 re-raise 不改变原有行为 |

### 6. 归档 (4)

| 事件名 | 触发时机 | 级别 | 聚合/bypass | 字段规格 | 互斥/备注 |
|--------|---------|------|:---:|---------|---------|
| `archive_complete` | 归档完成（含 count=0） | info | 聚合 | `{"count": "int [必填]", "directories": "list[str] [可选]", "standard_number": "str [可选]", "elapsed_ms": "int [可选]"}` | count=0 时正文显示"未归档任何目录" |
| `archive_failed` | 部分文件归档失败 | error | bypass | `{"count": "int [必填]", "error": "str [必填]"}` | result["failed"]>0 时触发 |
| `archive_abandoned` | 重试上限（7 次）均失败，或业务终态跳过（采标版权受限 / 非国标） | error | bypass | `{"standard_info": "str [必填]", "error": "str [必填]"}` | 收藏下载链放弃分支 / 终态跳过分支触发（favorite_chain_processor；跳过分支一次即终态，不消耗重试窗口） |
| `expire_standard_moved` | 废止标准移入过期作废目录 | info | 聚合 | `{"standard_number": "str [必填]", "target_path": "str [必填]"}` | 与 archive_complete 同时触发，互不替代 |

### 7. 公告抓取 (3)

| 事件名 | 触发时机 | 级别 | 聚合/bypass | 字段规格 | 互斥/备注 |
|--------|---------|------|:---:|---------|---------|
| `announcement_fetch_complete` | 公告拉取完成 | info | 聚合 | `{"count": "int [必填]", "source": "str [可选]"}` | 仅手动路径触发（定时路径不发此事件） |
| `announcement_check_complete` | 公告检查完成 | info/warning/error | 聚合 | `{"source": "str [可选]", "total_announcements": "int [必填]", "gb_count": "int [必填]", "hb_count": "int [必填]", "db_count": "int [必填]", "total_standards": "int [必填]", "failures": "int [可选]"}` | 全失败→error，部分失败→warning |
| `announcement_fetch_failed` | 公告抓取全站点失败 | error | bypass | `{"source": "str [必填]", "error": "str [必填]"}` | total_announcements=0 且 failures>0 时触发 |

### 8. 废止处理 (1) — expire_standard_moved 见归档模块

| 事件名 | 触发时机 | 级别 | 聚合/bypass | 字段规格 | 互斥/备注 |
|--------|---------|------|:---:|---------|---------|
| `replacement_not_found` | 替代标准查找失败（所有适配器均未找到） | warning | bypass | `{"standard_number": "str [必填]", "searched_sources": "list[str] [条件: 非空时存在]"}` | searched_sources 为空时降级提示"未配置搜索源" |

### 9. 系统运维 (5)

| 事件名 | 触发时机 | 级别 | 聚合/bypass | 字段规格 | 互斥/备注 |
|--------|---------|------|:---:|---------|---------|
| `auto_backup` | 每周自动备份数据库 | info(成功)/error(失败) | bypass | `{"success": "bool [必填]", "backup_path": "str [条件: 成功时]", "size_mb": "float [条件: 成功时]", "error": "str [条件: 失败时]"}` | 每周日凌晨 3 点执行 |
| `image_update_available` | 镜像新版本可用 / 检查失败 | info/error | bypass | `{"error": "str [条件: 失败时]", "old_digest": "str [条件: 成功时]", "new_digest": "str [条件: 成功时]", "release_notes": "str [可选]"}` | 向下兼容: old_version/new_version 回退读取 |
| `worker_error` | 后台 Worker 线程异常 | error | bypass | `{"worker": "str [必填]", "error": "str [必填]", "traceback": "str [可选]"}` | pending_query_dialog 中的 Worker |
| `task_execution_failed` | APScheduler 定时任务执行异常 | error | bypass | `{"task_name": "str [必填]", "error": "str [必填]"}` | 全局 error listener 触发 |
| `quota_exhausted` | 适配器日配额首次耗尽 | warning | bypass | `{"site_name": "str [必填]", "quota_limit": "str [必填]", "reset_time": "str [必填]"}` | 每站点每日仅触发一次，跨天自动重置 |

### 10. 用户交互 (1)

| 事件名 | 触发时机 | 级别 | 聚合/bypass | 字段规格 | 互斥/备注 |
|--------|---------|------|:---:|---------|---------|
| `date_reminder` | 标准实施日期到期提醒 | info | 聚合 | `{"standard_number": "str [必填]", "std_name": "str [必填]", "days_before": "int [必填]", "remind_type": "str [必填]"}` | 提前 30/15/7/0 天各提醒一次 |
| `trust_ip_update` | 企业微信可信 IP 变更 | info/warning | bypass | `{"title": "str [必填]", "body": "str [必填]", "ip": "str [可选]", "update_time": "str [可选]", "status": "str [可选]"}` | "失败"关键词触发 warning 级别 |

---

## 互斥对显式标注

| 互斥对 | 条件 A | 条件 B |
|--------|--------|--------|
| `scan_complete` ↔ `scan_empty` | count > 0 | count = 0 |
| `batch_query_summary` ↔ `query_empty` | found > 0 | found = 0 |

## 同时触发事件

| 组合 | 场景 | 关系 |
|------|------|------|
| `standard_status_changed` + `standard_expired` | 标准状态变更为"已废止"时 | 同时触发，互不替代 |
| `archive_complete` + `expire_standard_moved` | 废止标准归档完成时 | expire_standard_moved 按废止条目逐条触发 |

## 聚合策略

| 策略 | 事件数 | 事件列表 |
|------|:---:|------|
| 聚合（aggregated） | 18 | archive_complete, standard_status_changed, standard_expired, standard_first_registered, validity_batch_report, validity_round_summary, validity_standard_failed, scan_complete, scan_empty, batch_query_summary, query_empty, batch_download_complete, normalize_complete, announcement_fetch_complete, announcement_check_complete, expire_standard_moved, date_reminder, (trust_ip_update=info 时) |
| 实时（bypass） | 14 | auto_scan_failed, query_failed, download_failed, normalize_failed, archive_failed, archive_abandoned, announcement_fetch_failed, replacement_not_found, auto_backup, image_update_available, worker_error, task_execution_failed, quota_exhausted, validity_system_failed |

## 事件构建器文件索引

| 文件 | 事件数 | 事件列表 |
|------|:---:|------|
| `_builders_system.py` | 8 | archive_complete, auto_backup, announcement_check_complete, fallback, image_update_available, trust_ip_update, worker_error, task_execution_failed, announcement_fetch_failed, quota_exhausted |
| `_builders_batch.py` | 16 | announcement_fetch_complete, batch_download_complete, batch_query_summary, auto_scan_failed, download_failed, archive_abandoned, normalize_complete, scan_complete, date_reminder, scan_empty, query_failed, query_empty, archive_failed, normalize_failed, expire_standard_moved, replacement_not_found |
| `_builders_validity.py` | 8 | standard_status_changed, standard_expired, standard_first_registered, validity_batch_report, validity_round_summary, validity_standard_failed, validity_system_failed |

---

*本文档由 Q20 第三批修复完成后自动生成，与代码状态一致。字段规格以构建器源码 `data.get()` 调用为准。*
