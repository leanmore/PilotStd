# 事件通知全链路审计报告（Vibe Coding 治理样板 · 第一批）

- **审计日期**：2026-08-24
- **审计方式**：只读静态分析 + 生产 API 实证 + 本地复现脚本（零业务代码改动，`git status` 零差异）
- **审计范围**：`pilotstd/core/notification/` 全链路 + 全部 `send_event` 调用点（pilotstd/ + docker/）
- **阻断问题**：公告拉取后通知报 `HTTP 400: Bad Request: message text is empty`
- **复用能力**：`scripts/audit_notification_chain.py`（纯标准库静态审计，`--module` 可复用）

---

## 一、执行摘要

> **一句话结论**：阻断问题的直接根因是**聚合器合并消息时丢失 `blocks`（仅保留空 `body`），导致 Telegram 渲染出空文本**；`favorite_created` 因 `bypass_aggregation=True` 走直发路径保留 `blocks` 所以成功，而公告类事件走聚合路径全部失败——这是同一个聚合缺陷对不同事件的差异化暴露。

**关键发现**（按严重度）：

| # | 严重度 | 问题 | 位置 |
|---|--------|------|------|
| F-01 | 🔴 P0 | 聚合器 `_send_merged` 构造合并消息时**只保留 `body`、丢弃 `blocks`**，单条聚合 `format_summary` 返回原始 `body`（恒为空串）→ 渲染空文本 → Telegram 400 | `aggregate_buffer.py:196-218` |
| F-02 | 🟠 P1 | `renderer.render()` 在 `blocks` 为空时回退 `message.body`，**无空文本兜底/校验** | `renderer.py:38-41` |
| F-03 | 🟠 P1 | 测试消息路径 `do_test_send` 从 config.json 读凭证、跳过 enabled/聚合，与事件路径（DB 凭证 + 聚合）**双源不一致**，掩盖了真实故障 | `_format_utils.py:44-117` |
| F-04 | 🟡 P2 | `manager.py:88` `except Exception: pass` 吞掉 CredentialHelper 初始化错误（静默降级，无日志） | `manager.py:85-89` |
| F-05 | 🟡 P2 | `telegram.py:70` 读取 400 响应体时内层 `except Exception: pass` 吞错 | `telegram.py:67-79` |
| F-06 | 🟢 P3 | 数据模型无独立 `standard_type` 字段，gb/hb/db 靠 `source_site` 命名约定（`announcement_gb/hb/db`）区分 | `announcement_record.source_site` |

---

## 二、阻断问题现场快照（Phase 0）

### 2.1 现场证据（生产 API `GET /api/notification/logs`，2026-08-24 采集）

**最近两条失败记录（当前阻断问题）**：

| id | event_type | channel | title | body | status | error_msg | sent_at |
|----|-----------|---------|-------|------|--------|-----------|---------|
| 670 | announcement_fetch_complete | telegram | 公告拉取完成 | ``(空)`` | failed | `HTTP 400: Bad Request: message text is empty` | 2026-08-24T12:34:16.215070 |
| 669 | announcement_check_complete | telegram | 公告检查完成 | ``(空)`` | failed | `HTTP 400: Bad Request: message text is empty` | 2026-08-24T12:34:15.376042 |

**同窗口对照组（证明凭证/渠道/渲染正常，问题特定于聚合路径）**：

| id 范围 | event_type | status | 说明 |
|---------|-----------|--------|------|
| 652–668 | favorite_created | **success ×17** | 2026-08-24 12:21–12:31 全部成功 |
| 639–648 | favorite_created | failed ×10 | 2026-08-23 09:24–09:27（Fernet 凭证时代，`发送失败`） |

**时间线证据（Fernet 修复前 → 后）**：

| 日期 | 事件 | 结果 | 错误文案 |
|------|------|------|---------|
| 08-20 ~ 08-23 | announcement_* / favorite_created | 全部 failed | `发送失败`（凭证损坏，错误被吞） |
| 08-24 12:21–12:31 | favorite_created | success ×17 | —（Fernet 修复 + 新版 telegram 透传 last_error） |
| 08-24 12:34 | announcement_check_complete / fetch_complete | **failed** | `HTTP 400: Bad Request: message text is empty`（新版暴露真实根因） |

