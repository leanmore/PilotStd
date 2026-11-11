# PilotStd 治理验收用例（Acceptance Cases）

> **性质**：治理对账的“什么叫没问题”定义。不是需求文档，也不是测试清单；每条用例给出**一个可执行操作 + 一句话通过判据 + 依赖的代码/表/配置**。
> **版本**：U36 / 2026-11-09
> **基线**：`main` @ `222c42c6`，`VERSION=0.181.1`，本地 schema v76。

---

## 0. 来源说明（必须先读）

### 0.1 W-001 缺失

本次工作要求读取“用户最初报的 6 个问题（W-001）”。实际检索结果：

- 全仓 `rg 'W-001|W001|W_001'`（含 `docs/`、代码、配置、日志）**零命中**；
- `git log --all -S "W-001"`、`git log --all -S "用户最初"` **零命中**；
- `D:\` 下按文件名 `*W-001*` 深度 4 **零命中**；
- `docs/.local/archive/2026-11-08/` 与 `docs/pending/` 也**没有** W-001 原文。

因此**不能声称“已按 W-001 原文验收”**。本文件采用可复核的替代口径：

> **把 `docs/onboarding/26-fix-dossiers.md` 的 D-01～D-06 六份 dossier 作为“六个原始问题”的现存书面投影**，并用 `08-known-boundaries.md`、`11-open-questions.md`、`docs/records/2026-10-22-open-issues-project.md`、`27-implementation-log.md` 交叉印证。六者恰好一一对应：
>
> | 替代编号 | 原始问题（dossier 现象） | 主要来源 |
> |---|---|---|
> | W1 | Web 五段式下载件不进入归档 | D-01 / 08 #1 / 27 §1 |
> | W2 | Docker monitor 只 scan+archive、空目录不清理 | D-02 / 08 #2 |
> | W3 | 无“过期作废”/有效性不落地 | D-03 / 27 §5 |
> | W4 | 通知聚合失效 / 页面与通知不一致 | D-04 / 11 Q8 / 27 §2 |
> | W5 | 路由 v2 采样为 0 | D-05 / 11 Q1 / 27 §6 |
> | W6 | 查询缓存不新鲜 | D-06 / 11 Q7 / 27 §4 |
>
> **若 W-001 原文与这六项不同，本文件的覆盖结论即失效，必须重跑第 1 步。** 这是本报告最大的单点不确定性，已在回传中列为“卡点”。

### 0.2 全量验证基线（2026-11-09 实测）

| 命令 | 结果 |
|---|---|
| `python -m pytest tests/ -q -n 8 -k "not gui"` | **6254 passed / 10 skipped / 399 subtests passed / 333.29s**；进程退出码 1 仅由 PowerShell 把子进程 stderr 的 `UnicodeDecodeError` 包成 `NativeCommandError` 所致，pytest 摘要无 FAILED/ERROR |
| `pytest` 定向 167 例（monitor/validity/notification/router_v2/download/pipeline/archive） | **167 passed** |
| `pnpm test`（前端全量，45 files） | **354 passed**；进程 exit 1 同样来自 stderr 的测试日志，不是断言失败 |
| `bash scripts/check_all.sh --fast --guards --local` | **EXIT 0**（PowerShell 直调会因 stderr 显示 exit 1，见 P2-10） |
| `check_g_032_doc_health.py` | 4 warning（STATUS 缺失 ×2、known-issues 22 天、gates 引用 `docs/architecture/architecture.md`） |
| `check_docs_drift.py`（G-052） | 违规 **0** |

> **读法**：单元/集成层“绿”不等于验收层“过”。本文件每条用例都单独标了当前证据强度。

---

## 1. 我定义“治理完成”的六个条件

不是“没有 bug”，而是下面六条同时成立：

1. **主链闭环**：一个文件从进入 Inbox 到归档，盘上位置、`file_index`、`standard_validity`、通知内容四者可对账；不存在“页面说成功、库里没有”。
2. **结论正确**：查询与时效性结论不得返回已过期/已 stale 的数据而不告知；任何“废止/搬移”必须有 L2 证据与回滚。
3. **失败可见**：异常不得以 `pass`/空 `return`/`debug` 静默收场；用户或运维至少有一个可见出口（UI 错误、warning 日志、失败通知）。
4. **隔离成立**：多用户下日志、未读数、偏好、投递不串号；非 admin 不能调用 admin 写端点。
5. **可恢复**：停止、重启、重试不会留下假成功、半搬移或“永远 running”的脏状态。
6. **可验证**：每条结论能落到测试/日志/DB 行/`/api/health` 版本；部署版本可核对，而不是靠本地 tag。

> 后文 7 条用例就是这六条的可执行化。用例数控制在 7 条：再少会漏掉“多用户/可恢复”这两类横切风险，再多会退化成测试清单。

---

## 2. 验收用例

### AC-1 批量一键闭环（覆盖 W1；关联 P0-01）

**一句话**：在 Inbox 放入 **20 个**可解析标准文件，从 Web「一键处理」跑完 scan→query→download→normalize→archive，所有 `exact` 且非采标项要么**下载成功并进入归档**（盘上分类目录 + `file_index` + `standard_validity` 均有记录），要么在待确认/失败清单里**逐条给出原因**；页面汇总数与 DB 行数一致，点「停止」只停在阶段边界且状态为 `stopped`。

**通过判据**

- `downloadResult.stats.total == 所有 exact 非采标项数`，不是 10；
- 每个 `status=success` 的 `saved_path` 都出现在归档结果中；
- `file_index` 行数增量 = 实际归档文件数（允许重复跳过，但必须计入 skipped 并说明）；
- 停止后 `pipeline_runs.status=stopped`，无下一阶段请求。

**依赖**

| 层 | 具体路径 |
|---|---|
| 前端 | `web/src/views/TaskView.vue:236-350`（`runPipeline`）、`:277`（`dlNums` 的 `.slice(0,10)`）、`:326`（`buildArchiveItems`）、`web/src/utils/taskPipeline.ts` |
| API | `docker/api/tasks.py`（scan/query/download/normalize/archive 五段与停止/恢复）、`docker/api/archive.py:61`、`docker/api/download.py` |
| 后端 | `pilotstd/manager/facade/_auto.py::auto_run`、`_organize.py::archive_standards`、`pilotstd/download/engine.py`、`pilotstd/organizer/mover.py` |
| 表 | `pipeline_runs`、`file_index`、`standards`、`standard_validity`、`pending_lookup`、`download_queue` |
| 配置 | `storage.inbox_dir`、`storage.root_dir`、`validity.auto_move_expired`（间接） |
| 测试/证据 | `web/src/views/TaskView.test.ts`（354 前端用例中的一部分）、`tests/test_api_tasks_endpoints.py`、`tests/test_download_task_persistence.py`、`tests/test_archive_reconcile.py` |

**当前证据强度**：**PASS（mock 全链）**。`TaskView.test.ts` 新增 20 条 exact 用例：`postDownload` 收到 20 个号、归档 payload 21 条（1 扫描件 + 20 下载件），并逐条断言 20 个 `saved_path` 都在归档 items 中。**未做**：真实 20 文件落库的端到端（现有归档/监控集成测试覆盖 mechanics，但没有 20 条同批）。

---

### AC-2 监控投放闭环（覆盖 W2；关联 P1-05）

**一句话**：向 Docker monitor 的 `watch_path` 连续投放 3 个文件（其中 1 个无法解析），主链按目录去抖只跑一轮：2 个进正确分类目录并写 `file_index`，1 个在监控状态/日志/通知里显式失败；归档后空目录被清理；**服务重启后“今日统计”不归零**。

**通过判据**

- 同一目录 10 秒内多次事件只触发一次 `auto_run`（日志只有一条“主链归档完成/失败”）；
- 无法解析的文件 `stats.failed` +1，且 `[MONITOR] 未识别到标准号` 可见；
- 空目录被删，非空目录不动；
- 重启后 `processed_today/success_today/failed_today` 等于重启前（允许跨日归零）。

**依赖**

| 层 | 具体路径 |
|---|---|
| 监控 | `pilotstd/monitor/scheduler.py:165-229`（`_on_file`、去抖/锁、`auto_run`、`_cleanup_empty_dirs`）、`pilotstd/monitor/config.py:76-154`（`MonitorStats`） |
| 主链 | `pilotstd/manager/facade/_auto.py::auto_run`、`_organize.py` |
| 表 | `monitor_stats`、`file_index`、`standards`、`notification_log` |
| 配置 | `auto_archive`、`monitor.watch_path`（由 `resolve_monitor_config` 解析） |
| 测试/证据 | `tests/integration/test_monitor_archive_e2e.py`、`tests/test_monitor_scheduler.py`、`tests/test_monitor_cleanup.py`（本次定向 167 例中通过） |

**当前证据强度**：**PASS（代码/集成）**；**待部署实测**。`monitor_stats` 的 DB 历史无读路径，重启会归零（P1-05）。

---

### AC-3 通知对账（覆盖 W4；关联 P1-02、P1-06、P2-13）

**一句话**：一次批量归档 + 一次 `warning` 事件后，每个启用渠道**恰好收到 1 条聚合消息**；Web 通知日志同一事件只显示 1 条且 `body` 含 count/skip/fail；同一用户 `unread-count` 等于 `is_read=false` 列表的 `total`；管理员 `all=true` 才看全库；非 admin 调用 admin 写端点返回 403。

**通过判据**

- 渠道消息数 = 1/事件/渠道，不是“每文件一条”；
- `notification_log.body` 对 `archive_complete` 非空，且含“已归档 N / 跳过 / 失败”；
- `GET /api/notification/unread-count` == `GET /api/notification/logs?is_read=false` 的 `total`（同一用户）；
- `all=true` 非 admin 返回 403；
- 关闭通知后历史仍可读（`_record_when_disabled`）。

**依赖**

| 层 | 具体路径 |
|---|---|
| 事件/聚合 | `pilotstd/core/notification/_dispatcher.py`、`notification_aggregator.py`、`batch.py`、`aggregate_keys.py` |
| 构建器 | `pilotstd/core/notification/_builders_batch.py`（`archive_complete` 正文）、`_builders_validity.py`（`validity_batch_report`）、`_builders_common.py` |
| 日志/未读 | `pilotstd/core/notification/_manager_ops.py:199-255`、`:313-338`、`_log_scope.py`、`docker/api/notification_logs.py:119-184`、`:274-287` |
| 表 | `notification_log`（`user_id/body/failed_items`）、`notification_queue`、`notification_policy`、`user_credentials` |
| 配置 | `notification.enabled`、`notification.channels.*`、`notification.rules.*`、`notification.quiet_hours_*`、`notification.aggregate_*` |
| 测试/证据 | `tests/test_notification_unread_isolation.py`、`tests/test_notification_logs_user_isolation.py`、`tests/test_api_tasks_endpoints.py`/`test_notification_api.py`（30 passed）、`tests/test_notification_e2e.py` |

**当前证据强度**：**PARTIAL**。日志/未读/权限已修并有测试；`validity_batch_report` 每 10 条的中间消息仍硬编码 `count=0, changed=10`（P1-02）；企微/钉钉/飞书真实发送未复测（P1-06）。

---

### AC-4 查询正确性与缓存新鲜度（覆盖 W5+W6；关联 P0-02）

**一句话**：查询一个 30 天前缓存过、且公告状态已变化的标准：返回**最新状态**或在 UI 明示 `stale`；`announcement_match` 的过期行不得作为命中；v2 路由对本次查询写入 `routing_version` 决策或 `v2_skipped` 原因；全程无静默异常。

**通过判据**

- `standard_info_cache`：`data_state='stale'` 不被当命中（已实现）；
- `announcement_match`：`data_state='stale'` 拒绝；`expires_at` 可解析时优先，缺失时按 `cached_at + active_ttl`（默认 30 天）判定；过期不得命中（**2026-11-09 已实现**）；
- `query.use_announcement_match=false` 时仍可能回退公告缓存的行为在文档中写清；
- `logs/router_v2_decisions.jsonl` 对每条查询至少有一条 `routing_version`（v1/v2/v2_skipped），且 `v2_skipped` 带 `reason`；
- 适配器异常被记录为 warning，不返回空结果冒充“未找到”。

**依赖**

| 层 | 具体路径 |
|---|---|
| 单条查询 | `pilotstd/query/engine/_single.py:179-330`（`_query_one`、`_query_one_v2`、`record_v2_skip`） |
| 缓存 | `pilotstd/query/cache.py:42-75`（`get`：主表 stale 检查 + 公告回退）、`:77-102`（`put` 置 fresh） |
| 公告缓存写入 | `pilotstd/announcement/matcher.py:459`（写 `expires_at`；**当前实际写 NULL**，TTL 以 `cached_at` 兜底） |
| 失效 | `pilotstd/core/cache_manager.py:150-160`（`invalidate_by_source`）、`manager/facade/_scan.py:95/183`、`docker/api/validity.py:272`、`announce/notifier.py:132` |
| 路由 | `pilotstd/query/routing/router_v2.py`、`router_v2_metrics.py`、`query/engine/_batch_dispatcher.py` |
| 表 | `standard_info_cache`、`announcement_match`、`data_source_versions`、`adapter_state`、`daily_quota` |
| 配置 | `query.use_cache`、`query.use_announcement_match`、`query.site_order`、`ROUTING_ENGINE_VERSION` |
| 测试/证据 | `tests/query/engine/test_single_v2_route.py`（v2 分支 11 例）、`tests/test_router_v2*.py`、`tests/test_query.py::TestCacheRepository`；本次定向 v2 覆盖 `_single.py` **79%** |

**当前证据强度**：**PASS（缓存层 + 查询链）**。`tests/test_query.py` 新增：31 天前 `cached_at` → `cache.get` miss；`data_state='stale'` miss；显式 `expires_at` 过期 miss；fresh hit；`TestQueryEngine` 全链用 30 天前“已废止”公告 + mock 适配器，返回“现行”而非旧公告。v2 已有 409 条本地样本、真实 ≥1000 条待验证（P3-06）。

---

### AC-5 时效性检查闭环（覆盖 W3；关联 P1-01、P1-02、P1-07）

**一句话**：定时和手动各跑一轮时效性检查：L2 判废止且 `auto_move_expired=true` 时文件移到「过期作废」、失败回滚；`standard_validity` / `validity_check_log` / `validity_check_queue` 状态一致；手动运行后页面计数与历史一致**或明示“本轮不计入”**；每 10 条变化的中间通知数字与最终报告一致。

**通过判据**

- L2 + 开关 true → 移动成功；任一文件移动失败 → 回滚且不写废止状态；
- `validity_check_queue` pending 被 drain，success/failed 可查；
- 手动 `/api/validity/run` 返回的 `checked/changed` 与 `validity_check_log` 新增行数一致；
- `validity.checked_count` 与 `round_completed` 不再出现“历史 15 天、计数 0”且无解释；
- 中间 `validity_batch_report` 的 `count/changed` 与累计值一致。

**依赖**

| 层 | 具体路径 |
|---|---|
| 检查器 | `pilotstd/core/validity_checker.py:75-86`（`should_apply_side_effects`）、`:88-236`（`update_status`/搬移/回滚）、`:240-332`（`_move_expired_file`/`_rollback_moves`） |
| 批次 | `pilotstd/core/_validity_pipeline.py:192-203`（每 10 条中间通知）、`:325-350`（最终报告）、`pilotstd/core/validity_log.py`、`manager/validity_service.py` |
| API | `docker/api/validity.py:61-134`（配置/计数）、`:250-280`（手动 run，`update_counters=False`） |
| 表 | `standard_validity`、`validity_check_queue`、`validity_check_log`、`file_index`、`download_queue` |
| 配置 | `validity.auto_move_expired`（**出厂默认 True**）、`check_ratio`、`batch_size`、`total_weeks`、`l2_concurrency` |
| 测试/证据 | `tests/test_validity_checker*.py`、`tests/test_validity_queue_v75.py`、`tests/core/test_validity_move_rollback.py`、`tests/test_validity_move_closure.py`（合并覆盖 93%）、`tests/test_migrate_v74_validity_keys.py` |

**当前证据强度**：**PARTIAL**。搬移/回滚/队列有测试；手动计数不更新（P1-01）、中间通知硬编码（P1-02）、默认开关与文档矛盾（P1-07）、4 条畸形键保留（P2-11）。

---

### AC-6 多用户与权限隔离（横切；关联 P2-13）

**一句话**：两个用户各自触发通知并查看日志：各自只看到自己的记录/未读数；user2 未绑定渠道时跳过且不发给 user1；非 admin 调 admin 端点 403；admin `all=true` 才跨用户。

**通过判据**

- `notification_log.user_id` 各归各；`get_logs`/`unread`/`mark_read` 同口径；
- user2 未绑定渠道 → `channel not initialized`，不落 user1 日志；
- admin 默认看“自己 + 系统通知”，`all=true` 才全库；
- 11 个未配置 `meta.permission` 的视图至少有可读的 403 处理；其中 `OrganizeView` 的 admin-only “加入有效性队列”对非 admin 不显示或明示无权限（当前审计：11 个未守卫）。

**依赖**

| 层 | 具体路径 |
|---|---|
| 鉴权 | `docker/auth.py`（`require_role`）、`docker/auth_middleware.py`、`docker/api/users.py`、`docker/api/auth_register.py` |
| 通知作用域 | `pilotstd/core/notification/_log_scope.py`、`_manager_ops.py`、`docker/api/notification_logs.py` |
| 表 | `users`、`user_credentials`、`user_preferences`、`notification_log.user_id`、`notification_policy`、`user_layouts` |
| 配置 | `notification.enabled`（偏好优先）、`notification.channels.*` |
| 测试/证据 | `tests/test_notification_unread_isolation.py`、`tests/test_notification_logs_user_isolation.py`、`tests/test_docker_auth.py`、`scripts/audit_api_matrix.py`（139 route/call pairs / 111 calls / write_without_admin=0 / unguarded_views=11） |

**当前证据强度**：**PARTIAL**。后端隔离有测试；多用户真实环境（A-35）仅验证到 2026-11-02 的部分项；前端 11 个视图无 permission 元数据（P2-13）。

---

### AC-7 失败可见与可恢复（横切；关联 P1-03、P1-04、P2-10）

**一句话**：任一阶段注入故障（DB 锁、网络超时、文件不可读）：UI 显示失败原因、日志有 warning/error 含上下文、任务状态为 `failed/interrupted` 而非假成功；服务重启后 `running→interrupted` 可 `resume/retry`；`/api/health` 的 `version/schema_version` 与构建一致。

**通过判据**

- 故障分支不得只 `pass`/空 `return`/`debug`；G-050 基线新增即阻断；
- `pipeline_runs` 启动时 `running/stopping→interrupted`，`resume` 只从阶段边界继续；
- 下载任务落 `task_queue`，重启可重试，超过 `max_retries` 保持 failed；
- `/api/health` 返回真实版本（`0.181.1`）与 `schema_version=76`，不是 `unknown`。

**依赖**

| 层 | 具体路径 |
|---|---|
| 健康 | `docker/api/health.py`、`pilotstd/__init__.py`、`VERSION` |
| 管道恢复 | `pilotstd/task/pipeline_store.py:84-127`、`docker/app.py:82`、`docker/api/tasks.py:251-270` |
| 下载恢复 | `pilotstd/download/task_store.py`、`download/engine.py:334`、`pilotstd/core/task/manager.py` |
| 静默错 | `scripts/silent_errors_baseline.json`、`scripts/check_g_050_silent_errors.py`、`gates.md` G-050 段 |
| 表 | `pipeline_runs`、`task_queue`、`batch_state`、`fetch_failures`、`monitor_stats` |
| 测试/证据 | 全量 6254 passed；G-050 基线 46/50/72；`tests/test_pipeline_store.py`、`tests/test_download_task_persistence.py`、`tests/test_app_startup_failfast.py` |

**当前证据强度**：**PARTIAL**。主链失败可见性总体好；`fetch_failures` / `batch_state` / `monitor_stats` 三个“写了没人读”的表让部分失败与状态不可见（P1-03/04/05）；测试/门禁进程退出码受 PowerShell stderr 影响（P2-10）。

---

## 3. 覆盖自检：7 条用例是否覆盖六个原始问题？

| 原始问题（替代编号） | 覆盖用例 | 是否遗漏 | 说明 |
|---|---|---|---|
| W1 Web 下载件不归档 | AC-1 | 否 | 同时暴露 10 条硬上限（P0-01） |
| W2 monitor 只 scan+archive | AC-2 | 否 | 去抖/清理/计数均入判据 |
| W3 有效性不落地 | AC-5 | 否 | 搬移/回滚/队列/计数全链 |
| W4 通知聚合/页面不一致 | AC-3 | 否 | 聚合、body、未读、权限 |
| W5 路由 v2 采样 0 | AC-4 | 否 | 决策与 `v2_skipped` 都要求 |
| W6 查询缓存不新鲜 | AC-4 | 否 | 主表 + 公告回退都要求 |
| 横切：多用户 | AC-6 | 不遗漏 | 六问题未单列，但通知/日志隔离是 W4 的必要条件 |
| 横切：可恢复/可观测 | AC-7 | 不遗漏 | 六问题的修复若不可见/不可恢复，等于没修 |

**有意不纳入验收的项（及理由）**

1. **非 GB / 采标 GB 下载**：设计边界 + 版权限制，无合法来源就不能靠验收倒逼（`08 #14`，P3-03）。
2. **Windows 托盘分流**：需 Windows 桌面实跑，CI 无法覆盖（A-22，P3-06）。
3. **真实渠道发送**：需企微/钉钉/飞书凭证与公网回调，属于部署验收而非代码验收（T-40/A-27.1，P1-06/P3-06）。
4. **v49 迁移清空偏好**：受 P-106 约束不可修，触发条件极窄（P3-01）。
5. **`.doc` OLE2 附件**：无样本、无用户反馈，已从静默升为 warning（P3-02）。