### 2.2 触发点代码位置

| 事件 | 触发点 | 文件:行号 |
|------|--------|----------|
| announcement_check_complete | `check_announce` 手动路径 | `docker/api/announce.py:68` |
| announcement_check_complete | `AnnounceNotifier.after_fetch` 定时路径 | `pilotstd/announce/notifier.py:37` |
| announcement_fetch_complete | `check_announce` 手动路径（仅手动） | `docker/api/announce.py:70-73` |
| favorite_created | `POST /api/favorites` 收藏成功 | `docker/api/favorites.py:150-158` |

### 2.3 触发时 payload 实际内容

**announcement_check_complete（手动路径，announce.py:64-68）**：
```python
stats = _get_check_stats(mgr.db, check_start)   # total_announcements/total_standards/gb_count/hb_count/db_count...
stats["failures"] = failure_count
stats["source"] = "手动"
mgr.notification_mgr.send_event("announcement_check_complete", stats)
```

**announcement_fetch_complete（announce.py:70-73）**：
```python
mgr.notification_mgr.send_event(
    "announcement_fetch_complete",
    {"count": stats["total_announcements"], "source": stats["source"]},
)
```

### 2.4 数据库状态确认

- **本地 DB**（`data/pilotstd.db`，开发环境）：`notification_log` **0 行**、`notification_queue` **0 行**——本地数据不可靠（AGENTS.md 声明）。
- **生产 DB**（容器 `bec3f327baf2`）：`notification_log` 共 38 条，事件发送**与公告入库无时序依赖**（公告先入库、统计后发事件，非事务内触发）——**排除"触发在事务提交之前"假设**。
- 生产 `notification_policy`：telegram 订阅 35 个事件（含 announcement_check_complete / announcement_fetch_complete / favorite_created 等）。
- 生产配置：`enabled=true`、telegram `chat_id=-1002647786159`、`aggregate_enabled=true`（本地 config 佐证，生产行为符合聚合窗口 5s）。

---

## 三、事件-构建器映射表（Phase 1.2）

> 事件定义 SSOT：`pilotstd/core/notification/events.py`（`ALL_EVENTS`，35 个事件）。构建器映射：`manager.py:322-359` `_EVENT_BUILDERS`。构建器实现分布在 `_builders_batch.py`（20 个）、`_builders_system.py`（10 个）、`_builders_validity.py`（7 个），重导出至 `_message_builders.py`。**实测无装饰器映射，全部为显式 dict**。

| 事件名 | 构建器函数 | 位置 | bypass | payload schema（实际读取字段） |
|--------|-----------|------|--------|------------------------------|
| archive_complete | `_build_archive_complete_message` | `_builders_system.py:28` | — | count, directories, standard_number, status, target_id, elapsed_ms |
| standard_status_changed | `_build_standard_status_changed_message` | `_builders_validity.py:21` | — | standard_number, old_status, new_status, is_expired, changed_at |
| standard_expired | `_build_standard_expired_message` | `_builders_validity.py:50` | — | standard_number, old_status, changed_at |
| standard_first_registered | `_build_standard_first_registered_message` | `_builders_validity.py:73` | — | standards[]/standard_number, name, detail_url, elapsed_ms |
| announcement_fetch_complete | `_build_announcement_fetch_complete_message` | `_builders_batch.py:27` | — | count, source |
| announce_fetch_summary | `_build_announce_fetch_summary_message` | `_builders_batch.py:378` | ✅ | adapters[], total_count, has_error |
| auto_backup | `_build_auto_backup_message` | `_builders_system.py:60` | ✅ | success, backup_path, size_mb, error |
| announcement_check_complete | `_build_announcement_check_complete_message` | `_builders_system.py:87` | — | source, total_announcements, gb_count, hb_count, db_count, total_standards, failures |
| batch_download_complete | `_build_batch_download_complete_message` | `_builders_batch.py:41` | — | success, failed, skipped |
| batch_query_summary | `_build_batch_query_summary_message` | `_builders_batch.py:69` | — | total, found, pending, results[] |
| auto_scan_failed | `_build_auto_scan_failed_message` | `_builders_batch.py:101` | ✅ | path, error |
| validity_batch_report | `_build_validity_batch_report_message` | `_builders_validity.py:112` | — | count, changed, failed, adapter_status |
| validity_round_summary | `_build_validity_round_summary_message` | `_builders_validity.py:144` | — | round, total_checks, total_changes, total_failures, change_list[] |
| validity_standard_failed | `_build_validity_standard_failed_message` | `_builders_validity.py:176` | — | standard_number, error |
| validity_system_failed | `_build_validity_system_failed_message` | `_builders_validity.py:193` | ✅ | error, context |
| image_update_available | `_build_image_update_available_message` | `_builders_system.py:138` | ✅ | error / old_digest, new_digest, release_notes |
| trust_ip_update | `_build_trust_ip_update_message` | `_builders_system.py:172` | ✅ | title, body, ip, update_time, status |
| worker_error | `_build_worker_error_message` | `_builders_system.py:191` | ✅ | worker, error, traceback |
| download_failed | `_build_download_failed_message` | `_builders_batch.py:115` | ✅ | standard_number, error |
| archive_abandoned | `_build_archive_abandoned_message` | `_builders_batch.py:200` | ✅ | standard_info, error |
| favorite_created | `_build_favorite_created_message` | `_builders_batch.py:130` | ✅ | standard_no, standard_name |
| download_started | `_build_download_started_message` | `_builders_batch.py:157` | — | standard_number |
| download_complete | `_build_download_complete_message` | `_builders_batch.py:177` | — | standard_number, local_path |
| normalize_complete | `_build_normalize_complete_message` | `_builders_batch.py:215` | — | total, success, failed |
| scan_complete | `_build_scan_complete_message` | `_builders_batch.py:236` | — | count, failed |
| task_execution_failed | `_build_task_execution_failed_message` | `_builders_system.py:211` | ✅ | task_name, error |
| date_reminder | `_build_date_reminder_message` | `_builders_batch.py:252` | — | standard_number, std_name, days_before, remind_type |
| scan_empty | `_build_scan_empty_message` | `_builders_batch.py:274` | — | （无） |
| query_failed | `_build_query_failed_message` | `_builders_batch.py:285` | ✅ | standard_number, error |
| query_empty | `_build_query_empty_message` | `_builders_batch.py:301` | — | total |
| archive_failed | `_build_archive_failed_message` | `_builders_batch.py:313` | ✅ | count, error |
| announcement_fetch_failed | `_build_announcement_fetch_failed_message` | `_builders_system.py:227` | ✅ | source, error |
| normalize_failed | `_build_normalize_failed_message` | `_builders_batch.py:326` | ✅ | total, error |
| expire_standard_moved | `_build_expire_standard_moved_message` | `_builders_batch.py:339` | — | standard_number, target_path |
| replacement_not_found | `_build_replacement_not_found_message` | `_builders_batch.py:358` | ✅ | standard_number, searched_sources[] |
| quota_exhausted | `_build_quota_exhausted_message` | `_builders_system.py:240` | ✅ | site_name, quota_limit, reset_time |
| （未注册 fallback） | `_build_fallback_message` | `_builders_system.py:122` | — | 任意 event_type + data |

> 注：`events.py` 中的 `ALL_EVENTS` 有 35 项，其中 `standard_status_changed` 等已注册；`EVENT_*` 常量与 `ALL_EVENTS` 字符串一致（已验证无漂移）。

### 调用点 payload 匹配核验（Phase 1.4）