> 这五项“可遗漏”的共同理由：**不是主链必经路径，或修复代价 > 风险，或需要外部环境**；不是“忘了”。

---

## 4. U36 P0/P1 修复后执行记录（2026-11-09/10）

### AC-1 执行记录

| 步骤 | 实际操作 | 证据 |
|---|---|---|
| 1. 构造 | 20 个 `match_status='exact'`、`is_adopted=false` 的查询结果 | `TaskView.test.ts` 新增用例 |
| 2. 走链 | `TaskView` 点击开始 → scan → query → download → normalize → archive（API 全 mock，但链路完整） | 同上 |
| 3. 断言下载列表 | `mockPostDownload` 只调用 1 次，参数长度 **20**，首/末为 `GB/T 1-2020` / `GB/T 20-2020` | 同上 |
| 4. 断言归档 | `mockPostArchive` payload **21** 条（1 扫描件 + 20 下载件），20 个 `saved_path` 全在 | 同上 |
| 5. 结果 | **过（mock 全链）** | `vitest run src/views/TaskView.test.ts` → **5 passed**；前端全量 **355 passed** |

**残留**：真实 20 文件落库（`file_index`/`standard_validity`）未在同一用例执行；现有 `test_archive_reconcile.py`/`test_monitor_archive_e2e.py` 覆盖归档 mechanics。