| 触发点 | 事件 | payload 字段 | 与 builder 读取一致？ |
|--------|------|-------------|----------------------|
| `docker/api/announce.py:68` | announcement_check_complete | stats 全字段 + failures + source | ✅ |
| `docker/api/announce.py:70` | announcement_fetch_complete | count, source | ✅ |
| `pilotstd/announce/notifier.py:37-50` | announcement_check_complete | source/total/gb/hb/db/failures | ✅ |
| `pilotstd/announce/notifier.py:75` | announce_fetch_summary | build_fetch_summary(adapters) | ✅ |
| `docker/api/favorites.py:150-158` | favorite_created | standard_no, standard_name | ✅ |
| `pilotstd/tasks/favorite_download.py:106/129/151` | download_failed/started/complete | standard_number, error, local_path | ✅ |
| `docker/scheduler.py:100/113` | auto_backup | success, backup_path, size_mb / error | ✅ |
| `pilotstd/core/_validity_pipeline.py:73/89/140/195` | validity_* | 各字段 | ✅ |
| `pilotstd/manager/facade/_query_subsystem.py:226/242/247` | query_failed/query_empty/batch_query_summary | 各字段 | ✅ |
| `pilotstd/manager/facade/_scan.py:69/74/142/147/170/175/183` | scan_complete/scan_empty/auto_scan_failed | 各字段 | ✅ |
| `pilotstd/manager/classifier.py:179` | replacement_not_found | standard_number, searched_sources | ✅ |
| `pilotstd/manager/archive_retry_service.py:133` | archive_abandoned | standard_info, error | ✅ |
| `pilotstd/core/task_status.py:78` + `docker/scheduler.py:258` | task_execution_failed | task_name, error | ✅ |
| `pilotstd/query/daily_quota.py:91` | quota_exhausted | site_name, quota_limit, reset_time | ✅ |
| `docker/api/system.py:144/185` | image_update_available | error / old_digest, new_digest | ✅ |
| `pilotstd/manager/organize/organizer.py:252` | archive_failed | count, error | ✅ |
| `pilotstd/manager/facade/_organize.py:164/172` | expire_standard_moved / archive_complete | 各字段 | ✅ |
| `pilotstd/wechat_ip_service.py:26` | trust_ip_update | title, body | ✅ |

**结论：全部 20+ 调用点 payload 与 builder 读取字段匹配，无 schema 不匹配的触发点。**

---

## 四、数据模型评估（Phase 1.3）

> **实测**：项目**无 SQLAlchemy Model**，数据层为原生 SQLite（`pilotstd/core/db/database.py` + 迁移脚本 `_migrate_*.py`）。以下基于实际建表 SQL。

| 表 | 关键字段 | 是否支撑 gb/hb/db 分类 |
|----|---------|----------------------|
| `announcement_record` | `source_site`（announcement_gb/hb/db）、`standard_number`、`source_type`（默认`网页解析`，v39 新增） | ✅ 通过 `source_site` 命名约定区分（`crawler_service.py:76-84`）；`source_type` 字段与分类**无关**（语义为抓取来源方式） |
| `announcements` | `source_site`、`parse_status` | ✅ 同上 |
| `user_favorites` | `record_id` → announcement_record | ⚠️ 间接（join 后按 source_site） |
| `favorite_downloads` | `standard_no`、`standard_name`、`record_id` | ⚠️ 间接 |
| `download_queue` | `standard_number`、`standard_name` | ❌ 无 source_site/standard_type，仅标准号 |
| `standards` | `code`（标准号）、`name` | ❌ 无分类字段 |

**【P0-模型缺陷标记】**：不存在独立 `source_type` / `standard_type` 枚举字段，gb/hb/db 依赖 `source_site` 字符串约定。**影响面**：收藏/下载链（favorite_downloads、download_queue）无法直接从本表区分国/行/地标，需 join `announcement_record` 或解析标准号前缀。**修复建议**（增量、非阻断）：迁移为 `favorite_downloads`/`download_queue` 增加 `standard_type` 列（'gb'/'hb'/'db'），由收藏落库时一并写入；存量数据按 `standard_no` 前缀回填（GB→gb、HG→hb、DB→db，需建立前缀映射表）。

---

## 五、构建器健壮性审查表（Phase 2）

> 方法：对 `manager._EVENT_BUILDERS` 全部 36 个构建器逐一核对四项检查。**共同结论**：所有构建器均不查库（无时序依赖 ✅）、均无 `except: pass`（纯函数无异常处理 ✅）、空值守卫与返回校验普遍缺失（P1）。

| 事件名 | 空值守卫 | 异常处理 | 返回校验 | 时序依赖 | 问题标记 |
|--------|:---:|:---:|:---:|:---:|---------|
| archive_complete | ⚠️ | ✅ | ❌ | ✅ | P2：count=0 有兜底文案，但 directories 元素为空 dict 时 ListBlock 渲染空行 |
| standard_status_changed | ⚠️ | ✅ | ❌ | ✅ | P2：std_no 空时 label 为空串 |
| standard_expired | ⚠️ | ✅ | ❌ | ✅ | P2：同左 |
| standard_first_registered | ✅ | ✅ | ❌ | ✅ | P1：standards 为空且无 standard_number 时 blocks 仍含"共 0 条"文案（不空但无意义） |
| announcement_fetch_complete | ⚠️ | ✅ | ❌ | ✅ | P1：blocks 恒 1 个 KeyValueBlock，不空 ✅ |
| announce_fetch_summary | ⚠️ | ✅ | ❌ | ✅ | P2：adapters 为空时仅"总计: 0" |
| auto_backup | ✅ | ✅ | ❌ | ✅ | P2：success 分支 KeyValueBlock value 可能空 |
| announcement_check_complete | ✅ | ✅ | ❌ | ✅ | P1：blocks 恒 6 个（来源+5 KV），直发不空；**聚合后为空（F-01）** |
| batch_download_complete | ⚠️ | ✅ | ❌ | ✅ | P2：value 全 0 也渲染（不空） |
| batch_query_summary | ⚠️ | ✅ | ❌ | ✅ | P2：results 内元素缺 number 时 KeyError 风险（无守卫） |
| auto_scan_failed | ⚠️ | ✅ | ❌ | ✅ | P2 |
| validity_batch_report | ✅ | ✅ | ❌ | ✅ | P2：全 0 时有"开始有效性检查"兜底 |
| validity_round_summary | ⚠️ | ✅ | ❌ | ✅ | P2 |
| validity_standard_failed | ⚠️ | ✅ | ❌ | ✅ | P2 |
| validity_system_failed | ⚠️ | ✅ | ❌ | ✅ | P2 |
| image_update_available | ✅ | ✅ | ❌ | ✅ | P2：old/new_digest 空时 StatusChangeBlock 渲染"→ " |
| trust_ip_update | ⚠️ | ✅ | ❌ | ✅ | P2：body 空时仅 title |
| worker_error | ✅ | ✅ | ❌ | ✅ | P2 |
| download_failed | ⚠️ | ✅ | ❌ | ✅ | P2 |
| archive_abandoned | ⚠️ | ✅ | ❌ | ✅ | P2 |
| favorite_created | ✅ | ✅ | ❌ | ✅ | P2：std_no/std_name 空时仍渲染"已加入下载队列"（不空） |
| download_started | ⚠️ | ✅ | ❌ | ✅ | P2：std_no 空时"标准号："空值 |
| download_complete | ⚠️ | ✅ | ❌ | ✅ | P2：同左 |
| normalize_complete | ⚠️ | ✅ | ❌ | ✅ | P2 |
| scan_complete | ⚠️ | ✅ | ❌ | ✅ | P2 |
| task_execution_failed | ✅ | ✅ | ❌ | ✅ | P2 |
| date_reminder | ⚠️ | ✅ | ❌ | ✅ | P2：days_before 空时渲染"还有 0 天" |
| scan_empty | ✅ | ✅ | ❌ | ✅ | P2 |
| query_failed | ⚠️ | ✅ | ❌ | ✅ | P2 |
| query_empty | ⚠️ | ✅ | ❌ | ✅ | P2 |
| archive_failed | ⚠️ | ✅ | ❌ | ✅ | P2 |
| announcement_fetch_failed | ✅ | ✅ | ❌ | ✅ | P2 |
| normalize_failed | ⚠️ | ✅ | ❌ | ✅ | P2 |
| expire_standard_moved | ⚠️ | ✅ | ❌ | ✅ | P2 |
| replacement_not_found | ✅ | ✅ | ❌ | ✅ | P2：sources 空有兜底文案 |
| quota_exhausted | ✅ | ✅ | ❌ | ✅ | P2 |
| fallback | ✅ | ✅ | ❌ | ✅ | P2 |