### AC-4 执行记录

| 步骤 | 实际操作 | 证据 |
|---|---|---|
| 1. 构造旧公告 | `announcement_match` 插入 `GB/T 19001-2020`、状态“已废止”、`cached_at=31 天前`、`data_state='fresh'` | `test_expired_announcement_cache_falls_through_to_latest` |
| 2. 回退层 | `cache.get()` 返回 `None`（过期不命中） | 同用例 |
| 3. 查询链 | `QueryEngine.query_standards()` → mock 适配器返回“现行” | 同用例 |
| 4. 断言最新 | `r.status == 现行`、`r.source_site == mock_active`（不是旧公告的“已废止”） | 同用例 |
| 5. 结果 | **过（缓存层 + 查询链）** | `pytest tests/test_query.py` → **83 passed**；全量后端 **6259 passed / 10 skipped / 318.73s** |

**残留**：v2 真实 ≥1000 条样本；过期公告集中回源的生产网络压力（P3-06/P0-02 风险）未实测。

### AC-5 子场景执行记录（P1-01/P1-02，2026-11-10）

| 项 | 操作 | 证据 |
|---|---|---|
| P1-01 手动计数 | `POST /api/validity/run`（mock `do_check`）；断言 `update_counters=True` | `tests/test_api_validity_manual_counters.py` 2 例；相关 validity 套件 324 passed |
| P1-02 中间报告 | 12 个候选全部变化 → 第 10 条变化发中间报告 | `test_batch_notification_at_10_changes` 断言 `count=10/changed=10/failed=0` |
| 结果 | **AC-5 子场景过**；AC-5 整体仍 PARTIAL（P1-07 默认开关、P2-11 4 条畸形键） | 台账 §5.1 |