> 图例：✅ 达标；⚠️ 部分/默认值兜底；❌ 缺失。
> **无 builder 存在 `except: pass` 或错误吞没（全部为纯函数）**；**无 builder 查库（无时序依赖）**。

---

## 六、运行时日志分析报告（Phase 3）

### 6.1 生产 notification_log 统计（38 条全量）

| event_type | 失败 | 成功 | 典型 error_msg | 根因推断 |
|-----------|:---:|:---:|----------------|---------|
| announcement_check_complete | 5 | 0 | `HTTP 400: ... message text is empty`（最新）/ `发送失败`（历史） | **F-01 聚合丢 blocks → 空文本** |
| announcement_fetch_complete | 3 | 0 | 同上 | 同上 |
| favorite_created | 10 | 17 | `发送失败`（08-23 凭证时代） | 历史：Fernet 凭证损坏；08-24 起 bypass 直发成功 |
| scan_empty | 1 | 0 | `发送失败` | 走聚合 → 同 F-01（08-24 03:00，静音时段压制后补发） |
| task_execution_failed | 2 | 0 | `发送失败` / `HTTP 404: Not Found` | bypass 直发，404 疑为 Telegram 偶发/参数问题（待查） |

### 6.2 关键错误反向追踪

- `message text is empty` ×2（id 669/670，08-24 12:34）→ announcement_check_complete / announcement_fetch_complete → **聚合路径空文本**，与本地复现完全一致。
- 历史 `发送失败`（08-20~08-23）→ Fernet key 丢失时代，凭证解密失败被 `_credentials.py:55-56` 静默跳过 → 渠道初始化失败 → 通用文案掩盖真实原因。

### 6.3 error_msg 长度限制检查

- `notification_log.error_msg` 为 `TEXT`，**无长度限制**，不存在截断问题。
- **但存在"错误信息丢失"问题**：`manager.py:237` 在 `last_error` 为空时回退固定文案 `发送失败 (无详细错误)`；历史版本（08-23 前）更是直接写死 `发送失败`。本次能定位根因，得益于新版 `telegram.py` 透传 `HTTP {code}: {desc}`。**建议**：所有失败路径必须填充 `last_error`（渠道侧），管理层不再回退模糊文案。

---

## 七、问题清单（按严重度排序）

| # | 级别 | 位置 | 现状 | 修复建议 |
|---|------|------|------|---------|
| F-01 | 🔴 **P0 阻断** | `aggregate_buffer.py:196-218` | `_send_merged` 构造的合并消息只有 `body`（单条=原始空 body），`blocks` 全部丢失 → 聚合事件渲染空文本 | **方案 A（最小）**：`_send_merged` 合并时若 `len(entries)==1` 直接回调原始消息（不重建）；多条时用 `first_msg.blocks` + 摘要 body 重建。**方案 B（根治）**：`render()` 空文本兜底——渲染结果为空时回退 `title` 或抛错；并在 `format_summary` 单条分支返回 `title` 而非空 body |
| F-02 | 🟠 P1 | `renderer.py:38-41` | 无 blocks 时回退 body，body 也空则返回 `""`，无任何防护 | `render()` 末尾 `if not text: return self._render_title(...) or "（无内容）"`；Telegram 渠道发送前 `if not text: last_error=...; return False` |
| F-03 | 🟠 P1 | `_format_utils.py:44-117` | 测试路径读 config.json、跳过 enabled/聚合；事件路径读 DB 凭证 + 聚合。双源不一致 | 统一：`do_test_send` 也走 `_init_channels` 同源凭证读取；测试消息默认绕过聚合但保留与事件一致的渲染链路 |
| F-04 | 🟡 P2 | `manager.py:85-89` | CredentialHelper 初始化失败被 `except Exception: pass` 吞掉，无日志 | 改为 `logger.warning` 记录异常原因 |
| F-05 | 🟡 P2 | `telegram.py:67-79` | 响应体读取内层异常被吞 | 内层 `except Exception: pass` 改为记录原始异常；desc 提取失败回退 `str(e)` |
| F-06 | 🟢 P3 | 数据模型 | 无独立 standard_type 字段，gb/hb/db 靠 source_site 命名约定 | 迁移新增 `favorite_downloads.standard_type` / `download_queue.standard_type`（见 §四） |
| F-07 | 🟢 P3 | `aggregate_buffer.py:222-266` | `format_summary` 多条分支用 `m.body[:40]` 拼接，body 恒空时摘要只剩统计行 | 多条摘要优先用渲染后的 blocks 首行，或 builder 统一填充 body 字段 |