### 批量覆盖执行记录（2026-11-11，100 文件）

| AC | 场景 | 证据 | 结果 |
|---|---|---|---|
| AC-1 | Web 五段式 100 个 exact 项 | `TaskView.test.ts` 新增“100 个 exact 项全部进入下载与归档”：`postDownload` 100 个号、归档 101 条（1 扫描件 + 100 下载件） | **mock 批量过** |
| AC-2 | monitor 同目录 100 个文件 | `tests/integration/test_monitor_archive_e2e.py::test_100_files_archived_in_one_event`：一次 `_on_file` 归档 100 条、`file_index` 100 行、计数 processed=1/success=1 | **代码/集成批量过** |

> 仍不是生产级：AC 生产级覆盖 0/7；批量覆盖从 0/7 提升到 **2/7**（AC-1 mock、AC-2 集成）。

### 总体验证

| 项 | 结果 |
|---|---|
| 后端全量 | 6270 passed / 10 skipped / 399 subtests / 327.09s；进程 exit 1 仅 PowerShell stderr 包装，pytest 摘要无 FAILED |
| 前端四件套 | type-check 0；lint 0 error（既有 warning）；test 359 passed；build 成功 |
| 门禁 | `check_all --fast --guards --local` **EXIT 0**；`check_all --ci` **EXIT 0** |

---

## 5. 这份验收定义的局限（必须与结论一起读）

1. **W-001 原文缺失**：覆盖结论只对“D-01～D-06 重建的六问题”成立。
2. **生产不可达**：`192.168.1.18` 按文档不可达；本文件的“通过”只到本地/CI 层，生产部署版本与数据未核。
3. **GUI 未执行**：本地全量排除了 `tests/gui/`；Win 桌面与浏览器交互只到代码/单测层。
4. **人工验收未执行**：`docs/guides/人工测试方案.md` 的记录表 **全部 ⬜**，没有一份人工签署的端到端结果（P1-08）。
5. **时间窗**：所有实测截至 2026-11-10 19:32（Asia/Shanghai）；之后的新提交需重跑。