---

## 八、修复优先级排序

1. **阻断级（P0）**：F-01 聚合丢 blocks → 修复 `_send_merged`（方案 A 最小改动，先恢复公告事件）。
2. **数据一致性（P1）**：F-03 双源凭证统一（防止再出现"测试成功、事件失败"的割裂）。
3. **可观测性（P1）**：F-02 空文本防护 + F-04/F-05 错误透传（让下次故障直接可见）。
4. **优化项（P2/P3）**：F-06/F-07 模型字段与摘要质量（可排工单，不阻塞）。

---

## 九、存量数据迁移建议（如涉及加字段）

**适用场景**：采纳 F-06（新增 `standard_type` 列）时。

```sql
-- 迁移脚本草案（需在 pilotstd/core/db/_migrate_v*.py 注册）
ALTER TABLE favorite_downloads ADD COLUMN standard_type TEXT DEFAULT 'gb';
ALTER TABLE download_queue ADD COLUMN standard_type TEXT DEFAULT 'gb';
-- 存量回填（前缀映射，谨慎：GB→gb, GB/T→gb, HG→hb, DB→db, 其余按 source_site join 回填）
UPDATE favorite_downloads SET standard_type = 'hb' WHERE standard_no LIKE 'HG%';
UPDATE favorite_downloads SET standard_type = 'db' WHERE standard_no LIKE 'DB%';
```

> 执行要求：走既有迁移框架（`migrations.py` 注册 + 校验和），禁止手改生产库。

---

## 十、复现证据（本地模拟，零网络请求）

`data/_audit_repro.py`（临时脚本，已 gitignore）关键输出：

```
[A] announcement_check_complete: blocks 数=6, body='', 直发渲染=非空 ✅
[B] announcement_fetch_complete:  blocks 数=2, body='', 直发渲染=非空 ✅
[C] favorite_created (bypass 直发): blocks 数=3, 直发渲染=非空 ✅
[D] 聚合后消息（blocks 丢失，仅 body）: check 渲染='', fetch 渲染='' → 空文本=True 🔴
[E] format_summary 单条分支: return entries[0][0].body  ← 空串来源
```

**证据链**：builder 产出 blocks（非空）→ 直发渲染非空 → 生产 favorite_created（bypass）成功 ✅ → 聚合后仅剩空 body → 渲染空文本 → 生产 announcement_*（非 bypass）Telegram 400 ✅。根因锁定 `aggregate_buffer._send_merged`。

---

## 十一、审计方法学（可复用）

| 步骤 | 手段 | 产物 |
|------|------|------|
| 0. 现场取证 | 生产 API 拉取 notification_log 全量 + 触发点源码定位 + 时间线对照 | 现场快照 |
| 1. 地图建立 | 读 events.py / builders / manager 映射 / 全部调用点 | 事件-构建器映射表 |
| 2. 健壮性审查 | 36 个 builder 四项检查（空值/异常/空串/时序） | 审查表 |
| 3. 运行时实证 | 生产日志分组统计 + 本地复现脚本闭环 | 日志分析 |
| 4. 交付 | 报告 + `scripts/audit_notification_chain.py` | 双交付物 |

> **复用到收藏/下载/归档模块**：`python scripts/audit_notification_chain.py --module favorite`（或 `download`/`archive`）即可对指定前缀事件做同款静态审计；`--scope all` 可扩展到全库吞错扫描；`--json -o out.json` 输出结构化结果。报告模板（本文件）可作为统一审计骨架。

---

*本报告为只读审计产物，未修改任何业务代码；修复方案待人工确认后另行实施。*
